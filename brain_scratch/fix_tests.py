"""
Script untuk update semua file test agar menggunakan kode akun COA baru.
Hanya mengganti kode akun di dalam string SQL/data test, bukan di services.
"""

import os

BASEDIR = r"c:\Users\rieke\code-project\sistem-akuntansi-cabai\sistem-akuntansi-cabai"

TEST_FILES = [
    "tests/test_dashboard.py",
    "tests/test_special_journals.py",
    "tests/test_statements.py",
    "tests/test_commodity_migration.py",
    "tests/test_e2e_accounting_cycle.py",
    "tests/test_transactions.py",
    "tests/test_journal.py",
    "tests/test_ledger.py",
    "tests/test_trial_balance.py",
    "tests/test_master_data.py",
    "tests/test_export.py",
    "tests/test_depreciation.py",
    "tests/test_inventory.py",
]

# Penggantian string untuk kode akun lama → baru di file test
# URUTAN PENTING: ganti yang lebih spesifik dulu (1502K sebelum 1502)
REPLACEMENTS = [
    # Akun di SQL INSERT dan kode akun literal
    # --- Aset ---
    ("'1101'", "'1110'"),
    ("'1102'", "'1110'"),
    # Piutang: 1201 → 1120
    ("'1201'", "'1120'"),
    # Perlengkapan: 1401 → 1130
    ("'1401'", "'1130'"),
    # Persediaan: 1301, 1307, 1150 → 1140
    ("'1301'", "'1140'"),
    ("'1307'", "'1140'"),
    ("'1150'", "'1140'"),
    # Aset Tetap (urutan K sebelum angka)
    ("'1502K'", "'1221'"),
    ("'1502'",  "'1220'"),
    ("'1503K'", "'1231'"),
    ("'1503'",  "'1230'"),
    ("'1504K'", "'1241'"),
    ("'1504'",  "'1240'"),
    ("'1505K'", "'1251'"),
    ("'1505'",  "'1250'"),
    ("'1501'",  "'1210'"),
    # --- Liabilitas ---
    ("'2101'", "'2110'"),
    ("'2201'", "'2210'"),
    # --- Ekuitas ---
    ("'3101'", "'3110'"),
    ("'3201'", "'3120'"),
    ("'3301'", "'3130'"),
    # --- Pendapatan ---
    ("'4101'", "'4110'"),
    # --- HPP ---
    ("'5108'", "'5110'"),
    # --- Beban Produksi → Operasional ---
    ("'5101'", "'6110'"),
    ("'5102'", "'6110'"),
    ("'5103'", "'6110'"),
    ("'5104'", "'6110'"),
    ("'5105'", "'6110'"),
    ("'5106'", "'6160'"),
    ("'5107'", "'6160'"),
    # --- Beban Operasional lama ---
    ("'6101'", "'6130'"),
    ("'6102'", "'6140'"),
    ("'6103'", "'6150'"),
    ("'6104'", "'6120'"),
    ("'6105'", "'6160'"),
    ("'6901'", "'7110'"),

    # Nama akun
    ("'HPP Penjualan Cabai'", "'Harga Pokok Penjualan'"),
    ("'Persediaan Bahan Produksi'", "'Persediaan'"),
    ("'Persediaan Bahan'", "'Persediaan'"),
    ("'Persediaan Cabai'", "'Persediaan'"),
    ("'Persediaan Cabai Rawit (kg)'", "'Persediaan'"),
    ("'Beban Upah'", "'Beban Gaji'"),
    ("'Beban Listrik'", "'Beban Air, Listrik, dan Telepon'"),
    ("'Modal Disetor'", "'Modal Pribadi'"),
    ("'Laba Ditahan'", "'Laba'"),
    ("'Ikhtisar Laba Rugi'", "'Ikhtisar Laba Rugi'"),  # sudah sama
    ("'Utang Usaha'", "'Utang Usaha'"),  # sudah sama, 2101→2110 sudah diganti

    # Kategori akun
    ("'Aset Lancar'", "'Aset'"),
    ("'Beban Produksi'", "'Beban Operasional'"),

    # Referensi kode dalam assert / docstring
    ("kode_akun='1101'", "kode_akun='1110'"),
    ("kode_akun='1102'", "kode_akun='1110'"),
    ("kode_akun='1201'", "kode_akun='1120'"),
    ("kode_akun='4101'", "kode_akun='4110'"),
    ("kode_akun='5108'", "kode_akun='5110'"),
    ("kode_akun='5101'", "kode_akun='6110'"),
    ("kode_akun='6101'", "kode_akun='6130'"),
    ("kode_akun='1301'", "kode_akun='1140'"),
    ("kode_akun='1307'", "kode_akun='1140'"),
    ("kode_akun='2101'", "kode_akun='2110'"),
    ("kode_akun='3101'", "kode_akun='3110'"),

    # String dalam assert dan komentar
    ('"1101"', '"1110"'),
    ('"1102"', '"1110"'),
    ('"1201"', '"1120"'),
    ('"4101"', '"4110"'),
    ('"5108"', '"5110"'),
    ('"5101"', '"6110"'),
    ('"5102"', '"6110"'),
    ('"5103"', '"6110"'),
    ('"5104"', '"6110"'),
    ('"5105"', '"6110"'),
    ('"5106"', '"6160"'),
    ('"5107"', '"6160"'),
    ('"6101"', '"6130"'),
    ('"6102"', '"6140"'),
    ('"6103"', '"6150"'),
    ('"6104"', '"6120"'),
    ('"6105"', '"6160"'),
    ('"6901"', '"7110"'),
    ('"1301"', '"1140"'),
    ('"1307"', '"1140"'),
    ('"1501"', '"1210"'),
    ('"1502K"', '"1221"'),
    ('"1502"', '"1220"'),
    ('"1503K"', '"1231"'),
    ('"1503"', '"1230"'),
    ('"1504K"', '"1241"'),
    ('"1504"', '"1240"'),
    ('"1505K"', '"1251"'),
    ('"1505"', '"1250"'),
    ('"2101"', '"2110"'),
    ('"2201"', '"2210"'),
    ('"3101"', '"3110"'),
    ('"3201"', '"3120"'),
    ('"3301"', '"3130"'),
]

total = 0
for rel in TEST_FILES:
    path = os.path.join(BASEDIR, rel)
    if not os.path.exists(path):
        print(f"[SKIP] {rel}")
        continue
    with open(path, encoding="utf-8") as f:
        original = f.read()
    content = original
    changes = []
    for old, new in REPLACEMENTS:
        if old in content and old != new:
            count = content.count(old)
            content = content.replace(old, new)
            changes.append(f"{old}→{new}({count}x)")
    if changes:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"[OK] {rel}: {len(changes)} jenis perubahan")
        total += len(changes)
    else:
        print(f"[--] {rel}: tidak ada perubahan")

print(f"\nTotal: {total} jenis perubahan di test files")
