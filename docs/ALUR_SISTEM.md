# Alur Sistem Akuntansi Cabai
**PT Sari Subur Langgeng Jaya Hidroponik Farm**
*Dokumen ini merupakan panduan alur data dan arsitektur sistem dari Fase 0 hingga Fase 8.*

---

## 1. Arsitektur Umum & Prinsip Desain

### Diagram Alur Siklus Akuntansi

```
[Master Data & Saldo Awal]  (views/01_master_data.py)
        │
        ▼
[Input Transaksi]          (views/02_input_transaksi.py - 10 Form Transaksi)
        │
        ▼
[Mesin Jurnal & Validasi]  (services/transaction_service.py + journal_service.py)
        │                  (Debit == Kredit Wajib Seimbang)
        ├─────────────────────────────────────────────────────────────┐
        ▼                                                             ▼
[5 Jenis Jurnal]                                            [Kartu Persediaan]
  • Jurnal Penjualan (tempo)                                 (services/inventory_service.py)
  • Jurnal Penerimaan Kas (tunai, piutang, modal)            Sistem Perpetual
  • Jurnal Pengeluaran Kas (beli bahan, upah, beban)         Metode Rata-rata Bergerak
  • Jurnal Pembelian (kredit)                                Stok Bahan & Hasil Panen Cabai
  • Jurnal Umum (pemakaian bahan, memorial)                  HPP dan stok berkurang saat penjualan
        │
        ▼
[Posting Buku Besar & BB Pembantu]
  • Buku Besar Utama (services/ledger_service.py)
  • BB Pembantu Piutang, Persediaan, Aset Tetap (services/subsidiary_service.py)
        │
        ▼
[Neraca Saldo Sebelum Penyesuaian] (services/trial_balance_service.py)
        │
        ▼
[Ayat Jurnal Penyesuaian]          (services/adjusting_service.py + depreciation_service.py)
  • Penyusutan Aset Tetap (Garis Lurus)
  • Amortisasi Plastik Mulsa (1,5 tahun)
  • Akrual Upah Tenaga Kerja
        │
        ▼
[Neraca Lajur 10 Kolom]            (services/worksheet_service.py)
  (NS → Penyesuaian → NSD → Laba Rugi → Neraca)
        │
        ▼
[Laporan Keuangan]                 (services/statements_service.py)
  1. Laporan Laba Rugi             → Menghasilkan Laba Bersih
  2. Laporan Perubahan Ekuitas     → Modal Akhir = Modal Awal + Setoran + Laba Bersih
  3. Neraca (Bentuk Laporan)       → Total Aset == Total Liabilitas + Total Ekuitas
  4. Laporan Arus Kas              → Metode Langsung (Operasi, Investasi, Pendanaan)
        │
        ▼
[Jurnal Penutup & Tutup Periode]   (services/closing_service.py)
  • Tutup Pendapatan & Beban ke Ikhtisar L/R
  • Tutup Ikhtisar L/R ke Laba Ditahan
  • Neraca Saldo Setelah Penutup (Akun Riil Tersisa, Periode 'tutup')
        │
        ▼
[Dashboard, Backup & Export]       (views/00_dashboard.py, views/14_backup_export.py)
  • Dashboard Visual: Saldo Kas, Piutang Jatuh Tempo, Stok, Grafik Per Komoditas & Beban
  • Backup Database (.db) & Export Multi-Sheet Excel (.xlsx) / PDF (.pdf)
```

### Prinsip Satu Sumber Kebenaran
Semua perhitungan finansial bersumber dari baris jurnal di tabel `journal_lines`. Tidak ada duplikasi penyimpanan angka:
- **Buku Besar**: Agregasi dan filter `journal_lines` berdasarkan `account_id` dan `period_id`.
- **Neraca Saldo**: Kompilasi saldo akhir setiap akun dari `journal_lines` + saldo awal `opening_balances`.
- **Neraca Lajur & Laporan**: Derivasi bertingkat dari Neraca Saldo Disesuaikan.

---

## 2. Rincian Alur per Fase

### Fase 0 — Fondasi & Arsitektur
- **Database SQLite**: Skema 11 tabel relasional dibuat di `database/schema.py` dengan foreign keys aktif.
- **Bagan Akun (COA)**: Standar 6 digit berkategori Aset (1), Liabilitas (2), Ekuitas (3), Pendapatan (4), Beban Produksi (5), Beban Operasional (6).
- **Tema & UI**: Tema terpusat di `.streamlit/config.toml` (warna hijau alami `#2E7D32`) dan komponen `streamlit-antd-components` dibungkus rapi di `utils/ui_components.py`.

### Fase 1 — Master Data
- Mengelola data entitas: Bagan Akun, Pelanggan, Supplier, Item Persediaan, Pekerja, Aset Tetap, Blok Lahan, Saldo Awal, Periode, dan Parameter Operasional.
- Validasi input di `services/master_data_service.py` tanpa mencampur kode Streamlit.

### Fase 2 — Input Transaksi & Mesin Jurnal
- 10 Form transaksi terpisah di `views/02_input_transaksi.py`:
  1. Penjualan Tunai
  2. Penjualan Tempo (Faktur & Jatuh Tempo 7 Hari)
  3. Terima Pelunasan Piutang
  4. Setoran Modal
  5. Pembelian Bahan Tunai (Toko Sido Panen)
  6. Pembelian Kredit
  7. Pemakaian Bahan ke Blok Lahan
  8. Pencatatan Hasil Panen Cabai
  9. Biaya Operasional (BBM, Listrik, Sewa Traktor)
  10. Pembelian Aset Tetap Tunai
