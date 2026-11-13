"""
database/seed.py
----------------
Tujuan  : Mengisi database dengan data contoh (Oktober 2026) agar
          semua laporan bisa langsung dicoba tanpa input manual.
          Data ini berdasarkan hasil observasi 26 Oktober 2026.

PENTING: Angka modal/kas ADALAH CONTOH - ganti dengan data asli.
         Semua catatan 'CONTOH' menandai data yang harus diganti.

Input   : Database kosong (tabel sudah dibuat oleh schema.py).
Output  : Database terisi data contoh siap pakai.
Dipanggil oleh : app.py (saat startup, jika db kosong)
"""

import sqlite3
from datetime import date, timedelta
from database.connection import get_connection


# ---------------------------------------------------------------
# HELPER: Fungsi pembantu insert yang lebih ringkas
# ---------------------------------------------------------------
def _insert(cursor: sqlite3.Cursor, tabel: str, data: dict) -> int:
    """Insert satu baris ke tabel dan kembalikan ID yang dibuat."""
    kolom = ", ".join(data.keys())
    placeholder = ", ".join("?" for _ in data)
    nilai = list(data.values())
    cursor.execute(f"INSERT INTO {tabel} ({kolom}) VALUES ({placeholder})", nilai)
    return cursor.lastrowid


def _buat_jurnal(
    cursor: sqlite3.Cursor,
    period_id: int,
    tanggal: str,
    no_bukti: str,
    journal_type: str,
    keterangan: str,
    baris: list[dict],
    komoditas: str = "cabai",
    pihak_terkait: str | None = None,
) -> int:
    """
    Membuat header jurnal + baris-barisnya sekaligus.
    Otomatis memvalidasi debit == kredit sebelum insert.

    baris = list of dict: [{"account_id": X, "debit": Y, "kredit": Z}, ...]
    """
    # Validasi: total debit harus sama dengan total kredit
    total_debit = sum(b["debit"] for b in baris)
    total_kredit = sum(b["kredit"] for b in baris)
    if total_debit != total_kredit:
        raise ValueError(
            f"Jurnal {no_bukti} tidak seimbang! "
            f"Debit={total_debit:,} Kredit={total_kredit:,}"
        )

    # Insert header jurnal
    entry_id = _insert(cursor, "journal_entries", {
        "period_id": period_id,
        "tanggal": tanggal,
        "no_bukti": no_bukti,
        "journal_type": journal_type,
        "keterangan": keterangan,
        "komoditas": komoditas,
        "pihak_terkait": pihak_terkait,
    })

    # Insert setiap baris debit/kredit
    for b in baris:
        _insert(cursor, "journal_lines", {
            "journal_entry_id": entry_id,
            "account_id": b["account_id"],
            "debit": b["debit"],
            "kredit": b["kredit"],
            "keterangan": b.get("keterangan"),
        })

    return entry_id


# ---------------------------------------------------------------
# FUNGSI UTAMA SEED
# ---------------------------------------------------------------
def jalankan_seed() -> None:
    """
    Mengisi database dengan semua data contoh.
    Dipanggil sekali saat database masih kosong.
    """
    koneksi = get_connection()
    cursor = koneksi.cursor()

    print("[SEED] Menjalankan seed data...")

    # ===== A. PARAMETER OPERASIONAL =====
    _seed_parameter(cursor)

    # ===== B. BAGAN AKUN (COA) =====
    akun = _seed_bagan_akun(cursor)

    # ===== C. PERIODE =====
    period_id = _seed_periode(cursor)

    # ===== D. MASTER DATA =====
    pelanggan = _seed_pelanggan(cursor)
    supplier = _seed_supplier(cursor)
    item = _seed_item(cursor, akun)
    pekerja = _seed_pekerja(cursor)
    aset_tetap = _seed_aset_tetap(cursor, akun)
    _seed_blok_lahan(cursor)

    # ===== E. SALDO AWAL (1 Oktober 2026) =====
    _seed_saldo_awal(cursor, period_id, akun)

    # ===== F. TRANSAKSI OKTOBER 2026 =====
    _seed_transaksi(cursor, period_id, akun, pelanggan, supplier, item, pekerja)

    koneksi.commit()
    tutup_connection(koneksi)
    print("[OK] Seed data berhasil! Database siap digunakan.")


def _seed_parameter(cursor: sqlite3.Cursor) -> None:
    """Mengisi parameter operasional yang bisa diubah user."""
    params = [
        ("upah_tetap_harian", "90000", "Rupiah/hari",
         "Upah harian pekerja tetap (konfirmasi narasumber)"),
        ("upah_tambahan_harian", "120000", "Rupiah/hari",
         "Upah harian tenaga tambahan (cangkul/olah tanah)"),
        ("hasil_panen_per_pohon_gram", "700", "gram/pohon/panen",
         "Rata-rata hasil 700g per pohon per pemetikan (konfirmasi narasumber)"),
        ("frekuensi_panen_per_minggu", "3", "kali/minggu",
         "Pemetikan 3x seminggu"),
        ("harga_jual_cabai_default", "60000", "Rupiah/kg",
         "Harga saat observasi - FLUKTUATIF, ubah sesuai aktual"),
        ("alokasi_listrik_cabai_persen", "30", "persen",
         "Alokasi listrik untuk komoditas cabai (dari Rp500.000/bln)"),
        ("listrik_total_bulanan", "500000", "Rupiah/bulan",
         "Total tagihan listrik pompa per bulan"),
        ("bbm_pengiriman_mingguan", "150000", "Rupiah/minggu",
         "BBM pengiriman per minggu"),
        ("bbm_operasional_mingguan", "250000", "Rupiah/minggu",
         "BBM operasional per minggu"),
        ("sewa_traktor_per_hari", "350000", "Rupiah/hari",
         "Sewa traktor per hari pakai"),
        ("jatuh_tempo_piutang_hari", "7", "hari",
         "Jatuh tempo piutang penjualan tempo"),
    ]
    for kunci, nilai, satuan, catatan in params:
        _insert(cursor, "parameters", {
            "kunci": kunci,
            "nilai": nilai,
            "satuan": satuan,
            "catatan": catatan,
        })


