import re
import io
from pathlib import Path
from PIL import Image

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
    """Extracts text from a photo/image using Windows 10/11 Native OCR or pytesseract."""
    # 1. Try Windows 10/11 Native Media OCR
    try:
        import winrt.windows.media.ocr as ocr
        import winrt.windows.globalization as glob
        import winrt.windows.graphics.imaging as imaging
        import winrt.windows.storage.streams as streams

        # Limit max dimension for fast processing
        w, h = img.width, img.height
        max_dim = 2400
        if max(w, h) > max_dim:
            scale = max_dim / max(w, h)
            img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)

        rgba_img = img.convert('RGBA')
        writer = streams.DataWriter()
        writer.write_bytes(rgba_img.tobytes())
        sb = imaging.SoftwareBitmap.create_copy_from_buffer(
            writer.detach_buffer(),
            imaging.BitmapPixelFormat.RGBA8,
            rgba_img.width,
            rgba_img.height
        )

        eng = ocr.OcrEngine.try_create_from_language(glob.Language('en-US'))
        if not eng:
            eng = ocr.OcrEngine.try_create_from_user_profile_languages()

        if eng:
            op = eng.recognize_async(sb)
            res = op.get()
            if res and res.lines:
                lines = [line.text.strip() for line in res.lines if line.text.strip()]
                if lines:
                    return "\n".join(lines)
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
        if pdf_text.strip():
            return pdf_text.strip()

    # 2. Photo / Image receipts
    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}:
        try:
            img = Image.open(io.BytesIO(data))
            img_text = ocr_image_pil(img)
            if img_text.strip():
                return img_text.strip()
        except Exception:
            pass

    # 3. Plain text / fallback
    return data.decode("utf-8", errors="ignore")


def classify_category(text: str) -> str:
    t = text.lower()
    # Alcohol check (strictly non-reimbursable)
    if any(x in t for x in ["alcohol", "wine", "beer", "whiskey", "vodka", "spirits", "liquor", "cocktail", "pub", "bar "]):
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
    """Parses extracted receipt text to find vendor, total amount, expense date, and category."""
    lines = [x.strip() for x in text.splitlines() if x.strip()]
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

    # 2. Extract Total Amount
    amount = None

    # Priority A: Lines with explicit total / net amount / amount paid keywords
    total_line_patterns = [
        r'(?:GRAND\s*TOTAL|FINAL\s*TOTAL|NET\s*AMOUNT|TOTAL\s*AMOUNT|TOTAL\s*DUE|AMOUNT\s*PAID|BALANCE|TOTAL)[\s:=-]+(?:₹|INR|RS\.?|\$)?\s*([0-9,]+(?:\.[0-9]{1,2})?)',
        r'(?:TOTAL|AMOUNT)[\s:=-]+([0-9,]+(?:\.[0-9]{1,2})?)',
    ]
    for pattern in total_line_patterns:
        matches = re.findall(pattern, text, re.I)
        if matches:
            for m in reversed(matches):
                try:
                    val = float(m.replace(',', ''))
                    if val > 0:
                        amount = val
                        break
                except ValueError:
                    pass
        if amount is not None:
            break

    # Priority B: Explicit currency symbols (₹, INR, Rs., $)
    if amount is None:
        curr_matches = re.findall(r'(?:₹|INR|Rs\.?|\$)\s*([0-9,]+(?:\.[0-9]{1,2})?)', text, re.I)
        if curr_matches:
            for m in reversed(curr_matches):
                try:
                    val = float(m.replace(',', ''))
                    if val > 0:
                        amount = val
                        break
                except ValueError:
                    pass

    # Priority C: Scan lines from bottom up for numbers with decimals
    if amount is None:
        decimal_matches = re.findall(r'\b([0-9]{1,6}\.[0-9]{2})\b', text)
        if decimal_matches:
            try:
                candidates = [float(x) for x in decimal_matches if float(x) > 0]
                if candidates:
                    amount = max(candidates)
            except Exception:
                pass

    # 3. Extract Expense Date
    dm = re.search(r'\b(20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}[-/.]\d{1,2}[-/.]20\d{2})\b', text)
    date_val = dm.group(1).replace('.', '-') if dm else None

    # 4. Classify Category
    category = classify_category(text)

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
