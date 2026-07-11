# -*- coding: utf-8 -*-
"""项目初始化脚本 —— 为新任务准备干净的 output/ 目录，验证依赖，构建模板。

用法：python scripts/init_project.py
"""
import os
import sys
import shutil
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'output')
FIG_DIR = os.path.join(OUTPUT_DIR, 'figures')
TBL_DIR = os.path.join(OUTPUT_DIR, 'tables')
REF_DOCX = os.path.join(PROJECT_ROOT, 'templates', 'reference.docx')
GITIGNORE = os.path.join(OUTPUT_DIR, '.gitignore')

# ====== CLI 参数 ======
KEEP_REFERENCE = '--keep-reference' in sys.argv
SKIP_DEPS = '--skip-deps' in sys.argv
FORCE = '--force' in sys.argv or '-f' in sys.argv
HELP = '--help' in sys.argv or '-h' in sys.argv

if HELP:
    print("""用法：python scripts/init_project.py [选项]

初始化数学建模项目，为新任务准备干净的 output/ 目录。

选项：
  --force, -f        跳过确认提示，直接清空 output/
  --keep-reference    保留现有的 templates/reference.docx（不重建）
  --skip-deps         跳过依赖检查
  --help, -h          显示此帮助
""")
    sys.exit(0)

print("=" * 60)
print("  MathModel v3.0 —— 项目初始化")
print("=" * 60)
print()

# ====== Step 1: 依赖检查 ======
if not SKIP_DEPS:
    print("[1/5] 检查依赖...")

    deps_ok = True
    deps = {
        'pandoc':  'winget install JohnMacFarlane.Pandoc',
        'python':  'https://www.python.org/downloads/',
    }
    py_pkgs = {
        'docx':       ('python-docx',  'pip install python-docx'),
        'PIL':        ('Pillow',       'pip install Pillow'),
        'numpy':      ('numpy',        'pip install numpy'),
        'scipy':      ('scipy',        'pip install scipy'),
        'pandas':     ('pandas',       'pip install pandas'),
        'matplotlib': ('matplotlib',   'pip install matplotlib'),
        'sklearn':    ('scikit-learn', 'pip install scikit-learn'),
        'lxml':       ('lxml',         'pip install lxml'),
    }

    # 检查系统工具
    pandoc_path = None
    for loc in [
        os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Pandoc', 'pandoc.exe'),
        os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Microsoft', 'WinGet', 'Packages'),
    ]:
        if os.path.exists(loc):
            if 'WinGet' in loc:
                import glob
                candidates = glob.glob(os.path.join(loc, 'JohnMacFarlane.Pandoc_*', 'pandoc-*', 'pandoc.exe'))
                if candidates:
                    pandoc_path = candidates[0]
                    break
            else:
                pandoc_path = loc
                break

    if pandoc_path and os.path.exists(pandoc_path):
        result = subprocess.run([pandoc_path, '--version'], capture_output=True, text=True)
        version_line = result.stdout.split('\n')[0] if result.stdout else 'unknown'
        print(f'  [OK] pandoc — {version_line}')
    else:
        try:
            result = subprocess.run(['pandoc', '--version'], capture_output=True, text=True)
            version_line = result.stdout.split('\n')[0] if result.stdout else 'unknown'
            print(f'  [OK] pandoc — {version_line} (PATH)')
        except FileNotFoundError:
            print(f'  [WARN] pandoc 未找到。安装：winget install JohnMacFarlane.Pandoc')
            deps_ok = False

    # 检查 Python 包
    for imp, (pkg, inst) in py_pkgs.items():
        try:
            __import__(imp)
            print(f'  [OK] {pkg}')
        except ImportError:
            print(f'  [WARN] {pkg} 未安装。安装：{inst}')
            deps_ok = False

    if not deps_ok:
        print('\n  请安装缺失的依赖后重试，或使用 --skip-deps 跳过检查。')
    print()

# ====== Step 2: 清空 output/ ======
print("[2/5] 准备 output/ 目录...")

existing = os.listdir(OUTPUT_DIR) if os.path.exists(OUTPUT_DIR) else []
has_content = any(f not in ('.gitignore',) for f in existing)

if has_content:
    files_preview = ', '.join(existing[:8])
    if len(existing) > 8:
        files_preview += f' ... (+{len(existing)-8} files)'
    print(f'  现有内容: {files_preview}')

    if FORCE:
        confirm = 'y'
    else:
        confirm = input('  清空并重建？[y/N] ').strip().lower()
    if confirm == 'y':
        for item in existing:
            item_path = os.path.join(OUTPUT_DIR, item)
            if item == '.gitignore':
                continue
            if os.path.isfile(item_path) or os.path.islink(item_path):
                os.remove(item_path)
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path)
        print('  已清空。')
    else:
        print('  跳过清空（使用 --force 跳过确认）。')
else:
    print('  已是空目录。')

