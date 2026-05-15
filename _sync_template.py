"""Sync dashboard/index.html back into build_dashboard.py's INDEX_HTML r''' block."""
import re, os

BD = r'D:\SIPs\build_dashboard.py'
IDX = r'D:\SIPs\dashboard\index.html'

with open(BD, 'r', encoding='utf-8') as f:
    src = f.read()

with open(IDX, 'r', encoding='utf-8') as f:
    new_html = f.read()

# Find INDEX_HTML = r'''<!DOCTYPE html> ... </html>'''
pattern = re.compile(r"INDEX_HTML\s*=\s*r'''.*?'''", re.DOTALL)
match = pattern.search(src)
if not match:
    raise RuntimeError('Could not find INDEX_HTML r\'\'\'...\'\'\' block')

# Sanity: new_html must not contain triple-single-quote
if "'''" in new_html:
    raise RuntimeError("new index.html contains ''' which conflicts with r''' embedding")

replacement = f"INDEX_HTML = r'''{new_html}'''"
new_src = src[:match.start()] + replacement + src[match.end():]

with open(BD, 'w', encoding='utf-8') as f:
    f.write(new_src)

print(f'[OK] synced {len(new_html)} bytes of HTML into INDEX_HTML block')
print(f'[OK] build_dashboard.py now {len(new_src)} bytes total')
