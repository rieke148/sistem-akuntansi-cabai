"""
services/adjusting_service.py
-------------------------------
Tujuan  : Membuat ayat jurnal penyesuaian di akhir periode.
          Jenis penyesuaian yang didukung:
          1. Penyusutan aset tetap (dari depreciation_service, metode garis lurus)
          2. Amortisasi plastik mulsa (masa pakai 1,5 tahun)
          3. Akrual upah (sisa upah belum dibayar di akhir periode)
Input   : period_id, tanggal, parameter akun.
Output  : Jurnal penyesuaian disimpan ke journal_entries dengan journal_type='umum',
          no_bukti diawali 'PA-' (Penyesuaian Akhir).
Dipanggil oleh : views/10_ayat_penyesuaian.py

KONVENSI NOMOR BUKTI:
  Semua jurnal penyesuaian menggunakan prefix 'PA-' agar mudah diidentifikasi
  dan difilter dari Neraca Saldo sebelum penyesuaian.
  Format: 'PA-PENYUSUTAN-{asset_id}-{period_id}'
           'PA-MULSA-{period_id}'
           'PA-AKRUAL-UPAH-{period_id}'

CATATAN AKUNTANSI:
  Penyesuaian adalah proses mencatat beban/pendapatan yang sudah terjadi
  tapi belum dicatat di jurnal biasa, agar laporan keuangan akurat.
"""

import pandas as pd
from database.connection import get_connection
from services.depreciation_service import hitung_penyusutan_bulanan, hitung_amortisasi_mulsa_bulanan
from services.journal_service import simpan_jurnal


def buat_penyesuaian_penyusutan(
    period_id: int,
    tanggal: str,
) -> list[int]:
    """
    Membuat jurnal penyesuaian penyusutan untuk SEMUA aset aktif yang perlu disusutkan.
    Satu jurnal dibuat per aset (agar rincian jelas).

    Jurnal per aset:
      Debit : Beban Penyusutan [nama aset]   (akun beban dari account_id aset)
      Kredit: Akumulasi Penyusutan [nama aset] (akun akumulasi dari account_akum_id)

    Args:
        period_id : ID periode akuntansi.
        tanggal   : Tanggal jurnal penyesuaian 'YYYY-MM-DD'.

    Returns:
        List ID journal_entry yang dibuat. Kosong jika tidak ada aset disusutkan.

    Raises:
        ValueError: Jika aset tidak punya akun beban atau akun akumulasi.
    """
    koneksi = get_connection()
    try:
        # Ambil semua aset aktif yang perlu disusutkan
        aset_rows = koneksi.execute(
            """
            SELECT fa.id, fa.kode_aset, fa.nama_aset,
                   fa.account_id, fa.account_akum_id,
                   fa.kategori_aset
            FROM fixed_assets fa
            WHERE fa.aktif = 1
              AND fa.is_disusutkan = 1
            ORDER BY fa.kode_aset
            """
        ).fetchall()
    finally:
        koneksi.close()

    if not aset_rows:
        return []

    id_jurnal_dibuat = []

    for aset in aset_rows:
        asset_id = aset["id"]
        nama_aset = aset["nama_aset"]
        akun_beban_id = aset["account_id"]
        akun_akum_id = aset["account_akum_id"]

        # Validasi: aset harus punya akun beban dan akun akumulasi
        if not akun_beban_id or not akun_akum_id:
            raise ValueError(
                f"Aset '{nama_aset}' belum memiliki akun beban atau akun akumulasi penyusutan. "
                f"Lengkapi di Master Data → Aset Tetap."
            )

        # Hitung penyusutan bulan ini
        detail = hitung_penyusutan_bulanan(asset_id)
        penyusutan = detail["penyusutan_per_bulan"]

        if penyusutan <= 0:
            continue  # lewati aset tanpa penyusutan

        # Buat nomor bukti unik per aset per periode
        no_bukti = f"PA-PENYUSUTAN-{asset_id}-{period_id}"

        # Cek apakah sudah ada jurnal penyesuaian ini
        koneksi2 = get_connection()
        cek = koneksi2.execute(
            "SELECT id FROM journal_entries WHERE no_bukti = ?",
            (no_bukti,)
        ).fetchone()
        koneksi2.close()

        if cek:
            id_jurnal_dibuat.append(cek["id"])
            continue  # sudah ada, lewati

        # Baris jurnal: Debit beban penyusutan, Kredit akumulasi penyusutan
        baris_jurnal = [
            {"account_id": akun_beban_id, "debit": penyusutan, "kredit": 0},
            {"account_id": akun_akum_id, "debit": 0, "kredit": penyusutan},
        ]

        # Tentukan akun beban yang tepat berdasarkan kategori aset
        # (aset produksi → Beban Penyusutan Aset Produksi; aset non-produksi → non-produksi)
        keterangan = f"Penyesuaian: Penyusutan {nama_aset} bulan ini"

        journal_id = simpan_jurnal(
            period_id=period_id,
            tanggal=tanggal,
            no_bukti=no_bukti,
            journal_type="umum",
            keterangan=keterangan,
            baris=baris_jurnal,
        )
        id_jurnal_dibuat.append(journal_id)

    return id_jurnal_dibuat


