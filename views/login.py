"""
views/login.py
--------------
Halaman login dan setup administrator pertama.
"""

import os
import time
import streamlit as st

from services import auth_service
from services.permission_service import hapus_session_login


def _bootstrap_key() -> str:
    value = os.environ.get("BOOTSTRAP_SETUP_KEY", "")
    if value:
        return value
    try:
        return str(st.secrets.get("BOOTSTRAP_SETUP_KEY", ""))
    except Exception:
        return ""


def tampilkan() -> None:
    st.title("🌶️ Sistem Informasi Siklus Akuntansi")
    st.caption("PT Sari Subur Langgeng Jaya Hidroponik Farm")
    st.markdown("### Masuk ke akun Anda")

    if auth_service.jumlah_pengguna() == 0:
        st.info(
            "Belum ada akun pengguna. Buat akun Admin / Owner pertama menggunakan "
            "kunci setup yang disimpan di konfigurasi rahasia aplikasi."
        )
        expected_key = _bootstrap_key()
        if not expected_key:
            st.error(
                "Setup belum diaktifkan. Tambahkan BOOTSTRAP_SETUP_KEY pada "
                "Streamlit Secrets atau environment variable sebelum membuat admin pertama."
            )
            st.code('BOOTSTRAP_SETUP_KEY = "buat-kunci-rahasia-yang-panjang-dan-unik"')
            return

        with st.form("form_setup_admin", clear_on_submit=False):
            setup_key = st.text_input("Kunci setup", type="password")
            full_name = st.text_input("Nama pemilik / administrator")
            username = st.text_input("Username admin")
            password = st.text_input("Password baru", type="password")
            confirm = st.text_input("Ulangi password", type="password")
            submitted = st.form_submit_button("Buat Admin Pertama", use_container_width=True)
        if submitted:
            if password != confirm:
                st.error("Konfirmasi password tidak cocok.")
                return
            try:
                user_id = auth_service.buat_admin_pertama(
                    username, full_name, password, setup_key, expected_key
                )
                st.session_state["auth_user_id"] = user_id
                st.session_state["auth_login_at"] = time.time()
                st.session_state["auth_last_activity"] = time.time()
                st.success("Akun Admin / Owner berhasil dibuat. Anda sudah masuk.")
                st.rerun()
            except ValueError as error:
                st.error(str(error))
        return

    with st.form("form_login", clear_on_submit=True):
        username = st.text_input("Username", autocomplete="username")
        password = st.text_input("Password", type="password", autocomplete="current-password")
        submitted = st.form_submit_button("Masuk", use_container_width=True)

    if submitted:
        user = auth_service.autentikasi(username, password)
        if not user:
            st.error("Username atau password salah, akun nonaktif, atau login sedang dikunci.")
            return
        hapus_session_login()
        st.session_state["auth_user_id"] = int(user["id"])
        now = time.time()
        st.session_state["auth_login_at"] = now
        st.session_state["auth_last_activity"] = now
        st.success(f"Selamat datang, {user['full_name']}!")
        st.rerun()


