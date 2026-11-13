import os
import re

views_dir = r"c:\Users\rieke\code-project\sistem-akuntansi-cabai\sistem-akuntansi-cabai\views"

for f in sorted(os.listdir(views_dir)):
    if not f.endswith(".py"):
        continue
    path = os.path.join(views_dir, f)
    with open(path, "r", encoding="utf-8") as fp:
        lines = fp.readlines()
    labels = {}
    for i, line in enumerate(lines, 1):
        m = re.search(r"st\.(selectbox|radio|multiselect|button|download_button)\s*\(\s*['\"]([^'\"]+)['\"]", line)
        if m:
            wtype, lbl = m.group(1), m.group(2)
            has_key = "key=" in line
            if lbl in labels and not has_key:
                print(f"Possible duplicate in {f}:{i} (previous: {labels[lbl]}): {wtype}('{lbl}') without key")
            labels[lbl] = f"{f}:{i}"

print("Scan completed.")
