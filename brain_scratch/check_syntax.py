"""Script untuk cek syntax semua file Python di project."""
import ast, pathlib, sys

base = pathlib.Path(r"c:\Users\rieke\code-project\sistem-akuntansi-cabai\sistem-akuntansi-cabai")
dirs = ["views", "services", "utils", "database"]
errors = []

for d in dirs:
    for f in (base / d).glob("*.py"):
        try:
            ast.parse(f.read_text("utf-8"))
        except SyntaxError as e:
            errors.append(f"❌ {f.relative_to(base)}: {e}")

if errors:
    for e in errors:
        print(e)
    sys.exit(1)
else:
    print(f"✅ Semua file OK ({sum(1 for d in dirs for f in (base/d).glob('*.py'))} file)")
