"""
views/02_input_transaksi.py
----------------------------
Tujuan  : Form input semua jenis transaksi. Setiap jenis transaksi
          punya form terpisah. Jurnal dibuat otomatis dengan pratinjau
          sebelum disimpan (2-step: isi form → pratinjau → simpan).
Input   : Data transaksi dari user via form Streamlit.
Output  : Jurnal tersimpan ke database, pesan sukses/error.
Dipanggil oleh : app.py (st.navigation)

JENIS TRANSAKSI:
  Penjualan   : 1. Penjualan Tunai, 2. Penjualan Tempo
  Pembelian   : 3. Pembelian Barang Dagang Tunai, 4. Pembelian Kredit
  Kas         : 5. Terima Pelunasan Piutang, 6. Setoran Modal
  Persediaan  : 7. Catat Panen
  Lainnya     : 8. Biaya Operasional, 9. Pembelian Aset
"""

import streamlit as st
import pandas as pd
import streamlit_antd_components as sac
from database.connection import get_connection
from services import transaction_service as ts
from services.inventory_service import hitung_nilai_keluar
from utils.formatting import format_rupiah, format_tanggal
from utils.ui_components import divider_dengan_judul, selector_periode
from theme import WARNA_PRIMER, WARNA_SUKSES, WARNA_BAHAYA


# ================================================================
# HELPER: Ambil data referensi dari DB
# ================================================================

@st.cache_data(ttl=60)
def _ambil_periode_buka():
    """Ambil semua periode dengan status 'buka'."""
    koneksi = get_connection()
    rows = koneksi.execute(
        "SELECT id, nama_bulan AS label FROM periods WHERE status = 'buka' ORDER BY tahun, bulan"
    ).fetchall()
    koneksi.close()
    return [dict(r) for r in rows]


@st.cache_data(ttl=60)
def _ambil_customers():
    koneksi = get_connection()
    rows = koneksi.execute(
        "SELECT id, nama FROM customers WHERE aktif = 1 ORDER BY nama"
    ).fetchall()
    koneksi.close()
    return [dict(r) for r in rows]


@st.cache_data(ttl=60)
def _ambil_suppliers():
    koneksi = get_connection()
    rows = koneksi.execute(
        "SELECT id, nama FROM suppliers WHERE aktif = 1 ORDER BY nama"
    ).fetchall()
    koneksi.close()
    return [dict(r) for r in rows]


@st.cache_data(ttl=60)
def _ambil_items(tipe: str | None = None):
    """Ambil items, mengambil item berdasarkan tipe hasil panen cabai."""
    koneksi = get_connection()
    if tipe:
        rows = koneksi.execute(
            "SELECT id, nama_item AS nama, satuan, account_id FROM items WHERE tipe = ? AND aktif = 1 ORDER BY nama_item",
            (tipe,)
        ).fetchall()
    else:
        rows = koneksi.execute(
            "SELECT id, nama_item AS nama, satuan, tipe, account_id FROM items WHERE aktif = 1 ORDER BY nama_item"
        ).fetchall()
    koneksi.close()
    return [dict(r) for r in rows]


@st.cache_data(ttl=60)
def _ambil_blok_lahan():
    koneksi = get_connection()
    rows = koneksi.execute(
        "SELECT id, kode_blok AS kode, kode_blok AS nama, jumlah_pohon FROM blok_lahan WHERE aktif = 1 ORDER BY kode_blok"
    ).fetchall()
    koneksi.close()
    return [dict(r) for r in rows]


@st.cache_data(ttl=60)
def _ambil_akun(kategori: str | None = None):
    """Ambil akun, opsional filter per kategori."""
    koneksi = get_connection()
    if kategori:
        rows = koneksi.execute(
            "SELECT id, kode_akun, nama_akun, is_kontra FROM accounts WHERE kategori = ? AND aktif = 1 ORDER BY kode_akun",
            (kategori,)
        ).fetchall()
    else:
        rows = koneksi.execute(
            "SELECT id, kode_akun, nama_akun, kategori, is_kontra FROM accounts WHERE aktif = 1 ORDER BY kode_akun"
        ).fetchall()
    koneksi.close()
    return [dict(r) for r in rows]


def _cari_akun_by_kode(kode: str) -> int | None:
    """Cari account_id berdasarkan kode_akun."""
    koneksi = get_connection()
    row = koneksi.execute(
        "SELECT id FROM accounts WHERE kode_akun = ?", (kode,)
    ).fetchone()
    koneksi.close()
    return row["id"] if row else None


def _cari_akun_penjualan(komoditas: str) -> int | None:
    """Mengembalikan akun pendapatan untuk penjualan cabai."""
    if komoditas != "cabai":
        return None
    return _cari_akun_by_kode("4110")


def _cari_akun_peralatan() -> int | None:
    """Mengembalikan akun aset untuk peralatan pertanian (1250)."""
    akun_id = _cari_akun_by_kode("1250")
    if akun_id:
        return akun_id
    for a in _ambil_akun("Aset"):
        if "peralatan" in a["nama_akun"].lower() and not a.get("is_kontra"):
            return a["id"]
    return None


def _bersihkan_pratinjau():
    """Bersihkan state pratinjau dari session_state."""
    for key in ["pratinjau_data", "pratinjau_baris", "pratinjau_params"]:
        if key in st.session_state:
            del st.session_state[key]


# ================================================================
# KOMPONEN PRATINJAU JURNAL
# ================================================================

def _tampilkan_pratinjau(baris: list[dict], params: dict) -> bool:
    """
    Menampilkan tabel pratinjau jurnal dan tombol Simpan/Batal.
    Mengembalikan True jika pengguna klik Simpan, False jika Batal.

    Args:
        baris  : List dict [{account_id, debit, kredit}] dari form.
        params : Dict parameter transaksi yang akan diteruskan ke service.

    Returns:
        True jika jurnal berhasil disimpan.
    """
    sac.divider(label="Pratinjau Jurnal", icon="journal-check", align="center", color=WARNA_PRIMER)

    # Ambil nama akun untuk pratinjau
    account_ids = [b["account_id"] for b in baris]
    df_pratinjau = ts.buat_baris_pratinjau(baris, account_ids)

    # Hitung total untuk validasi keseimbangan
    baris_data = df_pratinjau[df_pratinjau["Akun"] != "**TOTAL**"]
    total_debit = int(baris_data["Debit"].sum())
    total_kredit = int(baris_data["Kredit"].sum())
    seimbang = total_debit == total_kredit

    # Format angka sebagai Rupiah untuk tampilan
    df_tampil = df_pratinjau.copy()
    df_tampil["Debit"] = df_tampil["Debit"].apply(
        lambda x: format_rupiah(x) if x > 0 else "-"
    )
    df_tampil["Kredit"] = df_tampil["Kredit"].apply(
        lambda x: format_rupiah(x) if x > 0 else "-"
    )

    st.dataframe(df_tampil, use_container_width=True, hide_index=True)

    # Tampilkan status keseimbangan
    if seimbang:
        sac.alert(
            label="Jurnal Seimbang ✅",
            description=f"Total Debit = Total Kredit = {format_rupiah(total_debit)}",
            color="success", icon=True,
        )
    else:
        sac.alert(
            label="Jurnal TIDAK Seimbang ❌",
            description=f"Debit: {format_rupiah(total_debit)} ≠ Kredit: {format_rupiah(total_kredit)}",
            color="error", icon=True,
        )
        return False

    # Tombol Simpan dan Batal
    kol_simpan, kol_batal, _ = st.columns([1, 1, 3])
    with kol_simpan:
        if st.button("💾 Simpan Jurnal", type="primary", use_container_width=True):
            return True
    with kol_batal:
        if st.button("❌ Batal", use_container_width=True):
            _bersihkan_pratinjau()
            st.rerun()

    return False


# ================================================================
# FORM 1: PENJUALAN TUNAI
# ================================================================

