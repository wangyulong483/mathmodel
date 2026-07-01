# -*- coding: utf-8 -*-
"""
Fix: 重写 reference.docx 中的 Table 样式为真正的三线表
EXA MCP 最优方案：直接编辑 styles.xml，Pandoc 3.x 不再硬编码边框
三线表 = 顶线粗(1.5pt) + 表头下线细(0.75pt) + 底线粗(1.5pt)，无任何竖线
"""
import zipfile
import xml.etree.ElementTree as ET
import io

REF_DOCX = 'reference.docx'
NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
MC = 'http://schemas.openxmlformats.org/markup-compatibility/2006'

ET.register_namespace('w', NS)
ET.register_namespace('mc', MC)
ET.register_namespace('r', 'http://schemas.openxmlformats.org/officeDocument/2006/relationships')

def W(tag):
    return f'{{{NS}}}{tag}'

print("Reading reference.docx...")
with zipfile.ZipFile(REF_DOCX, 'r') as zin:
    all_files = {name: zin.read(name) for name in zin.namelist()}

root = ET.fromstring(all_files['word/styles.xml'])

# ---- Step 1: Remove ALL existing table styles ----
to_remove = []
for style in root.findall(W('style')):
    stype = style.get(W('type'))
    if stype == 'table':
        sid = style.get(W('styleId'))
        name_el = style.find(W('name'))
        name = name_el.get(W('val')) if name_el is not None else '?'
        to_remove.append(style)
        print(f'  [REMOVE] table style: {sid} ({name})')

for style in to_remove:
    root.remove(style)

# ---- Step 2: Build clean three-line Table style ----
# In OOXML, table styles define borders in <w:tblPr><w:tblBorders>
# and conditional formats in <w:tblStylePr w:type="firstRow|lastRow|...">
#
# For 三线表:
#   - Whole table borders: top thick, bottom thick, NO left, NO right, NO insideH, NO insideV
#   - firstRow: bottom border thin (middle line)
#   - NO banding

table_style = ET.Element(W('style'))
table_style.set(W('type'), 'table')
table_style.set(W('styleId'), 'Table')

ET.SubElement(table_style, W('name')).set(W('val'), 'Table')
ET.SubElement(table_style, W('uiPriority')).set(W('val'), '59')
ET.SubElement(table_style, W('qFormat'))
# Do NOT base on anything — standalone style

# ==== tblPr: whole-table borders ====
tblPr = ET.SubElement(table_style, W('tblPr'))

# Table width: auto
tblW = ET.SubElement(tblPr, W('tblW'))
tblW.set(W('w'), '5000')
tblW.set(W('type'), 'pct')

# Cell margins (normal spacing)
tblCellMar = ET.SubElement(tblPr, W('tblCellMar'))
for side, val in [('top', '50'), ('left', '108'), ('bottom', '50'), ('right', '108')]:
    el = ET.SubElement(tblCellMar, W(side))
    el.set(W('w'), val)
    el.set(W('type'), 'dxa')

# Borders for whole table
tblBorders = ET.SubElement(tblPr, W('tblBorders'))

# Top: THICK (反线 1.5pt = sz 12)
ET.SubElement(tblBorders, W('top')).set(W('val'), 'single')
tblBorders.find(W('top')).set(W('sz'), '12')
tblBorders.find(W('top')).set(W('space'), '0')
tblBorders.find(W('top')).set(W('color'), '000000')

# Bottom: THICK (反线 1.5pt = sz 12)
ET.SubElement(tblBorders, W('bottom')).set(W('val'), 'single')
tblBorders.find(W('bottom')).set(W('sz'), '12')
tblBorders.find(W('bottom')).set(W('space'), '0')
tblBorders.find(W('bottom')).set(W('color'), '000000')

# Left: NONE
ET.SubElement(tblBorders, W('left')).set(W('val'), 'none')
tblBorders.find(W('left')).set(W('sz'), '0')
tblBorders.find(W('left')).set(W('space'), '0')
tblBorders.find(W('left')).set(W('color'), 'auto')

