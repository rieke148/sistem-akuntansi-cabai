"""
utils/ui_components.py
----------------------
Tujuan  : Membungkus semua pemanggilan streamlit-antd-components (sac)
          di satu tempat. Jika ingin ganti library UI, cukup ubah file ini.
Input   : Parameter konfigurasi komponen (judul, ikon, daftar item, dll).
Output  : Komponen UI yang dirender ke halaman Streamlit.
Dipanggil oleh : app.py (menu navigasi), semua file views/

CATATAN: Semua komponen sac hanya untuk navigasi dan elemen tampilan.
         Tabel, form, grafik tetap pakai komponen native Streamlit.
"""

import streamlit as st
import streamlit_antd_components as sac
from theme import NAMA_PERUSAHAAN, NAMA_APLIKASI, WARNA_PRIMER


# ---------------------------------------------------------------
# NAVIGASI SIDEBAR (sac.menu)
# ---------------------------------------------------------------
def render_menu_sidebar() -> str | None:
    """
    Menampilkan menu navigasi bergaya Ant Design di sidebar.
    Mengembalikan nama halaman yang dipilih user (string).

    Struktur menu mengikuti urutan siklus akuntansi dari brief.
    """
    with st.sidebar:
        # Logo / nama aplikasi
        st.subheader(f"🌶️ {NAMA_APLIKASI}")
        st.caption(NAMA_PERUSAHAAN)
        st.divider()

        # Menu navigasi dengan sac.menu
        # Grup menu mengikuti alur siklus akuntansi
        pilihan = sac.menu(
            items=[
                # --- Grup 1: Beranda ---
                sac.MenuItem("Dashboard", icon="speedometer2"),

                # --- Grup 2: Setup ---
                sac.MenuItem("Master Data", icon="database", children=[
                    sac.MenuItem("Bagan Akun (COA)", icon="list-ul"),
                    sac.MenuItem("Pelanggan & Supplier", icon="people"),
                    sac.MenuItem("Item Persediaan", icon="box-seam"),
                    sac.MenuItem("Pekerja", icon="person-badge"),
                    sac.MenuItem("Aset Tetap", icon="building"),
                    sac.MenuItem("Blok Lahan", icon="geo-alt"),
                    sac.MenuItem("Saldo Awal", icon="wallet2"),
                    sac.MenuItem("Periode", icon="calendar3"),
                    sac.MenuItem("Parameter", icon="gear"),
                ]),

                # --- Grup 3: Input Transaksi ---
                sac.MenuItem("Input Transaksi", icon="pencil-square"),
                sac.MenuItem("Penggajian", icon="cash-stack"),

                # --- Grup 4: Jurnal ---
                sac.MenuItem("Jurnal Umum", icon="journal-text"),
                sac.MenuItem("Jurnal Khusus", icon="journals"),

                # --- Grup 5: Buku Besar ---
                sac.MenuItem("Kartu Persediaan", icon="box-seam"),
                sac.MenuItem("Buku Besar", icon="book"),
                sac.MenuItem("BB Pembantu", icon="bookmarks"),

                # --- Grup 6: Laporan ---
                sac.MenuItem("Neraca Saldo", icon="table"),
                sac.MenuItem("Ayat Penyesuaian", icon="pencil"),
                sac.MenuItem("Neraca Lajur", icon="grid-3x3"),
                sac.MenuItem("Laporan Keuangan", icon="file-earmark-bar-graph"),
                sac.MenuItem("Jurnal Penutup", icon="lock"),

                # --- Grup 7: Utilitas ---
                sac.MenuItem("Backup & Export", icon="download"),
            ],
            format_func="title",
            open_all=False,
            indent=16,
            color=WARNA_PRIMER,
        )

    return pilihan


