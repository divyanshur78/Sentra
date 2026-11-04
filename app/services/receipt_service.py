import re
import io
import subprocess
import tempfile
from pathlib import Path
from PIL import Image, ImageEnhance

try:
    import fitz
except ImportError:
    fitz = None

try:
    import pypdf
except ImportError:
    pypdf = None

from app.config import settings
from app.db import get_db
from app.utils import new_id, now_iso


def ocr_image_pil(img: Image.Image) -> str:
    """Extracts text from a photo/image using Windows 10/11 Native OCR via PowerShell, or pytesseract."""
    # 1. Try Windows 10/11 Native Media OCR via PowerShell
    try:
        script_path = Path(__file__).parent.parent / "utils" / "win_ocr.ps1"
        if script_path.exists():
            w, h = img.width, img.height
            proc_img = img

            # Optimize dimensions for OCR accuracy:
            # - If small (< 1000px), scale up so periods, commas, and small numbers aren't lost
            # - If excessively large (> 2400px), downscale for fast OCR throughput
            if max(w, h) > 2400:
                scale = 2400 / max(w, h)
                proc_img = proc_img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
            elif max(w, h) < 1000:
                scale = min(2.5, 1200 / max(w, h))
                proc_img = proc_img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)

            # Enhance contrast slightly to make black-on-white text crisp
            try:
                proc_img = ImageEnhance.Contrast(proc_img.convert("RGB")).enhance(1.4)
            except Exception:
                proc_img = proc_img.convert("RGB")

            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
                temp_path = Path(tf.name)
            try:
                proc_img.save(temp_path, format="PNG")
                cmd = [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy", "Bypass",
                    "-File", str(script_path),
                    "-ImagePath", str(temp_path)
                ]
                res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=15)
                if res.returncode == 0 and res.stdout.strip():
                    return res.stdout.strip()
            finally:
                if temp_path.exists():
                    try:
                        temp_path.unlink()
                    except Exception:
                        pass
    except Exception:
        pass

    # 2. Try pytesseract as fallback
    try:
        import pytesseract
        text = pytesseract.image_to_string(img)
        if text.strip():
            return text.strip()
    except Exception:
        pass

    return ""


def extract_text_from_pdf(data: bytes) -> str:
    """Extracts text from PDF documents, including both native text and scanned pages."""
    # 1. Try PyMuPDF (fitz)
    if fitz:
        try:
            doc = fitz.open(stream=data, filetype="pdf")
            pages_text = []
            for page in doc:
                t = page.get_text().strip()
                if t:
                    pages_text.append(t)
                else:
                    # Scanned page inside PDF: render to image and run OCR
                    try:
                        pix = page.get_pixmap(dpi=150)
                        page_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                        ocr_t = ocr_image_pil(page_img)
                        if ocr_t:
                            pages_text.append(ocr_t)
                    except Exception:
                        pass
            if pages_text:
                return "\n".join(pages_text)
        except Exception:
            pass

    # 2. Try pypdf fallback
    if pypdf:
        try:
            reader = pypdf.PdfReader(io.BytesIO(data))
            text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
            if text:
                return text
        except Exception:
            pass

    return ""


def extract_text(data: bytes, filename: str) -> str:
    """Extracts text from uploaded file: handles photos (.png, .jpg, .jpeg, .webp) and PDFs (.pdf)."""
    suffix = Path(filename).suffix.lower()

    # 1. PDF Documents
    if suffix == ".pdf":
        pdf_text = extract_text_from_pdf(data)
        return pdf_text.strip() if pdf_text else ""

    # 2. Photo / Image receipts
    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}:
        try:
            img = Image.open(io.BytesIO(data))
            img_text = ocr_image_pil(img)
            if img_text.strip():
                return img_text.strip()
        except Exception:
            pass
        return ""

    # 3. Plain text / fallback
    try:
        return data.decode("utf-8", errors="ignore").strip()
    except Exception:
        return ""


