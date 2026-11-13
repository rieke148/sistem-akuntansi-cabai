"""
views/01_master_data.py
------------------------
Tujuan  : Halaman pengelolaan Master Data — CRUD lengkap semua entitas.
          10 tab: COA | Pelanggan | Supplier | Item | Pekerja |
                  Aset Tetap | Blok Lahan | Saldo Awal | Periode | Parameter
Input   : Form input dari user (st.form).
Output  : Data tersimpan/diubah/dinonaktifkan di database.
Dipanggil oleh : app.py (st.navigation)

CARA BACA FILE INI:
  1. tampilkan()       → fungsi utama, routing ke 10 tab
  2. _tab_xxx()        → fungsi per tab
  3. _form_tambah_xxx() / _form_edit_xxx() → sub-form dalam expander

ATURAN:
  Semua logika DB ada di services/master_data_service.py.
  File ini hanya tampilan + memanggil service.
"""

import streamlit as st
import pandas as pd
from datetime import date

import streamlit_antd_components as sac

from services import master_data_service as svc
from utils.formatting import format_rupiah, format_tanggal, nama_bulan_tahun
from utils.ui_components import divider_dengan_judul, selector_periode
from theme import WARNA_PRIMER


# ================================================================
# FUNGSI UTAMA
# ================================================================
def tampilkan() -> None:
    """Fungsi utama halaman Master Data. Dipanggil oleh app.py."""
    st.title("🗄️ Master Data")
    st.caption("Kelola semua data referensi: akun, pelanggan, supplier, pekerja, dan aset.")

    tab_dipilih = sac.tabs(
        items=[
            sac.TabsItem(label="Bagan Akun", icon="list-ul"),
            sac.TabsItem(label="Pelanggan", icon="person-check"),
            sac.TabsItem(label="Supplier", icon="truck"),
            sac.TabsItem(label="Item Persediaan", icon="box-seam"),
            sac.TabsItem(label="Pekerja", icon="person-badge"),
            sac.TabsItem(label="Aset Tetap", icon="building"),
            sac.TabsItem(label="Blok Lahan", icon="geo-alt"),
            sac.TabsItem(label="Saldo Awal", icon="wallet2"),
            sac.TabsItem(label="Periode", icon="calendar3"),
            sac.TabsItem(label="Parameter", icon="gear"),
        ],
        color=WARNA_PRIMER,
        return_index=False,
    )

    # Routing ke sub-fungsi per tab
    routing = {
        "Bagan Akun": _tab_bagan_akun,
        "Pelanggan": _tab_pelanggan,
        "Supplier": _tab_supplier,
        "Item Persediaan": _tab_item,
        "Pekerja": _tab_pekerja,
        "Aset Tetap": _tab_aset_tetap,
        "Blok Lahan": _tab_blok_lahan,
        "Saldo Awal": _tab_saldo_awal,
        "Periode": _tab_periode,
        "Parameter": _tab_parameter,
    }
    if tab_dipilih in routing:
        routing[tab_dipilih]()


# ================================================================
# TAB 1 — BAGAN AKUN (COA)
# ================================================================
def _tab_bagan_akun() -> None:
    """
    Menampilkan Bagan Akun lengkap.
    Fitur: filter kategori, tambah akun baru, edit akun.
    """
    divider_dengan_judul("Bagan Akun (Chart of Accounts)", "list-ul")

    # --- Filter ---
    opsi_kategori = ["Semua"] + svc.KATEGORI_AKUN
    kategori_filter = st.selectbox("Filter Kategori", opsi_kategori, key="filter_kategori_akun")
    filter_val = None if kategori_filter == "Semua" else kategori_filter

    # --- Tabel ---
    df = svc.ambil_semua_akun(kategori=filter_val)
    df_tampil = df[["kode_akun", "nama_akun", "kategori", "saldo_normal", "is_kontra", "aktif"]].copy()
    df_tampil["is_kontra"] = df_tampil["is_kontra"].map({1: "Ya", 0: "-"})
    df_tampil["aktif"] = df_tampil["aktif"].map({1: "Aktif", 0: "Nonaktif"})
    df_tampil.columns = ["Kode Akun", "Nama Akun", "Kategori", "Saldo Normal", "Kontra?", "Status"]

    st.dataframe(df_tampil, use_container_width=True, hide_index=True)
    st.caption(f"Total: {len(df_tampil)} akun")

    kol1, kol2 = st.columns(2)

    # --- Form Tambah ---
    with kol1:
        with st.expander("➕ Tambah Akun Baru"):
            _form_tambah_akun()

    # --- Form Edit ---
    with kol2:
        with st.expander("✏️ Edit Akun"):
            _form_edit_akun(df)

    # --- Hapus permanen ---
    with st.expander("🗑️ Hapus Akun"):
        st.warning(
            "Akun hanya dapat dihapus permanen jika belum digunakan pada jurnal, "
            "saldo awal, item persediaan, atau aset tetap. Akun yang sudah "
            "digunakan harus dinonaktifkan melalui form Edit Akun agar histori "
            "pencatatan tetap terjaga."
        )

        if df.empty:
            st.info("Tidak ada akun pada filter yang dipilih.")
        else:
            pilihan_hapus = {
                f"{r['kode_akun']} - {r['nama_akun']} ({'Aktif' if r['aktif'] else 'Nonaktif'})": int(r["id"])
                for _, r in df.iterrows()
            }
            akun_hapus_label = st.selectbox(
                "Pilih Akun yang Akan Dihapus",
                list(pilihan_hapus.keys()),
                key="hapus_akun_sel",
            )
            akun_hapus_id = pilihan_hapus[akun_hapus_label]
            akun_hapus = df[df["id"] == akun_hapus_id].iloc[0]

            st.caption(
                f"Akun terpilih: **{akun_hapus['kode_akun']} — {akun_hapus['nama_akun']}**. "
                "Penghapusan permanen tidak dapat dibatalkan."
            )
            konfirmasi_hapus = st.checkbox(
                "Saya yakin ingin menghapus akun ini secara permanen.",
                key=f"konfirmasi_hapus_akun_{akun_hapus_id}",
            )

            if st.button(
                "🗑️ Hapus Akun Permanen",
                type="secondary",
                use_container_width=True,
                disabled=not konfirmasi_hapus,
                key="btn_hapus_akun",
            ):
                try:
                    svc.hapus_akun(akun_hapus_id)
                    st.success(
                        f"Akun '{akun_hapus['kode_akun']} - {akun_hapus['nama_akun']}' "
                        "berhasil dihapus."
                    )
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"Gagal menghapus akun: {e}")


