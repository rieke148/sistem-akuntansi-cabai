"""
Cek imports di semua views dan bandingkan dengan fungsi yang ada di services.
"""
import ast
import os
import sys

base = r"c:\Users\rieke\code-project\sistem-akuntansi-cabai\sistem-akuntansi-cabai"

# Ambil semua fungsi yang ada di setiap service
service_functions = {}
for fname in os.listdir(os.path.join(base, "services")):
    if not fname.endswith(".py"):
        continue
    module = fname[:-3]
    fpath = os.path.join(base, "services", fname)
    with open(fpath, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())
    funcs = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and not n.name.startswith("_")]
    service_functions[module] = funcs

# Cek imports di setiap view
errors = []
view_dir = os.path.join(base, "views")
for fname in sorted(os.listdir(view_dir)):
    if not fname.endswith(".py"):
        continue
    fpath = os.path.join(view_dir, fname)
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()
    
    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        errors.append(f"SYNTAX ERROR {fname}: {e}")
        continue
    
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("services."):
            module = node.module.split(".")[-1]
            if module not in service_functions:
                errors.append(f"{fname}: import dari modul tidak dikenal: {node.module}")
                continue
            available = service_functions[module]
            for alias in node.names:
                name = alias.name
                if name not in available:
                    errors.append(f"{fname}: import '{name}' dari {module} TIDAK ADA (tersedia: {', '.join(available[:5])}...)")

print("=== CEK IMPORTS VIEW vs SERVICE ===")
if errors:
    for e in errors:
        print(f"  ❌ {e}")
else:
    print("  ✅ Semua imports valid!")

# Juga tampilkan semua fungsi yang tersedia
print("\n=== FUNGSI PER SERVICE ===")
for module, funcs in sorted(service_functions.items()):
    print(f"  {module}: {', '.join(funcs)}")
