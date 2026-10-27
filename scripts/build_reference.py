# -*- coding: utf-8 -*-
"""
构建 reference.docx v2.1
  1. 从 pandoc 默认生成基础 reference.docx
  2. 修复段落/字符样式（CJK/Latin 字体分离 + 字号/加粗/对齐/行距）
  3. 注入 "Table" 表格样式（三线表边框：1.5pt 顶/底 + 0.75pt 表头下）
  4. 注入页脚 PAGE 字段、页面设置（A4 + 2.5 cm 页边距）与 sectPr 引用
  5. 确保所有字体颜色 #000000，禁用 keepNext

用法：python scripts/build_reference.py

v2.1 变更：
  - sectPr 补齐 w:footerReference / w:pgSz / w:pgMar：
    A4 11906x16838 twips，四边 2.5 cm = 1417 twips，页眉页脚 720 twips
  - footerReference 的 r:id 动态取自 document.xml.rels（当前为 rId31）
  - 修正新增 Relationship 缺 Relationships 命名空间的问题，并归一化 rels 输出
  - 幂等：重复运行先删旧 footerReference/pgSz/pgMar 再按 CT_SectPr 顺序插入

v2.0 变更：
  - "Table" 样式 → Pandoc 3.x 自动应用到所有表格 → 零后处理
"""
import subprocess, sys, os, zipfile, xml.etree.ElementTree as ET

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
REF_DOCX = os.path.join(PROJECT_ROOT, 'templates', 'reference.docx')

NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
REL_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
PKG_REL_NS = 'http://schemas.openxmlformats.org/package/2006/relationships'
CT_NS = 'http://schemas.openxmlformats.org/package/2006/content-types'
FOOTER_REL_TYPE = REL_NS + '/footer'
ET.register_namespace('w', NS)
ET.register_namespace('r', REL_NS)

# OOXML CT_SectPr 子元素顺序；footerReference 必须排在 footnotePr/pgSz 之前
SECTPR_ORDER = [
    'headerReference', 'footerReference', 'footnotePr', 'endnotePr', 'type',
    'pgSz', 'pgMar', 'paperSrc', 'pgBorders', 'lnNumType', 'pgNumType', 'cols',
    'formProt', 'vAlign', 'noEndnote', 'titlePg', 'textDirection', 'bidi',
    'rtlGutter', 'docGrid', 'printerSettings', 'sectPrChange',
]

# A4 纵向 21 x 29.7 cm，四边 2.5 cm，页眉页脚 1.27 cm（单位：twips）
PAGE_SETUP = {
    'pgSz': {'w': '11906', 'h': '16838'},
    'pgMar': {
        'top': '1417', 'right': '1417', 'bottom': '1417', 'left': '1417',
        'header': '720', 'footer': '720', 'gutter': '0',
    },
}

def W(tag): return f'{{{NS}}}{tag}'

def get_or_create(parent, tag):
    el = parent.find(W(tag))
    if el is None:
        el = ET.SubElement(parent, W(tag))
    return el

def remove_all(parent, tag):
    for el in list(parent.findall(W(tag))):
        parent.remove(el)

def local_name(tag):
    """返回带命名空间标签的本地名。"""
    return tag.split('}')[-1]

def serialize_with_default_ns(root, namespace):
    """用 OPC 默认命名空间序列化，输出 <Relationships xmlns=...> 而非 ns0: 前缀。"""
    ET.register_namespace('', namespace)
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)

def insert_sectpr_child(sect_pr, child):
    """按 OOXML CT_SectPr 规定顺序插入 sectPr 子元素。"""
    order = {name: index for index, name in enumerate(SECTPR_ORDER)}
    fallback = len(SECTPR_ORDER)
    target = order.get(local_name(child.tag), fallback)
    position = len(sect_pr)
    for index, existing in enumerate(sect_pr):
        if order.get(local_name(existing.tag), fallback) > target:
            position = index
            break
    sect_pr.insert(position, child)

