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
- practical reinforcement detailing limits.

The program does not replace engineering judgement. Final design decisions, detailing, anchorage, lap lengths, execution constraints, and project-specific assumptions must be reviewed by a qualified structural engineer.

---

## Installation

Clone the repository:

```bash
git clone https://github.com/lutondatomalela/ColumnsEC2.git
cd ColumnsEC2
