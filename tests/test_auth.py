"""Pengujian autentikasi dan otorisasi berbasis SQLite sementara."""

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from database import schema
from services import auth_service


@pytest.fixture
def auth_db(tmp_path, monkeypatch):
    db_path = tmp_path / "auth_test.db"

    def open_db():
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    monkeypatch.setattr(schema, "get_connection", open_db)
    monkeypatch.setattr(auth_service, "get_connection", open_db)
    auth_service.inisialisasi_otorisasi()
    return open_db


def test_hash_password_salt_berbeda_dan_verifikasi():
    one = auth_service.buat_hash_password("PasswordAman!2026")
    two = auth_service.buat_hash_password("PasswordAman!2026")
    assert one != two
    assert auth_service.verifikasi_password("PasswordAman!2026", one)
    assert not auth_service.verifikasi_password("password-salah", one)


def test_validasi_password():
    auth_service.validasi_password("PasswordAman!2026")
    with pytest.raises(ValueError):
        auth_service.validasi_password("pendek")
    with pytest.raises(ValueError):
        auth_service.validasi_password("semua huruf kecil saja")


def test_setup_admin_pertama_dan_setup_kedua_ditolak(auth_db):
    user_id = auth_service.buat_admin_pertama(
        "owner01", "Pemilik Sistem", "PasswordAman!2026",
        "setup-secret-yang-panjang-2026", "setup-secret-yang-panjang-2026",
    )
    assert user_id > 0
    assert auth_service.jumlah_pengguna() == 1
    with pytest.raises(ValueError, match="sudah pernah"):
        auth_service.buat_admin_pertama(
            "owner02", "Admin Kedua", "PasswordAman!2026",
            "setup-secret-yang-panjang-2026", "setup-secret-yang-panjang-2026",
        )


def test_setup_admin_membutuhkan_kunci_yang_benar(auth_db):
    with pytest.raises(ValueError, match="tidak valid"):
        auth_service.buat_admin_pertama(
            "owner01", "Pemilik Sistem", "PasswordAman!2026",
            "salah", "setup-secret-yang-panjang-2026",
        )
    assert auth_service.jumlah_pengguna() == 0


def test_autentikasi_pengguna_aktif(auth_db):
    user_id = auth_service.buat_admin_pertama(
        "owner01", "Pemilik Sistem", "PasswordAman!2026",
        "setup-secret-yang-panjang-2026", "setup-secret-yang-panjang-2026",
    )
    user = auth_service.autentikasi("OWNER01", "PasswordAman!2026")
    assert user["id"] == user_id
    assert user["role_code"] == "admin_owner"
    assert "password_hash" not in user


def test_login_salah_dikunci_setelah_lima_percobaan(auth_db):
    auth_service.buat_admin_pertama(
        "owner01", "Pemilik Sistem", "PasswordAman!2026",
        "setup-secret-yang-panjang-2026", "setup-secret-yang-panjang-2026",
    )
    for _ in range(auth_service.MAX_LOGIN_FAILURES):
        assert auth_service.autentikasi("owner01", "PasswordSalah!2026") is None
    assert auth_service.autentikasi("owner01", "PasswordAman!2026") is None


def test_role_memiliki_permission_yang_berbeda(auth_db):
    role_ids = {}
    conn = auth_db()
    for row in conn.execute("SELECT id, role_code FROM roles"):
        role_ids[row["role_code"]] = row["id"]
    conn.close()

    admin = auth_service.ambil_permission_role(role_ids["admin_owner"])
    accountant = auth_service.ambil_permission_role(role_ids["accountant"])
    inventory = auth_service.ambil_permission_role(role_ids["inventory"])
    leadership = auth_service.ambil_permission_role(role_ids["leadership"])

    assert "users.manage" in admin
    assert "users.manage" not in accountant
    assert "transactions.inventory.manage" in inventory
    assert "transactions.financial.manage" not in inventory
    assert "reports.view" in leadership
    assert "reports.manage" not in leadership


def test_admin_terakhir_tidak_bisa_dinonaktifkan(auth_db):
    admin_id = auth_service.buat_admin_pertama(
        "owner01", "Pemilik Sistem", "PasswordAman!2026",
        "setup-secret-yang-panjang-2026", "setup-secret-yang-panjang-2026",
    )
    with pytest.raises(ValueError, match="terakhir"):
        auth_service.ubah_status_pengguna(admin_id, False, actor_user_id=admin_id)


def test_akun_duplikat_ditolak(auth_db):
    auth_service.buat_admin_pertama(
        "owner01", "Pemilik Sistem", "PasswordAman!2026",
        "setup-secret-yang-panjang-2026", "setup-secret-yang-panjang-2026",
    )
    with pytest.raises(ValueError, match="Username sudah digunakan"):
        auth_service.buat_pengguna(
            "OWNER01", "Admin Kedua", "PasswordAman!2026",
            "admin_owner", actor_user_id=1,
        )