# ---------------------------------------------------------------
# INDIKATOR TAHAPAN SIKLUS (sac.steps) — untuk Dashboard
# ---------------------------------------------------------------
def render_steps_siklus(tahap_aktif: int = 0) -> None:
    """
    Menampilkan indikator tahapan siklus akuntansi di Dashboard.

    Args:
        tahap_aktif : Index tahap saat ini (0 = Input Transaksi).
    """
    sac.steps(
        items=[
            sac.StepsItem(title="Input Transaksi", icon="pencil-square"),
            sac.StepsItem(title="Posting BB", icon="book"),
            sac.StepsItem(title="Neraca Saldo", icon="table"),
            sac.StepsItem(title="Penyesuaian", icon="pencil"),
            sac.StepsItem(title="Lap. Keuangan", icon="file-earmark-bar-graph"),
            sac.StepsItem(title="Penutupan", icon="lock"),
        ],
        index=tahap_aktif,
        format_func="title",
        color=WARNA_PRIMER,
    )


# ---------------------------------------------------------------
# TAB JURNAL KHUSUS (sac.tabs) — untuk halaman Jurnal Khusus
# ---------------------------------------------------------------
def render_tabs_jurnal_khusus() -> str:
    """
    Menampilkan 4 tab untuk 4 jenis Jurnal Khusus.
    Mengembalikan nama tab yang dipilih.
    """
    tab_dipilih = sac.tabs(
        items=[
            sac.TabsItem(label="Jurnal Penjualan", icon="cart-check"),
            sac.TabsItem(label="Jurnal Pembelian", icon="cart-plus"),
            sac.TabsItem(label="Jurnal Penerimaan Kas", icon="cash-coin"),
            sac.TabsItem(label="Jurnal Pengeluaran Kas", icon="cash-stack"),
        ],
        color=WARNA_PRIMER,
        return_index=False,
    )
    return tab_dipilih


# ---------------------------------------------------------------
# FILTER SEGMENTED (sac.segmented) — untuk filter periode/komoditas
# ---------------------------------------------------------------
def render_filter_komoditas(key: str = "filter_komoditas") -> str:
    """
    Menampilkan filter komoditas bergaya segmented button.
    Mengembalikan komoditas yang dipilih.
    """
    return sac.segmented(
        items=[
            sac.SegmentedItem(label="Semua", icon="grid"),
            sac.SegmentedItem(label="Cabai", icon="fire"),
        ],
        label="Filter Komoditas",
        color=WARNA_PRIMER,
        key=key,
        return_index=False,
    )


# ---------------------------------------------------------------
# ALERT STATUS VALIDASI (sac.alert / sac.result)
# ---------------------------------------------------------------
def alert_jurnal_seimbang(debit: int, kredit: int) -> bool:
    """
    Menampilkan alert status apakah jurnal seimbang (Debit == Kredit).

    Returns:
        True jika seimbang, False jika tidak.
    """
    seimbang = debit == kredit
    if seimbang:
        sac.alert(
            label="✅ Jurnal Seimbang",
            description=f"Total Debit = Total Kredit = Rp{debit:,}".replace(",", "."),
            color="success",
            icon=True,
        )
    else:
        sac.alert(
            label="❌ Jurnal Tidak Seimbang!",
            description=(
                f"Debit: Rp{debit:,} | Kredit: Rp{kredit:,} | "
                f"Selisih: Rp{abs(debit - kredit):,}"
            ).replace(",", "."),
            color="error",
            icon=True,
        )
    return seimbang


def alert_neraca_seimbang(aset: int, liabilitas_ekuitas: int) -> bool:
    """
    Menampilkan alert apakah neraca seimbang (Aset = Liabilitas + Ekuitas).
    """
    seimbang = aset == liabilitas_ekuitas
    if seimbang:
        sac.alert(
            label="✅ Neraca Seimbang",
            description=f"Aset = Liabilitas + Ekuitas = Rp{aset:,}".replace(",", "."),
            color="success",
            icon=True,
        )
    else:
        sac.alert(
            label="❌ Neraca Tidak Seimbang!",
            description=(
                f"Aset: Rp{aset:,} | Liabilitas+Ekuitas: Rp{liabilitas_ekuitas:,}"
            ).replace(",", "."),
            color="error",
            icon=True,
        )
    return seimbang


