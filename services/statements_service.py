"""
services/statements_service.py
--------------------------------
Tujuan  : Menyusun 4 Laporan Keuangan dari data NS Disesuaikan.
Input   : period_id (int).
Output  : Dict per laporan berisi angka dan DataFrame detail.
Dipanggil oleh : views/12_laporan_keuangan.py

URUTAN PENYUSUNAN (penting — saling bergantung):
  1. Laba Rugi          → menghasilkan laba_bersih
  2. Perubahan Ekuitas  → pakai laba_bersih, menghasilkan modal_akhir
  3. Neraca             → pakai modal_akhir, validasi Aset = Liab + Ekuitas
  4. Arus Kas           → opsional, metode langsung dari journal_lines

SUMBER DATA:
  - Semua angka diambil dari hitung_neraca_saldo(termasuk_penyesuaian=True)
  - Modal Awal = saldo akun 'Modal Disetor' (3101) + 'Laba Ditahan' (3201)
    dari opening_balances
"""

import pandas as pd
from database.connection import get_connection
from services.trial_balance_service import hitung_neraca_saldo


# ---------------------------------------------------------------------------
# Fungsi utama — 4 laporan keuangan
# ---------------------------------------------------------------------------

def susun_laporan_laba_rugi(period_id: int) -> dict:
    """
    Menyusun Laporan Laba Rugi (Income Statement).

    Rumus:
        Laba Bersih = Total Pendapatan - (Total Beban Produksi + Total Beban Operasional)

    Args:
        period_id : ID periode.

    Returns:
        Dict berisi:
        {
          'pendapatan'         : list of dict [{nama_akun, jumlah}, ...],
          'beban_produksi'     : list of dict [{nama_akun, jumlah}, ...],
          'beban_operasional'  : list of dict [{nama_akun, jumlah}, ...],
          'total_pendapatan'   : int,
          'total_beban_produksi' : int,
          'total_beban_operasional' : int,
          'total_beban'        : int,
          'laba_bersih'        : int,  (positif=laba, negatif=rugi)
        }
    """
    # Ambil NS Disesuaikan (semua jurnal termasuk penyesuaian PA-)
    df_ns = hitung_neraca_saldo(period_id, termasuk_penyesuaian=True)

    if df_ns.empty:
        return _laba_rugi_kosong()

    hasil = _laba_rugi_kosong()

    for _, baris in df_ns.iterrows():
        kategori = baris["kategori"]
        kode = str(baris["kode_akun"])
        nama = baris["nama_akun"]
        # Pendapatan: saldo normal Kredit → kredit - debit
        # Beban: saldo normal Debit → debit - kredit (memperhitungkan retur/kredit panen)
        if baris["saldo_normal"] == "Debit":
            jumlah = int(baris["debit"]) - int(baris["kredit"])
        else:
            jumlah = int(baris["kredit"]) - int(baris["debit"])

        if kategori == "Pendapatan":
            hasil["pendapatan"].append({"nama_akun": nama, "jumlah": jumlah})
            hasil["total_pendapatan"] += jumlah

        elif kategori == "Beban Produksi":
            hasil["beban_produksi"].append({"nama_akun": nama, "jumlah": jumlah})
            hasil["total_beban_produksi"] += jumlah
            if kode == "5108":
                hasil["hpp_penjualan"].append({"nama_akun": nama, "jumlah": jumlah})
                hasil["total_hpp_penjualan"] += jumlah
            else:
                hasil["beban_produksi_lain"].append({"nama_akun": nama, "jumlah": jumlah})
                hasil["total_beban_produksi_lain"] += jumlah

        elif kategori == "Beban Operasional":
            hasil["beban_operasional"].append({"nama_akun": nama, "jumlah": jumlah})
            hasil["total_beban_operasional"] += jumlah

    # HPP dipisahkan agar laba kotor dapat dibaca: Penjualan - HPP Penjualan.
    hasil["laba_kotor"] = hasil["total_pendapatan"] - hasil["total_hpp_penjualan"]
    hasil["total_beban"] = hasil["total_beban_produksi"] + hasil["total_beban_operasional"]
    hasil["laba_bersih"] = hasil["total_pendapatan"] - hasil["total_beban"]

    return hasil