def test_akun_nonaktif_tidak_bisa_login(auth_db):
    admin_id = auth_service.buat_admin_pertama(
        "owner01", "Pemilik Sistem", "PasswordAman!2026",
        "setup-secret-yang-panjang-2026", "setup-secret-yang-panjang-2026",
    )
    user_id = auth_service.buat_pengguna(
        "accountant01", "Akuntan", "PasswordAman!2026",
        "accountant", actor_user_id=admin_id,
    )
    auth_service.ubah_status_pengguna(user_id, False, actor_user_id=admin_id)
    assert auth_service.autentikasi("accountant01", "PasswordAman!2026") is None


def test_perubahan_role_membatalkan_versi_session(auth_db):
    admin_id = auth_service.buat_admin_pertama(
        "owner01", "Pemilik Sistem", "PasswordAman!2026",
        "setup-secret-yang-panjang-2026", "setup-secret-yang-panjang-2026",
    )
    user_id = auth_service.buat_pengguna(
        "accountant01", "Akuntan", "PasswordAman!2026",
        "accountant", actor_user_id=admin_id,
    )
    sebelum = auth_service.ambil_pengguna(user_id)["session_version"]
    auth_service.ubah_role_pengguna(user_id, "inventory", actor_user_id=admin_id)
    sesudah = auth_service.ambil_pengguna(user_id)["session_version"]
    assert sesudah == sebelum + 1


def test_non_admin_tidak_bisa_mengelola_pengguna(auth_db):
    admin_id = auth_service.buat_admin_pertama(
        "owner01", "Pemilik Sistem", "PasswordAman!2026",
        "setup-secret-yang-panjang-2026", "setup-secret-yang-panjang-2026",
    )
    accountant_id = auth_service.buat_pengguna(
        "accountant01", "Akuntan", "PasswordAman!2026",
        "accountant", actor_user_id=admin_id,
    )
    with pytest.raises(PermissionError, match="Hanya Admin"):
        auth_service.buat_pengguna(
            "inventory01", "Petugas Gudang", "PasswordAman!2026",
            "inventory", actor_user_id=accountant_id,
        )
    with pytest.raises(PermissionError, match="Hanya Admin"):
        auth_service.ubah_status_pengguna(
            admin_id, False, actor_user_id=accountant_id
        )



def test_lockout_kedaluwarsa_dan_login_kembali_berhasil(auth_db, monkeypatch):
    """Setelah 15 menit, pengguna dapat login dan penghitung gagal direset."""
    waktu_awal = datetime(2026, 11, 17, 10, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(auth_service, "_utc_now", lambda: waktu_awal)
    auth_service.buat_admin_pertama(
        "owner01", "Pemilik Sistem", "PasswordAman!2026",
        "setup-secret-yang-panjang-2026", "setup-secret-yang-panjang-2026",
    )

    for _ in range(auth_service.MAX_LOGIN_FAILURES):
        assert auth_service.autentikasi("owner01", "PasswordSalah!2026") is None

    monkeypatch.setattr(
        auth_service, "_utc_now", lambda: waktu_awal + timedelta(minutes=16)
    )
    user = auth_service.autentikasi("owner01", "PasswordAman!2026")
    assert user is not None
    assert user["username"] == "owner01"

    koneksi = auth_db()
    jumlah_attempt = koneksi.execute(
        "SELECT COUNT(*) FROM login_attempts WHERE username_key = 'owner01'"
    ).fetchone()[0]
    koneksi.close()
    assert jumlah_attempt == 0


def test_login_berhasil_menghapus_percobaan_gagal(auth_db):
    """Login yang benar menghapus hitungan gagal sebelum akun terkunci."""
    auth_service.buat_admin_pertama(
        "owner01", "Pemilik Sistem", "PasswordAman!2026",
        "setup-secret-yang-panjang-2026", "setup-secret-yang-panjang-2026",
    )
    auth_service.autentikasi("owner01", "PasswordSalah!2026")
    auth_service.autentikasi("owner01", "PasswordSalah!2026")

    assert auth_service.autentikasi("owner01", "PasswordAman!2026") is not None

    koneksi = auth_db()
    jumlah_attempt = koneksi.execute(
        "SELECT COUNT(*) FROM login_attempts WHERE username_key = 'owner01'"
    ).fetchone()[0]
    koneksi.close()
    assert jumlah_attempt == 0


def test_reset_password_mengganti_password_dan_membatalkan_session(auth_db):
    """Reset password menaikkan session_version dan menolak password lama."""
    admin_id = auth_service.buat_admin_pertama(
        "owner01", "Pemilik Sistem", "PasswordAman!2026",
        "setup-secret-yang-panjang-2026", "setup-secret-yang-panjang-2026",
    )
    user_id = auth_service.buat_pengguna(
        "accountant01", "Akuntan", "PasswordAman!2026",
        "accountant", actor_user_id=admin_id,
    )
    versi_sebelum = auth_service.ambil_pengguna(user_id)["session_version"]

    auth_service.reset_password_pengguna(
        user_id, "PasswordBaru!2026", actor_user_id=admin_id
    )

    pengguna = auth_service.ambil_pengguna(user_id)
    assert pengguna["session_version"] == versi_sebelum + 1
    assert auth_service.autentikasi("accountant01", "PasswordAman!2026") is None
    assert auth_service.autentikasi("accountant01", "PasswordBaru!2026") is not None
