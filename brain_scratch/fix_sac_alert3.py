"""
Fix sac.alert() - ganti 'type=' → 'color=' dan 'message=' → 'label='
Strategi sederhana: parse baris per baris, track apakah sedang dalam sac.alert().
"""

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
        lines = open(f, encoding="utf-8").readlines()
    except FileNotFoundError:
        continue

    new_lines = []
    in_sac_alert = False
    paren_depth = 0
    changed = False

    for line in lines:
        # Deteksi awal sac.alert(
        if "sac.alert(" in line:
            in_sac_alert = True
            paren_depth = 0

        if in_sac_alert:
            # Hitung kedalaman tanda kurung
            paren_depth += line.count("(") - line.count(")")

            # Ganti parameter yang salah
            new_line = line
            if "message=" in new_line:
                new_line = new_line.replace("message=", "label=")
                changed = True
            if "        type=" in new_line or "    type=" in new_line or ", type=" in new_line:
                new_line = new_line.replace("        type=", "        color=")
                new_line = new_line.replace("    type=", "    color=")
                new_line = new_line.replace(", type=", ", color=")
                changed = True

            new_lines.append(new_line)

            # Keluar dari sac.alert() saat kurung tutup
            if paren_depth <= 0:
                in_sac_alert = False
        else:
            new_lines.append(line)

    if changed:
        open(f, "w", encoding="utf-8").writelines(new_lines)
        print(f"Fixed: {f}")
    else:
        print(f"No change: {f}")