def _form_penjualan_tunai(period_id: int):
    """Form input penjualan tunai cabai."""
    st.subheader("🛒 Penjualan Tunai")

    customers = _ambil_customers()
    nama_customers = [f"{c['nama']}" for c in customers]
    items_panen = _ambil_items("hasil_panen")
    if not items_panen:
        st.warning("Belum ada item hasil panen cabai. Tambahkan item hasil panen di Master Data dan hubungkan ke akun persediaan.")
        return

    with st.form("form_penjualan_tunai"):
        kol1, kol2 = st.columns(2)
        with kol1:
            tanggal = st.date_input("Tanggal Transaksi", value="today")
            pelanggan_pilih = st.selectbox(
                "Pelanggan", options=["(Ketik nama baru)"] + nama_customers
            )
            if pelanggan_pilih == "(Ketik nama baru)":
                pelanggan = st.text_input("Nama Pelanggan *", placeholder="Nama pelanggan")
            else:
                pelanggan = pelanggan_pilih
        with kol2:
            jumlah_kg = st.number_input("Jumlah (kg)", min_value=0.1, step=0.1, value=1.0)
            harga_per_kg = st.number_input(
                "Harga per kg (Rp)", min_value=1000, step=500, value=50000
            )
            komoditas = "cabai"
            st.text_input("Komoditas", value="Cabai", disabled=True)
            item_panen_idx = st.selectbox(
                "Persediaan Cabai yang Dijual",
                range(len(items_panen)),
                format_func=lambda i: f"{items_panen[i]['nama']} ({items_panen[i]['satuan']})",
            )

        keterangan = st.text_input("Keterangan Tambahan", placeholder="(opsional)")
        st.caption(f"**Total: {format_rupiah(int(jumlah_kg * harga_per_kg))}**")

        pratinjau_btn = st.form_submit_button("👁️ Pratinjau Jurnal", type="primary")

    if pratinjau_btn:
        if not pelanggan:
            st.error("Nama pelanggan wajib diisi.")
            return

        akun_kas_id = _cari_akun_by_kode("1110")
        # Gunakan akun penjualan cabai
        akun_jual_id = _cari_akun_penjualan(komoditas)

        if not akun_kas_id or not akun_jual_id:
            st.error("Akun Kas atau Penjualan tidak ditemukan. Periksa master data COA.")
            return

        total = int(jumlah_kg * harga_per_kg)
        item_panen = items_panen[item_panen_idx]
        if not item_panen.get("account_id"):
            st.error("Item hasil panen belum dihubungkan ke akun persediaan.")
            return
        akun_hpp_id = _cari_akun_by_kode("5110")
        if not akun_hpp_id:
            st.error("Akun Harga Pokok Penjualan (5110) belum tersedia.")
            return
        try:
            hasil_hpp = hitung_nilai_keluar(item_panen["id"], jumlah_kg)
        except ValueError as e:
            st.error(str(e))
            return
        total_hpp = int(hasil_hpp["total_keluar"])
        if total_hpp <= 0:
            st.error("Harga pokok persediaan belum tersedia. Periksa saldo awal atau harga pokok hasil panen.")
            return

        baris = [
            {"account_id": akun_kas_id, "debit": total, "kredit": 0},
            {"account_id": akun_jual_id, "debit": 0, "kredit": total},
            {"account_id": akun_hpp_id, "debit": total_hpp, "kredit": 0},
            {"account_id": item_panen["account_id"], "debit": 0, "kredit": total_hpp},
        ]

        st.session_state["pratinjau_baris"] = baris
        st.session_state["pratinjau_params"] = {
            "jenis": "penjualan_tunai",
            "period_id": period_id,
            "tanggal": str(tanggal),
            "pelanggan": pelanggan,
            "jumlah_kg": jumlah_kg,
            "harga_per_kg": harga_per_kg,
            "akun_kas_id": akun_kas_id,
            "akun_penjualan_id": akun_jual_id,
            "komoditas": komoditas,
            "keterangan_tambahan": keterangan,
            "item_panen_id": item_panen["id"],
            "hpp_estimasi": total_hpp,
        }

    # Tampilkan pratinjau jika ada
    if "pratinjau_baris" in st.session_state and st.session_state.get("pratinjau_params", {}).get("jenis") == "penjualan_tunai":
        disimpan = _tampilkan_pratinjau(
            st.session_state["pratinjau_baris"],
            st.session_state["pratinjau_params"],
        )
        if disimpan:
            try:
                p = st.session_state["pratinjau_params"]
                ts.catat_penjualan_tunai(
                    period_id=p["period_id"], tanggal=p["tanggal"],
                    pelanggan=p["pelanggan"], jumlah_kg=p["jumlah_kg"],
                    harga_per_kg=p["harga_per_kg"], akun_kas_id=p["akun_kas_id"],
                    akun_penjualan_id=p["akun_penjualan_id"],
                    komoditas=p["komoditas"], keterangan_tambahan=p["keterangan_tambahan"],
                    item_panen_id=p["item_panen_id"], hpp_estimasi=p["hpp_estimasi"],
                )
                st.success(f"✅ Penjualan tunai ke **{p['pelanggan']}** berhasil disimpan!")
                _bersihkan_pratinjau()
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Gagal menyimpan: {e}")


# ================================================================
# FORM 2: PENJUALAN TEMPO
# ================================================================

def _form_penjualan_tempo(period_id: int):
    """Form input penjualan tempo / kredit."""
    st.subheader("📋 Penjualan Tempo (Kredit)")

    customers = _ambil_customers()
    items_panen = _ambil_items("hasil_panen")
    if not customers:
        st.warning("Belum ada data pelanggan. Tambahkan di menu Master Data > Pelanggan.")
        return
    if not items_panen:
        st.warning("Belum ada item hasil panen cabai. Tambahkan item hasil panen di Master Data.")
        return

    with st.form("form_penjualan_tempo"):
        kol1, kol2 = st.columns(2)
        with kol1:
            tanggal = st.date_input("Tanggal Transaksi", value="today")
            customer_idx = st.selectbox(
                "Pelanggan *",
                options=range(len(customers)),
                format_func=lambda i: customers[i]["nama"],
            )
            komoditas = "cabai"
            st.text_input("Komoditas", value="Cabai", disabled=True)
            item_panen_idx = st.selectbox(
                "Persediaan Cabai yang Dijual",
                range(len(items_panen)),
                format_func=lambda i: f"{items_panen[i]['nama']} ({items_panen[i]['satuan']})",
            )
        with kol2:
            jumlah_kg = st.number_input("Jumlah (kg)", min_value=0.1, step=0.1, value=1.0)
            harga_per_kg = st.number_input(
                "Harga per kg (Rp)", min_value=1000, step=500, value=50000
            )

        total = int(jumlah_kg * harga_per_kg)
        st.caption(f"**Total: {format_rupiah(total)}** | Jatuh tempo: 7 hari")
        pratinjau_btn = st.form_submit_button("👁️ Pratinjau Jurnal", type="primary")

    if pratinjau_btn:
        customer = customers[customer_idx]
        akun_piutang_id = _cari_akun_by_kode("1120")
        akun_jual_id = _cari_akun_penjualan(komoditas)

        if not akun_piutang_id or not akun_jual_id:
            st.error("Akun Piutang (1120) atau Akun Penjualan tidak ditemukan.")
            return

        item_panen = items_panen[item_panen_idx]
        if not item_panen.get("account_id"):
            st.error("Item hasil panen belum dihubungkan ke akun persediaan.")
            return
        akun_hpp_id = _cari_akun_by_kode("5110")
        if not akun_hpp_id:
            st.error("Akun Harga Pokok Penjualan (5110) belum tersedia.")
            return
        try:
            hasil_hpp = hitung_nilai_keluar(item_panen["id"], jumlah_kg)
        except ValueError as e:
            st.error(str(e))
            return
        total_hpp = int(hasil_hpp["total_keluar"])
        if total_hpp <= 0:
            st.error("Harga pokok persediaan belum tersedia. Periksa saldo awal atau harga pokok hasil panen.")
            return

        baris = [
            {"account_id": akun_piutang_id, "debit": total, "kredit": 0},
            {"account_id": akun_jual_id, "debit": 0, "kredit": total},
            {"account_id": akun_hpp_id, "debit": total_hpp, "kredit": 0},
            {"account_id": item_panen["account_id"], "debit": 0, "kredit": total_hpp},
        ]
        st.session_state["pratinjau_baris"] = baris
        st.session_state["pratinjau_params"] = {
            "jenis": "penjualan_tempo",
            "period_id": period_id,
            "tanggal": str(tanggal),
            "customer_id": customer["id"],
            "pelanggan_nama": customer["nama"],
            "jumlah_kg": jumlah_kg,
            "harga_per_kg": harga_per_kg,
            "akun_piutang_id": akun_piutang_id,
            "akun_penjualan_id": akun_jual_id,
            "komoditas": komoditas,
            "item_panen_id": item_panen["id"],
            "hpp_estimasi": total_hpp,
        }

    if "pratinjau_baris" in st.session_state and st.session_state.get("pratinjau_params", {}).get("jenis") == "penjualan_tempo":
        disimpan = _tampilkan_pratinjau(
            st.session_state["pratinjau_baris"],
            st.session_state["pratinjau_params"],
        )
        if disimpan:
            try:
                p = st.session_state["pratinjau_params"]
                ts.catat_penjualan_tempo(
                    period_id=p["period_id"], tanggal=p["tanggal"],
                    customer_id=p["customer_id"], pelanggan_nama=p["pelanggan_nama"],
                    jumlah_kg=p["jumlah_kg"], harga_per_kg=p["harga_per_kg"],
                    akun_piutang_id=p["akun_piutang_id"],
                    akun_penjualan_id=p["akun_penjualan_id"],
                    komoditas=p["komoditas"],
                    item_panen_id=p["item_panen_id"], hpp_estimasi=p["hpp_estimasi"],
                )
                st.success(f"✅ Penjualan tempo ke **{p['pelanggan_nama']}** berhasil disimpan!")
                _bersihkan_pratinjau()
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Gagal menyimpan: {e}")


