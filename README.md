# ColumnsEC2

**ColumnsEC2** is a Python-based tool for the analysis and design of reinforced-concrete columns in accordance with **Eurocode 2** workflows, with particular focus on **EN 1992-1-1 / NP EN 1992-1-1** applications.

The software imports column internal forces, preserves physical column segments, checks combined axial force and biaxial bending, proposes practical reinforcement arrangements, and exports calculation outputs to Excel, PDF and DXF formats.

> Current development status: **v0.1**  
> ColumnsEC2 is under active validation and should be used with independent engineering review.

---

## Main features

- Import of column force tables from Excel and CSV files.
- Robust CSV handling for UTF-8, UTF-16, BOM-marked files, semicolon-separated tables and decimal-comma formats.
- Extraction of `member`, `node` and `case` from identifiers such as `Barra/Nó/Caso`.
- Preservation of physical column segments by member, column line, storey, section and material.
- Design and verification of reinforced-concrete columns under combined `N-My-Mz` effects.
- Practical reinforcement proposal for rectangular and circular sections.
- Reinforcement rationalisation by column stack, after local segment verification.
- Serviceability, shear, torsion and detailing diagnostic checks.
- Export of calculation results to:
  - Excel workbook;
  - PDF calculation report;
  - DXF column reinforcement schedule.
- Optional integration with the `structuralcodes` library for selected external calculation backends and cross-check routines.

---

## Intended use

ColumnsEC2 is intended to support reinforced-concrete column design workflows in structural engineering offices, particularly where internal forces are exported from structural analysis software.

The tool is focused on:

- maintaining the traceability of simultaneous design actions;
- avoiding premature grouping of different physical column segments;
- selecting governing design cases per segment;
- proposing constructible reinforcement arrangements;
- rationalising reinforcement by column line without losing local design requirements;
- producing clear calculation records for engineering review.

---

## Engineering basis

The core workflow is based on reinforced-concrete column design principles from Eurocode 2, with emphasis on:

- axial force and biaxial bending interaction;
- material design strengths;
- reinforcement limits;
- practical detailing constraints;
- segment-by-segment design verification;
- column-stack reinforcement rationalisation.

The main reference framework is **EN 1992-1-1 / NP EN 1992-1-1**, including the Portuguese National Annex where applicable.

The software does not replace the judgement of the responsible structural engineer. Final design assumptions, second-order effects, effective lengths, detailing, laps, anchorage, seismic requirements, fire design and execution constraints must be reviewed independently.

---

## External calculation libraries

ColumnsEC2 also uses, or can interface with, the open-source **`structuralcodes`** Python library for selected calculation support and comparison workflows.

Depending on the active backend and runtime configuration, `structuralcodes` may be used for auxiliary checks, alternative code-format calculations or cross-checking routines, for example related to:

- Eurocode 2 calculation expressions;
- alternative EC2-generation backends exposed by the software;
- fib Model Code 2010 comparison workflows, where available;
- independent verification of selected material or section-related calculations.

The internal ColumnsEC2 workflow remains the main calculation route for the standard Portuguese EC2 column-design process unless another supported backend is explicitly selected.

To install the optional external calculation dependencies:

```bash
python -m pip install --upgrade structuralcodes shapely numpy
```

---

## Installation

Clone the repository:

```bash
git clone https://github.com/lutondatomalela/ColumnsEC2.git
cd ColumnsEC2
```

Create a Python virtual environment:

```bash
python -m venv .venv
```

Activate the environment.

On Windows:

```bash
.venv\Scripts\activate
```

On macOS or Linux:

```bash
source .venv/bin/activate
```

Install the project dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Optional external calculation libraries:

```bash
python -m pip install --upgrade structuralcodes shapely numpy
```

---

## Running the application

From the project root:

```bash
python main.py
```

or:

```bash
python ColumnsEC2.py
```

or as a Python module:

```bash
python -m columns_ec2
```

---

## Input data

ColumnsEC2 accepts Excel and CSV force tables. A typical imported table may include an identifier column such as:

```text
Barra/Nó/Caso
```

with values such as:

```text
119/ 24/ 507 (C)
```

which are interpreted as:

```text
member = 119
node   = 24
case   = 507
```

The design workflow should preserve simultaneous action effects from the same member, node and load case. Independent envelopes of axial force and bending moments should not be combined as if they were simultaneous.

For physical segment identification, the recommended grouping basis is:

```text
member + column line + storey + section + material
```

Grouping by column name only is not sufficient, because it may collapse different storeys, members or section changes into a single design result.

---

## Calculation workflow

The intended calculation sequence is:

```text
1. Import force tables from Excel files, CSV files, or directly from the clipboard.
2. Parse member, node and load case.
3. Preserve all physical column segments.
4. Select governing design cases per physical segment.
5. Design or check each segment locally.
6. Apply reinforcement rationalisation by column line.
7. Separate local required reinforcement from adopted stack reinforcement.
8. Export Excel, PDF and DXF outputs.
```

The workflow keeps a fast design path for ordinary cases and activates a more rigorous reinforcement search only when the fast automatic search fails.

---

## Outputs

ColumnsEC2 can generate:

- detailed Excel calculation workbook;
- PDF calculation report;
- DXF column reinforcement schedule;
- diagnostic tables for governing combinations, failures, warnings, serviceability and detailing checks.

The DXF export is intended to include all column lines in the project. When required, the schedule should be organised in multiple blocks or pages rather than omitting columns.

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

## Development status

ColumnsEC2 is currently in release-candidate development.

Recent development areas include:

- robust CSV import and encoding detection;
- preservation of physical column segments;
- governing-case reduction for large force tables;
- serviceability-combination detection;
- practical automatic reinforcement layouts;
- column-stack reinforcement rationalisation;
- stable Excel, PDF and DXF export routines;
- optional external backend support through `structuralcodes`.

See [`CHANGELOG.md`](CHANGELOG.md) for release-candidate history.

---

## Limitations

ColumnsEC2 should be treated as an engineering-assistance tool, not as an autonomous design authority.

The following items require project-specific engineering review:

- design assumptions and load combinations;
- second-order effects;
- effective lengths;
- sway or non-sway classification;
- minimum eccentricities;
- creep and long-term effects;
- reinforcement anchorage and lap lengths;
- seismic detailing requirements;
- fire design;
- local discontinuities and construction-stage effects;
- final reinforcement drawings and execution details.

---

## Disclaimer

This software is provided for structural engineering calculation assistance, research and development purposes.

The author accepts no responsibility for direct or indirect consequences resulting from the use of the software. All results must be independently reviewed and validated by a qualified structural engineer before being used for design, construction documentation, checking, approval or execution.

---

## Author

Developed by **Eng.º Lutonda Tomalela**.

Repository: <https://github.com/lutondatomalela/ColumnsEC2>
