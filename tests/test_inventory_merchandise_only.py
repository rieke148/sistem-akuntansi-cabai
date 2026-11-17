"""Regression tests for the merchandise-only inventory workflow."""

import sqlite3

import pytest

from database.schema import migrasikan_persediaan_barang_dagang_saja
from services.master_data_service import TIPE_ITEM, tambah_item
from services.inventory_service import ambil_daftar_item_persediaan
from services.dashboard_service import ambil_stok_persediaan
from services.transaction_service import _validasi_item_barang_dagang


def _database_file(path):
    def buka_koneksi():
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
    return buka_koneksi


def test_master_data_hanya_mengizinkan_barang_dagang_hasil_panen():
    assert TIPE_ITEM == ["hasil_panen"]


def test_tambah_item_menolak_tipe_bahan_lama():
    with pytest.raises(ValueError, match="Tipe item persediaan tidak dikenal"):
        tambah_item(
            kode_item="BHN-TEST",
            nama_item="Pupuk Uji",
            satuan="kg",
            tipe="bahan",
            komoditas="cabai",
            account_id=None,
        )


def test_migrasi_menonaktifkan_item_bahan_tanpa_menghapus_histori(tmp_path, monkeypatch):
    db_path = tmp_path / "merchandise_only.db"
    buka_koneksi = _database_file(db_path)
    conn = buka_koneksi()
    conn.executescript("""
        CREATE TABLE items (
            id INTEGER PRIMARY KEY,
            kode_item TEXT NOT NULL,
            nama_item TEXT NOT NULL,
            tipe TEXT NOT NULL,
            aktif INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE journal_entries (
            id INTEGER PRIMARY KEY,
            no_bukti TEXT NOT NULL
        );
        CREATE TABLE journal_lines (
            id INTEGER PRIMARY KEY,
            journal_entry_id INTEGER NOT NULL REFERENCES journal_entries(id)
        );
        CREATE TABLE inventory_movements (
            id INTEGER PRIMARY KEY,
            item_id INTEGER NOT NULL REFERENCES items(id),
            journal_entry_id INTEGER REFERENCES journal_entries(id),
            qty REAL NOT NULL
        );
        INSERT INTO items VALUES
            (1, 'BHN-001', 'Pupuk Lama', 'bahan', 1),
            (2, 'HSL-001', 'Cabai Rawit', 'hasil_panen', 1);
        INSERT INTO journal_entries VALUES (1, 'JU-001'), (2, 'JU-002');
        INSERT INTO journal_lines VALUES (1, 1), (2, 2);
        INSERT INTO inventory_movements VALUES (1, 1, 1, 5), (2, 2, 2, 100);
    """)
    conn.commit()
    conn.close()

    monkeypatch.setattr("database.schema.get_connection", buka_koneksi)

    migrasikan_persediaan_barang_dagang_saja()
    migrasikan_persediaan_barang_dagang_saja()  # harus aman dipanggil berulang

    conn = buka_koneksi()
    try:
        status = {
            row["kode_item"]: row["aktif"]
            for row in conn.execute("SELECT kode_item, aktif FROM items")
        }
        assert status == {"BHN-001": 0, "HSL-001": 1}
        assert conn.execute("SELECT COUNT(*) FROM inventory_movements").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM journal_entries").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM journal_lines").fetchone()[0] == 2
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        conn.close()


def test_transaksi_barang_dagang_menolak_item_bahan_dan_nonaktif(tmp_path, monkeypatch):
    db_path = tmp_path / "validasi_item.db"
    buka_koneksi = _database_file(db_path)
    conn = buka_koneksi()
    conn.executescript("""
        CREATE TABLE items (
            id INTEGER PRIMARY KEY,
            tipe TEXT NOT NULL,
            account_id INTEGER,
            aktif INTEGER NOT NULL
        );
        INSERT INTO items VALUES
            (1, 'hasil_panen', 1140, 1),
            (2, 'bahan', 1140, 1),
            (3, 'hasil_panen', 1140, 0);
    """)
    conn.commit()
    conn.close()

    monkeypatch.setattr("services.transaction_service.get_connection", buka_koneksi)

    _validasi_item_barang_dagang(1, 1140)
    with pytest.raises(ValueError, match="bukan hasil panen"):
        _validasi_item_barang_dagang(2, 1140)
    with pytest.raises(ValueError, match="nonaktif"):
        _validasi_item_barang_dagang(3, 1140)
    with pytest.raises(ValueError, match="tidak sesuai"):
        _validasi_item_barang_dagang(1, 9999)


