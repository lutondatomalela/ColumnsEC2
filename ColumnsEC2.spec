# PyInstaller specification: run from the repository root.
from pathlib import Path
from PyInstaller.utils.hooks import collect_all
root = Path(SPECPATH)
import base64
icon_path = root / 'build' / 'ColumnsEC2.ico'
icon_path.parent.mkdir(parents=True, exist_ok=True)
icon_path.write_bytes(base64.b64decode((root / 'assets/ColumnsEC2.ico.b64').read_text()))
datas = [(str(root / "columns_ec2" / "runtime" / name), "columns_ec2/runtime")
         for name in __import__("runpy").run_path(str(root / "columns_ec2/runtime/manifest.py"))["RUNTIME_MODULES"]]
datas.append((str(icon_path), 'columns_ec2/gui'))
binaries = []
hiddenimports = ["tkinter", "tkinter.ttk", "tkinter.filedialog", "tkinter.messagebox", "tkinter.simpledialog"]
for package in ("pandas", "numpy", "openpyxl", "reportlab", "shapely", "structuralcodes"):
    package_datas, package_binaries, package_imports = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_imports
a = Analysis([str(root / "tools/windows_entry.py")], pathex=[str(root)], binaries=binaries,
             datas=datas, hiddenimports=hiddenimports, hookspath=[], runtime_hooks=[], excludes=[])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="ColumnsEC2", debug=False,
          bootloader_ignore_signals=False, strip=False, upx=False, console=False, icon=str(icon_path))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="ColumnsEC2")
