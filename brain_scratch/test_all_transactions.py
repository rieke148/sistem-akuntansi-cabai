"""
Script test komprehensif - simulasi semua jenis transaksi input.
Jalankan dari root project folder.
"""
import sys
import os
sys.path.insert(0, r"c:\Users\rieke\code-project\sistem-akuntansi-cabai\sistem-akuntansi-cabai")

from database.connection import get_connection

# ==============================================================
# HELPERS
# ==============================================================
def get_first_period():
    with get_connection() as db:
        row = db.execute("SELECT id FROM periods LIMIT 1").fetchone()
        return row[0] if row else None

def get_account_id(kode):
    with get_connection() as db:
        row = db.execute("SELECT id FROM accounts WHERE kode_akun=?", (kode,)).fetchone()
        return row[0] if row else None

def get_customer_id():
    with get_connection() as db:
        row = db.execute("SELECT id FROM customers LIMIT 1").fetchone()
        return row[0] if row else None

def get_supplier_id():
    with get_connection() as db:
        row = db.execute("SELECT id FROM suppliers LIMIT 1").fetchone()
        return row[0] if row else None

def get_item(tipe):
    with get_connection() as db:
        row = db.execute(
            "SELECT id, kode_item, nama_item, satuan, account_id FROM items WHERE tipe=? AND aktif=1 LIMIT 1",
            (tipe,)
        ).fetchone()
        if row:
            return {"id": row[0], "kode_item": row[1], "nama_item": row[2], "satuan": row[3], "account_id": row[4]}
        return None

def get_blok():
    with get_connection() as db:
        row = db.execute("SELECT id, kode_blok, komoditas FROM blok_lahan WHERE aktif=1 LIMIT 1").fetchone()
        if row:
            return {"id": row[0], "kode_blok": row[1], "komoditas": row[2]}
        return None

def get_receivable():
    with get_connection() as db:
        row = db.execute(
            "SELECT id, customer_id, jumlah FROM receivables WHERE lunas=0 LIMIT 1"
        ).fetchone()
        if row:
            return {"id": row[0], "customer_id": row[1], "jumlah": row[2]}
        return None

def get_asset():
    with get_connection() as db:
        row = db.execute("SELECT id, kode_akun FROM accounts WHERE kode_akun LIKE '15%' AND aktif=1 AND is_kontra=0 LIMIT 1").fetchone()
        if row:
            return {"id": row[0], "kode_akun": row[1]}
        return None

def print_ok(label):
    print(f"  ✅ {label}")

def print_fail(label, err):
    print(f"  ❌ {label}: {err}")

# ==============================================================
# TESTS
# ==============================================================
import services.transaction_service as ts

period_id = get_first_period()
print(f"Period ID: {period_id}")
print()

# --- TEST 1: Penjualan Tunai ---
print("=== TEST 1: Penjualan Tunai ===")
try:
    akun_kas = get_account_id("1101")
    akun_jual = get_account_id("4101")
    customer_id = get_customer_id()
    result = ts.catat_penjualan_tunai(
        period_id=period_id,
        tanggal="2026-10-15",
        customer_id=customer_id,
        jumlah_kg=10.0,
        harga_per_kg=60000,
        akun_kas_id=akun_kas,
        akun_penjualan_id=akun_jual,
        komoditas="cabai"
    )
    print_ok(f"Penjualan tunai cabai: {result}")
except Exception as e:
    print_fail("Penjualan tunai cabai", e)

# --- TEST 2: Penjualan Tempo ---
print("\n=== TEST 2: Penjualan Tempo ===")
try:
    akun_piutang = get_account_id("1201")
    akun_jual = get_account_id("4101")
    customer_id = get_customer_id()
    result = ts.catat_penjualan_tempo(
        period_id=period_id,
        tanggal="2026-10-16",
        customer_id=customer_id,
        jumlah_kg=5.0,
        harga_per_kg=55000,
        akun_piutang_id=akun_piutang,
        akun_penjualan_id=akun_jual,
        komoditas="cabai"
    )
    print_ok(f"Penjualan tempo cabai: {result}")
except Exception as e:
    print_fail("Penjualan tempo cabai", e)

# --- TEST 3: Beli Bahan Tunai ---
print("\n=== TEST 3: Beli Bahan Tunai ===")
try:
    item = get_item("bahan")
    akun_kas = get_account_id("1101")
    supplier_id = get_supplier_id()
    if item:
        result = ts.catat_pembelian_tunai(
            period_id=period_id,
            tanggal="2026-10-17",
            supplier_id=supplier_id,
            item_id=item["id"],
            jumlah=10,
            harga_satuan=50000,
            akun_kas_id=akun_kas,
            akun_persediaan_id=item["account_id"],
            satuan=item["satuan"],
            komoditas="cabai"
        )
        print_ok(f"Beli bahan tunai ({item['nama_item']}): {result}")
    else:
        print_fail("Beli bahan tunai", "Tidak ada item bahan")
except Exception as e:
    print_fail("Beli bahan tunai", e)

