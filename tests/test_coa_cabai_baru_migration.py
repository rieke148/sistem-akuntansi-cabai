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

        # COA detail persis mengikuti 28 akun pada CSV; kode kelompok tidak dimasukkan.
        assert kode_akun == {
            "1110", "1120", "1130", "1140",
            "1210", "1220", "1221", "1230", "1231",
            "1240", "1241", "1250", "1251",
            "2110", "2210",
            "3110", "3120", "3130",
            "4110", "5110",
            "6110", "6120", "6130", "6140", "6150", "6160", "6170",
            "7110",
        }
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
