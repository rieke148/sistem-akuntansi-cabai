"""
scripts/migrasi_hpp_data_contoh.py

Pratinjau dan migrasi data CONTOH dari pencatatan periodik ke perpetual.
Default hanya membaca database. Perubahan hanya dilakukan dengan --apply.

Jalankan dari folder utama:
    python scripts/migrasi_hpp_data_contoh.py
    python scripts/migrasi_hpp_data_contoh.py --apply

Asumsi data contoh:
- Saldo awal HSL-001 pada 1 Oktober 2026 = 3.000 kg @ Rp25.000/kg.
- Periode Oktober dan November 2026.
- Akun persediaan 1307, HPP 5108, dan pendapatan lain-lain 4901.

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

TAHUN = 2026
BULAN_OKTOBER = 10
BULAN_NOVEMBER = 11
TANGGAL_AWAL_OKTOBER = "2026-10-01"
TANGGAL_AWAL_NOVEMBER = "2026-11-01"
KODE_ITEM = "HSL-001"
QTY_AWAL = 3000.0
HARGA_AWAL = 25000
NILAI_AWAL = 75_000_000
KODE_PERSEDIAAN = "1307"
KODE_PENJUALAN = "4101"
KODE_HPP = "5108"
KODE_PENDAPATAN_LAIN = "4901"
KODE_LABA_DITAHAN = "3201"
KODE_IKHTISAR_LR = "3301"
MARKER_SALDO_AWAL_NOV = (
    "MIGRASI DATA CONTOH - saldo akhir Oktober 2026; "
    "laba/rugi Oktober ditutup ke laba ditahan"
)
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


def saldo_akun_jurnal(
    conn: sqlite3.Connection, entry_id: int, kode: str
) -> tuple[int, int]:
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


def hitung_saldo_awal_november(
    conn: sqlite3.Connection,
    period_oktober_id: int,
    period_november_id: int,
    akun_inv_id: int,
    akun_hpp_id: int,
    akun_penjualan_id: int,
    akun_lain_id: int,
    sales: list[dict],
    hpp_to_add: list[dict],
    legacy: list[dict],
    nilai_persediaan_awal_november: int,
) -> dict:
    """
    Bentuk saldo awal November dari posisi akhir Oktober.

    Akun aset, liabilitas, dan ekuitas dibawa ke November. Akun pendapatan
    serta beban direset agar Laba Rugi November hanya memuat aktivitas November.
    Laba/rugi Oktober dipindahkan ke akun Laba Ditahan (3201).
    """
    akun_rows = conn.execute(
        "SELECT id,kode_akun,kategori,aktif FROM accounts"
    ).fetchall()
    akun_by_id = {int(r["id"]): dict(r) for r in akun_rows}
    akun_by_kode = {r["kode_akun"]: int(r["id"]) for r in akun_rows}

    if KODE_LABA_DITAHAN not in akun_by_kode:
        raise ValueError("Akun Laba Ditahan (3201) tidak ditemukan.")
    retained_id = akun_by_kode[KODE_LABA_DITAHAN]
    summary_id = akun_by_kode.get(KODE_IKHTISAR_LR)

    # Periksa saldo awal November sebelum validasi lain agar saldo manual
    # tidak pernah tertimpa atau tertutup pesan kesalahan yang tidak relevan.
    existing_rows = conn.execute(
        """
        SELECT account_id,saldo_debit,saldo_kredit,catatan
        FROM opening_balances WHERE period_id=?
        """,
        (period_november_id,),
    ).fetchall()
    if existing_rows and not all(
        row["catatan"] == MARKER_SALDO_AWAL_NOV for row in existing_rows
    ):
        raise ValueError(
            "Sudah ada saldo awal November yang bukan hasil migrasi ini. "
            "Migrasi tidak akan menimpa input manual; rekonsiliasi dahulu."
        )

    # Saldo awal Oktober adalah titik awal perhitungan.
    saldo = {aid: 0 for aid in akun_by_id}
    opening_rows = conn.execute(
        """
        SELECT account_id,saldo_debit,saldo_kredit
        FROM opening_balances WHERE period_id=?
        """,
        (period_oktober_id,),
    ).fetchall()
    for row in opening_rows:
        aid = int(row["account_id"])
        saldo[aid] = saldo.get(aid, 0) + int(row["saldo_debit"]) - int(row["saldo_kredit"])

    inv_opening_exists = any(int(r["account_id"]) == akun_inv_id for r in opening_rows)
    if not inv_opening_exists:
        saldo[akun_inv_id] = saldo.get(akun_inv_id, 0) + NILAI_AWAL

    # Mutasi semua jurnal bertanggal Oktober, termasuk yang saat ini salah periode.
    journal_rows = conn.execute(
        """
        SELECT jl.account_id,
               COALESCE(SUM(jl.debit),0) debit,
               COALESCE(SUM(jl.kredit),0) kredit
        FROM journal_lines jl
        JOIN journal_entries je ON je.id=jl.journal_entry_id
        WHERE substr(je.tanggal,1,7)='2026-10'
        GROUP BY jl.account_id
        """
    ).fetchall()
    for row in journal_rows:
        aid = int(row["account_id"])
        saldo[aid] = saldo.get(aid, 0) + int(row["debit"]) - int(row["kredit"])

    # Masukkan pasangan jurnal HPP yang masih akan dibuat untuk penjualan Oktober.
    sale_by_id = {int(s["id"]): s for s in sales}
    for row in hpp_to_add:
        sale = sale_by_id[int(row["entry_id"])]
        if str(sale["tanggal"]).startswith("2026-10"):
            amount = int(row["hpp"])
            saldo[akun_hpp_id] = saldo.get(akun_hpp_id, 0) + amount
            saldo[akun_inv_id] = saldo.get(akun_inv_id, 0) - amount

    # Simulasikan reklasifikasi penjualan selada dari akun 4101 ke akun 4901.
    for row in legacy:
        if str(row["tanggal"]).startswith("2026-10"):
            nilai_net_debit = int(row["debit"]) - int(row["kredit"])
            saldo[akun_penjualan_id] = saldo.get(akun_penjualan_id, 0) - nilai_net_debit
            saldo[akun_lain_id] = saldo.get(akun_lain_id, 0) + nilai_net_debit

    # Validasi saldo awal Oktober setelah saldo persediaan contoh ditambahkan.
    total_opening_debit = sum(int(r["saldo_debit"]) for r in opening_rows)
    total_opening_kredit = sum(int(r["saldo_kredit"]) for r in opening_rows)
    if not inv_opening_exists:
        total_opening_debit += NILAI_AWAL
    if total_opening_debit != total_opening_kredit:
        raise ValueError(
            "Saldo awal Oktober tidak seimbang setelah saldo persediaan contoh "
            f"diperhitungkan: debit {total_opening_debit:,}, "
            f"kredit {total_opening_kredit:,}. Rekonsiliasi dahulu."
        )

    # Pendapatan dan beban ditutup ke laba ditahan. Akun 3301 (jika digunakan)
    # ikut diperhitungkan sebagai ikhtisar hasil penutupan agar tidak dihitung ganda.
    saldo_temporer = 0
    for aid, info in akun_by_id.items():
        if info["kategori"] in ("Pendapatan", "Beban Produksi", "Beban Operasional"):
            saldo_temporer += saldo.get(aid, 0)
    if summary_id is not None:
        saldo_temporer += saldo.get(summary_id, 0)
    laba_bersih_oktober = -saldo_temporer

    # Saldo disimpan sebagai debit - kredit. Karena laba bersih positif
    # adalah saldo normal kredit pada Laba Ditahan, nilainya harus dikurangkan.
    # Jika rugi (negatif), operasi ini menghasilkan saldo debit.
    saldo[retained_id] = saldo.get(retained_id, 0) - laba_bersih_oktober

    # Saldo awal November berisi akun permanen. Akun pendapatan/beban dan
    # Ikhtisar Laba Rugi direset supaya laporan laba rugi November tidak kumulatif.
    saldo_awal_november = []
    for aid, info in akun_by_id.items():
        kategori = info["kategori"]
        kode = info["kode_akun"]
        if kategori not in ("Aset", "Liabilitas", "Ekuitas"):
            continue
        if kode == KODE_IKHTISAR_LR:
            continue

        net = int(saldo.get(aid, 0))
        if net == 0:
            continue
        debit = max(net, 0)
        kredit = max(-net, 0)
        saldo_awal_november.append({
            "account_id": aid,
            "saldo_debit": debit,
            "saldo_kredit": kredit,
            "catatan": MARKER_SALDO_AWAL_NOV,
        })

    total_debit = sum(r["saldo_debit"] for r in saldo_awal_november)
    total_kredit = sum(r["saldo_kredit"] for r in saldo_awal_november)
    if total_debit != total_kredit:
        raise ValueError(
            "Saldo awal November hasil carry forward tidak seimbang: "
            f"debit {total_debit:,}, kredit {total_kredit:,}. "
            "Migrasi dihentikan agar laporan tidak salah."
        )

    # Saldo buku besar akun 1307 harus sama dengan nilai kartu persediaan per 1 Nov.
    nilai_buku_persediaan = int(saldo.get(akun_inv_id, 0))
    if nilai_buku_persediaan != int(nilai_persediaan_awal_november):
        raise ValueError(
            "Nilai buku akun 1307 tidak sama dengan kartu persediaan per 1 November: "
            f"buku besar {nilai_buku_persediaan:,}, "
            f"kartu {int(nilai_persediaan_awal_november):,}. "
            "Periksa jurnal panen dan transaksi persediaan sebelum migrasi."
        )

    # Jangan menimpa saldo awal November yang pernah diinput manual.
    expected_map = {
        int(r["account_id"]): (int(r["saldo_debit"]), int(r["saldo_kredit"]))
        for r in saldo_awal_november
    }
    if existing_rows:
        existing_map = {
            int(r["account_id"]): (int(r["saldo_debit"]), int(r["saldo_kredit"]))
            for r in existing_rows
        }
        all_marked = all(r["catatan"] == MARKER_SALDO_AWAL_NOV for r in existing_rows)
        if not all_marked or existing_map != expected_map:
            raise ValueError(
                "Sudah ada saldo awal November yang bukan hasil migrasi ini, "
                "atau nilainya berbeda. Jangan ditimpa; rekonsiliasi manual dahulu."
            )
        rows_to_insert = []
    else:
        rows_to_insert = saldo_awal_november

    return {
        "rows": saldo_awal_november,
        "rows_to_insert": rows_to_insert,
        "total_debit": total_debit,
        "total_kredit": total_kredit,
        "laba_bersih_oktober": laba_bersih_oktober,
        "nilai_persediaan": nilai_buku_persediaan,
    }


def build_plan(conn: sqlite3.Connection) -> dict:
    aid_inv = akun_id(conn, KODE_PERSEDIAAN)
    aid_hpp = akun_id(conn, KODE_HPP)
    aid_sales = akun_id(conn, KODE_PENJUALAN)
    aid_lain = akun_id(conn, KODE_PENDAPATAN_LAIN)
    periode_okt = periode_id(conn, TAHUN, BULAN_OKTOBER)
    periode_nov = periode_id(conn, TAHUN, BULAN_NOVEMBER)
    pid_okt = int(periode_okt["id"])
    pid_nov = int(periode_nov["id"])

    items = conn.execute(
        "SELECT id,account_id,aktif FROM items WHERE kode_item=?", (KODE_ITEM,)
    ).fetchall()
    if (
        len(items) != 1
        or not items[0]["aktif"]
        or int(items[0]["account_id"] or 0) != aid_inv
    ):
        raise ValueError(
            f"Item {KODE_ITEM} harus ada satu, aktif, dan terhubung ke akun 1307."
        )
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
        """
        SELECT saldo_debit,saldo_kredit FROM opening_balances
        WHERE period_id=? AND account_id=?
        """,
        (pid_okt, aid_inv),
    ).fetchone()
    if ob and (
        int(ob["saldo_debit"]) != NILAI_AWAL
        or int(ob["saldo_kredit"]) != 0
    ):
        raise ValueError(
            "Saldo awal akun 1307 Oktober sudah ada dengan nilai berbeda; tidak ditimpa."
        )

    # Snapshot kartu yang didukung migrasi: awal Oktober dan awal November.
    opening_rows = conn.execute(
        """
        SELECT id,tanggal,qty,harga_satuan,total_nilai,saldo_qty,
               saldo_nilai,harga_rata2,keterangan
        FROM inventory_movements
        WHERE item_id=? AND tipe_gerakan='saldo_awal'
        ORDER BY tanggal,id
        """,
        (item_id,),
    ).fetchall()
    snapshots = {}
    for row in opening_rows:
        tanggal = row["tanggal"]
        if tanggal not in (TANGGAL_AWAL_OKTOBER, TANGGAL_AWAL_NOVEMBER):
            raise ValueError(
                f"Snapshot saldo awal HSL-001 pada {tanggal} di luar cakupan migrasi."
            )
        if tanggal in snapshots:
            raise ValueError(f"Ada lebih dari satu snapshot HSL-001 pada {tanggal}.")
        snapshots[tanggal] = row

    snapshot_okt = snapshots.get(TANGGAL_AWAL_OKTOBER)
    if snapshot_okt and (
        not math.isclose(float(snapshot_okt["qty"]), QTY_AWAL, abs_tol=1e-9, rel_tol=0)
        or int(snapshot_okt["harga_satuan"]) != HARGA_AWAL
        or int(snapshot_okt["total_nilai"]) != NILAI_AWAL
    ):
        raise ValueError(
            "Snapshot saldo awal Oktober yang ada berbeda dari asumsi contoh; migrasi dihentikan."
        )

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
        if any_lines and not (
            hpp_d > 0 and hpp_k == 0 and inv_d == 0 and inv_k == hpp_d
        ):
            raise ValueError(
                f"Jurnal {row['no_bukti']} memiliki baris HPP/persediaan tidak berpasangan."
            )
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
                raise ValueError(
                    "Ada mutasi keluar HSL-001 yang bukan penjualan cabai terpilih."
                )

    for eid, rows in by_sale.items():
        if len(rows) != 1 or rows[0]["tipe_gerakan"] != "keluar":
            raise ValueError(f"Mutasi untuk transaksi penjualan ID {eid} tidak valid.")
        m = rows[0]
        sale = sales_by_id[eid]
        if (
            m["tanggal"] != sale["tanggal"]
            or not math.isclose(
                float(m["qty"]), sale["qty"], abs_tol=1e-6, rel_tol=0
            )
        ):
            raise ValueError(
                f"Tanggal/kuantitas mutasi tidak sama dengan jurnal {sale['no_bukti']}."
            )

    # Sisipkan titik snapshot 1 Oktober dan 1 November sebagai checkpoint kronologis.
    events = []
    for tanggal in (TANGGAL_AWAL_OKTOBER, TANGGAL_AWAL_NOVEMBER):
        events.append({
            "kind": "snapshot",
            "tanggal": tanggal,
            "seq": -1,
            "row": snapshots.get(tanggal),
        })

    for m in movements:
        if m["tipe_gerakan"] == "saldo_awal":
            continue
        seq = (
            int(m["journal_entry_id"])
            if m["journal_entry_id"] is not None
            else int(m["id"])
        )
        events.append({
            "kind": "movement",
            "tanggal": m["tanggal"],
            "seq": seq,
            "movement_id": int(m["id"]),
            "row": m,
        })

    for sale in sales:
        if sale["id"] not in by_sale:
            events.append({
                "kind": "sale",
                "tanggal": sale["tanggal"],
                "seq": sale["id"],
                "movement_id": None,
                "sale": sale,
            })

    events.sort(
        key=lambda e: (
            e["tanggal"],
            e["seq"],
            0 if e["kind"] == "snapshot" else 1,
        )
    )

    qty_balance = 0.0
    value_balance = 0
    avg = 0
    initialized = False
    nov_opening_qty = None
    nov_opening_value = None
    nov_opening_avg = None
    hpp_by_month = {"2026-10": 0, "2026-11": 0}
    updates = []
    inserts = []

    for e in events:
        if e["kind"] == "snapshot":
            tanggal = e["tanggal"]
            existing = e["row"]
            if tanggal == TANGGAL_AWAL_OKTOBER:
                if initialized or qty_balance != 0 or value_balance != 0:
                    raise ValueError("Saldo awal Oktober bukan peristiwa persediaan pertama.")
                qty_balance = QTY_AWAL
                value_balance = NILAI_AWAL
                avg = HARGA_AWAL
                initialized = True
                payload = {
                    "qty": QTY_AWAL,
                    "harga_satuan": HARGA_AWAL,
                    "total_nilai": NILAI_AWAL,
                    "saldo_qty": qty_balance,
                    "saldo_nilai": value_balance,
                    "harga_rata2": avg,
                    "keterangan": (
                        "CONTOH - saldo awal hasil panen cabai; "
                        "3.000 kg @ Rp25.000/kg"
                    ),
                }
            else:
                if not initialized:
                    raise ValueError("Snapshot November ditemukan sebelum saldo awal Oktober.")
                nov_opening_qty = qty_balance
                nov_opening_value = value_balance
                nov_opening_avg = avg
                payload = {
                    "qty": qty_balance,
                    "harga_satuan": avg,
                    "total_nilai": value_balance,
                    "saldo_qty": qty_balance,
                    "saldo_nilai": value_balance,
                    "harga_rata2": avg,
                    "keterangan": (
                        "SALDO AWAL NOVEMBER - hasil saldo akhir kartu persediaan "
                        "per 31 Oktober 2026"
                    ),
                }

            if existing is None:
                inserts.append({
                    "item_id": item_id,
                    "journal_entry_id": None,
                    "tanggal": tanggal,
                    "tipe_gerakan": "saldo_awal",
                    **payload,
                })
            else:
                if tanggal == TANGGAL_AWAL_NOVEMBER:
                    beda = (
                        not math.isclose(float(existing["qty"]), qty_balance, abs_tol=1e-6, rel_tol=0)
                        or int(existing["total_nilai"]) != value_balance
                    )
                    if beda:
                        raise ValueError(
                            "Snapshot persediaan 1 November sudah ada tetapi berbeda "
                            "dari saldo akhir Oktober. Rekonsiliasi manual dahulu."
                        )
                updates.append({
                    "id": int(existing["id"]),
                    "tanggal": tanggal,
                    "tipe_gerakan": "saldo_awal",
                    **payload,
                })
            continue

        if not initialized:
            raise ValueError(
                "Ada mutasi persediaan sebelum saldo awal 1 Oktober 2026."
            )

        if e["kind"] == "movement":
            m = e["row"]
            mid = int(m["id"])
            qty = float(m["qty"])
            if qty <= 0:
                raise ValueError(
                    f"Mutasi persediaan ID {mid} mempunyai kuantitas tidak valid."
                )
            if m["tipe_gerakan"] == "masuk":
                amount = int(m["total_nilai"])
                unit = int(m["harga_satuan"])
                if amount < 0 or unit < 0:
                    raise ValueError(f"Nilai mutasi masuk ID {mid} tidak valid.")
                qty_balance += qty
                value_balance += amount
                avg = int(value_balance / qty_balance) if qty_balance else 0
                updates.append({
                    "id": mid,
                    "tanggal": m["tanggal"],
                    "tipe_gerakan": "masuk",
                    "qty": qty,
                    "harga_satuan": unit,
                    "total_nilai": amount,
                    "saldo_qty": qty_balance,
                    "saldo_nilai": value_balance,
                    "harga_rata2": avg,
                    "keterangan": m["keterangan"],
                })
                continue
            if m["tipe_gerakan"] != "keluar":
                raise ValueError(
                    f"Tipe mutasi {m['tipe_gerakan']} pada ID {mid} tidak dikenal."
                )
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
        bulan_transaksi = str(sale["tanggal"])[:7]
        if bulan_transaksi in hpp_by_month:
            hpp_by_month[bulan_transaksi] += int(hpp)

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
                "id": int(m["id"]),
                "tanggal": m["tanggal"],
                "tipe_gerakan": "keluar",
                **payload,
            })
        else:
            inserts.append({
                "item_id": item_id,
                "journal_entry_id": sale["id"],
                "tanggal": sale["tanggal"],
                "tipe_gerakan": "keluar",
                **payload,
            })

    if nov_opening_qty is None:
        raise ValueError("Saldo awal November tidak berhasil dihitung.")

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
                "entry_id": sale["id"],
                "no_bukti": sale["no_bukti"],
                "hpp": expected,
            })

    # Entri bertanggal Oktober harus berada di periode Oktober.
    move_rows = conn.execute(
        """
        SELECT je.id,je.no_bukti,je.tanggal,je.period_id,p.nama_bulan periode_lama
        FROM journal_entries je JOIN periods p ON p.id=je.period_id
        WHERE substr(je.tanggal,1,7)='2026-10' AND je.period_id!=?
        ORDER BY je.tanggal,je.id
        """,
        (pid_okt,),
    ).fetchall()

    # Entri bertanggal November harus berada di periode November.
    nov_move_rows = conn.execute(
        """
        SELECT je.id,je.no_bukti,je.tanggal,je.period_id,p.nama_bulan periode_lama
        FROM journal_entries je JOIN periods p ON p.id=je.period_id
        WHERE substr(je.tanggal,1,7)='2026-11' AND je.period_id!=?
        ORDER BY je.tanggal,je.id
        """,
        (pid_nov,),
    ).fetchall()

    # Jangan memindahkan transaksi Oktober keluar dari periode sumber yang masih
    # mempunyai saldo awal nonzero; saldo awal sumber perlu direkonsiliasi manual.
    source_ids = sorted({int(r["period_id"]) for r in move_rows})
    if source_ids:
        marks = ",".join("?" for _ in source_ids)
        opening_nonzero = conn.execute(
            f"""
            SELECT COUNT(*) jumlah FROM opening_balances
            WHERE period_id IN ({marks})
              AND (saldo_debit!=0 OR saldo_kredit!=0)
            """,
            source_ids,
        ).fetchone()["jumlah"]
        if int(opening_nonzero or 0):
            raise ValueError(
                "Ada saldo awal nonzero pada periode sumber transaksi Oktober. "
                "Rekonsiliasi periode perlu dilakukan manual."
            )

    # Penjualan selada lama tidak boleh ikut menjadi pendapatan penjualan cabai.
    legacy = conn.execute(
        """
        SELECT DISTINCT je.id,jl.id line_id,je.keterangan,je.tanggal,
               jl.debit,jl.kredit
        FROM journal_entries je
        JOIN journal_lines jl ON jl.journal_entry_id=je.id
        JOIN accounts a ON a.id=jl.account_id
        WHERE a.kode_akun='4101' AND jl.kredit>0
          AND lower(je.keterangan) LIKE '%penjualan selada%'
        ORDER BY je.id,jl.id
        """
    ).fetchall()
    legacy = [dict(r) for r in legacy]

    saldo_nov = hitung_saldo_awal_november(
        conn=conn,
        period_oktober_id=pid_okt,
        period_november_id=pid_nov,
        akun_inv_id=aid_inv,
        akun_hpp_id=aid_hpp,
        akun_penjualan_id=aid_sales,
        akun_lain_id=aid_lain,
        sales=sales,
        hpp_to_add=hpp_to_add,
        legacy=legacy,
        nilai_persediaan_awal_november=int(nov_opening_value),
    )

    return {
        "period_oktober_id": pid_okt,
        "period_november_id": pid_nov,
        "period_oktober_label": periode_okt["nama_bulan"],
        "period_november_label": periode_nov["nama_bulan"],
        "item_id": item_id,
        "akun_inv_id": aid_inv,
        "akun_hpp_id": aid_hpp,
        "akun_lain_id": aid_lain,
        "opening_balance_exists": ob is not None,
        "opening_movement_oktober_exists": snapshot_okt is not None,
        "opening_movement_november_exists": snapshots.get(TANGGAL_AWAL_NOVEMBER) is not None,
        "sales": sales,
        "sales_qty": sum(float(s["qty"]) for s in sales),
        "hpp_total": sum(int(s["hpp_expected"]) for s in sales),
        "hpp_october": hpp_by_month["2026-10"],
        "hpp_november": hpp_by_month["2026-11"],
        "hpp_to_add": hpp_to_add,
        "updates": updates,
        "inserts": inserts,
        "ending_qty": qty_balance,
        "ending_value": value_balance,
        "ending_avg": avg,
        "nov_opening_qty": nov_opening_qty,
        "nov_opening_value": nov_opening_value,
        "nov_opening_avg": nov_opening_avg,
        "nov_opening_rows": saldo_nov["rows"],
        "nov_opening_rows_to_insert": saldo_nov["rows_to_insert"],
        "nov_opening_total_debit": saldo_nov["total_debit"],
        "nov_opening_total_kredit": saldo_nov["total_kredit"],
        "laba_bersih_oktober": saldo_nov["laba_bersih_oktober"],
        "move_rows": [dict(r) for r in move_rows],
        "nov_move_rows": [dict(r) for r in nov_move_rows],
        "legacy": legacy,
    }


def rupiah(value: int) -> str:
    return "Rp" + f"{int(value):,}".replace(",", ".")


def print_plan(plan: dict) -> None:
    print("=" * 78)
    print("PRATINJAU MIGRASI HPP DATA CONTOH — DATABASE TIDAK DIUBAH")
    print("=" * 78)
    print(f"Database: {PATH_DATABASE}")
    print(
        f"Periode Oktober: {plan['period_oktober_label']} "
        f"(ID {plan['period_oktober_id']})"
    )
    print(
        f"Periode November: {plan['period_november_label']} "
        f"(ID {plan['period_november_id']})"
    )
    print()
    print("SALDO AWAL CONTOH PER 1 OKTOBER:")
    print(f"  HSL-001: {QTY_AWAL:,.1f} kg @ {rupiah(HARGA_AWAL)}/kg".replace(",", "."))
    print(f"  Nilai: {rupiah(NILAI_AWAL)}")
    print(
        "  Snapshot kartu: "
        + ("sudah ada" if plan["opening_movement_oktober_exists"] else "akan ditambahkan")
    )
    print(
        "  Saldo awal akun 1307: "
        + ("sudah ada" if plan["opening_balance_exists"] else "akan ditambahkan")
    )
    print()
    print("PENJUALAN CABAI DAN HPP:")
    print(f"  Transaksi: {len(plan['sales'])}")
    print(f"  Kuantitas: {plan['sales_qty']:,.4f} kg".replace(",", "."))
    print(f"  HPP Oktober: {rupiah(plan['hpp_october'])}")
    print(f"  HPP November: {rupiah(plan['hpp_november'])}")
    print(f"  Total HPP: {rupiah(plan['hpp_total'])}")
    print(f"  HPP sudah ada: {len(plan['sales']) - len(plan['hpp_to_add'])}")
    print(f"  Jurnal HPP yang akan ditambahkan: {len(plan['hpp_to_add'])}")
    for row in plan["hpp_to_add"]:
        print(f"    {row['no_bukti']}: {rupiah(row['hpp'])}")
    print()
    print("SALDO AKHIR OKTOBER / SALDO AWAL NOVEMBER:")
    print(f"  Kuantitas: {plan['nov_opening_qty']:,.4f} kg".replace(",", "."))
    print(f"  Nilai: {rupiah(plan['nov_opening_value'])}")
    print(f"  Rata-rata: {rupiah(plan['nov_opening_avg'])}/kg")
    print(
        "  Snapshot kartu 1 November: "
        + ("sudah ada" if plan["opening_movement_november_exists"] else "akan ditambahkan")
    )
    print(
        f"  Saldo awal akun November: {len(plan['nov_opening_rows'])} akun "
        f"(debit {rupiah(plan['nov_opening_total_debit'])} = "
        f"kredit {rupiah(plan['nov_opening_total_kredit'])})"
    )
    print(
        "  Laba/rugi Oktober yang dipindahkan ke Laba Ditahan (3201): "
        + rupiah(plan["laba_bersih_oktober"])
    )
    print()
    print("SALDO AKHIR KARTU PERSEDIAAN SETELAH TRANSAKSI NOVEMBER:")
    print(f"  Kuantitas: {plan['ending_qty']:,.4f} kg".replace(",", "."))
    print(f"  Nilai: {rupiah(plan['ending_value'])}")
    print(f"  Rata-rata: {rupiah(plan['ending_avg'])}/kg")
    print(f"  Mutasi diperbarui: {len(plan['updates'])}")
    print(f"  Mutasi ditambahkan: {len(plan['inserts'])}")
    print()
    print(
        f"ENTRI OKTOBER YANG DIPINDAHKAN KE {plan['period_oktober_label']}: "
        f"{len(plan['move_rows'])}"
    )
    for row in plan["move_rows"]:
        print(
            f"  ID {row['id']} | {row['no_bukti']} | {row['tanggal']} | "
            f"dari {row['periode_lama']}"
        )
    print()
    print(
        f"ENTRI NOVEMBER YANG DIPINDAHKAN KE {plan['period_november_label']}: "
        f"{len(plan['nov_move_rows'])}"
    )
    for row in plan["nov_move_rows"]:
        print(
            f"  ID {row['id']} | {row['no_bukti']} | {row['tanggal']} | "
            f"dari {row['periode_lama']}"
        )
    print()
    print(f"PENJUALAN SELADA YANG DIREKLASIFIKASI KE 4901: {len(plan['legacy'])}")
    for row in plan["legacy"]:
        print(f"  ID {row['id']} | {row['keterangan']}")
    print()
    print(
        "Catatan: saldo awal November membawa akun aset, liabilitas, dan ekuitas "
        "dari akhir Oktober. Pendapatan/beban Oktober ditutup ke Laba Ditahan "
        "agar Laba Rugi November hanya mencakup transaksi November."
    )
    print("Tidak ada perubahan yang dilakukan.")
    print("Untuk menerapkan setelah meninjau pratinjau:")
    print("  python scripts/migrasi_hpp_data_contoh.py --apply")
    print("=" * 78)


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
            (plan["period_oktober_id"], int(row["id"])),
        )

    for row in plan["nov_move_rows"]:
        conn.execute(
            "UPDATE journal_entries SET period_id=? WHERE id=?",
            (plan["period_november_id"], int(row["id"])),
        )

    if not plan["opening_balance_exists"]:
        conn.execute(
            """
            INSERT INTO opening_balances
                (period_id,account_id,saldo_debit,saldo_kredit,catatan)
            VALUES (?,?,?,0,?)
            """,
            (
                plan["period_oktober_id"],
                plan["akun_inv_id"],
                NILAI_AWAL,
                "CONTOH - 3.000 kg @ Rp25.000/kg; migrasi saldo awal perpetual",
            ),
        )

    # Saldo awal November semua akun permanen, dihitung dari saldo akhir Oktober.
    for row in plan["nov_opening_rows_to_insert"]:
        conn.execute(
            """
            INSERT INTO opening_balances
                (period_id,account_id,saldo_debit,saldo_kredit,catatan)
            VALUES (?,?,?,?,?)
            """,
            (
                plan["period_november_id"],
                row["account_id"],
                row["saldo_debit"],
                row["saldo_kredit"],
                row["catatan"],
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
                row["tanggal"],
                row["tipe_gerakan"],
                row["qty"],
                row["harga_satuan"],
                row["total_nilai"],
                row["saldo_qty"],
                row["saldo_nilai"],
                row["harga_rata2"],
                row["keterangan"],
                row["id"],
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
                row["item_id"],
                row["journal_entry_id"],
                row["tanggal"],
                row["tipe_gerakan"],
                row["qty"],
                row["harga_satuan"],
                row["total_nilai"],
                row["saldo_qty"],
                row["saldo_nilai"],
                row["harga_rata2"],
                row["keterangan"],
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
                row["entry_id"],
                plan["akun_hpp_id"],
                row["hpp"],
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
                row["entry_id"],
                plan["akun_inv_id"],
                row["hpp"],
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
        "--apply",
        action="store_true",
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
    print(
        "Saldo awal persediaan November: "
        f"{latest_plan['nov_opening_qty']:,.4f} kg"
    )
    print(
        "Nilai saldo awal persediaan November: "
        f"{rupiah(latest_plan['nov_opening_value'])}"
    )
    print("Jalankan diagnostik dan pytest untuk verifikasi.")


if __name__ == "__main__":
    main()
