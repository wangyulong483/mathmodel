@echo off
REM ================================================
REM   数学建模论文 Markdown → Word 转换工具
REM   Pandoc + reference.docx → paper.docx
REM ================================================

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

REM Detect Pandoc path
set "PANDOC="
if exist "%LOCALAPPDATA%\Pandoc\pandoc.exe" (
    set "PANDOC=%LOCALAPPDATA%\Pandoc\pandoc.exe"
) else if exist "%LOCALAPPDATA%\Microsoft\WinGet\Packages\JohnMacFarlane.Pandoc_Microsoft.Winget.Source_8wekyb3d8bbwe\pandoc-*\pandoc.exe" (
    for /d %%d in ("%LOCALAPPDATA%\Microsoft\WinGet\Packages\JohnMacFarlane.Pandoc_Microsoft.Winget.Source_8wekyb3d8bbwe\pandoc-*") do (
        if exist "%%d\pandoc.exe" set "PANDOC=%%d\pandoc.exe"
    )
) else (
    where pandoc >nul 2>&1
    if %ERRORLEVEL% EQU 0 set "PANDOC=pandoc"
)

if "%PANDOC%"=="" (
    echo [ERROR] Pandoc not found. Install: winget install JohnMacFarlane.Pandoc
    pause
    exit /b 1
)

echo ================================================
echo   Math Paper Generator
echo ================================================
echo.
echo [1/2] Pandoc: paper.md → paper.docx
echo.

"%PANDOC%" paper.md -o paper.docx --reference-doc=reference.docx --mathml --syntax-highlighting=pygments

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Pandoc conversion failed.
    pause
    exit /b 1
)

echo [2/2] Post-processing: tables, page numbers, styles ...
python -c "
from docx import Document; from docx.shared import Cm; from docx.oxml.ns import qn; from lxml import etree
import zipfile

doc = Document('paper.docx')

for i, table in enumerate(doc.tables):
    table.autofit = False
    tbl = table._tbl; tblPr = tbl.find(qn('w:tblPr'))
    if tblPr is None: tblPr = etree.SubElement(tbl, qn('w:tblPr'))

    # 100% width + fixed layout
    for tag in ['tblW','tblLayout']:
        for el in list(tblPr):
            if el.tag == qn(f'w:{tag}'): tblPr.remove(el)
    tw = etree.SubElement(tblPr, qn('w:tblW')); tw.set(qn('w:w'),'5000'); tw.set(qn('w:type'),'pct')
    etree.SubElement(tblPr, qn('w:tblLayout')).set(qn('w:type'),'fixed')

    # 3-line borders
    for el in list(tblPr):
        if el.tag == qn('w:tblBorders'): tblPr.remove(el)
    borders = etree.SubElement(tblPr, qn('w:tblBorders'))
    for side, sz in [('top','12'),('bottom','12')]:
        el = etree.SubElement(borders, qn(f'w:{side}'))
        for a,v in [('w:val','single'),('w:sz',sz),('w:space','0'),('w:color','000000')]: el.set(qn(a),v)
    for side in ['left','right','insideH','insideV']:
        el = etree.SubElement(borders, qn(f'w:{side}'))
        for a,v in [('w:val','none'),('w:sz','0'),('w:space','0'),('w:color','auto')]: el.set(qn(a),v)

    # Clear cell borders
    for tc in tbl.findall(f'.//{qn(\"w:tc\")}'):
        tcp = tc.find(qn('w:tcPr'))
        if tcp is not None:
            for tcb in list(tcp):
                if tcb.tag == qn('w:tcBorders'): tcp.remove(tcb)

    # Column widths
    ncols = len(table.columns)
    if i == 0 and ncols == 3:
        widths = [Cm(3.0), Cm(9.6), Cm(3.0)]
    else:
        w = Cm(15.6 / ncols); widths = [w] * ncols

    for row in table.rows:
        for ci, cell in enumerate(row.cells):
            if ci < len(widths): cell.width = widths[ci]

    # Header row thin bottom border
    rows = tbl.findall(qn('w:tr'))
    if rows:
        for tc in rows[0].findall(qn('w:tc')):
            tcp = tc.find(qn('w:tcPr'))
            if tcp is None: tcp = etree.SubElement(tc, qn('w:tcPr'))
            for el in list(tcp):
                if el.tag == qn('w:tcBorders'): tcp.remove(el)
            tcb = etree.SubElement(tcp, qn('w:tcBorders'))
            b = etree.SubElement(tcb, qn('w:bottom'))
            for a,v in [('w:val','single'),('w:sz','6'),('w:space','0'),('w:color','000000')]: b.set(qn(a),v)

