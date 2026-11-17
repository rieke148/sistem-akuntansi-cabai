"""
services/auth_service.py
------------------------
Autentikasi pengguna, pengelolaan akun, role, permission, dan audit log.
Password disimpan menggunakan PBKDF2-HMAC-SHA256 (600.000 iterasi),
salt acak per pengguna, dan perbandingan hash constant-time.
"""

import base64
import hashlib
import hmac
import json
import re
import secrets
from datetime import datetime, timedelta, timezone

from database.connection import get_connection
from database.schema import buat_tabel_otorisasi


ITERATIONS = 600_000
SALT_BYTES = 16
MAX_LOGIN_FAILURES = 5
LOCKOUT_MINUTES = 15

ROLES = {
    "admin_owner": ("Admin / Owner", "Akses penuh dan pengelolaan sistem."),
    "accountant": ("Akuntan", "Pencatatan akuntansi dan penyusunan laporan."),
    "inventory": ("Petugas Gudang / Persediaan", "Pengelolaan item, panen, dan stok."),
    "leadership": ("Pimpinan", "Pemantauan dashboard dan laporan secara baca-saja."),
}

PERMISSIONS = {
    "dashboard.view": ("Lihat Dashboard", "Beranda", "Melihat ringkasan dashboard."),
    "master_data.view": ("Lihat Master Data", "Master Data", "Membuka menu master data."),
    "master_data.accounts.manage": ("Kelola Bagan Akun", "Master Data", "Menambah dan mengubah bagan akun."),
    "master_data.partners.manage": ("Kelola Pelanggan dan Supplier", "Master Data", "Mengelola pelanggan dan supplier."),
    "master_data.items.view": ("Lihat Item Persediaan", "Master Data", "Melihat daftar item persediaan."),
    "master_data.items.manage": ("Kelola Item Persediaan", "Master Data", "Menambah, mengubah, dan menonaktifkan item."),
    "master_data.staff.manage": ("Kelola Data Pekerja dan Aset", "Master Data", "Mengelola pekerja, aset, dan blok lahan."),
    "master_data.opening.manage": ("Kelola Saldo Awal", "Master Data", "Mengelola saldo awal akun dan persediaan."),
    "master_data.settings.manage": ("Kelola Periode dan Parameter", "Master Data", "Mengelola periode serta parameter."),
    "transactions.view": ("Buka Input Transaksi", "Transaksi", "Membuka halaman input transaksi."),
    "transactions.financial.manage": ("Kelola Transaksi Keuangan", "Transaksi", "Mencatat penjualan, pembelian, kas, biaya, dan aset."),
    "transactions.inventory.manage": ("Kelola Transaksi Persediaan", "Transaksi", "Mencatat panen dan transaksi persediaan."),
    "payroll.manage": ("Kelola Penggajian", "Penggajian", "Mengelola absensi dan jurnal penggajian."),
    "payroll.summary.view": ("Lihat Ringkasan Penggajian", "Penggajian", "Melihat ringkasan penggajian."),
    "journals.view": ("Lihat Jurnal", "Jurnal", "Melihat jurnal umum dan jurnal khusus."),
    "journals.manage": ("Kelola Jurnal", "Jurnal", "Melakukan proses pencatatan jurnal."),
    "inventory.view": ("Lihat Kartu Persediaan", "Persediaan", "Melihat saldo dan riwayat persediaan."),
    "inventory.manage": ("Kelola Persediaan", "Persediaan", "Mengelola proses persediaan."),
    "ledger.view": ("Lihat Buku Besar", "Buku Besar", "Melihat buku besar dan buku besar pembantu."),
    "reports.view": ("Lihat Laporan", "Laporan", "Melihat neraca saldo dan laporan keuangan."),
    "reports.manage": ("Proses Laporan dan Penyesuaian", "Laporan", "Mengelola penyesuaian dan proses laporan."),
    "closing.manage": ("Proses Jurnal Penutup", "Penutupan", "Menjalankan proses jurnal penutup."),
    "backup.access": ("Buka Backup dan Export", "Utilitas", "Membuka fitur backup dan export."),
    "backup.export": ("Export Data", "Utilitas", "Mengunduh laporan dan backup."),
    "backup.restore": ("Restore Database", "Utilitas", "Memulihkan database dari file backup."),
    "users.manage": ("Kelola Pengguna", "Administrasi", "Membuat dan mengelola akun pengguna."),
    "audit.view": ("Lihat Audit Log", "Administrasi", "Melihat catatan aktivitas sistem."),
}

