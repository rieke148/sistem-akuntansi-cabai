"""Debug test_special_journals piutang"""
import sqlite3
import pandas as pd

conn = sqlite3.connect(":memory:")
conn.row_factory = sqlite3.Row
conn.executescript("""
    CREATE TABLE periods (id INTEGER PRIMARY KEY, tahun INTEGER, bulan INTEGER, nama_bulan TEXT, status TEXT DEFAULT 'buka');
    CREATE TABLE accounts (id INTEGER PRIMARY KEY, kode_akun TEXT UNIQUE, nama_akun TEXT, kategori TEXT, saldo_normal TEXT, is_kontra INTEGER DEFAULT 0, aktif INTEGER DEFAULT 1);
    CREATE TABLE journal_entries (id INTEGER PRIMARY KEY AUTOINCREMENT, period_id INTEGER, tanggal TEXT, no_bukti TEXT UNIQUE, journal_type TEXT, keterangan TEXT, komoditas TEXT DEFAULT 'cabai', pihak_terkait TEXT);
    CREATE TABLE journal_lines (id INTEGER PRIMARY KEY AUTOINCREMENT, journal_entry_id INTEGER, account_id INTEGER, debit INTEGER DEFAULT 0, kredit INTEGER DEFAULT 0, keterangan TEXT);
    CREATE TABLE receivables (id INTEGER PRIMARY KEY AUTOINCREMENT, journal_entry_id INTEGER, customer_id INTEGER, no_faktur TEXT, tanggal_faktur TEXT, tanggal_jatuh_tempo TEXT, jumlah INTEGER, jumlah_terbayar INTEGER DEFAULT 0, status TEXT DEFAULT 'belum_lunas');

    INSERT INTO periods VALUES (1, 2026, 10, 'Oktober 2026', 'buka');
    INSERT INTO accounts (id, kode_akun, nama_akun, kategori, saldo_normal)
    VALUES
        (1,  '1110', 'Kas',               'Aset',             'Debit'),
        (2,  '1120', 'Piutang Usaha',      'Aset',             'Debit'),
        (3,  '1140', 'Persediaan',   'Aset',             'Debit'),
        (4,  '2110', 'Utang Usaha',        'Liabilitas',       'Kredit'),
        (5,  '3110', 'Modal Pribadi',      'Ekuitas',          'Kredit'),
        (6,  '4110', 'Penjualan Cabai',    'Pendapatan',       'Kredit'),
        (7,  '6110', 'Beban Gaji',         'Beban Operasional',   'Debit'),
        (8,  '6130', 'Beban Air, Listrik, dan Telepon',      'Beban Operasional','Debit'),
        (9,  '5110', 'Harga Pokok Penjualan', 'HPP',   'Debit');

    INSERT INTO journal_entries (period_id, tanggal, no_bukti, journal_type, keterangan, pihak_terkait)
    VALUES (1, '2026-10-05', 'JL-OKT26-001', 'penjualan', 'Jual tempo ke Restoran A', 'Restoran A');
    INSERT INTO journal_lines (journal_entry_id, account_id, debit, kredit)
    VALUES
        (1, 2, 600000, 0), (1, 6, 0, 600000),
        (1, 9, 100000, 0), (1, 3, 0, 100000);
    INSERT INTO receivables (journal_entry_id, customer_id, no_faktur, tanggal_faktur, tanggal_jatuh_tempo, jumlah)
    VALUES (1, 1, 'JL-OKT26-001', '2026-10-05', '2026-10-12', 600000);
""")

# Test piutang query
sql = """
    SELECT
        je.id AS entry_id,
        je.tanggal,
        je.no_bukti AS no_faktur,
        COALESCE(je.pihak_terkait, '-') AS pelanggan,
        COALESCE(r.tanggal_jatuh_tempo, '-') AS jatuh_tempo,
        SUM(CASE WHEN a.kode_akun LIKE '12%' AND jl.debit > 0 THEN jl.debit ELSE 0 END) AS piutang_d,
        SUM(CASE WHEN a.kode_akun LIKE '4%' AND jl.kredit > 0 THEN jl.kredit ELSE 0 END) AS penjualan_k,
        SUM(CASE WHEN a.kode_akun = '5110' AND jl.debit > 0 THEN jl.debit ELSE 0 END) AS hpp_d,
        SUM(CASE WHEN a.kode_akun = '1140' AND jl.kredit > 0 THEN jl.kredit ELSE 0 END) AS persediaan_k
    FROM journal_entries je
    JOIN journal_lines jl ON je.id = jl.journal_entry_id
    JOIN accounts a ON jl.account_id = a.id
    LEFT JOIN receivables r ON je.id = r.journal_entry_id
    WHERE je.journal_type = 'penjualan'
    GROUP BY je.id, je.tanggal, je.no_bukti, je.pihak_terkait, r.tanggal_jatuh_tempo
    ORDER BY je.tanggal, je.id
"""

df = pd.read_sql_query(sql, conn)
print("Jurnal Penjualan:")
print(df)
print()

# Cek semua accounts
df2 = pd.read_sql_query("SELECT * FROM accounts", conn)
print("Accounts:")
print(df2)

# Cek journal_lines
df3 = pd.read_sql_query("""
    SELECT jl.*, a.kode_akun, a.nama_akun 
    FROM journal_lines jl JOIN accounts a ON jl.account_id = a.id
""", conn)
print("\nJournal Lines:")
print(df3)