# Fix un-styled paragraphs
for p in doc.paragraphs:
    pPr = p._element.find(qn('w:pPr'))
    if pPr is not None:
        for tag in ['keepNext','keepLines']:
            for el in list(pPr):
                if el.tag == qn(f'w:{tag}'): pPr.remove(el)
    if p.style is None and p.text.strip():
        try: p.style = doc.styles['Compact']
        except: pass

# Page numbers
sect = doc.sections[0]
sectPr = sect._sectPr
for el in list(sectPr):
    if el.tag in [qn('w:footerReference'), qn('w:pgNumType')]: sectPr.remove(el)
fr = etree.SubElement(sectPr, qn('w:footerReference'))
fr.set(qn('w:type'), 'default'); fr.set(qn('r:id'), 'rFooter1')
etree.SubElement(sectPr, qn('w:pgNumType')).set(qn('w:fmt'), 'decimal')

footer_xml = b'<?xml version=\"1.0\"?><w:ftr xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\"><w:p><w:pPr><w:jc w:val=\"center\"/></w:pPr><w:r><w:rPr><w:rFonts w:ascii=\"Times New Roman\" w:hAnsi=\"Times New Roman\"/><w:sz w:val=\"21\"/></w:rPr><w:fldChar w:fldCharType=\"begin\"/></w:r><w:r><w:rPr><w:rFonts w:ascii=\"Times New Roman\" w:hAnsi=\"Times New Roman\"/><w:sz w:val=\"21\"/></w:rPr><w:instrText xml:space=\"preserve\"> PAGE </w:instrText></w:r><w:r><w:rPr><w:rFonts w:ascii=\"Times New Roman\" w:hAnsi=\"Times New Roman\"/><w:sz w:val=\"21\"/></w:rPr><w:fldChar w:fldCharType=\"end\"/></w:r></w:p></w:ftr>'

doc.save('paper.docx')

# Inject footer
with zipfile.ZipFile('paper.docx','r') as z:
    all_files = {n:z.read(n) for n in z.namelist()}
all_files['word/footer1.xml'] = footer_xml
rel_root = etree.fromstring(all_files['word/_rels/document.xml.rels'])
etree.SubElement(rel_root, '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}Relationship').set('Id', 'rFooter1')
rel_root[-1].set('Type', 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer')
rel_root[-1].set('Target', 'footer1.xml')
all_files['word/_rels/document.xml.rels'] = etree.tostring(rel_root, encoding='utf-8', xml_declaration=True)
ct_root = etree.fromstring(all_files['[Content_Types].xml'])
ct_ns = 'http://schemas.openxmlformats.org/package/2006/content-types'
ov = etree.SubElement(ct_root, f'{{{ct_ns}}}Override')
ov.set('PartName', '/word/footer1.xml')
ov.set('ContentType', 'application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml')
all_files['[Content_Types].xml'] = etree.tostring(ct_root, encoding='utf-8', xml_declaration=True)
with zipfile.ZipFile('paper.docx','w', zipfile.ZIP_DEFLATED) as z:
    for n,d in all_files.items(): z.writestr(n,d)

echo ================================================
echo   [DONE] paper.docx generated.
echo ================================================
echo   Tables: 100% width, 3-line borders
echo   Page numbers: footer center, decimal
echo.
pause
