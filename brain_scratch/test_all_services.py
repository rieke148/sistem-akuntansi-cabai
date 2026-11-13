"""
Test semua service yang dipakai di views untuk memastikan tidak ada error.
Mensimulasikan pemanggilan yang dilakukan views saat startup.
"""
import sys
sys.path.insert(0, r"c:\Users\rieke\code-project\sistem-akuntansi-cabai\sistem-akuntansi-cabai")

results = []

def ok(label):
    results.append(("OK", label))
    print(f"  ✅ {label}")

def fail(label, err):
    results.append(("FAIL", label, str(err)))
    print(f"  ❌ {label}: {err}")

# ==================================================================
print("=== SERVICES YANG DIPAKAI VIEWS ===\n")

# -- journal_service --
print("1. journal_service")
try:
    from services.journal_service import ambil_semua_jurnal, generate_nomor_bukti
    df = ambil_semua_jurnal(period_id=1)
    ok(f"ambil_semua_jurnal: {len(df)} rows")
    nb = generate_nomor_bukti("KK", "OKT26")
    ok(f"generate_nomor_bukti: {nb}")
except Exception as e:
    fail("journal_service", e)

# -- ledger_service --
print("\n2. ledger_service")
try:
    from services.ledger_service import ambil_buku_besar
    df = ambil_buku_besar(period_id=1)
    ok(f"ambil_buku_besar: {len(df)} rows")
except Exception as e:
    fail("ledger_service", e)

# -- trial_balance_service --
print("\n3. trial_balance_service")
try:
    from services.trial_balance_service import hitung_neraca_saldo
    df = hitung_neraca_saldo(period_id=1)
    ok(f"hitung_neraca_saldo: {len(df)} rows")
except Exception as e:
    fail("trial_balance_service", e)

# -- special_journal_service --
print("\n4. special_journal_service")
try:
    from services.special_journal_service import (
        ambil_jurnal_penjualan, ambil_jurnal_pembelian,
        ambil_jurnal_penerimaan_kas, ambil_jurnal_pengeluaran_kas
    )
    df1 = ambil_jurnal_penjualan(period_id=1)
    ok(f"ambil_jurnal_penjualan: {len(df1)} rows, cols={list(df1.columns)}")
    df2 = ambil_jurnal_pembelian(period_id=1)
    ok(f"ambil_jurnal_pembelian: {len(df2)} rows")
    df3 = ambil_jurnal_penerimaan_kas(period_id=1)
    ok(f"ambil_jurnal_penerimaan_kas: {len(df3)} rows")
    df4 = ambil_jurnal_pengeluaran_kas(period_id=1)
    ok(f"ambil_jurnal_pengeluaran_kas: {len(df4)} rows")
except Exception as e:
    fail("special_journal_service", e)

# -- subsidiary_service --
print("\n5. subsidiary_service")
try:
    from services.subsidiary_service import (
        ambil_bb_piutang, ambil_ringkasan_piutang_per_pelanggan,
        ambil_bb_persediaan, ambil_bb_aset_tetap
    )
    df = ambil_bb_piutang()
    ok(f"ambil_bb_piutang: {len(df)} rows, cols={list(df.columns)}")
    df2 = ambil_ringkasan_piutang_per_pelanggan()
    ok(f"ambil_ringkasan_piutang: {len(df2)} rows")
    # cek item pertama
    from database.connection import get_connection
    with get_connection() as db:
        item = db.execute("SELECT id FROM items LIMIT 1").fetchone()
    if item:
        df3 = ambil_bb_persediaan(item["id"])
        ok(f"ambil_bb_persediaan: {len(df3)} rows")
    df4 = ambil_bb_aset_tetap()
    ok(f"ambil_bb_aset_tetap: {len(df4)} rows")
except Exception as e:
    fail("subsidiary_service", e)

