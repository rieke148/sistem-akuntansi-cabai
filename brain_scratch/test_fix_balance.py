import sys
sys.path.insert(0, r"c:\Users\rieke\code-project\sistem-akuntansi-cabai\sistem-akuntansi-cabai")

from services.trial_balance_service import hitung_neraca_saldo

df_ns = hitung_neraca_saldo(1, termasuk_penyesuaian=True)

pendapatan = 0
beban_prod = 0
beban_ops = 0

for _, baris in df_ns.iterrows():
    kat = baris["kategori"]
    norm = baris["saldo_normal"]
    if norm == "Debit":
        jml = int(baris["debit"]) - int(baris["kredit"])
    else:
        jml = int(baris["kredit"]) - int(baris["debit"])
        
    if kat == "Pendapatan":
        pendapatan += jml
    elif kat == "Beban Produksi":
        beban_prod += jml
    elif kat == "Beban Operasional":
        beban_ops += jml

tot_beban = beban_prod + beban_ops
laba = pendapatan - tot_beban
print(f"Pendapatan: {pendapatan}")
print(f"Beban Produksi: {beban_prod}")
print(f"Beban Ops: {beban_ops}")
print(f"Total Beban: {tot_beban}")
print(f"Laba Bersih: {laba}")

import services.statements_service as ss
pe = ss.susun_laporan_perubahan_ekuitas(1, laba)
print(f"Modal Akhir: {pe['modal_akhir']}")

neraca = ss.susun_neraca(1, pe["modal_akhir"])
print(f"Total Aset: {neraca['total_aset']}")
print(f"Total Liabilitas & Ekuitas: {neraca['total_liabilitas_ekuitas']}")
print(f"Seimbang? {neraca['total_aset'] == neraca['total_liabilitas_ekuitas']}")
