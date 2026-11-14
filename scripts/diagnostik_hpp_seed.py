"""
scripts/diagnostik_hpp_seed.py
-------------------------------
Pemeriksaan READ-ONLY untuk memverifikasi transaksi penjualan contoh
yang belum memiliki HPP dan riwayat stok item HSL-001.

Jalankan dari folder utama proyek:
    python scripts/diagnostik_hpp_seed.py

Script ini TIDAK mengubah database.
"""

import re
import sys
from pathlib import Path

ROOT_PROYEK = Path(__file__).resolve().parents[1]
if str(ROOT_PROYEK) not in sys.path:
    sys.path.insert(0, str(ROOT_PROYEK))

from database.connection import PATH_DATABASE, get_connection


POLA_QTY = re.compile(r"(\d+(?:[.,]\d+)?)\s*kg\s*@", re.IGNORECASE)


def main() -> None:
    print("=" * 76)
    print("DIAGNOSTIK HPP PENJUALAN — READ ONLY")
    print("=" * 76)
    print(f"Database: {PATH_DATABASE}")
    print()

    koneksi = get_connection()
    try:
        akun = koneksi.execute("""
            SELECT id, kode_akun, nama_akun
            FROM accounts
            WHERE kode_akun IN ('4101', '5108', '1307')
            ORDER BY kode_akun
        """).fetchall()
        print("AKUN TERKAIT:")
        for row in akun:
            print(f"  {row['kode_akun']} | {row['nama_akun']} | id={row['id']}")
        print()

        items = koneksi.execute("""
            SELECT i.id, i.kode_item, i.nama_item, i.tipe,
                   i.account_id, a.kode_akun
            FROM items i
            LEFT JOIN accounts a ON a.id = i.account_id
            WHERE i.tipe = 'hasil_panen'
            ORDER BY i.kode_item
        """).fetchall()
        print("ITEM HASIL PANEN:")
        for row in items:
            print(
                f"  {row['kode_item']} | {row['nama_item']} | "
                f"akun={row['kode_akun']} | item_id={row['id']}"
            )
        print()

        penjualan = koneksi.execute("""
            SELECT
                je.id,
                je.tanggal,
                je.no_bukti,
                je.journal_type,
                je.keterangan,
                SUM(jl.kredit) AS total_penjualan,
                COALESCE((
                    SELECT SUM(hpp.debit)
                    FROM journal_lines hpp
                    JOIN accounts ahpp ON ahpp.id = hpp.account_id
                    WHERE hpp.journal_entry_id = je.id
                      AND ahpp.kode_akun = '5108'
                ), 0) AS total_hpp,
                (
                    SELECT COUNT(*)
                    FROM inventory_movements im
                    WHERE im.journal_entry_id = je.id
                ) AS jumlah_mutasi_terkait
            FROM journal_entries je
            JOIN journal_lines jl ON jl.journal_entry_id = je.id
            JOIN accounts a ON a.id = jl.account_id
            WHERE je.journal_type IN ('penjualan', 'penerimaan_kas')
              AND a.kode_akun = '4101'
              AND jl.kredit > 0
              AND je.keterangan LIKE 'Penjualan cabai%'
            GROUP BY je.id, je.tanggal, je.no_bukti, je.journal_type, je.keterangan
            ORDER BY je.tanggal, je.id
        """).fetchall()

        print(f"PENJUALAN CABAI (4101, deskripsi cabai): {len(penjualan)} transaksi")
        total_qty = 0.0
        belum_hpp = 0
        tidak_terbaca = 0
        for row in penjualan:
            match = POLA_QTY.search(row["keterangan"] or "")
            qty = None
            if match:
                qty = float(match.group(1).replace(",", "."))
                total_qty += qty
            else:
                tidak_terbaca += 1

            if int(row["total_hpp"] or 0) == 0:
                belum_hpp += 1

            qty_label = f"{qty:g} kg" if qty is not None else "QTY TIDAK TERBACA"
            print(
                f"  id={row['id']} | {row['tanggal']} | {row['no_bukti']} | "
                f"{row['journal_type']} | {qty_label} | "
                f"penjualan=Rp{int(row['total_penjualan'] or 0):,} | "
                f"HPP=Rp{int(row['total_hpp'] or 0):,} | "
                f"mutasi_terkait={row['jumlah_mutasi_terkait']}"
            )
            print(f"    {row['keterangan']}")

        print()
        print(f"Total kuantitas yang terbaca : {total_qty:g} kg")
        print(f"Transaksi belum punya HPP   : {belum_hpp}")
        print(f"Keterangan tanpa kuantitas  : {tidak_terbaca}")
        print()

        for item in items:
            if item["kode_item"] != "HSL-001":
                continue

            movements = koneksi.execute("""
                SELECT id, tanggal, tipe_gerakan, qty, harga_satuan,
                       total_nilai, saldo_qty, saldo_nilai, harga_rata2,
                       journal_entry_id, keterangan
                FROM inventory_movements
                WHERE item_id = ?
                ORDER BY tanggal, id
            """, (item["id"],)).fetchall()

            print("RIWAYAT KARTU PERSEDIAAN HSL-001:")
            if not movements:
                print("  Tidak ada mutasi persediaan.")
            for row in movements:
                print(
                    f"  id={row['id']} | {row['tanggal']} | {row['tipe_gerakan']} | "
                    f"qty={row['qty']} | harga={row['harga_satuan']} | "
                    f"nilai={row['total_nilai']} | saldo_qty={row['saldo_qty']} | "
                    f"saldo_nilai={row['saldo_nilai']} | rata2={row['harga_rata2']} | "
                    f"journal_id={row['journal_entry_id']}"
                )
                print(f"    {row['keterangan']}")

            saldo_awal = [m for m in movements if m["tipe_gerakan"] == "saldo_awal"]
            print()
            print("SALDO AWAL AKUN PERSEDIAAN 1307 (SEMUA PERIODE):")
            opening = koneksi.execute("""
                SELECT p.tahun, p.bulan, p.nama_bulan,
                       ob.saldo_debit, ob.saldo_kredit, ob.catatan
                FROM opening_balances ob
                JOIN accounts a ON a.id = ob.account_id
                JOIN periods p ON p.id = ob.period_id
                WHERE a.kode_akun = '1307'
                ORDER BY p.tahun, p.bulan
            """).fetchall()
            if not opening:
                print("  TIDAK ADA SALDO AWAL AKUN 1307.")
            for row in opening:
                print(
                    f"  {row['nama_bulan']} {row['tahun']} | "
                    f"debit={row['saldo_debit']} | kredit={row['saldo_kredit']} | "
                    f"catatan={row['catatan']}"
                )
            print(
                f"Snapshot saldo_awal pada kartu item: "
                f"{'ADA' if saldo_awal else 'TIDAK ADA'}"
            )
            print()

        print("PENDAPATAN 4XXX NON-PENJUALAN (untuk cek peringatan yang terlalu luas):")
        lainnya = koneksi.execute("""
            SELECT je.id, je.tanggal, je.no_bukti, je.journal_type,
                   je.keterangan, a.kode_akun, a.nama_akun, jl.kredit
            FROM journal_entries je
            JOIN journal_lines jl ON jl.journal_entry_id = je.id
            JOIN accounts a ON a.id = jl.account_id
            WHERE a.kode_akun LIKE '4%'
              AND a.kode_akun != '4101'
              AND jl.kredit > 0
            ORDER BY je.tanggal, je.id
        """).fetchall()
        if not lainnya:
            print("  Tidak ada.")
        for row in lainnya:
            print(
                f"  id={row['id']} | {row['tanggal']} | {row['no_bukti']} | "
                f"{row['kode_akun']} {row['nama_akun']} | "
                f"Rp{int(row['kredit']):,} | {row['keterangan']}"
            )

        print()
        print("Pemeriksaan selesai. Database tidak diubah.")
    finally:
        koneksi.close()


if __name__ == "__main__":
    main()
