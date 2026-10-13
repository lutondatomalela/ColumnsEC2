# Windows portable distribution

Use 64-bit Python 3.12 on Windows. Install requirements.txt, requirements-optional.txt and PyInstaller, then run:

```powershell
python -m PyInstaller --clean --noconfirm ColumnsEC2.spec
```

The complete dist/ColumnsEC2 folder must be distributed together. Start ColumnsEC2.exe.
The specification includes all 23 runtime source blocks in their original order and explicitly collects dependencies that static import analysis cannot see.

The Windows portable build workflow checks source calculations, compiles on Windows and launches the packaged application for a runtime/calculation/Tkinter check. It uploads a portable ZIP artifact; it does not publish a release.

Before publishing a release, manually verify CSV/XLSX import, project calculations and Excel/PDF/DXF exports on Windows.
Build success is not validation of structural design results.
The private project CSV used for local verification is not included in the distribution.
