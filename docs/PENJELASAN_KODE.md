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
│   ├── depreciation_service.py # Penyusutan aset tetap garis lurus
│   ├── adjusting_service.py    # Pembuatan jurnal penyesuaian otomatis
│   ├── trial_balance_service.py# Penyusunan & validasi neraca saldo
│   ├── worksheet_service.py    # Penyusunan neraca lajur 10 kolom
│   ├── statements_service.py   # Penyusunan 4 laporan keuangan
│   ├── closing_service.py      # Jurnal penutup & penguncian periode
│   └── dashboard_service.py    # Agregasi metrik finansial & operasional
├── views/                      # Lapisan Tampilan UI (1 file = 1 halaman)
│   ├── 00_dashboard.py         # Dashboard visual & ringkasan eksekutif
│   ├── 01_master_data.py       # Pengelolaan data master (10 tab)
│   ├── 02_input_transaksi.py   # Form input transaksi (9 form + pratinjau)
│   ├── 03_penggajian.py        # Penggajian 2 mingguan & slip gaji
│   ├── 04_jurnal_umum.py       # Jurnal umum format kronologis
│   ├── 05_jurnal_khusus.py     # 4 Jurnal khusus format kolom akuntansi
│   ├── 06_kartu_persediaan.py  # Kartu stok barang dagang cabai hasil panen
│   ├── 07_buku_besar.py        # Buku besar saldo berjalan per akun
│   ├── 08_buku_besar_pembantu.py # BB pembantu piutang usaha & utang usaha
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
- **Penjualan Tunai**: Kas (D) / Penjualan (K), sekaligus HPP Penjualan Cabai (D) / Persediaan (1140) (K).
- **Penjualan Tempo**: Piutang Usaha (D) / Penjualan (K), sekaligus HPP Penjualan Cabai (D) / Persediaan (1140) (K) + otomatis membuat entri di tabel `receivables` dengan jatuh tempo 7 hari.
- **Terima Pelunasan Piutang**: Kas (D) / Piutang Usaha (K) + update sisa piutang di `receivables`.
- **Setoran Modal**: Kas (1110) (D) / Modal Pribadi (3110) (K).
- **Pembelian Barang Dagang Tunai**: Persediaan Cabai (D) / Kas (K).
- **Pembelian Barang Dagang Kredit**: Persediaan Cabai (D) / Utang Usaha (K).
- **Pencatatan Panen**: Persediaan Barang Dagang Cabai (D) / HPP Panen (K).
- **Validasi Keseimbangan**: `sum(debit) == sum(kredit)`. Jika tidak sama, transaksi ditolak oleh `journal_service.validasi_jurnal_seimbang()`.

---

### B. Kartu Persediaan Perpetual — Rata-Rata Bergerak (`services/inventory_service.py`)
Setiap pembelian barang dagang, panen, dan penjualan langsung memperbarui kartu stok serta saldo akun persediaan. Persediaan aktif hanya berisi barang dagang cabai hasil panen yang diposting ke akun **1140 — Persediaan**. Kartu stok tetap terpisah per item. Penjualan cabai tidak menunggu akhir periode untuk menghitung HPP:
- **Saldo Awal**: Kuantitas dan harga pokok diinput per item. Sistem mencatat gerakan `saldo_awal` dan menyelaraskan saldo debit pada `opening_balances`.
- **Penjualan Tunai**: Kas (D), Penjualan (K), HPP Penjualan (D), Persediaan (1140) (K).
- **Penjualan Tempo**: Piutang Usaha (D), Penjualan (K), HPP Penjualan (D), Persediaan (1140) (K).
- **Akun HPP**: `5110 - Harga Pokok Penjualan`, bertipe Beban Produksi agar masuk ke laporan laba rugi dan penutupan periode.
- **Saat Barang Masuk**:
  $$\text{Saldo Qty Baru} = \text{Saldo Qty Lama} + \text{Qty Masuk}$$
  $$\text{Saldo Nilai Baru} = \text{Saldo Nilai Lama} + (\text{Qty Masuk} \times \text{Harga Satuan})$$
  $$\text{Harga Rata-Rata Baru} = \frac{\text{Saldo Nilai Baru}}{\text{Saldo Qty Baru}}$$
- **Saat Barang Keluar**:
  $$\text{Total Nilai Keluar} = \text{Qty Keluar} \times \text{Harga Rata-Rata Terakhir}$$
  $$\text{Saldo Qty Baru} = \text{Saldo Qty Lama} - \text{Qty Keluar}$$
  $$\text{Saldo Nilai Baru} = \text{Saldo Nilai Lama} - \text{Total Nilai Keluar}$$
  *(Harga rata-rata tidak berubah saat barang keluar, kecuali saldo menjadi nol).*

**Contoh HPP penjualan**:
Jika stok 100 kg dengan harga rata-rata Rp25.000/kg dan terjual 20 kg:
- HPP = 20 × Rp25.000 = Rp500.000.
- Jurnal: Dr HPP Penjualan Rp500.000 / Cr Persediaan Cabai Rp500.000.
- Sisa stok = 80 kg dengan nilai Rp2.000.000.

