"""
Script untuk memperbaiki semua referensi kode akun lama di services/ dan views/.

Pemetaan kode akun lama -> baru:
- 1101/1102 -> 1110 (Kas)
- 1301/1307/1150 -> 1140 (Persediaan)
- 1501 -> 1210 (Tanah), 1502->1220, 1502K->1221
- 1503->1230, 1503K->1231, 1504->1240, 1504K->1241
- 1505->1250, 1505K->1251
- 2101->2110, 2201->2210
- 3101->3110, 3201->3120
- 4101->4110 (Penjualan Cabai)
- 5101->6110, 5108->5110
- 6101->6130 (Beban Listrik)
- 6102->6140, 6103->6150, 6104->6120, 6105->6160
"""

import os
import re

BASEDIR = r"c:\Users\rieke\code-project\sistem-akuntansi-cabai\sistem-akuntansi-cabai"

# File-file yang perlu diubah (services + views + schema + app)
TARGET_FILES = [
    "services/dashboard_service.py",
    "services/special_journal_service.py",
    "services/statements_service.py",
    "services/transaction_service.py",
    "services/master_data_service.py",
    "services/payroll_service.py",
    "services/adjusting_service.py",
    "services/closing_service.py",
    "services/ledger_service.py",
    "database/schema.py",
    "views/00_dashboard.py",
    "views/01_master_data.py",
    "views/02_input_transaksi.py",
    "views/03_penggajian.py",
    "views/04_jurnal_umum.py",
    "views/05_jurnal_khusus.py",
    "views/07_buku_besar.py",
    "views/09_neraca_saldo.py",
    "views/10_ayat_penyesuaian.py",
    "views/11_neraca_lajur.py",
    "views/12_laporan_keuangan.py",
    "views/13_jurnal_penutup.py",
    "views/14_backup_export.py",
    "app.py",
]

