# Penjelasan Kode — Sistem Akuntansi Cabai
**PT Sari Subur Langgeng Jaya Hidroponik Farm**
*Panduan memahami kode untuk pemula dan dokumentasi teknis sistem.*

---

## 1. Panduan Arsitektur & Folder

```
sistem-akuntansi-cabai/
├── app.py                      # Pintu masuk utama & konfigurasi st.navigation
├── theme.py                    # Konstanta tema, warna, dan identitas perusahaan
├── requirements.txt            # Dependensi Python dengan versi dipin
├── .streamlit/config.toml      # Konfigurasi tema warna Streamlit
├── database/                   # Lapisan Database (SQLite)
│   ├── connection.py           # Manajemen koneksi SQLite (Row factory)
│   ├── schema.py               # Pembuatan 11 tabel relasional
│   └── seed.py                 # Data awal Oktober 2026 (observasi lapangan)
├── services/                   # Lapisan Logika Akuntansi (Bebas Streamlit)
│   ├── period_service.py       # Manajemen periode multi-tahun, kalender & auto-create
│   ├── master_data_service.py  # Logika CRUD Master Data
│   ├── transaction_service.py  # Pemetaan transaksi ke jurnal debit/kredit
│   ├── journal_service.py      # Validasi & penyimpanan jurnal umum/khusus
│   ├── inventory_service.py    # Perhitungan kartu stok moving average
│   ├── ledger_service.py       # Posting buku besar saldo berjalan
│   ├── subsidiary_service.py   # Buku pembantu piutang, persediaan, aset
│   ├── payroll_service.py      # Penggajian & perhitungan utang gaji
│   ├── depreciation_service.py # Penyusutan garis lurus & amortisasi mulsa
│   ├── adjusting_service.py    # Pembuatan jurnal penyesuaian otomatis
│   ├── trial_balance_service.py# Penyusunan & validasi neraca saldo
│   ├── worksheet_service.py    # Penyusunan neraca lajur 10 kolom
│   ├── statements_service.py   # Penyusunan 4 laporan keuangan
│   ├── closing_service.py      # Jurnal penutup & penguncian periode
│   └── dashboard_service.py    # Agregasi metrik finansial & operasional
├── views/                      # Lapisan Tampilan UI (1 file = 1 halaman)
│   ├── 00_dashboard.py         # Dashboard visual & ringkasan eksekutif
│   ├── 01_master_data.py       # Pengelolaan data master (10 tab)
│   ├── 02_input_transaksi.py   # Form input transaksi (10 form + pratinjau)
│   ├── 03_penggajian.py        # Penggajian 2 mingguan & slip gaji
│   ├── 04_jurnal_umum.py       # Jurnal umum format kronologis
│   ├── 05_jurnal_khusus.py     # 4 Jurnal khusus format kolom akuntansi
│   ├── 06_kartu_persediaan.py  # Kartu stok bahan & hasil panen cabai
│   ├── 07_buku_besar.py        # Buku besar saldo berjalan per akun
│   ├── 08_buku_besar_pembantu.py # BB pembantu piutang & umur piutang
│   ├── 09_neraca_saldo.py      # Neraca saldo sebelum penyesuaian
│   ├── 10_ayat_penyesuaian.py  # Form & pembuatan ayat penyesuaian
│   ├── 11_neraca_lajur.py      # Kertas kerja 10 kolom
│   ├── 12_laporan_keuangan.py  # Laba Rugi, Ekuitas, Neraca, Arus Kas
│   ├── 13_jurnal_penutup.py    # Penutupan akun nominal & neraca penutup
│   └── 14_backup_export.py     # Backup .db, ekspor Excel/PDF, reset
├── utils/                      # Fungsi Pembantu
│   ├── formatting.py           # Format mata uang Rupiah & tanggal
│   ├── ui_components.py        # Pembungkus komponen Ant Design (sac)
│   └── export.py               # Generator Excel (openpyxl) & PDF (fpdf2)
└── tests/                      # Pengujian Otomatis (Pytest)
```

---

## 2. Penjelasan Logika & Rumus Akuntansi