def susun_laporan_perubahan_ekuitas(
    period_id: int,
    laba_bersih: int,
) -> dict:
    """
    Menyusun Laporan Perubahan Ekuitas.

    Karena ini PT (tidak ada Prive):
        Modal Akhir = Modal Awal + Setoran Modal Periode Ini + Laba Bersih

    Args:
        period_id  : ID periode.
        laba_bersih: Laba bersih dari susun_laporan_laba_rugi().

    Returns:
        Dict berisi:
        {
          'modal_disetor_awal' : int,   (saldo Modal Disetor dari opening_balances)
          'laba_ditahan_awal'  : int,   (saldo Laba Ditahan dari opening_balances)
          'modal_awal'         : int,   (modal_disetor_awal + laba_ditahan_awal)
          'tambahan_setoran'   : int,   (setoran modal selama periode — dari jurnal)
          'laba_bersih'        : int,
          'modal_akhir'        : int,
          'detail'             : list of dict (baris demi baris laporan)
        }
    """
    # Ambil saldo awal Modal Disetor (3101) dan Laba Ditahan (3201)
    modal_disetor_awal, laba_ditahan_awal = _ambil_saldo_awal_ekuitas(period_id)

    # Tambahan setoran modal selama periode (jurnal kredit ke akun Modal Disetor)
    tambahan_setoran = _ambil_tambahan_setoran_modal(period_id)

    modal_awal = modal_disetor_awal + laba_ditahan_awal
    modal_akhir = modal_awal + tambahan_setoran + laba_bersih

    detail = [
        {"keterangan": "Modal Disetor (saldo awal)",       "jumlah": modal_disetor_awal},
        {"keterangan": "Laba Ditahan (saldo awal)",        "jumlah": laba_ditahan_awal},
        {"keterangan": "Modal Awal",                       "jumlah": modal_awal, "is_subtotal": True},
        {"keterangan": "Tambahan Setoran Modal",           "jumlah": tambahan_setoran},
        {"keterangan": "Laba Bersih Periode Ini",          "jumlah": laba_bersih},
        {"keterangan": "Modal Akhir",                      "jumlah": modal_akhir, "is_total": True},
    ]

    return {
        "modal_disetor_awal": modal_disetor_awal,
        "laba_ditahan_awal": laba_ditahan_awal,
        "modal_awal": modal_awal,
        "tambahan_setoran": tambahan_setoran,
        "laba_bersih": laba_bersih,
        "modal_akhir": modal_akhir,
        "detail": detail,
    }


