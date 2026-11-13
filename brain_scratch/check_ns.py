import sys
sys.path.insert(0, r"c:\Users\rieke\code-project\sistem-akuntansi-cabai\sistem-akuntansi-cabai")

from services.trial_balance_service import hitung_neraca_saldo
df = hitung_neraca_saldo(1, termasuk_penyesuaian=True)
print("Columns:", list(df.columns))
print(df[df["kode_akun"].isin(["5104", "1307", "1301", "4101"])])
