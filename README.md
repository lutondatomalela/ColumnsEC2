# ColumnsEC2 v0.9 RC26 Modular

**ColumnsEC2** is a reinforced-concrete column analysis and design tool for Eurocode 2 workflows.

This release continues the controlled refactor started in RC9. The calculation behaviour remains aligned with the validated RC8 runtime, while stable import/material utilities and a programmatic API have now been moved into conventional modules.

## Run the application

From the project root:

```powershell
python main.py
```

or:

```powershell
python ColumnsEC2.py
```

or, from the parent folder:

```powershell
python -m columns_ec2
```

## Install dependencies

```powershell
python -m pip install -r requirements.txt
```

For the optional `structuralcodes` calculation engines:

```powershell
python -m pip install --upgrade structuralcodes shapely numpy
```


## RC26 changes

RC26 keeps the RC24/RC25 performance improvements and adds a safe fallback for the false failures produced by the fast reinforcement search.

Main changes:

- when the fast dimensioning mode reports a N-My-Mz failure, the program now launches an automatic fallback search for that physical tramo only;
- the fallback uses the full reinforcement catalogue, including heavier exceptional arrangements, before declaring a real failure;
- false failures of the type `interação N-My-Mz não verificada no modo rápido RC24` are replaced by either a verified adopted solution or by `Sem solução automática verificada após pesquisa rigorosa`;
- each fallback run is isolated in its own design state to avoid accumulated capacity-cache interactions in long projects;
- the normal fast path is preserved for all tramos that already verify, keeping the program responsive;
- result rows include `rc26_rigorous_fallback` and `rc26_layout_tests` for auditability;
- version metadata updated to `v0.9 RC26 Modular`.

Validation with `ESFORCOS_PILARES.csv`:

- 16 388 imported rows;
- 8 194 member/case pairs;
- 241 physical tramos preserved;
- dimensioning test completed in approximately 25 s in the validation environment;
- the previous 14 fast-mode failures were reduced to 1 remaining real automatic-catalogue failure in the validation run.

## RC19 changes

RC19 focuses on constructability-driven reinforcement optimisation. The numerical engine is kept within the validated modular runtime, but the automatic reinforcement catalogue and the column schedule are now more aligned with normal design-office practice.

Main changes:

- rectangular automatic layouts are limited to practical additional face-bar counts;
- long strings such as `10Ø`/`12Ø` distributed along the faces are no longer accepted as normal automatic arrangements;
- face reinforcement remains limited to `Ø10`, `Ø12` and `Ø16`;
- corner/perimeter reinforcement remains limited to `Ø10`, `Ø12`, `Ø16` and `Ø20`;
- the normal automatic catalogue allows at most 8 additional face bars, with not more than 2 additional bars on each individual face;
- the layout score now penalises congestion, high reinforcement ratio, too many small face bars and unnecessary Ø20 corner bars;
- reinforcement arrangements are written explicitly, for example: `4Ø16 corner bars + 1Ø12 on each 25 cm face + 2Ø12 on each 40 cm face`;
- generic wording such as `distributed along the faces` is avoided in the adopted arrangement;
- new constructability fields are added to the schedule: reinforcement ratio, number of additional face bars, constructability class and constructability note;
- if the section would require excessive face reinforcement, the program now recommends increasing the section, reviewing actions/effective lengths, or using a special manual arrangement instead of hiding the issue behind many small bars;
- DXF and Excel exports use the constructability-optimised adopted arrangement.

Additional RC18/RC17 logic retained:

- the summary remains consolidated as one physical segment per `Column line + Storey + Member + Section`;
- local design arrangement and adopted arrangement remain separated;
- vertical rationalisation is still based on a base column-line cage plus local reinforcement;
- circular sections are labelled with `D=...` and drawn as circular sections in DXF.

## Structure

```text
columns_ec2/
├── __main__.py                      # Enables: python -m columns_ec2
├── app_info.py                      # Metadata without loading GUI/runtime
├── api.py                           # Public programmatic API
├── main.py                          # Application entry point
├── gui/                             # GUI facade and app factory
├── core/                            # Stable utilities + calculation facades
├── backends/                        # Backend facades: PT EC2 2010, EC2 2004 SC, EC2 2023 SC, fib MC2010 SC
├── export/                          # Excel, PDF and DXF export facades
├── diagnostics/                     # Backend/scope/performance diagnostics facades
├── resources/                       # PT and EN-UK terminology resources
└── runtime/                         # Ordered validated runtime blocks
```

