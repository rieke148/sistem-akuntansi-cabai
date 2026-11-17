"""
views/15_manajemen_pengguna.py
-------------------------------
Administrasi pengguna dan audit aktivitas. Hanya Admin / Owner.
"""

import streamlit as st
from utils.ui_components import render_page_header
import pandas as pd

from services import auth_service
from services.permission_service import wajib_punya_izin, pengguna_aktif, punya_izin


wajib_punya_izin("users.manage")
user = pengguna_aktif()
if not user:
    st.stop()
actor_id = int(user["id"])

render_page_header("Manajemen Pengguna", "Atur akun, peran, izin akses, dan riwayat aktivitas pengguna.", eyebrow="administrasi")
st.caption("Buat akun, atur role, aktif/nonaktifkan pengguna, dan reset password.")

label_tab = ["Pengguna"]
if punya_izin("audit.view"):
    label_tab.append("Audit Aktivitas")

semua_tab = st.tabs(label_tab)
tab_user = semua_tab[0]
tab_audit = semua_tab[1] if len(semua_tab) > 1 else None

with tab_user:
    st.subheader("Buat Akun Pengguna")
    roles = auth_service.daftar_role()
    role_labels = {f"{r['role_name']} ({r['role_code']})": r["role_code"] for r in roles}

    with st.form("form_buat_pengguna", clear_on_submit=True):
        full_name = st.text_input("Nama lengkap")
        username = st.text_input("Username")
        role_label = st.selectbox("Role", list(role_labels))
        password = st.text_input("Password awal", type="password")
        confirm = st.text_input("Konfirmasi password", type="password")
        submitted = st.form_submit_button("Buat Pengguna", use_container_width=True)
    if submitted:
        if password != confirm:
            st.error("Konfirmasi password tidak cocok.")
        else:
            try:
                new_id = auth_service.buat_pengguna(
                    username, full_name, password, role_labels[role_label], actor_id
                )
                st.success(f"Akun berhasil dibuat (ID: {new_id}).")
                st.rerun()
            except (ValueError, PermissionError) as error:
                st.error(str(error))

    st.divider()
    st.subheader("Daftar Pengguna")
    users = auth_service.daftar_pengguna()
    if users:
        df = pd.DataFrame(users)
        df["status"] = df["is_active"].map({1: "Aktif", 0: "Nonaktif", True: "Aktif", False: "Nonaktif"})
        df = df.rename(columns={
            "full_name": "Nama", "username": "Username",
            "role_name": "Role", "status": "Status",
            "created_at": "Dibuat", "last_login_at": "Login Terakhir",
        })
        st.dataframe(
            df[["Nama", "Username", "Role", "Status", "Dibuat", "Login Terakhir"]],
            use_container_width=True, hide_index=True,
        )
    else:
        st.info("Belum ada pengguna.")

    if users:
        user_options = {
            f"{u['username']} — {u['full_name']} ({u['role_name']})": u
            for u in users
        }
        selected_label = st.selectbox("Pilih akun untuk dikelola", list(user_options))
        selected = user_options[selected_label]

        with st.expander("Ubah Role Pengguna"):
            with st.form("form_ubah_role"):
                new_role_label = st.selectbox(
                    "Role baru", list(role_labels),
                    index=list(role_labels.values()).index(selected["role_code"]),
                )
                save_role = st.form_submit_button("Simpan Role")
            if save_role:
                try:
                    auth_service.ubah_role_pengguna(
                        int(selected["id"]), role_labels[new_role_label], actor_id
                    )
                    st.success("Role berhasil diperbarui.")
                    st.rerun()
                except (ValueError, PermissionError) as error:
                    st.error(str(error))

        with st.expander("Status Akun"):
            active_new = st.checkbox(
                "Akun aktif", value=bool(selected["is_active"]),
                key=f"status_user_{selected['id']}",
            )
            if st.button("Simpan Status Akun", key=f"save_status_{selected['id']}"):
                try:
                    auth_service.ubah_status_pengguna(
                        int(selected["id"]), active_new, actor_id
                    )
                    st.success("Status akun berhasil diperbarui.")
                    st.rerun()
                except (ValueError, PermissionError) as error:
                    st.error(str(error))

        with st.expander("Reset Password"):
            with st.form("form_reset_password"):
                new_password = st.text_input("Password baru", type="password")
                confirm_password = st.text_input("Konfirmasi password baru", type="password")
                reset = st.form_submit_button("Reset Password")
            if reset:
                if new_password != confirm_password:
                    st.error("Konfirmasi password tidak cocok.")
                else:
                    try:
                        auth_service.reset_password_pengguna(
                            int(selected["id"]), new_password, actor_id
                        )
                        st.success("Password berhasil direset. Sampaikan password baru melalui kanal pribadi yang aman.")
                    except (ValueError, PermissionError) as error:
                        st.error(str(error))

if tab_audit is not None:
    with tab_audit:
        st.subheader("Audit Aktivitas Terbaru")
        logs = auth_service.daftar_audit_logs(250)
        if logs:
            audit_df = pd.DataFrame(logs).rename(columns={
                "created_at": "Waktu", "username": "Username",
                "full_name": "Nama Pengguna", "action": "Aktivitas",
                "entity_type": "Objek", "entity_id": "ID Objek",
                "details": "Detail",
            })
            st.dataframe(
                audit_df[["Waktu", "Username", "Nama Pengguna", "Aktivitas", "Objek", "ID Objek", "Detail"]],
                use_container_width=True, hide_index=True,
            )
        else:
            st.info("Belum ada aktivitas tercatat.")
