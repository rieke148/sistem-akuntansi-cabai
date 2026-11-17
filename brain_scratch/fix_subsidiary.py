"""Fix subsidiary_service.py - update kode akun 2101 -> 2110"""

with open('services/subsidiary_service.py', 'r', encoding='utf-8') as f:
    content = f.read()

old = "\"SELECT id FROM accounts WHERE kode_akun = '2101'\""
new = "\"SELECT id FROM accounts WHERE kode_akun = '2110'\""

if old in content:
    content = content.replace(old, new)
    print("OK replaced 2101 -> 2110")
else:
    print("Not found, checking...")
    idx = content.find("2101")
    if idx >= 0:
        print(repr(content[idx-50:idx+100]))

# also update comment
content = content.replace("akun 2101 (Utang Usaha)", "akun 2110 (Utang Usaha)")
content = content.replace("(kode 2101)", "(kode 2110)")

with open('services/subsidiary_service.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Done. Remaining 2101:", content.count("2101"))
