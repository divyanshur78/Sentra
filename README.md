# Sentra AI — Governed ExpenseClaim Agent

Governed AI agents for secure, intelligent, and human-controlled task automation.

## Architecture
- **Backend**: FastAPI core, SQLite database, employee memory, receipt OCR/extraction, LLM intent parsing, deterministic policy rules (R1–R9), and Person 3 policy gateway integration (R10 prompt injection & red-team defence, immutable hash-chained audit log).
- **Frontend**: React + Vite single page application with dedicated portals for:
  - **Employee**: Submit claims, chat with Sentra AI assistant, attach receipts, track expenses.
  - **Manager**: Review and approve/reject claims, AI companion for approval policy checks.
  - **Owner**: Evaluation matrix, Red-Team security lab, verifiable audit log.

## Quick Start

### 1. Automated Start (Windows)
Run the startup script from PowerShell in the project root:
```powershell
.\start.ps1
```
Or with batch file:
```cmd
start.bat
```

### 2. Manual Start

#### Backend:
```powershell
# Copy environment file if not present
Copy-Item .env.example .env

# Initialize database
python init_db.py

# Run FastAPI backend
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
- API Docs: http://127.0.0.1:8000/docs
- Health check: http://127.0.0.1:8000/health

#### Frontend:
```powershell
cd Sentrafrnt
npm install
npm run dev
```
- App UI: http://localhost:5173

## Demo Accounts
- **Employee**: `emp-001` (Aarav Sharma), `emp-002` (Diya Patel) — (any password)
- **Manager**: `mgr-001` (Rohan Mehta), `mgr-002` (Neha Verma) — (any password)
- **Owner**: `O1001` / Password: `Own@123`

## Deterministic Governance Rules
- **R1**: At least one valid receipt required.
- **R2**: Monthly employee limit enforced.
- **R3**: Category limit (Meal max ₹5,000).
- **R4**: Restricted categories blocked (Alcohol, personal travel, cash withdrawal).
- **R5**: Duplicate claim detection (same vendor, amount, date).
- **R6**: Manager approval escalation for claims > ₹25,000.
- **R7**: Claims without valid receipts cannot be approved.
- **R8**: Cross-employee profile/claim access denied.
- **R9**: Manager assignment enforced (only assigned manager may approve).
- **R10**: Untrusted receipt text treated as data, never executable instructions (prompt injection blocked).

## Testing
Run backend unit & policy tests:
```powershell
pytest
```
