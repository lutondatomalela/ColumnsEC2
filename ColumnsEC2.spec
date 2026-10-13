# PyInstaller specification: run from the repository root.
from pathlib import Path
from PyInstaller.utils.hooks import collect_all
root = Path(SPECPATH)
datas = [(str(root / "columns_ec2" / "runtime" / name), "columns_ec2/runtime")
         for name in __import__("runpy").run_path(str(root / "columns_ec2/runtime/manifest.py"))["RUNTIME_MODULES"]]
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
          bootloader_ignore_signals=False, strip=False, upx=False, console=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="ColumnsEC2")
