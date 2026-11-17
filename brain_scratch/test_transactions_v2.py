"""
Script test yang meniru persis cara view memanggil service.
"""
import sys
sys.path.insert(0, r"c:\Users\rieke\code-project\sistem-akuntansi-cabai\sistem-akuntansi-cabai")

from database.connection import get_connection
import services.transaction_service as ts

def p(label, val):
    print(f"  ✅ {label}: {val}")

def f(label, err):
    print(f"  ❌ {label}: {err}")

# --- cek skema tabel ---
print("=== SKEMA TABEL ===")
with get_connection() as db:
    for tbl in ["journal_entries", "receivables", "items", "blok_lahan", "inventory_movements"]:
        cols = db.execute(f"PRAGMA table_info({tbl})").fetchall()
        print(f"  {tbl}: {[c['name'] for c in cols]}")

print()

# --- cek data dasar ---
print("=== DATA DASAR ===")
with get_connection() as db:
    period = db.execute("SELECT id, nama_bulan FROM periods LIMIT 1").fetchone()
    print(f"  period: id={period['id']}, nama_bulan={period['nama_bulan']}")
    
    cust = db.execute("SELECT id, nama FROM customers LIMIT 1").fetchone()
    print(f"  customer: id={cust['id']}, nama={cust['nama']}")
    
    supp = db.execute("SELECT id, nama FROM suppliers LIMIT 1").fetchone()
    print(f"  supplier: id={supp['id']}, nama={supp['nama']}")
    
    items = db.execute("SELECT id, kode_item, nama_item, satuan, tipe, account_id FROM items WHERE aktif=1 LIMIT 5").fetchall()
    for it in items:
        print(f"  item: id={it['id']}, kode={it['kode_item']}, nama={it['nama_item']}, tipe={it['tipe']}, account_id={it['account_id']}")
    
    bloks = db.execute("SELECT id, kode_blok, komoditas FROM blok_lahan WHERE aktif=1 LIMIT 3").fetchall()
    for b in bloks:
        print(f"  blok: id={b['id']}, kode={b['kode_blok']}, komoditas={b['komoditas']}")
    
    piutang = db.execute("SELECT id, customer_id, jumlah, jumlah_terbayar, status FROM receivables WHERE status != 'lunas' LIMIT 2").fetchall()
    for r in piutang:
        print(f"  receivable: id={r['id']}, jumlah={r['jumlah']}, status={r['status']}")

print()

# --- ambil data untuk test ---
with get_connection() as db:
    period_id = db.execute("SELECT id FROM periods LIMIT 1").fetchone()["id"]
    pelanggan = db.execute("SELECT id, nama FROM customers LIMIT 1").fetchone()
    supplier = db.execute("SELECT id, nama FROM suppliers LIMIT 1").fetchone()
    item_bahan = db.execute("SELECT id, kode_item, nama_item, satuan, account_id FROM items WHERE tipe='bahan' AND aktif=1 LIMIT 1").fetchone()
    item_panen = db.execute("SELECT id, kode_item, nama_item, satuan, account_id FROM items WHERE tipe='hasil_panen' AND aktif=1 LIMIT 1").fetchone()
    blok = db.execute("SELECT id, kode_blok, komoditas FROM blok_lahan WHERE aktif=1 LIMIT 1").fetchone()
    piutang = db.execute("SELECT id, customer_id, jumlah FROM receivables WHERE status != 'lunas' LIMIT 1").fetchone()
    akun_kas = db.execute("SELECT id FROM accounts WHERE kode_akun='1101'").fetchone()
    akun_modal = db.execute("SELECT id FROM accounts WHERE kode_akun='3101'").fetchone()
    akun_piutang = db.execute("SELECT id FROM accounts WHERE kode_akun='1201'").fetchone()
    akun_jual_cabai = db.execute("SELECT id FROM accounts WHERE kode_akun='4101'").fetchone()
    akun_utang = db.execute("SELECT id FROM accounts WHERE kode_akun='2101'").fetchone()
    akun_listrik = db.execute("SELECT id FROM accounts WHERE kode_akun='6101'").fetchone()
    akun_hpp = db.execute("SELECT id FROM accounts WHERE kode_akun='5104'").fetchone()
    akun_aset = db.execute("SELECT id FROM accounts WHERE kode_akun='1505'").fetchone()
    akun_beban_prod = db.execute("SELECT id FROM accounts WHERE kode_akun='5101'").fetchone()
    
    # cek stok persediaan
    stok = db.execute("SELECT saldo_qty, harga_rata2 FROM inventory_movements WHERE item_id=? ORDER BY id DESC LIMIT 1", (item_bahan["id"],)).fetchone() if item_bahan else None

print(f"item_bahan: {dict(item_bahan) if item_bahan else None}")
print(f"item_panen: {dict(item_panen) if item_panen else None}")
print(f"blok: {dict(blok) if blok else None}")
print(f"piutang: {dict(piutang) if piutang else None}")
print(f"stok item_bahan: {dict(stok) if stok else None}")
print()

# ==============================================================
# TEST SETIAP TRANSAKSI PERSIS SEPERTI VIEW MEMANGGILNYA
# ==============================================================
print("=== TEST TRANSAKSI (seperti dari view) ===")

# TEST 1: Penjualan Tunai
print("\n1. Penjualan Tunai cabai")
try:
    result = ts.catat_penjualan_tunai(
        period_id=period_id,
        tanggal="2026-10-25",
        pelanggan=pelanggan["nama"],
        jumlah_kg=10.0,
        harga_per_kg=60000,
        akun_kas_id=akun_kas["id"],
        akun_penjualan_id=akun_jual_cabai["id"],
        komoditas="cabai",
        keterangan_tambahan=""
    )
    p("Penjualan tunai", result)
