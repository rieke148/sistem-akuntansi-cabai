import re

files = [
    "views/11_neraca_lajur.py",
    "views/12_laporan_keuangan.py",
    "views/13_jurnal_penutup.py",
]

for f in files:
    content = open(f, encoding="utf-8").read()
    # Hapus ", bold=True" atau ", bold=False" dari sac.divider() calls
    new_content = re.sub(r",\s*bold=(True|False)", "", content)
    if new_content != content:
        open(f, "w", encoding="utf-8").write(new_content)
        print(f"Fixed: {f}")
    else:
        print(f"No change: {f}")
