lines = open('views/00_dashboard.py', encoding='utf-8').read().split('\n')
for i, line in enumerate(lines):
    if 'F6' in line:
        lines[i] = '        ("\u2705", "F6", "Neraca Lajur + Laporan Keuangan + Penutup"),'
        print(f"Fixed line {i}: {lines[i]}")
open('views/00_dashboard.py', 'w', encoding='utf-8').write('\n'.join(lines))
