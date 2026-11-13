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
   - Bagan Akun (Chart of Accounts 6 Digit), Pelanggan, Supplier, Item Persediaan, Pekerja, Aset Tetap, Blok Lahan, Saldo Awal, Periode Akuntansi, dan Parameter Operasional.

3. **Input Transaksi & Mesin Jurnal Otomatis**:
   - 10 Formulir transaksi spesifik (Penjualan Tunai/Tempo, Pembelian Tunai/Kredit, Pelunasan Piutang, Setoran Modal, Pemakaian Bahan, Catat Panen, Biaya Operasional, dan Beli Aset).
   - Fitur **Pratinjau Jurnal Interaktif** dengan validasi keseimbangan Debit == Kredit sebelum data tersimpan.

4. **Jurnal Umum & 4 Jurnal Khusus**:
   - Jurnal Umum kronologis lengkap dengan kode referensi akun.
   - 4 Jurnal Khusus berformat kolom akuntansi: *Sales Journal*, *Purchase Journal*, *Cash Receipt Journal*, dan *Cash Payment Journal*.

5. **Buku Besar & Buku Besar Pembantu**:
   - Buku Besar utama saldo berjalan dengan filter periode.
   - Buku Besar Pembantu Piutang (dengan analisis umur piutang / aging), Persediaan, dan Aset Tetap.

6. **Kartu Persediaan Moving Average**:
   - Kartu persediaan perpetual menggunakan metode rata-rata bergerak (*moving average*) untuk bahan produksi (bibit, pupuk, bambu, mulsa, pestisida) dan hasil panen cabai.

7. **Penggajian & Slip Upah**:
   - Perhitungan upah harian pekerja tetap (Rp90.000/hari) dan pekerja tambahan (Rp120.000/hari) per periode 2 mingguan, cetak slip upah, dan pencatatan akrual utang gaji.

8. **Ayat Jurnal Penyesuaian**:
   - Perhitungan otomatis penyusutan aset tetap (garis lurus), amortisasi plastik mulsa (1,5 tahun), akrual upah tenaga kerja, dan pemakaian bahan.

9. **Neraca Lajur 10 Kolom (Worksheet)**:
   - Kertas kerja lengkap 10 kolom menghubungkan Neraca Saldo, Penyesuaian, NSD, Laba Rugi, dan Neraca dengan verifikasi keseimbangan otomatis.

10. **Laporan Keuangan Standar**:
    - Laporan Laba Rugi (Pendapatan - Beban Produksi & Operasional = Laba Bersih).
    - Laporan Perubahan Ekuitas (Modal Awal + Tambahan Modal + Laba Bersih = Modal Akhir).
    - Neraca Bentuk Laporan (Validasi: Total Aset == Total Liabilitas + Total Ekuitas).
    - Laporan Arus Kas Metode Langsung (Operasi, Investasi, Pendanaan).

11. **Jurnal Penutup & Neraca Penutup**:
    - Penutupan akun nominal ke Ikhtisar L/R dan Laba Ditahan, serta penguncian periode akuntansi.

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

## ☁️ Panduan Deployment ke Streamlit Community Cloud

Aplikasi ini telah dioptimalkan untuk deployment ke **Streamlit Community Cloud** langsung dari repositori GitHub:

1. **Push Proyek ke GitHub**:
   - Pastikan file `requirements.txt`, `.streamlit/config.toml`, folder `database/`, `services/`, `views/`, dan `utils/` telah ter-commit.
2. **Koneksikan ke Streamlit Community Cloud**:
   - Buka [share.streamlit.io](https://share.streamlit.io).
   - Klik **New app**.
   - Pilih repository GitHub Anda, branch `main`, dan set **Main file path** ke `app.py`.
3. **Inisialisasi Otomatis (Cold-Start Safe)**:
   - Karena filesystem Streamlit Cloud bersifat ephemeral, `app.py` secara otomatis mendeteksi keberadaan database. Jika database belum ada, skema tabel, periode dasar (2025-2027), dan data seed contoh akan langsung dibuat otomatis saat pertama kali diakses.
   - Gunakan menu **Backup & Export** untuk mengunduh berkas `.db` secara berkala sebelum menutup sesi cloud.

---

## 🧪 Pengujian Otomatis (Testing)

Proyek ini dilengkapi dengan 204 tes otomatis menggunakan `pytest` yang memvalidasi seluruh formula akuntansi, keseimbangan jurnal, neraca saldo, neraca lajur, laporan keuangan, kartu persediaan, manajemen periode, dan siklus akuntansi end-to-end:

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
