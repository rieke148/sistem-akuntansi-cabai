import sys
sys.path.insert(0, r"c:\Users\rieke\code-project\sistem-akuntansi-cabai\sistem-akuntansi-cabai")

import services.dashboard_service as ds
import pandas as pd

pid = ds.ambil_period_id_aktif()
print(f"Active period: {pid}")

info = ds.ambil_info_periode(pid)
print(f"Info periode: {info}")

kas = ds.ambil_saldo_kas_bank(pid)
print(f"Kas & bank: {kas}")

pv = ds.ambil_ringkasan_penjualan_beban(pid)
print(f"Penjualan vs beban: {pv}")

stok = ds.ambil_stok_persediaan()
print(f"Stok persediaan ({len(stok)} items): {stok[:2]}")

ringkasan = ds.ambil_ringkasan_jurnal(pid)
print(f"Ringkasan jurnal: {ringkasan}")

overdue = ds.ambil_piutang_overdue()
print(f"Overdue ({len(overdue)} items): {overdue}")

progress = ds.cek_progress_siklus(pid)
print(f"Progress siklus: {progress}")

komoditas_df = ds.ambil_penjualan_per_komoditas(pid)
print(f"Penjualan per komoditas:\n{komoditas_df}")

# Test Altair chart creation directly
import altair as alt
peta_nama = {
    "cabai": "🌶️ Cabai",
    "selada": "🥬 Selada",
    "melon": "🍈 Melon",
    "umum": "📦 Umum",
}
komoditas_df["komoditas_label"] = komoditas_df["komoditas"].map(lambda x: peta_nama.get(x, x))
chart_data = komoditas_df.set_index("komoditas_label")["penjualan"]
print("Chart data index:", chart_data.index.tolist())
print("Chart data values:", chart_data.values.tolist())