def _seed_bagan_akun(cursor: sqlite3.Cursor) -> dict:
    """
    Membuat Bagan Akun (COA) lengkap.
    Mengembalikan dict {kode_akun: id} untuk referensi.
    """
    # Format: (kode, nama, kategori, saldo_normal, is_kontra)
    daftar_akun = [
        # --- ASET (1xxx) ---
        ("1101", "Kas", "Aset", "Debit", 0),
        ("1102", "Bank BRI", "Aset", "Debit", 0),
        ("1201", "Piutang Usaha", "Aset", "Debit", 0),
        ("1301", "Persediaan Bibit Cabai", "Aset", "Debit", 0),
        ("1302", "Persediaan Pupuk", "Aset", "Debit", 0),
        ("1303", "Persediaan Pupuk NPK", "Aset", "Debit", 0),
        ("1304", "Persediaan Pestisida", "Aset", "Debit", 0),
        ("1305", "Persediaan Plastik Mulsa", "Aset", "Debit", 0),
        ("1306", "Persediaan Bambu", "Aset", "Debit", 0),
        ("1307", "Persediaan Cabai Rawit (kg)", "Aset", "Debit", 0),
        ("1401", "Perlengkapan Pertanian", "Aset", "Debit", 0),
        ("1501", "Tanah", "Aset", "Debit", 0),
        ("1502", "Bangunan Kantor dan Gudang", "Aset", "Debit", 0),
        ("1502K", "Akumulasi Penyusutan Bangunan", "Aset", "Kredit", 1),
        ("1503", "Kendaraan", "Aset", "Debit", 0),
        ("1503K", "Akumulasi Penyusutan Kendaraan", "Aset", "Kredit", 1),
        ("1504", "Komputer", "Aset", "Debit", 0),
        ("1504K", "Akumulasi Penyusutan Komputer", "Aset", "Kredit", 1),
        ("1505", "Peralatan Pertanian", "Aset", "Debit", 0),
        ("1505K", "Akumulasi Penyusutan Peralatan", "Aset", "Kredit", 1),
        ("1601", "Plastik Mulsa (Perlengkapan)", "Aset", "Debit", 0),
        ("1601K", "Akumulasi Amortisasi Plastik Mulsa", "Aset", "Kredit", 1),

        # --- LIABILITAS (2xxx) ---
        ("2101", "Utang Usaha", "Liabilitas", "Kredit", 0),
        ("2201", "Utang Gaji", "Liabilitas", "Kredit", 0),
        ("2202", "Utang Listrik", "Liabilitas", "Kredit", 0),
        ("2203", "Utang Lain-lain", "Liabilitas", "Kredit", 0),

        # --- EKUITAS (3xxx) ---
        ("3101", "Modal Disetor", "Ekuitas", "Kredit", 0),
        ("3201", "Laba Ditahan", "Ekuitas", "Kredit", 0),
        ("3301", "Ikhtisar Laba Rugi", "Ekuitas", "Kredit", 0),

        # --- PENDAPATAN (4xxx) ---
        ("4101", "Penjualan Cabai Rawit", "Pendapatan", "Kredit", 0),
        ("4102", "Penjualan Selada", "Pendapatan", "Kredit", 0),
        ("4103", "Penjualan Melon", "Pendapatan", "Kredit", 0),
        ("4901", "Pendapatan Lain-lain", "Pendapatan", "Kredit", 0),

        # --- BEBAN PRODUKSI (5xxx) ---
        ("5101", "Beban Bibit", "Beban Produksi", "Debit", 0),
        ("5102", "Beban Pupuk", "Beban Produksi", "Debit", 0),
        ("5103", "Beban Pestisida", "Beban Produksi", "Debit", 0),
        ("5104", "Beban Bahan Produksi Lain", "Beban Produksi", "Debit", 0),
        ("5105", "Beban Upah Langsung", "Beban Produksi", "Debit", 0),
        ("5106", "Beban Penyusutan Aset Produksi", "Beban Produksi", "Debit", 0),
        ("5107", "Beban Amortisasi Plastik Mulsa", "Beban Produksi", "Debit", 0),

        # --- BEBAN OPERASIONAL (6xxx) ---
        ("6101", "Beban Listrik", "Beban Operasional", "Debit", 0),
        ("6102", "Beban BBM Pengiriman", "Beban Operasional", "Debit", 0),
        ("6103", "Beban BBM Operasional", "Beban Operasional", "Debit", 0),
        ("6104", "Beban Sewa Traktor", "Beban Operasional", "Debit", 0),
        ("6105", "Beban Penyusutan Aset Non-Produksi", "Beban Operasional", "Debit", 0),
        ("6901", "Beban Lain-lain", "Beban Operasional", "Debit", 0),
    ]

    akun_map = {}  # {kode_akun: id}
    for kode, nama, kategori, saldo_normal, is_kontra in daftar_akun:
        akun_id = _insert(cursor, "accounts", {
            "kode_akun": kode,
            "nama_akun": nama,
            "kategori": kategori,
            "saldo_normal": saldo_normal,
            "is_kontra": is_kontra,
        })
        akun_map[kode] = akun_id

    return akun_map