def classify_category(text: str) -> str:
    t = text.lower()
    # Alcohol check (strictly non-reimbursable) - use word boundaries to avoid false positives (e.g. 'forum' matching 'rum', 'engine' matching 'gin')
    alcohol_patterns = [
        r'\balcohol\b', r'\bwine\b', r'\bbeer\b', r'\bwhiskey\b', r'\bwhisky\b',
        r'\bvodka\b', r'\bspirits\b', r'\bliquor\b', r'\bcocktail\b', r'\bpub\b',
        r'\bbrewery\b', r'\btavern\b', r'\bscotch\b', r'\brum\b', r'\bgin\b'
    ]
    if any(re.search(pat, t) for pat in alcohol_patterns):
        return "alcohol"
    # Meal / Dining
    if any(x in t for x in ["restaurant", "cafe", "coffee", "tea", "dinner", "lunch", "food", "meal", "breakfast", "caffe", "pizza", "burger", "bakery", "kitchen", "swiggy", "zomato"]):
        return "meal"
    # Lodging / Hotel
    if any(x in t for x in ["hotel", "stay", "room", "accommodation", "lodging", "resort", "inn", "suites", "oyo", "marriott", "taj", "hyatt"]):
        return "lodging"
    # Flight / Airfare
    if any(x in t for x in ["flight", "airline", "airfare", "boarding", "indigo", "air india", "spicejet", "vistara", "emirates", "akasa"]):
        return "airfare"
    # Transport / Travel
    if any(x in t for x in ["taxi", "cab", "uber", "ola", "transport", "auto", "metro", "fuel", "petrol", "diesel", "parking", "toll", "irctc", "train"]):
        return "transport"
    # Software / Cloud
    if any(x in t for x in ["software", "saas", "subscription", "aws", "gcp", "azure", "github", "hosting", "cloud"]):
        return "software"
    # Office Supplies
    if any(x in t for x in ["office", "supplies", "stationery", "paper", "print", "courier", "staples"]):
        return "office supplies"
    return "other"


