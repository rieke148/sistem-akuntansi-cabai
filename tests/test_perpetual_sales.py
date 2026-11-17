"""
tests/test_perpetual_sales.py
------------------------------
Tujuan  : Memastikan transaksi penjualan membentuk jurnal pendapatan dan HPP
          serta mengurangi stok dengan sistem perpetual.
Jalankan: pytest tests/test_perpetual_sales.py -v
"""

from unittest.mock import patch

from services import transaction_service as ts


def _hpp_contoh(*args, **kwargs):
    """Menyiapkan data HPP contoh tanpa mengakses database."""
    return {
        "item_id": 77,
        "nama_item": "Cabai Rawit",
        "akun_persediaan_id": 13,
        "akun_hpp_id": 18,
        "total_hpp": 500_000,
        "harga_rata2": 25_000,
    }


def test_penjualan_tunai_mencatat_jurnal_pendapatan_dan_hpp(monkeypatch):
    """Penjualan tunai harus memuat empat baris jurnal perpetual."""
    tersimpan = {}
    mutasi = []

    monkeypatch.setattr(ts, "_siapkan_hpp_penjualan", _hpp_contoh)
    monkeypatch.setattr(ts, "_label_periode", lambda period_id: "OKT26")
    monkeypatch.setattr(ts, "generate_nomor_bukti", lambda *args: "KM-OKT26-001")
    monkeypatch.setattr(
        ts, "simpan_jurnal",
        lambda **kwargs: tersimpan.update(kwargs) or 91,
    )
    monkeypatch.setattr(
        ts, "_catat_hpp_penjualan",
        lambda *args: mutasi.append(args),
    )

    entry_id = ts.catat_penjualan_tunai(
        period_id=1,
        tanggal="2026-10-03",
        pelanggan="Restoran Pronto",
        jumlah_kg=20,
        harga_per_kg=60_000,
        akun_kas_id=1,
        akun_penjualan_id=2,
        item_panen_id=77,
        hpp_estimasi=500_000,
    )

    assert entry_id == 91
    assert tersimpan["journal_type"] == "penerimaan_kas"
    assert len(tersimpan["baris"]) == 4
    assert tersimpan["baris"][0] == {"account_id": 1, "debit": 1_200_000, "kredit": 0}
    assert tersimpan["baris"][1] == {"account_id": 2, "debit": 0, "kredit": 1_200_000}
    assert tersimpan["baris"][2] == {"account_id": 18, "debit": 500_000, "kredit": 0}
    assert tersimpan["baris"][3] == {"account_id": 13, "debit": 0, "kredit": 500_000}
    assert len(mutasi) == 1


def test_penjualan_tunai_tidak_menyimpan_jika_stok_tidak_cukup(monkeypatch):
    """Validasi stok harus terjadi sebelum jurnal disimpan."""
    monkeypatch.setattr(
        ts, "_siapkan_hpp_penjualan",
        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("Stok tidak mencukupi")),
    )
    jurnal_dipanggil = []
    monkeypatch.setattr(ts, "simpan_jurnal", lambda **kwargs: jurnal_dipanggil.append(kwargs))

    try:
        ts.catat_penjualan_tunai(
            period_id=1, tanggal="2026-10-03", pelanggan="Pelanggan",
            jumlah_kg=20, harga_per_kg=60_000, akun_kas_id=1,
            akun_penjualan_id=2, item_panen_id=77,
        )
    except ValueError as error:
        assert "Stok tidak mencukupi" in str(error)
    else:
        raise AssertionError("Penjualan tanpa stok seharusnya ditolak.")

    assert jurnal_dipanggil == []


class _KoneksiPalsu:
    """Koneksi sederhana untuk memeriksa pencatatan piutang tempo."""

    def __init__(self):
        self.sql = None
        self.params = None
        self.committed = False
        self.closed = False

    def execute(self, sql, params):
        self.sql = sql
        self.params = params
        return self

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


def test_penjualan_tempo_mencatat_hpp_dan_piutang(monkeypatch):
    """Penjualan tempo tetap mengurangi stok pada saat faktur dibuat."""
    tersimpan = {}
    mutasi = []
    koneksi = _KoneksiPalsu()

    monkeypatch.setattr(ts, "_siapkan_hpp_penjualan", _hpp_contoh)
    monkeypatch.setattr(ts, "_label_periode", lambda period_id: "OKT26")
    monkeypatch.setattr(ts, "generate_nomor_bukti", lambda *args: "JL-OKT26-001")
    monkeypatch.setattr(ts, "_ambil_parameter", lambda nama: "7")
    monkeypatch.setattr(ts, "get_connection", lambda: koneksi)
    monkeypatch.setattr(
        ts, "simpan_jurnal",
        lambda **kwargs: tersimpan.update(kwargs) or 92,
    )
    monkeypatch.setattr(
        ts, "_catat_hpp_penjualan",
        lambda *args: mutasi.append(args),
    )

    entry_id, no_faktur = ts.catat_penjualan_tempo(
        period_id=1,
        tanggal="2026-10-05",
        customer_id=3,
        pelanggan_nama="Supermarket Laris",
        jumlah_kg=20,
        harga_per_kg=60_000,
        akun_piutang_id=4,
        akun_penjualan_id=2,
        item_panen_id=77,
        hpp_estimasi=500_000,
    )

    assert entry_id == 92
    assert no_faktur == "JL-OKT26-001"
    assert tersimpan["journal_type"] == "penjualan"
    assert len(tersimpan["baris"]) == 4
    assert len(mutasi) == 1
    assert koneksi.params[0] == 92
    assert koneksi.params[1] == 3
    assert koneksi.params[4] == "2026-10-12"
    assert koneksi.params[5] == 1_200_000
    assert koneksi.committed is True
    assert koneksi.closed is True
