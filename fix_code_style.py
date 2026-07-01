# -*- coding: utf-8 -*-
"""
EXA MCP 最优方案：修复 reference.docx 中的代码块样式
- Verbatim Char: 字符样式，Consolas 9pt（小五号）
- Source Code: 段落样式，基于 Normal 但单倍行距、无缩进、link Verbatim Char
- 该方案不添加 *Tok 样式，让 pandoc 根据 --highlight-style 动态生成语法高亮颜色
"""
import zipfile
import xml.etree.ElementTree as ET

REF_DOCX = 'reference.docx'
NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'

ET.register_namespace('w', NS)

def W(tag):
    return f'{{{NS}}}{tag}'

print("Reading reference.docx...")
with zipfile.ZipFile(REF_DOCX, 'r') as zin:
    all_files = {name: zin.read(name) for name in zin.namelist()}

root = ET.fromstring(all_files['word/styles.xml'])

# ---- Step 1: Fix/Add Verbatim Char ----
# Remove existing Verbatim Char if present
for style in list(root.findall(W('style'))):
    style_id = style.get(W('styleId'))
    if style_id == 'VerbatimChar':
        root.remove(style)
        print('[REMOVE] Old VerbatimChar')

# Create proper Verbatim Char (character style)
vc = ET.Element(W('style'))
vc.set(W('type'), 'character')
vc.set(W('styleId'), 'VerbatimChar')
ET.SubElement(vc, W('name')).set(W('val'), 'Verbatim Char')
ET.SubElement(vc, W('basedOn')).set(W('val'), 'DefaultParagraphFont')
rPr_vc = ET.SubElement(vc, W('rPr'))
# Font: Consolas 9pt
rFonts_vc = ET.SubElement(rPr_vc, W('rFonts'))
rFonts_vc.set(W('ascii'), 'Consolas')
rFonts_vc.set(W('hAnsi'), 'Consolas')
rFonts_vc.set(W('eastAsia'), '宋体')
rFonts_vc.set(W('cs'), 'Consolas')
# Size: 9pt = 18 half-pts
sz_vc = ET.SubElement(rPr_vc, W('sz'))
sz_vc.set(W('val'), '18')
szCs_vc = ET.SubElement(rPr_vc, W('szCs'))
szCs_vc.set(W('val'), '18')

root.insert(0, vc)
print('[ADD] Verbatim Char: Consolas 9pt (小五号)')

# ---- Step 2: Add Source Code paragraph style ----
# Remove existing Source Code if present
for style in list(root.findall(W('style'))):
    name_el = style.find(W('name'))
    if name_el is not None and name_el.get(W('val')) == 'Source Code':
        root.remove(style)
        print('[REMOVE] Old Source Code')

sc = ET.Element(W('style'))
sc.set(W('type'), 'paragraph')
sc.set(W('styleId'), 'SourceCode')
ET.SubElement(sc, W('name')).set(W('val'), 'Source Code')
ET.SubElement(sc, W('basedOn')).set(W('val'), 'Normal')
ET.SubElement(sc, W('link')).set(W('val'), 'VerbatimChar')
ET.SubElement(sc, W('uiPriority')).set(W('val'), '29')
ET.SubElement(sc, W('qFormat'))

# Run properties: Consolas 9pt
rPr_sc = ET.SubElement(sc, W('rPr'))
rFonts_sc = ET.SubElement(rPr_sc, W('rFonts'))
rFonts_sc.set(W('ascii'), 'Consolas')
rFonts_sc.set(W('hAnsi'), 'Consolas')
rFonts_sc.set(W('eastAsia'), '宋体')
rFonts_sc.set(W('cs'), 'Consolas')
sz_sc = ET.SubElement(rPr_sc, W('sz'))
sz_sc.set(W('val'), '18')
szCs_sc = ET.SubElement(rPr_sc, W('szCs'))
szCs_sc.set(W('val'), '18')

# Paragraph properties: single spacing, no indent, keep with next
pPr_sc = ET.SubElement(sc, W('pPr'))
# Single line spacing
spacing_sc = ET.SubElement(pPr_sc, W('spacing'))
spacing_sc.set(W('line'), '240')     # 1.0x
spacing_sc.set(W('lineRule'), 'auto')
spacing_sc.set(W('before'), '0')
spacing_sc.set(W('after'), '0')
# No first-line indent
ind_sc = ET.SubElement(pPr_sc, W('ind'))
ind_sc.set(W('firstLine'), '0')
ind_sc.set(W('left'), '0')
ind_sc.set(W('right'), '0')
# No word wrap (let code extend)
ET.SubElement(pPr_sc, W('wordWrap')).set(W('val'), 'off')

root.insert(0, sc)
print('[ADD] Source Code: Consolas 9pt, 1.0x line, no indent, link→VerbatimChar')

# ---- Step 3: Remove any *Tok styles that would lock highlighting colors ----
removed_toks = []
for style in list(root.findall(W('style'))):
    style_id = style.get(W('styleId'), '')
    if style_id.endswith('Tok'):
        root.remove(style)
        removed_toks.append(style_id)

if removed_toks:
    print(f'[REMOVE] {len(removed_toks)} *Tok styles (will be dynamically generated): {removed_toks[:5]}...')
else:
    print('[OK] No *Tok styles present (pandoc will generate dynamically)')

# Write back
all_files['word/styles.xml'] = ET.tostring(root, encoding='utf-8', xml_declaration=True)

with zipfile.ZipFile(REF_DOCX, 'w', zipfile.ZIP_DEFLATED) as zout:
    for name, data in all_files.items():
        zout.writestr(name, data)

print('\n[DONE] reference.docx updated for code blocks')
print('  - Verbatim Char: Consolas 9pt (inline code)')
print('  - Source Code: Consolas 9pt, single spacing, no indent (code blocks)')
print('  - *Tok styles removed → pandoc --highlight-style controls syntax colors')
