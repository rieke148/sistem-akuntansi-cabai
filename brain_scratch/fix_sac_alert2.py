"""
Fix sac.alert() parameter type= → color= di semua views.
Gunakan pendekatan per-token, bukan regex single-line.
"""
import re

files = [
    "views/11_neraca_lajur.py",
    "views/12_laporan_keuangan.py",
    "views/13_jurnal_penutup.py",
    "views/09_neraca_saldo.py",
    "views/10_ayat_penyesuaian.py",
    "views/03_penggajian.py",
    "views/02_input_transaksi.py",
    "views/04_jurnal_umum.py",
    "views/05_jurnal_khusus.py",
    "views/06_kartu_persediaan.py",
    "views/07_buku_besar.py",
    "views/08_buku_besar_pembantu.py",
]

for f in files:
    try:
        content = open(f, encoding="utf-8").read()
    except FileNotFoundError:
        continue

    original = content

    # Ganti 'message=' → 'label=' di dalam sac.alert (re.DOTALL untuk multiline)
    content = re.sub(
        r'(sac\.alert\((?:[^()]*|\([^()]*\))*?)message=',
        r'\1label=',
        content,
        flags=re.DOTALL
    )

    # Ganti 'type=' → 'color=' di dalam sac.alert (re.DOTALL untuk multiline)
    # Hanya di dalam blok sac.alert(), bukan di tempat lain
    # Strategi: ganti semua 'type="success"' dll yang ada di baris setelah sac.alert(
    content = re.sub(
        r'(sac\.alert\((?:[^()]*|\([^()]*\))*?)type=',
        r'\1color=',
        content,
        flags=re.DOTALL
    )

    if content != original:
        open(f, "w", encoding="utf-8").write(content)
        print(f"Fixed: {f}")
    else:
        print(f"No change: {f}")
