import sys
sys.path.insert(0, r"c:\Users\rieke\code-project\sistem-akuntansi-cabai\sistem-akuntansi-cabai")

import pandas as pd
import services.statements_service as ss
from utils.formatting import format_rupiah

period_id = 1

# 1. Laba Rugi
lr = ss.susun_laporan_laba_rugi(period_id)
baris_lr = []
baris_lr.append({"Komponen": "PENDAPATAN", "Akun": "", "Jumlah": ""})
for it in lr["pendapatan"]:
    baris_lr.append({"Komponen": "Pendapatan", "Akun": it["nama_akun"], "Jumlah": it["jumlah"]})
baris_lr.append({"Komponen": "Total Pendapatan", "Akun": "", "Jumlah": lr["total_pendapatan"]})

baris_lr.append({"Komponen": "BEBAN PRODUKSI", "Akun": "", "Jumlah": ""})
for it in lr["beban_produksi"]:
    baris_lr.append({"Komponen": "Beban Produksi", "Akun": it["nama_akun"], "Jumlah": it["jumlah"]})
baris_lr.append({"Komponen": "Total Beban Produksi", "Akun": "", "Jumlah": lr["total_beban_produksi"]})

baris_lr.append({"Komponen": "BEBAN OPERASIONAL", "Akun": "", "Jumlah": ""})
for it in lr["beban_operasional"]:
    baris_lr.append({"Komponen": "Beban Operasional", "Akun": it["nama_akun"], "Jumlah": it["jumlah"]})
baris_lr.append({"Komponen": "Total Beban Operasional", "Akun": "", "Jumlah": lr["total_beban_operasional"]})

baris_lr.append({"Komponen": "TOTAL BEBAN", "Akun": "", "Jumlah": lr["total_beban"]})
baris_lr.append({"Komponen": "LABA BERSIH", "Akun": "", "Jumlah": lr["laba_bersih"]})
df_lr = pd.DataFrame(baris_lr)
print("=== DF LABA RUGI ===")
print(df_lr.head(10))

# 2. Perubahan Ekuitas
pe = ss.susun_laporan_perubahan_ekuitas(period_id, lr["laba_bersih"])
baris_pe = []
for it in pe["detail"]:
    baris_pe.append({"Keterangan": it["keterangan"], "Jumlah": it["jumlah"]})
df_pe = pd.DataFrame(baris_pe)
print("\n=== DF PERUBAHAN EKUITAS ===")
print(df_pe)

# 3. Neraca
neraca = ss.susun_neraca(period_id, pe["modal_akhir"])
baris_neraca = []
baris_neraca.append({"Kategori": "ASET LANCAR", "Akun": "", "Jumlah": ""})
for it in neraca["aset_lancar"]:
    baris_neraca.append({"Kategori": "Aset Lancar", "Akun": it["nama_akun"], "Jumlah": it["jumlah"]})
baris_neraca.append({"Kategori": "Total Aset Lancar", "Akun": "", "Jumlah": neraca["total_aset_lancar"]})

baris_neraca.append({"Kategori": "ASET TETAP", "Akun": "", "Jumlah": ""})
for it in neraca["aset_tetap"]:
    baris_neraca.append({"Kategori": "Aset Tetap", "Akun": it["nama_akun"], "Jumlah": it["jumlah"]})
baris_neraca.append({"Kategori": "Total Aset Tetap", "Akun": "", "Jumlah": neraca["total_aset_tetap"]})
baris_neraca.append({"Kategori": "TOTAL ASET", "Akun": "", "Jumlah": neraca["total_aset"]})

baris_neraca.append({"Kategori": "LIABILITAS", "Akun": "", "Jumlah": ""})
for it in neraca["liabilitas_lancar"]:
    baris_neraca.append({"Kategori": "Liabilitas Lancar", "Akun": it["nama_akun"], "Jumlah": it["jumlah"]})
for it in neraca["liabilitas_jangka_panjang"]:
    baris_neraca.append({"Kategori": "Liabilitas Jangka Panjang", "Akun": it["nama_akun"], "Jumlah": it["jumlah"]})
baris_neraca.append({"Kategori": "Total Liabilitas", "Akun": "", "Jumlah": neraca["total_liabilitas"]})

baris_neraca.append({"Kategori": "EKUITAS", "Akun": "", "Jumlah": ""})
for it in neraca["ekuitas"]:
    baris_neraca.append({"Kategori": "Ekuitas", "Akun": it["nama_akun"], "Jumlah": it["jumlah"]})
baris_neraca.append({"Kategori": "TOTAL LIABILITAS & EKUITAS", "Akun": "", "Jumlah": neraca["total_liabilitas_ekuitas"]})
df_neraca = pd.DataFrame(baris_neraca)
print("\n=== DF NERACA ===")
print(df_neraca.head(10))

# 4. Arus Kas
ak = ss.susun_arus_kas(period_id)
baris_ak = []
baris_ak.append({"Aktivitas": "ARUS KAS DARI AKTIVITAS OPERASI", "Keterangan": "", "Jumlah": ""})
for it in ak["operasi"]["penerimaan"]:
    baris_ak.append({"Aktivitas": "Operasi (Masuk)", "Keterangan": it["keterangan"], "Jumlah": it["jumlah"]})
for it in ak["operasi"]["pengeluaran"]:
    baris_ak.append({"Aktivitas": "Operasi (Keluar)", "Keterangan": it["keterangan"], "Jumlah": -it["jumlah"]})
baris_ak.append({"Aktivitas": "Arus Kas Bersih dari Aktivitas Operasi", "Keterangan": "", "Jumlah": ak["operasi"]["neto"]})

baris_ak.append({"Aktivitas": "ARUS KAS DARI AKTIVITAS INVESTASI", "Keterangan": "", "Jumlah": ""})
for it in ak["investasi"]["pengeluaran"]:
    baris_ak.append({"Aktivitas": "Investasi (Keluar)", "Keterangan": it["keterangan"], "Jumlah": -it["jumlah"]})
baris_ak.append({"Aktivitas": "Arus Kas Bersih dari Aktivitas Investasi", "Keterangan": "", "Jumlah": ak["investasi"]["neto"]})

baris_ak.append({"Aktivitas": "ARUS KAS DARI AKTIVITAS PENDANAAN", "Keterangan": "", "Jumlah": ""})
for it in ak["pendanaan"]["penerimaan"]:
    baris_ak.append({"Aktivitas": "Pendanaan (Masuk)", "Keterangan": it["keterangan"], "Jumlah": it["jumlah"]})
baris_ak.append({"Aktivitas": "Arus Kas Bersih dari Aktivitas Pendanaan", "Keterangan": "", "Jumlah": ak["pendanaan"]["neto"]})

baris_ak.append({"Aktivitas": "KENAIKAN (PENURUNAN) KAS BERSIH", "Keterangan": "", "Jumlah": ak["kenaikan_penurunan_kas"]})
baris_ak.append({"Aktivitas": "SALDO KAS AWAL", "Keterangan": "", "Jumlah": ak["saldo_kas_awal"]})
baris_ak.append({"Aktivitas": "SALDO KAS AKHIR", "Keterangan": "", "Jumlah": ak["saldo_kas_akhir"]})
df_ak = pd.DataFrame(baris_ak)
print("\n=== DF ARUS KAS ===")
print(df_ak.head(10))
