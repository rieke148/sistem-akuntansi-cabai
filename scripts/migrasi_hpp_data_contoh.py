"""
scripts/migrasi_hpp_data_contoh.py

Pratinjau dan migrasi data CONTOH dari pencatatan periodik ke perpetual.
Default hanya membaca database. Perubahan hanya dilakukan dengan --apply.

Jalankan dari folder utama:
    python scripts/migrasi_hpp_data_contoh.py
    python scripts/migrasi_hpp_data_contoh.py --apply

Asumsi contoh: saldo awal HSL-001 = 3.000 kg @ Rp25.000/kg,
periode dasar Oktober 2026, akun persediaan 1307, akun HPP 5108.
Jangan gunakan pada data observasi/produksi aktual tanpa rekonsiliasi.
"""
from __future__ import annotations

import argparse
import math
import re
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database.connection import PATH_DATABASE, get_connection

PERIODE_TAHUN = 2026
PERIODE_BULAN = 10
PERIODE_TANGGAL = "2026-10-01"
KODE_ITEM = "HSL-001"
QTY_AWAL = 3000.0
HARGA_AWAL = 25000
NILAI_AWAL = 75_000_000
KODE_PERSEDIAAN = "1307"
KODE_PENJUALAN = "4101"
KODE_HPP = "5108"
KODE_PENDAPATAN_LAIN = "4901"
POLA_QTY = re.compile(r"(\d+(?:[.,]\d+)?)\s*kg\s*@", re.IGNORECASE)


def akun_id(conn: sqlite3.Connection, kode: str) -> int:
    row = conn.execute(
        "SELECT id FROM accounts WHERE kode_akun=? AND aktif=1", (kode,)
    ).fetchone()
    if not row:
        raise ValueError(f"Akun {kode} tidak ditemukan atau tidak aktif.")
    return int(row["id"])


def periode_id(conn: sqlite3.Connection, tahun: int, bulan: int) -> sqlite3.Row:
    row = conn.execute(
        "SELECT id,tahun,bulan,nama_bulan,status FROM periods WHERE tahun=? AND bulan=?",
        (tahun, bulan),
    ).fetchone()
    if not row:
        raise ValueError(f"Periode {bulan:02d}/{tahun} tidak ditemukan.")
    if row["status"] == "tutup":
        raise ValueError(f"Periode {row['nama_bulan']} sudah ditutup.")
    return row


def saldo_akun_jurnal(conn: sqlite3.Connection, entry_id: int, kode: str) -> tuple[int, int]:
    row = conn.execute(
        """
        SELECT COALESCE(SUM(jl.debit),0) debit,
               COALESCE(SUM(jl.kredit),0) kredit
        FROM journal_lines jl JOIN accounts a ON a.id=jl.account_id
        WHERE jl.journal_entry_id=? AND a.kode_akun=?
        """,
        (entry_id, kode),
    ).fetchone()
    return int(row["debit"]), int(row["kredit"])


def parse_qty(teks: str, no_bukti: str) -> float:
    match = POLA_QTY.search(teks or "")
    if not match:
        raise ValueError(f"Kuantitas kg tidak terbaca pada {no_bukti}: {teks}")
    qty = float(match.group(1).replace(",", "."))
    if qty <= 0:
        raise ValueError(f"Kuantitas {no_bukti} harus lebih besar dari nol.")
    return qty


