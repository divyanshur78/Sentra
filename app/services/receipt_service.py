import re, io
from pathlib import Path
from PIL import Image
import fitz
from app.config import settings
from app.db import get_db
from app.utils import new_id, now_iso

def extract_text(data: bytes, filename: str) -> str:
    suffix=Path(filename).suffix.lower()
    if suffix==".pdf":
        doc=fitz.open(stream=data,filetype="pdf")
        return "\n".join(page.get_text() for page in doc)
    if suffix in {".png",".jpg",".jpeg",".webp"}:
        try:
            import pytesseract
            return pytesseract.image_to_string(Image.open(io.BytesIO(data)))
        except Exception:
            return ""
    return data.decode("utf-8",errors="ignore")

def classify_category(text):
    t=text.lower()
    if any(x in t for x in ["restaurant","cafe","dinner","lunch","food"]): return "meal"
    if any(x in t for x in ["hotel","stay","room"]): return "lodging"
    if any(x in t for x in ["flight","airline","boarding"]): return "airfare"
    if any(x in t for x in ["taxi","cab","uber","ola","transport"]): return "transport"
    if any(x in t for x in ["alcohol","wine","beer"]): return "alcohol"
    return "other"

def parse_receipt(text):
    amounts=re.findall(r"(?:₹|INR|Rs\.?|TOTAL\s*[:\-]?\s*)\s*([0-9,]+(?:\.[0-9]{1,2})?)",text,re.I)
    if not amounts: amounts=re.findall(r"\b([0-9,]+\.[0-9]{2})\b",text)
    amount=float(amounts[-1].replace(",","")) if amounts else None
    dm=re.search(r"\b(20\d{2}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]20\d{2})\b",text)
    lines=[x.strip() for x in text.splitlines() if x.strip()]
    return {"vendor":lines[0][:100] if lines else "Unknown vendor","date":dm.group(1) if dm else None,
            "amount":amount,"category":classify_category(text),
            "confidence":0.85 if amount is not None and dm else (0.55 if amount is not None else 0.2)}

def save_receipt(employee_id,filename,data):
    if len(data)>settings.max_upload_mb*1024*1024: raise ValueError("File exceeds upload size limit")
    text=extract_text(data,filename); parsed=parse_receipt(text); rid=new_id("rcpt")
    with get_db() as db:
        if not db.execute("SELECT id FROM employees WHERE id=?",(employee_id,)).fetchone():
            raise ValueError("Employee not found")
        db.execute("""INSERT INTO receipts
          (id,employee_id,filename,vendor,expense_date,amount,category,extracted_text,confidence,created_at)
          VALUES (?,?,?,?,?,?,?,?,?,?)""",
          (rid,employee_id,filename,parsed["vendor"],parsed["date"],parsed["amount"],parsed["category"],text,parsed["confidence"],now_iso()))
    return {"receipt_id":rid,"filename":filename,"extracted_text":text[:4000],**parsed}
