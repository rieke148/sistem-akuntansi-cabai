"""
Script untuk syntax check semua views dan services sekaligus.
"""
import ast
import os
import sys

base = r"c:\Users\rieke\code-project\sistem-akuntansi-cabai\sistem-akuntansi-cabai"
dirs_to_check = ["views", "services", "utils"]

errors = []
ok_count = 0

for d in dirs_to_check:
    folder = os.path.join(base, d)
    if not os.path.exists(folder):
        continue
    for fname in sorted(os.listdir(folder)):
        if not fname.endswith(".py"):
            continue
        fpath = os.path.join(folder, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                src = f.read()
            ast.parse(src)
            ok_count += 1
        except SyntaxError as e:
            errors.append(f"SYNTAX ERROR {d}/{fname}:{e.lineno} - {e.msg}")
        except Exception as e:
            errors.append(f"ERROR {d}/{fname} - {e}")

print(f"=== Syntax Check: {ok_count} OK, {len(errors)} ERRORS ===")
for e in errors:
    print(e)
if not errors:
    print("Semua file OK!")
