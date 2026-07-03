# -*- coding: utf-8 -*-
"""
国赛格式优化：样式字体/字号/行距/缩进/标题黑色
参考：全国大学生数学建模竞赛论文格式规范 + 通用惯例
"""
import zipfile, xml.etree.ElementTree as ET

REF_DOCX = '../templates/reference.docx'
NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'

ET.register_namespace('w', NS)
ET.register_namespace('r', 'http://schemas.openxmlformats.org/officeDocument/2006/relationships')
ET.register_namespace('mc', 'http://schemas.openxmlformats.org/markup-compatibility/2006')
ET.register_namespace('w14', 'http://schemas.microsoft.com/office/word/2010/wordml')

def W(tag): return f'{{{NS}}}{tag}'

def get_or_create(el, tag):
    c = el.find(W(tag))
    if c is None: c = ET.SubElement(el, W(tag))
    return c

def remove_all(el, tag):
    for c in el.findall(W(tag)): el.remove(c)

def fix_fonts(style_elem, ascii_font, ea_font):
    rPr = get_or_create(style_elem, 'rPr')
    rFonts = get_or_create(rPr, 'rFonts')
    for a in ['ascii','hAnsi','eastAsia','cs']: rFonts.set(W(a), '')
    rFonts.set(W('ascii'), ascii_font); rFonts.set(W('hAnsi'), ascii_font)
    rFonts.set(W('eastAsia'), ea_font); rFonts.set(W('cs'), ascii_font)

def fix_font_size(style_elem, pt_size):
    rPr = get_or_create(style_elem, 'rPr')
    remove_all(rPr, 'sz'); remove_all(rPr, 'szCs')
    ET.SubElement(rPr, W('sz')).set(W('val'), str(int(pt_size*2)))
    ET.SubElement(rPr, W('szCs')).set(W('val'), str(int(pt_size*2)))

def fix_bold(style_elem, bold_on):
    rPr = get_or_create(style_elem, 'rPr')
    remove_all(rPr, 'b'); remove_all(rPr, 'bCs')
    if bold_on:
        ET.SubElement(rPr, W('b'))
        bc = ET.SubElement(rPr, W('bCs')); bc.set(W('val'), 'true')

def fix_color(style_elem, hex_color):
    """Set font color to black, clearing any theme color"""
    rPr = get_or_create(style_elem, 'rPr')
    remove_all(rPr, 'color')
    c = ET.SubElement(rPr, W('color'))
    c.set(W('val'), hex_color)

def fix_alignment(style_elem, align_val):
    if align_val is None: return
    pPr = get_or_create(style_elem, 'pPr')
    remove_all(pPr, 'jc')
    ET.SubElement(pPr, W('jc')).set(W('val'), align_val)

def fix_line_spacing(style_elem, multiplier):
    pPr = get_or_create(style_elem, 'pPr')
    remove_all(pPr, 'spacing')
    s = ET.SubElement(pPr, W('spacing'))
    s.set(W('line'), str(int(multiplier*240))); s.set(W('lineRule'), 'auto')

def fix_first_line_indent(style_elem, cm_val):
    pPr = get_or_create(style_elem, 'pPr')
    ind = pPr.find(W('ind'))
    if ind is None: ind = ET.SubElement(pPr, W('ind'))
    if cm_val and cm_val > 0: ind.set(W('firstLine'), str(int(cm_val*567)))
    else:
        for a in ['firstLine','hanging','firstLineChars']:
            if W(a) in ind.attrib: del ind.attrib[W(a)]

def fix_space_before_after(style_elem, before_pt, after_pt):
    pPr = get_or_create(style_elem, 'pPr')
    s = pPr.find(W('spacing'))
    if s is None: s = ET.SubElement(pPr, W('spacing'))
    if before_pt is not None: s.set(W('before'), str(int(before_pt*20)))
    if after_pt is not None: s.set(W('after'), str(int(after_pt*20)))

def fix_keep_with_next(style_elem, keep=True):
    pPr = get_or_create(style_elem, 'pPr')
    if keep: get_or_create(pPr, 'keepNext')
    else: remove_all(pPr, 'keepNext')

def rename_style(style_elem, new_name):
    name_el = style_elem.find(W('name'))
    if name_el is not None: name_el.set(W('val'), new_name)

# ---- Style specs ----
# (name, ascii_font, ea_font, size_pt, bold, alignment, line_spacing, indent_cm, before_pt, after_pt, keep_next, color_hex)

