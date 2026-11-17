"""AppTest semua views — cek error 0"""
import sys, os
sys.path.insert(0, '.')
os.environ.setdefault('STREAMLIT_TESTING', '1')

from streamlit.testing.v1 import AppTest

views_dir = 'views'
files = sorted(f for f in os.listdir(views_dir) if f.endswith('.py') and not f.startswith('__'))

results = []
for fname in files:
    path = f'{views_dir}/{fname}'
    try:
        at = AppTest.from_file(path, default_timeout=30)
        at.run()
        status = 'OK' if not at.exception else f'ERROR: {at.exception}'
    except Exception as e:
        status = f'FAIL: {type(e).__name__}: {e}'
    results.append((fname, status))
    print(f'{fname}: {status}')

errors = [(f, s) for f, s in results if not s.startswith('OK')]
print(f'\n=== Total: {len(results)} views, {len(errors)} errors ===')
for f, s in errors:
    print(f'  FAIL: {f} -> {s}')