def _form_tambah_akun() -> None:
    """Form tambah akun baru ke COA."""
    with st.form("form_tambah_akun", clear_on_submit=True):
        kode = st.text_input(
            "Kode Akun *",
            placeholder="Contoh: 1101",
            help="Kode unik: 1xxx=Aset, 2xxx=Liabilitas, 3xxx=Ekuitas, 4xxx=Pendapatan, 5xxx=Beban Produksi, 6xxx=Beban Operasional"
        )
        nama = st.text_input("Nama Akun *", placeholder="Contoh: Kas")
        kategori = st.selectbox("Kategori *", svc.KATEGORI_AKUN)
        saldo_normal = st.selectbox("Saldo Normal *", svc.SALDO_NORMAL)
        is_kontra = st.checkbox("Akun Kontra?", help="Centang untuk akun seperti Akumulasi Penyusutan")

        if st.form_submit_button("💾 Simpan Akun", use_container_width=True):
            try:
                svc.tambah_akun(kode, nama, kategori, saldo_normal, is_kontra)
                st.success(f"Akun '{kode} - {nama}' berhasil ditambahkan!")
                st.rerun()
            except Exception as e:
                st.error(f"Gagal: {e}")


def _form_edit_akun(df: pd.DataFrame) -> None:
    """Form edit akun yang sudah ada."""
    # Buat pilihan akun dari DataFrame
    pilihan_akun = {f"{r['kode_akun']} - {r['nama_akun']}": r["id"]
                    for _, r in df.iterrows()}
    akun_dipilih = st.selectbox("Pilih Akun", list(pilihan_akun.keys()), key="edit_akun_sel")
    if not akun_dipilih:
        return

    akun_id = pilihan_akun[akun_dipilih]
    baris = df[df["id"] == akun_id].iloc[0]

    with st.form("form_edit_akun"):
        st.caption(f"Kode Akun: **{baris['kode_akun']}** (tidak bisa diubah)")
        nama_baru = st.text_input("Nama Akun *", value=baris["nama_akun"])
        kat_baru = st.selectbox("Kategori *", svc.KATEGORI_AKUN,
                                index=svc.KATEGORI_AKUN.index(baris["kategori"]))
        saldo_baru = st.selectbox("Saldo Normal *", svc.SALDO_NORMAL,
                                  index=svc.SALDO_NORMAL.index(baris["saldo_normal"]))
        kontra_baru = st.checkbox("Akun Kontra?", value=bool(baris["is_kontra"]))
        aktif_baru = st.checkbox("Aktif?", value=bool(baris["aktif"]))

        if st.form_submit_button("💾 Simpan Perubahan", use_container_width=True):
            try:
                svc.ubah_akun(akun_id, nama_baru, kat_baru, saldo_baru, kontra_baru, aktif_baru)
                st.success("Akun berhasil diperbarui!")
                st.rerun()
            except Exception as e:
                st.error(f"Gagal: {e}")


# ================================================================
# TAB 2 — PELANGGAN
# ================================================================
def _tab_pelanggan() -> None:
    """CRUD Pelanggan."""
    divider_dengan_judul("Data Pelanggan", "person-check")

    df = svc.ambil_semua_pelanggan()
    df_tampil = df[["nama", "tipe", "telepon", "alamat", "aktif"]].copy()
    df_tampil["aktif"] = df_tampil["aktif"].map({1: "Aktif", 0: "Nonaktif"})
    df_tampil.columns = ["Nama", "Tipe", "Telepon", "Alamat", "Status"]
    st.dataframe(df_tampil, use_container_width=True, hide_index=True)
    st.caption(f"{len(df)} pelanggan terdaftar")

    kol1, kol2 = st.columns(2)
    with kol1:
        with st.expander("➕ Tambah Pelanggan"):
            _form_tambah_pelanggan()
    with kol2:
        with st.expander("✏️ Edit Pelanggan"):
            _form_edit_pelanggan(df)


def _form_tambah_pelanggan() -> None:
    with st.form("form_tambah_pelanggan", clear_on_submit=True):
        nama = st.text_input("Nama Pelanggan *")
        tipe = st.selectbox("Tipe", svc.TIPE_PELANGGAN)
        telepon = st.text_input("Telepon")
        alamat = st.text_area("Alamat", height=80)
        if st.form_submit_button("💾 Simpan", use_container_width=True):
            try:
                svc.tambah_pelanggan(nama, tipe, telepon, alamat)
                st.success(f"Pelanggan '{nama}' berhasil ditambahkan!")
                st.rerun()
            except Exception as e:
                st.error(f"Gagal: {e}")


def _form_edit_pelanggan(df: pd.DataFrame) -> None:
    pilihan = {r["nama"]: r["id"] for _, r in df.iterrows()}
    dipilih = st.selectbox("Pilih Pelanggan", list(pilihan.keys()), key="edit_pelanggan_sel")
    if not dipilih:
        return
    baris = df[df["id"] == pilihan[dipilih]].iloc[0]
    with st.form("form_edit_pelanggan"):
        nama_b = st.text_input("Nama *", value=baris["nama"])
        tipe_b = st.selectbox("Tipe", svc.TIPE_PELANGGAN,
                              index=svc.TIPE_PELANGGAN.index(baris["tipe"]))
        telp_b = st.text_input("Telepon", value=baris["telepon"] or "")
        adr_b = st.text_area("Alamat", value=baris["alamat"] or "", height=80)
        aktif_b = st.checkbox("Aktif?", value=bool(baris["aktif"]))
        if st.form_submit_button("💾 Simpan Perubahan", use_container_width=True):
            try:
                svc.ubah_pelanggan(baris["id"], nama_b, tipe_b, telp_b, adr_b, aktif_b)
                st.success("Data pelanggan berhasil diperbarui!")
                st.rerun()
            except Exception as e:
                st.error(f"Gagal: {e}")


