import sys, os
sys.path.insert(0, r"c:\Users\rieke\code-project\sistem-akuntansi-cabai\sistem-akuntansi-cabai")

from services.inventory_service import ambil_kartu_persediaan, ambil_saldo_persediaan
from database.connection import get_connection

with get_connection() as db:
    items = db.execute('SELECT id, nama_item, tipe, satuan FROM items').fetchall()

print(f"Total items: {len(items)}")
for it in items:
    df = ambil_kartu_persediaan(it['id'])
    saldo = ambil_saldo_persediaan(it['id'])
    print(f"Item {it['id']} [{it['tipe']}] {it['nama_item']}: {len(df)} movements, saldo={saldo}")
