"""
tests/test_coa_cabai_baru_migration.py
-------------------------------------
Memastikan database lama dimigrasikan ke COA terbaru tanpa kehilangan
jurnal, saldo awal per periode, atau kartu stok per item.
"""

from tests.test_inventory_account_migration import _database_lama
from database.schema import migrasikan_coa_cabai_baru


def test_migrasi_coa_baru_menggabungkan_persediaan_dan_menjaga_riwayat(
    tmp_path, monkeypatch
):
    buka_koneksi = _database_lama(tmp_path, monkeypatch)

    migrasikan_coa_cabai_baru()

    koneksi = buka_koneksi()
    try:
        akun = koneksi.execute(
            "SELECT kode_akun, nama_akun FROM accounts ORDER BY kode_akun"
        ).fetchall()
        kode_akun = {row["kode_akun"] for row in akun}

        # COA detail persis mengikuti kode dan nama akun pada CSV.
        # Kode kelompok 1000–7000 tidak disimpan sebagai akun jurnal.
        akun_sesuai_csv = {
            "1110": "Kas",
            "1120": "Piutang Usaha",
            "1130": "Perlengkapan",
            "1140": "Persediaan",
            "1210": "Tanah",
            "1220": "Bangunan",
            "1221": "Akumulasi Penyusutan Bangunan",
            "1230": "Kendaraan",
            "1231": "Akumulasi Penyusutan Kendaraan",
            "1240": "Komputer",
            "1241": "Akumulasi Penyusutan Komputer",
            "1250": "Peralatan Pertanian",
            "1251": "Akumulasi Penyusutan Peralatan",
            "2110": "Utang Usaha",
            "2210": "Utang Gaji",
            "3110": "Modal Pribadi",
            "3120": "Laba",
            "3130": "Ikhtisar Laba Rugi",
            "4110": "Penjualan Cabai",
            "5110": "Harga Pokok Penjualan",
            "6110": "Beban Gaji",
            "6120": "Beban Sewa",
            "6130": "Beban Air, Listrik, dan Telepon",
            "6140": "Beban BBM Pengiriman",
            "6150": "Beban BBM Operasional",
            "6160": "Beban Penyusutan",
            "6170": "Beban Perbaikan",
            "7110": "Beban Lain-lain",
        }
        assert {
            row["kode_akun"]: row["nama_akun"] for row in akun
        } == akun_sesuai_csv
        assert kode_akun == set(akun_sesuai_csv)
        assert len(akun) == 28
        assert "1140" in kode_akun
        assert "1301" not in kode_akun
        assert "1307" not in kode_akun

        akun_persediaan_id = koneksi.execute(
            "SELECT id FROM accounts WHERE kode_akun = '1140'"
        ).fetchone()["id"]

        # Seluruh jurnal persediaan bahan dan hasil panen diarahkan ke akun 1140.
        akun_jurnal = koneksi.execute(
            """
            SELECT DISTINCT account_id
            FROM journal_lines
            """
        ).fetchall()
        assert {row["account_id"] for row in akun_jurnal} == {akun_persediaan_id}

        # Saldo awal beberapa akun lama digabung per periode, bukan ditimpa.
        saldo = koneksi.execute(
            """
            SELECT period_id, saldo_debit, saldo_kredit
            FROM opening_balances
            WHERE account_id = ?
            ORDER BY period_id
            """,
            (akun_persediaan_id,),
        ).fetchall()
        assert [
            (row["period_id"], row["saldo_debit"], row["saldo_kredit"])
            for row in saldo
        ] == [
            (1, 850, 10),
            (2, 100, 0),
        ]

        # Setiap kartu stok tetap terkait dengan item masing-masing.
        item_accounts = koneksi.execute(
            "SELECT DISTINCT account_id FROM items"
        ).fetchall()
        assert {row["account_id"] for row in item_accounts} == {akun_persediaan_id}
        jumlah_mutasi = koneksi.execute(
            "SELECT COUNT(*) FROM inventory_movements"
        ).fetchone()[0]
        assert jumlah_mutasi == 7

        assert koneksi.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        koneksi.close()

    # Migrasi aman dijalankan ulang tanpa menggandakan akun atau saldo.
    migrasikan_coa_cabai_baru()

    koneksi = buka_koneksi()
    try:
        assert koneksi.execute("SELECT COUNT(*) FROM accounts").fetchone()[0] == 28
        saldo_akhir = koneksi.execute(
            """
            SELECT SUM(saldo_debit), SUM(saldo_kredit)
            FROM opening_balances ob
            JOIN accounts a ON a.id = ob.account_id
            WHERE a.kode_akun = '1140'
            """
        ).fetchone()
        assert tuple(saldo_akhir) == (950, 10)
        assert koneksi.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        koneksi.close()