def tag_status(status: str) -> None:
    """
    Menampilkan tag berwarna untuk status (mis. lunas, belum_lunas, buka, tutup).
    """
    peta_warna = {
        "lunas": "green",
        "belum_lunas": "red",
        "sebagian": "orange",
        "buka": "blue",
        "tutup": "gray",
        "aktif": "green",
        "nonaktif": "gray",
    }
    peta_label = {
        "lunas": "✅ Lunas",
        "belum_lunas": "⏳ Belum Lunas",
        "sebagian": "🔶 Sebagian",
        "buka": "🔓 Buka",
        "tutup": "🔒 Tutup",
        "aktif": "✅ Aktif",
        "nonaktif": "⛔ Nonaktif",
    }
    warna = peta_warna.get(status, "default")
    label = peta_label.get(status, status)
    sac.tags([sac.Tag(label=label, color=warna)])


def divider_dengan_judul(judul: str, icon: str = "chevron-right") -> None:
    """Menampilkan divider dengan judul bergaya Ant Design."""
    sac.divider(label=judul, icon=icon, align="left", color="gray")


# ---------------------------------------------------------------
# PEMILIH PERIODE FLEKSIBEL & KALENDER (Bulan Ini, Bulan Lalu, dll)
# ---------------------------------------------------------------
def selector_periode(
    label: str = "📅 Pilih Periode",
    key: str = "selector_periode",
    hanya_buka: bool = False,
    izinkan_semua: bool = False,
    tampilkan_kalender: bool = True,
    help: str = "Pilih periode akuntansi bulanan",
) -> int | None:
    """
    Komponen pemilih periode terpadu untuk seluruh menu dalam sistem.
    Mendukung:
    - Pilihan dropdown lengkap (Tahun Ini, Tahun Lalu, Bulan Ini, Bulan Lalu)
    - Fitur Kalender / Pemilih Bulan & Tahun manual (auto-generate jika belum ada)
    - Tombol shortcut preset cepat (Bulan Ini, Bulan Lalu, Observasi Okt 2026)
    - Sinkronisasi session state antar halaman
    """
    import services.period_service as ps
    from datetime import date

    # Ambil semua periode dari database
    daftar_periode = ps.ambil_semua_periode(hanya_buka=hanya_buka, urutan_terbaru=True)
    if not daftar_periode:
        st.warning("Belum ada periode yang tersedia.")
        return None

    today = date.today()
    bln_ini = today.month
    thn_ini = today.year
    bln_lalu = 12 if bln_ini == 1 else bln_ini - 1
    thn_lalu = thn_ini - 1 if bln_ini == 1 else thn_ini

    # Bangun daftar opsi untuk selectbox
    opsi_list = []
    if izinkan_semua:
        opsi_list.append({"id": None, "label": "🌐 Semua Periode (Semua Transaksi)"})

    for p in daftar_periode:
        nama = p["nama_bulan"]
        status_label = "🔓 Buka" if p["status"] == "buka" else "🔒 Tutup"
        tag_khusus = ""
        if p["tahun"] == 2026 and p["bulan"] == 10:
            tag_khusus = " ⭐ (Data Observasi)"
        elif p["tahun"] == thn_ini and p["bulan"] == bln_ini:
            tag_khusus = " ⚡ (Bulan Ini)"
        elif p["tahun"] == thn_lalu and p["bulan"] == bln_lalu:
            tag_khusus = " ⏪ (Bulan Lalu)"
        elif p["tahun"] == thn_ini - 1:
            tag_khusus = " 🗓️ (Tahun Lalu)"

        opsi_list.append({
            "id": p["id"],
            "tahun": p["tahun"],
            "bulan": p["bulan"],
            "label": f"{nama} [{status_label}]{tag_khusus}",
        })

    # Tentukan index default yang terpilih
    state_key = f"{key}_active_id"
    default_id = st.session_state.get(state_key, st.session_state.get("periode_global_id", 1))

    # Cari index yang cocok
    default_idx = 0
    for idx, item in enumerate(opsi_list):
        if item["id"] == default_id:
            default_idx = idx
            break

    # 1. Dropdown Utama Pemilihan Periode
    pilihan_idx = st.selectbox(
        label=label,
        options=range(len(opsi_list)),
        index=default_idx,
        format_func=lambda i: opsi_list[i]["label"],
        key=f"{key}_sb",
        help=help,
    )

    periode_terpilih = opsi_list[pilihan_idx]
    terpilih_id = periode_terpilih["id"]

    # Update session state jika berubah dari selectbox
    if terpilih_id is not None:
        st.session_state[state_key] = terpilih_id
        st.session_state["periode_global_id"] = terpilih_id

    # 2. Panel Fitur Kalender & Shortcut Cepat
    if tampilkan_kalender:
        with st.popover("🗓️ Buka Kalender & Pilihan Cepat", use_container_width=True):
            st.caption("Pilih periode secara instan atau tentukan bulan dan tahun kalender:")

            # Baris Shortcut Preset Cepat
            k1, k2, k3, k4 = st.columns(4)
            with k1:
                if st.button("⚡ Bulan Ini", key=f"{key}_btn_bln_ini", use_container_width=True):
                    p_curr = ps.ambil_atau_buat_periode(thn_ini, bln_ini)
                    st.session_state[state_key] = p_curr["id"]
                    st.session_state["periode_global_id"] = p_curr["id"]
                    st.rerun()
            with k2:
                if st.button("⏪ Bulan Lalu", key=f"{key}_btn_bln_lalu", use_container_width=True):
                    p_prev = ps.ambil_atau_buat_periode(thn_lalu, bln_lalu)
                    st.session_state[state_key] = p_prev["id"]
                    st.session_state["periode_global_id"] = p_prev["id"]
                    st.rerun()
            with k3:
                if st.button("🌾 Oktober 2026", key=f"{key}_btn_okt_26", use_container_width=True):
                    p_obs = ps.ambil_atau_buat_periode(2026, 10)
                    st.session_state[state_key] = p_obs["id"]
                    st.session_state["periode_global_id"] = p_obs["id"]
                    st.rerun()
            with k4:
                if st.button("🗓️ Tahun Lalu (2025)", key=f"{key}_btn_thn_lalu", use_container_width=True):
                    p_thn_lalu = ps.ambil_atau_buat_periode(thn_ini - 1, bln_ini)
                    st.session_state[state_key] = p_thn_lalu["id"]
                    st.session_state["periode_global_id"] = p_thn_lalu["id"]
                    st.rerun()

            st.markdown("---")
            # Pemilih Kalender Manual (Bulan & Tahun)
            st.markdown("**📅 Pemilih Bulan & Tahun Kalender Manual:**")
            kol_m1, kol_m2, kol_m3 = st.columns([2, 2, 2])
            with kol_m1:
                bulan_pilih = st.selectbox(
                    "Bulan Kalender",
                    options=range(1, 13),
                    index=bln_ini - 1,
                    format_func=lambda b: f"{b:02d} - {ps.NAMA_BULAN[b-1]}",
                    key=f"{key}_cal_bulan",
                )
            with kol_m2:
                tahun_pilih = st.number_input(
                    "Tahun Kalender",
                    min_value=2020,
                    max_value=2035,
                    value=thn_ini,
                    step=1,
                    key=f"{key}_cal_tahun",
                )
            with kol_m3:
                st.write("") # spacer
                st.write("")
                if st.button("🎯 Terapkan Periode", key=f"{key}_cal_terapkan", type="primary", use_container_width=True):
                    p_manual = ps.ambil_atau_buat_periode(int(tahun_pilih), int(bulan_pilih))
                    st.session_state[state_key] = p_manual["id"]
                    st.session_state["periode_global_id"] = p_manual["id"]
                    st.rerun()

    return terpilih_id

