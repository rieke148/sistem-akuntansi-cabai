"""
views/07_buku_besar.py
-----------------------
Tujuan  : Menampilkan Buku Besar per akun dengan saldo berjalan.
          "Posting" dari jurnal ke buku besar dihitung dinamis dari journal_lines.
Input   : Pilihan akun (dropdown), filter periode.
Output  : Tabel buku besar dengan saldo berjalan + metrik saldo akhir.
Dipanggil oleh : app.py (st.navigation)

KONSEP BUKU BESAR:
  Buku Besar (General Ledger) menampilkan seluruh transaksi per akun
  secara kronologis dengan kolom saldo berjalan.
  Saldo bergerak sesuai saldo normal:
  - Akun Debit (Aset, Beban): saldo += debit - kredit
  - Akun Kredit (Liab, Ekuitas, Pendapatan): saldo += kredit - debit
"""

import streamlit as st
import pandas as pd
from database.connection import get_connection
from services.ledger_service import ambil_buku_besar, ambil_saldo_akun
from utils.formatting import format_rupiah, format_tanggal
from utils.ui_components import selector_periode


@st.cache_data(ttl=30)
def _ambil_daftar_akun() -> list[dict]:
    """Ambil semua akun dari database untuk dropdown."""
    koneksi = get_connection()
    rows = koneksi.execute(
        """
        SELECT id, kode_akun, nama_akun, saldo_normal
        FROM accounts
        ORDER BY kode_akun
        """
    ).fetchall()
    koneksi.close()
    return [dict(r) for r in rows]


@st.cache_data(ttl=30)
def _ambil_daftar_periode() -> list[dict]:
    """Ambil semua periode dari database."""
    koneksi = get_connection()
    rows = koneksi.execute(
        "SELECT id, tahun, bulan, nama_bulan FROM periods ORDER BY tahun, bulan"
    ).fetchall()
    koneksi.close()
    return [dict(r) for r in rows]


def _tampilkan_tabel_buku_besar(df: pd.DataFrame) -> None:
    """
    Tampilkan tabel buku besar dengan format yang rapi.
    Baris 'Saldo Awal' ditampilkan dengan latar berbeda (styling).
    """
    if df.empty:
        st.info("Tidak ada transaksi untuk akun dan periode yang dipilih.")
        return

    df_tampil = df.copy()

    # Format tanggal
    df_tampil["tanggal"] = df_tampil["tanggal"].apply(
        lambda t: format_tanggal(t) if t != "-" else "Saldo Awal"
    )

    # Format angka uang — debit & kredit (0 ditampilkan kosong)
    df_tampil["debit"] = df_tampil["debit"].apply(
        lambda x: format_rupiah(x) if x > 0 else "-"
    )
    df_tampil["kredit"] = df_tampil["kredit"].apply(
        lambda x: format_rupiah(x) if x > 0 else "-"
    )
    df_tampil["saldo"] = df_tampil["saldo"].apply(format_rupiah)

    # Rename kolom
    df_tampil = df_tampil.rename(columns={
        "tanggal": "Tanggal",
        "no_bukti": "No. Bukti",
        "keterangan": "Keterangan",
        "debit": "Debit",
        "kredit": "Kredit",
        "saldo": "Saldo",
    })

    st.dataframe(df_tampil, use_container_width=True, hide_index=True)


def tampilkan() -> None:
    """Fungsi utama halaman Buku Besar."""
    st.title("📖 Buku Besar")
    st.caption(
        "Posting transaksi dari jurnal ke buku besar per akun (saldo berjalan). "
        "Pilih akun dan periode untuk melihat detail."
    )

    # Ambil data dropdown
    semua_akun = _ambil_daftar_akun()
    semua_periode = _ambil_daftar_periode()

    if not semua_akun:
        st.warning("⚠️ Belum ada akun. Tambahkan akun di Master Data → Bagan Akun.")
        return

    # Susun filter di sidebar / kolom atas
    kol_akun, kol_periode = st.columns([2, 1])

    with kol_akun:
        # Dropdown akun: tampilkan kode + nama + saldo normal
        opsi_akun = {
            f"{a['kode_akun']} - {a['nama_akun']} [{a['saldo_normal']}]": a
            for a in semua_akun
        }
        akun_dipilih_key = st.selectbox(
            "Pilih Akun",
            list(opsi_akun.keys()),
            help="Pilih akun untuk melihat buku besarnya"
        )
        akun_dipilih = opsi_akun[akun_dipilih_key]
        account_id = akun_dipilih["id"]

    with kol_periode:
        period_id = selector_periode(
            label="Periode Buku Besar",
            key="buku_besar_periode",
            hanya_buka=False,
            izinkan_semua=True,
            tampilkan_kalender=True,
        )

    sertakan_saldo_awal = st.checkbox(
        "Tampilkan baris Saldo Awal",
        value=True,
        help="Jika dicentang, baris pertama menampilkan saldo awal dari opening balances"
    )

    st.divider()

    # Ambil dan tampilkan buku besar
    df = ambil_buku_besar(
        account_id=account_id,
        period_id=period_id,
        sertakan_saldo_awal=sertakan_saldo_awal,
    )

    # Hitung saldo akhir dan tampilkan metrik
    saldo_akhir = ambil_saldo_akun(account_id, period_id=period_id)
    jumlah_transaksi = len(df) - (1 if sertakan_saldo_awal else 0)

    # Tampilkan nama akun + metrik
    st.subheader(f"📋 {akun_dipilih['kode_akun']} — {akun_dipilih['nama_akun']}")

    kol_m1, kol_m2, kol_m3 = st.columns(3)
    with kol_m1:
        st.metric(
            label="💰 Saldo Akhir",
            value=format_rupiah(saldo_akhir),
            help=f"Saldo normal: {akun_dipilih['saldo_normal']}"
        )
    with kol_m2:
        # Hitung total debit dari journal_lines (tidak termasuk baris saldo awal)
        df_transaksi = df[df["no_bukti"] != "-"] if not df.empty else df
        total_debit = int(df_transaksi["debit"].sum()) if not df_transaksi.empty else 0
        st.metric(
            label="⬆ Total Debit",
            value=format_rupiah(total_debit),
        )
    with kol_m3:
        total_kredit = int(df_transaksi["kredit"].sum()) if not df_transaksi.empty else 0
        st.metric(
            label="⬇ Total Kredit",
            value=format_rupiah(total_kredit),
        )

    if jumlah_transaksi >= 0:
        st.caption(f"📌 Ditemukan **{max(0, jumlah_transaksi)} transaksi** untuk akun dan periode yang dipilih.")

    # Tampilkan tabel
    _tampilkan_tabel_buku_besar(df)

    # Tombol cetak / export (placeholder untuk Fase 7)
    st.divider()
    st.caption(
        "💡 **Tip:** Gunakan menu Export di Fase 7 untuk mengunduh buku besar "
        "dalam format Excel atau PDF."
    )


# Panggil fungsi utama
tampilkan()
