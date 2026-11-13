"""Quick check signatures of service functions used by views."""
import sys
sys.path.insert(0, r"c:\Users\rieke\code-project\sistem-akuntansi-cabai\sistem-akuntansi-cabai")
import inspect

funcs = [
    ("services.depreciation_service", "hitung_semua_penyusutan"),
    ("services.adjusting_service", "cek_penyesuaian_sudah_ada"),
    ("services.trial_balance_service", "validasi_neraca_saldo_seimbang"),
    ("services.worksheet_service", "validasi_neraca_lajur"),
    ("services.statements_service", "susun_neraca"),
    ("services.payroll_service", "hitung_upah_pekerja"),
]

for modname, fname in funcs:
    try:
        mod = __import__(modname, fromlist=[fname])
        func = getattr(mod, fname)
        sig = inspect.signature(func)
        print(f"  {fname}{sig}")
    except Exception as e:
        print(f"  ERROR {fname}: {e}")
