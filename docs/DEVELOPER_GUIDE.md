# Developer guide — ColumnsEC2 RC14

## Refactor rule

Do not change calculation logic and architecture in the same commit/release. Move one block at a time, then compare outputs against the control workbooks.

## Current state

- GUI: still loaded from the validated runtime.
- Main design engine: still loaded from the validated runtime.
- Stable utilities: moved to `core/utils.py`, `core/materials.py`, `core/import_data.py`.
- Public API: available in `columns_ec2/api.py`.

## Recommended next extraction order

1. `order_end_moments_ec2`, `lambda_lim_ec2_practical` → `core/second_order.py`.
2. `detailing_check_v4` → `core/detailing.py`.
3. `shear_check_ec2_v4` and `torsion_check_ec2_v4` → `core/shear.py` and `core/torsion.py`.
4. `elastic_service_check_v4` → `core/serviceability.py`.
5. Excel/PDF/DXF writers → `export/`.

## Validation after each extraction

Run the same input table through both versions and compare:

- number of analysed cases;
- selected reinforcement;
- `eta_NMyMz` / `η_NMyMz`;
- global/module status;
- failure/warning counts.
