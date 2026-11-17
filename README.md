# 🌶️ Sistem Informasi Siklus Akuntansi
### PT Sari Subur Langgeng Jaya Hidroponik Farm

Aplikasi web sistem informasi siklus akuntansi terpadu berbasis Python dan Streamlit, dibangun khusus untuk usaha budidaya cabai rawit hidroponik di Ungaran Barat, Kabupaten Semarang.

---

## 📋 Daftar Isi
- [Tentang Usaha & Sistem](#-tentang-usaha--sistem)
- [Fitur Utama Sistem](#-fitur-utama-sistem)
- [Struktur Siklus Akuntansi](#-struktur-siklus-akuntansi)
- [Teknologi & Batasan Teknis](#-teknologi--batasan-teknis)
- [Panduan Instalasi & Menjalankan Lokal](#-panduan-instalasi--menjalankan-lokal)
- [Panduan Deployment ke Streamlit Community Cloud](#-panduan-deployment-ke-streamlit-community-cloud)
- [Pengujian Otomatis (Testing)](#-pengujian-otomatis-testing)
- [Struktur Folder](#-struktur-folder)

---

## 🌾 Tentang Usaha & Sistem
**PT Sari Subur Langgeng Jaya Hidroponik Farm** adalah perseroan terbatas di sektor agribisnis hortikultura dengan spesialisasi budidaya cabai rawit sistem hidroponik semi-intensif seluas 2.471 m² yang terbagi dalam 5 blok lahan (A–E) berkapasitas 5.000 pohon. Panen dilakukan berkala 3 kali per minggu dengan hasil rata-rata 700 gram per pohon per pemetikan, dipasarkan langsung ke restoran, supermarket, dan mitra UMKM.

Sistem akuntansi ini mengotomatiskan seluruh tahapan siklus akuntansi dari pencatatan transaksi awal hingga penerbitan laporan keuangan standar dan penutupan buku periode.

---

## ✨ Fitur Utama Sistem

1. **Dashboard Visual & Metrik Eksekutif**:
   - Saldo Kas riil, piutang tempo jatuh tempo (< 7 hari), status stok persediaan.
   - Grafik interaktif tren penjualan cabai dan perbandingan Penjualan vs Beban operasional.
   - Pemilih periode fleksibel terpadu di bagian atas dashboard.

2. **Master Data Terpadu (10 Tab)**:
   - Bagan Akun (Chart of Accounts 4 Digit, 28 akun detail sesuai CSV), Pelanggan, Supplier, Item Persediaan, Pekerja, Aset Tetap, Blok Lahan, Saldo Awal, Periode Akuntansi, dan Parameter Operasional.

3. **Input Transaksi & Mesin Jurnal Otomatis**:
   - 9 Formulir transaksi spesifik (Penjualan Tunai/Tempo, Pembelian Barang Dagang Tunai/Kredit, Pelunasan Piutang, Setoran Modal, Catat Panen, Biaya Operasional, dan Beli Aset).
   - Fitur **Pratinjau Jurnal Interaktif** dengan validasi keseimbangan Debit == Kredit sebelum data tersimpan.

4. **Jurnal Umum & 4 Jurnal Khusus**:
   - Jurnal Umum kronologis lengkap dengan kode referensi akun.
   - 4 Jurnal Khusus berformat kolom akuntansi: *Sales Journal*, *Purchase Journal*, *Cash Receipt Journal*, dan *Cash Payment Journal*.

5. **Buku Besar & Buku Besar Pembantu**:
   - Buku Besar utama saldo berjalan dengan filter periode.
   - Buku Besar Pembantu Piutang Usaha (analisis umur piutang / aging) dan Utang Usaha per supplier.
   - Kartu persediaan tersedia terpisah pada menu Kartu Persediaan; data aset tetap tetap dikelola pada Master Data dan penyusutannya pada Ayat Penyesuaian.

6. **Kartu Persediaan Perpetual — Moving Average**:
   - Persediaan aktif hanya untuk barang dagang cabai hasil panen pada akun GL **1140 — Persediaan**. Kartu stok tetap terpisah per item agar satuan, kuantitas, dan harga pokok tidak tercampur.
   - Pembelian barang dagang, pencatatan panen, dan penjualan langsung memperbarui kuantitas serta nilai persediaan.
   - Penjualan tunai dan tempo otomatis membentuk jurnal Harga Pokok Penjualan (Dr 5110) / Persediaan (Cr 1140).
   - HPP dihitung dengan rata-rata bergerak. Penjualan yang melebihi stok yang tersedia ditolak.
   - Saldo awal dimasukkan per item (kuantitas fisik × harga pokok per satuan) melalui Master Data → Saldo Awal Persediaan.

7. **Penggajian & Slip Upah**:
   - Perhitungan upah harian pekerja tetap (Rp90.000/hari) dan pekerja tambahan (Rp120.000/hari) per periode 2 mingguan, cetak slip upah, dan pencatatan akrual utang gaji.

8. **Ayat Jurnal Penyesuaian**:
   - Perhitungan otomatis penyusutan aset tetap (garis lurus) dan akrual upah tenaga kerja.

9. **Neraca Lajur 10 Kolom (Worksheet)**:
   - Kertas kerja lengkap 10 kolom menghubungkan Neraca Saldo, Penyesuaian, NSD, Laba Rugi, dan Neraca dengan verifikasi keseimbangan otomatis.

10. **Laporan Keuangan Standar**:
    - Laporan Laba Rugi (Penjualan Cabai - HPP - Beban Operasional - Beban Lain-lain = Laba Bersih).
    - Laporan Perubahan Ekuitas (Modal Awal + Tambahan Modal + Laba Bersih = Modal Akhir).
    - Neraca Bentuk Laporan (Validasi: Total Aset == Total Liabilitas + Total Ekuitas).
    - Laporan Arus Kas Metode Langsung (Operasi, Investasi, Pendanaan).

11. **Jurnal Penutup & Neraca Penutup**:
    - Penutupan akun nominal ke Ikhtisar L/R (3130) dan Laba (3120), serta penguncian periode akuntansi.

12. **Ekspor Multi-Format & Cadangan Data**:
    - Ekspor paket laporan keuangan ke Excel (.xlsx) multi-sheet dan dokumen PDF (.pdf) berformat formal.
    - Backup database SQLite (.db) dan fitur pemulihan (*restore*) data.

13. **Pemilih Periode Fleksibel & Fitur Kalender**:
    - Pilihan periode multi-opsi di seluruh menu (tidak hanya Oktober 2026): mencakup seluruh bulan tahun ini (2026), tahun lalu (2025), dan tahun depan (2027) sebanyak 36 periode.
    - Fitur **Kalender / Pemilih Bulan & Tahun Bebas** serta tombol shortcut cepat (*Bulan Ini*, *Bulan Lalu*, *Tahun Ini*, *Tahun Lalu*, *Data Observasi*) dengan pembuatan periode otomatis (*auto-create*) jika memilih tanggal baru.

---

## 🔄 Struktur Siklus Akuntansi

```
[Input Transaksi] ──► [Mesin Jurnal] ──► [Jurnal Khusus & Umum]
                            │
                            ├──────────────────────────┐
                            ▼                          ▼
                     [Posting BB]             [Kartu Persediaan]
                            │
                            ▼
                    [Neraca Saldo]
                            │
                            ▼
                  [Ayat Penyesuaian]
                            │
                            ▼
                  [Neraca Lajur 10 Kolom]
                            │
                            ▼
                   [Laporan Keuangan]
             (Laba Rugi, Ekuitas, Neraca, Arus Kas)
                            │
                            ▼
                   [Jurnal Penutup] ──► [Neraca Saldo Penutup]
```

---

## 🛠️ Teknologi & Batasan Teknis

- **100% Bahasa Pemrograman Python**: Seluruh logika bisnis dan antarmuka pengguna dibangun murni menggunakan Python tanpa kode HTML, CSS, atau JavaScript mentah.
- **Framework UI**: Streamlit 1.40+ dengan arsitektur navigasi modern `st.navigation` dan `st.Page`.
- **Komponen Tampilan**: `streamlit-antd-components` (Ant Design) terbungkus rapi di `utils/ui_components.py`.
- **Database**: SQLite3 bawaan Python dengan penanganan Foreign Keys dan `sqlite3.Row` factory.
- **Pengolahan Data**: Pandas untuk manipulasi tabel dan agregasi finansial.
- **Ekspor Dokumen**: OpenPyXL untuk Excel multi-sheet dan FPDF2 untuk dokumen PDF.
- **Testing**: Pytest untuk pengujian otomatis komprehensif.

---

## 🚀 Panduan Instalasi & Menjalankan Lokal

### 1. Prasyarat
- Python versi 3.11 atau lebih baru (termasuk Python 3.12, 3.13, dan 3.14).

### 2. Langkah Instalasi

```bash
# 1. Buka terminal dan arahkan ke direktori proyek
cd sistem-akuntansi-cabai

# 2. Buat virtual environment (opsional namun sangat disarankan)
python -m venv venv

# 3. Aktifkan virtual environment
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Windows (CMD):
.\venv\Scripts\activate.bat
# Linux / macOS:
source venv/bin/activate

# 4. Pasang dependensi yang telah dipin
pip install -r requirements.txt

# 5. Jalankan aplikasi Streamlit
streamlit run app.py
```

Setelah aplikasi berjalan, buka peramban di `http://localhost:8501`. Database SQLite akan terinisialisasi dan terisi otomatis dengan data contoh observasi Oktober 2026.

---

## 🚀 Panduan Deployment dengan Database Persisten

Untuk penggunaan operasional yang menyimpan transaksi keuangan, deployment yang disarankan adalah **server/VPS dengan Docker Compose**. Aplikasi menggunakan SQLite pada `database/akuntansi_cabai.db`; karena itu direktori database harus berada pada volume persisten agar perubahan tetap ada setelah container diperbarui atau dibuat ulang.

### Opsi utama: VPS / server dengan Docker

Prasyarat: server Linux, Docker Engine, dan Docker Compose plugin.

1. Clone repository pada server dan masuk ke folder proyek.
2. Buat file konfigurasi rahasia:
   ```bash
   cp .env.example .env
   ```
   Ganti `BOOTSTRAP_SETUP_KEY` pada `.env` dengan secret acak yang panjang. Jangan commit atau membagikan file `.env`.
3. Pastikan folder `database/` dan file database yang akan dipakai sudah benar. Buat backup di luar folder kerja sebelum deployment pertama.
4. Jalankan:
   ```bash
   docker compose up -d --build
   docker compose ps
   docker compose logs -f akuntansi-cabai
   ```
5. Akses aplikasi melalui `http://ALAMAT-SERVER:8501`. Untuk akses publik, pasang reverse proxy dengan HTTPS (misalnya Nginx atau Caddy) dan batasi port langsung aplikasi dari internet.
6. Buat akun Admin / Owner pertama menggunakan kunci setup. Setelah akun pertama berhasil dibuat, hapus atau rotasi `BOOTSTRAP_SETUP_KEY` dari environment server.
7. Jadwalkan backup SQLite secara berkala ke lokasi terpisah dari server/container. Uji proses restore pada salinan database, bukan database operasional.

**Persistensi database:** `docker-compose.yml` memasang `./database` sebagai volume ke `/app/database`. Jangan menghapus volume atau folder tersebut saat memperbarui aplikasi. Simpan backup terenkripsi di luar server.

### Opsi demo: Streamlit Community Cloud

Streamlit Community Cloud dapat dipakai untuk demo atau uji coba, tetapi filesystem lokalnya tidak cocok dijadikan penyimpanan permanen untuk transaksi keuangan. Database SQLite lokal dapat hilang saat aplikasi diredeploy atau lingkungan dibuat ulang. Jangan gunakan opsi ini untuk data operasional kecuali aplikasi sudah dipindahkan ke layanan database eksternal yang persisten dan telah diuji.

### Catatan keamanan database

Repository ini membawa file SQLite yang sudah ada agar data tidak hilang sesuai kebijakan pemeliharaan proyek. File tersebut dapat berisi informasi keuangan. Batasi akses repository dan server hanya kepada pihak berwenang; jangan menaruh database, backup, atau file rahasia di repository publik. Aturan `.gitignore` mencegah file database baru terlacak, tetapi tidak otomatis menghapus file database yang sudah pernah di-commit.


---

## 🧪 Pengujian Otomatis (Testing)

Proyek ini dilengkapi dengan rangkaian tes otomatis menggunakan `pytest` untuk memvalidasi formula akuntansi, keseimbangan jurnal, neraca saldo, neraca lajur, laporan keuangan, mutasi persediaan perpetual, HPP penjualan, manajemen periode, dan siklus akuntansi end-to-end:

```bash
# Jalankan seluruh test suite
pytest tests/ -v

# Jalankan uji end-to-end siklus akuntansi
pytest tests/test_e2e_accounting_cycle.py -v
```

Hasil uji: **204 passed (100% lulus)**.

---

## 📁 Struktur Folder

```text
sistem-akuntansi-cabai/
├── app.py                      # Entry point aplikasi
├── requirements.txt            # Dependensi pip dipin
├── theme.py                    # Tema warna dan identitas usaha
├── README.md                   # Dokumentasi publik proyek
├── PROJECT_BRIEF.md            # Spesifikasi dan master prompt proyek
├── .streamlit/
│   └── config.toml             # Konfigurasi tema warna Streamlit
├── database/                   # Modul database SQLite & seed data
├── services/                   # 15 modul logika akuntansi independen
├── views/                      # 15 halaman antarmuka pengguna
├── utils/                      # Formatting, export Excel/PDF, UI components
├── tests/                      # 13 file unit test & end-to-end test
└── docs/                       # Dokumentasi arsitektur & penjelasan kode
```

---
*Dibuat untuk PT Sari Subur Langgeng Jaya Hidroponik Farm.*