# ================================================================
# FORM 3: TERIMA PELUNASAN PIUTANG
# ================================================================

def _form_terima_piutang(period_id: int):
    """Form penerimaan pelunasan piutang dari pelanggan."""
    st.subheader("💰 Terima Pelunasan Piutang")

    df_piutang = ts.ambil_piutang_terbuka()
    if df_piutang.empty:
        st.info("Tidak ada piutang yang belum lunas.")
        return

    # Buat pilihan dropdown
    opsi_piutang = [
        f"{row['no_faktur']} | {row['pelanggan']} | Sisa: {format_rupiah(int(row['sisa_piutang']))}"
        for _, row in df_piutang.iterrows()
    ]

    with st.form("form_terima_piutang"):
        piutang_idx = st.selectbox("Pilih Faktur Piutang *", range(len(opsi_piutang)),
                                   format_func=lambda i: opsi_piutang[i])
        tanggal = st.date_input("Tanggal Penerimaan", value="today")

        baris_piutang = df_piutang.iloc[piutang_idx]
        sisa = int(baris_piutang["sisa_piutang"])
        jumlah = st.number_input(
            f"Jumlah Diterima (Rp) — Sisa: {format_rupiah(sisa)}",
            min_value=1000, max_value=sisa, value=sisa, step=1000,
        )
        keterangan = st.text_input("Keterangan", placeholder="(opsional)")
        pratinjau_btn = st.form_submit_button("👁️ Pratinjau Jurnal", type="primary")

    if pratinjau_btn:
        akun_kas_id = _cari_akun_by_kode("1110")
        akun_piutang_id = _cari_akun_by_kode("1120")
        baris_piutang = df_piutang.iloc[piutang_idx]

        baris = [
            {"account_id": akun_kas_id, "debit": jumlah, "kredit": 0},
            {"account_id": akun_piutang_id, "debit": 0, "kredit": jumlah},
        ]
        st.session_state["pratinjau_baris"] = baris
        st.session_state["pratinjau_params"] = {
            "jenis": "terima_piutang",
            "period_id": period_id,
            "receivable_id": int(baris_piutang["id"]),
            "tanggal": str(tanggal),
            "jumlah": jumlah,
            "akun_kas_id": akun_kas_id,
            "akun_piutang_id": akun_piutang_id,
            "keterangan_tambahan": keterangan,
        }

    if "pratinjau_baris" in st.session_state and st.session_state.get("pratinjau_params", {}).get("jenis") == "terima_piutang":
        disimpan = _tampilkan_pratinjau(
            st.session_state["pratinjau_baris"],
            st.session_state["pratinjau_params"],
        )
        if disimpan:
            try:
                p = st.session_state["pratinjau_params"]
                ts.catat_penerimaan_piutang(
                    period_id=p["period_id"], receivable_id=p["receivable_id"],
                    tanggal=p["tanggal"], jumlah=p["jumlah"],
                    akun_kas_id=p["akun_kas_id"], akun_piutang_id=p["akun_piutang_id"],
                    keterangan_tambahan=p.get("keterangan_tambahan", ""),
                )
                st.success("✅ Pelunasan piutang berhasil dicatat!")
                _bersihkan_pratinjau()
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Gagal menyimpan: {e}")


# ================================================================
# FORM 4: SETORAN MODAL
# ================================================================

def _form_setoran_modal(period_id: int):
    """Form setoran modal dari pemilik."""
    st.subheader("💼 Setoran Modal")

    with st.form("form_setoran_modal"):
        tanggal = st.date_input("Tanggal", value="today")
        jumlah = st.number_input("Jumlah Modal (Rp)", min_value=100000, step=100000, value=1000000)
        keterangan = st.text_input("Keterangan", value="Setoran modal pemilik")
        pratinjau_btn = st.form_submit_button("👁️ Pratinjau Jurnal", type="primary")

    if pratinjau_btn:
        akun_kas_id = _cari_akun_by_kode("1110")
        akun_modal_id = _cari_akun_by_kode("3110")

        baris = [
            {"account_id": akun_kas_id, "debit": jumlah, "kredit": 0},
            {"account_id": akun_modal_id, "debit": 0, "kredit": jumlah},
        ]
        st.session_state["pratinjau_baris"] = baris
        st.session_state["pratinjau_params"] = {
            "jenis": "setoran_modal",
            "period_id": period_id,
            "tanggal": str(tanggal),
            "jumlah": jumlah,
            "akun_kas_id": akun_kas_id,
            "akun_modal_id": akun_modal_id,
            "keterangan": keterangan,
        }

    if "pratinjau_baris" in st.session_state and st.session_state.get("pratinjau_params", {}).get("jenis") == "setoran_modal":
        disimpan = _tampilkan_pratinjau(
            st.session_state["pratinjau_baris"],
            st.session_state["pratinjau_params"],
        )
        if disimpan:
            try:
                p = st.session_state["pratinjau_params"]
                ts.catat_setoran_modal(
                    period_id=p["period_id"], tanggal=p["tanggal"],
                    jumlah=p["jumlah"], akun_kas_id=p["akun_kas_id"],
                    akun_modal_id=p["akun_modal_id"], keterangan=p["keterangan"],
                )
                st.success(f"✅ Setoran modal {format_rupiah(p['jumlah'])} berhasil dicatat!")
                _bersihkan_pratinjau()
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Gagal menyimpan: {e}")


# ================================================================
# FORM 5: PEMBELIAN BARANG DAGANG TUNAI
# ================================================================