# ================================================================
# TAB 3 — SUPPLIER
# ================================================================
def _tab_supplier() -> None:
    """CRUD Supplier."""
    divider_dengan_judul("Data Supplier", "truck")

    df = svc.ambil_semua_supplier()
    df_tampil = df[["nama", "telepon", "alamat", "aktif"]].copy()
    df_tampil["aktif"] = df_tampil["aktif"].map({1: "Aktif", 0: "Nonaktif"})
    df_tampil.columns = ["Nama", "Telepon", "Alamat", "Status"]
    st.dataframe(df_tampil, use_container_width=True, hide_index=True)

    kol1, kol2 = st.columns(2)
    with kol1:
        with st.expander("➕ Tambah Supplier"):
            with st.form("form_tambah_supplier", clear_on_submit=True):
                nama = st.text_input("Nama Supplier *")
                telepon = st.text_input("Telepon")
                alamat = st.text_area("Alamat", height=80)
                if st.form_submit_button("💾 Simpan", use_container_width=True):
                    try:
                        svc.tambah_supplier(nama, telepon, alamat)
                        st.success(f"Supplier '{nama}' berhasil ditambahkan!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Gagal: {e}")

    with kol2:
        with st.expander("✏️ Edit Supplier"):
            pilihan = {r["nama"]: r["id"] for _, r in df.iterrows()}
            dipilih = st.selectbox("Pilih Supplier", list(pilihan.keys()), key="edit_sup_sel")
            if dipilih:
                baris = df[df["id"] == pilihan[dipilih]].iloc[0]
                with st.form("form_edit_supplier"):
                    nama_b = st.text_input("Nama *", value=baris["nama"])
                    telp_b = st.text_input("Telepon", value=baris["telepon"] or "")
                    adr_b = st.text_area("Alamat", value=baris["alamat"] or "", height=80)
                    aktif_b = st.checkbox("Aktif?", value=bool(baris["aktif"]))
                    if st.form_submit_button("💾 Simpan Perubahan", use_container_width=True):
                        try:
                            svc.ubah_supplier(baris["id"], nama_b, telp_b, adr_b, aktif_b)
                            st.success("Data supplier berhasil diperbarui!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Gagal: {e}")


# ================================================================
# TAB 4 — ITEM PERSEDIAAN
# ================================================================
def _tab_item() -> None:
    """CRUD Item Persediaan."""
    divider_dengan_judul("Item Persediaan & Hasil Panen", "box-seam")
    st.caption("Item bisa berupa bahan produksi (pupuk, bibit, dll) atau hasil panen (cabai kg).")

    df = svc.ambil_semua_item()
    df_tampil = df[["kode_item", "nama_item", "satuan", "tipe", "komoditas", "akun_persediaan", "aktif"]].copy()
    df_tampil["aktif"] = df_tampil["aktif"].map({1: "Aktif", 0: "Nonaktif"})
    df_tampil.columns = ["Kode", "Nama Item", "Satuan", "Tipe", "Komoditas", "Akun Persediaan", "Status"]
    st.dataframe(df_tampil, use_container_width=True, hide_index=True)

    # Ambil daftar akun persediaan untuk dropdown
    from database.connection import get_connection
    koneksi = get_connection()
    akun_persediaan_rows = koneksi.execute(
        "SELECT id, kode_akun, nama_akun FROM accounts WHERE kategori='Aset' AND aktif=1 ORDER BY kode_akun"
    ).fetchall()
    koneksi.close()
    opsi_akun = {"(Tidak ada)": None}
    opsi_akun.update({f"{r['kode_akun']} - {r['nama_akun']}": r["id"] for r in akun_persediaan_rows})

    kol1, kol2 = st.columns(2)
    with kol1:
        with st.expander("➕ Tambah Item"):
            with st.form("form_tambah_item", clear_on_submit=True):
                kode = st.text_input("Kode Item *", placeholder="Contoh: BHN-007")
                nama = st.text_input("Nama Item *")
                satuan = st.text_input("Satuan *", placeholder="Contoh: kg, karung, batang")
                tipe = st.selectbox("Tipe", svc.TIPE_ITEM,
                                    help="bahan=input produksi, hasil_panen=output")
                komoditas = st.selectbox("Komoditas", svc.KOMODITAS_ITEM)
                akun_dipilih = st.selectbox("Akun Persediaan", list(opsi_akun.keys()))
                akun_id = opsi_akun[akun_dipilih]
                if st.form_submit_button("💾 Simpan", use_container_width=True):
                    try:
                        svc.tambah_item(kode, nama, satuan, tipe, komoditas, akun_id)
                        st.success(f"Item '{nama}' berhasil ditambahkan!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Gagal: {e}")

    with kol2:
        with st.expander("✏️ Edit Item"):
            pilihan = {f"{r['kode_item']} - {r['nama_item']}": r["id"] for _, r in df.iterrows()}
            dipilih = st.selectbox("Pilih Item", list(pilihan.keys()), key="edit_item_sel")
            if dipilih:
                baris = df[df["id"] == pilihan[dipilih]].iloc[0]
                with st.form("form_edit_item"):
                    st.caption(f"Kode: **{baris['kode_item']}** (tidak bisa diubah)")
                    nama_b = st.text_input("Nama Item *", value=baris["nama_item"])
                    sat_b = st.text_input("Satuan *", value=baris["satuan"])
                    tipe_b = st.selectbox("Tipe", svc.TIPE_ITEM,
                                          index=svc.TIPE_ITEM.index(baris["tipe"]))
                    kom_b = st.selectbox("Komoditas", svc.KOMODITAS_ITEM,
                                         index=svc.KOMODITAS_ITEM.index(baris["komoditas"]))
                    akun_key = next((k for k, v in opsi_akun.items()
                                     if v == baris.get("account_id")), "(Tidak ada)")
                    akun_b = st.selectbox("Akun Persediaan", list(opsi_akun.keys()),
                                          index=list(opsi_akun.keys()).index(akun_key))
                    aktif_b = st.checkbox("Aktif?", value=bool(baris["aktif"]))
                    if st.form_submit_button("💾 Simpan Perubahan", use_container_width=True):
                        try:
                            svc.ubah_item(baris["id"], nama_b, sat_b, tipe_b, kom_b, opsi_akun[akun_b], aktif_b)
                            st.success("Item berhasil diperbarui!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Gagal: {e}")

    # --- Hapus permanen ---
    with st.expander("🗑️ Hapus Item"):
        st.warning(
            "Penghapusan permanen hanya tersedia untuk item yang belum pernah "
            "memiliki pergerakan stok. Item yang sudah memiliki histori harus "
            "dinonaktifkan melalui menu Edit Item agar kartu persediaan tetap utuh."
        )

        if df.empty:
            st.info("Belum ada item yang dapat dipilih.")
        else:
            pilihan_hapus = {
                f"{r['kode_item']} - {r['nama_item']} ({'Aktif' if r['aktif'] else 'Nonaktif'})": int(r["id"])
                for _, r in df.iterrows()
            }
            item_hapus_label = st.selectbox(
                "Pilih Item yang Akan Dihapus",
                list(pilihan_hapus.keys()),
                key="hapus_item_sel",
            )
            item_hapus_id = pilihan_hapus[item_hapus_label]
            item_hapus = df[df["id"] == item_hapus_id].iloc[0]

            st.caption(
                f"Item terpilih: **{item_hapus['kode_item']} — {item_hapus['nama_item']}**. "
                "Tindakan ini tidak dapat dibatalkan."
            )
            konfirmasi_hapus = st.checkbox(
                "Saya yakin ingin menghapus item ini secara permanen.",
                key=f"konfirmasi_hapus_item_{item_hapus_id}",
            )

            if st.button(
                "🗑️ Hapus Item Permanen",
                type="secondary",
                use_container_width=True,
                disabled=not konfirmasi_hapus,
                key="btn_hapus_item",
            ):
                try:
                    svc.hapus_item(item_hapus_id)
                    st.success(f"Item '{item_hapus['nama_item']}' berhasil dihapus.")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"Gagal menghapus item: {e}")