def test_migrasi_coa_memetakan_akun_lama_ke_akun_yang_semakna(tmp_path, monkeypatch):
    buka_koneksi = _database_lama(tmp_path, monkeypatch)
    conn = buka_koneksi()
    conn.executemany(
        """
        INSERT INTO accounts
            (id, kode_akun, nama_akun, kategori, saldo_normal, is_kontra)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            (8, "5102", "Beban Pupuk", "Beban Produksi", "Debit", 0),
            (9, "5103", "Beban Pestisida", "Beban Produksi", "Debit", 0),
            (10, "1601K", "Akumulasi Amortisasi Plastik Mulsa", "Aset", "Kredit", 1),
            (11, "2202", "Utang Listrik", "Liabilitas", "Kredit", 0),
            (12, "2203", "Utang Lain-lain", "Liabilitas", "Kredit", 0),
        ],
    )
    conn.executemany(
        """
        INSERT INTO journal_lines (journal_entry_id, account_id, debit, kredit)
        VALUES (?, ?, ?, ?)
        """,
        [
            (1, 8, 120, 0),
            (2, 9, 80, 0),
            (3, 10, 0, 30),
            (4, 11, 0, 40),
            (5, 12, 0, 50),
        ],
    )
    conn.executemany(
        """
        INSERT INTO opening_balances
            (period_id, account_id, saldo_debit, saldo_kredit, catatan)
        VALUES (2, ?, ?, ?, ?)
        """,
        [
            (8, 120, 0, "Pupuk"),
            (9, 80, 0, "Pestisida"),
            (10, 0, 30, "Akumulasi amortisasi mulsa"),
            (11, 0, 40, "Utang listrik"),
            (12, 0, 50, "Utang lain-lain"),
        ],
    )
    conn.commit()
    conn.close()

    migrasikan_coa_cabai_baru()

    conn = buka_koneksi()
    try:
        def kode_akun_dari_baris(journal_entry_id):
            return conn.execute(
                """
                SELECT a.kode_akun
                FROM journal_lines jl JOIN accounts a ON a.id = jl.account_id
                WHERE jl.journal_entry_id = ?
                ORDER BY jl.id DESC LIMIT 1
                """,
                (journal_entry_id,),
            ).fetchone()["kode_akun"]

        assert kode_akun_dari_baris(1) == "5110"
        assert kode_akun_dari_baris(2) == "5110"
        assert kode_akun_dari_baris(3) == "1130"
        assert kode_akun_dari_baris(4) == "2110"
        assert kode_akun_dari_baris(5) == "2110"

        saldo = {
            row["kode_akun"]: (row["saldo_debit"], row["saldo_kredit"])
            for row in conn.execute(
                """
                SELECT a.kode_akun, ob.saldo_debit, ob.saldo_kredit
                FROM opening_balances ob
                JOIN accounts a ON a.id = ob.account_id
                WHERE ob.period_id = 2
                """
            ).fetchall()
        }
        assert saldo["5110"] == (200, 0)
        assert saldo["1130"] == (0, 30)
        assert saldo["2110"] == (0, 90)

        assert conn.execute(
            "SELECT COUNT(*) FROM accounts WHERE kode_akun IN ('5102','5103','1601K','2202','2203')"
        ).fetchone()[0] == 0
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        conn.close()