def _form_pembelian_barang_dagang_tunai(period_id: int):
    """Form pembelian barang dagang cabai, perlengkapan, atau peralatan secara tunai."""
    st.subheader("🛒 Beli Tunai")

    suppliers = _ambil_suppliers()
    items_panen = _ambil_items("hasil_panen")

    kategori_pembelian = st.radio(
        "Kategori Pembelian *",
        [
            "🌶️ Barang Dagang (Cabai)",
            "📦 Perlengkapan (Bambu, Plastik Mulsa, Karung, Keranjang, dll)",
            "🔧 Peralatan (Ember, Cangkul, Sabit, Tangki Semprot, dll)",
        ],
        horizontal=True,
        key=f"kat_beli_tunai_{period_id}",
    )

    if kategori_pembelian.startswith("🌶️"):
        if not items_panen:
            st.warning("Belum ada item barang dagang cabai. Tambahkan di Master Data > Item.")
            return

        with st.form("form_beli_tunai"):
            kol1, kol2 = st.columns(2)
            with kol1:
                tanggal = st.date_input("Tanggal", value="today")
                if suppliers:
                    supplier_idx = st.selectbox(
                        "Supplier",
                        range(len(suppliers)),
                        format_func=lambda i: suppliers[i]["nama"],
                    )
                    supplier_nama = suppliers[supplier_idx]["nama"]
                else:
                    supplier_nama = st.text_input("Nama Supplier", placeholder="Nama supplier")

                item_idx = st.selectbox(
                    "Item *",
                    range(len(items_panen)),
                    format_func=lambda i: f"{items_panen[i]['nama']} ({items_panen[i]['satuan']})",
                )

            with kol2:
                qty = st.number_input("Kuantitas", min_value=0.1, step=0.1, value=1.0)
                harga_satuan = st.number_input("Harga Satuan (Rp)", min_value=1000, step=500, value=10000)

                st.caption("Akun otomatis: **1140 - Persediaan Barang Dagang**")

            keterangan = st.text_input("Keterangan", placeholder="(opsional)")
            total = int(qty * harga_satuan)
            st.caption(f"**Total: {format_rupiah(total)}**")
            pratinjau_btn = st.form_submit_button("👁️ Pratinjau Jurnal", type="primary")

        if pratinjau_btn:
            item = items_panen[item_idx]
            akun_persediaan_id = item.get("account_id")
            if not akun_persediaan_id:
                st.error(
                    "Item belum terhubung ke akun 1140 - Persediaan. "
                    "Periksa Master Data > Item."
                )
                return

            akun_kas_id = _cari_akun_by_kode("1110")

            baris = [
                {"account_id": akun_persediaan_id, "debit": total, "kredit": 0},
                {"account_id": akun_kas_id, "debit": 0, "kredit": total},
            ]
            st.session_state["pratinjau_baris"] = baris
            st.session_state["pratinjau_params"] = {
                "jenis": "beli_tunai",
                "period_id": period_id,
                "tanggal": str(tanggal),
                "supplier_nama": supplier_nama,
                "item_id": item["id"],
                "qty": qty,
                "harga_satuan": harga_satuan,
                "akun_persediaan_id": akun_persediaan_id,
                "akun_kas_id": akun_kas_id,
                "keterangan": keterangan,
            }

        if "pratinjau_baris" in st.session_state and st.session_state.get("pratinjau_params", {}).get("jenis") == "beli_tunai":
            disimpan = _tampilkan_pratinjau(
                st.session_state["pratinjau_baris"],
                st.session_state["pratinjau_params"],
            )
            if disimpan:
                try:
                    p = st.session_state["pratinjau_params"]
                    ts.catat_pembelian_tunai(
                        period_id=p["period_id"], tanggal=p["tanggal"],
                        supplier_nama=p["supplier_nama"], item_id=p["item_id"],
                        qty=p["qty"], harga_satuan=p["harga_satuan"],
                        akun_persediaan_id=p["akun_persediaan_id"],
                        akun_kas_id=p["akun_kas_id"], keterangan=p["keterangan"],
                    )
                    st.success("✅ Pembelian barang dagang tunai berhasil dicatat!")
                    _bersihkan_pratinjau()
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Gagal menyimpan: {e}")

    elif kategori_pembelian.startswith("📦"):
        # Pembelian Perlengkapan Tunai (Bambu, Plastik Mulsa, Karung, Keranjang, dll)
        with st.form("form_beli_perlengkapan_tunai"):
            kol1, kol2 = st.columns(2)
            with kol1:
                tanggal = st.date_input("Tanggal", value="today")
                if suppliers:
                    supplier_idx = st.selectbox(
                        "Supplier",
                        range(len(suppliers)),
                        format_func=lambda i: suppliers[i]["nama"],
                        key=f"supp_pt_{period_id}",
                    )
                    supplier_nama = suppliers[supplier_idx]["nama"]
                else:
                    supplier_nama = st.text_input("Nama Supplier", placeholder="Nama supplier", key=f"supp_txt_pt_{period_id}")

                pilihan_perlengkapan = [
                    "Bambu",
                    "Plastik Mulsa",
                    "Karung",
                    "Keranjang",
                    "Lainnya (Ketik Manual)",
                ]
                pilih_item_p = st.selectbox("Jenis Perlengkapan *", options=pilihan_perlengkapan, key=f"jenis_pt_{period_id}")
                if pilih_item_p == "Lainnya (Ketik Manual)":
                    nama_perlengkapan = st.text_input("Nama Perlengkapan *", placeholder="Contoh: Ajir / Terpal", key=f"manual_pt_{period_id}")
                else:
                    nama_perlengkapan = pilih_item_p

            with kol2:
                kol_qty, kol_satuan = st.columns([1, 1])
                with kol_qty:
                    qty = st.number_input("Kuantitas", min_value=0.1, step=0.1, value=1.0, key=f"qty_pt_{period_id}")
                with kol_satuan:
                    satuan_p = st.selectbox(
                        "Satuan",
                        ["batang", "roll", "karung / lembar", "buah", "ikat", "meter", "kg", "pack"],
                        key=f"satuan_pt_{period_id}",
                    )
                harga_satuan = st.number_input("Harga Satuan (Rp)", min_value=100, step=500, value=10000, key=f"harga_pt_{period_id}")
                st.caption("Akun otomatis: **1130 - Perlengkapan** (Bukan Persediaan)")

            keterangan = st.text_input("Keterangan", placeholder="(opsional)", key=f"ket_pt_{period_id}")
            total = int(qty * harga_satuan)
            st.caption(f"**Total: {format_rupiah(total)}**")
            pratinjau_btn = st.form_submit_button("👁️ Pratinjau Jurnal", type="primary")

        if pratinjau_btn:
            if not nama_perlengkapan.strip():
                st.error("Nama perlengkapan wajib diisi.")
                return
            akun_perlengkapan_id = _cari_akun_by_kode("1130")
            if not akun_perlengkapan_id:
                st.error("Akun 1130 - Perlengkapan tidak ditemukan dalam Bagan Akun.")
                return
            akun_kas_id = _cari_akun_by_kode("1110")
            if not akun_kas_id:
                st.error("Akun 1110 - Kas tidak ditemukan dalam Bagan Akun.")
                return

            baris = [
                {"account_id": akun_perlengkapan_id, "debit": total, "kredit": 0},
                {"account_id": akun_kas_id, "debit": 0, "kredit": total},
            ]
            st.session_state["pratinjau_baris"] = baris
            label_nama = f"{nama_perlengkapan} ({qty:g} {satuan_p})"
            st.session_state["pratinjau_params"] = {
                "jenis": "beli_perlengkapan_tunai",
                "period_id": period_id,
                "tanggal": str(tanggal),
                "supplier_nama": supplier_nama,
                "nama_perlengkapan": label_nama,
                "qty": qty,
                "harga_satuan": harga_satuan,
                "akun_perlengkapan_id": akun_perlengkapan_id,
                "akun_kas_id": akun_kas_id,
                "keterangan": keterangan or f"Beli perlengkapan {label_nama} tunai - {supplier_nama}",
            }

        if "pratinjau_baris" in st.session_state and st.session_state.get("pratinjau_params", {}).get("jenis") == "beli_perlengkapan_tunai":
            disimpan = _tampilkan_pratinjau(
                st.session_state["pratinjau_baris"],
                st.session_state["pratinjau_params"],
            )
            if disimpan:
                try:
                    p = st.session_state["pratinjau_params"]
                    ts.catat_pembelian_perlengkapan_tunai(
                        period_id=p["period_id"],
                        tanggal=p["tanggal"],
                        supplier_nama=p["supplier_nama"],
                        nama_perlengkapan=p["nama_perlengkapan"],
                        qty=p["qty"],
                        harga_satuan=p["harga_satuan"],
                        akun_perlengkapan_id=p["akun_perlengkapan_id"],
                        akun_kas_id=p["akun_kas_id"],
                        keterangan=p["keterangan"],
                    )
                    st.success(f"✅ Pembelian perlengkapan **{p['nama_perlengkapan']}** tunai berhasil dicatat!")
                    _bersihkan_pratinjau()
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Gagal menyimpan: {e}")

    else:
        # Pembelian Peralatan Tunai (Ember, Cangkul, Sabit, Tangki Semprot, Timbangan, Pompa Air, Selang Air, dll)
        with st.form("form_beli_peralatan_tunai"):
            kol1, kol2 = st.columns(2)
            with kol1:
                tanggal = st.date_input("Tanggal", value="today")
                if suppliers:
                    supplier_idx = st.selectbox(
                        "Supplier",
                        range(len(suppliers)),
                        format_func=lambda i: suppliers[i]["nama"],
                        key=f"supp_alat_t_{period_id}",
                    )
                    supplier_nama = suppliers[supplier_idx]["nama"]
                else:
                    supplier_nama = st.text_input("Nama Supplier", placeholder="Nama supplier / toko", key=f"supp_txt_alat_t_{period_id}")

                pilihan_peralatan = [
                    "Ember",
                    "Cangkul",
                    "Sabit",
                    "Tangki Semprot",
                    "Timbangan",
                    "Pompa Air",
                    "Selang Air",
                    "Lainnya (Ketik Manual)",
                ]
                pilih_item_alat = st.selectbox("Jenis Peralatan *", options=pilihan_peralatan, key=f"jenis_alat_t_{period_id}")
                if pilih_item_alat == "Lainnya (Ketik Manual)":
                    nama_peralatan = st.text_input("Nama Peralatan *", placeholder="Contoh: Gembor / Terpal", key=f"manual_alat_t_{period_id}")
                else:
                    nama_peralatan = pilih_item_alat

            with kol2:
                kol_qty, kol_satuan = st.columns([1, 1])
                with kol_qty:
                    qty = st.number_input("Kuantitas", min_value=1.0, step=1.0, value=1.0, key=f"qty_alat_t_{period_id}")
                with kol_satuan:
                    satuan_alat = st.selectbox(
                        "Satuan",
                        ["unit", "buah", "set", "meter", "roll", "paket"],
                        key=f"satuan_alat_t_{period_id}",
                    )
                harga_satuan = st.number_input("Harga Satuan (Rp)", min_value=1000, step=5000, value=50000, key=f"harga_alat_t_{period_id}")
                st.caption("Akun otomatis: **1250 - Peralatan** (Aset Tetap)")

            keterangan = st.text_input("Keterangan", placeholder="(opsional)", key=f"ket_alat_t_{period_id}")
            total = int(qty * harga_satuan)
            st.caption(f"**Total: {format_rupiah(total)}**")
            pratinjau_btn = st.form_submit_button("👁️ Pratinjau Jurnal", type="primary")

        if pratinjau_btn:
            if not nama_peralatan.strip():
                st.error("Nama peralatan wajib diisi.")
                return
            akun_peralatan_id = _cari_akun_peralatan()
            if not akun_peralatan_id:
                st.error("Akun 1250 - Peralatan tidak ditemukan dalam Bagan Akun.")
                return
            akun_kas_id = _cari_akun_by_kode("1110")
            if not akun_kas_id:
                st.error("Akun 1110 - Kas tidak ditemukan dalam Bagan Akun.")
                return

            baris = [
                {"account_id": akun_peralatan_id, "debit": total, "kredit": 0},
                {"account_id": akun_kas_id, "debit": 0, "kredit": total},
            ]
            st.session_state["pratinjau_baris"] = baris
            label_nama = f"{nama_peralatan} ({qty:g} {satuan_alat})"
            st.session_state["pratinjau_params"] = {
                "jenis": "beli_peralatan_tunai",
                "period_id": period_id,
                "tanggal": str(tanggal),
                "supplier_nama": supplier_nama,
                "nama_peralatan": label_nama,
                "qty": qty,
                "harga_satuan": harga_satuan,
                "akun_peralatan_id": akun_peralatan_id,
                "akun_kas_id": akun_kas_id,
                "keterangan": keterangan or f"Beli peralatan {label_nama} tunai - {supplier_nama}",
            }

        if "pratinjau_baris" in st.session_state and st.session_state.get("pratinjau_params", {}).get("jenis") == "beli_peralatan_tunai":
            disimpan = _tampilkan_pratinjau(
                st.session_state["pratinjau_baris"],
                st.session_state["pratinjau_params"],
            )
            if disimpan:
                try:
                    p = st.session_state["pratinjau_params"]
                    ts.catat_pembelian_peralatan_tunai(
                        period_id=p["period_id"],
                        tanggal=p["tanggal"],
                        supplier_nama=p["supplier_nama"],
                        nama_peralatan=p["nama_peralatan"],
                        qty=p["qty"],
                        harga_satuan=p["harga_satuan"],
                        akun_peralatan_id=p["akun_peralatan_id"],
                        akun_kas_id=p["akun_kas_id"],
                        keterangan=p["keterangan"],
                    )
                    st.success(f"✅ Pembelian peralatan **{p['nama_peralatan']}** tunai berhasil dicatat!")
                    _bersihkan_pratinjau()
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Gagal menyimpan: {e}")