def buat_penyesuaian_amortisasi_mulsa(
    period_id: int,
    tanggal: str,
    akun_beban_id: int,
    akun_akumulasi_id: int,
    harga_per_blok: int = 400_000,
    jumlah_blok: int = 5,
    umur_tahun: float = 1.5,
) -> int:
    """
    Membuat jurnal penyesuaian amortisasi plastik mulsa.

    Plastik mulsa dipakai selama 1,5 tahun (18 bulan).
    Amortisasi per bulan = total harga / 18 bulan.

    Jurnal:
      Debit : Beban Amortisasi Plastik Mulsa (5107)
      Kredit: Akumulasi Amortisasi Plastik Mulsa (1601K)

    Args:
        period_id        : ID periode akuntansi.
        tanggal          : Tanggal jurnal 'YYYY-MM-DD'.
        akun_beban_id    : ID akun Beban Amortisasi Plastik Mulsa.
        akun_akumulasi_id: ID akun Akumulasi Amortisasi Plastik Mulsa.
        harga_per_blok   : Harga plastik mulsa per blok (default Rp400.000).
        jumlah_blok      : Jumlah blok yang memakai mulsa (default 5 blok).
        umur_tahun       : Masa pakai mulsa dalam tahun (default 1,5 tahun).

    Returns:
        ID journal_entry yang dibuat. 0 jika sudah ada.

    Rumus:
        total_harga      = harga_per_blok × jumlah_blok = Rp400.000 × 5 = Rp2.000.000
        amortisasi/bulan = total_harga / (umur_tahun × 12) = Rp2.000.000 / 18 = Rp111.111
    """
    no_bukti = f"PA-MULSA-{period_id}"

    # Cek apakah sudah ada
    koneksi = get_connection()
    cek = koneksi.execute(
        "SELECT id FROM journal_entries WHERE no_bukti = ?",
        (no_bukti,)
    ).fetchone()
    koneksi.close()

    if cek:
        return cek["id"]

    # Hitung amortisasi bulanan menggunakan fungsi dari depreciation_service
    amortisasi = hitung_amortisasi_mulsa_bulanan(
        harga_per_blok=harga_per_blok,
        jumlah_blok=jumlah_blok,
        umur_tahun=umur_tahun,
    )

    if amortisasi <= 0:
        return 0

    baris_jurnal = [
        {"account_id": akun_beban_id, "debit": amortisasi, "kredit": 0},
        {"account_id": akun_akumulasi_id, "debit": 0, "kredit": amortisasi},
    ]

    keterangan = (
        f"Penyesuaian: Amortisasi Plastik Mulsa "
        f"({jumlah_blok} blok × Rp{harga_per_blok:,} / {int(umur_tahun*12)} bulan)"
    )

    journal_id = simpan_jurnal(
        period_id=period_id,
        tanggal=tanggal,
        no_bukti=no_bukti,
        journal_type="umum",
        keterangan=keterangan,
        baris=baris_jurnal,
    )
    return journal_id


def buat_penyesuaian_akrual_upah(
    period_id: int,
    tanggal: str,
    akun_beban_upah_id: int,
    akun_utang_gaji_id: int,
    jumlah_akrual: int,
) -> int:
    """
    Mencatat upah yang sudah menjadi beban tapi belum dibayar (akrual).
    Digunakan jika ada pekerja yang upah minggu-2 belum dibayar di akhir bulan.

    Jurnal:
      Debit : Beban Upah Langsung (5105)
      Kredit: Utang Gaji (2201)

    Args:
        period_id          : ID periode akuntansi.
        tanggal            : Tanggal jurnal 'YYYY-MM-DD'.
        akun_beban_upah_id : ID akun Beban Upah Langsung.
        akun_utang_gaji_id : ID akun Utang Gaji.
        jumlah_akrual      : Total upah yang belum dibayar (Rupiah, integer).

    Returns:
        ID journal_entry yang dibuat. 0 jika jumlah_akrual = 0 atau sudah ada.
    """
    if jumlah_akrual <= 0:
        return 0

    no_bukti = f"PA-AKRUAL-UPAH-{period_id}"

    # Cek apakah sudah ada
    koneksi = get_connection()
    cek = koneksi.execute(
        "SELECT id FROM journal_entries WHERE no_bukti = ?",
        (no_bukti,)
    ).fetchone()
    koneksi.close()

    if cek:
        return cek["id"]

    baris_jurnal = [
        {"account_id": akun_beban_upah_id, "debit": jumlah_akrual, "kredit": 0},
        {"account_id": akun_utang_gaji_id, "debit": 0, "kredit": jumlah_akrual},
    ]

    keterangan = "Penyesuaian: Akrual upah pekerja yang belum dibayar"

    journal_id = simpan_jurnal(
        period_id=period_id,
        tanggal=tanggal,
        no_bukti=no_bukti,
        journal_type="umum",
        keterangan=keterangan,
        baris=baris_jurnal,
    )
    return journal_id


