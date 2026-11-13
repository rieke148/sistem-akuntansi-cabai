"""
database/schema.py
------------------
Tujuan  : Mendefinisikan dan membuat semua tabel database SQLite.
          Jalankan fungsi buat_semua_tabel() sekali saat aplikasi
          pertama kali dijalankan (dipanggil dari app.py).
Input   : Tidak ada.
Output  : Tabel-tabel SQLite terbuat di file database.
Dipanggil oleh : app.py (saat startup), database/seed.py

CATATAN DESAIN:
  Semua angka uang disimpan sebagai INTEGER (dalam Rupiah bulat).
  Hindari REAL/FLOAT karena masalah pembulatan desimal di akuntansi.
  Contoh: Rp1.500.000 disimpan sebagai 1500000 (integer).
"""

import sqlite3
from database.connection import get_connection


def buat_semua_tabel() -> None:
    """
    Membuat semua tabel jika belum ada (CREATE TABLE IF NOT EXISTS).
    Aman dipanggil berulang — tidak akan menghapus data yang sudah ada.
    """
    koneksi = get_connection()
    cursor = koneksi.cursor()

    # ---------------------------------------------------------------
    # 1. TABEL PERIODE AKUNTANSI
    # ---------------------------------------------------------------
    # Setiap periode = 1 bulan. Status 'buka' atau 'tutup'.
    # Periode yang sudah tutup tidak bisa diedit.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS periods (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            tahun       INTEGER NOT NULL,          -- contoh: 2026
            bulan       INTEGER NOT NULL,          -- 1-12
            nama_bulan  TEXT NOT NULL,             -- contoh: 'Oktober 2026'
            status      TEXT NOT NULL DEFAULT 'buka'
                        CHECK (status IN ('buka', 'tutup')),
            UNIQUE (tahun, bulan)                  -- satu bulan = satu periode
        )
    """)

    # ---------------------------------------------------------------
    # 2. TABEL BAGAN AKUN (Chart of Accounts)
    # ---------------------------------------------------------------
    # Struktur kode akun:
    #   1xxx = Aset
    #   2xxx = Liabilitas
    #   3xxx = Ekuitas
    #   4xxx = Pendapatan
    #   5xxx = Beban Produksi
    #   6xxx = Beban Operasional
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            kode_akun       TEXT NOT NULL UNIQUE,  -- contoh: '1101'
            nama_akun       TEXT NOT NULL,         -- contoh: 'Kas'
            kategori        TEXT NOT NULL
                            CHECK (kategori IN (
                                'Aset', 'Liabilitas', 'Ekuitas',
                                'Pendapatan', 'Beban Produksi', 'Beban Operasional'
                            )),
            saldo_normal    TEXT NOT NULL
                            CHECK (saldo_normal IN ('Debit', 'Kredit')),
            -- Akun kontra (mis. Akumulasi Penyusutan) ditandai dengan is_kontra=1
            is_kontra       INTEGER NOT NULL DEFAULT 0
                            CHECK (is_kontra IN (0, 1)),
            aktif           INTEGER NOT NULL DEFAULT 1
                            CHECK (aktif IN (0, 1))
        )
    """)

    # ---------------------------------------------------------------
    # 3. TABEL HEADER JURNAL
    # ---------------------------------------------------------------
    # Satu entri di sini = satu transaksi (mis. 1 faktur penjualan).
    # Detail debit/kredit ada di tabel journal_lines.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS journal_entries (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            period_id       INTEGER NOT NULL REFERENCES periods(id),
            tanggal         TEXT NOT NULL,         -- format: 'YYYY-MM-DD'
            no_bukti        TEXT NOT NULL UNIQUE,  -- nomor bukti transaksi
            journal_type    TEXT NOT NULL
                            CHECK (journal_type IN (
                                'penjualan',
                                'penerimaan_kas',
                                'pengeluaran_kas',
                                'pembelian',
                                'umum'
                            )),
            keterangan      TEXT NOT NULL,         -- deskripsi transaksi
            komoditas       TEXT DEFAULT 'cabai'
                            CHECK (komoditas IN ('cabai', 'selada', 'melon', 'umum')),
            pihak_terkait   TEXT,                  -- nama pelanggan/supplier (opsional)
            dibuat_pada     TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
    """)

    # ---------------------------------------------------------------
    # 4. TABEL BARIS JURNAL (sumber kebenaran semua angka)
    # ---------------------------------------------------------------
    # Setiap transaksi punya minimal 2 baris (1 debit, 1 kredit).
    # ATURAN: total debit = total kredit untuk setiap journal_entry_id.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS journal_lines (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            journal_entry_id    INTEGER NOT NULL
                                REFERENCES journal_entries(id) ON DELETE CASCADE,
            account_id          INTEGER NOT NULL REFERENCES accounts(id),
            debit               INTEGER NOT NULL DEFAULT 0,  -- dalam Rupiah
            kredit              INTEGER NOT NULL DEFAULT 0,  -- dalam Rupiah
            keterangan          TEXT,                        -- keterangan per baris (opsional)
            -- Validasi: salah satu harus > 0, tidak keduanya
            CHECK (
                (debit > 0 AND kredit = 0) OR
                (kredit > 0 AND debit = 0)
            )
        )
    """)

    # ---------------------------------------------------------------
    # 5. TABEL PELANGGAN
    # ---------------------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            nama        TEXT NOT NULL,
            tipe        TEXT NOT NULL DEFAULT 'umum'
                        CHECK (tipe IN ('restoran', 'supermarket', 'umkm', 'umum')),
            telepon     TEXT,
            alamat      TEXT,
            aktif       INTEGER NOT NULL DEFAULT 1
        )
    """)

    # ---------------------------------------------------------------
    # 6. TABEL SUPPLIER
    # ---------------------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS suppliers (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            nama        TEXT NOT NULL,
            telepon     TEXT,
            alamat      TEXT,
            aktif       INTEGER NOT NULL DEFAULT 1
        )
    """)

    # ---------------------------------------------------------------
    # 7. TABEL ITEM PERSEDIAAN
    # ---------------------------------------------------------------
    # Item bisa berupa bahan (input produksi) atau hasil panen (output).
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            kode_item       TEXT NOT NULL UNIQUE,  -- contoh: 'BHN-001'
            nama_item       TEXT NOT NULL,         -- contoh: 'Bibit Cabai'
            satuan          TEXT NOT NULL,         -- contoh: 'batang', 'kg', 'karung'
            tipe            TEXT NOT NULL
                            CHECK (tipe IN ('bahan', 'hasil_panen')),
            komoditas       TEXT NOT NULL DEFAULT 'cabai'
                            CHECK (komoditas IN ('cabai', 'selada', 'melon')),
            account_id      INTEGER REFERENCES accounts(id),  -- akun persediaan terkait
            aktif           INTEGER NOT NULL DEFAULT 1
        )
    """)

    # ---------------------------------------------------------------
    # 8. TABEL KARTU PERSEDIAAN (gerakan stok)
    # ---------------------------------------------------------------
    # Setiap baris = 1 gerakan masuk atau keluar.
    # Metode rata-rata bergerak: harga_rata2 dihitung ulang setiap masuk.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory_movements (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id             INTEGER NOT NULL REFERENCES items(id),
            journal_entry_id    INTEGER REFERENCES journal_entries(id),
            tanggal             TEXT NOT NULL,         -- 'YYYY-MM-DD'
            tipe_gerakan        TEXT NOT NULL
                                CHECK (tipe_gerakan IN ('masuk', 'keluar', 'saldo_awal')),
            qty                 REAL NOT NULL,         -- kuantitas (bisa desimal, misal 0.5 kg)
            harga_satuan        INTEGER NOT NULL,      -- harga per unit (Rupiah)
            total_nilai         INTEGER NOT NULL,      -- qty x harga_satuan
            -- Saldo setelah gerakan ini (dihitung oleh inventory_service)
            saldo_qty           REAL NOT NULL DEFAULT 0,
            saldo_nilai         INTEGER NOT NULL DEFAULT 0,
            harga_rata2         INTEGER NOT NULL DEFAULT 0,  -- harga rata-rata bergerak
            keterangan          TEXT
        )
    """)

    # ---------------------------------------------------------------
    # 9. TABEL PEKERJA
    # ---------------------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            nama            TEXT NOT NULL,
            tipe_pekerja    TEXT NOT NULL DEFAULT 'tetap'
                            CHECK (tipe_pekerja IN ('tetap', 'tambahan')),
            -- Upah harian sesuai tipe (bisa diubah di Master Data)
            upah_harian     INTEGER NOT NULL,  -- Rp90.000 tetap / Rp120.000 tambahan
            komoditas       TEXT NOT NULL DEFAULT 'cabai'
                            CHECK (komoditas IN ('cabai', 'selada', 'melon')),
            aktif           INTEGER NOT NULL DEFAULT 1
        )
    """)

    # ---------------------------------------------------------------
    # 10. TABEL ABSENSI / HARI KERJA
    # ---------------------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id     INTEGER NOT NULL REFERENCES employees(id),
            period_id       INTEGER NOT NULL REFERENCES periods(id),
            -- Periode pembayaran: 'minggu1' (tgl 1-14) atau 'minggu2' (tgl 15-akhir)
            periode_bayar   TEXT NOT NULL
                            CHECK (periode_bayar IN ('minggu1', 'minggu2')),
            hari_kerja      INTEGER NOT NULL DEFAULT 0,  -- jumlah hari hadir
            total_upah      INTEGER NOT NULL DEFAULT 0,  -- hari_kerja x upah_harian
            sudah_dibayar   INTEGER NOT NULL DEFAULT 0
                            CHECK (sudah_dibayar IN (0, 1)),
            journal_entry_id INTEGER REFERENCES journal_entries(id)
        )
    """)

    # ---------------------------------------------------------------
    # 11. TABEL ASET TETAP
    # ---------------------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fixed_assets (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            kode_aset           TEXT NOT NULL UNIQUE,  -- contoh: 'AT-001'
            nama_aset           TEXT NOT NULL,
            kategori_aset       TEXT NOT NULL
                                CHECK (kategori_aset IN (
                                    'Tanah', 'Bangunan', 'Kendaraan',
                                    'Komputer', 'Peralatan', 'Perlengkapan'
                                )),
            tanggal_perolehan   TEXT NOT NULL,         -- 'YYYY-MM-DD'
            harga_perolehan     INTEGER NOT NULL,      -- Rupiah
            nilai_residu        INTEGER NOT NULL DEFAULT 0,
            umur_ekonomis_tahun INTEGER NOT NULL DEFAULT 1,
            jumlah_unit         INTEGER NOT NULL DEFAULT 1,
            -- Tanah tidak disusutkan (is_disusutkan=0)
            is_disusutkan       INTEGER NOT NULL DEFAULT 1
                                CHECK (is_disusutkan IN (0, 1)),
            account_id          INTEGER REFERENCES accounts(id),  -- akun aset tetap
            account_akum_id     INTEGER REFERENCES accounts(id),  -- akun akumulasi penyusutan
            aktif               INTEGER NOT NULL DEFAULT 1,
            keterangan          TEXT
        )
    """)

    # ---------------------------------------------------------------
    # 12. TABEL PIUTANG USAHA
    # ---------------------------------------------------------------
    # Dibuat otomatis saat ada penjualan tempo (jurnal penjualan).
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS receivables (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            journal_entry_id    INTEGER NOT NULL REFERENCES journal_entries(id),
            customer_id         INTEGER NOT NULL REFERENCES customers(id),
            no_faktur           TEXT NOT NULL UNIQUE,
            tanggal_faktur      TEXT NOT NULL,         -- 'YYYY-MM-DD'
            tanggal_jatuh_tempo TEXT NOT NULL,         -- tanggal_faktur + 7 hari
            jumlah              INTEGER NOT NULL,      -- Rupiah
            jumlah_terbayar     INTEGER NOT NULL DEFAULT 0,
            status              TEXT NOT NULL DEFAULT 'belum_lunas'
                                CHECK (status IN ('belum_lunas', 'lunas', 'sebagian'))
        )
    """)

    # ---------------------------------------------------------------
    # 13. TABEL SALDO AWAL AKUN
    # ---------------------------------------------------------------
    # Diisi user di halaman Master Data > Saldo Awal.
    # Ditandai sebagai 'CONTOH' jika dari seed — user harus ganti.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS opening_balances (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            period_id       INTEGER NOT NULL REFERENCES periods(id),
            account_id      INTEGER NOT NULL REFERENCES accounts(id),
            saldo_debit     INTEGER NOT NULL DEFAULT 0,
            saldo_kredit    INTEGER NOT NULL DEFAULT 0,
            catatan         TEXT,  -- mis. 'CONTOH - ganti dengan data asli'
            UNIQUE (period_id, account_id)
        )
    """)

    # ---------------------------------------------------------------
    # 14. TABEL PARAMETER OPERASIONAL
    # ---------------------------------------------------------------
    # Parameter yang bisa diubah user tanpa ubah kode.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS parameters (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            kunci   TEXT NOT NULL UNIQUE,  -- contoh: 'upah_tetap_harian'
            nilai   TEXT NOT NULL,         -- nilai disimpan sebagai teks
            satuan  TEXT,                  -- contoh: 'Rupiah/hari', 'gram/pohon'
            catatan TEXT
        )
    """)

    # ---------------------------------------------------------------
    # 15. TABEL BLOK LAHAN
    # ---------------------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS blok_lahan (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            kode_blok       TEXT NOT NULL UNIQUE,  -- 'A', 'B', 'C', 'D', 'E'
            jumlah_pohon    INTEGER NOT NULL DEFAULT 1000,
            tanggal_tanam   TEXT,                  -- 'YYYY-MM-DD'
            komoditas       TEXT NOT NULL DEFAULT 'cabai',
            luas_m2         REAL,                  -- luas blok dalam m2
            jarak_tanam_cm  REAL DEFAULT 100,      -- jarak tanam (default 1 m)
            keterangan      TEXT,                  -- mis. catatan penyakit
            aktif           INTEGER NOT NULL DEFAULT 1
        )
    """)

    # Simpan semua perubahan ke file database
    koneksi.commit()
    tutup_connection(koneksi)
    print("[OK] Semua tabel berhasil dibuat.")


def tutup_connection(koneksi: sqlite3.Connection) -> None:
    """Menutup koneksi database dengan aman."""
    if koneksi:
        koneksi.close()


if __name__ == "__main__":
    # Jalankan langsung untuk membuat tabel: python -m database.schema
    buat_semua_tabel()
