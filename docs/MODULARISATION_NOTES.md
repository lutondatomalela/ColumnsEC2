# Modularisation notes

This is a controlled refactor.

## What changed

- The original single-file RC8 source was split into ordered runtime modules.
- Public import boundaries were added for `core`, `gui`, `backends`, `export`, `diagnostics` and `resources`.
- The launchers `main.py` and `ColumnsEC2.py` now call the package entry point.

## What did not change

- Calculation logic.
- Backend behaviour.
- GUI workflow.
- Excel, PDF and DXF export logic.

## Why the runtime folder still exists

The historic file was built as a sequence of patches. Moving everything into conventional imports in one step would risk changing behaviour. The runtime folder preserves the exact execution order while the project gains an organised package structure.

## Recommended next steps

1. Move pure utility functions to `core/utils.py`.
2. Move material functions to `core/materials.py`.
3. Move import/parsing functions to `core/import_data.py`.
4. Move PDF/XLSX/DXF exporters to `export/`.
5. Move EN-UK/PT dictionaries fully to `resources/`.
6. Validate numerical equality after each step.