# Daftar penggantian string literal (lebih aman dari regex untuk kode spesifik)
# Format: (string_lama, string_baru, deskripsi)
REPLACEMENTS = [
    # ---- Kode akun dalam SQL/Python string ----
    # Kas
    ("'1101', '1102'", "'1110'", "Kas 1101+1102 -> 1110"),
    ("'1101'", "'1110'", "Kas 1101 -> 1110"),
    ("'1102'", "'1110'", "Bank BRI 1102 -> 1110"),
    # Persediaan
    ("'1301'", "'1140'", "Persediaan Bahan 1301 -> 1140"),
    ("'1307'", "'1140'", "Persediaan Cabai 1307 -> 1140"),
    ("'1150'", "'1140'", "Persediaan 1150 -> 1140"),
    # Aset Tetap
    ("'1501'", "'1210'", "Tanah 1501 -> 1210"),
    ("'1502K'", "'1221'", "Akum Bangunan 1502K -> 1221"),
    ("'1502'", "'1220'", "Bangunan 1502 -> 1220"),
    ("'1503K'", "'1231'", "Akum Kendaraan 1503K -> 1231"),
    ("'1503'", "'1230'", "Kendaraan 1503 -> 1230"),
    ("'1504K'", "'1241'", "Akum Komputer 1504K -> 1241"),
    ("'1504'", "'1240'", "Komputer 1504 -> 1240"),
    ("'1505K'", "'1251'", "Akum Peralatan 1505K -> 1251"),
    ("'1505'", "'1250'", "Peralatan 1505 -> 1250"),
    # Liabilitas
    ("'2101'", "'2110'", "Utang Usaha 2101 -> 2110"),
    ("'2201'", "'2210'", "Utang Gaji 2201 -> 2210"),
    # Ekuitas
    ("'3101', '3201'", "'3110'", "Modal+Laba Ditahan -> 3110"),
    ("'3101'", "'3110'", "Modal 3101 -> 3110"),
    ("'3201'", "'3120'", "Laba Ditahan 3201 -> 3120"),
    # Pendapatan
    ("'4101'", "'4110'", "Penjualan 4101 -> 4110"),
    # HPP & Beban Produksi
    ("'5108'", "'5110'", "HPP 5108 -> 5110"),
    ("'5101'", "'6110'", "Beban Upah 5101 -> 6110"),
    # Beban Operasional
    ("'6101'", "'6130'", "Beban Listrik 6101 -> 6130"),
    ("'6102'", "'6140'", "Beban BBM Kirim 6102 -> 6140"),
    ("'6103'", "'6150'", "Beban BBM Ops 6103 -> 6150"),
    ("'6104'", "'6120'", "Beban Sewa Traktor 6104 -> 6120"),
    ("'6105'", "'6160'", "Beban Penyusutan Non-Prod 6105 -> 6160"),
    ("'6901'", "'7110'", "Beban Lain 6901 -> 7110"),

    # ---- Komentar/docstring ----
    ("(akun 5108)", "(akun 5110)", "komentar 5108->5110"),
    ("(akun 4101)", "(akun 4110)", "komentar 4101->4110"),
    ("akun 5108", "akun 5110", "komentar 5108->5110"),
    ("kode 5108", "kode 5110", "komentar kode 5108->5110"),
    ("kode 5101", "kode 6110", "komentar kode 5101->6110"),
    ("Akun 5108", "Akun 5110", "error msg 5108->5110"),
    ("HPP Penjualan Cabai", "Harga Pokok Penjualan", "nama akun HPP"),
    ("id=38, kode 5105", "kode 6110", "komentar payroll"),

    # ---- _cari_akun_by_kode / helper di views ----
    ('_cari_akun_by_kode("4101")', '_cari_akun_by_kode("4110")', "view 4101->4110"),
    ('_cari_akun_by_kode("1101")', '_cari_akun_by_kode("1110")', "view 1101->1110"),
    ('_cari_akun_by_kode("5108")', '_cari_akun_by_kode("5110")', "view 5108->5110"),
    ('_cari_akun_by_kode("3101")', '_cari_akun_by_kode("3110")', "view 3101->3110"),

    # ---- Caption / help text di views ----
    ("1301 - Persediaan Bahan Produksi", "1140 - Persediaan", "caption persediaan bahan"),
    ("1307 - Persediaan Cabai", "1140 - Persediaan", "caption persediaan cabai"),
    ("Bahan → 1301 Persediaan Bahan Produksi; ", "Bahan → 1140 Persediaan; ", "caption item bahan"),
    ("hasil panen → 1307 Persediaan Cabai.", "hasil panen → 1140 Persediaan.", "caption item panen"),
    ("Bahan → 1301; ", "Bahan → 1140; ", "caption 2 item bahan"),
    ("Hasil panen → 1307.", "Hasil panen → 1140.", "caption 2 item panen"),
    ("Saldo Kas Tunai (1101) + Bank BRI (1102)", "Saldo Kas Tunai (1110)", "help text kas"),
    ("Total kredit akun 4101 - Penjualan Cabai", "Total kredit akun 4110 - Penjualan Cabai", "help penjualan"),
    ("Total debit ke akun 5108 - HPP Penjualan Cabai", "Total debit ke akun 5110 - Harga Pokok Penjualan", "help hpp"),
    ("Penjualan dikurangi HPP Penjualan (akun 5108)", "Penjualan dikurangi HPP Penjualan (akun 5110)", "help laba"),
    ("Contoh: 1101", "Contoh: 1110", "placeholder akun"),
    ("akun 1301 - Persediaan Bahan Produksi", "akun 1140 - Persediaan", "error msg persediaan"),

    # ---- master_data_service: mapping tipe item ----
    ('"bahan": "1301", "hasil_panen": "1307"', '"bahan": "1140", "hasil_panen": "1140"', "mapping tipe item"),

    # ---- schema.py migrasi lama ----
    ("'1302', '1303', '1304', '1305', '1306'", "'1120', '1130'", "akun lama migrasi"),
    ("('1301', '1302', '1303', '1304', '1305', '1306', '1307')", "('1140',)", "kode terkait migrasi"),
    ("pastikan_akun(\"1301\", \"Persediaan Bahan Produksi\")", "pastikan_akun(\"1140\", \"Persediaan\")", "schema pastikan 1301"),
    ("pastikan_akun(\"1307\", \"Persediaan Cabai\")", "pastikan_akun(\"1140\", \"Persediaan\")", "schema pastikan 1307"),
    ("('5108', 'HPP Penjualan Cabai', 'Beban Produksi'", "('5110', 'Harga Pokok Penjualan', 'HPP'", "schema HPP akun"),
    ("kode_akun = '5108'", "kode_akun = '5110'", "schema HPP kode"),
    ("WHERE kode_akun = '5108'", "WHERE kode_akun = '5110'", "schema HPP WHERE"),

    # ---- Kategori HPP ----
    ("'HPP Penjualan Cabai', 'Beban Produksi', 'Debit'", "'Harga Pokok Penjualan', 'HPP', 'Debit'", "schema HPP insert"),
    ("'5108', 'HPP Penjualan Cabai'", "'5110', 'Harga Pokok Penjualan'", "schema HPP nama"),

    # ---- beban_upah_d di special_journal ----
    ("kode_akun = '5101'", "kode_akun = '6110'", "special journal beban upah 5101->6110"),
    ("!= '5101'", "!= '6110'", "special journal beban upah neq"),
    ("beban_upah_d    = debit ke Beban Upah (5101)", "beban_upah_d    = debit ke Beban Gaji (6110)", "docstring beban upah"),

    # ---- statements_service kode ekuitas ----
    ("kode_akun IN ('3101', '3201')", "kode_akun IN ('3110', '3120')", "statements ekuitas"),
    ("kode_akun = '3101'", "kode_akun = '3110'", "statements modal"),
]

total_changed = 0

for rel_path in TARGET_FILES:
    path = os.path.join(BASEDIR, rel_path)
    if not os.path.exists(path):
        print(f"[SKIP] File tidak ditemukan: {rel_path}")
        continue

    with open(path, encoding="utf-8") as f:
        original = f.read()

    content = original
    file_changes = []

    for old, new, desc in REPLACEMENTS:
        if old in content:
            content = content.replace(old, new)
            file_changes.append(desc)

    if file_changes:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"[OK] {rel_path}: {', '.join(file_changes)}")
        total_changed += len(file_changes)
    else:
        print(f"[--] {rel_path}: tidak ada perubahan")

print(f"\nTotal penggantian: {total_changed}")
