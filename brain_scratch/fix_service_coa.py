"""Script untuk update pola COA di special_journal_service.py"""
import re

with open('services/special_journal_service.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Hitung sebelum
cnt_13 = content.count("LIKE '13%'")
cnt_110 = content.count("LIKE '110%'")
print(f"Sebelum: LIKE '13%' = {cnt_13}, LIKE '110%' = {cnt_110}")

# Update persediaan: LIKE '13%' -> = '1140'
content_new = content.replace("LIKE '13%'", "= '1140'")

# Update kas: LIKE '110%' -> = '1110'
content_new = content_new.replace("LIKE '110%'", "= '1110'")

with open('services/special_journal_service.py', 'w', encoding='utf-8') as f:
    f.write(content_new)

print("Done!")
print(f"  Persediaan (13% -> 1140): {cnt_13} perubahan")
print(f"  Kas (110% -> 1110): {cnt_110} perubahan")