# --- TEST 4: Beli Kredit ---
print("\n=== TEST 4: Beli Kredit ===")
try:
    item = get_item("bahan")
    akun_utang = get_account_id("2101")
    supplier_id = get_supplier_id()
    if item:
        result = ts.catat_pembelian_kredit(
            period_id=period_id,
            tanggal="2026-10-18",
            supplier_id=supplier_id,
            item_id=item["id"],
            jumlah=5,
            harga_satuan=50000,
            akun_utang_id=akun_utang,
            akun_persediaan_id=item["account_id"],
            satuan=item["satuan"],
            komoditas="cabai"
        )
        print_ok(f"Beli kredit ({item['nama_item']}): {result}")
    else:
        print_fail("Beli kredit", "Tidak ada item bahan")
except Exception as e:
    print_fail("Beli kredit", e)

# --- TEST 5: Pemakaian Bahan ---
print("\n=== TEST 5: Pemakaian Bahan ===")
try:
    item = get_item("bahan")
    blok = get_blok()
    if item and blok:
        result = ts.catat_pemakaian_bahan(
            period_id=period_id,
            tanggal="2026-10-19",
            item_id=item["id"],
            jumlah=2,
            biaya_satuan=50000,
            blok_id=blok["id"],
            akun_persediaan_id=item["account_id"],
            satuan=item["satuan"],
            komoditas=blok["komoditas"]
        )
        print_ok(f"Pemakaian bahan ({item['nama_item']} blok {blok['kode_blok']}): {result}")
    else:
        print_fail("Pemakaian bahan", f"item={item}, blok={blok}")
except Exception as e:
    print_fail("Pemakaian bahan", e)

# --- TEST 6: Catat Panen ---
print("\n=== TEST 6: Catat Panen ===")
try:
    item_panen = get_item("hasil_panen")
    blok = get_blok()
    if item_panen and blok:
        result = ts.catat_panen(
            period_id=period_id,
            tanggal="2026-10-20",
            item_id=item_panen["id"],
            jumlah_kg=50.0,
            hpp_per_kg=10000,
            blok_id=blok["id"],
            akun_persediaan_id=item_panen["account_id"],
            komoditas=blok["komoditas"]
        )
        print_ok(f"Catat panen ({item_panen['nama_item']}): {result}")
    else:
        print_fail("Catat panen", f"item_panen={item_panen}, blok={blok}")
except Exception as e:
    print_fail("Catat panen", e)

# --- TEST 7: Biaya Operasional (Listrik) ---
print("\n=== TEST 7: Biaya Operasional - Listrik ===")
try:
    akun_kas = get_account_id("1101")
    akun_beban = get_account_id("6101")
    result = ts.catat_biaya_operasional(
        period_id=period_id,
        tanggal="2026-10-21",
        jenis_biaya="listrik",
        jumlah=500000,
        akun_kas_id=akun_kas,
        akun_beban_id=akun_beban,
        komoditas="umum"
    )
    print_ok(f"Biaya listrik: {result}")
except Exception as e:
    print_fail("Biaya listrik", e)

# --- TEST 7b: Biaya Operasional (Sewa Traktor) ---
print("\n=== TEST 7b: Biaya Operasional - Sewa Traktor ===")
try:
    akun_kas = get_account_id("1101")
    akun_beban = get_account_id("6104")
    result = ts.catat_biaya_operasional(
        period_id=period_id,
        tanggal="2026-10-21",
        jenis_biaya="sewa_traktor",
        jumlah=350000,
        akun_kas_id=akun_kas,
        akun_beban_id=akun_beban,
        komoditas="cabai"
    )
    print_ok(f"Biaya sewa traktor: {result}")
except Exception as e:
    print_fail("Biaya sewa traktor", e)

# --- TEST 8: Setoran Modal ---
print("\n=== TEST 8: Setoran Modal ===")
try:
    akun_kas = get_account_id("1101")
    akun_modal = get_account_id("3101")
    result = ts.catat_setoran_modal(
        period_id=period_id,
        tanggal="2026-10-22",
        jumlah=10000000,
        akun_kas_id=akun_kas,
        akun_modal_id=akun_modal
    )
    print_ok(f"Setoran modal: {result}")
except Exception as e:
    print_fail("Setoran modal", e)

# --- TEST 9: Terima Piutang ---
print("\n=== TEST 9: Terima Piutang ===")
try:
    piutang = get_receivable()
    akun_kas = get_account_id("1101")
    akun_piutang = get_account_id("1201")
    if piutang:
        result = ts.catat_penerimaan_piutang(
            period_id=period_id,
            tanggal="2026-10-23",
            receivable_id=piutang["id"],
            jumlah_bayar=piutang["jumlah"],
            akun_kas_id=akun_kas,
            akun_piutang_id=akun_piutang
        )
        print_ok(f"Terima piutang (Rp{piutang['jumlah']:,}): {result}")
    else:
        print_fail("Terima piutang", "Tidak ada piutang belum lunas")
except Exception as e:
    print_fail("Terima piutang", e)

# --- TEST 10: Beli Aset ---
print("\n=== TEST 10: Beli Aset Tetap ===")
try:
    akun_kas = get_account_id("1101")
    akun_aset = get_account_id("1505")  # Peralatan
    result = ts.catat_pembelian_aset(
        period_id=period_id,
        tanggal="2026-10-24",
        nama_aset="Pompa Air Baru",
        jumlah=1500000,
        akun_kas_id=akun_kas,
        akun_aset_id=akun_aset,
        komoditas="cabai"
    )
    print_ok(f"Beli aset tetap: {result}")
except Exception as e:
    print_fail("Beli aset tetap", e)

print("\n=== SELESAI ===")
