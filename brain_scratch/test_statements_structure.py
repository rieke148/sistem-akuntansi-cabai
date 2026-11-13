import sys
sys.path.insert(0, r"c:\Users\rieke\code-project\sistem-akuntansi-cabai\sistem-akuntansi-cabai")

import services.statements_service as ss

lr = ss.susun_laporan_laba_rugi(1)
print("=== LABA RUGI ===")
print("Keys:", list(lr.keys()))
print("Total Pendapatan:", lr.get("total_pendapatan"))
print("Laba Bersih:", lr.get("laba_bersih"))

pe = ss.susun_laporan_perubahan_ekuitas(1, lr.get("laba_bersih", 0))
print("\n=== PERUBAHAN EKUITAS ===")
print("Modal Akhir:", pe.get("modal_akhir"))

neraca = ss.susun_neraca(1, pe.get("modal_akhir", 0))
print("\n=== NERACA ===")
print("Total Aset:", neraca.get("total_aset"))
print("Total Liabilitas & Ekuitas:", neraca.get("total_liabilitas_ekuitas"))
print("Seimbang:", neraca.get("seimbang"))

ak = ss.susun_arus_kas(1)
print("\n=== ARUS KAS ===")
print("Kas Akhir:", ak.get("kas_akhir"))