@pytest.fixture
def db_barang_dagang_baru(tmp_path, monkeypatch):
    """Database uji untuk alur pendaftaran barang dagang sampai selector persediaan."""
    db_path = tmp_path / "barang_dagang_baru.db"
    buka_koneksi = _database_file(db_path)
    conn = buka_koneksi()
    conn.executescript("""
        CREATE TABLE accounts (
            id INTEGER PRIMARY KEY,
            kode_akun TEXT NOT NULL UNIQUE,
            aktif INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kode_item TEXT NOT NULL UNIQUE,
            nama_item TEXT NOT NULL,
            satuan TEXT NOT NULL,
            tipe TEXT NOT NULL CHECK (tipe IN ('bahan', 'hasil_panen')),
            komoditas TEXT NOT NULL DEFAULT 'cabai',
            account_id INTEGER,
            aktif INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE inventory_movements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            journal_entry_id INTEGER,
            tanggal TEXT NOT NULL,
            tipe_gerakan TEXT NOT NULL,
            qty REAL NOT NULL,
            harga_satuan INTEGER NOT NULL,
            total_nilai INTEGER NOT NULL,
            saldo_qty REAL NOT NULL,
            saldo_nilai INTEGER NOT NULL,
            harga_rata2 INTEGER NOT NULL,
            keterangan TEXT
        );
        INSERT INTO accounts (id, kode_akun, aktif) VALUES (1, '1140', 1);
        INSERT INTO items
            (kode_item, nama_item, satuan, tipe, komoditas, account_id, aktif)
        VALUES
            ('BHN-001', 'Pupuk Lama', 'kg', 'bahan', 'cabai', 1, 1),
            ('CAB-OLD', 'Cabai Arsip', 'kg', 'hasil_panen', 'cabai', 1, 0);
    """)
    conn.commit()
    conn.close()

    monkeypatch.setattr("services.master_data_service.get_connection", buka_koneksi)
    monkeypatch.setattr("services.inventory_service.get_connection", buka_koneksi)
    monkeypatch.setattr("services.dashboard_service.get_connection", buka_koneksi)
    monkeypatch.setattr("services.transaction_service.get_connection", buka_koneksi)
    return buka_koneksi


def test_barang_baru_muncul_di_pilihan_transaksi_dan_kartu_persediaan(db_barang_dagang_baru):
    """Cabai Ijo yang dibuat melalui Master Data langsung masuk daftar barang aktif."""
    item_id = tambah_item(
        kode_item="cab-002",
        nama_item="Cabai Ijo",
        satuan="kg",
        tipe="hasil_panen",
        komoditas="cabai",
        account_id=None,
    )

    item = next(
        item for item in ambil_daftar_item_persediaan()
        if item["id"] == item_id
    )
    assert item["kode_item"] == "CAB-002"
    assert item["nama_item"] == "Cabai Ijo"
    assert item["satuan"] == "kg"
    assert item["account_id"] == 1

    # Service transaksi harus menerima item baru dengan akun persediaan otomatis 1140.
    _validasi_item_barang_dagang(item_id, 1)

    # Item yang sama dengan mutasi stok tampil di ringkasan stok dashboard.
    conn = db_barang_dagang_baru()
    conn.execute(
        """
        INSERT INTO inventory_movements
            (item_id, tanggal, tipe_gerakan, qty, harga_satuan, total_nilai,
             saldo_qty, saldo_nilai, harga_rata2, keterangan)
        VALUES (?, '2026-11-01', 'masuk', 25, 30000, 750000,
                25, 750000, 30000, 'Stok awal Cabai Ijo')
        """,
        (item_id,),
    )
    conn.commit()
    conn.close()

    stok_dashboard = ambil_stok_persediaan()
    assert len(stok_dashboard) == 1
    assert stok_dashboard[0]["kode_item"] == "CAB-002"
    assert stok_dashboard[0]["saldo_qty"] == 25
    assert stok_dashboard[0]["saldo_nilai"] == 750000


@pytest.mark.parametrize(
    ("kode", "nama", "satuan", "pesan"),
    [
        ("", "Cabai Ijo", "kg", "Kode barang tidak boleh kosong"),
        ("CAB-003", "   ", "kg", "Nama barang tidak boleh kosong"),
        ("CAB-003", "Cabai Ijo", "", "Satuan barang tidak boleh kosong"),
        ("CAB-003", "Cabai Ijo", "gram", "Satuan barang dagang cabai harus kg"),
    ],
)
def test_tambah_barang_menolak_input_tidak_valid(
    db_barang_dagang_baru, kode, nama, satuan, pesan
):
    with pytest.raises(ValueError, match=pesan):
        tambah_item(kode, nama, satuan, "hasil_panen", "cabai", None)


def test_tambah_barang_menolak_kode_duplikat(db_barang_dagang_baru):
    tambah_item("CAB-004", "Cabai Keriting", "kg", "hasil_panen", "cabai", None)
    with pytest.raises(ValueError, match="sudah digunakan"):
        tambah_item("CAB-004", "Cabai Ijo", "kg", "hasil_panen", "cabai", None)