# ================================================================
# TAB 5 — PEKERJA
# ================================================================
def _tab_pekerja() -> None:
    """CRUD Pekerja. Upah harian adalah INPUT USER — bisa diubah."""
    divider_dengan_judul("Data Pekerja", "person-badge")

    df = svc.ambil_semua_pekerja()
    df_tampil = df[["nama", "tipe_pekerja", "upah_harian", "komoditas", "aktif"]].copy()
    df_tampil["upah_harian"] = df_tampil["upah_harian"].apply(format_rupiah)
    df_tampil["aktif"] = df_tampil["aktif"].map({1: "Aktif", 0: "Nonaktif"})
    df_tampil.columns = ["Nama", "Tipe", "Upah Harian", "Komoditas", "Status"]
    st.dataframe(df_tampil, use_container_width=True, hide_index=True)

    # Info upah dari parameter
    upah_tetap = int(svc.ambil_nilai_parameter("upah_tetap_harian", "90000"))
    upah_tambahan = int(svc.ambil_nilai_parameter("upah_tambahan_harian", "120000"))
    st.info(
        f"Tarif upah saat ini: **Pekerja Tetap = {format_rupiah(upah_tetap)}/hari** | "
        f"**Tenaga Tambahan = {format_rupiah(upah_tambahan)}/hari**  "
        f"(ubah di tab Parameter)"
    )

    kol1, kol2 = st.columns(2)
    with kol1:
        with st.expander("➕ Tambah Pekerja"):
            with st.form("form_tambah_pekerja", clear_on_submit=True):
                nama = st.text_input("Nama Pekerja *")
                tipe = st.selectbox("Tipe Pekerja", svc.TIPE_PEKERJA,
                                    help="tetap=harian tetap, tambahan=cangkul/olah tanah")
                # Isi otomatis sesuai tipe, tapi bisa diubah
                upah_default = upah_tetap if tipe == "tetap" else upah_tambahan
                upah = st.number_input("Upah Harian (Rp) *", min_value=1,
                                       value=upah_default, step=5000)
                komoditas = st.selectbox("Komoditas", svc.KOMODITAS_ITEM)
                if st.form_submit_button("💾 Simpan", use_container_width=True):
                    try:
                        svc.tambah_pekerja(nama, tipe, upah, komoditas)
                        st.success(f"Pekerja '{nama}' berhasil ditambahkan!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Gagal: {e}")

    with kol2:
        with st.expander("✏️ Edit Pekerja"):
            pilihan = {r["nama"]: r["id"] for _, r in df.iterrows()}
            dipilih = st.selectbox("Pilih Pekerja", list(pilihan.keys()), key="edit_pek_sel")
            if dipilih:
                baris = df[df["id"] == pilihan[dipilih]].iloc[0]
                with st.form("form_edit_pekerja"):
                    nama_b = st.text_input("Nama *", value=baris["nama"])
                    tipe_b = st.selectbox("Tipe", svc.TIPE_PEKERJA,
                                          index=svc.TIPE_PEKERJA.index(baris["tipe_pekerja"]))
                    upah_b = st.number_input("Upah Harian (Rp) *",
                                             min_value=1, value=int(baris["upah_harian"]), step=5000)
                    kom_b = st.selectbox("Komoditas", svc.KOMODITAS_ITEM,
                                         index=svc.KOMODITAS_ITEM.index(baris["komoditas"]))
                    aktif_b = st.checkbox("Aktif?", value=bool(baris["aktif"]))
                    if st.form_submit_button("💾 Simpan Perubahan", use_container_width=True):
                        try:
                            svc.ubah_pekerja(baris["id"], nama_b, tipe_b, upah_b, kom_b, aktif_b)
                            st.success("Data pekerja berhasil diperbarui!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Gagal: {e}")