---

### C. Penggajian Pekerja (`services/payroll_service.py`)
- Upah dihitung per pekerja per 2 mingguan:
  - **Pekerja Tetap**: $\text{Hari Kerja} \times \text{Rp90.000}$
  - **Pekerja Tambahan** (olah tanah/cangkul): $\text{Hari Kerja} \times \text{Rp120.000}$
- Saat pembayaran: Beban Upah Tenaga Kerja (D) / Kas (K).
- Jika ada upah belum dibayar di akhir bulan, dibuat penyesuaian akrual:
  $$\text{Debit: Beban Upah} \quad / \quad \text{Kredit: Utang Gaji (2102)}$$

---

### D. Penyusutan Aset Tetap (`services/depreciation_service.py`)
- **Penyusutan Aset Tetap (Metode Garis Lurus Bulanan)**:
  $$\text{Penyusutan per Bulan} = \frac{\text{Harga Perolehan} - \text{Nilai Residu}}{\text{Umur Ekonomis (Tahun)} \times 12}$$
  - Tanah memiliki umur ekonomis 0 (tidak disusutkan).

---

### E. Neraca Lajur 10 Kolom (`services/worksheet_service.py`)
Kertas kerja 10 kolom menghubungkan seluruh proses dari neraca saldo hingga laporan keuangan:
1. **Neraca Saldo (Kolom 1-2)**: Saldo awal + mutasi jurnal umum & khusus.
2. **Ayat Penyesuaian (Kolom 3-4)**: Mutasi jurnal dengan kode `PA-`.
3. **Neraca Saldo Disesuaikan (Kolom 5-6)**:
   - Akun Debit Normal: $\text{NS Debit} + \text{Peny Debit} - \text{Peny Kredit}$
   - Akun Kredit Normal: $\text{NS Kredit} + \text{Peny Kredit} - \text{Peny Debit}$
4. **Laba Rugi (Kolom 7-8)**: Akun nominal Pendapatan (4xxx), HPP (5xxx), Beban Operasional (6xxx), dan Beban Lainnya (7xxx).
5. **Neraca (Kolom 9-10)**: Akun riil Aset (1), Liabilitas (2), Ekuitas (3).
- **Validasi Keseimbangan**:
  $$\text{Laba Bersih} = \sum \text{Kredit L/R} - \sum \text{Debit L/R}$$
  $$\sum \text{Debit Neraca} = \sum \text{Kredit Neraca} + \text{Laba Bersih}$$

---

### F. Laporan Keuangan (`services/statements_service.py`)
1. **Laporan Laba Rugi**:
   $\text{Laba Bersih} = \text{Penjualan Cabai} - \text{HPP} - \text{Beban Operasional} - \text{Beban Lain-lain}$
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
1. Menutup semua akun Pendapatan ke akun Ikhtisar Laba Rugi (3130).
2. Menutup semua akun Beban ke akun Ikhtisar Laba Rugi (3130).
3. Menutup saldo Ikhtisar Laba Rugi (3130) ke akun Laba (3120).
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


---

## J. Autentikasi dan Session Pengguna

### 1. Membuat dan memverifikasi password — `services/auth_service.py`
- `buat_hash_password()` membuat salt acak 16 byte, lalu menghitung PBKDF2-HMAC-SHA256 sebanyak 600.000 iterasi.
- `verifikasi_password()` menghitung ulang hash dari password yang dimasukkan dan membandingkannya dengan `hmac.compare_digest()`. Fungsi mengembalikan nilai benar/salah, bukan password.
- `validasi_password()` mewajibkan minimal 12 karakter dan sedikitnya tiga kelompok karakter: huruf kecil, huruf besar, angka, atau simbol.

### 2. Proses login dan penguncian akun
- `autentikasi(username, password)` mencari akun berdasarkan username tanpa membedakan huruf besar/kecil.
- Setelah verifikasi hash, fungsi memulai transaksi tulis SQLite (`BEGIN IMMEDIATE`) dan membaca ulang status akun. Langkah ini mencegah hitungan percobaan login yang berjalan berdekatan saling menimpa serta menolak akun yang dinonaktifkan atau password-nya berubah saat proses login.
- Percobaan gagal disimpan pada tabel `login_attempts`. Setelah lima kegagalan, username dikunci selama 15 menit. Login yang berhasil menghapus catatan kegagalan sebelumnya.
- Profil yang dikembalikan tidak menyertakan `password_hash`.

### 3. Memvalidasi session — `services/permission_service.py`
- Saat login berhasil, `views/login.py` menyimpan ID pengguna, versi sesi, dan waktu aktivitas terakhir ke `st.session_state`.
- `pengguna_aktif()` memeriksa tiga hal pada setiap rerun: waktu tidak aktif maksimal 8 jam, akun masih aktif, dan versi sesi sama dengan nilai terbaru di database.
- Jika waktu aktivitas atau versi sesi hilang/rusak, pemeriksaan ditolak (*fail closed*) dan seluruh state dibersihkan.
- Perubahan role, reset password, atau penonaktifan akun menaikkan `session_version`; sesi lama otomatis tidak berlaku.