## Non-GUI smoke test

```powershell
python tools/smoke_test.py
```

Expected result:

```text
ColumnsEC2 RC21 smoke test: OK
```

## Programmatic use

```python
import pandas as pd
from columns_ec2.api import DesignParameters, design_dataframe

input_table = pd.read_excel("my_column_forces.xlsx", dtype=str)
params = DesignParameters(calc_mode="dimensionamento", reduce_cases=True)
results = design_dataframe(input_table, params)
results.to_excel("column_results.xlsx", index=False)
```

## Important note

The `runtime/` directory still executes the validated patch sequence in order. This remains intentional: the objective is to preserve calculation output while moving stable, low-risk code into conventional modules.

The next refactor step should move calculation kernels progressively from `runtime/` into `core/`, starting with:

1. second-order helper functions;
2. detailing checks;
3. shear and torsion checks;
4. serviceability checks;
5. export modules.

Each move should be validated against the same control files.

## Validation target

Compare this RC19 Modular build against RC8/RC9/RC16 using the same test files:

- `CONTROL_EC2_2010_PT.xlsx`
- `TEST_EC2_2004_structuralcodes.xlsx`
- `TEST_EC2_2023_structuralcodes.xlsx`
- `TEST_fibMC_2010_structuralcodes.xlsx`

Key values to compare:

- `N_Ed`, `My,Ed`, `Mz,Ed`
- adopted reinforcement
- `η_NMyMz`
- module status
- Excel/PDF/DXF exports


## RC16 notes

- Automatic catalogue revised for practical building-column detailing:
  - Ø25 and Ø32 remain outside the automatic catalogue;
  - rectangular corner bars use Ø10/Ø12/Ø16/Ø20, with Ø12/Ø16 preferred;
  - face-distribution bars use Ø10/Ø12/Ø16 only;
  - Ø10 main/corner/perimeter bars are discouraged unless the column is small and lightly loaded.
- Candidate generation is now spacing-based, allowing more Ø16 face bars before declaring that no automatic solution is available.
- The column schedule summary is rebuilt as one row per physical segment: Column line + Storey + Member + Section.
- Reinforcement arrangements are rationalised by column line where practical, especially corner/perimeter bars.
- Failure messages now distinguish real design limitations from automatic-catalogue limits.
- Numerical resistance equations remain aligned with RC16; the changes affect candidate generation, layout ranking and schedule rationalisation.

## RC19 notes

- Replaced the aggressive RC17 vertical propagation with a balanced column-line rationalisation.
- The schedule now uses a base column-line cage plus local additional reinforcement, instead of copying the full upper-storey arrangement to all lower storeys.
- Principal/corner/perimeter bars are rationalised first; face-distribution bars remain local unless full propagation is proportionate.
- Full upper-storey reinforcement is not propagated when the increase in adopted reinforcement would be disproportionate.
- Ø10 is restricted as a principal/corner/perimeter bar; Ø12 is the preferred practical minimum except for small and lightly loaded columns.
- Added reporting fields for base cage, local additional reinforcement and over-reinforcement percentage.
- The physical-segment schedule is rebuilt as one row per Column line + Storey + Member + Section.


## RC26 — desempenho

- Redução rápida por tramo físico: por defeito, o programa escolhe 1 caso ELU governante por `member + prumada + piso + secção/material`.
- A tabela completa permanece disponível para ELS e auditoria.
- Para a tabela `ESFORCOS_PILARES.csv`: 8194 pares member/case → 241 casos de cálculo, preservando os 241 tramos físicos.
- `COLUMNSEC2_RC24_CASES_PER_TRAMO=3` permite manter até 3 casos governantes por tramo para verificação mais conservadora, com maior tempo de cálculo.
- Modo Dimensionamento usa pesquisa rápida RC26 de armaduras, evitando a pesquisa exaustiva de normal shortlist; fallback checks up to 100 catalogue layouts by default por caso.
