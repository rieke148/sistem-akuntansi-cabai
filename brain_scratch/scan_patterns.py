"""
Scan semua views untuk mendeteksi pola SQL yang berpotensi error.
"""
import re
import os

base = r"c:\Users\rieke\code-project\sistem-akuntansi-cabai\sistem-akuntansi-cabai"
dirs = ["services", "views"]

# Pola yang dicari
patterns = {
    "UPDATE ORDER BY": r"UPDATE\s+\w+\s+SET.*ORDER\s+BY",
    "kolom 'nama' di items": r"items.*['\"]nama['\"]",
    "kolom 'kode' di blok": r"blok_lahan.*['\"]kode['\"](?!\s*_blok)",
    "kolom 'jatuh_tempo' tanpa tanggal": r"jatuh_tempo['\"](?!\s*\))",
    "kolom 'label' di periods": r"periods.*['\"]label['\"]",
    "COUNT(*) no_bukti": r"COUNT.*no_bukti.*LIKE",
    "bold=True di sac": r"sac\..*bold\s*=",
    "type= di sac.alert": r"sac\.alert.*type\s*=",
}

print("=== SCAN POLA BERMASALAH ===\n")
found_any = False

for d in dirs:
    folder = os.path.join(base, d)
    if not os.path.exists(folder):
        continue
    for fname in sorted(os.listdir(folder)):
        if not fname.endswith(".py"):
            continue
        fpath = os.path.join(folder, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        for i, line in enumerate(lines, 1):
            for pname, pat in patterns.items():
                if re.search(pat, line, re.IGNORECASE):
                    print(f"  [{pname}] {d}/{fname}:{i}: {line.strip()[:80]}")
                    found_any = True

if not found_any:
    print("  Tidak ada pola bermasalah ditemukan! ✅")

# --- Cek juga khusus inventory_service untuk UPDATE ORDER BY ---
print("\n=== CEK inventory_service UPDATE statements ===")
with open(os.path.join(base, "services", "inventory_service.py"), "r", encoding="utf-8") as f:
    content = f.read()
    
update_matches = re.finditer(r"(koneksi\.execute\(.*?(?:\"\"\"|'''))(.*?)\1", content, re.DOTALL)
for m in update_matches:
    sql = m.group(2)
    if "UPDATE" in sql.upper() and "ORDER" in sql.upper():
        print(f"  ⚠️ UPDATE dengan ORDER BY ditemukan:\n{sql[:200]}")

print("\nSELESAI")