### A. Mesin Jurnal & Pemetaan Transaksi (`services/transaction_service.py`)
Setiap transaksi yang diinput pengguna dipetakan ke pasangan akun debit dan kredit:
- **Penjualan Tunai**: Kas (D) / Penjualan (K)
- **Penjualan Tempo**: Piutang Usaha (D) / Penjualan (K) + otomatis membuat entri di tabel `receivables` dengan jatuh tempo 7 hari.
- **Terima Pelunasan Piutang**: Kas (D) / Piutang Usaha (K) + update sisa piutang di `receivables`.
- **Setoran Modal**: Kas (D) / Modal Disetor (K).
- **Pembelian Tunai**: Persediaan (D) / Kas (K).
- **Pembelian Kredit**: Persediaan (D) / Utang Usaha (K).
- **Pemakaian Bahan**: Beban Bahan Produksi (D) / Persediaan (K).
- **Pencatatan Panen**: Persediaan Hasil Panen (D) / Beban Bahan Produksi Lain (K).
- **Validasi Keseimbangan**: `sum(debit) == sum(kredit)`. Jika tidak sama, transaksi ditolak oleh `journal_service.validasi_jurnal_seimbang()`.

---

### B. Kartu Persediaan Rata-Rata Bergerak (`services/inventory_service.py`)
Mencatat mutasi persediaan secara *perpetual*:
- **Saat Barang Masuk**:
  $$\text{Saldo Qty Baru} = \text{Saldo Qty Lama} + \text{Qty Masuk}$$
  $$\text{Saldo Nilai Baru} = \text{Saldo Nilai Lama} + (\text{Qty Masuk} \times \text{Harga Satuan})$$
  $$\text{Harga Rata-Rata Baru} = \frac{\text{Saldo Nilai Baru}}{\text{Saldo Qty Baru}}$$
- **Saat Barang Keluar**:
  $$\text{Total Nilai Keluar} = \text{Qty Keluar} \times \text{Harga Rata-Rata Terakhir}$$
  $$\text{Saldo Qty Baru} = \text{Saldo Qty Lama} - \text{Qty Keluar}$$
  $$\text{Saldo Nilai Baru} = \text{Saldo Nilai Lama} - \text{Total Nilai Keluar}$$
  *(Harga rata-rata tidak berubah saat barang keluar).*

---

### C. Penggajian Pekerja (`services/payroll_service.py`)
- Upah dihitung per pekerja per 2 mingguan:
  - **Pekerja Tetap**: $\text{Hari Kerja} \times \text{Rp90.000}$
  - **Pekerja Tambahan** (olah tanah/cangkul): $\text{Hari Kerja} \times \text{Rp120.000}$
- Saat pembayaran: Beban Upah Tenaga Kerja (D) / Kas (K).
- Jika ada upah belum dibayar di akhir bulan, dibuat penyesuaian akrual:
  $$\text{Debit: Beban Upah} \quad / \quad \text{Kredit: Utang Gaji (2102)}$$

---

### D. Penyusutan & Amortisasi (`services/depreciation_service.py`)
- **Penyusutan Aset Tetap (Metode Garis Lurus Bulanan)**:
  $$\text{Penyusutan per Bulan} = \frac{\text{Harga Perolehan} - \text{Nilai Residu}}{\text{Umur Ekonomis (Tahun)} \times 12}$$
  - Tanah memiliki umur ekonomis 0 (tidak disusutkan).
- **Amortisasi Plastik Mulsa**:
  - Plastik mulsa dipakai per blok dengan masa pakai 1,5 tahun (18 bulan):
  $$\text{Amortisasi per Bulan} = \frac{\text{Total Biaya Mulsa}}{18}$$

---

### E. Neraca Lajur 10 Kolom (`services/worksheet_service.py`)
Kertas kerja 10 kolom menghubungkan seluruh proses dari neraca saldo hingga laporan keuangan:
1. **Neraca Saldo (Kolom 1-2)**: Saldo awal + mutasi jurnal umum & khusus.
2. **Ayat Penyesuaian (Kolom 3-4)**: Mutasi jurnal dengan kode `PA-`.
3. **Neraca Saldo Disesuaikan (Kolom 5-6)**:
   - Akun Debit Normal: $\text{NS Debit} + \text{Peny Debit} - \text{Peny Kredit}$
   - Akun Kredit Normal: $\text{NS Kredit} + \text{Peny Kredit} - \text{Peny Debit}$
