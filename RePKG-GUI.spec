# -*- mode: python ; coding: utf-8 -*-
"""
RePKG-GUI PyInstaller 打包配置
onefile 模式 — 生成单个 EXE，数据文件（templates/static/config.json）随 build.bat 手动布置
"""
import os
import sys

ROOT = os.path.abspath(SPECPATH)
APP_NAME = 'RePKG-GUI'
APP_VERSION = '1.1.0'

# ---- 隐藏导入（PyInstaller 无法自动检测的模块） ----
hiddenimports = [
    'flask',
    'flask.json',
    'werkzeug',
    'jinja2',
    'jinja2.ext',
    'markupsafe',
    'webview',
    'webview.platforms',
    'webview.platforms.winforms',
    'webview.platforms.edgechromium',
    'webview.http',
    'webview.js',
    'webview.menu',
    'bottle',
    'clr',
    'backend',
    'backend.api',
    'backend.config',
    'backend.executor',
    'backend.scanner',
    'backend.server',
    'backend.steam',
    'backend.paths',
    'json',
    'urllib',
    'shutil',
    'subprocess',
    'threading',
    'socket',
]

# ---- 排除模块 ----
excludes = [
    'tkinter',
    'unittest',
    'test',
    'pytest',
    'setuptools',
    'pip',
    'xml',
    'pdb',
    'profile',
    'cProfile',
]

a = Analysis(
    ['app.py'],
    pathex=[ROOT],
    binaries=[],
    datas=[],           # 数据文件由 build.bat 手动复制
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(ROOT, 'static', 'assets', 'images', 'icon.ico'),
)