- Fitur **Pratinjau Jurnal Interaktif**: Mengharuskan Total Debit == Total Kredit sebelum disimpan. Pratinjau penjualan juga menampilkan HPP dan pengurangan persediaan berdasarkan rata-rata bergerak; stok tidak mencukupi akan ditolak.

### Fase 3 — Jurnal Umum & 4 Jurnal Khusus
- **Jurnal Umum** (`views/04_jurnal_umum.py`): Format kronologis dengan kolom Tanggal, No Bukti, Keterangan, Ref Akun, Debit, dan Kredit.
- **Jurnal Khusus** (`views/05_jurnal_khusus.py`): 4 tab format kolom akuntansi:
  - *Sales Journal*: Piutang Usaha (D) / Penjualan (K), serta HPP Penjualan (D) / Persediaan Cabai (K).
  - *Purchase Journal*: Persediaan (D) / Utang Usaha (K)
  - *Cash Receipt Journal*: Kas (D), Piutang (K), Penjualan (K), Lain-lain (K), dengan kolom tambahan HPP (D) / Persediaan Cabai (K) yang tidak dihitung sebagai sumber kas.
  - *Cash Payment Journal*: Kas (K), Persediaan (D), Beban Upah (D), Beban Lain (D)

### Fase 4 — Buku Besar, BB Pembantu & Kartu Persediaan
- **Buku Besar**: Menampilkan saldo berjalan per akun dengan saldo awal dan mutasi debit/kredit.
- **BB Pembantu**: Rincian piutang per pelanggan (dilengkapi analisa umur piutang / aging), stok persediaan, dan buku pembantu aset tetap.
- **Kartu Persediaan**: Sistem perpetual dengan metode rata-rata bergerak (*moving average*). Pembelian, saldo awal, pemakaian bahan, panen, dan penjualan langsung memperbarui saldo kuantitas serta nilai.
- **Saldo Awal Persediaan**: Kuantitas fisik dan harga pokok dimasukkan per item. Sistem mencatat mutasi `saldo_awal` dan menyelaraskan saldo akun persediaan pada `opening_balances`.
- **Penjualan Cabai**: Setiap penjualan memeriksa ketersediaan stok dan membentuk dua pasangan jurnal: Kas/Piutang terhadap Penjualan, serta HPP Penjualan terhadap Persediaan Cabai.
- **Validasi**: Penjualan atau pemakaian yang melebihi stok ditolak. Mutasi per item harus dicatat kronologis agar rata-rata bergerak akurat.

### Fase 5 — Neraca Saldo, Penggajian & Penyesuaian
- **Neraca Saldo**: Menghitung saldo seluruh akun dan memvalidasi keseimbangan Debit == Kredit.
- **Penggajian**: Menghitung upah pekerja harian tetap (Rp90.000/hari) dan pekerja tambahan (Rp120.000/hari) per periode 2 mingguan, serta mencatat akrual utang gaji.
- **Ayat Penyesuaian**: Penyusutan aset tetap garis lurus bulanan, amortisasi plastik mulsa (1,5 tahun), akrual upah, dan pemakaian bahan.

### Fase 6 — Neraca Lajur, Laporan Keuangan & Penutupan
- **Neraca Lajur 10 Kolom**: 5 pasang kolom terverifikasi seimbang (Neraca Saldo, Penyesuaian, NSD, Laba Rugi, dan Neraca).
- **Laporan Keuangan**:
  - *Laba Rugi*: Pendapatan - (Beban Produksi + Beban Operasional) = Laba Bersih
  - *Perubahan Ekuitas*: Modal Awal + Setoran Tambahan + Laba Bersih = Modal Akhir
  - *Neraca*: Total Aset == Total Liabilitas + Total Ekuitas
  - *Arus Kas*: Metode langsung (Aktivitas Operasi, Investasi, dan Pendanaan)
- **Jurnal Penutup**: Menutup akun nominal (4, 5, 6) ke Ikhtisar L/R, memindahkan laba ke Laba Ditahan, dan mengunci periode ke status `tutup`.

### Fase 7 — Dashboard, Ekspor Dokumen & Cadangan
- **Dashboard Eksekutif**: Metrik kas, piutang jatuh tempo, grafik penjualan cabai, grafik Penjualan vs Beban, dan tabel status stok.
- **Ekspor Dokumen**: Ekspor laporan keuangan ke Excel (.xlsx) multi-sheet dan PDF (.pdf) bebas error unicode.
- **Backup & Restore**: Cadangkan database SQLite (`.db`) atau seluruh tabel ke Excel, serta restore data secara aman.

### Fase 8 — Pengujian Menyeluruh, Kerapian Kode, Manajemen Periode & Kesiapan Deploy
- **Pemilih Periode Fleksibel & Kalender**: Komponen terpadu `selector_periode` dipasang di seluruh menu dengan dukungan multi-periode (2025-2027), preset cepat (Bulan Ini, Bulan Lalu, Tahun Ini, Tahun Lalu, Observasi Okt 2026), dan pemilih kalender manual yang otomatis membuat periode jika belum terdaftar.
- **Test Suite 100% Passed**: 204 tes otomatis mencakup unit tests, period service tests, dan end-to-end accounting cycle test.
- **100% Python Murni**: Bebas dari tag HTML/CSS/JS mentah. Seluruh antarmuka menggunakan widget native Streamlit dan wrapper `streamlit-antd-components`.
- **Kesiapan Streamlit Community Cloud**: Konfigurasi `.streamlit/config.toml`, dependency dipin di `requirements.txt`, penanganan database otomatis saat cold-start, dan file path berbasis `pathlib.Path` yang agnostik terhadap OS.