def susun_neraca(period_id: int, modal_akhir: int) -> dict:
    """
    Menyusun Neraca (Balance Sheet) dalam bentuk laporan.

    Validasi: Total Aset == Total Liabilitas + Total Ekuitas

    Args:
        period_id  : ID periode.
        modal_akhir: Ekuitas akhir dari susun_laporan_perubahan_ekuitas().

    Returns:
        Dict berisi:
        {
          'aset_lancar'       : list of dict [{nama_akun, jumlah}, ...],
          'aset_tetap'        : list of dict [{nama_akun, jumlah}, ...],
          'total_aset_lancar' : int,
          'total_aset_tetap'  : int,
          'total_aset'        : int,
          'liabilitas_lancar' : list of dict,
          'liabilitas_jangka_panjang' : list of dict,
          'total_liabilitas'  : int,
          'ekuitas'           : list of dict,
          'total_ekuitas'     : int,
          'total_liabilitas_ekuitas' : int,
          'seimbang'          : bool,
        }
    """
    # Ambil NS Disesuaikan sebagai sumber saldo
    df_ns = hitung_neraca_saldo(period_id, termasuk_penyesuaian=True)

    hasil = {
        "aset_lancar": [],
        "aset_tetap": [],
        "total_aset_lancar": 0,
        "total_aset_tetap": 0,
        "total_aset": 0,
        "liabilitas_lancar": [],
        "liabilitas_jangka_panjang": [],
        "total_liabilitas": 0,
        "ekuitas": [],
        "total_ekuitas": modal_akhir,
        "total_liabilitas_ekuitas": 0,
        "seimbang": False,
    }

    if df_ns.empty:
        return hasil

    for _, baris in df_ns.iterrows():
        kategori = baris["kategori"]
        nama = baris["nama_akun"]
        kode = baris["kode_akun"]
        # Saldo normal Debit: debit - kredit; Saldo normal Kredit: kredit - debit
        saldo_normal = baris["saldo_normal"]
        if saldo_normal == "Debit":
            jumlah = int(baris["debit"]) - int(baris["kredit"])
        else:
            jumlah = int(baris["kredit"]) - int(baris["debit"])

        if kategori == "Aset":
            # Aset lancar: Kas & Bank (11xx), Piutang (12xx), Persediaan (13xx), Perlengkapan (14xx)
            # Aset tetap: 15xx dan aset lain-lain (16xx)
            is_kontra = kode.endswith("K")  # konvensi kode kontra pakai suffix K
            if kode.startswith(("11", "12", "13", "14")):
                hasil["aset_lancar"].append({
                    "nama_akun": nama,
                    "jumlah": jumlah,
                    "is_kontra": is_kontra,
                    "kode": kode,
                })
                if not is_kontra:
                    hasil["total_aset_lancar"] += jumlah
                else:
                    hasil["total_aset_lancar"] -= jumlah
            else:
                # Aset tetap dan aset tidak lancar lainnya (1501 ke atas)
                hasil["aset_tetap"].append({
                    "nama_akun": nama,
                    "jumlah": jumlah,
                    "is_kontra": is_kontra,
                    "kode": kode,
                })
                if not is_kontra:
                    hasil["total_aset_tetap"] += jumlah
                else:
                    hasil["total_aset_tetap"] -= jumlah

        elif kategori == "Liabilitas":
            # Pisahkan liabilitas lancar (21xx) dan jangka panjang (22xx ke atas)
            if kode.startswith("21"):
                hasil["liabilitas_lancar"].append({"nama_akun": nama, "jumlah": jumlah, "kode": kode})
                hasil["total_liabilitas"] += jumlah
            else:
                hasil["liabilitas_jangka_panjang"].append({"nama_akun": nama, "jumlah": jumlah, "kode": kode})
                hasil["total_liabilitas"] += jumlah

        # Akun Ekuitas dari NS (Modal Disetor, Laba Ditahan) — nilainya dipakai
        # hanya untuk referensi; total ekuitas pakai modal_akhir dari Perubahan Ekuitas

    # Hitung total aset
    hasil["total_aset"] = hasil["total_aset_lancar"] + hasil["total_aset_tetap"]

    # Susun baris ekuitas untuk tampilan (pakai modal_akhir yang sudah dihitung)
    hasil["ekuitas"] = [
        {"nama_akun": "Modal Disetor dan Laba Bersih", "jumlah": modal_akhir}
    ]
    hasil["total_ekuitas"] = modal_akhir

    # Total sisi kanan neraca
    hasil["total_liabilitas_ekuitas"] = hasil["total_liabilitas"] + hasil["total_ekuitas"]

    # Validasi: Aset = Liabilitas + Ekuitas
    hasil["seimbang"] = hasil["total_aset"] == hasil["total_liabilitas_ekuitas"]

    return hasil


