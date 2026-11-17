"""Script untuk fix komentar/docstring kode akun lama di statements_service.py"""

with open('services/statements_service.py', encoding='utf-8') as f:
    content = f.read()

fixes = [
    ("Modal Disetor' (3101)", "Modal Pribadi' (3110)"),
    ("'Laba Ditahan' (3201)", "'Laba' (3120)"),
    ("Modal Disetor (3101)", "Modal Pribadi (3110)"),
    ("Laba Ditahan (3201)", "Laba (3120)"),
    ("Modal Disetor (3101) dan Laba Ditahan (3201)", "Modal Pribadi (3110) dan Laba (3120)"),
    ("Modal Disetor (3101)", "Modal Pribadi (3110)"),
    ("setoran modal = jurnal kredit ke akun Modal Disetor (3101)", "setoran modal = jurnal kredit ke akun Modal Pribadi (3110)"),
]

for old, new in fixes:
    if old in content:
        content = content.replace(old, new)
        print(f"[OK] {old[:60]}")
    else:
        print(f"[--] {old[:60]}")

with open('services/statements_service.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Selesai.")
