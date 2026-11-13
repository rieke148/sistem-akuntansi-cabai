import sys
sys.path.insert(0, r"c:\Users\rieke\code-project\sistem-akuntansi-cabai\sistem-akuntansi-cabai")
from database.connection import get_connection
conn = get_connection()

print("=== Semua akun (lengkap) ===")
rows = conn.execute("SELECT kode_akun, nama_akun, kategori FROM accounts ORDER BY kode_akun").fetchall()
for r in rows:
    print(f"  {r['kode_akun']} | {r['nama_akun']} | {r['kategori']}")
