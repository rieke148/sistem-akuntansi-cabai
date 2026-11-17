"""Update closing_service.py account codes to new COA"""

with open('services/closing_service.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Update konstanta kode akun
content = content.replace(
    'KODE_IKHTISAR_LR = "3301"   # Ikhtisar Laba Rugi',
    'KODE_IKHTISAR_LR = "3130"   # Ikhtisar Laba Rugi'
)
content = content.replace(
    'KODE_LABA_DITAHAN = "3201"  # Laba Ditahan',
    'KODE_LABA_DITAHAN = "3120"  # Laba (Laba Ditahan)'
)
# update error message
content = content.replace(
    'Pastikan akun Ikhtisar Laba Rugi (3301) dan Laba Ditahan (3201) sudah ada.',
    'Pastikan akun Ikhtisar Laba Rugi (3130) dan Laba (3120) sudah ada.'
)
# update docstring references
content = content.replace('(3301)', '(3130)')
content = content.replace('(3201)', '(3120)')
content = content.replace('3301', '3130')
content = content.replace('3201', '3120')

with open('services/closing_service.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Done')
print('3301 remaining:', content.count('3301'))
print('3201 remaining:', content.count('3201'))
print('3130 count:', content.count('3130'))
print('3120 count:', content.count('3120'))