ADMIN_PERMISSIONS = set(PERMISSIONS)
ACCOUNTANT_PERMISSIONS = {
    "dashboard.view", "master_data.view",
    "master_data.accounts.manage", "master_data.partners.manage",
    "master_data.items.view", "master_data.staff.manage",
    "master_data.opening.manage", "master_data.settings.manage",
    "transactions.view", "transactions.financial.manage",
    "payroll.manage", "journals.view", "journals.manage",
    "inventory.view", "ledger.view", "reports.view", "reports.manage",
    "closing.manage", "backup.access", "backup.export",
}
INVENTORY_PERMISSIONS = {
    "master_data.view", "master_data.items.view",
    "master_data.items.manage", "transactions.view",
    "transactions.inventory.manage", "inventory.view", "inventory.manage",
}
LEADERSHIP_PERMISSIONS = {
    "dashboard.view", "payroll.summary.view", "journals.view",
    "inventory.view", "ledger.view", "reports.view",
}
ROLE_PERMISSIONS = {
    "admin_owner": ADMIN_PERMISSIONS,
    "accountant": ACCOUNTANT_PERMISSIONS,
    "inventory": INVENTORY_PERMISSIONS,
    "leadership": LEADERSHIP_PERMISSIONS,
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_text(value: datetime | None = None) -> str:
    return (value or _utc_now()).isoformat(timespec="seconds")


def buat_hash_password(password: str) -> str:
    """Menghasilkan hash PBKDF2 dengan salt unik. Hash ini bukan password asli."""
    salt = secrets.token_bytes(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, ITERATIONS
    )
    return "pbkdf2_sha256$%s$%s$%s" % (
        ITERATIONS,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    )


def verifikasi_password(password: str, encoded_hash: str) -> bool:
    """Memverifikasi password tanpa membandingkan hash dengan operator biasa."""
    try:
        algorithm, iterations, salt_b64, digest_b64 = encoded_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        rounds = int(iterations)
        if rounds < 100_000 or rounds > 2_000_000:
            return False
        salt = base64.b64decode(salt_b64, validate=True)
        expected = base64.b64decode(digest_b64, validate=True)
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, rounds
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError, AttributeError):
        return False


def validasi_password(password: str) -> None:
    """Aturan password baru: minimal 12 karakter dan 3 dari 4 kelompok karakter."""
    if len(password) < 12:
        raise ValueError("Password minimal 12 karakter.")
    kelompok = sum((
        bool(re.search(r"[a-z]", password)),
        bool(re.search(r"[A-Z]", password)),
        bool(re.search(r"\d", password)),
        bool(re.search(r"[^A-Za-z0-9]", password)),
    ))
    if kelompok < 3:
        raise ValueError(
            "Gunakan minimal 3 jenis karakter: huruf kecil, huruf besar, angka, atau simbol."
        )


