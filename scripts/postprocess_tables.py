# -*- coding: utf-8 -*-
"""
后处理 paper.docx: 在表格实例上直接写入三线表边框
绕过 Word 样式继承/条件格式的不确定性
"""
import zipfile
import xml.etree.ElementTree as ET
import shutil
import os

DOCX = 'paper.docx'
NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'

ET.register_namespace('w', NS)

def W(tag):
    return f'{{{NS}}}{tag}'

print(f"Processing {DOCX}...")

with zipfile.ZipFile(DOCX, 'r') as zin:
    all_files = {name: zin.read(name) for name in zin.namelist()}

root = ET.fromstring(all_files['word/document.xml'])

table_count = 0
for tbl in root.findall('.//' + W('tbl')):
    table_count += 1
    tblPr = tbl.find(W('tblPr'))
    if tblPr is None:
        tblPr = ET.Element(W('tblPr'))
        tbl.insert(0, tblPr)

    # ---- 1. Remove all hardcoded cell borders (just in case) ----
    for tc in tbl.findall('.//' + W('tc')):
        tcPr = tc.find(W('tcPr'))
        if tcPr is not None:
            tcBorders = tcPr.find(W('tcBorders'))
            if tcBorders is not None:
                tcPr.remove(tcBorders)

    # ---- 2. Set table width to 100% (full text width) ----
    tblW = tblPr.find(W('tblW'))
    if tblW is None:
        tblW = ET.SubElement(tblPr, W('tblW'))
    tblW.set(W('w'), '5000')
    tblW.set(W('type'), 'pct')

    # ---- 3. Set table-level borders (top thick, bottom thick) ----
    # Remove existing tblBorders
    existing_borders = tblPr.find(W('tblBorders'))
    if existing_borders is not None:
        tblPr.remove(existing_borders)

    borders = ET.SubElement(tblPr, W('tblBorders'))

    # Top: THICK 1.5pt
    top = ET.SubElement(borders, W('top'))
    top.set(W('val'), 'single')
    top.set(W('sz'), '12')
    top.set(W('space'), '0')
    top.set(W('color'), '000000')

    # Bottom: THICK 1.5pt
    bottom = ET.SubElement(borders, W('bottom'))
    bottom.set(W('val'), 'single')
    bottom.set(W('sz'), '12')
    bottom.set(W('space'), '0')
    bottom.set(W('color'), '000000')

    # Left/Right/InsideH/InsideV: NONE
    for side in ['left', 'right', 'insideH', 'insideV']:
        el = ET.SubElement(borders, W(side))
        el.set(W('val'), 'none')
        el.set(W('sz'), '0')
        el.set(W('space'), '0')
        el.set(W('color'), 'auto')

    # ---- 3. Header row: thin bottom border on each cell ----
    rows = tbl.findall(W('tr'))
    if rows:
        first_row = rows[0]
        for tc in first_row.findall(W('tc')):
            tcPr = tc.find(W('tcPr'))
            if tcPr is None:
                tcPr = ET.SubElement(tc, W('tcPr'))
                tc.insert(0, tcPr)

            # Remove existing tcBorders
            existing_tcBorders = tcPr.find(W('tcBorders'))
            if existing_tcBorders is not None:
                tcPr.remove(existing_tcBorders)

            tcBorders = ET.SubElement(tcPr, W('tcBorders'))
            hdr_bottom = ET.SubElement(tcBorders, W('bottom'))
            hdr_bottom.set(W('val'), 'single')
            hdr_bottom.set(W('sz'), '6')      # THIN 0.75pt
            hdr_bottom.set(W('space'), '0')
            hdr_bottom.set(W('color'), '000000')

    print(f'  Table {table_count}: 3-line borders written (top=1.5pt, header-bottom=0.75pt, bottom=1.5pt)')

print(f'\nTotal tables processed: {table_count}')

# Write back
all_files['word/document.xml'] = ET.tostring(root, encoding='utf-8', xml_declaration=True)

with zipfile.ZipFile(DOCX, 'w', zipfile.ZIP_DEFLATED) as zout:
    for name, data in all_files.items():
        zout.writestr(name, data)

print(f'[DONE] {DOCX} updated — tables are now TRUE three-line style')