# ================================================================
# FORM 6: PEMBELIAN KREDIT
# ================================================================

def _form_pembelian_kredit(period_id: int):
    """Form pembelian barang dagang, perlengkapan, atau peralatan secara kredit (menambah utang usaha)."""
    st.subheader("🏷️ Pembelian Barang Dagang Kredit (Utang Dagang)")

    suppliers = _ambil_suppliers()
    items_panen = _ambil_items("hasil_panen")

    kategori_pembelian = st.radio(
        "Kategori Pembelian *",
        [
            "🌶️ Barang Dagang (Cabai)",
            "📦 Perlengkapan (Bambu, Plastik Mulsa, Karung, Keranjang, dll)",
            "🔧 Peralatan (Ember, Cangkul, Sabit, Tangki Semprot, dll)",
        ],
        horizontal=True,
        key=f"kat_beli_kredit_{period_id}",
    )

    if kategori_pembelian.startswith("🌶️"):
        if not items_panen:
            st.warning("Belum ada item barang dagang cabai.")
            return

        with st.form("form_beli_kredit"):
            kol1, kol2 = st.columns(2)
            with kol1:
                tanggal = st.date_input("Tanggal", value="today")
                if suppliers:
                    supplier_idx = st.selectbox(
                        "Supplier *",
                        range(len(suppliers)),
                        format_func=lambda i: suppliers[i]["nama"],
                    )
                    supplier_nama = suppliers[supplier_idx]["nama"]
                else:
                    supplier_nama = st.text_input("Nama Supplier *")

                item_idx = st.selectbox(
                    "Item *",
                    range(len(items_panen)),
                    format_func=lambda i: f"{items_panen[i]['nama']} ({items_panen[i]['satuan']})",
                )
            with kol2:
                qty = st.number_input("Kuantitas", min_value=0.1, step=0.1, value=1.0)
                harga_satuan = st.number_input("Harga Satuan (Rp)", min_value=1000, step=500, value=10000)

                st.caption("Akun otomatis: **1140 - Persediaan Barang Dagang**")

            keterangan = st.text_input("Keterangan", placeholder="(opsional)")
            total = int(qty * harga_satuan)
            st.caption(f"**Total: {format_rupiah(total)}**")
            pratinjau_btn = st.form_submit_button("👁️ Pratinjau Jurnal", type="primary")

        if pratinjau_btn:
            item = items_panen[item_idx]
            akun_persediaan_id = item.get("account_id")
            if not akun_persediaan_id:
                st.error(
                    "Item belum terhubung ke akun 1140 - Persediaan. "
                    "Periksa Master Data > Item."
                )
                return

            akun_utang_id = _cari_akun_by_kode("2110")

            baris = [
                {"account_id": akun_persediaan_id, "debit": total, "kredit": 0},
                {"account_id": akun_utang_id, "debit": 0, "kredit": total},
            ]
            st.session_state["pratinjau_baris"] = baris
            st.session_state["pratinjau_params"] = {
                "jenis": "beli_kredit",
                "period_id": period_id,
                "tanggal": str(tanggal),
                "supplier_nama": supplier_nama,
                "item_id": item["id"],
                "qty": qty,
                "harga_satuan": harga_satuan,
                "akun_persediaan_id": akun_persediaan_id,
                "akun_utang_id": akun_utang_id,
                "keterangan": keterangan,
            }

        if "pratinjau_baris" in st.session_state and st.session_state.get("pratinjau_params", {}).get("jenis") == "beli_kredit":
            disimpan = _tampilkan_pratinjau(
                st.session_state["pratinjau_baris"],
                st.session_state["pratinjau_params"],
            )
            if disimpan:
                try:
                    p = st.session_state["pratinjau_params"]
                    ts.catat_pembelian_kredit(
                        period_id=p["period_id"], tanggal=p["tanggal"],
                        supplier_nama=p["supplier_nama"], item_id=p["item_id"],
                        qty=p["qty"], harga_satuan=p["harga_satuan"],
                        akun_persediaan_id=p["akun_persediaan_id"],
                        akun_utang_id=p["akun_utang_id"], keterangan=p["keterangan"],
                    )
                    st.success("✅ Pembelian barang dagang kredit berhasil dicatat!")
                    _bersihkan_pratinjau()
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Gagal menyimpan: {e}")

    elif kategori_pembelian.startswith("📦"):
        # Pembelian Perlengkapan Kredit (Bambu, Plastik Mulsa, Karung, Keranjang, dll)
        with st.form("form_beli_perlengkapan_kredit"):
            kol1, kol2 = st.columns(2)
            with kol1:
                tanggal = st.date_input("Tanggal", value="today")
                if suppliers:
                    supplier_idx = st.selectbox(
                        "Supplier *",
                        range(len(suppliers)),
                        format_func=lambda i: suppliers[i]["nama"],
                        key=f"supp_pk_{period_id}",
                    )
                    supplier_nama = suppliers[supplier_idx]["nama"]
                else:
                    supplier_nama = st.text_input("Nama Supplier *", key=f"supp_txt_pk_{period_id}")

                pilihan_perlengkapan = [
                    "Bambu",
                    "Plastik Mulsa",
                    "Karung",
                    "Keranjang",
                    "Lainnya (Ketik Manual)",
                ]
                pilih_item_p = st.selectbox("Jenis Perlengkapan *", options=pilihan_perlengkapan, key=f"jenis_pk_{period_id}")
                if pilih_item_p == "Lainnya (Ketik Manual)":
                    nama_perlengkapan = st.text_input("Nama Perlengkapan *", placeholder="Contoh: Ajir / Terpal", key=f"manual_pk_{period_id}")
                else:
                    nama_perlengkapan = pilih_item_p

            with kol2:
                kol_qty, kol_satuan = st.columns([1, 1])
                with kol_qty:
                    qty = st.number_input("Kuantitas", min_value=0.1, step=0.1, value=1.0, key=f"qty_pk_{period_id}")
                with kol_satuan:
                    satuan_p = st.selectbox(
                        "Satuan",
                        ["batang", "roll", "karung / lembar", "buah", "ikat", "meter", "kg", "pack"],
                        key=f"satuan_pk_{period_id}",
                    )
                harga_satuan = st.number_input("Harga Satuan (Rp)", min_value=100, step=500, value=10000, key=f"harga_pk_{period_id}")
                st.caption("Akun otomatis: **1130 - Perlengkapan** (Bukan Persediaan)")

            keterangan = st.text_input("Keterangan", placeholder="(opsional)", key=f"ket_pk_{period_id}")
            total = int(qty * harga_satuan)
            st.caption(f"**Total: {format_rupiah(total)}** | Jatuh tempo standar 30 hari")
            pratinjau_btn = st.form_submit_button("👁️ Pratinjau Jurnal", type="primary")

        if pratinjau_btn:
            if not supplier_nama:
                st.error("Nama supplier wajib diisi.")
                return
            if not nama_perlengkapan.strip():
                st.error("Nama perlengkapan wajib diisi.")
                return
            akun_perlengkapan_id = _cari_akun_by_kode("1130")
            if not akun_perlengkapan_id:
                st.error("Akun 1130 - Perlengkapan tidak ditemukan dalam Bagan Akun.")
                return
            akun_utang_id = _cari_akun_by_kode("2110")
            if not akun_utang_id:
                st.error("Akun 2110 - Utang Usaha tidak ditemukan dalam Bagan Akun.")
                return

            baris = [
                {"account_id": akun_perlengkapan_id, "debit": total, "kredit": 0},
                {"account_id": akun_utang_id, "debit": 0, "kredit": total},
            ]
            st.session_state["pratinjau_baris"] = baris
            label_nama = f"{nama_perlengkapan} ({qty:g} {satuan_p})"
            st.session_state["pratinjau_params"] = {
                "jenis": "beli_perlengkapan_kredit",
                "period_id": period_id,
                "tanggal": str(tanggal),
                "supplier_nama": supplier_nama,
                "nama_perlengkapan": label_nama,
                "qty": qty,
                "harga_satuan": harga_satuan,
                "akun_perlengkapan_id": akun_perlengkapan_id,
                "akun_utang_id": akun_utang_id,
                "keterangan": keterangan or f"Beli kredit perlengkapan {label_nama} dari {supplier_nama}",
            }

        if "pratinjau_baris" in st.session_state and st.session_state.get("pratinjau_params", {}).get("jenis") == "beli_perlengkapan_kredit":
            disimpan = _tampilkan_pratinjau(
                st.session_state["pratinjau_baris"],
                st.session_state["pratinjau_params"],
            )
            if disimpan:
                try:
                    p = st.session_state["pratinjau_params"]
                    ts.catat_pembelian_perlengkapan_kredit(
                        period_id=p["period_id"],
                        tanggal=p["tanggal"],
                        supplier_nama=p["supplier_nama"],
                        nama_perlengkapan=p["nama_perlengkapan"],
                        qty=p["qty"],
                        harga_satuan=p["harga_satuan"],
                        akun_perlengkapan_id=p["akun_perlengkapan_id"],
                        akun_utang_id=p["akun_utang_id"],
                        keterangan=p["keterangan"],
                    )
                    st.success(f"✅ Pembelian kredit perlengkapan **{p['nama_perlengkapan']}** berhasil dicatat!")
                    _bersihkan_pratinjau()
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Gagal menyimpan: {e}")

    else:
        # Pembelian Peralatan Kredit (Ember, Cangkul, Sabit, Tangki Semprot, Timbangan, Pompa Air, Selang Air, dll)
        with st.form("form_beli_peralatan_kredit"):
            kol1, kol2 = st.columns(2)
            with kol1:
                tanggal = st.date_input("Tanggal", value="today")
                if suppliers:
                    supplier_idx = st.selectbox(
                        "Supplier *",
                        range(len(suppliers)),
                        format_func=lambda i: suppliers[i]["nama"],
                        key=f"supp_alat_k_{period_id}",
                    )
                    supplier_nama = suppliers[supplier_idx]["nama"]
                else:
                    supplier_nama = st.text_input("Nama Supplier *", key=f"supp_txt_alat_k_{period_id}")

                pilihan_peralatan = [
                    "Ember",
                    "Cangkul",
                    "Sabit",
                    "Tangki Semprot",
                    "Timbangan",
                    "Pompa Air",
                    "Selang Air",
                    "Lainnya (Ketik Manual)",
                ]
                pilih_item_alat = st.selectbox("Jenis Peralatan *", options=pilihan_peralatan, key=f"jenis_alat_k_{period_id}")
                if pilih_item_alat == "Lainnya (Ketik Manual)":
                    nama_peralatan = st.text_input("Nama Peralatan *", placeholder="Contoh: Gembor / Terpal", key=f"manual_alat_k_{period_id}")
                else:
                    nama_peralatan = pilih_item_alat

            with kol2:
                kol_qty, kol_satuan = st.columns([1, 1])
                with kol_qty:
                    qty = st.number_input("Kuantitas", min_value=1.0, step=1.0, value=1.0, key=f"qty_alat_k_{period_id}")
                with kol_satuan:
                    satuan_alat = st.selectbox(
                        "Satuan",
                        ["unit", "buah", "set", "meter", "roll", "paket"],
                        key=f"satuan_alat_k_{period_id}",
                    )
                harga_satuan = st.number_input("Harga Satuan (Rp)", min_value=1000, step=5000, value=50000, key=f"harga_alat_k_{period_id}")
                st.caption("Akun otomatis: **1250 - Peralatan** (Aset Tetap)")

            keterangan = st.text_input("Keterangan", placeholder="(opsional)", key=f"ket_alat_k_{period_id}")
            total = int(qty * harga_satuan)
            st.caption(f"**Total: {format_rupiah(total)}** | Jatuh tempo standar 30 hari")
            pratinjau_btn = st.form_submit_button("👁️ Pratinjau Jurnal", type="primary")

        if pratinjau_btn:
            if not supplier_nama:
                st.error("Nama supplier wajib diisi.")
                return
            if not nama_peralatan.strip():
                st.error("Nama peralatan wajib diisi.")
                return
            akun_peralatan_id = _cari_akun_peralatan()
            if not akun_peralatan_id:
                st.error("Akun 1250 - Peralatan tidak ditemukan dalam Bagan Akun.")
                return
            akun_utang_id = _cari_akun_by_kode("2110")
            if not akun_utang_id:
                st.error("Akun 2110 - Utang Usaha tidak ditemukan dalam Bagan Akun.")
                return

            baris = [
                {"account_id": akun_peralatan_id, "debit": total, "kredit": 0},
                {"account_id": akun_utang_id, "debit": 0, "kredit": total},
            ]
            st.session_state["pratinjau_baris"] = baris
            label_nama = f"{nama_peralatan} ({qty:g} {satuan_alat})"
            st.session_state["pratinjau_params"] = {
                "jenis": "beli_peralatan_kredit",
                "period_id": period_id,
                "tanggal": str(tanggal),
                "supplier_nama": supplier_nama,
                "nama_peralatan": label_nama,
                "qty": qty,
                "harga_satuan": harga_satuan,
                "akun_peralatan_id": akun_peralatan_id,
                "akun_utang_id": akun_utang_id,
                "keterangan": keterangan or f"Beli kredit peralatan {label_nama} dari {supplier_nama}",
            }

        if "pratinjau_baris" in st.session_state and st.session_state.get("pratinjau_params", {}).get("jenis") == "beli_peralatan_kredit":
            disimpan = _tampilkan_pratinjau(
                st.session_state["pratinjau_baris"],
                st.session_state["pratinjau_params"],
            )
            if disimpan:
                try:
                    p = st.session_state["pratinjau_params"]
                    ts.catat_pembelian_peralatan_kredit(
                        period_id=p["period_id"],
                        tanggal=p["tanggal"],
                        supplier_nama=p["supplier_nama"],
                        nama_peralatan=p["nama_peralatan"],
                        qty=p["qty"],
                        harga_satuan=p["harga_satuan"],
                        akun_peralatan_id=p["akun_peralatan_id"],
                        akun_utang_id=p["akun_utang_id"],
                        keterangan=p["keterangan"],
                    )
                    st.success(f"✅ Pembelian kredit peralatan **{p['nama_peralatan']}** berhasil dicatat!")
                    _bersihkan_pratinjau()
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Gagal menyimpan: {e}")