# ================================================================
# TAB 6 — ASET TETAP
# ================================================================
def _tab_aset_tetap() -> None:
    """
    CRUD Aset Tetap.
    Penting: umur ekonomis, nilai residu, jumlah unit adalah INPUT USER.
    Preview penyusutan ditampilkan otomatis saat user isi form.
    """
    divider_dengan_judul("Aset Tetap", "building")

    st.warning(
        "⚠️ Verifikasi jumlah unit dan tanggal perolehan dengan data asli "
        "sebelum menghitung penyusutan!"
    )

    df = svc.ambil_semua_aset_tetap()

    # Tampilkan tabel ringkas
    df_tampil = df[[
        "kode_aset", "nama_aset", "kategori_aset",
        "harga_perolehan", "nilai_residu", "umur_ekonomis_tahun",
        "jumlah_unit", "is_disusutkan", "aktif"
    ]].copy()
    df_tampil["harga_perolehan"] = df_tampil["harga_perolehan"].apply(format_rupiah)
    df_tampil["nilai_residu"] = df_tampil["nilai_residu"].apply(format_rupiah)
    df_tampil["is_disusutkan"] = df_tampil["is_disusutkan"].map({1: "Ya", 0: "Tidak"})
    df_tampil["aktif"] = df_tampil["aktif"].map({1: "Aktif", 0: "Nonaktif"})
    df_tampil.columns = ["Kode", "Nama Aset", "Kategori", "Harga Perolehan",
                         "Nilai Residu", "Umur (Th)", "Unit", "Disusutkan?", "Status"]
    st.dataframe(df_tampil, use_container_width=True, hide_index=True)

    # Preview penyusutan semua aset
    with st.expander("📊 Preview Penyusutan Semua Aset"):
        _preview_penyusutan_semua(df)

    # Ambil akun untuk dropdown
    from database.connection import get_connection
    koneksi = get_connection()
    akun_aset_rows = koneksi.execute(
        "SELECT id, kode_akun, nama_akun FROM accounts WHERE kategori='Aset' AND is_kontra=0 AND aktif=1 ORDER BY kode_akun"
    ).fetchall()
    akun_akum_rows = koneksi.execute(
        "SELECT id, kode_akun, nama_akun FROM accounts WHERE kategori='Aset' AND is_kontra=1 AND aktif=1 ORDER BY kode_akun"
    ).fetchall()
    koneksi.close()

    opsi_aset_akun = {"(Pilih akun)": None}
    opsi_aset_akun.update({f"{r['kode_akun']} - {r['nama_akun']}": r["id"] for r in akun_aset_rows})
    opsi_akum_akun = {"(Tidak ada / Tanah)": None}
    opsi_akum_akun.update({f"{r['kode_akun']} - {r['nama_akun']}": r["id"] for r in akun_akum_rows})

    kol1, kol2 = st.columns(2)
    with kol1:
        with st.expander("➕ Tambah Aset Tetap"):
            _form_tambah_aset(opsi_aset_akun, opsi_akum_akun)
    with kol2:
        with st.expander("✏️ Edit Aset Tetap"):
            _form_edit_aset(df, opsi_aset_akun, opsi_akum_akun)


def _preview_penyusutan_semua(df: pd.DataFrame) -> None:
    """Tampilkan tabel preview penyusutan semua aset yang aktif."""
    baris_list = []
    for _, r in df[df["is_disusutkan"] == 1].iterrows():
        harga = int(r["harga_perolehan"])
        residu = int(r["nilai_residu"])
        umur = int(r["umur_ekonomis_tahun"])
        unit = int(r["jumlah_unit"])
        preview = svc.hitung_penyusutan_preview(harga, residu, umur, unit)
        baris_list.append({
            "Nama Aset": r["nama_aset"],
            "Harga Total": format_rupiah(harga * unit),
            "Residu Total": format_rupiah(residu * unit),
            "Dasar": format_rupiah(preview["dasar_penyusutan"]),
            "Umur (Th)": umur,
            "Penyusutan/Bulan": format_rupiah(preview["penyusutan_per_bulan"]),
            "Penyusutan/Tahun": format_rupiah(preview["penyusutan_per_tahun"]),
        })
    if baris_list:
        df_prev = pd.DataFrame(baris_list)
        st.dataframe(df_prev, use_container_width=True, hide_index=True)
        total_bln = sum(svc.hitung_penyusutan_preview(
            int(r["harga_perolehan"]), int(r["nilai_residu"]),
            int(r["umur_ekonomis_tahun"]), int(r["jumlah_unit"])
        )["penyusutan_per_bulan"] for _, r in df[df["is_disusutkan"] == 1].iterrows())
        st.metric("Total Penyusutan per Bulan", format_rupiah(total_bln))
    else:
        st.info("Belum ada aset yang perlu disusutkan.")


def _form_tambah_aset(opsi_aset_akun: dict, opsi_akum_akun: dict) -> None:
    """Form tambah aset tetap baru dengan preview penyusutan real-time."""
    with st.form("form_tambah_aset", clear_on_submit=True):
        kode = st.text_input("Kode Aset *", placeholder="Contoh: AT-013")
        nama = st.text_input("Nama Aset *")
        kategori = st.selectbox("Kategori *", svc.KATEGORI_ASET)
        tgl = st.date_input("Tanggal Perolehan *", value=date.today())
        unit = st.number_input("Jumlah Unit *", min_value=1, value=1)
        harga = st.number_input("Harga Perolehan per Unit (Rp) *",
                                min_value=1, value=1_000_000, step=100_000)
        residu = st.number_input("Nilai Residu per Unit (Rp)",
                                 min_value=0, value=0, step=100_000,
                                 help="Nilai sisa aset di akhir umur ekonomis. 0 jika tidak ada.")
        umur = st.number_input("Umur Ekonomis (Tahun) *",
                               min_value=1, value=5,
                               help="Tanah diabaikan — otomatis tidak disusutkan.")

        st.caption("Akun Aset & Akumulasi (dari COA)")
        akun_aset = st.selectbox("Akun Aset *", list(opsi_aset_akun.keys()))
        akun_akum = st.selectbox("Akun Akumulasi Penyusutan", list(opsi_akum_akun.keys()),
                                 help="Kosongkan untuk Tanah")
        keterangan = st.text_input("Keterangan", placeholder="Opsional")

        # Preview penyusutan
        if kategori != "Tanah" and umur > 0 and harga > residu:
            preview = svc.hitung_penyusutan_preview(harga, residu, umur, unit)
            st.info(
                f"**Preview Penyusutan:**  "
                f"Dasar = {format_rupiah(preview['dasar_penyusutan'])} | "
                f"Per Bulan = {format_rupiah(preview['penyusutan_per_bulan'])} | "
                f"Per Tahun = {format_rupiah(preview['penyusutan_per_tahun'])}"
            )

        if st.form_submit_button("💾 Simpan Aset", use_container_width=True):
            try:
                svc.tambah_aset_tetap(
                    kode_aset=kode,
                    nama_aset=nama,
                    kategori_aset=kategori,
                    tanggal_perolehan=str(tgl),
                    harga_perolehan=harga,
                    nilai_residu=residu,
                    umur_ekonomis_tahun=umur,
                    jumlah_unit=unit,
                    account_id=opsi_aset_akun.get(akun_aset),
                    account_akum_id=opsi_akum_akun.get(akun_akum),
                    keterangan=keterangan,
                )
                st.success(f"Aset '{nama}' berhasil ditambahkan!")
                st.rerun()
            except Exception as e:
                st.error(f"Gagal: {e}")