def rebuild_rels(rels_bytes):
    """归一化 document.xml.rels，确保 footer 关系存在，返回 (新字节, footer rId)。

    历史版本用 ET.SubElement(rels_root, 'Relationship') 追加关系，生成的是
    无 Relationships 命名空间的元素；这里统一重建为带 OPC 命名空间的干净 XML。
    """
    entries = []
    if rels_bytes:
        root = ET.fromstring(rels_bytes)
        entries = [
            dict(element.attrib) for element in root
            if local_name(element.tag) == 'Relationship'
        ]

    footer = next(
        (entry for entry in entries if entry.get('Type', '') == FOOTER_REL_TYPE),
        None,
    )
    existing_ids = {entry.get('Id') for entry in entries}
    next_id = 1 + max(
        [int(entry['Id'][3:]) for entry in entries
         if str(entry.get('Id', '')).startswith('rId') and entry['Id'][3:].isdigit()]
        or [0]
    )

    def allocate_id():
        nonlocal next_id
        while f'rId{next_id}' in existing_ids:
            next_id += 1
        relation_id = f'rId{next_id}'
        existing_ids.add(relation_id)
        next_id += 1
        return relation_id

    if footer is None:
        footer = {'Id': allocate_id(), 'Type': FOOTER_REL_TYPE, 'Target': 'footer1.xml'}
        entries.append(footer)
    footer.setdefault('Id', allocate_id())
    footer['Type'] = FOOTER_REL_TYPE
    footer['Target'] = 'footer1.xml'

    new_root = ET.Element(f'{{{PKG_REL_NS}}}Relationships')
    for entry in entries:
        relation = ET.SubElement(new_root, f'{{{PKG_REL_NS}}}Relationship')
        for key in ('Id', 'Type', 'Target', 'TargetMode'):
            if key in entry:
                relation.set(key, entry[key])
    return serialize_with_default_ns(new_root, PKG_REL_NS), footer['Id']

def apply_page_setup(document_bytes, footer_rid):
    """向 reference document.xml 的 sectPr 写入 A4 页面设置与页脚引用（幂等）。"""
    root = ET.fromstring(document_bytes)
    body = root.find(W('body'))
    if body is None:
        raise RuntimeError('reference.docx 的 document.xml 缺少 w:body')
    sect_pr = body.find(W('sectPr'))
    if sect_pr is None:
        sect_pr = ET.SubElement(body, W('sectPr'))

    # 先删旧值：重复运行不重复插入，旧 rId 也不会残留
    for tag in ('footerReference', 'pgSz', 'pgMar'):
        for element in list(sect_pr.findall(W(tag))):
            sect_pr.remove(element)

    footer_reference = ET.Element(W('footerReference'))
    footer_reference.set(W('type'), 'default')
    footer_reference.set(f'{{{REL_NS}}}id', footer_rid)
    insert_sectpr_child(sect_pr, footer_reference)

    page_size = ET.Element(W('pgSz'))
    for name, value in PAGE_SETUP['pgSz'].items():
        page_size.set(W(name), value)
    insert_sectpr_child(sect_pr, page_size)

    page_margin = ET.Element(W('pgMar'))
    for name, value in PAGE_SETUP['pgMar'].items():
        page_margin.set(W(name), value)
    insert_sectpr_child(sect_pr, page_margin)

    return ET.tostring(root, encoding='utf-8', xml_declaration=True)

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

    # ---- Step 2.5: 页脚 + 页面设置 + 关系/内容类型 ----
    print("\n[2.5/3] Preparing footer, page setup and relationships...")
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

    # document.xml.rels：归一化命名空间，确保 footer 关系存在并取回 rId
    rels_key = 'word/_rels/document.xml.rels'
    if rels_key not in all_files:
        print(f'ERROR: reference.docx 缺少 {rels_key}，无法关联页脚。')
        sys.exit(1)
    all_files[rels_key], footer_rid = rebuild_rels(all_files[rels_key])
    print(f'  document.xml.rels normalized (footer r:id={footer_rid} → footer1.xml)')

    # [Content_Types].xml：注册 footer1.xml
    content_types = all_files.get('[Content_Types].xml')
    if content_types is not None:
        ct_root = ET.fromstring(content_types)
        has_footer_ct = any(ct.get('PartName') == '/word/footer1.xml' for ct in ct_root)
        if not has_footer_ct:
            footer_ct = ET.SubElement(ct_root, '{%s}Override' % CT_NS)
            footer_ct.set('PartName', '/word/footer1.xml')
            footer_ct.set('ContentType', 'application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml')
            all_files['[Content_Types].xml'] = serialize_with_default_ns(ct_root, CT_NS)
            print('  Updated [Content_Types].xml (footer1.xml registered)')
        else:
            print('  [Content_Types].xml 已注册 footer1.xml')

    # document.xml：写入 sectPr 页面设置与 footerReference
    document_key = 'word/document.xml'
    if document_key not in all_files:
        print(f'ERROR: reference.docx 缺少 {document_key}。')
        sys.exit(1)
    all_files[document_key] = apply_page_setup(all_files[document_key], footer_rid)
    print(f'  [OK] sectPr: footerReference(r:id={footer_rid}) + pgSz(A4) + pgMar(2.5cm)')

    print('  [OK] Footer and page setup ready')

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
