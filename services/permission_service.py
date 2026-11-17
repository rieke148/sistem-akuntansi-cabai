"""
services/permission_service.py
------------------------------
Pembantu pemeriksaan session dan hak akses (RBAC) untuk halaman Streamlit.
"""

import time
import streamlit as st

from services import auth_service

SESSION_IDLE_SECONDS = 8 * 60 * 60


def hapus_session_login() -> None:
    """Bersihkan seluruh state sesi agar data sementara tidak berpindah antar pengguna."""
    st.session_state.clear()


def keluar_pengguna(user_id: int) -> bool:
    """
    Catat logout lalu selalu bersihkan seluruh state sesi.
    Mengembalikan False jika audit log gagal, tetapi pengguna tetap dikeluarkan.
    """
    audit_berhasil = True
    try:
        auth_service.catat_logout(int(user_id))
    except Exception:
        # Kegagalan audit tidak boleh membuat sesi pengguna tetap terbuka.
        audit_berhasil = False
    finally:
        hapus_session_login()
    return audit_berhasil


def pengguna_aktif() -> dict | None:
    """Memvalidasi akun, versi sesi, dan batas tidak aktif sebelum halaman dibuka."""
    user_id = st.session_state.get("auth_user_id")
    if not user_id:
        return None

    # ID akun harus berupa bilangan bulat yang valid; state rusak ditolak.
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        hapus_session_login()
        return None

    now = time.time()
    aktivitas_terakhir = st.session_state.get("auth_last_activity")

    # Sesi yang kehilangan waktu aktivitas dianggap tidak valid (fail closed).
    try:
        if aktivitas_terakhir is None:
            raise ValueError("Waktu aktivitas sesi tidak tersedia.")
        last_activity = float(aktivitas_terakhir)
    except (TypeError, ValueError):
        hapus_session_login()
        return None

    if now - last_activity > SESSION_IDLE_SECONDS:
        keluar_pengguna(user_id)
        return None

    user = auth_service.ambil_pengguna(user_id)
    if not user:
        hapus_session_login()
        return None

    # Nilai versi yang hilang/rusak tidak boleh melewati pemeriksaan sesi.
    try:
        session_version = int(st.session_state.get("auth_session_version"))
    except (TypeError, ValueError):
        hapus_session_login()
        return None

    if session_version != int(user["session_version"]):
        hapus_session_login()
        return None

    st.session_state["auth_last_activity"] = now
    return user


def punya_izin(permission_code: str) -> bool:
    """Memeriksa apakah role pengguna aktif memiliki izin yang diminta."""
    user = pengguna_aktif()
    if not user:
        return False
    cache_key = f"permissions_{user['role_code']}"
    permissions = st.session_state.get(cache_key)
    if permissions is None:
        permissions = auth_service.ambil_permission_role(int(user["role_id"]))
        st.session_state[cache_key] = sorted(permissions)
    return permission_code in permissions


def wajib_punya_izin(permission_code: str) -> None:
    """Menghentikan halaman jika pengguna tidak memiliki izin yang diperlukan."""
    if not punya_izin(permission_code):
        st.error("Anda tidak memiliki hak akses untuk membuka halaman atau menjalankan tindakan ini.")
        st.stop()