def _form_edit_aset(df: pd.DataFrame, opsi_aset_akun: dict, opsi_akum_akun: dict) -> None:
    """Form edit aset tetap — kode & kategori tidak bisa diubah."""
    pilihan = {f"{r['kode_aset']} - {r['nama_aset']}": r["id"] for _, r in df.iterrows()}
    dipilih = st.selectbox("Pilih Aset", list(pilihan.keys()), key="edit_aset_sel")
    if not dipilih:
        return
    baris = df[df["id"] == pilihan[dipilih]].iloc[0]

    with st.form("form_edit_aset"):
        st.caption(f"Kode: **{baris['kode_aset']}** | Kategori: **{baris['kategori_aset']}** (tidak bisa diubah)")
        nama_b = st.text_input("Nama Aset *", value=baris["nama_aset"])
        tgl_b = st.date_input("Tanggal Perolehan *",
                               value=date.fromisoformat(baris["tanggal_perolehan"]))
        unit_b = st.number_input("Jumlah Unit *", min_value=1, value=int(baris["jumlah_unit"]))
        harga_b = st.number_input("Harga Perolehan per Unit (Rp) *",
                                  min_value=1, value=int(baris["harga_perolehan"]), step=100_000)
        residu_b = st.number_input("Nilai Residu per Unit (Rp)", min_value=0,
                                   value=int(baris["nilai_residu"]), step=100_000)
        umur_b = st.number_input("Umur Ekonomis (Tahun)", min_value=1,
                                  value=int(baris["umur_ekonomis_tahun"]))

        # Preview penyusutan langsung
        if baris["is_disusutkan"] and umur_b > 0 and harga_b > residu_b:
            preview = svc.hitung_penyusutan_preview(harga_b, residu_b, umur_b, unit_b)
            st.info(
                f"**Preview Penyusutan:**  "
                f"Per Bulan = **{format_rupiah(preview['penyusutan_per_bulan'])}** | "
                f"Per Tahun = {format_rupiah(preview['penyusutan_per_tahun'])}"
            )

        # Akun
        akun_aset_key = next((k for k, v in opsi_aset_akun.items()
                               if v == baris.get("account_id")), "(Pilih akun)")
        akun_aset_b = st.selectbox("Akun Aset", list(opsi_aset_akun.keys()),
                                    index=list(opsi_aset_akun.keys()).index(akun_aset_key)
                                    if akun_aset_key in opsi_aset_akun else 0)
        akun_akum_key = next((k for k, v in opsi_akum_akun.items()
                               if v == baris.get("account_akum_id")), "(Tidak ada / Tanah)")
        akun_akum_b = st.selectbox("Akun Akumulasi", list(opsi_akum_akun.keys()),
                                    index=list(opsi_akum_akun.keys()).index(akun_akum_key)
                                    if akun_akum_key in opsi_akum_akun else 0)
        ktr_b = st.text_input("Keterangan", value=baris["keterangan"] or "")
        aktif_b = st.checkbox("Aktif?", value=bool(baris["aktif"]))

        if st.form_submit_button("💾 Simpan Perubahan", use_container_width=True):
            try:
                svc.ubah_aset_tetap(
                    asset_id=baris["id"],
                    nama_aset=nama_b,
                    tanggal_perolehan=str(tgl_b),
                    harga_perolehan=harga_b,
                    nilai_residu=residu_b,
                    umur_ekonomis_tahun=umur_b,
                    jumlah_unit=unit_b,
                    account_id=opsi_aset_akun.get(akun_aset_b),
                    account_akum_id=opsi_akum_akun.get(akun_akum_b),
                    aktif=aktif_b,
                    keterangan=ktr_b,
                )
                st.success("Data aset berhasil diperbarui!")
                st.rerun()
            except Exception as e:
                st.error(f"Gagal: {e}")