def build_plan(conn: sqlite3.Connection) -> dict:
    aid_inv = akun_id(conn, KODE_PERSEDIAAN)
    aid_hpp = akun_id(conn, KODE_HPP)
    aid_lain = akun_id(conn, KODE_PENDAPATAN_LAIN)
    p = periode_id(conn, PERIODE_TAHUN, PERIODE_BULAN)
    pid = int(p["id"])

    items = conn.execute(
        "SELECT id,account_id,aktif FROM items WHERE kode_item=?", (KODE_ITEM,)
    ).fetchall()
    if len(items) != 1 or not items[0]["aktif"] or int(items[0]["account_id"] or 0) != aid_inv:
        raise ValueError(f"Item {KODE_ITEM} harus ada satu, aktif, dan terhubung ke akun 1307.")
    item_id = int(items[0]["id"])
    item_lain = conn.execute(
        "SELECT kode_item FROM items WHERE account_id=? AND aktif=1 AND id!=?",
        (aid_inv, item_id),
    ).fetchall()
    if item_lain:
        raise ValueError(
            "Akun 1307 dipakai item lain. Saldo awal per item perlu direkonsiliasi dahulu."
        )

    ob = conn.execute(
        "SELECT saldo_debit,saldo_kredit FROM opening_balances "
        "WHERE period_id=? AND account_id=?",
        (pid, aid_inv),
    ).fetchone()
    if ob and (int(ob["saldo_debit"]) != NILAI_AWAL or int(ob["saldo_kredit"]) != 0):
        raise ValueError("Saldo awal akun 1307 sudah ada dengan nilai berbeda; tidak ditimpa.")

    opening_rows = conn.execute(
        """
        SELECT id,tanggal,qty,harga_satuan,total_nilai
        FROM inventory_movements
        WHERE item_id=? AND tipe_gerakan='saldo_awal'
        ORDER BY tanggal,id
        """,
        (item_id,),
    ).fetchall()
    if len(opening_rows) > 1:
        raise ValueError("Ada lebih dari satu snapshot saldo awal HSL-001.")
    opening = opening_rows[0] if opening_rows else None
    if opening and (
        opening["tanggal"] != PERIODE_TANGGAL
        or not math.isclose(float(opening["qty"]), QTY_AWAL, abs_tol=1e-9, rel_tol=0)
        or int(opening["harga_satuan"]) != HARGA_AWAL
        or int(opening["total_nilai"]) != NILAI_AWAL
    ):
        raise ValueError("Snapshot saldo awal yang ada berbeda dari asumsi contoh; migrasi dihentikan.")

    sale_rows = conn.execute(
        """
        SELECT DISTINCT je.id,je.period_id,je.tanggal,je.no_bukti,
               je.journal_type,je.keterangan
        FROM journal_entries je
        JOIN journal_lines jl ON jl.journal_entry_id=je.id
        JOIN accounts a ON a.id=jl.account_id
        WHERE je.journal_type IN ('penjualan','penerimaan_kas')
          AND a.kode_akun=? AND jl.kredit>0
          AND je.keterangan LIKE 'Penjualan cabai%'
        ORDER BY je.tanggal,je.id
        """,
        (KODE_PENJUALAN,),
    ).fetchall()
    if not sale_rows:
        raise ValueError("Tidak ditemukan transaksi Penjualan Cabai berkode akun 4101.")

    sales = []
    sales_by_id = {}
    for row in sale_rows:
        eid = int(row["id"])
        hpp_d, hpp_k = saldo_akun_jurnal(conn, eid, KODE_HPP)
        inv_d, inv_k = saldo_akun_jurnal(conn, eid, KODE_PERSEDIAAN)
        any_lines = any((hpp_d, hpp_k, inv_d, inv_k))
        if any_lines and not (hpp_d > 0 and hpp_k == 0 and inv_d == 0 and inv_k == hpp_d):
            raise ValueError(f"Jurnal {row['no_bukti']} memiliki baris HPP/persediaan tidak berpasangan.")
        sale = {
            "id": eid,
            "period_id": int(row["period_id"]),
            "tanggal": row["tanggal"],
            "no_bukti": row["no_bukti"],
            "journal_type": row["journal_type"],
            "keterangan": row["keterangan"],
            "qty": parse_qty(row["keterangan"], row["no_bukti"]),
            "hpp_existing": hpp_d if any_lines else None,
        }
        sales.append(sale)
        sales_by_id[eid] = sale

    movements = conn.execute(
        """
        SELECT id,journal_entry_id,tanggal,tipe_gerakan,qty,harga_satuan,
               total_nilai,saldo_qty,saldo_nilai,harga_rata2,keterangan
        FROM inventory_movements WHERE item_id=?
        ORDER BY tanggal,COALESCE(journal_entry_id,id),id
        """,
        (item_id,),
    ).fetchall()
    by_sale = {}
    for m in movements:
        if m["journal_entry_id"] is not None:
            eid = int(m["journal_entry_id"])
            if eid in sales_by_id:
                by_sale.setdefault(eid, []).append(m)
            elif m["tipe_gerakan"] == "keluar":
                raise ValueError(
                    f"Mutasi keluar HSL-001 ID {m['id']} terkait jurnal non-penjualan {eid}."
                )
        if m["tipe_gerakan"] == "keluar":
            eid = m["journal_entry_id"]
            if eid is None or int(eid) not in sales_by_id:
                raise ValueError("Ada mutasi keluar HSL-001 yang bukan penjualan cabai terpilih.")

    for eid, rows in by_sale.items():
        if len(rows) != 1 or rows[0]["tipe_gerakan"] != "keluar":
            raise ValueError(f"Mutasi untuk transaksi penjualan ID {eid} tidak valid.")
        m = rows[0]
        sale = sales_by_id[eid]
        if m["tanggal"] != sale["tanggal"] or not math.isclose(
            float(m["qty"]), sale["qty"], abs_tol=1e-6, rel_tol=0
        ):
            raise ValueError(f"Tanggal/kuantitas mutasi tidak sama dengan jurnal {sale['no_bukti']}.")

    # Saldo awal, mutasi yang ada, dan penjualan yang belum memiliki mutasi.
    events = [{
        "kind": "opening",
        "tanggal": opening["tanggal"] if opening else PERIODE_TANGGAL,
        "seq": -1,
        "movement_id": int(opening["id"]) if opening else None,
        "row": opening,
    }]
    for m in movements:
        if m["tipe_gerakan"] == "saldo_awal":
            continue
        seq = int(m["journal_entry_id"]) if m["journal_entry_id"] is not None else int(m["id"])
        events.append({
            "kind": "movement", "tanggal": m["tanggal"], "seq": seq,
            "movement_id": int(m["id"]), "row": m,
        })
    for sale in sales:
        if sale["id"] not in by_sale:
            events.append({
                "kind": "sale", "tanggal": sale["tanggal"], "seq": sale["id"],
                "movement_id": None, "sale": sale,
            })
    events.sort(key=lambda e: (e["tanggal"], e["seq"], 0 if e["kind"] == "opening" else 1))

    qty_balance = 0.0
    value_balance = 0
    avg = 0
    total_hpp = 0
    updates = []
    inserts = []

    for e in events:
        if e["kind"] == "opening":
            if qty_balance != 0 or value_balance != 0:
                raise ValueError("Saldo awal bukan peristiwa persediaan pertama.")
            qty_balance = QTY_AWAL
            value_balance = NILAI_AWAL
            avg = HARGA_AWAL
            payload = {
                "qty": QTY_AWAL, "harga_satuan": HARGA_AWAL,
                "total_nilai": NILAI_AWAL, "saldo_qty": qty_balance,
                "saldo_nilai": value_balance, "harga_rata2": avg,
                "keterangan": "CONTOH - saldo awal hasil panen cabai; 3.000 kg @ Rp25.000/kg",
            }
            if e["movement_id"] is None:
                inserts.append({
                    "item_id": item_id, "journal_entry_id": None,
                    "tanggal": PERIODE_TANGGAL, "tipe_gerakan": "saldo_awal",
                    **payload,
                })
            else:
                updates.append({"id": e["movement_id"], "tanggal": PERIODE_TANGGAL,
                                "tipe_gerakan": "saldo_awal", **payload})
            continue

        if e["kind"] == "movement":
            m = e["row"]
            mid = int(m["id"])
            qty = float(m["qty"])
            if qty <= 0:
                raise ValueError(f"Mutasi persediaan ID {mid} mempunyai kuantitas tidak valid.")
            if m["tipe_gerakan"] == "masuk":
                amount = int(m["total_nilai"])
                unit = int(m["harga_satuan"])
                if amount < 0 or unit < 0:
                    raise ValueError(f"Nilai mutasi masuk ID {mid} tidak valid.")
                qty_balance += qty
                value_balance += amount
                avg = int(value_balance / qty_balance) if qty_balance else 0
                updates.append({
                    "id": mid, "tanggal": m["tanggal"], "tipe_gerakan": "masuk",
                    "qty": qty, "harga_satuan": unit, "total_nilai": amount,
                    "saldo_qty": qty_balance, "saldo_nilai": value_balance,
                    "harga_rata2": avg, "keterangan": m["keterangan"],
                })
                continue
            if m["tipe_gerakan"] != "keluar":
                raise ValueError(f"Tipe mutasi {m['tipe_gerakan']} pada ID {mid} tidak dikenal.")
            sale = sales_by_id[int(m["journal_entry_id"])]
            qty_out = qty
        else:
            sale = e["sale"]
            qty_out = float(sale["qty"])
            m = None

        if qty_balance <= 0 or qty_out - qty_balance > 1e-9:
            raise ValueError(
                f"Stok tidak cukup pada {sale['no_bukti']}: "
                f"tersedia {qty_balance:g} kg, dibutuhkan {qty_out:g} kg."
            )
        unit_before = avg
        hpp = (
            value_balance
            if math.isclose(qty_out, qty_balance, abs_tol=1e-9, rel_tol=0)
            else int(qty_out * unit_before)
        )
        if math.isclose(qty_out, qty_balance, abs_tol=1e-9, rel_tol=0):
            qty_balance, value_balance, avg = 0.0, 0, 0
        else:
            qty_balance -= qty_out
            value_balance = max(0, value_balance - hpp)

        sale["hpp_expected"] = int(hpp)
        total_hpp += int(hpp)
        payload = {
            "qty": qty_out,
            "harga_satuan": unit_before,
            "total_nilai": int(hpp),
            "saldo_qty": qty_balance,
            "saldo_nilai": value_balance,
            "harga_rata2": avg,
            "keterangan": (
                m["keterangan"] if m is not None
                else "HPP penjualan cabai (migrasi data contoh) - " + sale["keterangan"]
            ),
        }
        if m is not None:
            updates.append({
                "id": int(m["id"]), "tanggal": m["tanggal"],
                "tipe_gerakan": "keluar", **payload,
            })
        else:
            inserts.append({
                "item_id": item_id, "journal_entry_id": sale["id"],
                "tanggal": sale["tanggal"], "tipe_gerakan": "keluar",
                **payload,
            })

    hpp_to_add = []
    for sale in sales:
        expected = int(sale.get("hpp_expected", 0))
        if expected <= 0:
            raise ValueError(f"HPP {sale['no_bukti']} terhitung nol.")
        if sale["hpp_existing"] is not None:
            if int(sale["hpp_existing"]) != expected:
                raise ValueError(
                    f"HPP {sale['no_bukti']} sudah Rp{sale['hpp_existing']:,}, "
                    f"hasil hitung ulang Rp{expected:,}. Migrasi dihentikan."
                )
        else:
            hpp_to_add.append({
                "entry_id": sale["id"], "no_bukti": sale["no_bukti"], "hpp": expected,
            })

    # Entri Oktober yang salah ditempatkan pada periode lain dipindahkan ke Oktober.
    move_rows = conn.execute(
        """
        SELECT je.id,je.no_bukti,je.tanggal,je.period_id,p.nama_bulan periode_lama
        FROM journal_entries je JOIN periods p ON p.id=je.period_id
        WHERE substr(je.tanggal,1,7)='2026-10' AND je.period_id!=?
        ORDER BY je.tanggal,je.id
        """,
        (pid,),
    ).fetchall()
    source_ids = sorted({int(r["period_id"]) for r in move_rows})
    if source_ids:
        marks = ",".join("?" for _ in source_ids)
        opening_nonzero = conn.execute(
            f"SELECT COUNT(*) jumlah FROM opening_balances "
            f"WHERE period_id IN ({marks}) AND (saldo_debit!=0 OR saldo_kredit!=0)",
            source_ids,
        ).fetchone()["jumlah"]
        if int(opening_nonzero or 0):
            raise ValueError(
                "Ada saldo awal nonzero pada periode sumber transaksi Oktober. "
                "Rekonsiliasi periode perlu dilakukan manual."
            )

    nov = conn.execute(
        "SELECT id FROM periods WHERE tahun=2026 AND bulan=11"
    ).fetchone()
    nov_mismatch = []
    if nov:
        nov_mismatch = conn.execute(
            """
            SELECT id,no_bukti,tanggal,period_id FROM journal_entries
            WHERE substr(tanggal,1,7)='2026-11' AND period_id!=?
            ORDER BY tanggal,id
            """,
            (int(nov["id"]),),
        ).fetchall()

    # Penjualan selada lama tidak boleh ikut menjadi pendapatan penjualan cabai.
    legacy = conn.execute(
        """
        SELECT DISTINCT je.id,jl.id line_id,je.keterangan
        FROM journal_entries je
        JOIN journal_lines jl ON jl.journal_entry_id=je.id
        JOIN accounts a ON a.id=jl.account_id
        WHERE a.kode_akun='4101' AND jl.kredit>0
          AND lower(je.keterangan) LIKE '%penjualan selada%'
        ORDER BY je.id,jl.id
        """
    ).fetchall()

    return {
        "period_id": pid, "period_label": p["nama_bulan"],
        "item_id": item_id, "akun_inv_id": aid_inv,
        "akun_hpp_id": aid_hpp, "akun_lain_id": aid_lain,
        "opening_balance_exists": ob is not None,
        "opening_movement_exists": opening is not None,
        "sales": sales, "sales_qty": sum(float(s["qty"]) for s in sales),
        "hpp_total": total_hpp, "hpp_to_add": hpp_to_add,
        "updates": updates, "inserts": inserts,
        "ending_qty": qty_balance, "ending_value": value_balance, "ending_avg": avg,
        "move_rows": [dict(r) for r in move_rows],
        "legacy": [dict(r) for r in legacy],
        "nov_mismatch": [dict(r) for r in nov_mismatch],
    }