def _seed_periode(cursor: sqlite3.Cursor) -> int:
    """Membuat periode Oktober 2026."""
    period_id = _insert(cursor, "periods", {
        "tahun": 2026,
        "bulan": 10,
        "nama_bulan": "Oktober 2026",
        "status": "buka",
    })
    return period_id


def _seed_pelanggan(cursor: sqlite3.Cursor) -> dict:
    """Membuat data pelanggan. Mengembalikan dict {nama: id}."""
    pelanggan_list = [
        ("Restoran Pronto", "restoran"),
        ("Supermarket Laris", "supermarket"),
        ("UMKM Bu Sri", "umkm"),
        ("Restoran Sederhana", "restoran"),
        ("Pasar Swalayan Maju", "supermarket"),
    ]
    result = {}
    for nama, tipe in pelanggan_list:
        pid = _insert(cursor, "customers", {"nama": nama, "tipe": tipe})
        result[nama] = pid
    return result


def _seed_supplier(cursor: sqlite3.Cursor) -> dict:
    """Membuat data supplier."""
    sid = _insert(cursor, "suppliers", {
        "nama": "Toko Sido Panen",
        "telepon": "024-XXXXXXX",
        "alamat": "Bandungan, Kab. Semarang",
    })
    return {"Toko Sido Panen": sid}


def _seed_item(cursor: sqlite3.Cursor, akun: dict) -> dict:
    """Membuat item persediaan."""
    items_list = [
        # (kode, nama, satuan, tipe, komoditas, kode_akun)
        ("BHN-001", "Bibit Cabai Rawit", "batang", "bahan", "cabai", "1301"),
        ("BHN-002", "Pupuk (Awal Tanam)", "karung", "bahan", "cabai", "1302"),
        ("BHN-003", "Pupuk NPK", "paket/blok", "bahan", "cabai", "1303"),
        ("BHN-004", "Pestisida", "paket/blok", "bahan", "cabai", "1304"),
        ("BHN-005", "Plastik Mulsa", "roll (200m)", "bahan", "cabai", "1305"),
        ("BHN-006", "Bambu", "batang", "bahan", "cabai", "1306"),
        ("HSL-001", "Cabai Rawit", "kg", "hasil_panen", "cabai", "1307"),
    ]
    result = {}
    for kode, nama, satuan, tipe, komoditas, kode_akun in items_list:
        iid = _insert(cursor, "items", {
            "kode_item": kode,
            "nama_item": nama,
            "satuan": satuan,
            "tipe": tipe,
            "komoditas": komoditas,
            "account_id": akun[kode_akun],
        })
        result[kode] = iid
    return result


def _seed_pekerja(cursor: sqlite3.Cursor) -> dict:
    """Membuat data pekerja. 4 pekerja cabai + 1 selada/melon."""
    pekerja_list = [
        ("Ahmad Suparto", "tetap", 90000, "cabai"),
        ("Budi Santoso", "tetap", 90000, "cabai"),
        ("Cahyo Wibowo", "tetap", 90000, "cabai"),
        ("Dian Rahayu", "tetap", 90000, "cabai"),
        ("Eko Prasetyo", "tetap", 90000, "selada"),
    ]
    result = {}
    for nama, tipe, upah, komoditas in pekerja_list:
        eid = _insert(cursor, "employees", {
            "nama": nama,
            "tipe_pekerja": tipe,
            "upah_harian": upah,
            "komoditas": komoditas,
        })
        result[nama] = eid
    return result


def _seed_aset_tetap(cursor: sqlite3.Cursor, akun: dict) -> dict:
    """
    Membuat data aset tetap berdasarkan hasil observasi.
    Jumlah unit peralatan masih CONTOH — user perlu mengisi di Master Data.
    """
    # (kode, nama, kategori, tgl_perolehan, harga, residu, umur_th, unit, is_susut, akun, akun_akum)
    aset_list = [
        ("AT-001", "Tanah Lahan 2.471m2", "Tanah",
         "2024-11-01", 2_500_000_000, 0, 50, 1, 0, "1501", None),
        ("AT-002", "Bangunan Kantor dan Gudang", "Bangunan",
         "2024-11-01", 120_000_000, 12_000_000, 20, 1, 1, "1502", "1502K"),
        ("AT-003", "Kendaraan Operasional", "Kendaraan",
         "2024-11-01", 250_000_000, 25_000_000, 8, 1, 1, "1503", "1503K"),
        ("AT-004", "Komputer", "Komputer",
         "2024-11-01", 15_000_000, 1_500_000, 4, 1, 1, "1504", "1504K"),
        # Peralatan — jumlah unit CONTOH, user harus input
        ("AT-005", "Cangkul", "Peralatan",
         "2024-11-01", 150_000, 0, 3, 5, 1, "1505", "1505K"),
        ("AT-006", "Sabit", "Peralatan",
         "2024-11-01", 110_000, 0, 3, 5, 1, "1505", "1505K"),
        ("AT-007", "Tangki Semprot", "Peralatan",
         "2024-11-01", 450_000, 0, 5, 3, 1, "1505", "1505K"),
        ("AT-008", "Keranjang Panen", "Peralatan",
         "2024-11-01", 40_000, 0, 2, 10, 1, "1505", "1505K"),
        ("AT-009", "Timbangan", "Peralatan",
         "2024-11-01", 500_000, 50_000, 4, 2, 1, "1505", "1505K"),
        ("AT-010", "Selang Air", "Peralatan",
         "2024-11-01", 250_000, 0, 5, 4, 1, "1505", "1505K"),
        ("AT-011", "Ember", "Peralatan",
         "2024-11-01", 35_000, 0, 2, 10, 1, "1505", "1505K"),
        ("AT-012", "Pompa Air", "Peralatan",
         "2024-11-01", 1_500_000, 150_000, 4, 2, 1, "1505", "1505K"),
    ]
    result = {}
    for kode, nama, kat, tgl, harga, residu, umur, unit, is_susut, kd_akun, kd_akum in aset_list:
        akum_id = akun[kd_akum] if kd_akum else None
        aid = _insert(cursor, "fixed_assets", {
            "kode_aset": kode,
            "nama_aset": nama,
            "kategori_aset": kat,
            "tanggal_perolehan": tgl,
            "harga_perolehan": harga,
            "nilai_residu": residu,
            "umur_ekonomis_tahun": umur,
            "jumlah_unit": unit,
            "is_disusutkan": is_susut,
            "account_id": akun[kd_akun],
            "account_akum_id": akum_id,
            "keterangan": "CONTOH - verifikasi jumlah unit dengan data asli",
        })
        result[kode] = aid
    return result


