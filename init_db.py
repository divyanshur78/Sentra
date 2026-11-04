from app.db import init_db
from app.seed import seed_demo_data
init_db()
seed_demo_data()
print('DB initialized and seeded')
import sqlite3
conn = sqlite3.connect('./sentra.db')
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print('Tables:', [t[0] for t in tables])
emp = conn.execute("SELECT id, name, role FROM employees").fetchall()
print('Employees:', [(e[0], e[1], e[2]) for e in emp])
conn.close()

