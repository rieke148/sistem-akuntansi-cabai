"""Script untuk memperbaiki sisa kode akun lama di seed.py"""

with open('database/seed.py', encoding='utf-8') as f:
    content = f.read()

# Mapping penggantian yang diperlukan
fixes = [
    # 1. Setoran modal: akun["3101"] -> MODAL
    (
        '{"account_id": akun["3101"], "debit": 0, "kredit": 50_000_000}])',
        '{"account_id": MODAL, "debit": 0, "kredit": 50_000_000}])',
    ),
    # 2. HPP seed: akun["5108"] -> akun["5110"]
    (
        'akun_hpp_id = akun["5108"]',
        'akun_hpp_id = akun["5110"]',
    ),
    # 3. Persediaan seed: akun["1307"] -> akun["1140"]
    (
        'akun_persediaan_id = akun["1307"]',
        'akun_persediaan_id = akun["1140"]',
    ),
]

for old, new in fixes:
    if old in content:
        content = content.replace(old, new)
        print(f"[OK] Diganti: {old[:50]}...")
    else:
        print(f"[SKIP] Tidak ditemukan: {old[:50]}...")

with open('database/seed.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Selesai.")
