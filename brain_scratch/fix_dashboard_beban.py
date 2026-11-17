"""Fix beban pattern in dashboard_service.py"""

with open('services/dashboard_service.py', 'r', encoding='utf-8') as f:
    content = f.read()

old = "SUM(CASE WHEN a.kode_akun LIKE '5%' AND jl.debit > 0\n                     THEN jl.debit ELSE 0 END) AS beban,"
new = """SUM(CASE WHEN (a.kode_akun LIKE '5%'
                          OR a.kode_akun LIKE '6%'
                          OR a.kode_akun LIKE '7%')
                          AND jl.debit > 0
                     THEN jl.debit ELSE 0 END) AS beban,"""

if old in content:
    content = content.replace(old, new)
    print("OK replaced beban pattern")
else:
    # cari versi dengan unicode
    print("Trying unicode version...")
    old2 = "SUM(CASE WHEN a.kode_akun LIKE '5%' AND jl.debit \u003e 0\n                     THEN jl.debit ELSE 0 END) AS beban,"
    if old2 in content:
        content = content.replace(old2, new)
        print("OK replaced (unicode version)")
    else:
        print("Not found! Showing context:")
        idx = content.find("LIKE '5%'")
        if idx >= 0:
            print(repr(content[idx-50:idx+200]))

with open('services/dashboard_service.py', 'w', encoding='utf-8') as f:
    f.write(content)
