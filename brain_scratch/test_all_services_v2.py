"""
Test runtime semua service dengan nama fungsi yang benar.
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

print("=== TEST RUNTIME SEMUA SERVICE ===\n")

# -- journal_service --
print("1. journal_service")
try:
    from services.journal_service import ambil_semua_jurnal, generate_nomor_bukti
    df = ambil_semua_jurnal(period_id=1)
    ok(f"ambil_semua_jurnal: {len(df)} rows")
    nb = generate_nomor_bukti("KK", "OKT26")
    ok(f"generate_nomor_bukti: {nb} (harus unik)")
except Exception as e:
    fail("journal_service", e)

# -- ledger_service --
print("\n2. ledger_service")
try:
    from services.ledger_service import ambil_buku_besar, ambil_saldo_akun, ambil_semua_saldo_akun
    from database.connection import get_connection
    with get_connection() as db:
        akun = db.execute("SELECT id FROM accounts WHERE kode_akun='1101'").fetchone()
    df = ambil_buku_besar(account_id=akun["id"], period_id=1)
    ok(f"ambil_buku_besar(account_id): {len(df)} rows")
    saldo = ambil_saldo_akun(akun["id"], period_id=1)
    ok(f"ambil_saldo_akun: Rp{saldo:,}")
    saldo_semua = ambil_semua_saldo_akun(period_id=1)
    ok(f"ambil_semua_saldo_akun: {len(saldo_semua)} akun")
except Exception as e:
    fail("ledger_service", e)

# -- trial_balance_service --
print("\n3. trial_balance_service")
try:
    from services.trial_balance_service import hitung_neraca_saldo, validasi_neraca_saldo_seimbang
    df = hitung_neraca_saldo(period_id=1)
    ok(f"hitung_neraca_saldo: {len(df)} rows")
    valid, selisih = validasi_neraca_saldo_seimbang(period_id=1)
    ok(f"validasi_neraca_saldo_seimbang: seimbang={valid}, selisih={selisih}")
except Exception as e:
    fail("trial_balance_service", e)

# -- special_journal_service --
print("\n4. special_journal_service")
try:
    from services.special_journal_service import (
        ambil_jurnal_penjualan, ambil_jurnal_pembelian,
        ambil_jurnal_penerimaan_kas, ambil_jurnal_pengeluaran_kas, hitung_total_kolom
    )
    df1 = ambil_jurnal_penjualan(period_id=1)
    ok(f"ambil_jurnal_penjualan: {len(df1)} rows")
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
        ambil_bb_persediaan, ambil_bb_aset_tetap, ambil_bb_utang
    )
    from database.connection import get_connection
    with get_connection() as db:
        item = db.execute("SELECT id FROM items WHERE aktif=1 LIMIT 1").fetchone()
    df = ambil_bb_piutang()
    ok(f"ambil_bb_piutang: {len(df)} rows")
    df2 = ambil_ringkasan_piutang_per_pelanggan()
    ok(f"ambil_ringkasan_piutang: {len(df2)} rows")
    df3 = ambil_bb_persediaan(item["id"])
    ok(f"ambil_bb_persediaan: {len(df3)} rows")
    df4 = ambil_bb_aset_tetap()
    ok(f"ambil_bb_aset_tetap: {len(df4)} rows")
    df5 = ambil_bb_utang()
    ok(f"ambil_bb_utang: {len(df5)} rows")
except Exception as e:
    fail("subsidiary_service", e)

# -- inventory_service --
print("\n6. inventory_service")
try:
    from services.inventory_service import ambil_kartu_persediaan, ambil_saldo_persediaan
    from database.connection import get_connection
    with get_connection() as db:
        item = db.execute("SELECT id FROM items WHERE aktif=1 LIMIT 1").fetchone()
    df = ambil_kartu_persediaan(item["id"])
    ok(f"ambil_kartu_persediaan: {len(df)} rows")
    saldo = ambil_saldo_persediaan(item["id"])
    ok(f"ambil_saldo_persediaan: qty={saldo['saldo_qty']}, harga_rata2={saldo['harga_rata2']}")
except Exception as e:
    fail("inventory_service", e)

# -- payroll_service --
print("\n7. payroll_service")
try:
    from services.payroll_service import ambil_rekap_absensi, ambil_absensi_per_minggu
    hasil = ambil_rekap_absensi(period_id=1)
    ok(f"ambil_rekap_absensi: {len(hasil)} records")
except Exception as e:
    fail("payroll_service", e)

# -- depreciation_service --
print("\n8. depreciation_service")
try:
    from services.depreciation_service import hitung_semua_penyusutan, hitung_penyusutan_bulanan
    hasil = hitung_semua_penyusutan(period_id=1)
    ok(f"hitung_semua_penyusutan: {len(hasil)} aset")
except Exception as e:
    fail("depreciation_service", e)

# -- adjusting_service --
print("\n9. adjusting_service")
try:
    from services.adjusting_service import ambil_ringkasan_penyesuaian, cek_penyesuaian_sudah_ada
    hasil = ambil_ringkasan_penyesuaian(period_id=1)
    ok(f"ambil_ringkasan_penyesuaian: {type(hasil)}")
    sudah = cek_penyesuaian_sudah_ada(period_id=1)
    ok(f"cek_penyesuaian_sudah_ada: {sudah}")
except Exception as e:
    fail("adjusting_service", e)

# -- worksheet_service --
print("\n10. worksheet_service")
try:
    from services.worksheet_service import buat_neraca_lajur, validasi_neraca_lajur
    df = buat_neraca_lajur(period_id=1)
    ok(f"buat_neraca_lajur: {len(df)} rows")
    valid, selisih = validasi_neraca_lajur(df)
    ok(f"validasi_neraca_lajur: valid={valid}, selisih={selisih}")
except Exception as e:
    fail("worksheet_service", e)

# -- statements_service --
print("\n11. statements_service")
try:
    from services.statements_service import susun_laporan_laba_rugi, susun_neraca, susun_laporan_perubahan_ekuitas
    lr = susun_laporan_laba_rugi(period_id=1)
    ok(f"susun_laporan_laba_rugi: {type(lr)}")
    nr = susun_neraca(period_id=1)
    ok(f"susun_neraca: {type(nr)}")
    pe = susun_laporan_perubahan_ekuitas(period_id=1)
    ok(f"susun_laporan_perubahan_ekuitas: {type(pe)}")
except Exception as e:
    fail("statements_service", e)

# -- closing_service --
print("\n12. closing_service")
try:
    from services.closing_service import cek_jurnal_penutup_sudah_ada, preview_jurnal_penutup
    sudah = cek_jurnal_penutup_sudah_ada(period_id=1)
    ok(f"cek_jurnal_penutup_sudah_ada: {sudah}")
    if not sudah:
        preview = preview_jurnal_penutup(period_id=1, tanggal="2026-10-31")
        ok(f"preview_jurnal_penutup: {len(preview)} entries")
except Exception as e:
    fail("closing_service", e)

# -- dashboard_service --
print("\n13. dashboard_service")
try:
    from services.dashboard_service import (
        ambil_saldo_kas_bank, ambil_piutang_overdue,
        ambil_ringkasan_penjualan_beban, ambil_stok_persediaan,
        ambil_period_id_aktif, cek_progress_siklus
    )
    kas = ambil_saldo_kas_bank(period_id=1)
    ok(f"ambil_saldo_kas_bank: {kas}")
    piutang = ambil_piutang_overdue()
    ok(f"ambil_piutang_overdue: {len(piutang)} items")
    ringkasan = ambil_ringkasan_penjualan_beban(period_id=1)
    ok(f"ambil_ringkasan_penjualan_beban: {ringkasan}")
    stok = ambil_stok_persediaan()
    ok(f"ambil_stok_persediaan: {len(stok)} items")
    pid = ambil_period_id_aktif()
    ok(f"ambil_period_id_aktif: {pid}")
    progress = cek_progress_siklus(period_id=1)
    ok(f"cek_progress_siklus: {list(progress.keys())}")
except Exception as e:
    fail("dashboard_service", e)

# -- transaction_service helpers --
print("\n14. transaction_service")
try:
    from services.transaction_service import ambil_piutang_terbuka
    df = ambil_piutang_terbuka()
    ok(f"ambil_piutang_terbuka: {len(df)} rows")
except Exception as e:
    fail("transaction_service", e)

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
else:
    print("✅ Semua service berfungsi dengan baik!")