# Right: NONE
ET.SubElement(tblBorders, W('right')).set(W('val'), 'none')
tblBorders.find(W('right')).set(W('sz'), '0')
tblBorders.find(W('right')).set(W('space'), '0')
tblBorders.find(W('right')).set(W('color'), 'auto')

# InsideH (horizontal between rows): NONE
ET.SubElement(tblBorders, W('insideH')).set(W('val'), 'none')
tblBorders.find(W('insideH')).set(W('sz'), '0')
tblBorders.find(W('insideH')).set(W('space'), '0')
tblBorders.find(W('insideH')).set(W('color'), 'auto')

# InsideV (vertical between cols): NONE
ET.SubElement(tblBorders, W('insideV')).set(W('val'), 'none')
tblBorders.find(W('insideV')).set(W('sz'), '0')
tblBorders.find(W('insideV')).set(W('space'), '0')
tblBorders.find(W('insideV')).set(W('color'), 'auto')

# tblLook: what conditional formats to apply
tblLook = ET.SubElement(tblPr, W('tblLook'))
tblLook.set(W('firstRow'), '1')
tblLook.set(W('lastRow'), '0')
tblLook.set(W('firstColumn'), '0')
tblLook.set(W('lastColumn'), '0')
tblLook.set(W('noHBand'), '1')
tblLook.set(W('noVBand'), '1')
tblLook.set(W('val'), '0020')

# ==== tblStylePr: firstRow (表头行) ====
# This is the MIDDLE LINE of 三线表 (thin)
firstRow = ET.Element(W('tblStylePr'))
firstRow.set(W('type'), 'firstRow')

# Bold text for header
rPr_first = ET.SubElement(firstRow, W('rPr'))
ET.SubElement(rPr_first, W('b'))
bCs = ET.SubElement(rPr_first, W('bCs'))
bCs.set(W('val'), 'true')

# Font size for header
sz_first = ET.SubElement(rPr_first, W('sz'))
sz_first.set(W('val'), '21')  # 10.5pt for table header
szCs_first = ET.SubElement(rPr_first, W('szCs'))
szCs_first.set(W('val'), '21')

# Header cell bottom border: THIN (正线 0.75pt = sz 6)
tcPr_first = ET.SubElement(firstRow, W('tcPr'))
tcBorders_first = ET.SubElement(tcPr_first, W('tcBorders'))
bottom_first = ET.SubElement(tcBorders_first, W('bottom'))
bottom_first.set(W('val'), 'single')
bottom_first.set(W('sz'), '6')      # 0.75pt
bottom_first.set(W('space'), '0')
bottom_first.set(W('color'), '000000')

table_style.append(firstRow)

# ==== tblStylePr: lastRow ====
# Ensure last row bottom is the thick border (matches table bottom)
# Actually the table bottom border already covers this,
# but we add it for safety
lastRow = ET.Element(W('tblStylePr'))
lastRow.set(W('type'), 'lastRow')
tcPr_last = ET.SubElement(lastRow, W('tcPr'))
tcBorders_last = ET.SubElement(tcPr_last, W('tcBorders'))
bottom_last = ET.SubElement(tcBorders_last, W('bottom'))
bottom_last.set(W('val'), 'single')
bottom_last.set(W('sz'), '12')
bottom_last.set(W('space'), '0')
bottom_last.set(W('color'), '000000')

table_style.append(lastRow)

# Insert Table style at beginning of styles
root.insert(0, table_style)
print('  [ADD] Three-line table style \"Table\":')
print('         top=1.5pt thick | header-bottom=0.75pt thin | bottom=1.5pt thick')
print('         NO vertical lines | NO internal horizontal lines')

# Write back
all_files['word/styles.xml'] = ET.tostring(root, encoding='utf-8', xml_declaration=True)

with zipfile.ZipFile(REF_DOCX, 'w', zipfile.ZIP_DEFLATED) as zout:
    for name, data in all_files.items():
        zout.writestr(name, data)

print('\n[DONE] reference.docx updated with true three-line table style')