def rupiah(value: int) -> str:
    return "Rp" + f"{int(value):,}".replace(",", ".")


def print_plan(plan: dict) -> None:
    print("=" * 76)
    print("PRATINJAU MIGRASI HPP DATA CONTOH — DATABASE TIDAK DIUBAH")
    print("=" * 76)
    print(f"Database: {PATH_DATABASE}")
    print(f"Periode dasar: {plan['period_label']} (ID {plan['period_id']})")
    print()
    print("SALDO AWAL CONTOH:")
    print(f"  HSL-001: {QTY_AWAL:,.1f} kg @ {rupiah(HARGA_AWAL)}/kg".replace(",", "."))
    print(f"  Nilai: {rupiah(NILAI_AWAL)}")
    print("  Snapshot kartu: " + ("sudah ada" if plan["opening_movement_exists"] else "akan ditambahkan"))
    print("  Saldo awal akun 1307: " + ("sudah ada" if plan["opening_balance_exists"] else "akan ditambahkan"))
    print()
    print("PENJUALAN CABAI:")
    print(f"  Transaksi: {len(plan['sales'])}")
    print(f"  Kuantitas: {plan['sales_qty']:,.4f} kg".replace(",", "."))
    print(f"  HPP total: {rupiah(plan['hpp_total'])}")
    print(f"  HPP sudah ada: {len(plan['sales']) - len(plan['hpp_to_add'])}")
    print(f"  Jurnal HPP yang akan ditambahkan: {len(plan['hpp_to_add'])}")
    for row in plan["hpp_to_add"]:
        print(f"    {row['no_bukti']}: {rupiah(row['hpp'])}")
    print()
    print("SALDO AKHIR KARTU PERSEDIAAN:")
    print(f"  Kuantitas: {plan['ending_qty']:,.4f} kg".replace(",", "."))
    print(f"  Nilai: {rupiah(plan['ending_value'])}")
    print(f"  Rata-rata: {rupiah(plan['ending_avg'])}/kg")
    print(f"  Mutasi diperbarui: {len(plan['updates'])}")
    print(f"  Mutasi ditambahkan: {len(plan['inserts'])}")
    print()
    print(f"ENTRI OKTOBER YANG DIPINDAHKAN KE {plan['period_label']}: {len(plan['move_rows'])}")
    for row in plan["move_rows"]:
        print(
            f"  ID {row['id']} | {row['no_bukti']} | {row['tanggal']} | "
            f"dari {row['periode_lama']}"
        )
    print()
    print(f"TRANSAKSI NOVEMBER YANG TETAP DI PERIODE SAAT INI: {len(plan['nov_mismatch'])}")
    for row in plan["nov_mismatch"]:
        print(
            f"  ID {row['id']} | {row['no_bukti']} | {row['tanggal']} | "
            f"period_id={row['period_id']}"
        )
    print(
        "Catatan: transaksi November tidak dipindahkan otomatis karena saldo "
        "awal November untuk seluruh akun perlu direkonsiliasi terpisah."
    )
    print()
    print(f"PENJUALAN SELADA YANG DIREKLASIFIKASI KE 4901: {len(plan['legacy'])}")
    for row in plan["legacy"]:
        print(f"  ID {row['id']} | {row['keterangan']}")
    print()
    print("Tidak ada perubahan yang dilakukan.")
    print("Untuk menerapkan setelah meninjau pratinjau:")
    print("  python scripts/migrasi_hpp_data_contoh.py --apply")
    print("=" * 76)


