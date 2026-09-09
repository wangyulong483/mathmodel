# -*- coding: utf-8 -*-
"""
构建 reference.docx v2.0
  1. 从 pandoc 默认生成基础 reference.docx
  2. 修复段落/字符样式（CJK/Latin 字体分离 + 字号/加粗/对齐/行距）
  3. 注入 "Table" 表格样式（三线表边框：1.5pt 顶/底 + 0.75pt 表头下）
  4. 确保所有字体颜色 #000000，禁用 keepNext

用法：python scripts/build_reference.py

v2.0 新增：
  - "Table" 样式 → Pandoc 3.x 自动应用到所有表格 → 零后处理
  - 代码精简，移除废弃样式操作
"""
import subprocess, sys, os, zipfile, xml.etree.ElementTree as ET

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
REF_DOCX = os.path.join(PROJECT_ROOT, 'templates', 'reference.docx')

NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
ET.register_namespace('w', NS)
ET.register_namespace('r', 'http://schemas.openxmlformats.org/officeDocument/2006/relationships')

def W(tag): return f'{{{NS}}}{tag}'

def get_or_create(parent, tag):
    el = parent.find(W(tag))
    if el is None:
        el = ET.SubElement(parent, W(tag))
    return el

def remove_all(parent, tag):
    for el in list(parent.findall(W(tag))):
        parent.remove(el)

# ============================================================
#  字体/样式 辅助函数
# ============================================================

def set_fonts(style_elem, ascii_font, ea_font):
    """设置 CJK/Latin 分离字体，清除主题字体防止被覆盖（如 majorEastAsia→等线）"""
    rPr = get_or_create(style_elem, 'rPr')
    rFonts = get_or_create(rPr, 'rFonts')
    for a in ['ascii', 'hAnsi', 'eastAsia', 'cs']:
        rFonts.set(W(a), '')
    rFonts.set(W('ascii'), ascii_font)
    rFonts.set(W('hAnsi'), ascii_font)
    rFonts.set(W('eastAsia'), ea_font)
    rFonts.set(W('cs'), ascii_font)
    # 清除主题字体引用——否则 majorEastAsia→等线 会覆盖显式的 SimHei
    for a in ['asciiTheme', 'hAnsiTheme', 'eastAsiaTheme', 'cstheme']:
        rFonts.attrib.pop(W(a), None)

def set_font_size(style_elem, pt_size):
    rPr = get_or_create(style_elem, 'rPr')
    remove_all(rPr, 'sz'); remove_all(rPr, 'szCs')
    ET.SubElement(rPr, W('sz')).set(W('val'), str(int(pt_size * 2)))
    ET.SubElement(rPr, W('szCs')).set(W('val'), str(int(pt_size * 2)))

def set_bold(style_elem, bold_on):
    rPr = get_or_create(style_elem, 'rPr')
    remove_all(rPr, 'b'); remove_all(rPr, 'bCs')
    if bold_on:
        ET.SubElement(rPr, W('b'))
        bc = ET.SubElement(rPr, W('bCs'))
        bc.set(W('val'), 'true')

def set_color(style_elem, hex_color):
    """字体颜色设黑，清除主题色"""
    rPr = get_or_create(style_elem, 'rPr')
    remove_all(rPr, 'color')
    c = ET.SubElement(rPr, W('color'))
    c.set(W('val'), hex_color)

def set_alignment(style_elem, align_val):
    if align_val is None:
        return
    pPr = get_or_create(style_elem, 'pPr')
    remove_all(pPr, 'jc')
    ET.SubElement(pPr, W('jc')).set(W('val'), align_val)

def set_line_spacing(style_elem, multiplier):
    pPr = get_or_create(style_elem, 'pPr')
    remove_all(pPr, 'spacing')
    s = ET.SubElement(pPr, W('spacing'))
    s.set(W('line'), str(int(multiplier * 240)))
    s.set(W('lineRule'), 'auto')

def set_first_line_indent(style_elem, cm_val):
    pPr = get_or_create(style_elem, 'pPr')
    ind = pPr.find(W('ind'))
    if ind is None:
        ind = ET.SubElement(pPr, W('ind'))
    if cm_val and cm_val > 0:
        ind.set(W('firstLine'), str(int(cm_val * 567)))
    else:
        for a in ['firstLine', 'hanging', 'firstLineChars']:
            if W(a) in ind.attrib:
                del ind.attrib[W(a)]

