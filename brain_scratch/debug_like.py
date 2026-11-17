"""Debug inline LIKE pattern"""
import sqlite3
conn = sqlite3.connect(":memory:")
conn.executescript("""
    CREATE TABLE accounts (id INTEGER PRIMARY KEY, kode_akun TEXT UNIQUE);
    INSERT INTO accounts VALUES (1, '1110');
    INSERT INTO accounts VALUES (2, '1120');
    INSERT INTO accounts VALUES (3, '1140');
""")
cur = conn.execute("SELECT kode_akun FROM accounts WHERE kode_akun LIKE '12%'")
print("12% match:", [r[0] for r in cur.fetchall()])

cur2 = conn.execute("SELECT kode_akun FROM accounts WHERE kode_akun LIKE '11%'")
print("11% match:", [r[0] for r in cur2.fetchall()])