def susun_arus_kas(period_id: int) -> dict:
    """
    Menyusun Laporan Arus Kas metode langsung.

    Metode langsung: membaca langsung penerimaan dan pengeluaran kas
    dari journal_lines untuk akun Kas (kode 1101) dan Bank (kode 1102).

    Args:
        period_id : ID periode.

    Returns:
        Dict berisi:
        {
          'operasi'  : {'penerimaan': [...], 'pengeluaran': [...], 'neto': int},
          'investasi': {'penerimaan': [...], 'pengeluaran': [...], 'neto': int},
          'pendanaan': {'penerimaan': [...], 'pengeluaran': [...], 'neto': int},
          'kenaikan_penurunan_kas': int,
          'saldo_kas_awal': int,
          'saldo_kas_akhir': int,
        }
    """
    # Ambil semua transaksi yang melibatkan Kas dan Bank
    koneksi = get_connection()
    try:
        rows = koneksi.execute(
            """
            SELECT je.journal_type, je.keterangan,
                   jl.debit, jl.kredit,
                   a.kode_akun, a.nama_akun
            FROM journal_lines jl
            JOIN journal_entries je ON jl.journal_entry_id = je.id
            JOIN accounts a ON jl.account_id = a.id
            WHERE je.period_id = ?
              AND je.no_bukti NOT LIKE 'JP-%'  -- kecualikan jurnal penutup
            ORDER BY je.tanggal, je.id
            """,
            (period_id,)
        ).fetchall()

        # Saldo awal Kas dan Bank
        saldo_awal_rows = koneksi.execute(
            """
            SELECT a.kode_akun, ob.saldo_debit, ob.saldo_kredit
            FROM opening_balances ob
            JOIN accounts a ON ob.account_id = a.id
            WHERE ob.period_id = ?
              AND a.kode_akun IN ('1101', '1102')
            """,
            (period_id,)
        ).fetchall()
    finally:
        koneksi.close()

    # Hitung saldo kas awal
    saldo_kas_awal = sum(
        int(r["saldo_debit"]) - int(r["saldo_kredit"])
        for r in saldo_awal_rows
    )

    # Klasifikasikan arus kas berdasarkan journal_type
    # Penerimaan kas = debit di akun kas/bank; Pengeluaran = kredit di akun kas/bank
    penerimaan_operasi = 0
    pengeluaran_operasi = 0
    penerimaan_investasi = 0
    pengeluaran_investasi = 0
    penerimaan_pendanaan = 0
    pengeluaran_pendanaan = 0

    detail_operasi_masuk = []
    detail_operasi_keluar = []
    detail_investasi_masuk = []
    detail_investasi_keluar = []
    detail_pendanaan_masuk = []
    detail_pendanaan_keluar = []

    for r in rows:
        kode = r["kode_akun"]
        jenis = r["journal_type"]
        ket = r["keterangan"] or ""
        debit = int(r["debit"])
        kredit = int(r["kredit"])

        # Hanya proses baris yang melibatkan akun kas atau bank
        if kode not in ("1101", "1102"):
            continue

        if debit > 0:
            # Penerimaan kas
            if jenis in ("penerimaan_kas",) or "setoran modal" in ket.lower():
                if "setoran modal" in ket.lower() or "modal" in ket.lower():
                    penerimaan_pendanaan += debit
                    detail_pendanaan_masuk.append({"keterangan": ket, "jumlah": debit})
                else:
                    penerimaan_operasi += debit
                    detail_operasi_masuk.append({"keterangan": ket, "jumlah": debit})
            else:
                penerimaan_operasi += debit
                detail_operasi_masuk.append({"keterangan": ket, "jumlah": debit})

        if kredit > 0:
            # Pengeluaran kas
            if "beli aset" in ket.lower() or jenis == "pengeluaran_kas" and _adalah_beli_aset(ket):
                pengeluaran_investasi += kredit
                detail_investasi_keluar.append({"keterangan": ket, "jumlah": kredit})
            else:
                pengeluaran_operasi += kredit
                detail_operasi_keluar.append({"keterangan": ket, "jumlah": kredit})

    neto_operasi = penerimaan_operasi - pengeluaran_operasi
    neto_investasi = penerimaan_investasi - pengeluaran_investasi
    neto_pendanaan = penerimaan_pendanaan - pengeluaran_pendanaan
    kenaikan_kas = neto_operasi + neto_investasi + neto_pendanaan
    saldo_kas_akhir = saldo_kas_awal + kenaikan_kas

    return {
        "operasi": {
            "penerimaan": detail_operasi_masuk,
            "pengeluaran": detail_operasi_keluar,
            "total_penerimaan": penerimaan_operasi,
            "total_pengeluaran": pengeluaran_operasi,
            "neto": neto_operasi,
        },
        "investasi": {
            "penerimaan": detail_investasi_masuk,
            "pengeluaran": detail_investasi_keluar,
            "total_penerimaan": penerimaan_investasi,
            "total_pengeluaran": pengeluaran_investasi,
            "neto": neto_investasi,
        },
        "pendanaan": {
            "penerimaan": detail_pendanaan_masuk,
            "pengeluaran": detail_pendanaan_keluar,
            "total_penerimaan": penerimaan_pendanaan,
            "total_pengeluaran": pengeluaran_pendanaan,
            "neto": neto_pendanaan,
        },
        "kenaikan_penurunan_kas": kenaikan_kas,
        "saldo_kas_awal": saldo_kas_awal,
        "saldo_kas_akhir": saldo_kas_akhir,
    }