def hapus_penyesuaian(no_bukti: str) -> bool:
    """
    Menghapus satu jurnal penyesuaian berdasarkan no_bukti.
    Hanya bisa menghapus jurnal yang diawali 'PA-'.

    Args:
        no_bukti : Nomor bukti jurnal penyesuaian.

    Returns:
        True jika berhasil dihapus, False jika tidak ditemukan.

    Raises:
        ValueError: Jika no_bukti tidak diawali 'PA-' (bukan penyesuaian).
    """
    if not no_bukti.startswith("PA-"):
        raise ValueError(
            "Hanya jurnal penyesuaian (no. bukti diawali 'PA-') yang bisa dihapus di sini."
        )

    koneksi = get_connection()
    try:
        row = koneksi.execute(
            "SELECT id FROM journal_entries WHERE no_bukti = ?",
            (no_bukti,)
        ).fetchone()

        if not row:
            return False

        # journal_lines terhapus otomatis (ON DELETE CASCADE dari schema.py)
        koneksi.execute(
            "DELETE FROM journal_entries WHERE no_bukti = ?",
            (no_bukti,)
        )
        koneksi.commit()
        return True
    finally:
        koneksi.close()


def ambil_ringkasan_penyesuaian(period_id: int) -> pd.DataFrame:
    """
    Mengambil semua jurnal penyesuaian yang sudah dibuat untuk satu periode.
    Jurnal penyesuaian dikenali dari no_bukti yang diawali 'PA-'.

    Args:
        period_id : ID periode akuntansi.

    Returns:
        DataFrame: no_bukti | keterangan | tanggal | total_debit | total_kredit

    Dipakai untuk tampilan daftar penyesuaian yang sudah dibuat.
    """
    koneksi = get_connection()
    try:
        rows = koneksi.execute(
            """
            SELECT
                je.no_bukti,
                je.tanggal,
                je.keterangan,
                COALESCE(SUM(jl.debit), 0)  AS total_debit,
                COALESCE(SUM(jl.kredit), 0) AS total_kredit
            FROM journal_entries je
            LEFT JOIN journal_lines jl ON jl.journal_entry_id = je.id
            WHERE je.period_id = ?
              AND je.no_bukti LIKE 'PA-%'
            GROUP BY je.id, je.no_bukti, je.tanggal, je.keterangan
            ORDER BY je.tanggal ASC, je.no_bukti ASC
            """,
            (period_id,)
        ).fetchall()
    finally:
        koneksi.close()

    if not rows:
        return pd.DataFrame(columns=["no_bukti", "tanggal", "keterangan", "total_debit", "total_kredit"])

    return pd.DataFrame([dict(r) for r in rows])


def cek_penyesuaian_sudah_ada(period_id: int, jenis: str) -> bool:
    """
    Mengecek apakah penyesuaian jenis tertentu sudah dibuat untuk periode ini.

    Args:
        period_id : ID periode.
        jenis     : 'penyusutan', 'mulsa', 'akrual_upah'.

    Returns:
        True jika sudah ada, False jika belum.
    """
    prefix_map = {
        "penyusutan": "PA-PENYUSUTAN-%",
        "mulsa": f"PA-MULSA-{period_id}",
        "akrual_upah": f"PA-AKRUAL-UPAH-{period_id}",
    }

    if jenis not in prefix_map:
        return False

    koneksi = get_connection()
    try:
        if jenis == "penyusutan":
            row = koneksi.execute(
                """
                SELECT COUNT(*) AS jumlah FROM journal_entries
                WHERE period_id = ? AND no_bukti LIKE 'PA-PENYUSUTAN-%'
                """,
                (period_id,)
            ).fetchone()
            return int(row["jumlah"]) > 0
        else:
            no_cari = prefix_map[jenis]
            row = koneksi.execute(
                "SELECT id FROM journal_entries WHERE no_bukti = ? AND period_id = ?",
                (no_cari, period_id)
            ).fetchone()
            return row is not None
    finally:
        koneksi.close()