# ================================================================
# FORM 7: CATAT PANEN
# ================================================================

def _form_catat_panen(period_id: int):
    """Form pencatatan hasil panen masuk persediaan."""
    st.subheader("🌶️ Catat Hasil Panen")

    items_panen = _ambil_items("hasil_panen")
    blok_list = _ambil_blok_lahan()

    if not items_panen:
        st.warning("Belum ada data item hasil panen. Tambahkan di Master Data > Item.")
        return

    # Akun persediaan panen (kode 1140 = Persediaan, COA baru)
    # Gunakan semua akun Aset yang kodenya dimulai "114" (Persediaan COA baru)
    akun_panen_opts = [a for a in _ambil_akun("Aset") if a["kode_akun"].startswith("114")]
    # Fallback: jika tidak ada, tampilkan semua akun Aset
    if not akun_panen_opts:
        akun_panen_opts = _ambil_akun("Aset")

    with st.form("form_panen"):
        kol1, kol2 = st.columns(2)
        with kol1:
            tanggal = st.date_input("Tanggal Panen", value="today")
            item_idx = st.selectbox(
                "Jenis Hasil Panen *",
                range(len(items_panen)),
                format_func=lambda i: items_panen[i]["nama"],
            )
            if blok_list:
                blok_idx = st.selectbox(
                    "Blok Lahan",
                    range(len(blok_list)),
                    format_func=lambda i: f"Blok {blok_list[i]['kode']}",
                )
                blok_nama = f"Blok {blok_list[blok_idx]['kode']}"
            else:
                blok_nama = st.text_input("Blok Lahan", "")
        with kol2:
            jumlah_kg = st.number_input("Hasil Panen (kg)", min_value=0.1, step=0.1, value=1.0)
            harga_estimasi = st.number_input(
                "Estimasi Harga Pokok/kg (Rp)", min_value=1000, step=500, value=25000
            )
            if akun_panen_opts:
                akun_panen_idx = st.selectbox(
                    "Akun Persediaan Panen",
                    range(len(akun_panen_opts)),
                    format_func=lambda i: f"{akun_panen_opts[i]['kode_akun']} - {akun_panen_opts[i]['nama_akun']}",
                )
                akun_panen_id = akun_panen_opts[akun_panen_idx]["id"]
            else:
                akun_panen_id = None

        keterangan = st.text_input("Keterangan", placeholder="(opsional)")
        total = int(jumlah_kg * harga_estimasi)
        st.caption(f"**Nilai Panen: {format_rupiah(total)}**")
        pratinjau_btn = st.form_submit_button("👁️ Pratinjau Jurnal", type="primary")

    if pratinjau_btn:
        if not akun_panen_id:
            st.error("Pilih akun persediaan panen.")
            return

        item = items_panen[item_idx]
        # Akun lawan panen: HPP (5110) sebagai akun lawan saat mencatat panen ke persediaan
        # sesuai COA baru: Panen → Dr Persediaan (1140) / Kr HPP (5110)
        akun_hpp_id = _cari_akun_by_kode("5110")
        if not akun_hpp_id:
            hpp_list = _ambil_akun("HPP")
            akun_hpp_id = hpp_list[0]["id"] if hpp_list else None

        if not akun_hpp_id:
            st.error("Akun Harga Pokok Penjualan (5110) tidak ditemukan. Periksa master data.")
            return

        baris = [
            {"account_id": akun_panen_id, "debit": total, "kredit": 0},
            {"account_id": akun_hpp_id, "debit": 0, "kredit": total},
        ]
        st.session_state["pratinjau_baris"] = baris
        st.session_state["pratinjau_params"] = {
            "jenis": "panen",
            "period_id": period_id,
            "tanggal": str(tanggal),
            "item_panen_id": item["id"],
            "jumlah_kg": jumlah_kg,
            "harga_estimasi_per_kg": harga_estimasi,
            "akun_persediaan_panen_id": akun_panen_id,
            "akun_hpp_panen_id": akun_hpp_id,
            "blok_nama": blok_nama,
            "keterangan": keterangan,
        }

    if "pratinjau_baris" in st.session_state and st.session_state.get("pratinjau_params", {}).get("jenis") == "panen":
        disimpan = _tampilkan_pratinjau(
            st.session_state["pratinjau_baris"],
            st.session_state["pratinjau_params"],
        )
        if disimpan:
            try:
                p = st.session_state["pratinjau_params"]
                ts.catat_panen(
                    period_id=p["period_id"], tanggal=p["tanggal"],
                    item_panen_id=p["item_panen_id"], jumlah_kg=p["jumlah_kg"],
                    harga_estimasi_per_kg=p["harga_estimasi_per_kg"],
                    akun_persediaan_panen_id=p["akun_persediaan_panen_id"],
                    akun_hpp_panen_id=p["akun_hpp_panen_id"],
                    blok_nama=p["blok_nama"], keterangan=p["keterangan"],
                )
                st.success(f"✅ Panen {p['jumlah_kg']} kg berhasil dicatat!")
                _bersihkan_pratinjau()
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Gagal menyimpan: {e}")