specs = [
    ('Normal',          'Times New Roman', 'SimSun', 12, False, 'both',   1.25, 0.74, 0,  0, False, '000000'),
    ('Body Text',       'Times New Roman', 'SimSun', 12, False, 'both',   1.25, 0.74, 0,  0, False, '000000'),
    ('First Paragraph', 'Times New Roman', 'SimSun', 12, False, 'both',   1.25, 0.74, 0,  0, False, '000000'),
    ('Compact',         'Times New Roman', 'SimSun', 12, False, 'both',   1.25, 0,    0,  0, False, '000000'),
    ('Title',           'Times New Roman', 'SimHei',16, True,  'center', 1.5,  0,    12, 6, False, '000000'),
    ('Subtitle',        'Times New Roman', 'SimHei',14, False, 'center', 1.25, 0,    0,  6, False, '000000'),
    ('Author',          'Times New Roman', 'SimSun', 12, False, 'center', 1.25, 0,    0,  0, False, '000000'),
    ('Date',            'Times New Roman', 'SimSun', 12, False, 'center', 1.25, 0,    0,  0, False, '000000'),
    ('Abstract',        'Times New Roman', 'SimSun', 12, False, 'both',   1.25, 0.74, 0,  0, False, '000000'),
    ('Abstract Title',  'Times New Roman', 'SimHei',14, True,  'center', 1.25, 0,    6,  6, False, '000000'),
    ('Heading 1',       'Times New Roman', 'SimHei',14, True,  'center', 1.5,  0,    12, 6, False, '000000'),
    ('Heading 2',       'Times New Roman', 'SimHei',13, True,  'left',   1.5,  0,    8,  4, False, '000000'),
    ('Heading 3',       'Times New Roman', 'SimHei',12, True,  'left',   1.25, 0,    6,  3, False, '000000'),
    ('Caption',         'Times New Roman', 'SimSun', 10.5,True,  'center', 1.25, 0,    6,  3, False, '000000'),
    ('Table Caption',   'Times New Roman', 'SimSun', 10.5,True,  'center', 1.25, 0,    6,  3, False, '000000'),
    ('Image Caption',   'Times New Roman', 'SimSun', 10.5,True,  'center', 1.25, 0,    6,  3, False, '000000'),
    ('Bibliography',    'Times New Roman', 'SimSun', 10.5,False, 'both',   1.25, 0,    0,  0, False, '000000'),
    ('Source Code',     'Consolas',        'SimSun', 9,   False, 'left',   1.0,  0,    0,  0, False, '000000'),
    ('Block Text',      'Times New Roman', 'SimSun', 12,  False, 'both',   1.25, 0.74, 0,  0, False, '000000'),
    ('Footnote Text',   'Times New Roman', 'SimSun', 9,   False, 'left',   1.0,  0,    0,  0, False, '000000'),
    ('TOC Heading',     'Times New Roman', 'SimHei',14,  True,  'center', 1.5,  0,    12, 6, False, '000000'),
]
for i in range(4,10):
    specs.append((f'Heading {i}','Times New Roman','SimHei',12,True,'left',1.0,0,6,3,False,'000000'))

# Char variants
char_specs = []
for n,asc,ea,sz,bd,al,ls,fli,sb,sa,kwn,clr in specs:
    if al is not None:
        char_specs.append((f'{n} Char',asc,ea,sz,bd,None,None,None,None,None,None,clr))
all_specs = specs + char_specs

# ===== MAIN =====
print("Reading reference.docx...")
with zipfile.ZipFile(REF_DOCX, 'r') as zin:
    all_files = {n: zin.read(n) for n in zin.namelist()}

root = ET.fromstring(all_files['word/styles.xml'])
style_map = {}
for se in root.findall(W('style')):
    ne = se.find(W('name'))
    if ne is not None: style_map[ne.get(W('val')).lower()] = (se, ne.get(W('val')))

mod = 0
for n,asc,ea,sz,bd,al,ls,fli,sb,sa,kwn,clr in all_specs:
    k = n.lower()
    if k not in style_map: continue
    se, cn = style_map[k]
    if cn != n: rename_style(se, n)
    fix_fonts(se, asc, ea)
    fix_font_size(se, sz)
    fix_bold(se, bd)
    fix_color(se, clr)
    fix_alignment(se, al)
    if ls is not None: fix_line_spacing(se, ls)
    if fli is not None: fix_first_line_indent(se, fli)
    if sb is not None or sa is not None: fix_space_before_after(se, sb, sa)
    if kwn: fix_keep_with_next(se, True)
    mod += 1
    print(f'  [OK] {n:28s} | {sz}pt {clr} | {ea}/{asc}')

print(f'\nTotal modified: {mod}')

all_files['word/styles.xml'] = ET.tostring(root, encoding='utf-8', xml_declaration=True)
with zipfile.ZipFile(REF_DOCX, 'w', zipfile.ZIP_DEFLATED) as zout:
    for n, d in all_files.items(): zout.writestr(n, d)

print('[DONE] reference.docx updated — all headings BLACK, 1.0x line, Title=16pt, H2=12pt')
