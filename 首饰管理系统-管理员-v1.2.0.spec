# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['Jewelry_Management_System.py'],
    pathex=[],
    binaries=[],
    datas=[('Jewelry_images', 'Jewelry_images'), ('resources', 'resources'), ('Jewelry_Management_System.db', '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='首饰管理系统-管理员-v1.2.0',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='首饰管理系统-管理员-v1.2.0',
)