# ================================================================
# FORM 8: BIAYA OPERASIONAL
# ================================================================

def _form_biaya_operasional(period_id: int):
    """Form pencatatan biaya operasional (listrik, BBM, sewa traktor)."""
    st.subheader("⚡ Biaya Operasional")

    # Mapping jenis biaya ke kode akun (sesuai COA baru)
    JENIS_BIAYA = {
        "Listrik": "6130",           # Beban Air, Listrik, dan Telepon
        "BBM Pengiriman": "6140",    # Beban BBM Pengiriman
        "BBM Operasional": "6150",   # Beban BBM Operasional
        "Sewa Traktor": "6120",      # Beban Sewa
        "Upah Tenaga Kerja": "6110", # Beban Gaji
        "Lainnya": None,
    }

    with st.form("form_biaya_ops"):
        kol1, kol2 = st.columns(2)
        with kol1:
            tanggal = st.date_input("Tanggal", value="today")
            jenis = st.selectbox("Jenis Biaya *", list(JENIS_BIAYA.keys()))
            jumlah = st.number_input("Jumlah (Rp)", min_value=1000, step=1000, value=100000)
        with kol2:
            # Jika 'Lainnya', biarkan user pilih akun sendiri
            if jenis == "Lainnya":
                akun_beban_opts = _ambil_akun("Beban Operasional") + _ambil_akun("HPP") + _ambil_akun("Beban Lainnya")
                akun_beban_idx = st.selectbox(
                    "Akun Beban *",
                    range(len(akun_beban_opts)),
                    format_func=lambda i: f"{akun_beban_opts[i]['kode_akun']} - {akun_beban_opts[i]['nama_akun']}",
                )
                akun_beban_id = akun_beban_opts[akun_beban_idx]["id"] if akun_beban_opts else None
            else:
                kode_akun = JENIS_BIAYA[jenis]
                akun_beban_id = _cari_akun_by_kode(kode_akun) if kode_akun else None
                st.caption(f"Akun beban: **{kode_akun}** (otomatis)")

        keterangan = st.text_input("Keterangan", placeholder="(opsional)")
        pratinjau_btn = st.form_submit_button("👁️ Pratinjau Jurnal", type="primary")

    if pratinjau_btn:
        if not akun_beban_id:
            st.error("Akun beban tidak ditemukan. Periksa master data COA.")
            return

        akun_kas_id = _cari_akun_by_kode("1110")

        baris = [
            {"account_id": akun_beban_id, "debit": jumlah, "kredit": 0},
            {"account_id": akun_kas_id, "debit": 0, "kredit": jumlah},
        ]
        st.session_state["pratinjau_baris"] = baris
        st.session_state["pratinjau_params"] = {
            "jenis": "biaya_operasional",
            "period_id": period_id,
            "tanggal": str(tanggal),
            "jenis_biaya": jenis,
            "jumlah": jumlah,
            "akun_beban_id": akun_beban_id,
            "akun_kas_id": akun_kas_id,
            "keterangan": keterangan,
        }

    if "pratinjau_baris" in st.session_state and st.session_state.get("pratinjau_params", {}).get("jenis") == "biaya_operasional":
        disimpan = _tampilkan_pratinjau(
            st.session_state["pratinjau_baris"],
            st.session_state["pratinjau_params"],
        )
        if disimpan:
            try:
                p = st.session_state["pratinjau_params"]
                ts.catat_biaya_operasional(
                    period_id=p["period_id"], tanggal=p["tanggal"],
                    jenis_biaya=p["jenis_biaya"], jumlah=p["jumlah"],
                    akun_beban_id=p["akun_beban_id"], akun_kas_id=p["akun_kas_id"],
                    keterangan=p["keterangan"],
                )
                st.success(f"✅ Biaya {p['jenis_biaya']} {format_rupiah(p['jumlah'])} berhasil dicatat!")
                _bersihkan_pratinjau()
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Gagal menyimpan: {e}")


