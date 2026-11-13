"""
Audit semua referensi kolom yang tidak ada di DB.
Kolom yang BENAR berdasarkan PRAGMA table_info:
  items      : id, kode_item, nama_item, satuan, tipe, komoditas, account_id, aktif
  receivables: id, journal_entry_id, customer_id, no_faktur, tanggal_faktur,
               tanggal_jatuh_tempo, jumlah, jumlah_terbayar, status
  parameters : id, kunci, nilai, satuan, catatan
  customers  : id, nama, tipe, telepon, alamat, aktif
  suppliers  : id, nama, telepon, alamat, aktif
  employees  : id, nama, tipe_pekerja, upah_harian, komoditas, aktif
  periods    : id, tahun, bulan, nama_bulan, status
"""

import os, re, sys

# Pola yang SALAH → BENAR
FIXES = {
    # items
    r'\bitems\b.*?\bORDER BY nama\b': 'ORDER BY nama_item',
    # receivables - sudah fix
    # parameters - kunci bukan nama/key
}

# Kolom yang tidak ada di tabel masing-masing
WRONG_COLS = {
    'items': ['nama,', 'nama ', 'nama\n', '"nama"', "'nama'", 'ORDER BY nama'],
    'receivables': ['jatuh_tempo', 'jumlah_piutang'],
    'parameters': ['nama', 'key'],
}

# Scan semua .py di views/ dan services/
py_files = []
for folder in ['views', 'services', 'tests']:
    for fn in os.listdir(folder):
        if fn.endswith('.py'):
            py_files.append(f'{folder}/{fn}')

print("=== SCAN HASIL ===")
for f in sorted(py_files):
    try:
        lines = open(f, encoding='utf-8').readlines()
    except:
        continue
    for i, line in enumerate(lines, 1):
        # Cek kolom items yang salah
        if 'FROM items' in line or ('items' in line and ('nama,' in line or 'ORDER BY nama' in line)):
            if 'nama_item' not in line and ('nama,' in line or 'ORDER BY nama' in line or '" nama"' in line):
                print(f"  [items.nama] {f}:{i}: {line.rstrip()}")
        # Cek receivables yang salah
        if 'receivables' in line or 'FROM receivables' in line:
            if 'jatuh_tempo' in line and 'tanggal_jatuh_tempo' not in line:
                print(f"  [recv.jatuh_tempo] {f}:{i}: {line.rstrip()}")
            if 'jumlah_piutang' in line:
                print(f"  [recv.jumlah_piutang] {f}:{i}: {line.rstrip()}")
        # Cek parameters yang salah (kolom adalah 'kunci', bukan 'nama' atau 'key')
        if 'FROM parameters' in line or 'parameters' in line.lower():
            if re.search(r'parameters.*["\']nama["\']|WHERE nama\s*=', line):
                print(f"  [param.nama] {f}:{i}: {line.rstrip()}")
