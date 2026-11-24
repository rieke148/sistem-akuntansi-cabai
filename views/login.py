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
    """Menampilkan halaman akses akun dan setup administrator pertama."""
    panel_brand, panel_login = st.columns([1.15, 1])

    with panel_brand:
        with st.container(border=True):
            st.caption("SISTEM INFORMASI AKUNTANSI · ENTERPRISE")
            st.title("Kelola bisnis cabai dengan lebih terukur")
            st.write(
                "Satu ruang kerja untuk transaksi, persediaan, jurnal, "
                "dan laporan keuangan perusahaan."
            )
            st.divider()
            st.markdown("**Siklus akuntansi terintegrasi**")
            st.caption("Transaksi → Jurnal → Buku Besar → Laporan Keuangan")
            st.markdown("**Kontrol akses berbasis peran**")
            st.caption("Akses pengguna disesuaikan dengan tanggung jawab operasional.")
            st.markdown("**Data keuangan terpusat**")
            st.caption("Riwayat transaksi tersimpan dalam database perusahaan.")

    with panel_login:
        with st.container(border=True):
            jumlah_user = auth_service.jumlah_pengguna()
            if jumlah_user == 0:
                st.subheader("Setup administrator")
                st.caption("Buat akun Admin / Owner pertama untuk mengaktifkan aplikasi.")
                st.info(
                    "Setup awal memerlukan kunci rahasia yang disimpan pada "
                    "environment variable atau Streamlit Secrets."
                )
                expected_key = _bootstrap_key()
                if not expected_key:
                    st.error(
                        "Setup belum diaktifkan. Tambahkan BOOTSTRAP_SETUP_KEY "
                        "pada konfigurasi rahasia aplikasi sebelum membuat admin pertama."
                    )
                    return

                with st.form("form_setup_admin", clear_on_submit=False):
                    setup_key = st.text_input("Kunci setup", type="password")
                    full_name = st.text_input("Nama pemilik / administrator")
                    username = st.text_input("Username admin")
                    password = st.text_input("Password baru", type="password")
                    confirm = st.text_input("Ulangi password", type="password")
                    submitted = st.form_submit_button(
                        "Buat Admin Pertama",
                        use_container_width=True,
                        type="primary",
                    )
                if submitted:
                    if password != confirm:
                        st.error("Konfirmasi password tidak cocok.")
                        return
                    try:
                        user_id = auth_service.buat_admin_pertama(
                            username, full_name, password, setup_key, expected_key
                        )
                        st.session_state["auth_user_id"] = user_id
                        st.session_state["auth_session_version"] = 0
                        st.session_state["auth_login_at"] = time.time()
                        st.session_state["auth_last_activity"] = time.time()
                        st.success("Akun Admin / Owner berhasil dibuat.")
                        st.rerun()
                    except ValueError as error:
                        st.error(str(error))
                return

            st.subheader("Masuk ke akun")
            st.caption("Gunakan username dan password yang telah terdaftar.")
            with st.form("form_login", clear_on_submit=True):
                username = st.text_input("Username", autocomplete="username")
                password = st.text_input(
                    "Password",
                    type="password",
                    autocomplete="current-password",
                )
                submitted = st.form_submit_button(
                    "Masuk",
                    use_container_width=True,
                    type="primary",
                )

            if submitted:
                user = auth_service.autentikasi(username, password)
                if not user:
                    st.error(
                        "Username atau password salah, akun nonaktif, "
                        "atau login sedang dikunci."
                    )
                    return
                hapus_session_login()
                st.session_state["auth_user_id"] = int(user["id"])
                st.session_state["auth_session_version"] = int(user["session_version"])
                now = time.time()
                st.session_state["auth_login_at"] = now
                st.session_state["auth_last_activity"] = now
                st.success(f"Selamat datang, {user['full_name']}!")
                st.rerun()