# ================================================================
# FORM 9: PEMBELIAN ASET
# ================================================================

def _form_pembelian_aset(period_id: int):
    """Form pembelian perlengkapan & aset secara tunai."""
    st.subheader("🏗️ Pembelian Perlengkapan & Aset")

    # Akun perlengkapan & aset tetap COA baru: 1130 (Perlengkapan) dan 12xx (Aset Tetap)
    # Tidak termasuk akun kontra/akumulasi
    akun_aset_opts = [
        a for a in _ambil_akun("Aset")
        if (a["kode_akun"].startswith("12") or a["kode_akun"] == "1130")
        and not a.get("is_kontra")
    ]

    with st.form("form_beli_aset"):
        kol1, kol2 = st.columns(2)
        with kol1:
            tanggal = st.date_input("Tanggal", value="today")
            nama_aset = st.text_input("Nama Barang / Aset *", placeholder="Contoh: Bambu Penyangga / Pompa Air")
            jumlah = st.number_input("Total Pembelian (Rp)", min_value=1000, step=50000, value=1000000)
        with kol2:
            if akun_aset_opts:
                akun_aset_idx = st.selectbox(
                    "Akun Tujuan *",
                    range(len(akun_aset_opts)),
                    format_func=lambda i: f"{akun_aset_opts[i]['kode_akun']} - {akun_aset_opts[i]['nama_akun']}",
                )
                akun_aset_id = akun_aset_opts[akun_aset_idx]["id"]
            else:
                akun_aset_id = None
                st.warning("Akun perlengkapan/aset tidak ditemukan.")

        keterangan = st.text_input("Keterangan", placeholder="(opsional)")
        pratinjau_btn = st.form_submit_button("👁️ Pratinjau Jurnal", type="primary")

    if pratinjau_btn:
        if not nama_aset:
            st.error("Nama aset wajib diisi.")
            return
        if not akun_aset_id:
            st.error("Pilih akun aset tetap.")
            return

        akun_kas_id = _cari_akun_by_kode("1110")

        baris = [
            {"account_id": akun_aset_id, "debit": jumlah, "kredit": 0},
            {"account_id": akun_kas_id, "debit": 0, "kredit": jumlah},
        ]
        st.session_state["pratinjau_baris"] = baris
        st.session_state["pratinjau_params"] = {
            "jenis": "beli_aset",
            "period_id": period_id,
            "tanggal": str(tanggal),
            "nama_aset": nama_aset,
            "jumlah": jumlah,
            "akun_aset_id": akun_aset_id,
            "akun_kas_id": akun_kas_id,
            "keterangan": keterangan,
        }

    if "pratinjau_baris" in st.session_state and st.session_state.get("pratinjau_params", {}).get("jenis") == "beli_aset":
        disimpan = _tampilkan_pratinjau(
            st.session_state["pratinjau_baris"],
            st.session_state["pratinjau_params"],
        )
        if disimpan:
            try:
                p = st.session_state["pratinjau_params"]
                ts.catat_pembelian_aset(
                    period_id=p["period_id"], tanggal=p["tanggal"],
                    nama_aset=p["nama_aset"], jumlah=p["jumlah"],
                    akun_aset_id=p["akun_aset_id"], akun_kas_id=p["akun_kas_id"],
                    keterangan=p["keterangan"],
                )
                st.success(f"✅ Pembelian aset **{p['nama_aset']}** berhasil dicatat!")
                _bersihkan_pratinjau()
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Gagal menyimpan: {e}")


# ================================================================
# HALAMAN UTAMA
# ================================================================

def tampilkan() -> None:
    """Fungsi utama halaman Input Transaksi."""
    st.title("✏️ Input Transaksi")
    st.caption("Pilih jenis transaksi, isi form, lalu pratinjau jurnal sebelum disimpan.")

    # Pilih periode aktif
    kol_periode, _ = st.columns([2, 2])
    with kol_periode:
        period_id = selector_periode(
            label="📅 Periode Transaksi Aktif",
            key="input_transaksi_periode",
            hanya_buka=True,
            tampilkan_kalender=True,
            help="Pilih periode pembukuan transaksi (otomatis membuat periode jika memilih tanggal baru)",
        )

    if not period_id:
        st.error("Silakan pilih periode transaksi.")
        return

    st.divider()

    # Navigasi jenis transaksi dengan segmented
    kelompok = sac.segmented(
        items=[
            sac.SegmentedItem(label="Penjualan", icon="cart-check"),
            sac.SegmentedItem(label="Pembelian", icon="cart-plus"),
            sac.SegmentedItem(label="Kas", icon="cash-coin"),
            sac.SegmentedItem(label="Persediaan", icon="box-seam"),
            sac.SegmentedItem(label="Lainnya", icon="three-dots"),
        ],
        label="Kelompok Transaksi",
        color=WARNA_PRIMER,
        return_index=False,
        key="kelompok_transaksi",
    )

    # Reset pratinjau jika ganti kelompok
    if st.session_state.get("_kelompok_terakhir") != kelompok:
        _bersihkan_pratinjau()
        st.session_state["_kelompok_terakhir"] = kelompok

    st.divider()

    # Tampilkan form sesuai kelompok
    if kelompok == "Penjualan":
        tab1, tab2 = st.tabs(["💵 Penjualan Tunai", "📋 Penjualan Tempo"])
        with tab1:
            _form_penjualan_tunai(period_id)
        with tab2:
            _form_penjualan_tempo(period_id)

    elif kelompok == "Pembelian":
        tab1, tab2 = st.tabs(["🛒 Barang Dagang Tunai", "🏷️ Barang Dagang Kredit"])
        with tab1:
            _form_pembelian_barang_dagang_tunai(period_id)
        with tab2:
            _form_pembelian_kredit(period_id)

    elif kelompok == "Kas":
        tab1, tab2 = st.tabs(["💰 Terima Pelunasan Piutang", "💼 Setoran Modal"])
        with tab1:
            _form_terima_piutang(period_id)
        with tab2:
            _form_setoran_modal(period_id)

    elif kelompok == "Persediaan":
        _form_catat_panen(period_id)

    elif kelompok == "Lainnya":
        tab1, tab2 = st.tabs(["⚡ Biaya Operasional", "🏗️ Pembelian Aset"])
        with tab1:
            _form_biaya_operasional(period_id)
        with tab2:
            _form_pembelian_aset(period_id)


# Panggil fungsi utama
tampilkan()