def _seed_blok_lahan(cursor: sqlite3.Cursor) -> None:
    """Membuat data 5 blok lahan cabai."""
    blok_list = [
        # (kode, pohon, tgl_tanam, luas_m2)
        ("A", 1000, "2024-11-01", 494),
        ("B", 1000, "2025-03-01", 494),
        ("C", 1000, "2025-07-01", 494),
        ("D", 1000, "2025-11-01", 494),
        ("E", 1000, "2026-03-01", 494),
    ]
    for kode, pohon, tgl, luas in blok_list:
        _insert(cursor, "blok_lahan", {
            "kode_blok": kode,
            "jumlah_pohon": pohon,
            "tanggal_tanam": tgl,
            "komoditas": "cabai",
            "luas_m2": luas,
            "jarak_tanam_cm": 100,
            "keterangan": "CONTOH - verifikasi tanggal tanam dengan data asli",
        })


def _seed_saldo_awal(
    cursor: sqlite3.Cursor,
    period_id: int,
    akun: dict,
) -> None:
    """
    Saldo awal 1 Oktober 2026.
    SEMUA ANGKA ADALAH CONTOH — user wajib mengganti dengan data asli.

    Kas: Rp500.000.000 (CONTOH)
    Modal Disetor: Rp3.410.000.000 (CONTOH — total aset tetap + kas awal)
    """
    catatan = "⚠️ CONTOH - ganti dengan data asli"
    # Debit: Kas
    _insert(cursor, "opening_balances", {
        "period_id": period_id,
        "account_id": akun["1101"],
        "saldo_debit": 500_000_000,
        "saldo_kredit": 0,
        "catatan": catatan,
    })
    # Debit: Tanah
    _insert(cursor, "opening_balances", {
        "period_id": period_id,
        "account_id": akun["1501"],
        "saldo_debit": 2_500_000_000,
        "saldo_kredit": 0,
        "catatan": catatan,
    })
    # Debit: Bangunan
    _insert(cursor, "opening_balances", {
        "period_id": period_id,
        "account_id": akun["1502"],
        "saldo_debit": 120_000_000,
        "saldo_kredit": 0,
        "catatan": catatan,
    })
    # Debit: Kendaraan
    _insert(cursor, "opening_balances", {
        "period_id": period_id,
        "account_id": akun["1503"],
        "saldo_debit": 250_000_000,
        "saldo_kredit": 0,
        "catatan": catatan,
    })
    # Debit: Komputer
    _insert(cursor, "opening_balances", {
        "period_id": period_id,
        "account_id": akun["1504"],
        "saldo_debit": 15_000_000,
        "saldo_kredit": 0,
        "catatan": catatan,
    })
    # Kredit: Modal Disetor (selisih = jumlah semua aset)
    _insert(cursor, "opening_balances", {
        "period_id": period_id,
        "account_id": akun["3101"],
        "saldo_debit": 0,
        "saldo_kredit": 3_385_000_000,
        "catatan": catatan,
    })