def set_space_before_after(style_elem, before_pt, after_pt):
    pPr = get_or_create(style_elem, 'pPr')
    s = pPr.find(W('spacing'))
    if s is None:
        s = ET.SubElement(pPr, W('spacing'))
    if before_pt is not None:
        s.set(W('before'), str(int(before_pt * 20)))
    if after_pt is not None:
        s.set(W('after'), str(int(after_pt * 20)))

def disable_keep_next(style_elem):
    pPr = get_or_create(style_elem, 'pPr')
    remove_all(pPr, 'keepNext')
    remove_all(pPr, 'keepLines')

def rename_style(style_elem, new_name):
    name_el = style_elem.find(W('name'))
    if name_el is not None:
        name_el.set(W('val'), new_name)

# ============================================================
#  段落/字符样式规格
# ============================================================
# (name, ascii_font, ea_font, size_pt, bold, alignment,
#  line_spacing, indent_cm, before_pt, after_pt, color_hex)

# CUMCM community conventions (from LaTeX templates & 获奖论文):
#   Title:   三号黑体 (16pt) bold centered
#   H1:      四号黑体 (14pt) bold centered
#   H2/H3:   小四号黑体 (12pt) bold left-aligned
#   Body:    小四号宋体 (12pt)
#   Caption: 五号宋体 (10.5pt) bold centered
# Official rules (2026): font/size/line-spacing are not the main constraint,
#   but bold headings are universally expected in academic papers.
PARA_SPECS = [
    ('Normal',          'Times New Roman', 'SimSun', 12, False, 'both',   1.25, 0.74, 0,  0,  '000000'),
    ('Body Text',       'Times New Roman', 'SimSun', 12, False, 'both',   1.25, 0.74, 0,  0,  '000000'),
    ('First Paragraph', 'Times New Roman', 'SimSun', 12, False, 'both',   1.25, 0.74, 0,  0,  '000000'),
    ('Compact',         'Times New Roman', 'SimSun', 12, False, 'both',   1.25, 0,    0,  0,  '000000'),
    ('Title',           'Times New Roman', 'SimHei', 16, True,  'center', 1.5,  0,    12, 6,  '000000'),
    ('Subtitle',        'Times New Roman', 'SimHei', 14, False, 'center', 1.25, 0,    0,  6,  '000000'),
    ('Author',          'Times New Roman', 'SimSun', 12, False, 'center', 1.25, 0,    0,  0,  '000000'),
    ('Date',            'Times New Roman', 'SimSun', 12, False, 'center', 1.25, 0,    0,  0,  '000000'),
    ('Heading 1',       'Times New Roman', 'SimHei', 14, True,  'center', 1.5,  0,    12, 6,  '000000'),
    ('Heading 2',       'Times New Roman', 'SimHei', 12, True,  'left',   1.5,  0,    8,  4,  '000000'),
    ('Heading 3',       'Times New Roman', 'SimHei', 12, True,  'left',   1.25, 0,    6,  3,  '000000'),
    ('Caption',         'Times New Roman', 'SimSun', 10.5, True, 'center', 1.25, 0,    6,  3,  '000000'),
    ('Table Caption',   'Times New Roman', 'SimSun', 10.5, True, 'center', 1.25, 0,    6,  3,  '000000'),
    ('Image Caption',   'Times New Roman', 'SimSun', 10.5, True, 'center', 1.25, 0,    6,  3,  '000000'),
    ('Bibliography',    'Times New Roman', 'SimSun', 10.5, False,'both',   1.25, 0,    0,  0,  '000000'),
    ('Source Code',     'Consolas',        'SimSun', 9,  False, 'left',   1.0,  0,    0,  0,  '000000'),
    ('Block Text',      'Times New Roman', 'SimSun', 12,  False, 'both',   1.25, 0.74, 0,  0,  '000000'),
]

# H4-H9: 小四号黑体 (12pt) bold left
for i in range(4, 10):
    PARA_SPECS.append((f'Heading {i}', 'Times New Roman', 'SimHei', 12, True, 'left', 1.0, 0, 6, 3, '000000'))

# Character variants (no alignment/spacing/indent)
CHAR_SPECS = []
for n, asc, ea, sz, bd, al, ls, fli, sb, sa, clr in PARA_SPECS:
    if al is not None:
        CHAR_SPECS.append((f'{n} Char', asc, ea, sz, bd, None, None, None, None, None, clr))

ALL_PARA_SPECS = PARA_SPECS + CHAR_SPECS