# ================================================================
# TAB 7 — BLOK LAHAN
# ================================================================
def _tab_blok_lahan() -> None:
    """CRUD Blok Lahan."""
    divider_dengan_judul("Blok Lahan", "geo-alt")

    df = svc.ambil_semua_blok()
    df_tampil = df[["kode_blok", "jumlah_pohon", "tanggal_tanam",
                     "komoditas", "luas_m2", "jarak_tanam_cm", "keterangan", "aktif"]].copy()
    df_tampil["aktif"] = df_tampil["aktif"].map({1: "Aktif", 0: "Nonaktif"})
    df_tampil.columns = ["Blok", "Jml Pohon", "Tgl Tanam", "Komoditas",
                          "Luas (m²)", "Jarak Tanam (cm)", "Keterangan", "Status"]
    st.dataframe(df_tampil, use_container_width=True, hide_index=True)

    kol1, kol2 = st.columns(2)
    with kol1:
        with st.expander("➕ Tambah Blok Lahan"):
            with st.form("form_tambah_blok", clear_on_submit=True):
                kode = st.text_input("Kode Blok *", placeholder="Contoh: F",
                                     help="Satu huruf kapital. Blok A-E sudah ada.")
                pohon = st.number_input("Jumlah Pohon *", min_value=1, value=1000)
                tgl = st.date_input("Tanggal Tanam *", value=date.today())
                komoditas = st.selectbox("Komoditas", svc.KOMODITAS_ITEM)
                luas = st.number_input("Luas (m²)", min_value=0.0, value=494.0, step=10.0)
                jarak = st.number_input("Jarak Tanam (cm)", min_value=10.0, value=100.0, step=5.0)
                ket = st.text_input("Keterangan", placeholder="Opsional")
                if st.form_submit_button("💾 Simpan", use_container_width=True):
                    try:
                        svc.tambah_blok(kode, pohon, str(tgl), komoditas, luas, jarak, ket)
                        st.success(f"Blok '{kode.upper()}' berhasil ditambahkan!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Gagal: {e}")

    with kol2:
        with st.expander("✏️ Edit Blok Lahan"):
            pilihan = {r["kode_blok"]: r["id"] for _, r in df.iterrows()}
            dipilih = st.selectbox("Pilih Blok", list(pilihan.keys()), key="edit_blok_sel")
            if dipilih:
                baris = df[df["id"] == pilihan[dipilih]].iloc[0]
                with st.form("form_edit_blok"):
                    st.caption(f"Kode Blok: **{baris['kode_blok']}** (tidak bisa diubah)")
                    pohon_b = st.number_input("Jumlah Pohon *", min_value=1,
                                              value=int(baris["jumlah_pohon"]))
                    tgl_b = st.date_input("Tanggal Tanam",
                                          value=date.fromisoformat(baris["tanggal_tanam"])
                                          if baris["tanggal_tanam"] else date.today())
                    luas_b = st.number_input("Luas (m²)", min_value=0.0,
                                             value=float(baris["luas_m2"] or 0))
                    jarak_b = st.number_input("Jarak Tanam (cm)", min_value=10.0,
                                              value=float(baris["jarak_tanam_cm"] or 100))
                    ket_b = st.text_input("Keterangan", value=baris["keterangan"] or "")
                    aktif_b = st.checkbox("Aktif?", value=bool(baris["aktif"]))
                    if st.form_submit_button("💾 Simpan Perubahan", use_container_width=True):
                        try:
                            svc.ubah_blok(baris["id"], pohon_b, str(tgl_b),
                                          luas_b, jarak_b, ket_b, aktif_b)
                            st.success(f"Blok '{baris['kode_blok']}' berhasil diperbarui!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Gagal: {e}")


# ================================================================
# TAB 8 — SALDO AWAL
# ================================================================
def _tab_saldo_awal() -> None:
    """
    Input/edit saldo awal per akun per periode.
    PENTING: Semua data contoh harus diganti dengan data asli.
    Validasi: total debit == total kredit (Persamaan Akuntansi).
    """
    divider_dengan_judul("Saldo Awal Akun", "wallet2")

    # Pilih periode
    period_id = selector_periode(
        label="📅 Pilih Periode Saldo Awal",
        key="master_saldo_awal_periode",
        hanya_buka=False,
        tampilkan_kalender=True,
    )
    if not period_id:
        return

    # Tampilkan saldo awal
    df = svc.ambil_saldo_awal(period_id)

    if df.empty:
        st.info("Belum ada saldo awal untuk periode ini.")
    else:
        df_tampil = df[["kode_akun", "nama_akun", "kategori",
                         "saldo_normal", "saldo_debit", "saldo_kredit", "catatan"]].copy()
        df_tampil["saldo_debit"] = df_tampil["saldo_debit"].apply(format_rupiah)
        df_tampil["saldo_kredit"] = df_tampil["saldo_kredit"].apply(format_rupiah)
        df_tampil.columns = ["Kode Akun", "Nama Akun", "Kategori",
                              "Saldo Normal", "Debit", "Kredit", "Catatan"]
        st.dataframe(df_tampil, use_container_width=True, hide_index=True)

        # Validasi keseimbangan saldo awal
        seimbang, total_d, total_k = svc.validasi_saldo_awal_seimbang(period_id)
        if seimbang:
            st.success(
                f"Saldo awal SEIMBANG — Total Debit = Total Kredit = {format_rupiah(total_d)}"
            )
        else:
            st.error(
                f"Saldo awal TIDAK SEIMBANG! "
                f"Debit: {format_rupiah(total_d)} | Kredit: {format_rupiah(total_k)} | "
                f"Selisih: {format_rupiah(abs(total_d - total_k))}"
            )

    st.warning(
        "⚠️ Semua angka saldo awal bertanda 'CONTOH' harus diganti dengan data asli!"
    )

    # Form input/ubah saldo awal
    with st.expander("➕ Tambah / Ubah Saldo Awal Akun"):
        _form_input_saldo_awal(period_id)

    # Form hapus saldo awal
    if not df.empty:
        with st.expander("🗑️ Hapus Saldo Awal Akun"):
            pilihan_hapus = {f"{r['kode_akun']} - {r['nama_akun']}": r["id"]
                             for _, r in df.iterrows()}
            akun_hapus = st.selectbox("Pilih akun yang akan dihapus saldo awalnya",
                                      list(pilihan_hapus.keys()), key="hapus_saldo_sel")
            if st.button("🗑️ Hapus Saldo Awal Akun Ini", type="secondary"):
                try:
                    svc.hapus_saldo_awal(pilihan_hapus[akun_hapus])
                    st.success(f"Saldo awal akun '{akun_hapus}' berhasil dihapus!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Gagal: {e}")


