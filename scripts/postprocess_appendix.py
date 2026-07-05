# -*- coding: utf-8 -*-
"""后处理 v2.0：keepNext清除 + 表格列宽 + 验证

v2.0 变化：
  - 三线表边框由 reference.docx "Table" 样式自动处理（Pandoc 3.x）
  - 表头底线 0.75pt 由 tblStylePr firstRow 自动处理
  - 表格列宽：优先用 Word MCP set_table_column_widths；本脚本作为 fallback
  - keepNext 清除保留（无 MCP 替代）
  - 验证增强
"""
from docx import Document
from docx.shared import Cm
from docx.oxml.ns import qn
from lxml import etree
import os, sys, zipfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DOCX = os.path.join(PROJECT_ROOT, 'output', 'paper.docx')

doc = Document(DOCX)
NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'

def W(tag): return f'{{{NS}}}{tag}'

# ===== 0. 表题样式修正：检测表前的加粗"表N"段落 → Table Caption =====
print(f'[0/4] Fixing table captions...')
table_caption_style = None
try:
    table_caption_style = doc.styles['Table Caption']
except KeyError:
    try:
        table_caption_style = doc.styles['Caption']
    except KeyError:
        pass

if table_caption_style:
    fixed = 0
    for i, table in enumerate(doc.tables):
        tbl_elem = table._tbl
        # Find paragraph immediately before this table in document order
        prev = tbl_elem.getprevious()
        if prev is not None and prev.tag == qn('w:p'):
            # Check if it contains bold text with 表
            p_text = ''.join(node.text or '' for node in prev.iter() if node.tag == qn('w:t'))
            has_bold = prev.find('.//' + qn('w:b')) is not None
            if has_bold and '表' in p_text:
                # Apply Table Caption style
                pPr = prev.find(qn('w:pPr'))
                if pPr is None:
                    pPr = etree.SubElement(prev, qn('w:pPr'))
                # Remove existing pStyle if any
                for ps in list(pPr):
                    if ps.tag == qn('w:pStyle'):
                        pPr.remove(ps)
                ps = etree.SubElement(pPr, qn('w:pStyle'))
                ps.set(qn('w:val'), 'Table Caption')
                fixed += 1
    print(f'  Fixed {fixed} table captions → Table Caption style')
else:
    print('  WARN: Table Caption style not found in document')

# ===== 1. 表格列宽（fallback：如 MCP 已处理则跳过） =====
print(f'[1/4] Processing {len(doc.tables)} tables (column widths)...')
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

    print(f'  Table {i+1}: {len(table.rows)}r x {ncols}c, widths OK')

# ===== 2. Remove keepNext/keepLines =====
print('[2/4] Cleaning paragraphs (keepNext/keepLines)...')
keepnext_count = 0
for p in doc.paragraphs:
    pPr = p._element.find(qn('w:pPr'))
    if pPr is not None:
        for tag in ['keepNext', 'keepLines']:
            for el in list(pPr):
                if el.tag == qn(f'w:{tag}'):
                    pPr.remove(el)
                    keepnext_count += 1
    # Fix unstyled paragraphs
    if p.style is None and p.text.strip():
        try:
            p.style = doc.styles['Compact']
        except KeyError:
            pass
print(f'  Removed {keepnext_count} keepNext/keepLines')

# ===== SAVE =====
doc.save(DOCX)

# ===== 3. VALIDATE (v2.0: enhanced checks) =====
print('[3/4] Validating...')
errors = []
warnings = []

doc2 = Document(DOCX)

# Check "Table" style is applied (v2.0: Pandoc auto-applies from reference.docx)
# Note: borders come from the "Table" STYLE (styles.xml), not direct formatting
for i, table in enumerate(doc2.tables):
    tbl = table._tbl
    tblPr = tbl.find(qn('w:tblPr'))
    if tblPr is not None:
        tblStyle = tblPr.find(qn('w:tblStyle'))
        if tblStyle is not None:
            style_val = tblStyle.get(qn('w:val'))
            if style_val != 'Table':
                warnings.append(f'Table {i+1}: uses style "{style_val}" instead of "Table"')
        else:
            warnings.append(f'Table {i+1}: no tblStyle ref (expected "Table")')
    else:
        warnings.append(f'Table {i+1}: no tblPr (malformed table)')

# Check footer exists (inherited from reference.docx)
with zipfile.ZipFile(DOCX, 'r') as z:
    has_footer = any('footer' in f.lower() for f in z.namelist())
    if not has_footer:
        errors.append('No footer found — PAGE field missing')
    # Check for keepNext
    doc_xml = z.read('word/document.xml').decode('utf-8')
    if '<w:keepNext' in doc_xml:
        errors.append('keepNext still present in document.xml')

# Check images
img_count = sum(1 for r in doc2.part.rels.values() if 'image' in r.reltype)
if img_count == 0:
    warnings.append('No images embedded (skeleton or empty paper?)')
elif img_count < 4:
    warnings.append(f'Only {img_count} images (expected 8+ for full paper)')

# Report warnings
if warnings:
    print(f'  WARNINGS ({len(warnings)}):')
    for w in warnings:
        print(f'    WARN: {w}')

if errors:
    print(f'  FAIL: {len(errors)} error(s):')
    for e in errors:
        print(f'    FAIL: {e}')
    sys.exit(1)
else:
    size_kb = os.path.getsize(DOCX) / 1024
    print(f'  PASS: {len(doc2.tables)} tables, {img_count} images, footer OK, {size_kb:.0f} KB')
    print(f'\n[DONE] paper.docx validated (v2.0 — "Table" style handles borders).')