# ============================================================
#  "Table" 样式：三线表 OOXML 定义
# ============================================================

def create_table_style_xml():
    """返回完整的 <w:style w:type="table" w:styleId="Table"> 元素"""
    style = ET.Element(W('style'))
    style.set(W('type'), 'table')
    style.set(W('styleId'), 'Table')

    name = ET.SubElement(style, W('name'))
    name.set(W('val'), 'Table')

    basedOn = ET.SubElement(style, W('basedOn'))
    basedOn.set(W('val'), '7')  # Normal Table

    qf = ET.SubElement(style, W('qFormat'))

    # 表格属性：居中 + 三线表边框
    tblPr = ET.SubElement(style, W('tblPr'))

    jc = ET.SubElement(tblPr, W('jc'))
    jc.set(W('val'), 'center')

    tblBorders = ET.SubElement(tblPr, W('tblBorders'))
    # 顶线 1.5pt = sz 12
    top = ET.SubElement(tblBorders, W('top'))
    for a, v in [('val', 'single'), ('sz', '12'), ('space', '0'), ('color', '000000')]:
        top.set(W(a), v)
    # 底线 1.5pt
    bottom = ET.SubElement(tblBorders, W('bottom'))
    for a, v in [('val', 'single'), ('sz', '12'), ('space', '0'), ('color', '000000')]:
        bottom.set(W(a), v)
    # 无竖线 / 无行间线
    for side in ['left', 'right', 'insideH', 'insideV']:
        el = ET.SubElement(tblBorders, W(side))
        for a, v in [('val', 'none'), ('sz', '0'), ('space', '0'), ('color', 'auto')]:
            el.set(W(a), v)

    # 单元格属性：垂直居中
    tcPr = ET.SubElement(style, W('tcPr'))
    vAlign = ET.SubElement(tcPr, W('vAlign'))
    vAlign.set(W('val'), 'center')

    # 表头行条件格式：底线 0.75pt = sz 6
    tblStylePr = ET.SubElement(style, W('tblStylePr'))
    tblStylePr.set(W('type'), 'firstRow')
    tcPr_first = ET.SubElement(tblStylePr, W('tcPr'))
    tcBorders_first = ET.SubElement(tcPr_first, W('tcBorders'))
    bottom_first = ET.SubElement(tcBorders_first, W('bottom'))
    for a, v in [('val', 'single'), ('sz', '6'), ('space', '0'), ('color', '000000')]:
        bottom_first.set(W(a), v)

    return style

# ============================================================
#  主流程
# ============================================================

def main():
    # ---- Step 0: 生成基础 reference.docx ----
    if not os.path.exists(REF_DOCX):
        print("Generating base reference.docx from pandoc...")
        try:
            subprocess.run(['pandoc', '-o', REF_DOCX,
                          '--print-default-data-file', 'reference.docx'],
                          check=True, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"ERROR: pandoc not found or failed: {e}")
            print("Install: winget install JohnMacFarlane.Pandoc")
            sys.exit(1)
        print(f"  Created: {REF_DOCX}")
    else:
        print(f"Using existing: {REF_DOCX}")

    # ---- Step 1: 修复 styles.xml ----
    print("\n[1/3] Fixing paragraph/character styles...")
    with zipfile.ZipFile(REF_DOCX, 'r') as zin:
        all_files = {n: zin.read(n) for n in zin.namelist()}

    root = ET.fromstring(all_files['word/styles.xml'])

    # 构建 style_id → (element, current_name) 映射
    style_map = {}
    for se in root.findall(W('style')):
        ne = se.find(W('name'))
        if ne is not None:
            style_map[ne.get(W('val')).lower()] = (se, ne.get(W('val')))

    modified = 0
    for n, asc, ea, sz, bd, al, ls, fli, sb, sa, clr in ALL_PARA_SPECS:
        k = n.lower()
        if k not in style_map:
            continue
        se, cn = style_map[k]
        if cn != n:
            rename_style(se, n)
        set_fonts(se, asc, ea)
        set_font_size(se, sz)
        set_bold(se, bd)
        set_color(se, clr)
        set_alignment(se, al)
        if ls is not None:
            set_line_spacing(se, ls)
        if fli is not None:
            set_first_line_indent(se, fli)
        if sb is not None or sa is not None:
            set_space_before_after(se, sb, sa)
        disable_keep_next(se)
        modified += 1
        print(f'  [OK] {n:28s} | {sz}pt {clr} | {ea}/{asc}')

    print(f'  Total modified: {modified} paragraph/character styles')

    # ---- Step 2: 注入 "Table" 样式 ----
    print("\n[2/3] Injecting 'Table' style (three-line table borders)...")
    table_style = create_table_style_xml()

    # 检查是否已存在 "Table" 样式
    existing_table = None
    for se in root.findall(W('style')):
        if se.get(W('styleId')) == 'Table':
            existing_table = se
            break

    if existing_table is not None:
        root.remove(existing_table)
        print('  Removed existing "Table" style')

    root.append(table_style)
    print('  [OK] "Table" style injected: top 1.5pt + bottom 1.5pt + header-bottom 0.75pt')

    # ---- Step 2.5: 创建页脚页码 ----
    print("\n[2.5/3] Creating footer with PAGE field...")
    FOOTER_XML = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:ftr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:p>
    <w:pPr><w:jc w:val="center"/></w:pPr>
    <w:r>
      <w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/><w:sz w:val="21"/></w:rPr>
      <w:fldChar w:fldCharType="begin"/>
    </w:r>
    <w:r>
      <w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/><w:sz w:val="21"/></w:rPr>
      <w:instrText xml:space="preserve"> PAGE </w:instrText>
    </w:r>
    <w:r>
      <w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/><w:sz w:val="21"/></w:rPr>
      <w:fldChar w:fldCharType="end"/>
    </w:r>
  </w:p>