def _seed_transaksi(
    cursor: sqlite3.Cursor,
    period_id: int,
    akun: dict,
    pelanggan: dict,
    supplier: dict,
    item: dict,
    pekerja: dict,
) -> None:
    """
    Membuat 25+ transaksi realistis Oktober 2026.
    Semua transaksi mengikuti pemetaan jurnal di PROJECT_BRIEF.md.
    """
    # -----------------------------------------------------------------
    # Shortcut ID akun yang sering dipakai
    # -----------------------------------------------------------------
    KAS = akun["1101"]
    PIUTANG = akun["1201"]
    PERSEDIAAN_PUPUK = akun["1302"]
    PERSEDIAAN_PESTISIDA = akun["1304"]
    PERSEDIAAN_BAMBU = akun["1306"]
    PENJUALAN = akun["4101"]
    BEBAN_PUPUK = akun["5102"]
    BEBAN_PESTISIDA = akun["5103"]
    BEBAN_BAHAN_LAIN = akun["5104"]
    BEBAN_UPAH = akun["5105"]
    BEBAN_LISTRIK = akun["6101"]
    BEBAN_BBM_KIRIM = akun["6102"]
    BEBAN_BBM_OPS = akun["6103"]
    BEBAN_TRAKTOR = akun["6104"]
    UTANG_USAHA = akun["2101"]
    UTANG_GAJI = akun["2201"]

    no = 1  # nomor urut bukti

    def nb(prefix: str) -> str:
        """Generate nomor bukti."""
        nonlocal no
        kode = f"{prefix}-OKT26-{no:03d}"
        no += 1
        return kode

    # -----------------------------------------------------------------
    # 1. Penjualan TUNAI ke Restoran Pronto (3 Okt, 300 kg @ Rp60.000)
    # -----------------------------------------------------------------
    jml = 300 * 60_000  # = 18.000.000
    _buat_jurnal(cursor, period_id, "2026-10-03", nb("KM"),
                 "penerimaan_kas",
                 "Penjualan cabai tunai ke Restoran Pronto 300 kg @ Rp60.000",
                 [{"account_id": KAS, "debit": jml, "kredit": 0},
                  {"account_id": PENJUALAN, "debit": 0, "kredit": jml}],
                 pihak_terkait="Restoran Pronto")

    # -----------------------------------------------------------------
    # 2. Penjualan TEMPO ke Supermarket Laris (5 Okt, 500 kg @ Rp60.000)
    # -----------------------------------------------------------------
    jml = 500 * 60_000  # = 30.000.000
    eid = _buat_jurnal(cursor, period_id, "2026-10-05", nb("JL"),
                       "penjualan",
                       "Penjualan cabai tempo ke Supermarket Laris 500 kg @ Rp60.000",
                       [{"account_id": PIUTANG, "debit": jml, "kredit": 0},
                        {"account_id": PENJUALAN, "debit": 0, "kredit": jml}],
                       pihak_terkait="Supermarket Laris")
    # Catat piutang
    _insert(cursor, "receivables", {
        "journal_entry_id": eid,
        "customer_id": pelanggan["Supermarket Laris"],
        "no_faktur": "FAKTUR-OKT26-001",
        "tanggal_faktur": "2026-10-05",
        "tanggal_jatuh_tempo": "2026-10-12",
        "jumlah": jml,
        "jumlah_terbayar": 0,
        "status": "belum_lunas",
    })

    # -----------------------------------------------------------------
    # 3. Beli Pupuk TUNAI di Toko Sido Panen (6 Okt, 4 karung Rp720.000)
    # -----------------------------------------------------------------
    jml = 720_000
    _buat_jurnal(cursor, period_id, "2026-10-06", nb("KK"),
                 "pengeluaran_kas",
                 "Beli pupuk awal tanam 4 karung di Toko Sido Panen",
                 [{"account_id": PERSEDIAAN_PUPUK, "debit": jml, "kredit": 0},
                  {"account_id": KAS, "debit": 0, "kredit": jml}],
                 pihak_terkait="Toko Sido Panen")
    # Catat kartu persediaan
    _insert(cursor, "inventory_movements", {
        "item_id": item["BHN-002"],
        "tanggal": "2026-10-06",
        "tipe_gerakan": "masuk",
        "qty": 4,
        "harga_satuan": 180_000,
        "total_nilai": jml,
        "saldo_qty": 4,
        "saldo_nilai": jml,
        "harga_rata2": 180_000,
        "keterangan": "Pembelian tunai Toko Sido Panen",
    })

    # -----------------------------------------------------------------
    # 4. Beli Pestisida TUNAI (7 Okt, 1 blok Rp380.000)
    # -----------------------------------------------------------------
    jml = 380_000
    _buat_jurnal(cursor, period_id, "2026-10-07", nb("KK"),
                 "pengeluaran_kas",
                 "Beli pestisida 5 jenis untuk 1 blok di Toko Sido Panen",
                 [{"account_id": PERSEDIAAN_PESTISIDA, "debit": jml, "kredit": 0},
                  {"account_id": KAS, "debit": 0, "kredit": jml}],
                 pihak_terkait="Toko Sido Panen")
    _insert(cursor, "inventory_movements", {
        "item_id": item["BHN-004"],
        "tanggal": "2026-10-07",
        "tipe_gerakan": "masuk",
        "qty": 1,
        "harga_satuan": 380_000,
        "total_nilai": 380_000,
        "saldo_qty": 1,
        "saldo_nilai": 380_000,
        "harga_rata2": 380_000,
        "keterangan": "Pembelian tunai Toko Sido Panen",
    })

    # -----------------------------------------------------------------
    # 5. BBM Pengiriman minggu ke-1 (7 Okt, Rp150.000)
    # -----------------------------------------------------------------
    _buat_jurnal(cursor, period_id, "2026-10-07", nb("KK"),
                 "pengeluaran_kas",
                 "BBM pengiriman minggu ke-1 Oktober",
                 [{"account_id": BEBAN_BBM_KIRIM, "debit": 150_000, "kredit": 0},
                  {"account_id": KAS, "debit": 0, "kredit": 150_000}])

    # -----------------------------------------------------------------
    # 6. BBM Operasional minggu ke-1 (7 Okt, Rp250.000)
    # -----------------------------------------------------------------
    _buat_jurnal(cursor, period_id, "2026-10-07", nb("KK"),
                 "pengeluaran_kas",
                 "BBM operasional minggu ke-1 Oktober",
                 [{"account_id": BEBAN_BBM_OPS, "debit": 250_000, "kredit": 0},
                  {"account_id": KAS, "debit": 0, "kredit": 250_000}])

    # -----------------------------------------------------------------
    # 7. Penjualan TUNAI ke UMKM Bu Sri (8 Okt, 150 kg @ Rp60.000)
    # -----------------------------------------------------------------
    jml = 150 * 60_000  # = 9.000.000
    _buat_jurnal(cursor, period_id, "2026-10-08", nb("KM"),
                 "penerimaan_kas",
                 "Penjualan cabai tunai ke UMKM Bu Sri 150 kg @ Rp60.000",
                 [{"account_id": KAS, "debit": jml, "kredit": 0},
                  {"account_id": PENJUALAN, "debit": 0, "kredit": jml}],
                 pihak_terkait="UMKM Bu Sri")

    # -----------------------------------------------------------------
    # 8. Terima pelunasan piutang dari Supermarket Laris (12 Okt)
    # -----------------------------------------------------------------
    jml = 30_000_000
    _buat_jurnal(cursor, period_id, "2026-10-12", nb("KM"),
                 "penerimaan_kas",
                 "Terima pelunasan piutang dari Supermarket Laris",
                 [{"account_id": KAS, "debit": jml, "kredit": 0},
                  {"account_id": PIUTANG, "debit": 0, "kredit": jml}],
                 pihak_terkait="Supermarket Laris")
    # Update status piutang jadi lunas
    cursor.execute(
        "UPDATE receivables SET status='lunas', jumlah_terbayar=? WHERE no_faktur=?",
        (jml, "FAKTUR-OKT26-001")
    )

    # -----------------------------------------------------------------
    # 9. Bayar upah 2 minggu pertama pekerja cabai (14 Okt)
    #    4 pekerja x 14 hari x Rp90.000 = Rp5.040.000
    # -----------------------------------------------------------------
    jml = 4 * 14 * 90_000  # = 5.040.000
    _buat_jurnal(cursor, period_id, "2026-10-14", nb("KK"),
                 "pengeluaran_kas",
                 "Upah pekerja cabai 2 minggu pertama (1-14 Okt, 4 orang x 14 hari)",
                 [{"account_id": BEBAN_UPAH, "debit": jml, "kredit": 0},
                  {"account_id": KAS, "debit": 0, "kredit": jml}])
    # Catat absensi
    for nama_pk in ["Ahmad Suparto", "Budi Santoso", "Cahyo Wibowo", "Dian Rahayu"]:
        _insert(cursor, "attendance", {
            "employee_id": pekerja[nama_pk],
            "period_id": period_id,
            "periode_bayar": "minggu1",
            "hari_kerja": 14,
            "total_upah": 14 * 90_000,
            "sudah_dibayar": 1,
        })

    # -----------------------------------------------------------------
    # 10. Bayar listrik (15 Okt, Rp500.000 — total, Rp150.000 alokasi cabai)
    # -----------------------------------------------------------------
    _buat_jurnal(cursor, period_id, "2026-10-15", nb("KK"),
                 "pengeluaran_kas",
                 "Bayar listrik pompa Oktober (alokasi cabai Rp150.000 dari total Rp500.000)",
                 [{"account_id": BEBAN_LISTRIK, "debit": 150_000, "kredit": 0},
                  {"account_id": KAS, "debit": 0, "kredit": 150_000}])

    # -----------------------------------------------------------------
    # 11. Penjualan TEMPO ke Restoran Sederhana (15 Okt, 400 kg @ Rp62.000)
    # -----------------------------------------------------------------
    jml = 400 * 62_000  # = 24.800.000
    eid = _buat_jurnal(cursor, period_id, "2026-10-15", nb("JL"),
                       "penjualan",
                       "Penjualan cabai tempo ke Restoran Sederhana 400 kg @ Rp62.000",
                       [{"account_id": PIUTANG, "debit": jml, "kredit": 0},
                        {"account_id": PENJUALAN, "debit": 0, "kredit": jml}],
                       pihak_terkait="Restoran Sederhana")
    _insert(cursor, "receivables", {
        "journal_entry_id": eid,
        "customer_id": pelanggan["Restoran Sederhana"],
        "no_faktur": "FAKTUR-OKT26-002",
        "tanggal_faktur": "2026-10-15",
        "tanggal_jatuh_tempo": "2026-10-22",
        "jumlah": jml,
        "jumlah_terbayar": 0,
        "status": "belum_lunas",
    })

    # -----------------------------------------------------------------
    # 12. BBM Pengiriman minggu ke-2 (14 Okt)
    # -----------------------------------------------------------------
    _buat_jurnal(cursor, period_id, "2026-10-14", nb("KK"),
                 "pengeluaran_kas",
                 "BBM pengiriman minggu ke-2 Oktober",
                 [{"account_id": BEBAN_BBM_KIRIM, "debit": 150_000, "kredit": 0},
                  {"account_id": KAS, "debit": 0, "kredit": 150_000}])

    # -----------------------------------------------------------------
    # 13. BBM Operasional minggu ke-2 (14 Okt)
    # -----------------------------------------------------------------
    _buat_jurnal(cursor, period_id, "2026-10-14", nb("KK"),
                 "pengeluaran_kas",
                 "BBM operasional minggu ke-2 Oktober",
                 [{"account_id": BEBAN_BBM_OPS, "debit": 250_000, "kredit": 0},
                  {"account_id": KAS, "debit": 0, "kredit": 250_000}])

    # -----------------------------------------------------------------
    # 14. Sewa traktor (17 Okt, 2 hari, Rp700.000)
    # -----------------------------------------------------------------
    jml = 2 * 350_000  # = 700.000
    _buat_jurnal(cursor, period_id, "2026-10-17", nb("KK"),
                 "pengeluaran_kas",
                 "Sewa traktor 2 hari untuk pengolahan lahan blok E",
                 [{"account_id": BEBAN_TRAKTOR, "debit": jml, "kredit": 0},
                  {"account_id": KAS, "debit": 0, "kredit": jml}])

    # -----------------------------------------------------------------
    # 15. Beli bambu (18 Okt, 5000 batang @ Rp550 = Rp2.750.000)
    # -----------------------------------------------------------------
    jml = 5000 * 550  # = 2.750.000
    _buat_jurnal(cursor, period_id, "2026-10-18", nb("KK"),
                 "pengeluaran_kas",
                 "Beli 5.000 batang bambu untuk penyangga cabai @ Rp550",
                 [{"account_id": PERSEDIAAN_BAMBU, "debit": jml, "kredit": 0},
                  {"account_id": KAS, "debit": 0, "kredit": jml}],
                 pihak_terkait="Toko Sido Panen")
    _insert(cursor, "inventory_movements", {
        "item_id": item["BHN-006"],
        "tanggal": "2026-10-18",
        "tipe_gerakan": "masuk",
        "qty": 5000,
        "harga_satuan": 550,
        "total_nilai": jml,
        "saldo_qty": 5000,
        "saldo_nilai": jml,
        "harga_rata2": 550,
        "keterangan": "Pembelian tunai",
    })

    # -----------------------------------------------------------------
    # 16. Penjualan TUNAI ke Pasar Swalayan Maju (20 Okt, 600 kg @ Rp58.000)
    # -----------------------------------------------------------------
    jml = 600 * 58_000  # = 34.800.000
    _buat_jurnal(cursor, period_id, "2026-10-20", nb("KM"),
                 "penerimaan_kas",
                 "Penjualan cabai tunai ke Pasar Swalayan Maju 600 kg @ Rp58.000",
                 [{"account_id": KAS, "debit": jml, "kredit": 0},
                  {"account_id": PENJUALAN, "debit": 0, "kredit": jml}],
                 pihak_terkait="Pasar Swalayan Maju")

    # -----------------------------------------------------------------
    # 17. Terima pelunasan piutang dari Restoran Sederhana (22 Okt)
    # -----------------------------------------------------------------
    jml = 24_800_000
    _buat_jurnal(cursor, period_id, "2026-10-22", nb("KM"),
                 "penerimaan_kas",
                 "Terima pelunasan piutang Restoran Sederhana",
                 [{"account_id": KAS, "debit": jml, "kredit": 0},
                  {"account_id": PIUTANG, "debit": 0, "kredit": jml}],
                 pihak_terkait="Restoran Sederhana")
    cursor.execute(
        "UPDATE receivables SET status='lunas', jumlah_terbayar=? WHERE no_faktur=?",
        (jml, "FAKTUR-OKT26-002")
    )

    # -----------------------------------------------------------------
    # 18. BBM Pengiriman & Operasional minggu ke-3 (21 Okt)
    # -----------------------------------------------------------------
    _buat_jurnal(cursor, period_id, "2026-10-21", nb("KK"),
                 "pengeluaran_kas",
                 "BBM pengiriman minggu ke-3 Oktober",
                 [{"account_id": BEBAN_BBM_KIRIM, "debit": 150_000, "kredit": 0},
                  {"account_id": KAS, "debit": 0, "kredit": 150_000}])
    _buat_jurnal(cursor, period_id, "2026-10-21", nb("KK"),
                 "pengeluaran_kas",
                 "BBM operasional minggu ke-3 Oktober",
                 [{"account_id": BEBAN_BBM_OPS, "debit": 250_000, "kredit": 0},
                  {"account_id": KAS, "debit": 0, "kredit": 250_000}])

    # -----------------------------------------------------------------
    # 19. Penjualan TEMPO ke Supermarket Laris (23 Okt, 450 kg @ Rp65.000)
    # -----------------------------------------------------------------
    jml = 450 * 65_000  # = 29.250.000
    eid = _buat_jurnal(cursor, period_id, "2026-10-23", nb("JL"),
                       "penjualan",
                       "Penjualan cabai tempo ke Supermarket Laris 450 kg @ Rp65.000",
                       [{"account_id": PIUTANG, "debit": jml, "kredit": 0},
                        {"account_id": PENJUALAN, "debit": 0, "kredit": jml}],
                       pihak_terkait="Supermarket Laris")
    _insert(cursor, "receivables", {
        "journal_entry_id": eid,
        "customer_id": pelanggan["Supermarket Laris"],
        "no_faktur": "FAKTUR-OKT26-003",
        "tanggal_faktur": "2026-10-23",
        "tanggal_jatuh_tempo": "2026-10-30",
        "jumlah": jml,
        "jumlah_terbayar": 0,
        "status": "belum_lunas",
    })

    # -----------------------------------------------------------------
    # 20. Bayar upah 2 minggu ke-2 pekerja cabai (28 Okt)
    #     4 pekerja x 14 hari x Rp90.000 = Rp5.040.000
    # -----------------------------------------------------------------
    jml = 4 * 14 * 90_000
    _buat_jurnal(cursor, period_id, "2026-10-28", nb("KK"),
                 "pengeluaran_kas",
                 "Upah pekerja cabai 2 minggu ke-2 (15-28 Okt, 4 orang x 14 hari)",
                 [{"account_id": BEBAN_UPAH, "debit": jml, "kredit": 0},
                  {"account_id": KAS, "debit": 0, "kredit": jml}])
    for nama_pk in ["Ahmad Suparto", "Budi Santoso", "Cahyo Wibowo", "Dian Rahayu"]:
        _insert(cursor, "attendance", {
            "employee_id": pekerja[nama_pk],
            "period_id": period_id,
            "periode_bayar": "minggu2",
            "hari_kerja": 14,
            "total_upah": 14 * 90_000,
            "sudah_dibayar": 1,
        })

    # -----------------------------------------------------------------
    # 21. BBM minggu ke-4 (28 Okt)
    # -----------------------------------------------------------------
    _buat_jurnal(cursor, period_id, "2026-10-28", nb("KK"),
                 "pengeluaran_kas",
                 "BBM pengiriman minggu ke-4 Oktober",
                 [{"account_id": BEBAN_BBM_KIRIM, "debit": 150_000, "kredit": 0},
                  {"account_id": KAS, "debit": 0, "kredit": 150_000}])
    _buat_jurnal(cursor, period_id, "2026-10-28", nb("KK"),
                 "pengeluaran_kas",
                 "BBM operasional minggu ke-4 Oktober",
                 [{"account_id": BEBAN_BBM_OPS, "debit": 250_000, "kredit": 0},
                  {"account_id": KAS, "debit": 0, "kredit": 250_000}])

    # -----------------------------------------------------------------
    # 22. Penjualan TUNAI ke Restoran Pronto (28 Okt, 350 kg @ Rp62.000)
    # -----------------------------------------------------------------
    jml = 350 * 62_000  # = 21.700.000
    _buat_jurnal(cursor, period_id, "2026-10-28", nb("KM"),
                 "penerimaan_kas",
                 "Penjualan cabai tunai ke Restoran Pronto 350 kg @ Rp62.000",
                 [{"account_id": KAS, "debit": jml, "kredit": 0},
                  {"account_id": PENJUALAN, "debit": 0, "kredit": jml}],
                 pihak_terkait="Restoran Pronto")

    # -----------------------------------------------------------------
    # 23. PEMBELIAN KREDIT (SIMULASI) — pupuk NPK 1 blok dari supplier
    #     Catatan: Dari observasi, semua beli TUNAI. Ini simulasi untuk
    #     memenuhi syarat fitur Jurnal Pembelian. Tercantum di laporan.
    # -----------------------------------------------------------------
    jml = 1_190_000
    _buat_jurnal(cursor, period_id, "2026-10-25", nb("PB"),
                 "pembelian",
                 "[SIMULASI] Beli pupuk NPK 1 blok kredit dari Toko Sido Panen",
                 [{"account_id": PERSEDIAAN_PESTISIDA, "debit": jml, "kredit": 0},
                  {"account_id": UTANG_USAHA, "debit": 0, "kredit": jml}],
                 pihak_terkait="Toko Sido Panen")

    # -----------------------------------------------------------------
    # 24. Setoran modal tambahan (1 Okt, Rp50.000.000 — CONTOH)
    # -----------------------------------------------------------------
    _buat_jurnal(cursor, period_id, "2026-10-01", nb("KM"),
                 "penerimaan_kas",
                 "Setoran modal tambahan (CONTOH - ganti nominal asli)",
                 [{"account_id": KAS, "debit": 50_000_000, "kredit": 0},
                  {"account_id": akun["3101"], "debit": 0, "kredit": 50_000_000}])

    # -----------------------------------------------------------------
    # 25. Pemakaian bahan (Jurnal Umum) — Pupuk dipakai ke blok A (31 Okt)
    # -----------------------------------------------------------------
    jml = 720_000
    _buat_jurnal(cursor, period_id, "2026-10-31", nb("JU"),
                 "umum",
                 "Pemakaian pupuk ke blok A (penyesuaian persediaan)",
                 [{"account_id": BEBAN_PUPUK, "debit": jml, "kredit": 0},
                  {"account_id": PERSEDIAAN_PUPUK, "debit": 0, "kredit": jml}])
    _insert(cursor, "inventory_movements", {
        "item_id": item["BHN-002"],
        "tanggal": "2026-10-31",
        "tipe_gerakan": "keluar",
        "qty": 4,
        "harga_satuan": 180_000,
        "total_nilai": jml,
        "saldo_qty": 0,
        "saldo_nilai": 0,
        "harga_rata2": 0,
        "keterangan": "Pemakaian ke blok A",
    })

    # -----------------------------------------------------------------
    # 26. Pemakaian pestisida (31 Okt)
    # -----------------------------------------------------------------
    jml = 380_000
    _buat_jurnal(cursor, period_id, "2026-10-31", nb("JU"),
                 "umum",
                 "Pemakaian pestisida blok A (penyesuaian persediaan)",
                 [{"account_id": BEBAN_PESTISIDA, "debit": jml, "kredit": 0},
                  {"account_id": PERSEDIAAN_PESTISIDA, "debit": 0, "kredit": jml}])
    _insert(cursor, "inventory_movements", {
        "item_id": item["BHN-004"],
        "tanggal": "2026-10-31",
        "tipe_gerakan": "keluar",
        "qty": 1,
        "harga_satuan": 380_000,
        "total_nilai": 380_000,
        "saldo_qty": 0,
        "saldo_nilai": 0,
        "harga_rata2": 0,
        "keterangan": "Pemakaian ke blok A",
    })


def tutup_connection(koneksi: sqlite3.Connection) -> None:
    """Menutup koneksi database dengan aman."""
    if koneksi:
        koneksi.close()


if __name__ == "__main__":
    # Jalankan langsung: python -m database.seed
    from database.schema import buat_semua_tabel
    buat_semua_tabel()
    jalankan_seed()
