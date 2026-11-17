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
            kode_akun       TEXT NOT NULL UNIQUE,  -- contoh: '1110'
            nama_akun       TEXT NOT NULL,         -- contoh: 'Kas'
            kategori        TEXT NOT NULL
                            CHECK (kategori IN (
                                'Aset', 'Liabilitas', 'Ekuitas',
                                'Pendapatan', 'HPP', 'Beban Produksi',
                                'Beban Operasional', 'Beban Lainnya'
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
                            CHECK (komoditas IN ('cabai', 'umum')),
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
                            CHECK (komoditas = 'cabai'),
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
                            CHECK (komoditas = 'cabai'),
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

    # Relasi setiap jurnal penerimaan kas dengan faktur piutang yang dibayar.
    # Satu faktur dapat memiliki banyak pembayaran; satu jurnal hanya untuk satu faktur.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS receivable_payments (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            receivable_id    INTEGER NOT NULL REFERENCES receivables(id) ON DELETE CASCADE,
            journal_entry_id INTEGER NOT NULL UNIQUE REFERENCES journal_entries(id) ON DELETE CASCADE,
            jumlah_bayar     INTEGER NOT NULL CHECK (jumlah_bayar > 0),
            dibuat_pada      TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
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
            komoditas       TEXT NOT NULL DEFAULT 'cabai'
                            CHECK (komoditas = 'cabai'),
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


def _gabungkan_saldo_awal_akun(
    koneksi: sqlite3.Connection, account_id_lama: int, account_id_tujuan: int
) -> None:
    """Gabungkan saldo awal akun lama ke akun tujuan tanpa kehilangan nilai."""
    rows = koneksi.execute(
        "SELECT id, period_id, saldo_debit, saldo_kredit, catatan "
        "FROM opening_balances WHERE account_id = ?",
        (account_id_lama,),
    ).fetchall()

    for row in rows:
        tujuan = koneksi.execute(
            "SELECT id, saldo_debit, saldo_kredit, catatan "
            "FROM opening_balances WHERE period_id = ? AND account_id = ?",
            (row["period_id"], account_id_tujuan),
        ).fetchone()

        if tujuan:
            catatan = " | ".join(
                nilai for nilai in [tujuan["catatan"], row["catatan"]] if nilai
            ) or None
            koneksi.execute(
                "UPDATE opening_balances "
                "SET saldo_debit = ?, saldo_kredit = ?, catatan = ? WHERE id = ?",
                (
                    int(tujuan["saldo_debit"]) + int(row["saldo_debit"]),
                    int(tujuan["saldo_kredit"]) + int(row["saldo_kredit"]),
                    catatan,
                    tujuan["id"],
                ),
            )
            koneksi.execute("DELETE FROM opening_balances WHERE id = ?", (row["id"],))
        else:
            koneksi.execute(
                "UPDATE opening_balances SET account_id = ? WHERE id = ?",
                (account_id_tujuan, row["id"]),
            )


def _gabungkan_akun_penjualan_lama(koneksi: sqlite3.Connection) -> None:
    """
    Gabungkan akun pendapatan selain cabai ke akun penjualan cabai.
    Nilai jurnal dan saldo awal dipertahankan, sedangkan akun lama dihapus.
    """
    akun_lama = koneksi.execute(
        "SELECT id FROM accounts WHERE kode_akun IN ('4102', '4103')"
    ).fetchall()
    if not akun_lama:
        return

    akun_cabai = koneksi.execute(
        "SELECT id FROM accounts WHERE kode_akun = '4110'"
    ).fetchone()

    if akun_cabai is None:
        koneksi.execute(
            "INSERT INTO accounts "
            "(kode_akun, nama_akun, kategori, saldo_normal, is_kontra, aktif) "
            "VALUES ('4110', 'Penjualan Cabai Rawit', 'Pendapatan', 'Kredit', 0, 1)"
        )
        account_id_cabai = koneksi.execute(
            "SELECT id FROM accounts WHERE kode_akun = '4110'"
        ).fetchone()["id"]
    else:
        account_id_cabai = akun_cabai["id"]

    tabel_rows = koneksi.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()

    for akun in akun_lama:
        account_id_lama = akun["id"]

        for tabel_row in tabel_rows:
            nama_tabel = tabel_row["name"]
            foreign_keys = koneksi.execute(
                f'PRAGMA foreign_key_list("{nama_tabel}")'
            ).fetchall()

            for fk in foreign_keys:
                if fk["table"] != "accounts":
                    continue

                nama_kolom = fk["from"]
                if nama_tabel == "opening_balances" and nama_kolom == "account_id":
                    _gabungkan_saldo_awal_akun(
                        koneksi, account_id_lama, account_id_cabai
                    )
                else:
                    koneksi.execute(
                        f'UPDATE "{nama_tabel}" SET "{nama_kolom}" = ? '
                        f'WHERE "{nama_kolom}" = ?',
                        (account_id_cabai, account_id_lama),
                    )

        koneksi.execute("DELETE FROM accounts WHERE id = ?", (account_id_lama,))


def _bangun_ulang_tabel_komoditas(
    koneksi: sqlite3.Connection,
    nama_tabel: str,
    fragmen_check_baru: str,
    sql_baru: str,
    kolom: str,
    ekspresi_select: str,
) -> None:
    """Bangun ulang tabel agar CHECK constraint lama diganti tanpa menghapus relasi."""
    baris = koneksi.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
        (nama_tabel,),
    ).fetchone()
    if baris is None:
        return

    sql_lama = " ".join((baris["sql"] or "").lower().split())
    if fragmen_check_baru in sql_lama:
        # Tidak perlu membangun ulang tabel jika batasan sudah sesuai.
        return

    nama_tabel_baru = f"{nama_tabel}_baru"
    koneksi.execute(f'DROP TABLE IF EXISTS "{nama_tabel_baru}"')
    koneksi.execute(sql_baru)
    koneksi.execute(
        f'INSERT INTO "{nama_tabel_baru}" ({kolom}) '
        f'SELECT {ekspresi_select} FROM "{nama_tabel}"'
    )
    koneksi.execute(f'DROP TABLE "{nama_tabel}"')
    koneksi.execute(
        f'ALTER TABLE "{nama_tabel_baru}" RENAME TO "{nama_tabel}"'
    )


def migrasikan_komoditas_cabai_saja() -> None:
    """
    Migrasi database lama agar hanya mendukung komoditas cabai.

    Transaksi jurnal umum tetap dapat diberi penanda 'umum' untuk biaya
    yang belum dialokasikan ke suatu komoditas. Data historis yang sebelumnya
    memakai klasifikasi lain dipindahkan ke cabai, bukan dihapus.
    """
    koneksi = get_connection()
    try:
        koneksi.execute("PRAGMA foreign_keys = OFF")
        koneksi.execute("BEGIN IMMEDIATE")

        _gabungkan_akun_penjualan_lama(koneksi)

        _bangun_ulang_tabel_komoditas(
            koneksi,
            "journal_entries",
            "check (komoditas in ('cabai', 'umum'))",
            """
                CREATE TABLE journal_entries_baru (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    period_id INTEGER NOT NULL REFERENCES periods(id),
                    tanggal TEXT NOT NULL,
                    no_bukti TEXT NOT NULL UNIQUE,
                    journal_type TEXT NOT NULL
                        CHECK (journal_type IN (
                            'penjualan', 'penerimaan_kas', 'pengeluaran_kas',
                            'pembelian', 'umum'
                        )),
                    keterangan TEXT NOT NULL,
                    komoditas TEXT DEFAULT 'cabai'
                        CHECK (komoditas IN ('cabai', 'umum')),
                    pihak_terkait TEXT,
                    dibuat_pada TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
                )
            """,
            "id, period_id, tanggal, no_bukti, journal_type, keterangan, "
            "komoditas, pihak_terkait, dibuat_pada",
            "id, period_id, tanggal, no_bukti, journal_type, keterangan, "
            "CASE WHEN komoditas = 'umum' THEN 'umum' ELSE 'cabai' END AS komoditas, "
            "pihak_terkait, dibuat_pada",
        )

        _bangun_ulang_tabel_komoditas(
            koneksi,
            "items",
            "check (komoditas = 'cabai')",
            """
                CREATE TABLE items_baru (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kode_item TEXT NOT NULL UNIQUE,
                    nama_item TEXT NOT NULL,
                    satuan TEXT NOT NULL,
                    tipe TEXT NOT NULL CHECK (tipe IN ('bahan', 'hasil_panen')),
                    komoditas TEXT NOT NULL DEFAULT 'cabai' CHECK (komoditas = 'cabai'),
                    account_id INTEGER REFERENCES accounts(id),
                    aktif INTEGER NOT NULL DEFAULT 1
                )
            """,
            "id, kode_item, nama_item, satuan, tipe, komoditas, account_id, aktif",
            "id, kode_item, nama_item, satuan, tipe, 'cabai' AS komoditas, account_id, aktif",
        )

        _bangun_ulang_tabel_komoditas(
            koneksi,
            "employees",
            "check (komoditas = 'cabai')",
            """
                CREATE TABLE employees_baru (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nama TEXT NOT NULL,
                    tipe_pekerja TEXT NOT NULL DEFAULT 'tetap'
                        CHECK (tipe_pekerja IN ('tetap', 'tambahan')),
                    upah_harian INTEGER NOT NULL,
                    komoditas TEXT NOT NULL DEFAULT 'cabai' CHECK (komoditas = 'cabai'),
                    aktif INTEGER NOT NULL DEFAULT 1
                )
            """,
            "id, nama, tipe_pekerja, upah_harian, komoditas, aktif",
            "id, nama, tipe_pekerja, upah_harian, 'cabai' AS komoditas, aktif",
        )

        _bangun_ulang_tabel_komoditas(
            koneksi,
            "blok_lahan",
            "check (komoditas = 'cabai')",
            """
                CREATE TABLE blok_lahan_baru (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kode_blok TEXT NOT NULL UNIQUE,
                    jumlah_pohon INTEGER NOT NULL DEFAULT 1000,
                    tanggal_tanam TEXT,
                    komoditas TEXT NOT NULL DEFAULT 'cabai' CHECK (komoditas = 'cabai'),
                    luas_m2 REAL,
                    jarak_tanam_cm REAL DEFAULT 100,
                    keterangan TEXT,
                    aktif INTEGER NOT NULL DEFAULT 1
                )
            """,
            "id, kode_blok, jumlah_pohon, tanggal_tanam, komoditas, "
            "luas_m2, jarak_tanam_cm, keterangan, aktif",
            "id, kode_blok, jumlah_pohon, tanggal_tanam, 'cabai' AS komoditas, "
            "luas_m2, jarak_tanam_cm, keterangan, aktif",
        )

        koneksi.commit()
        koneksi.execute("PRAGMA foreign_keys = ON")
        pelanggaran_fk = koneksi.execute("PRAGMA foreign_key_check").fetchall()
        if pelanggaran_fk:
            raise RuntimeError(
                "Migrasi komoditas selesai, tetapi ditemukan relasi database "
                "yang tidak valid. Periksa hasil PRAGMA foreign_key_check."
            )
    except Exception:
        koneksi.rollback()
        raise
    finally:
        koneksi.close()



def migrasikan_akun_persediaan_bahan_produksi() -> None:
    """
    Menyatukan akun persediaan bahan lama (1301-1306) ke akun 1301.

    Fungsi migrasi database LAMA: menggabungkan 6 akun bahan (1301-1306)
    ke satu akun 1301. Akun cabai (1307) dipertahankan terpisah.
    Baris jurnal dan saldo awal lama dipindahkan tanpa mengubah nilainya.
    Kartu stok per item tidak digabung.

    Catatan: fungsi migrasikan_coa_baru() kemudian akan mengubah 1301 → 1140
    dan 1307 → 1140 (menyatukan keduanya ke akun Persediaan baru).
    """
    koneksi = get_connection()
    try:
        koneksi.execute("PRAGMA foreign_keys = OFF")
        koneksi.execute("BEGIN IMMEDIATE")

        kode_terkait = ("1301", "1302", "1303", "1304", "1305", "1306", "1307")
        placeholders = ", ".join("?" for _ in kode_terkait)
        akun_tersedia = koneksi.execute(
            f"SELECT kode_akun FROM accounts WHERE kode_akun IN ({placeholders})",
            kode_terkait,
        ).fetchall()

        # Database baru belum memiliki akun lama; biarkan seed membuat COA lengkap.
        if not akun_tersedia:
            koneksi.commit()
            return

        def pastikan_akun_lokal(kode: str, nama: str) -> int:
            row = koneksi.execute(
                "SELECT id FROM accounts WHERE kode_akun = ?", (kode,)
            ).fetchone()
            if row:
                account_id = int(row["id"])
                koneksi.execute(
                    """
                    UPDATE accounts
                    SET nama_akun = ?, kategori = 'Aset',
                        saldo_normal = 'Debit', is_kontra = 0, aktif = 1
                    WHERE id = ?
                    """,
                    (nama, account_id),
                )
                return account_id

            cursor = koneksi.execute(
                """
                INSERT INTO accounts
                    (kode_akun, nama_akun, kategori, saldo_normal, is_kontra, aktif)
                VALUES (?, ?, 'Aset', 'Debit', 0, 1)
                """,
                (kode, nama),
            )
            return int(cursor.lastrowid)

        # Akun tujuan: 1301 untuk bahan, 1307 untuk cabai tetap ada
        akun_bahan_id = pastikan_akun_lokal("1301", "Persediaan Bahan")

        # Akun lama yang akan digabung ke 1301 (1302-1306)
        akun_lama_bahan = koneksi.execute(
            "SELECT id FROM accounts WHERE kode_akun IN ('1302', '1303', '1304', '1305', '1306')"
        ).fetchall()

        tabel_rows = koneksi.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()

        for akun in akun_lama_bahan:
            account_id_lama = int(akun["id"])

            # Pindahkan seluruh foreign key yang menunjuk akun lama. Saldo awal
            # digabungkan per periode agar tidak bentrok dengan UNIQUE(period, account).
            for tabel_row in tabel_rows:
                nama_tabel = tabel_row["name"]
                foreign_keys = koneksi.execute(
                    f'PRAGMA foreign_key_list("{nama_tabel}")'
                ).fetchall()

                for fk in foreign_keys:
                    if fk["table"] != "accounts":
                        continue

                    nama_kolom = fk["from"]
                    if nama_tabel == "opening_balances" and nama_kolom == "account_id":
                        _gabungkan_saldo_awal_akun(
                            koneksi, account_id_lama, akun_bahan_id
                        )
                    else:
                        koneksi.execute(
                            f'UPDATE "{nama_tabel}" SET "{nama_kolom}" = ? '
                            f'WHERE "{nama_kolom}" = ?',
                            (akun_bahan_id, account_id_lama),
                        )

            koneksi.execute("DELETE FROM accounts WHERE id = ?", (account_id_lama,))

        # Perbaiki account_id item bahan ke 1301
        koneksi.execute(
            "UPDATE items SET account_id = ? WHERE tipe = 'bahan'",
            (akun_bahan_id,),
        )
        # Akun 1307 (cabai/hasil_panen) dibiarkan — tidak diubah di sini

        pelanggaran_fk = koneksi.execute("PRAGMA foreign_key_check").fetchall()
        if pelanggaran_fk:
            raise RuntimeError(
                "Migrasi akun persediaan menemukan relasi database yang tidak valid. "
                "Tidak ada perubahan yang disimpan."
            )

        koneksi.commit()
    except Exception:
        koneksi.rollback()
        raise
    finally:
        koneksi.execute("PRAGMA foreign_keys = ON")
        koneksi.close()


def pastikan_akun_hpp_penjualan_tersedia() -> None:
    """
    Memastikan akun Harga Pokok Penjualan (5110) tersedia pada database lama maupun baru.
    Kategori 'HPP' agar tampil terpisah di laporan laba rugi.
    """
    koneksi = get_connection()
    try:
        ada = koneksi.execute(
            "SELECT id FROM accounts WHERE kode_akun = '5110'"
        ).fetchone()
        if not ada:
            koneksi.execute("""
                INSERT INTO accounts
                    (kode_akun, nama_akun, kategori, saldo_normal, is_kontra, aktif)
                VALUES ('5110', 'Harga Pokok Penjualan', 'HPP', 'Debit', 0, 1)
            """)
            koneksi.commit()
    except Exception:
        koneksi.rollback()
        raise
    finally:
        koneksi.close()


def tutup_connection(koneksi: sqlite3.Connection) -> None:
    """Menutup koneksi database dengan aman."""
    if koneksi:
        koneksi.close()


def migrasikan_coa_baru() -> None:
    """
    Migrasi COA lama ke COA baru (file coa_cabai_baru.csv).

    Fungsi ini aman dipanggil berulang: hanya menjalankan UPDATE jika
    kode akun lama masih ada. Database baru (fresh seed) tidak terpengaruh.

    Pemetaan utama:
      1101/1102 → 1110  Kas
      1120 → 1120       Piutang Usaha (pertahankan)
      1130/1401 → 1130  Perlengkapan
      1301/1307/1150 → 1140  Persediaan (konsolidasi)
      1501 → 1210, 1502→1220, 1502K→1221
      1503→1230, 1503K→1231, 1504→1240, 1504K→1241
      1505→1250, 1505K→1251
      2101→2110, 2201→2210
      3101→3110, 3201→3120, 3301→3130
      4101→4110 (Penjualan Cabai)
      5101-5107→6110 (Beban Gaji), 5108→5110 (HPP)
      6101→6130, 6102→6140, 6103→6150, 6104→6120, 6105→6160, 6901→7110
    """
    koneksi = get_connection()
    try:
        koneksi.execute("PRAGMA foreign_keys = OFF")
        koneksi.execute("BEGIN IMMEDIATE")

        # --- 1. Tambah kategori baru yang belum ada di CHECK constraint ---
        # SQLite tidak bisa ALTER CHECK, tapi kita bisa update data setelah
        # schema sudah menggunakan kategori baru (sudah diubah di buat_semua_tabel).
        # Untuk database lama, kita gunakan PRAGMA ignore_check_constraints.
        koneksi.execute("PRAGMA ignore_check_constraints = ON")

        # Daftar: (kode_lama, kode_baru, nama_baru, kategori_baru)
        pemetaan = [
            # Aset Lancar
            ("1101", "1110", "Kas", "Aset"),
            ("1102", None,   None, None),   # Bank BCA → gabung ke 1110
            ("1150", "1140", "Persediaan", "Aset"),
            ("1201", "1120", "Piutang Usaha", "Aset"),
            ("1401", "1130", "Perlengkapan", "Aset"),
            ("1301", "1140", "Persediaan", "Aset"),
            ("1302", "1140", "Persediaan", "Aset"),  # Persediaan Pupuk → gabung ke 1140
            ("1303", "1140", "Persediaan", "Aset"),  # Persediaan Pupuk NPK → gabung ke 1140
            ("1304", "1140", "Persediaan", "Aset"),  # Persediaan Pestisida → gabung ke 1140
            ("1305", "1140", "Persediaan", "Aset"),  # Persediaan Plastik Mulsa → gabung ke 1140
            ("1306", "1140", "Persediaan", "Aset"),  # Persediaan Bambu → gabung ke 1140
            ("1307", "1140", "Persediaan", "Aset"),  # akan digabung
            # Aset Tetap
            ("1501",  "1210", "Tanah",                            "Aset"),
            ("1502",  "1220", "Bangunan",                         "Aset"),
            ("1502K", "1221", "Akumulasi Penyusutan Bangunan",    "Aset"),
            ("1503",  "1230", "Kendaraan",                        "Aset"),
            ("1503K", "1231", "Akumulasi Penyusutan Kendaraan",   "Aset"),
            ("1504",  "1240", "Komputer",                         "Aset"),
            ("1504K", "1241", "Akumulasi Penyusutan Komputer",    "Aset"),
            ("1505",  "1250", "Peralatan Pertanian",              "Aset"),
            ("1505K", "1251", "Akumulasi Penyusutan Peralatan",   "Aset"),
            # Aset lain yang dihapus (tidak ada di COA baru)
            ("1601",  None,  None, None),   # Plastik Mulsa → masuk ke Persediaan/Perlengkapan
            ("1601K", None,  None, None),   # Akumulasi amortisasi mulsa → offset kredit Perlengkapan (1130)
            # Liabilitas
            ("2101", "2110", "Utang Usaha",  "Liabilitas"),
            ("2201", "2210", "Utang Gaji",   "Liabilitas"),
            ("2202", None,   None, None),   # Utang listrik → gabung ke Utang Usaha (2110)
            ("2203", None,   None, None),   # Utang lain-lain → gabung ke Utang Usaha (2110) sebagai akun kewajiban umum
            # Ekuitas
            ("3101", "3110", "Modal Pribadi",     "Ekuitas"),
            ("3201", "3120", "Laba",              "Ekuitas"),
            ("3301", "3130", "Ikhtisar Laba Rugi","Ekuitas"),
            # Pendapatan
            ("4101", "4110", "Penjualan Cabai", "Pendapatan"),
            ("4901", "7110", "Beban Lain-lain", "Beban Lainnya"),  # reklasifikasi
            # HPP
            ("5108", "5110", "Harga Pokok Penjualan", "HPP"),
            # Beban Produksi → Beban Operasional
            ("5101", "6110", "Beban Gaji",          "Beban Operasional"),
            ("5102", "5110", "Harga Pokok Penjualan", "HPP"),  # Pupuk merupakan biaya produksi langsung
            ("5103", "5110", "Harga Pokok Penjualan", "HPP"),  # Pestisida merupakan biaya produksi langsung
            ("5104", "6110", "Beban Gaji",          "Beban Operasional"),
            ("5105", "6110", "Beban Gaji",          "Beban Operasional"),
            ("5106", "6160", "Beban Penyusutan",    "Beban Operasional"),
            ("5107", "6160", "Beban Penyusutan",    "Beban Operasional"),
            # Beban Operasional lama → baru
            ("6101", "6130", "Beban Air, Listrik, dan Telepon", "Beban Operasional"),
            ("6102", "6140", "Beban BBM Pengiriman",           "Beban Operasional"),
            ("6103", "6150", "Beban BBM Operasional",          "Beban Operasional"),
            ("6104", "6120", "Beban Sewa",                     "Beban Operasional"),
            ("6105", "6160", "Beban Penyusutan",               "Beban Operasional"),
            ("6901", "7110", "Beban Lain-lain",                "Beban Lainnya"),
        ]

        tabel_rows = koneksi.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()

        def pindahkan_referensi(id_lama: int, id_tujuan: int) -> None:
            """Pindahkan semua FK ke id_tujuan, lalu hapus akun lama."""
            for tr in tabel_rows:
                nama_tbl = tr["name"]
                fks = koneksi.execute(
                    f'PRAGMA foreign_key_list("{nama_tbl}")'
                ).fetchall()
                for fk in fks:
                    if fk["table"] != "accounts":
                        continue
                    kolom = fk["from"]
                    if nama_tbl == "opening_balances" and kolom == "account_id":
                        _gabungkan_saldo_awal_akun(koneksi, id_lama, id_tujuan)
                    else:
                        koneksi.execute(
                            f'UPDATE "{nama_tbl}" SET "{kolom}" = ? WHERE "{kolom}" = ?',
                            (id_tujuan, id_lama),
                        )
            koneksi.execute("DELETE FROM accounts WHERE id = ?", (id_lama,))

        for kode_lama, kode_baru, nama_baru, kategori_baru in pemetaan:
            akun_lama = koneksi.execute(
                "SELECT id FROM accounts WHERE kode_akun = ?", (kode_lama,)
            ).fetchone()
            if not akun_lama:
                continue  # sudah tidak ada, skip

            id_lama = int(akun_lama["id"])

            if kode_baru is None:
                # Akun dihapus: pindahkan referensi ke akun paling dekat yang ada
                # (misalnya 1102 Bank BCA → pindah ke 1110 Kas)
                fallback_map = {
                    "1102": "1110", "1601": "1130", "1601K": "1130",
                    "2202": "2110", "2203": "2110",
                }
                kode_fallback = fallback_map.get(kode_lama)
                if kode_fallback:
                    akun_fallback = koneksi.execute(
                        "SELECT id FROM accounts WHERE kode_akun = ?", (kode_fallback,)
                    ).fetchone()
                    if not akun_fallback:
                        # Buat akun tujuan minimal sebelum memindahkan FK. Ini
                        # diperlukan karena beberapa akun baru belum tentu ada
                        # saat urutan migrasi mencapai akun lama yang dihapus.
                        data_fallback = {
                            "1110": ("Kas", "Aset", "Debit", 0),
                            "1130": ("Perlengkapan", "Aset", "Debit", 0),
                            "2110": ("Utang Usaha", "Liabilitas", "Kredit", 0),
                        }.get(kode_fallback)
                        if data_fallback:
                            nama_fb, kategori_fb, normal_fb, kontra_fb = data_fallback
                            koneksi.execute(
                                """
                                INSERT INTO accounts
                                    (kode_akun, nama_akun, kategori, saldo_normal, is_kontra, aktif)
                                VALUES (?, ?, ?, ?, ?, 1)
                                """,
                                (kode_fallback, nama_fb, kategori_fb, normal_fb, kontra_fb),
                            )
                            akun_fallback = koneksi.execute(
                                "SELECT id FROM accounts WHERE kode_akun = ?",
                                (kode_fallback,),
                            ).fetchone()
                    if akun_fallback:
                        pindahkan_referensi(id_lama, int(akun_fallback["id"]))
                    else:
                        koneksi.execute("DELETE FROM accounts WHERE id = ?", (id_lama,))
                else:
                    koneksi.execute("DELETE FROM accounts WHERE id = ?", (id_lama,))
                continue

            # Cek apakah kode_baru sudah ada
            akun_baru = koneksi.execute(
                "SELECT id FROM accounts WHERE kode_akun = ?", (kode_baru,)
            ).fetchone()

            if akun_baru:
                # Kode baru sudah ada → gabungkan akun lama ke akun baru
                id_baru = int(akun_baru["id"])
                if id_lama != id_baru:
                    pindahkan_referensi(id_lama, id_baru)
            else:
                # Kode baru belum ada → rename kode lama
                koneksi.execute(
                    "UPDATE accounts SET kode_akun=?, nama_akun=?, kategori=? WHERE id=?",
                    (kode_baru, nama_baru, kategori_baru, id_lama),
                )

        # Pastikan nama akun 1110 adalah "Kas" (bukan "Bank BCA" jika dimerge)
        for kode, nama, kat in [
            ("1110", "Kas", "Aset"),
            ("1120", "Piutang Usaha", "Aset"),
            ("1130", "Perlengkapan", "Aset"),
            ("1140", "Persediaan", "Aset"),
            ("2110", "Utang Usaha", "Liabilitas"),
            ("2210", "Utang Gaji", "Liabilitas"),
            ("3110", "Modal Pribadi", "Ekuitas"),
            ("3120", "Laba", "Ekuitas"),
            ("3130", "Ikhtisar Laba Rugi", "Ekuitas"),
            ("4110", "Penjualan Cabai", "Pendapatan"),
            ("5110", "Harga Pokok Penjualan", "HPP"),
            ("6110", "Beban Gaji", "Beban Operasional"),
            ("6120", "Beban Sewa", "Beban Operasional"),
            ("6130", "Beban Air, Listrik, dan Telepon", "Beban Operasional"),
            ("6140", "Beban BBM Pengiriman", "Beban Operasional"),
            ("6150", "Beban BBM Operasional", "Beban Operasional"),
            ("6160", "Beban Penyusutan", "Beban Operasional"),
            ("6170", "Beban Perbaikan", "Beban Operasional"),
            ("7110", "Beban Lain-lain", "Beban Lainnya"),
        ]:
            exists = koneksi.execute(
                "SELECT id FROM accounts WHERE kode_akun = ?", (kode,)
            ).fetchone()
            if exists:
                koneksi.execute(
                    "UPDATE accounts SET nama_akun=?, kategori=? WHERE kode_akun=?",
                    (nama, kat, kode),
                )

        # Pastikan akun baru yang belum ada ditambahkan
        akun_wajib = [
            ("1110", "Kas", "Aset", "Debit", 0),
            ("1120", "Piutang Usaha", "Aset", "Debit", 0),
            ("1130", "Perlengkapan", "Aset", "Debit", 0),
            ("1140", "Persediaan", "Aset", "Debit", 0),
            ("1210", "Tanah", "Aset", "Debit", 0),
            ("1220", "Bangunan", "Aset", "Debit", 0),
            ("1221", "Akumulasi Penyusutan Bangunan", "Aset", "Kredit", 1),
            ("1230", "Kendaraan", "Aset", "Debit", 0),
            ("1231", "Akumulasi Penyusutan Kendaraan", "Aset", "Kredit", 1),
            ("1240", "Komputer", "Aset", "Debit", 0),
            ("1241", "Akumulasi Penyusutan Komputer", "Aset", "Kredit", 1),
            ("1250", "Peralatan Pertanian", "Aset", "Debit", 0),
            ("1251", "Akumulasi Penyusutan Peralatan", "Aset", "Kredit", 1),
            ("2110", "Utang Usaha", "Liabilitas", "Kredit", 0),
            ("2210", "Utang Gaji", "Liabilitas", "Kredit", 0),
            ("3110", "Modal Pribadi", "Ekuitas", "Kredit", 0),
            ("3120", "Laba", "Ekuitas", "Kredit", 0),
            ("3130", "Ikhtisar Laba Rugi", "Ekuitas", "Kredit", 0),
            ("4110", "Penjualan Cabai", "Pendapatan", "Kredit", 0),
            ("5110", "Harga Pokok Penjualan", "HPP", "Debit", 0),
            ("6110", "Beban Gaji", "Beban Operasional", "Debit", 0),
            ("6120", "Beban Sewa", "Beban Operasional", "Debit", 0),
            ("6130", "Beban Air, Listrik, dan Telepon", "Beban Operasional", "Debit", 0),
            ("6140", "Beban BBM Pengiriman", "Beban Operasional", "Debit", 0),
            ("6150", "Beban BBM Operasional", "Beban Operasional", "Debit", 0),
            ("6160", "Beban Penyusutan", "Beban Operasional", "Debit", 0),
            ("6170", "Beban Perbaikan", "Beban Operasional", "Debit", 0),
            ("7110", "Beban Lain-lain", "Beban Lainnya", "Debit", 0),
        ]
        for kode, nama, kat, saldo, kontra in akun_wajib:
            ada = koneksi.execute(
                "SELECT id FROM accounts WHERE kode_akun = ?", (kode,)
            ).fetchone()
            if not ada:
                koneksi.execute(
                    "INSERT INTO accounts (kode_akun, nama_akun, kategori, saldo_normal, is_kontra) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (kode, nama, kat, saldo, kontra),
                )

        # Perbarui items agar tipe bahan/panen → semua ke akun 1140
        akun_1140 = koneksi.execute(
            "SELECT id FROM accounts WHERE kode_akun = '1140'"
        ).fetchone()
        if akun_1140:
            koneksi.execute(
                "UPDATE items SET account_id = ? WHERE tipe IN ('bahan', 'hasil_panen')",
                (int(akun_1140["id"]),),
            )

        koneksi.execute("PRAGMA ignore_check_constraints = OFF")
        koneksi.commit()
        koneksi.execute("PRAGMA foreign_keys = ON")
        print("[OK] Migrasi COA baru selesai.")
    except Exception as e:
        koneksi.rollback()
        print(f"[ERROR] Migrasi COA gagal: {e}")
        raise
    finally:
        koneksi.close()


# Alias untuk backward-compatibility dan test suite
migrasikan_coa_cabai_baru = migrasikan_coa_baru


if __name__ == "__main__":
    # Jalankan langsung untuk membuat tabel: python -m database.schema
    buat_semua_tabel()