# ---------------------------------------------------------------------------
# Fungsi pembantu (private)
# ---------------------------------------------------------------------------

def _laba_rugi_kosong() -> dict:
    """Mengembalikan struktur dict kosong untuk Laba Rugi."""
    return {
        "pendapatan": [],
        "hpp_penjualan": [],
        "beban_produksi": [],
        "beban_produksi_lain": [],
        "beban_operasional": [],
        "total_pendapatan": 0,
        "total_hpp_penjualan": 0,
        "laba_kotor": 0,
        "total_beban_produksi": 0,
        "total_beban_produksi_lain": 0,
        "total_beban_operasional": 0,
        "total_beban": 0,
        "laba_bersih": 0,
    }


def _ambil_saldo_awal_ekuitas(period_id: int) -> tuple[int, int]:
    """
    Mengambil saldo awal Modal Disetor (3101) dan Laba Ditahan (3201)
    dari tabel opening_balances.

    Returns:
        (modal_disetor_awal, laba_ditahan_awal) dalam Rupiah.
    """
    koneksi = get_connection()
    try:
        rows = koneksi.execute(
            """
            SELECT a.kode_akun,
                   ob.saldo_debit,
                   ob.saldo_kredit
            FROM opening_balances ob
            JOIN accounts a ON ob.account_id = a.id
            WHERE ob.period_id = ?
              AND a.kode_akun IN ('3101', '3201')
            """,
            (period_id,)
        ).fetchall()
    finally:
        koneksi.close()

    modal_disetor = 0
    laba_ditahan = 0
    for r in rows:
        # Akun ekuitas: saldo normal Kredit → pakai saldo_kredit - saldo_debit
        saldo = int(r["saldo_kredit"]) - int(r["saldo_debit"])
        if r["kode_akun"] == "3101":
            modal_disetor = saldo
        elif r["kode_akun"] == "3201":
            laba_ditahan = saldo

    return modal_disetor, laba_ditahan


def _ambil_tambahan_setoran_modal(period_id: int) -> int:
    """
    Mengambil total setoran modal tambahan selama periode ini.
    Setoran modal = jurnal kredit ke akun Modal Disetor (3101) di periode ini.

    Returns:
        int: total tambahan setoran modal dalam Rupiah.
    """
    koneksi = get_connection()
    try:
        row = koneksi.execute(
            """
            SELECT COALESCE(SUM(jl.kredit), 0) AS total_kredit
            FROM journal_lines jl
            JOIN journal_entries je ON jl.journal_entry_id = je.id
            JOIN accounts a ON jl.account_id = a.id
            WHERE je.period_id = ?
              AND a.kode_akun = '3101'
              AND je.no_bukti NOT LIKE 'JP-%'
            """,
            (period_id,)
        ).fetchone()
    finally:
        koneksi.close()

    return int(row["total_kredit"]) if row else 0


def _adalah_beli_aset(keterangan: str) -> bool:
    """
    Menentukan apakah suatu keterangan jurnal adalah pembelian aset tetap
    (untuk klasifikasi arus kas investasi).
    """
    kata_kunci_aset = ["beli aset", "pembelian aset", "aset tetap", "tanah", "bangunan",
                       "kendaraan", "komputer", "peralatan"]
    ket_lower = keterangan.lower()
    return any(k in ket_lower for k in kata_kunci_aset)