def parse_receipt(text: str) -> dict:
    """Parses extracted receipt text to find vendor, final total amount, expense date, and category."""
    if not text or not text.strip():
        return {
            "vendor": "Unknown vendor",
            "date": None,
            "amount": None,
            "category": "other",
            "confidence": 0.0
        }

    # Normalize common OCR character confusions on numbers & decimals (e.g. .OO -> .00)
    cleaned_text = re.sub(r'(\d+)\.([Oo0]{2})\b', r'\1.00', text)
    cleaned_text = re.sub(r'(?:INR|RS\.?|₹)\s*(\d+)\.([Oo0]{2})\b', r'INR \1.00', cleaned_text, flags=re.I)

    lines = [x.strip() for x in cleaned_text.splitlines() if x.strip()]
    if not lines:
        return {
            "vendor": "Unknown vendor",
            "date": None,
            "amount": None,
            "category": "other",
            "confidence": 0.0
        }

    # 1. Extract Vendor Name
    vendor = "Unknown vendor"
    noise_prefixes = [
        "TAX INVOICE", "INVOICE", "RECEIPT", "CASH MEMO", "BILL", "ORIGINAL",
        "CUSTOMER COPY", "MERCHANT COPY", "DATE:", "WELCOME", "TEL:", "PHONE:"
    ]
    for line in lines[:6]:
        cleaned = re.sub(r'[^\w\s&.\'-]', '', line).strip()
        if (
            cleaned
            and len(cleaned) >= 3
            and not any(cleaned.upper().startswith(p) for p in noise_prefixes)
            and not re.match(r'^\d', cleaned)
        ):
            vendor = cleaned[:60]
            break

    # If first lines were noisy, fall back to first line
    if vendor == "Unknown vendor" and lines:
        vendor = lines[0][:60]

    # 2. Extract Final Total Amount (NOT individual item amounts!)
    amount = None
    num_pat = r'(?<![0-9])([0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]{2})?|[0-9]+(?:\.[0-9]{2}))(?![0-9])'

    # Priority A: Look for explicit Grand Total / Net Payable / Final Total lines
    high_priority_keywords = [
        'GRAND TOTAL', 'FINAL TOTAL', 'NET PAYABLE', 'TOTAL PAYABLE',
        'NET AMOUNT', 'TOTAL DUE', 'BILL TOTAL', 'INVOICE TOTAL',
        'AMOUNT DUE', 'AMOUNT PAID', 'TOTAL AMOUNT'
    ]
    for i, line in enumerate(lines):
        line_upper = line.upper()
        if any(k in line_upper for k in high_priority_keywords):
            if any(x in line_upper for x in ['TOTAL QTY', 'TOTAL ITEMS', 'TOTAL COUNT', 'TOTAL DISCOUNT']):
                continue
            m = re.findall(num_pat, line)
            if m:
                val = float(m[-1].replace(',', ''))
                if val > 0:
                    amount = val
                    break
            # If the keyword was on its own line, check the next line
            if i + 1 < len(lines):
                next_line = lines[i + 1]
                m_next = re.findall(num_pat, next_line)
                if m_next and not any(k in next_line.upper() for k in ['DATE', 'INVOICE', 'GST', 'TAX', 'THANK']):
                    val = float(m_next[-1].replace(',', ''))
                    if val > 0:
                        amount = val
                        break

    # Priority B: Standard 'TOTAL' or 'BALANCE' lines (excluding subtotal / discount / items)
    if amount is None:
        for i, line in enumerate(lines):
            line_upper = line.upper()
            if re.search(r'\bTOTAL\b|\bBALANCE\b', line_upper) and not re.search(r'\bSUB\s*TOTAL\b|\bSUBTOTAL\b|\bDISCOUNT\b|\bITEMS?\b|\bQTY\b', line_upper):
                m = re.findall(num_pat, line)
                if m:
                    val = float(m[-1].replace(',', ''))
                    if val > 0:
                        amount = val
                        break
                if i + 1 < len(lines):
                    next_line = lines[i + 1]
                    m_next = re.findall(num_pat, next_line)
                    if m_next and not any(k in next_line.upper() for k in ['DATE', 'INVOICE', 'GST', 'TAX', 'THANK']):
                        val = float(m_next[-1].replace(',', ''))
                        if val > 0:
                            amount = val
                            break

    # Priority C: Scan all monetary amounts on the bill
    # When receipts have column tables (where 'Total' label is separated), the final total is the maximum of the charges
    if amount is None:
        all_matches = re.findall(num_pat, cleaned_text)
        if all_matches:
            vals = []
            for m in all_matches:
                try:
                    v = float(m.replace(',', ''))
                    if v > 0:
                        vals.append(v)
                except ValueError:
                    pass
            if vals:
                # The final total is the maximum monetary sum on the bill (greater than each item rate / line item)
                amount = max(vals)

    # 3. Extract Expense Date
    dm = re.search(r'\b(20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}[-/.]\d{1,2}[-/.]20\d{2})\b', cleaned_text)
    date_val = dm.group(1).replace('.', '-') if dm else None

    # Textual month support e.g. '20 Jan 2025' or 'Jan 20, 2025'
    if not date_val:
        from datetime import datetime
        m1 = re.search(r'\b(\d{1,2})\s+([A-Za-z]{3,9})\s+(20\d{2})\b', cleaned_text)
        if m1:
            try:
                d_str = f"{m1.group(1)} {m1.group(2)[:3]} {m1.group(3)}"
                date_val = datetime.strptime(d_str, "%d %b %Y").strftime("%Y-%m-%d")
            except Exception:
                pass
        else:
            m2 = re.search(r'\b([A-Za-z]{3,9})\s+(\d{1,2}),?\s+(20\d{2})\b', cleaned_text)
            if m2:
                try:
                    d_str = f"{m2.group(2)} {m2.group(1)[:3]} {m2.group(3)}"
                    date_val = datetime.strptime(d_str, "%d %b %Y").strftime("%Y-%m-%d")
                except Exception:
                    pass

    # 4. Classify Category
    category = classify_category(cleaned_text)

    confidence = 0.9 if (amount is not None and date_val and vendor != "Unknown vendor") \
        else (0.7 if amount is not None else 0.3)

    return {
        "vendor": vendor,
        "date": date_val,
        "amount": amount,
        "category": category,
        "confidence": confidence
    }


def save_receipt(employee_id: str, filename: str, data: bytes) -> dict:
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise ValueError("File exceeds upload size limit")

    text = extract_text(data, filename)
    parsed = parse_receipt(text)
    rid = new_id("rcpt")

    with get_db() as db:
        if not db.execute("SELECT id FROM employees WHERE id=?", (employee_id,)).fetchone():
            raise ValueError("Employee not found")

        db.execute(
            """INSERT INTO receipts
            (id,employee_id,filename,vendor,expense_date,amount,category,extracted_text,confidence,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                rid,
                employee_id,
                filename,
                parsed["vendor"],
                parsed["date"],
                parsed["amount"],
                parsed["category"],
                text,
                parsed["confidence"],
                now_iso(),
            ),
        )

    return {
        "id": rid,
        "receipt_id": rid,
        "filename": filename,
        "extracted_text": text[:4000],
        **parsed,
    }
