# ColumnsEC2

**ColumnsEC2** is a Python tool for the analysis and design of reinforced-concrete columns according to **Eurocode 2 / NP EN 1992-1-1**.

The program imports column internal forces, performs reinforced-concrete checks under combined axial force and biaxial bending, proposes practical reinforcement arrangements, and exports calculation reports in Excel, PDF, and DXF formats.

> Current development status: **v0.9 RC26 Modular**  
> The software is under active validation and should be used with engineering review.

---

## Main features

- Import of column force tables from Excel or CSV.
- Robust CSV reader for UTF-16, UTF-8, semicolon-separated and comma-separated files.
- Extraction of `member`, `node`, and `case` from force-table identifiers such as `Barra/Nó/Caso`.
- Verification of physical column segments by:
  - member;
  - column line;
  - storey;
  - section;
  - material.
- N-My-Mz interaction check for reinforced-concrete columns.
- Reinforcement proposal using practical bar arrangements.
- Stack-level reinforcement rationalisation by column line.
- Support for rectangular and circular sections.
- Serviceability check using a selected SLS combination when available.
- Shear and torsion diagnostic checks.
- Optional use of the `structuralcodes` Python library for selected Eurocode/material calculation utilities and cross-check workflows.
- Export to:
  - `.xlsx` calculation workbook;
  - `.pdf` calculation report;
  - `.dxf` column reinforcement schedule.

---

## Intended use

ColumnsEC2 is intended for preliminary and detailed checking workflows in building-column design, especially when internal forces are exported from structural analysis software.

The tool is particularly focused on:

- preserving all physical column segments;
- avoiding premature grouping by column name only;
- selecting governing combinations per physical segment;
- rationalising reinforcement along the same column stack;
- avoiding impractical automatic reinforcement layouts.

---

## Engineering basis

The main design workflow is based on:

- Eurocode 2: EN 1992-1-1;
- Portuguese National Annex where applicable;
- reinforced-concrete column checks under axial force and biaxial bending;
- practical reinforcement detailing limits;
- selected calculation utilities from the open-source `structuralcodes` Python library, where available in the active backend.

The internal EC2 routines remain the primary workflow for ColumnsEC2. `structuralcodes` is used as an optional support/cross-check dependency in specific calculation paths and should not be interpreted as replacing project-specific engineering validation.

The program does not replace engineering judgement. Final design decisions, detailing, anchorage, lap lengths, execution constraints, and project-specific assumptions must be reviewed by a qualified structural engineer.

---

## Installation

Clone the repository:

```bash
git clone https://github.com/lutondatomalela/ColumnsEC2.git
cd ColumnsEC2
```

Create and activate a Python environment:

```bash
python -m venv .venv
```

On Windows:

```bash
.venv\Scripts\activate
```

On Linux/macOS:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Optional `structuralcodes` support:

```bash
python -m pip install --upgrade structuralcodes shapely numpy
```

`structuralcodes` is optional but recommended when using the alternative/checking backends that rely on it.

---

## External calculation libraries

ColumnsEC2 includes its own calculation workflow for EC2 column design, but it can also use the open-source `structuralcodes` Python library in selected backend/cross-check routines.

This is useful for:

- comparing material-property calculations;
- checking selected Eurocode expressions;
- supporting alternative backend experiments;
- keeping parts of the calculation workflow aligned with an external open-source engineering library.

Results obtained through any backend must still be reviewed by a qualified structural engineer.

## Running the application

From the project root:

```bash
python main.py
```

or:

```bash
python ColumnsEC2.py
```

or as a module:

```bash
python -m columns_ec2
```

---

## Input data

The program accepts Excel and CSV force tables.

A typical CSV input may include a column such as:

```text
Barra/Nó/Caso
```

with values like:

```text
119/ 24/ 101 (C)
```

which are parsed as:

```text
member = 119
node   = 24
case   = 101
```

The expected force-table workflow preserves simultaneous action effects from the same member, node and load case. The program should not combine independent envelopes of `N`, `My`, and `Mz` from different cases.

---

## Reference validation dataset

The current validation dataset used during RC23-RC26 development is:

```text
tests/data/ESFORCOS_PILARES.csv
```

Expected import result:

```text
Input rows:              16 388
Member/case pairs:        8 194
Physical column segments:   241
Column lines:                 84
SLS combination 302: detected
```

Any future change to the import, case-reduction or design pipeline should preserve these values unless the input dataset changes.

---

## Calculation workflow

The intended design pipeline is:

```text
1. Read Excel/CSV force table.
2. Parse member, node and case.
3. Preserve all physical column segments.
4. Select governing cases per physical segment.
5. Design/check each segment locally.
6. Apply reinforcement rationalisation by column line.
7. Separate local required reinforcement from adopted stack reinforcement.
8. Export Excel, PDF and DXF reports.
```

Grouping only by column name before local design is not acceptable, because it may collapse different storeys or physical members into a single result.

---

## Outputs

ColumnsEC2 can generate:

- detailed Excel calculation workbook;
- PDF calculation report;
- DXF column reinforcement schedule;
- diagnostic tables for governing combinations, failures, warnings, serviceability and detailing.

The DXF export is intended to include all column lines, using paginated schedule blocks when required.

---

## Non-GUI smoke test

Run:

```bash
python tools/smoke_test.py
```

Expected result:

```text
ColumnsEC2 smoke test: OK
```

---

## Programmatic use

```python
import pandas as pd
from columns_ec2.api import DesignParameters, design_dataframe

input_table = pd.read_excel("column_forces.xlsx", dtype=str)

params = DesignParameters(
    calc_mode="dimensionamento",
    reduce_cases=True,
)

results = design_dataframe(input_table, params)

results.to_excel("column_results.xlsx", index=False)
```

---

## Performance notes

For large models, the program reduces the force table to governing design cases per physical column segment.

The RC26 workflow keeps the fast search mode for ordinary cases and activates a rigorous fallback search only when the fast reinforcement search fails.

For additional conservative checks, the number of governing cases per physical segment may be increased through the relevant runtime setting.

---

## Development status

ColumnsEC2 is currently in release-candidate development.

Recent focus areas:

- robust CSV import;
- UTF-16 and BOM handling;
- preservation of all physical column segments;
- ELS combination detection;
- faster governing-case reduction;
- practical reinforcement layouts;
- stack-level reinforcement rationalisation;
- stable Excel/PDF/DXF exports.

Known validation target for RC26:

```text
241 physical column segments preserved
84 column lines exported to DXF
SLS case 302 detected and evaluated
No artificial failures with empty As or empty utilisation ratio
No "nan" or "None" text in final reports
```

---

## Limitations

The current version should be treated as an engineering-assistance tool, not as an autonomous design authority.

The following items require engineering review:

- second-order effects assumptions;
- effective lengths;
- sway/non-sway classification;
- reinforcement anchorage and lap lengths;
- seismic detailing requirements, where applicable;
- fire design;
- local discontinuities;
- construction-stage effects;
- final reinforcement detailing.

---

## Disclaimer

This software is provided for structural engineering calculation assistance and research/development purposes.

The author accepts no responsibility for direct or indirect consequences resulting from the use of the software. All results must be independently reviewed and validated by a qualified structural engineer before being used in design, construction documentation, checking, or approval processes.

---

## License

This project is licensed under the MIT License. See the [`LICENSE`](LICENSE) file for details.

---

## Author

Developed by **Eng.º Lutonda Tomalela**.

Repository:

```text
https://github.com/lutondatomalela/ColumnsEC2
```