4. **Laba Rugi (Kolom 7-8)**: Akun nominal Pendapatan (4), Beban Produksi (5), Beban Operasional (6).
5. **Neraca (Kolom 9-10)**: Akun riil Aset (1), Liabilitas (2), Ekuitas (3).
- **Validasi Keseimbangan**:
  $$\text{Laba Bersih} = \sum \text{Kredit L/R} - \sum \text{Debit L/R}$$
  $$\sum \text{Debit Neraca} = \sum \text{Kredit Neraca} + \text{Laba Bersih}$$

---

### F. Laporan Keuangan (`services/statements_service.py`)
1. **Laporan Laba Rugi**:
   $$\text{Laba Bersih} = \text{Total Pendapatan} - (\text{Total Beban Produksi} + \text{Total Beban Operasional})$$
2. **Laporan Perubahan Ekuitas**:
   $$\text{Modal Akhir} = \text{Modal Awal} + \text{Tambahan Setoran Modal} + \text{Laba Bersih}$$
3. **Neraca (Bentuk Laporan)**:
   $$\text{Total Aset} = \text{Aset Lancar} + \text{Aset Tetap (Nilai Buku)}$$
   $$\text{Total Liabilitas \& Ekuitas} = \text{Total Liabilitas} + \text{Modal Akhir}$$
   $$\text{Status Seimbang} = (\text{Total Aset} == \text{Total Liabilitas \& Ekuitas})$$
4. **Laporan Arus Kas (Metode Langsung)**:
   - **Arus Kas Operasi**: Penerimaan kas penjualan & piutang dikurangi pengeluaran beli bahan, upah, listrik, dan BBM.
   - **Arus Kas Investasi**: Pengeluaran kas pembelian aset tetap.
   - **Arus Kas Pendanaan**: Penerimaan kas dari setoran modal.
   - $\text{Saldo Kas Akhir} = \text{Saldo Kas Awal} + \text{Total Kenaikan/Penurunan Kas}$.

---

### G. Jurnal Penutup & Penguncian Periode (`services/closing_service.py`)
1. Menutup semua akun Pendapatan ke akun Ikhtisar Laba Rugi (3301).
2. Menutup semua akun Beban ke akun Ikhtisar Laba Rugi (3301).
3. Menutup saldo Ikhtisar Laba Rugi ke akun Laba Ditahan (3201).
4. Mengubah status periode di database menjadi `tutup`.
5. **Neraca Saldo Setelah Penutup**: Hanya memuat akun permanen (Aset, Liabilitas, Ekuitas); saldo seluruh akun pendapatan dan beban bernilai 0.

---

### H. Ekspor Multi-Format & Backup (`utils/export.py`, `views/14_backup_export.py`)
- **Excel Multi-Sheet**: Generator openpyxl membuat buku kerja (.xlsx) berisi sheet terpisah untuk setiap laporan dan tabel database dengan styling tabel profesional dan auto-fit lebar kolom.
- **PDF Sanitasi Unicode**: Generator fpdf2 menyaring karakter non-latin1 (seperti em-dash `—`, bullet `•`, dan smart quotes `“”`) melalui fungsi `_bersihkan_teks_pdf()` sehingga bebas dari `FPDFUnicodeEncodingException`.
- **Backup & Restore**: Mengunduh dan memulihkan berkas SQLite `.db` secara utuh.

---

### I. Pemilih Periode Fleksibel & Kalender (`services/period_service.py` & `utils/ui_components.py`)
- **Multi-Tahun & Multi-Bulan**: Tabel `periods` otomatis diisi periode tahun lalu (2025), tahun ini (2026), dan tahun depan (2027) sebanyak 36 periode.
- **Komponen `selector_periode`**:
  1. *Dropdown Terpadu*: Menampilkan seluruh bulan dengan penanda khusus (⭐ Data Observasi, ⚡ Bulan Ini, ⏪ Bulan Lalu, 🗓️ Tahun Lalu, status Buka/Tutup).
  2. *Shortcut Cepat*: Tombol instan untuk beralih ke Bulan Ini, Bulan Lalu, Tahun Lalu, atau Oktober 2026.
  3. *Kalender Manual*: Input bulan & tahun bebas. Jika periode belum terdaftar di database, sistem otomatis membuatnya (`INSERT INTO periods ... status='buka'`).
  4. *Session State Persistence*: Periode yang dipilih tersinkronisasi saat berpindah menu.