### 4. Logout yang selalu membersihkan state
- `keluar_pengguna(user_id)` mencoba mencatat aktivitas logout melalui `auth_service.catat_logout()`.
- Pembersihan `st.session_state` berada di blok `finally`, sehingga kegagalan penyimpanan audit tidak membuat pengguna tetap masuk.
- `app.py` menggunakan fungsi ini saat tombol **Keluar** ditekan.

**Contoh:** pengguna login dengan `session_version = 2`. Administrator mereset password sehingga database menyimpan versi 3. Pada rerun berikutnya, `pengguna_aktif()` membandingkan 2 dengan 3, menghapus session lama, lalu aplikasi meminta pengguna login kembali.


## K. Otorisasi Role dan Permission

### 1. Matriks role — `services/auth_service.py`
- `ROLES` menyimpan empat jenis pengguna: Admin/Owner, Akuntan, Petugas Gudang/Persediaan, dan Pimpinan.
- `PERMISSIONS` berisi kode izin untuk setiap kegiatan, misalnya `transactions.financial.manage` untuk transaksi keuangan dan `transactions.inventory.manage` untuk transaksi persediaan.
- `ROLE_PERMISSIONS` menentukan kumpulan izin untuk setiap role. Contohnya, Petugas Gudang mendapat izin transaksi persediaan tetapi tidak mendapat izin transaksi keuangan.

### 2. Sinkronisasi izin ke database
- `inisialisasi_otorisasi()` membuat role dan permission jika belum tersedia.
- Sebelum memasukkan ulang relasi izin suatu role, sistem menghapus relasi lama role tersebut dari `role_permissions`. Dengan begitu, izin yang sudah dicabut dari matriks kode tidak tertinggal di database.
- Proses ini aman dijalankan berulang karena data role dan permission memakai `INSERT OR IGNORE`, sedangkan relasi role-permission dibangun ulang sesuai konfigurasi terbaru.

### 3. Navigasi dan pemeriksaan halaman — `app.py`
- Daftar menu dibentuk dari permission aktual melalui `punya_izin()`, bukan dari daftar role yang ditulis ulang secara terpisah.
- Setiap halaman tetap memiliki `wajib_punya_izin(kode)` sendiri. Jadi, mengetahui alamat halaman saja tidak cukup untuk melewati pemeriksaan akses.
- Pemeriksaan di halaman dilakukan sebelum fungsi tampilan dipanggil. Menu yang tidak memiliki izin tidak dimasukkan ke navigasi.

### 4. Izin untuk tindakan khusus
- Halaman Input Transaksi menampilkan kelompok transaksi berdasarkan izin keuangan atau persediaan.
- Halaman Penggajian membedakan pengguna yang boleh mengelola absensi/jurnal dengan Pimpinan yang hanya boleh membaca ringkasan.
- Jurnal Umum hanya menampilkan kontrol hapus kepada pengguna dengan izin `journals.manage`.
- Ayat Penyesuaian dan Jurnal Penutup dibatasi oleh izin proses masing-masing.
- Backup database/restore/reset memerlukan `backup.restore`, sedangkan ekspor laporan memerlukan `backup.export`.

**Catatan arsitektur:** service di folder `services/` tetap bebas dari Streamlit sesuai aturan proyek. Karena itu, pemeriksaan session dan permission saat ini menjadi tanggung jawab lapisan `views/` dan `app.py`. Jika kelak service diakses dari API atau worker, otorisasi untuk jalur tersebut harus ditambahkan secara terpisah.


## Antarmuka dan komponen visual

1. `app.py` menampilkan identitas perusahaan dan pengguna aktif di sidebar, kemudian menyusun halaman melalui `st.navigation` sesuai permission.
2. `theme.py` menjadi sumber warna visual aplikasi. `.streamlit/config.toml` menerapkan tema pada komponen bawaan Streamlit.
3. `utils/ui_components.py` menyediakan komponen bersama: header halaman, header bagian, kartu metrik, alert status, indikator siklus, dan pemilih periode.
4. Setiap file di `views/` tetap bertanggung jawab pada tampilan halaman masing-masing. Perhitungan akuntansi tetap dipanggil dari `services/`.
5. Dashboard hanya memakai hasil query dari `services/dashboard_service.py`; angka tidak dibuat untuk sekadar mengisi kartu atau grafik.
6. Implementasi visual ditulis menggunakan Python dan API Streamlit/komponen Python yang sudah menjadi dependensi proyek. Tidak ada HTML, CSS, maupun JavaScript manual di source aplikasi.
7. Batas data: tabel `inventory_movements` belum menyimpan `blok_id`, sehingga dashboard tidak menyajikan sebaran panen per blok sampai relasi tersebut memang tersedia di model data.