</w:ftr>'''

    all_files['word/footer1.xml'] = FOOTER_XML.encode('utf-8')
    print('  Created word/footer1.xml (centered PAGE field, TNR 10.5pt)')

    # Update document.xml.rels to reference footer
    rels_xml = all_files.get('word/_rels/document.xml.rels')
    if rels_xml is not None:
        rels_root = ET.fromstring(rels_xml)
        RELS_NS = 'http://schemas.openxmlformats.org/package/2006/relationships'
        # Check if footer relationship already exists
        has_footer_rel = False
        for rel in rels_root:
            if rel.get('Type', '').endswith('/footer'):
                has_footer_rel = True
                break
        if not has_footer_rel:
            rId = 'rId99'
            # Find max rId
            max_id = 0
            for rel in rels_root:
                rid = rel.get('Id', 'rId0')
                if rid.startswith('rId'):
                    try:
                        max_id = max(max_id, int(rid[3:]))
                    except:
                        pass
            rId = f'rId{max_id + 1}'
            footer_rel = ET.SubElement(rels_root, 'Relationship')
            footer_rel.set('Id', rId)
            footer_rel.set('Type', 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer')
            footer_rel.set('Target', 'footer1.xml')
            all_files['word/_rels/document.xml.rels'] = ET.tostring(rels_root, encoding='utf-8', xml_declaration=True)
            print(f'  Updated document.xml.rels ({rId} → footer1.xml)')

    # Update [Content_Types].xml
    content_types = all_files.get('[Content_Types].xml')
    if content_types is not None:
        ct_root = ET.fromstring(content_types)
        CT_NS = 'http://schemas.openxmlformats.org/package/2006/content-types'
        has_footer_ct = False
        for ct in ct_root:
            if ct.get('PartName') == '/word/footer1.xml':
                has_footer_ct = True
                break
        if not has_footer_ct:
            footer_ct = ET.SubElement(ct_root, '{%s}Override' % CT_NS)
            footer_ct.set('PartName', '/word/footer1.xml')
            footer_ct.set('ContentType', 'application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml')
            all_files['[Content_Types].xml'] = ET.tostring(ct_root, encoding='utf-8', xml_declaration=True)
            print('  Updated [Content_Types].xml (footer1.xml registered)')

    print('  [OK] Footer ready')

    # ---- Step 3: 写回 ----
    print("\n[3/3] Writing reference.docx...")
    all_files['word/styles.xml'] = ET.tostring(root, encoding='utf-8', xml_declaration=True)

    with zipfile.ZipFile(REF_DOCX, 'w', zipfile.ZIP_DEFLATED) as zout:
        for n, d in all_files.items():
            zout.writestr(n, d)

    print(f'[DONE] {REF_DOCX} updated — all styles black, keepNext disabled, "Table" style ready.')
    print()
    print('Next: run scripts/build_paper.py after output/paper.md is ready.')
    print('Then: inspect output/audit_report.md and open the generated DOCX in Word/WPS.')

if __name__ == '__main__':
    main()