def _form_input_saldo_awal(period_id: int) -> None:
    """Form input/update saldo awal satu akun."""
    # Ambil semua akun aktif
    from database.connection import get_connection
    koneksi = get_connection()
    akun_rows = koneksi.execute(
        "SELECT id, kode_akun, nama_akun, saldo_normal, kategori "
        "FROM accounts WHERE aktif=1 ORDER BY kode_akun"
    ).fetchall()
    koneksi.close()

    opsi_akun = {f"{r['kode_akun']} - {r['nama_akun']} ({r['kategori']})": r
                 for r in akun_rows}

    with st.form("form_input_saldo_awal", clear_on_submit=True):
        akun_dipilih_key = st.selectbox("Pilih Akun *", list(opsi_akun.keys()))
        akun_row = opsi_akun[akun_dipilih_key]

        st.caption(
            f"Saldo Normal: **{akun_row['saldo_normal']}** — "
            f"isi di kolom yang sesuai saldo normalnya. Kolom lain isi 0."
        )

        kol1, kol2 = st.columns(2)
        with kol1:
            saldo_d = st.number_input("Saldo Debit (Rp)", min_value=0, value=0, step=100_000)
        with kol2:
            saldo_k = st.number_input("Saldo Kredit (Rp)", min_value=0, value=0, step=100_000)
        catatan = st.text_input("Catatan", value="",
                                placeholder="Contoh: Saldo per 1 Oktober 2026")

        if st.form_submit_button("💾 Simpan Saldo Awal", use_container_width=True):
            try:
                svc.simpan_saldo_awal(period_id, akun_row["id"],
                                      saldo_d, saldo_k, catatan)
                st.success(f"Saldo awal '{akun_dipilih_key}' berhasil disimpan!")
                st.rerun()
            except Exception as e:
                st.error(f"Gagal: {e}")


# ================================================================
# TAB 9 — PERIODE AKUNTANSI
# ================================================================
def _tab_periode() -> None:
    """Tambah dan kelola periode akuntansi (bulanan)."""
    divider_dengan_judul("Periode Akuntansi", "calendar3")
    st.caption("Satu periode = satu bulan. Periode yang sudah ditutup tidak bisa diedit.")

    df = svc.ambil_semua_periode()
    df_tampil = df[["nama_bulan", "tahun", "bulan", "status"]].copy()
    df_tampil["status"] = df_tampil["status"].map({"buka": "🔓 Buka", "tutup": "🔒 Tutup"})
    df_tampil.columns = ["Periode", "Tahun", "Bulan", "Status"]
    st.dataframe(df_tampil, use_container_width=True, hide_index=True)

    with st.expander("➕ Tambah Periode Baru"):
        with st.form("form_tambah_periode", clear_on_submit=True):
            kol1, kol2 = st.columns(2)
            with kol1:
                tahun = st.number_input("Tahun *", min_value=2024, max_value=2035, value=2026)
            with kol2:
                bulan = st.number_input("Bulan (1–12) *", min_value=1, max_value=12, value=11)
            st.caption(f"Periode yang akan ditambahkan: **{nama_bulan_tahun(bulan, tahun)}**")
            if st.form_submit_button("➕ Tambah Periode", use_container_width=True):
                try:
                    svc.tambah_periode(tahun, bulan)
                    st.success(f"Periode {nama_bulan_tahun(bulan, tahun)} berhasil ditambahkan!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Gagal (mungkin periode sudah ada): {e}")


# ================================================================
# TAB 10 — PARAMETER OPERASIONAL
# ================================================================
def _tab_parameter() -> None:
    """
    Tampilkan dan edit semua parameter operasional.
    Parameter dipakai oleh modul lain — ubah sesuai kondisi aktual.
    """
    divider_dengan_judul("Parameter Operasional", "gear")

    st.info(
        "Parameter ini dipakai di seluruh perhitungan sistem. "
        "Contoh: tarif upah dipakai di penggajian, alokasi listrik di penyesuaian."
    )

    df = svc.ambil_semua_parameter()

    # Tampilkan tabel
    df_tampil = df[["kunci", "nilai", "satuan", "catatan"]].copy()
    df_tampil.columns = ["Parameter", "Nilai", "Satuan", "Keterangan"]
    st.dataframe(df_tampil, use_container_width=True, hide_index=True)

    # Form edit parameter (satu per satu)
    with st.expander("✏️ Ubah Nilai Parameter"):
        pilihan_param = {r["kunci"]: {"id": r["id"], "nilai": r["nilai"], "satuan": r["satuan"]}
                         for _, r in df.iterrows()}
        param_dipilih = st.selectbox(
            "Pilih Parameter yang Ingin Diubah",
            list(pilihan_param.keys()),
            key="edit_param_sel",
            format_func=lambda k: f"{k}  ({pilihan_param[k]['satuan'] or ''})"
        )
        if param_dipilih:
            info_param = pilihan_param[param_dipilih]
            st.caption(f"Nilai saat ini: **{info_param['nilai']}** {info_param['satuan'] or ''}")

            with st.form("form_edit_parameter"):
                nilai_baru = st.text_input(
                    f"Nilai Baru untuk '{param_dipilih}'",
                    value=info_param["nilai"],
                    help="Masukkan angka tanpa titik atau koma. Contoh: 90000"
                )
                if st.form_submit_button("💾 Simpan Perubahan", use_container_width=True):
                    try:
                        svc.ubah_parameter(info_param["id"], nilai_baru)
                        st.success(
                            f"Parameter '{param_dipilih}' diubah menjadi "
                            f"'{nilai_baru}' {info_param['satuan'] or ''}"
                        )
                        st.rerun()
                    except Exception as e:
                        st.error(f"Gagal: {e}")

    # Info referensi parameter
    with st.expander("ℹ️ Panduan Parameter"):
        st.markdown("""
        | Parameter | Dipakai Di | Catatan |
        |-----------|-----------|---------|
        | `upah_tetap_harian` | Penggajian | Rp/hari pekerja tetap |
        | `upah_tambahan_harian` | Penggajian | Rp/hari tenaga tambahan |
        | `hasil_panen_per_pohon_gram` | Pencatatan Panen | Rata-rata per pohon per pemetikan |
        | `harga_jual_cabai_default` | Input Transaksi | Harga default — fluktuatif! |
        | `alokasi_listrik_cabai_persen` | Penyesuaian | % tagihan listrik dialokasikan ke cabai |
        | `listrik_total_bulanan` | Penyesuaian | Total tagihan listrik per bulan |
        | `bbm_pengiriman_mingguan` | Input Transaksi | BBM pengiriman per minggu |
        | `bbm_operasional_mingguan` | Input Transaksi | BBM operasional per minggu |
        | `sewa_traktor_per_hari` | Input Transaksi | Rp/hari sewa traktor |
        | `jatuh_tempo_piutang_hari` | Penjualan Tempo | Jatuh tempo piutang (default 7 hari) |
        """)


# Panggil fungsi utama
tampilkan()