def backup_database() -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = PATH_DATABASE.with_name(
        f"{PATH_DATABASE.stem}.backup_hpp_{stamp}{PATH_DATABASE.suffix}"
    )
    with sqlite3.connect(str(PATH_DATABASE)) as source:
        with sqlite3.connect(str(path)) as target:
            source.backup(target)
    return path


def apply_plan(conn: sqlite3.Connection, plan: dict) -> None:
    for row in plan["move_rows"]:
        conn.execute(
            "UPDATE journal_entries SET period_id=? WHERE id=?",
            (plan["period_id"], int(row["id"])),
        )

    if not plan["opening_balance_exists"]:
        conn.execute(
            """
            INSERT INTO opening_balances
                (period_id,account_id,saldo_debit,saldo_kredit,catatan)
            VALUES (?,?,?,0,?)
            """,
            (
                plan["period_id"], plan["akun_inv_id"], NILAI_AWAL,
                "CONTOH - 3.000 kg @ Rp25.000/kg; migrasi saldo awal perpetual",
            ),
        )

    for row in plan["updates"]:
        conn.execute(
            """
            UPDATE inventory_movements
            SET tanggal=?,tipe_gerakan=?,qty=?,harga_satuan=?,total_nilai=?,
                saldo_qty=?,saldo_nilai=?,harga_rata2=?,keterangan=?
            WHERE id=?
            """,
            (
                row["tanggal"], row["tipe_gerakan"], row["qty"], row["harga_satuan"],
                row["total_nilai"], row["saldo_qty"], row["saldo_nilai"],
                row["harga_rata2"], row["keterangan"], row["id"],
            ),
        )

    for row in plan["inserts"]:
        conn.execute(
            """
            INSERT INTO inventory_movements
                (item_id,journal_entry_id,tanggal,tipe_gerakan,qty,harga_satuan,
                 total_nilai,saldo_qty,saldo_nilai,harga_rata2,keterangan)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                row["item_id"], row["journal_entry_id"], row["tanggal"],
                row["tipe_gerakan"], row["qty"], row["harga_satuan"],
                row["total_nilai"], row["saldo_qty"], row["saldo_nilai"],
                row["harga_rata2"], row["keterangan"],
            ),
        )

    for row in plan["hpp_to_add"]:
        conn.execute(
            """
            INSERT INTO journal_lines
                (journal_entry_id,account_id,debit,kredit,keterangan)
            VALUES (?,?,?,0,?)
            """,
            (
                row["entry_id"], plan["akun_hpp_id"], row["hpp"],
                "HPP Penjualan Cabai - migrasi data contoh",
            ),
        )
        conn.execute(
            """
            INSERT INTO journal_lines
                (journal_entry_id,account_id,debit,kredit,keterangan)
            VALUES (?,?,0,?,?)
            """,
            (
                row["entry_id"], plan["akun_inv_id"], row["hpp"],
                "Pengurangan Persediaan Cabai - migrasi data contoh",
            ),
        )

    for row in plan["legacy"]:
        conn.execute(
            "UPDATE journal_lines SET account_id=? WHERE id=?",
            (plan["akun_lain_id"], int(row["line_id"])),
        )
        conn.execute(
            "UPDATE journal_entries SET komoditas='umum' WHERE id=?",
            (int(row["id"]),),
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pratinjau atau terapkan migrasi HPP database contoh."
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="Buat backup database lalu terapkan migrasi.",
    )
    args = parser.parse_args()

    if not PATH_DATABASE.exists():
        raise FileNotFoundError(f"Database tidak ditemukan: {PATH_DATABASE}")

    conn = get_connection()
    try:
        plan = build_plan(conn)
    finally:
        conn.close()

    print_plan(plan)
    if not args.apply:
        return

    print()
    print("Membuat backup database...")
    backup = backup_database()
    print(f"Backup: {backup}")

    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        # Rencana dihitung ulang di dalam transaksi untuk mencegah data berubah
        # antara pratinjau dan penerapan.
        latest_plan = build_plan(conn)
        apply_plan(conn, latest_plan)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print()
    print("MIGRASI SELESAI.")
    print(f"Jurnal HPP ditambahkan: {len(latest_plan['hpp_to_add'])}")
    print(f"Mutasi kartu ditambahkan: {len(latest_plan['inserts'])}")
    print(f"Saldo akhir contoh: {latest_plan['ending_qty']:,.4f} kg")
    print(f"Nilai saldo akhir: {rupiah(latest_plan['ending_value'])}")
    print("Jalankan diagnostik dan pytest untuk verifikasi.")


if __name__ == "__main__":
    main()
