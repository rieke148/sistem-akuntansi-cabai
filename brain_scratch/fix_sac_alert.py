"""
Fix semua sac.alert() di views F6:
- Ganti parameter 'message=' → 'label='
- Ganti parameter 'type="success"' → 'color="success"'
- Ganti parameter 'type="error"' → 'color="error"'
- Ganti parameter 'type="warning"' → 'color="warning"'
- Ganti parameter 'type="info"' → 'color="info"'
- Ganti parameter 'icon=True' → 'icon=True'  (sudah benar, biarkan)
"""
import re

files = [
    "views/11_neraca_lajur.py",
    "views/12_laporan_keuangan.py",
    "views/13_jurnal_penutup.py",
    "views/09_neraca_saldo.py",
    "views/10_ayat_penyesuaian.py",
    "views/03_penggajian.py",
]

for f in files:
    try:
        content = open(f, encoding="utf-8").read()
    except FileNotFoundError:
        print(f"Skip (not found): {f}")
        continue

    original = content

    # Ganti 'message=' → 'label='  di dalam sac.alert()
    content = re.sub(r'(sac\.alert\([^)]*?)message=', r'\1label=', content, flags=re.DOTALL)

    # Ganti 'type=' → 'color='  di dalam sac.alert()
    content = re.sub(r'(sac\.alert\([^)]*?)type=', r'\1color=', content, flags=re.DOTALL)

    if content != original:
        open(f, "w", encoding="utf-8").write(content)
        print(f"Fixed: {f}")
    else:
        print(f"No change: {f}")