# -- inventory_service --
print("\n6. inventory_service")
try:
    from services.inventory_service import ambil_kartu_persediaan, ambil_saldo_persediaan
    from database.connection import get_connection
    with get_connection() as db:
        item = db.execute("SELECT id FROM items WHERE aktif=1 LIMIT 1").fetchone()
    if item:
        df = ambil_kartu_persediaan(item["id"])
        ok(f"ambil_kartu_persediaan: {len(df)} rows")
        saldo = ambil_saldo_persediaan(item["id"])
        ok(f"ambil_saldo_persediaan: {saldo}")
except Exception as e:
    fail("inventory_service", e)

# -- payroll_service --
print("\n7. payroll_service")
try:
    from services.payroll_service import ambil_pekerja, hitung_upah_periode
    pekerja = ambil_pekerja()
    ok(f"ambil_pekerja: {len(pekerja)} pekerja")
except Exception as e:
    fail("payroll_service", e)

# -- depreciation_service --
print("\n8. depreciation_service")
try:
    from services.depreciation_service import hitung_penyusutan_semua_aset
    hasil = hitung_penyusutan_semua_aset(period_id=1)
    ok(f"hitung_penyusutan_semua_aset: {len(hasil)} aset")
except Exception as e:
    fail("depreciation_service", e)

# -- adjusting_service --
print("\n9. adjusting_service")
try:
    from services.adjusting_service import ambil_ayat_penyesuaian
    hasil = ambil_ayat_penyesuaian(period_id=1)
    ok(f"ambil_ayat_penyesuaian: {len(hasil)} item")
except Exception as e:
    fail("adjusting_service", e)

# -- worksheet_service --
print("\n10. worksheet_service")
try:
    from services.worksheet_service import hitung_neraca_lajur
    df = hitung_neraca_lajur(period_id=1)
    ok(f"hitung_neraca_lajur: {len(df)} rows")
except Exception as e:
    fail("worksheet_service", e)

# -- statements_service --
print("\n11. statements_service")
try:
    from services.statements_service import hitung_laba_rugi, hitung_neraca, hitung_perubahan_ekuitas
    lr = hitung_laba_rugi(period_id=1)
    ok(f"hitung_laba_rugi: {len(lr)} rows")
    nr = hitung_neraca(period_id=1)
    ok(f"hitung_neraca: {len(nr)} rows")
    pe = hitung_perubahan_ekuitas(period_id=1)
    ok(f"hitung_perubahan_ekuitas: {len(pe)} rows")
except Exception as e:
    fail("statements_service", e)

# -- closing_service --
print("\n12. closing_service")
try:
    from services.closing_service import ambil_status_penutupan
    status = ambil_status_penutupan(period_id=1)
    ok(f"ambil_status_penutupan: {status}")
except Exception as e:
    fail("closing_service", e)

# -- dashboard_service --
print("\n13. dashboard_service")
try:
    from services.dashboard_service import (
        ambil_saldo_kas, ambil_piutang_jatuh_tempo,
        ambil_ringkasan_penjualan_vs_biaya
    )
    kas = ambil_saldo_kas()
    ok(f"ambil_saldo_kas: Rp{kas:,}")
    piutang = ambil_piutang_jatuh_tempo()
    ok(f"ambil_piutang_jatuh_tempo: {len(piutang)} rows")
    df_pv = ambil_ringkasan_penjualan_vs_biaya(period_id=1)
    ok(f"ambil_ringkasan_penjualan_vs_biaya: {len(df_pv)} rows")
except Exception as e:
    fail("dashboard_service", e)

# -- transaction_service helpers --
print("\n14. transaction_service.ambil_piutang_terbuka")
try:
    from services.transaction_service import ambil_piutang_terbuka
    df = ambil_piutang_terbuka()
    ok(f"ambil_piutang_terbuka: {len(df)} rows, cols={list(df.columns)}")
except Exception as e:
    fail("ambil_piutang_terbuka", e)

# ==================================================================
print("\n=== RINGKASAN ===")
ok_count = sum(1 for r in results if r[0] == "OK")
fail_count = sum(1 for r in results if r[0] == "FAIL")
print(f"Total: {ok_count} OK, {fail_count} GAGAL")
if fail_count > 0:
    print("\nYANG GAGAL:")
    for r in results:
        if r[0] == "FAIL":
            print(f"  ❌ {r[1]}: {r[2]}")
