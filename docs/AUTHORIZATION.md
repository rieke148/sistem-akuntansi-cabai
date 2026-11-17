# Login dan Otorisasi Pengguna

## Role bawaan

| Kode | Role | Ringkasan |
|---|---|---|
| `admin_owner` | Admin / Owner | Akses penuh, manajemen pengguna, backup dan restore |
| `accountant` | Akuntan | Proses akuntansi, penggajian, laporan, dan ekspor laporan |
| `inventory` | Petugas Gudang / Persediaan | Item, panen, dan kartu persediaan |
| `leadership` | Pimpinan | Dashboard, jurnal, buku besar, dan laporan baca-saja |

Hak akses diberikan melalui daftar permission di `services/auth_service.py`.
Navigasi hanya menampilkan halaman yang diizinkan dan setiap halaman menjalankan
pemeriksaan permission kembali. Tab Master Data, kelompok transaksi, hapus jurnal,
serta restore/backup database juga dibatasi per izin.

## Setup Admin Pertama

Aplikasi tidak membuat username atau password default. Sebelum login pertama,
atur secret `BOOTSTRAP_SETUP_KEY` pada environment atau Streamlit Secrets.

Contoh lokal melalui file `.streamlit/secrets.toml` (jangan commit file ini ke Git):

```toml
BOOTSTRAP_SETUP_KEY = "isi-dengan-rahasia-panjang-dan-unik"
```

Pada Streamlit Community Cloud, masukkan nilai yang sama di pengaturan **Secrets**
aplikasi. Buka aplikasi, lalu buat akun Admin / Owner pertama menggunakan kunci
setup, nama, username, dan password. Form setup hanya tersedia saat belum ada
pengguna. Setelah admin pertama dibuat, setup awal otomatis ditutup.

Password minimal 12 karakter dan harus memakai setidaknya tiga kelompok karakter:
huruf kecil, huruf besar, angka, atau simbol. Username 4–32 karakter.

## Kontrol keamanan saat ini

- Password disimpan sebagai PBKDF2-HMAC-SHA256 dengan salt acak per akun
  dan 600.000 iterasi.
- Lima percobaan login gagal mengunci username selama 15 menit.
- Session berakhir setelah 8 jam tidak aktif. Logout, session kedaluwarsa, atau akun yang dinonaktifkan juga membersihkan seluruh state sementara Streamlit agar pratinjau transaksi dan form tidak terbawa ke pengguna berikutnya.
- Akun nonaktif ditolak saat login dan saat session diperiksa ulang.
- Perubahan pengguna, login, dan logout dicatat dalam `audit_logs`.
- Admin aktif terakhir tidak dapat dinonaktifkan atau diturunkan role-nya.
- Reset, restore, dan reset ke data contoh hanya tersedia untuk Admin / Owner.
- Akuntan hanya dapat mengekspor laporan, bukan mengunduh atau memulihkan database.

## Catatan pengujian dan deployment

Jalankan pengujian autentikasi dan session:

```bash
pytest tests/test_auth.py tests/test_permission_service.py -v
```

Lalu jalankan seluruh suite:

```bash
pytest tests/ -v
```

Aplikasi saat ini menggunakan SQLite lokal. Untuk aplikasi multi-worker atau beberapa
replica, pindahkan database pengguna dan data akuntansi ke database terpusat yang
mendukung akses bersamaan. Pastikan aplikasi diakses melalui HTTPS dan backup
database disimpan pada media persisten yang aman.

## Batas cakupan audit

Audit log pada implementasi awal mencatat autentikasi, logout, dan perubahan akun
pengguna. Pencatatan aktor untuk seluruh transaksi akuntansi dan perubahan master
data merupakan pekerjaan lanjutan yang perlu ditambahkan pada layanan bisnis.