except Exception as e:
    f("Penjualan tunai", e)

# TEST 2: Penjualan Tempo
print("\n2. Penjualan Tempo cabai")
try:
    result = ts.catat_penjualan_tempo(
        period_id=period_id,
        tanggal="2026-10-25",
        customer_id=pelanggan["id"],
        pelanggan_nama=pelanggan["nama"],
        jumlah_kg=5.0,
        harga_per_kg=55000,
        akun_piutang_id=akun_piutang["id"],
        akun_penjualan_id=akun_jual_cabai["id"],
        komoditas="cabai"
    )
    p("Penjualan tempo", result)
except Exception as e:
    f("Penjualan tempo", e)

# TEST 3: Beli Tunai
print("\n3. Beli Bahan Tunai")
try:
    result = ts.catat_pembelian_tunai(
        period_id=period_id,
        tanggal="2026-10-25",
        supplier_nama=supplier["nama"] if supplier else "Toko ABC",
        item_id=item_bahan["id"],
        qty=10.0,
        harga_satuan=50000,
        akun_persediaan_id=item_bahan["account_id"],
        akun_kas_id=akun_kas["id"],
        keterangan=""
    )
    p("Beli bahan tunai", result)
except Exception as e:
    f("Beli bahan tunai", e)

# TEST 4: Beli Kredit
print("\n4. Beli Kredit")
try:
    result = ts.catat_pembelian_kredit(
        period_id=period_id,
        tanggal="2026-10-25",
        supplier_nama=supplier["nama"] if supplier else "Toko ABC",
        item_id=item_bahan["id"],
        qty=5.0,
        harga_satuan=50000,
        akun_persediaan_id=item_bahan["account_id"],
        akun_utang_id=akun_utang["id"],
        keterangan=""
    )
    p("Beli kredit", result)
except Exception as e:
    f("Beli kredit", e)

# TEST 5: Pemakaian Bahan (cek stok dulu)
print("\n5. Pemakaian Bahan")
try:
    # Cek stok terkini
    with get_connection() as db:
        stok_row = db.execute(
            "SELECT saldo_qty, harga_rata2 FROM inventory_movements WHERE item_id=? ORDER BY id DESC LIMIT 1",
            (item_bahan["id"],)
        ).fetchone()
    if stok_row and stok_row["saldo_qty"] >= 1:
        result = ts.catat_pemakaian_bahan(
            period_id=period_id,
            tanggal="2026-10-25",
            item_id=item_bahan["id"],
            qty=1.0,
            akun_beban_id=akun_beban_prod["id"],
            akun_persediaan_id=item_bahan["account_id"],
            blok_nama=blok["kode_blok"] if blok else "A",
            keterangan="",
            komoditas=blok["komoditas"] if blok else "cabai"
        )
        p("Pemakaian bahan", result)
    else:
        print(f"  ⚠️ Stok tidak cukup: {stok_row}")
except Exception as e:
    f("Pemakaian bahan", e)

# TEST 6: Catat Panen
print("\n6. Catat Panen")
try:
    if item_panen and akun_hpp:
        result = ts.catat_panen(
            period_id=period_id,
            tanggal="2026-10-25",
            item_panen_id=item_panen["id"],
            jumlah_kg=50.0,
            harga_estimasi_per_kg=25000,
            akun_persediaan_panen_id=item_panen["account_id"],
            akun_hpp_panen_id=akun_hpp["id"],
            blok_nama=blok["kode_blok"] if blok else "A",
            komoditas=blok["komoditas"] if blok else "cabai",
            keterangan=""
        )
        p("Catat panen", result)
    else:
        print(f"  ⚠️ item_panen={item_panen}, akun_hpp={akun_hpp}")
except Exception as e:
    f("Catat panen", e)

# TEST 7: Biaya Operasional
print("\n7. Biaya Operasional - Listrik")
try:
    result = ts.catat_biaya_operasional(
        period_id=period_id,
        tanggal="2026-10-25",
        jenis_biaya="Listrik",
        jumlah=500000,
        akun_beban_id=akun_listrik["id"],
        akun_kas_id=akun_kas["id"],
        keterangan=""
    )
    p("Biaya listrik", result)
except Exception as e:
    f("Biaya listrik", e)

# TEST 8: Setoran Modal
print("\n8. Setoran Modal")
try:
    result = ts.catat_setoran_modal(
        period_id=period_id,
        tanggal="2026-10-25",
        jumlah=10000000,
        akun_kas_id=akun_kas["id"],
        akun_modal_id=akun_modal["id"],
        keterangan="Setoran modal pemilik"
    )
    p("Setoran modal", result)
except Exception as e:
    f("Setoran modal", e)

# TEST 9: Terima Piutang
print("\n9. Terima Piutang")
try:
    if piutang:
        result = ts.catat_penerimaan_piutang(
            period_id=period_id,
            receivable_id=piutang["id"],
            tanggal="2026-10-25",
            jumlah=piutang["jumlah"],
            akun_kas_id=akun_kas["id"],
            akun_piutang_id=akun_piutang["id"],
            keterangan_tambahan=""
        )
        p("Terima piutang", result)
    else:
        print("  ⚠️ Tidak ada piutang belum lunas")
except Exception as e:
    f("Terima piutang", e)

# TEST 10: Beli Aset
print("\n10. Beli Aset Tetap")
try:
    result = ts.catat_pembelian_aset(
        period_id=period_id,
        tanggal="2026-10-25",
        nama_aset="Pompa Air Baru",
        jumlah=1500000,
        akun_aset_id=akun_aset["id"],
        akun_kas_id=akun_kas["id"],
        keterangan=""
    )
    p("Beli aset tetap", result)
except Exception as e:
    f("Beli aset tetap", e)

print("\n=== SELESAI ===")
