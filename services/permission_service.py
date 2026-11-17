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
    for key in (
        "auth_user_id", "auth_login_at", "auth_last_activity",
        "permissions_admin_owner", "permissions_accountant",
        "permissions_inventory", "permissions_leadership",
    ):
        st.session_state.pop(key, None)


def pengguna_aktif() -> dict | None:
    user_id = st.session_state.get("auth_user_id")
    if not user_id:
        return None

    now = time.time()
    last_activity = float(st.session_state.get("auth_last_activity", now))
    if now - last_activity > SESSION_IDLE_SECONDS:
        try:
            auth_service.catat_logout(int(user_id))
        finally:
            hapus_session_login()
        return None

    user = auth_service.ambil_pengguna(int(user_id))
    if not user:
        hapus_session_login()
        return None

    st.session_state["auth_last_activity"] = now
    return user


def punya_izin(permission_code: str) -> bool:
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
    if not punya_izin(permission_code):
        st.error("Anda tidak memiliki hak akses untuk membuka halaman atau menjalankan tindakan ini.")
        st.stop()