def validasi_username(username: str) -> str:
    username = str(username or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{3,31}", username):
        raise ValueError(
            "Username harus 4–32 karakter dan hanya boleh berisi huruf, angka, titik, garis bawah, atau tanda hubung."
        )
    return username


def inisialisasi_otorisasi() -> None:
    """Membuat tabel dan menambahkan role/permission bawaan secara idempotent."""
    buat_tabel_otorisasi()
    koneksi = get_connection()
    try:
        for code, (name, description) in ROLES.items():
            koneksi.execute(
                "INSERT OR IGNORE INTO roles (role_code, role_name, description) VALUES (?, ?, ?)",
                (code, name, description),
            )
        for code, (name, module, description) in PERMISSIONS.items():
            koneksi.execute(
                """INSERT OR IGNORE INTO permissions
                   (permission_code, permission_name, module, description)
                   VALUES (?, ?, ?, ?)""",
                (code, name, module, description),
            )
        for role_code, codes in ROLE_PERMISSIONS.items():
            role = koneksi.execute(
                "SELECT id FROM roles WHERE role_code = ?", (role_code,)
            ).fetchone()
            for permission_code in codes:
                permission = koneksi.execute(
                    "SELECT id FROM permissions WHERE permission_code = ?",
                    (permission_code,),
                ).fetchone()
                koneksi.execute(
                    "INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)",
                    (role["id"], permission["id"]),
                )
        koneksi.commit()
    finally:
        koneksi.close()


def jumlah_pengguna() -> int:
    koneksi = get_connection()
    try:
        return int(koneksi.execute("SELECT COUNT(*) FROM users").fetchone()[0])
    finally:
        koneksi.close()


def daftar_role() -> list[dict]:
    koneksi = get_connection()
    try:
        rows = koneksi.execute(
            "SELECT role_code, role_name, description FROM roles ORDER BY id"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        koneksi.close()


def _catat_audit(
    koneksi,
    user_id: int | None,
    action: str,
    entity_type: str | None = None,
    entity_id: str | int | None = None,
    details: dict | None = None,
) -> None:
    koneksi.execute(
        """INSERT INTO audit_logs
           (user_id, action, entity_type, entity_id, details)
           VALUES (?, ?, ?, ?, ?)""",
        (
            user_id, action, entity_type,
            str(entity_id) if entity_id is not None else None,
            json.dumps(details or {}, ensure_ascii=False),
        ),
    )


def buat_admin_pertama(
    username: str,
    full_name: str,
    password: str,
    setup_key: str,
    expected_setup_key: str,
) -> int:
    """Membuat Admin pertama secara atomik hanya jika belum ada pengguna."""
    if not expected_setup_key or len(str(expected_setup_key)) < 24:
        raise ValueError(
            "BOOTSTRAP_SETUP_KEY harus diatur sebagai secret minimal 24 karakter."
        )
    if not hmac.compare_digest(str(setup_key), str(expected_setup_key)):
        raise ValueError("Kunci setup tidak valid.")

    username = validasi_username(username)
    nama = str(full_name or "").strip()
    if len(nama) < 2 or len(nama) > 100:
        raise ValueError("Nama lengkap harus berisi 2–100 karakter.")
    validasi_password(password)
    password_hash = buat_hash_password(password)

    koneksi = get_connection()
    try:
        # Kunci penulisan SQLite agar hanya satu request setup admin yang lolos.
        koneksi.execute("BEGIN IMMEDIATE")
        jumlah = int(koneksi.execute("SELECT COUNT(*) FROM users").fetchone()[0])
        if jumlah:
            raise ValueError("Setup admin pertama sudah pernah dilakukan.")

        role = koneksi.execute(
            "SELECT id FROM roles WHERE role_code = 'admin_owner'"
        ).fetchone()
        if not role:
            raise ValueError("Role Admin / Owner belum tersedia.")

        cursor = koneksi.execute(
            """INSERT INTO users (username, full_name, password_hash, role_id)
               VALUES (?, ?, ?, ?)""",
            (username, nama, password_hash, role["id"]),
        )
        user_id = int(cursor.lastrowid)
        _catat_audit(
            koneksi, None, "initial_admin_created", "users", user_id,
            {"username": username, "role": "admin_owner"},
        )
        koneksi.commit()
        return user_id
    except Exception as error:
        koneksi.rollback()
        if "UNIQUE constraint failed: users.username" in str(error):
            raise ValueError("Username sudah digunakan.") from error
        raise
    finally:
        koneksi.close()

def _pastikan_admin_aktif(actor_user_id: int) -> None:
    """Validasi Admin / Owner di lapisan service, bukan hanya di tampilan."""
    koneksi = get_connection()
    try:
        row = koneksi.execute(
            """SELECT r.role_code, u.is_active
               FROM users u JOIN roles r ON r.id = u.role_id
               WHERE u.id = ?""",
            (actor_user_id,),
        ).fetchone()
        if not row or not row["is_active"] or row["role_code"] != "admin_owner":
            raise PermissionError(
                "Hanya Admin / Owner aktif yang boleh mengelola akun pengguna."
            )
    finally:
        koneksi.close()


def buat_pengguna(
    username: str,
    full_name: str,
    password: str,
    role_code: str,
    actor_user_id: int,
) -> int:
    """Membuat akun pengguna oleh administrator yang sudah login."""
    _pastikan_admin_aktif(actor_user_id)
    return _buat_pengguna(
        username, full_name, password, role_code,
        actor_user_id=actor_user_id, action="user_created",
    )


def _buat_pengguna(
    username: str,
    full_name: str,
    password: str,
    role_code: str,
    actor_user_id: int | None,
    action: str,
) -> int:
    username = validasi_username(username)
    nama = str(full_name or "").strip()
    if len(nama) < 2 or len(nama) > 100:
        raise ValueError("Nama lengkap harus berisi 2–100 karakter.")
    validasi_password(password)
    if role_code not in ROLES:
        raise ValueError("Role pengguna tidak dikenal.")
    password_hash = buat_hash_password(password)

    koneksi = get_connection()
    try:
        role = koneksi.execute(
            "SELECT id FROM roles WHERE role_code = ?", (role_code,)
        ).fetchone()
        if not role:
            raise ValueError("Role belum tersedia. Inisialisasi sistem otorisasi terlebih dahulu.")
        cursor = koneksi.execute(
            """INSERT INTO users (username, full_name, password_hash, role_id)
               VALUES (?, ?, ?, ?)""",
            (username, nama, password_hash, role["id"]),
        )
        user_id = int(cursor.lastrowid)
        _catat_audit(
            koneksi, actor_user_id, action, "users", user_id,
            {"username": username, "role": role_code},
        )
        koneksi.commit()
        return user_id
    except Exception as error:
        koneksi.rollback()
        if "UNIQUE constraint failed: users.username" in str(error):
            raise ValueError("Username sudah digunakan.") from error
        raise
    finally:
        koneksi.close()


def _status_lockout(koneksi, username_key: str) -> datetime | None:
    row = koneksi.execute(
        "SELECT locked_until FROM login_attempts WHERE username_key = ?",
        (username_key,),
    ).fetchone()
    if not row or not row["locked_until"]:
        return None
    try:
        until = datetime.fromisoformat(row["locked_until"])
        if until > _utc_now():
            return until
    except ValueError:
        return None
    koneksi.execute(
        "UPDATE login_attempts SET failed_attempts = 0, locked_until = NULL WHERE username_key = ?",
        (username_key,),
    )
    return None


def autentikasi(username: str, password: str) -> dict | None:
    """
    Memeriksa kredensial. Mengembalikan profil pengguna tanpa hash password,
    atau None jika kredensial salah, akun nonaktif, atau sedang terkunci.
    """
    username_key = str(username or "").strip().casefold()
    if not username_key or not password:
        return None

    koneksi = get_connection()
    try:
        locked_until = _status_lockout(koneksi, username_key)
        if locked_until:
            koneksi.commit()
            return None

        row = koneksi.execute(
            """SELECT u.id, u.username, u.full_name, u.password_hash,
                      u.is_active, u.role_id, u.session_version, r.role_code, r.role_name
               FROM users u JOIN roles r ON r.id = u.role_id
               WHERE u.username = ? COLLATE NOCASE""",
            (username_key,),
        ).fetchone()

        password_valid = verifikasi_password(password, row["password_hash"]) if row else False
        if not row or not password_valid or not row["is_active"]:
            attempt = koneksi.execute(
                "SELECT failed_attempts FROM login_attempts WHERE username_key = ?",
                (username_key,),
            ).fetchone()
            failures = (int(attempt["failed_attempts"]) if attempt else 0) + 1
            lock_until = (
                _utc_text(_utc_now() + timedelta(minutes=LOCKOUT_MINUTES))
                if failures >= MAX_LOGIN_FAILURES else None
            )
            koneksi.execute(
                """INSERT INTO login_attempts
                   (username_key, failed_attempts, locked_until, updated_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(username_key) DO UPDATE SET
                     failed_attempts = excluded.failed_attempts,
                     locked_until = excluded.locked_until,
                     updated_at = excluded.updated_at""",
                (username_key, failures, lock_until, _utc_text()),
            )
            _catat_audit(
                koneksi, int(row["id"]) if row else None,
                "login_failed", "authentication", username_key,
                {"reason": "invalid_credentials_or_inactive"},
            )
            koneksi.commit()
            return None

        koneksi.execute(
            "DELETE FROM login_attempts WHERE username_key = ?", (username_key,)
        )
        koneksi.execute(
            "UPDATE users SET last_login_at = ?, updated_at = ? WHERE id = ?",
            (_utc_text(), _utc_text(), row["id"]),
        )
        _catat_audit(koneksi, int(row["id"]), "login_success", "authentication", row["id"])
        koneksi.commit()
        return {
            "id": int(row["id"]),
            "username": row["username"],
            "full_name": row["full_name"],
            "is_active": bool(row["is_active"]),
            "role_id": int(row["role_id"]),
            "session_version": int(row["session_version"]),
            "role_code": row["role_code"],
            "role_name": row["role_name"],
        }
    finally:
        koneksi.close()


def ambil_pengguna(user_id: int) -> dict | None:
    koneksi = get_connection()
    try:
        row = koneksi.execute(
            """SELECT u.id, u.username, u.full_name, u.is_active,
                      u.role_id, u.session_version, r.role_code, r.role_name
               FROM users u JOIN roles r ON r.id = u.role_id
               WHERE u.id = ?""",
            (user_id,),
        ).fetchone()
        if not row or not row["is_active"]:
            return None
        return dict(row)
    finally:
        koneksi.close()


def ambil_permission_role(role_id: int) -> set[str]:
    koneksi = get_connection()
    try:
        rows = koneksi.execute(
            """SELECT p.permission_code
               FROM role_permissions rp
               JOIN permissions p ON p.id = rp.permission_id
               WHERE rp.role_id = ?""",
            (role_id,),
        ).fetchall()
        return {row["permission_code"] for row in rows}
    finally:
        koneksi.close()


def daftar_pengguna() -> list[dict]:
    koneksi = get_connection()
    try:
        rows = koneksi.execute(
            """SELECT u.id, u.username, u.full_name, u.is_active,
                      u.created_at, u.updated_at, u.last_login_at,
                      r.role_code, r.role_name
               FROM users u JOIN roles r ON r.id = u.role_id
               ORDER BY u.created_at DESC, u.id DESC"""
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        koneksi.close()


def ubah_role_pengguna(user_id: int, role_code: str, actor_user_id: int) -> None:
    _pastikan_admin_aktif(actor_user_id)
    if role_code not in ROLES:
        raise ValueError("Role pengguna tidak dikenal.")
    koneksi = get_connection()
    try:
        role = koneksi.execute(
            "SELECT id FROM roles WHERE role_code = ?", (role_code,)
        ).fetchone()
        target = koneksi.execute(
            """SELECT u.id, r.role_code FROM users u
               JOIN roles r ON r.id = u.role_id WHERE u.id = ?""",
            (user_id,),
        ).fetchone()
        if not target:
            raise ValueError("Pengguna tidak ditemukan.")
        if target["role_code"] == "admin_owner" and role_code != "admin_owner":
            jumlah_admin = koneksi.execute(
                """SELECT COUNT(*) FROM users u JOIN roles r ON r.id = u.role_id
                   WHERE r.role_code = 'admin_owner' AND u.is_active = 1"""
            ).fetchone()[0]
            if int(jumlah_admin) <= 1:
                raise ValueError("Role admin terakhir tidak boleh diturunkan.")
        koneksi.execute(
            "UPDATE users SET role_id = ?, session_version = session_version + 1, updated_at = ? WHERE id = ?",
            (role["id"], _utc_text(), user_id),
        )
        _catat_audit(
            koneksi, actor_user_id, "user_role_changed", "users", user_id,
            {"new_role": role_code},
        )
        koneksi.commit()
    except Exception:
        koneksi.rollback()
        raise
    finally:
        koneksi.close()


def ubah_status_pengguna(
    user_id: int, is_active: bool, actor_user_id: int
) -> None:
    _pastikan_admin_aktif(actor_user_id)
    if user_id == actor_user_id and not is_active:
        raise ValueError("Anda tidak dapat menonaktifkan akun yang sedang digunakan.")
    koneksi = get_connection()
    try:
        target = koneksi.execute(
            """SELECT u.id, u.is_active, r.role_code FROM users u
               JOIN roles r ON r.id = u.role_id WHERE u.id = ?""",
            (user_id,),
        ).fetchone()
        if not target:
            raise ValueError("Pengguna tidak ditemukan.")
        if target["role_code"] == "admin_owner" and target["is_active"] and not is_active:
            jumlah_admin = koneksi.execute(
                """SELECT COUNT(*) FROM users u JOIN roles r ON r.id = u.role_id
                   WHERE r.role_code = 'admin_owner' AND u.is_active = 1"""
            ).fetchone()[0]
            if int(jumlah_admin) <= 1:
                raise ValueError("Admin aktif terakhir tidak boleh dinonaktifkan.")
        koneksi.execute(
            "UPDATE users SET is_active = ?, session_version = session_version + 1, updated_at = ? WHERE id = ?",
            (int(is_active), _utc_text(), user_id),
        )
        _catat_audit(
            koneksi, actor_user_id,
            "user_activated" if is_active else "user_deactivated",
            "users", user_id,
        )
        koneksi.commit()
    except Exception:
        koneksi.rollback()
        raise
    finally:
        koneksi.close()


def reset_password_pengguna(
    user_id: int, new_password: str, actor_user_id: int
) -> None:
    _pastikan_admin_aktif(actor_user_id)
    validasi_password(new_password)
    password_hash = buat_hash_password(new_password)
    koneksi = get_connection()
    try:
        target = koneksi.execute(
            "SELECT username FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if not target:
            raise ValueError("Pengguna tidak ditemukan.")
        koneksi.execute(
            "UPDATE users SET password_hash = ?, session_version = session_version + 1, updated_at = ? WHERE id = ?",
            (password_hash, _utc_text(), user_id),
        )
        koneksi.execute(
            "DELETE FROM login_attempts WHERE username_key = ?",
            (str(target["username"]).casefold(),),
        )
        _catat_audit(
            koneksi, actor_user_id, "password_reset", "users", user_id
        )
        koneksi.commit()
    except Exception:
        koneksi.rollback()
        raise
    finally:
        koneksi.close()


def catat_logout(user_id: int) -> None:
    koneksi = get_connection()
    try:
        _catat_audit(koneksi, user_id, "logout", "authentication", user_id)
        koneksi.commit()
    finally:
        koneksi.close()


def daftar_audit_logs(limit: int = 200) -> list[dict]:
    limit = max(1, min(int(limit), 1000))
    koneksi = get_connection()
    try:
        rows = koneksi.execute(
            """SELECT a.id, a.created_at, a.action, a.entity_type,
                      a.entity_id, a.details, u.username, u.full_name
               FROM audit_logs a LEFT JOIN users u ON u.id = a.user_id
               ORDER BY a.id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        koneksi.close()