# 确保子目录存在
os.makedirs(FIG_DIR, exist_ok=True)
os.makedirs(TBL_DIR, exist_ok=True)
print(f'  子目录就绪: figures/ tables/')

# 确保 .gitignore
if not os.path.exists(GITIGNORE):
    with open(GITIGNORE, 'w', encoding='utf-8') as f:
        f.write('# 生成物不提交\n*\n!.gitignore\n')
    print('  已创建 output/.gitignore')

print()

# ====== Step 3: 构建/验证 reference.docx ======
print("[3/5] 构建 reference.docx...")

if KEEP_REFERENCE and os.path.exists(REF_DOCX):
    print(f'  保留现有: {REF_DOCX}')
else:
    # 检查是否需要重新生成
    need_rebuild = not os.path.exists(REF_DOCX)
    if not need_rebuild:
        ref_stat = os.stat(REF_DOCX)
        ref_age_hours = (__import__('time').time() - ref_stat.st_mtime) / 3600
        if ref_age_hours > 168:  # > 1 week
            print(f'  reference.docx 已存在（{ref_age_hours:.0f} 小时前），如格式有变更建议重建。')
            print('  跳过重建（使用 --keep-reference 保留，或删除后重新运行以重建）。')
        else:
            print(f'  reference.docx 已存在且较新（{ref_age_hours:.0f} 小时前），跳过重建。')

    if need_rebuild or (not KEEP_REFERENCE and not os.path.exists(REF_DOCX)):
        build_script = os.path.join(SCRIPT_DIR, 'build_reference.py')
        result = subprocess.run([sys.executable, build_script], capture_output=True, text=True)
        if result.returncode != 0:
            print(f'  [ERROR] 构建失败：\n{result.stderr}')
            sys.exit(1)
        print(f'  [OK] reference.docx 构建完成')

print()

# ====== Step 4: 验证模板样式 ======
print("[4/5] 验证模板完整性...")

try:
    from docx import Document
    doc = Document(REF_DOCX)
    styles_ok = 0
    required_styles = ['Normal', 'Title', 'Heading 1', 'Heading 2', 'Heading 3',
                       'Caption', 'Image Caption', 'Table Caption', 'Bibliography']
    optional_styles = ['Source Code', 'Block Text', 'Compact']
    for sn in required_styles:
        try:
            # By-name lookup via iteration (avoids style_id deprecation warning)
            found = any(s.name == sn for s in doc.styles)
            if found:
                styles_ok += 1
            else:
                print(f'  [WARN] 样式 "{sn}" 缺失 — 运行 build_reference.py 修复')
        except Exception:
            print(f'  [WARN] 样式 "{sn}" 检查失败')
    for sn in optional_styles:
        if any(s.name == sn for s in doc.styles):
            styles_ok += 1

    # 检查 "Table" 表格样式
    from docx.oxml.ns import qn
    import zipfile, xml.etree.ElementTree as ET
    with zipfile.ZipFile(REF_DOCX, 'r') as z:
        styles_xml = z.read('word/styles.xml')
    root = ET.fromstring(styles_xml)
    ns = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
    table_style = root.find(f'.//{{{ns}}}style[@{{{ns}}}styleId="Table"]')
    has_table_style = table_style is not None

    if has_table_style:
        print(f'  [OK] {styles_ok}/{len(required_styles)} 段落样式 + "Table" 表格样式')
    else:
        print(f'  [WARN] {styles_ok}/{len(required_styles)} 段落样式，但 "Table" 表格样式缺失，运行 build_reference.py 修复')
except ImportError:
    print('  [SKIP] python-docx 不可用，无法验证样式')
except Exception as e:
    print(f'  [WARN] 验证失败: {e}')

print()

# ====== Step 5: 项目状态 ======
print("[5/5] 项目状态...")

input_files = [f for f in os.listdir(os.path.join(PROJECT_ROOT, 'input'))
               if os.path.isfile(os.path.join(PROJECT_ROOT, 'input', f))]
print(f'  input/  : {len(input_files)} 个文件 ({", ".join(input_files[:3])}{"..." if len(input_files)>3 else ""})')

output_files = [f for f in os.listdir(OUTPUT_DIR)
                if os.path.isfile(os.path.join(OUTPUT_DIR, f))]
print(f'  output/ : {len(output_files)} 个文件（不含子目录）')
print(f'  figures/: {len(os.listdir(FIG_DIR))} 个文件')
print(f'  tables/ : {len(os.listdir(TBL_DIR))} 个文件')

print()
print("=" * 60)
print("  初始化完成。")
print()
print("  下一步：")
print("  1. 编写 output/model.py（建模求解 + 生成图表）")
print("  2. 运行 python output/model.py 生成图表")
print("  3. 撰写 output/paper.md（论文 Markdown）")
print("  4. 运行 scripts\\convert.bat 生成 paper.docx")
print("=" * 60)
