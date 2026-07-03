# -*- coding: utf-8 -*-
"""后处理: 三线表边框 + keepNext清除 + 列宽修复 + 验证"""
from docx import Document
from docx.shared import Cm
from docx.oxml.ns import qn
from lxml import etree
import os, sys

# Resolve path relative to this script → project root → output/
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DOCX = os.path.join(PROJECT_ROOT, 'output', 'paper.docx')

doc = Document(DOCX)
NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'

def W(tag): return f'{{{NS}}}{tag}'

# ===== 1. 三线表边框 + 列宽 =====
print(f'[1/3] Processing {len(doc.tables)} tables...')
for i, table in enumerate(doc.tables):
    table.autofit = False
    tbl = table._tbl
    tblPr = tbl.find(qn('w:tblPr'))
    if tblPr is None:
        tblPr = etree.SubElement(tbl, qn('w:tblPr'))

    # Width 100% + fixed layout
    for tag in ['tblW', 'tblLayout']:
        for el in list(tblPr):
            if el.tag == qn(f'w:{tag}'):
                tblPr.remove(el)
    tw = etree.SubElement(tblPr, qn('w:tblW'))
    tw.set(qn('w:w'), '5000')
    tw.set(qn('w:type'), 'pct')
    etree.SubElement(tblPr, qn('w:tblLayout')).set(qn('w:type'), 'fixed')

    # Three-line: top 1.5pt + bottom 1.5pt, no verticals
    for el in list(tblPr):
        if el.tag == qn('w:tblBorders'):
            tblPr.remove(el)
    borders = etree.SubElement(tblPr, qn('w:tblBorders'))
    for side, sz in [('top', '12'), ('bottom', '12')]:
        el = etree.SubElement(borders, qn(f'w:{side}'))
        for a, v in [('w:val', 'single'), ('w:sz', sz),
                      ('w:space', '0'), ('w:color', '000000')]:
            el.set(qn(a), v)
    for side in ['left', 'right', 'insideH', 'insideV']:
        el = etree.SubElement(borders, qn(f'w:{side}'))
        for a, v in [('w:val', 'none'), ('w:sz', '0'),
                      ('w:space', '0'), ('w:color', 'auto')]:
            el.set(qn(a), v)

    # Clear cell-level borders
    for tc in tbl.findall(f'.//{{{NS}}}tc'):
        tcp = tc.find(qn('w:tcPr'))
        if tcp is not None:
            for tcb in list(tcp):
                if tcb.tag == qn('w:tcBorders'):
                    tcp.remove(tcb)

    # Header row: 0.75pt bottom
    rows = tbl.findall(qn('w:tr'))
    if rows:
        for tc in rows[0].findall(qn('w:tc')):
            tcp = tc.find(qn('w:tcPr'))
            if tcp is None:
                tcp = etree.SubElement(tc, qn('w:tcPr'))
            for el in list(tcp):
                if el.tag == qn('w:tcBorders'):
                    tcp.remove(el)
            tcb = etree.SubElement(tcp, qn('w:tcBorders'))
            b = etree.SubElement(tcb, qn('w:bottom'))
            for a, v in [('w:val', 'single'), ('w:sz', '6'),
                          ('w:space', '0'), ('w:color', '000000')]:
                b.set(qn(a), v)

    # Column widths
    ncols = len(table.columns)
    if i == 0 and ncols == 3:
        widths = [Cm(3.0), Cm(9.6), Cm(3.0)]
    else:
        w = Cm(15.6 / ncols)
        widths = [w] * ncols
    for row in table.rows:
        for ci, cell in enumerate(row.cells):
            if ci < len(widths):
                cell.width = widths[ci]

    print(f'  Table {i+1}: {len(rows)}r x {ncols}c OK')

# ===== 2. Remove keepNext/keepLines, fix un-styled =====
print('[2/3] Cleaning paragraphs...')
keepnext_count = 0
for p in doc.paragraphs:
    pPr = p._element.find(qn('w:pPr'))
    if pPr is not None:
        for tag in ['keepNext', 'keepLines']:
            for el in list(pPr):
                if el.tag == qn(f'w:{tag}'):
                    pPr.remove(el)
                    keepnext_count += 1
    if p.style is None and p.text.strip():
        try:
            p.style = doc.styles['Compact']
        except:
            pass
print(f'  Removed {keepnext_count} keepNext/keepLines')

# ===== SAVE =====
doc.save(DOCX)

# ===== 3. VALIDATE =====
print('[3/3] Validating...')
errors = []

# Re-open for clean validation
doc2 = Document(DOCX)

# Check tables have borders
for i, table in enumerate(doc2.tables):
    tbl = table._tbl
    tblPr = tbl.find(qn('w:tblPr'))
    if tblPr is not None:
        borders = tblPr.find(qn('w:tblBorders'))
        if borders is None:
            errors.append(f'Table {i+1}: no borders')
        else:
            top = borders.find(qn('w:top'))
            if top is None or top.get(qn('w:sz')) != '12':
                errors.append(f'Table {i+1}: top border missing/wrong')

# Check footer exists (inherited from reference.docx)
import zipfile
with zipfile.ZipFile(DOCX, 'r') as z:
    has_footer = any('footer' in f.lower() for f in z.namelist())
    if not has_footer:
        errors.append('No footer found — PAGE field missing')
    # Check for keepNext
    doc_xml = z.read('word/document.xml').decode('utf-8')
    if '<w:keepNext' in doc_xml:
        errors.append('keepNext still present in document.xml')

# Check images (warn but don't fail — skeleton may have 0)
img_count = sum(1 for r in doc2.part.rels.values() if 'image' in r.reltype)
if img_count == 0:
    print(f'  WARN: No images embedded (skeleton or empty paper?)')
elif img_count < 4:
    print(f'  WARN: Only {img_count} images (expected 8+ for full paper)')

if errors:
    print(f'  FAIL: {len(errors)} error(s):')
    for e in errors:
        print(f'    ✗ {e}')
    sys.exit(1)
else:
    size_kb = os.path.getsize(DOCX) / 1024
    print(f'  PASS: {len(doc2.tables)} tables, {img_count} images, footer OK, {size_kb:.0f} KB')
    print(f'\n[DONE] paper.docx validated.')
