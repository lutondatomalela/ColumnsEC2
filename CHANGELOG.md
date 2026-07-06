# Changelog

All notable development changes to ColumnsEC2 are summarised in this file.

The project is currently in release-candidate development. Numerical and detailing changes should be validated against controlled input files before being used in production workflows.

---

## v0.9 RC26

- Added rigorous reinforcement-search fallback when the fast automatic design mode fails.
- Reduced false `N-My-Mz` failures caused by limited fast-mode reinforcement catalogues.
- Preserved the performance improvements introduced in RC24 and RC25.
- Added fallback audit fields, including fallback activation and number of tested layouts.
- Improved distinction between real structural failures and automatic-catalogue limitations.
- Maintained the physical-segment preservation workflow for large imported force tables.

## v0.9 RC25

- Reworked PDF export through a direct final report routine.
- Reworked DXF column schedule export for more stable output generation.
- Improved report text sanitisation to avoid `nan`, `None` and similar artefacts.
- Improved PDF text compatibility for reinforcement notation.
- Kept the large-table performance improvements from RC24.

## v0.9 RC24

- Improved governing-case reduction for large force tables.
- Reduced excessive runtime during automatic column design.
- Preserved physical column segments during case reduction.
- Added performance-oriented design pathways while maintaining traceability of imported actions.

## v0.9 RC23

- Improved CSV import for UTF-16 encoded files.
- Fixed BOM handling in imported headers.
- Improved parsing of `Barra/Nó/Caso` identifiers.
- Correctly extracted member, node and load case from combined identifier fields.
- Improved detection of serviceability combinations in imported force tables.

## v0.9 RC22

- Improved CSV import robustness.
- Improved DXF schedule generation.
- Continued work on preserving all physical column segments during import and reduction.

## v0.9 RC21

- Introduced column-line reinforcement rationalisation logic.
- Improved separation between local design requirements and stack-level adopted reinforcement.
- Identified the need to preserve physical segments before any column-line consolidation.

## v0.9 RC20

- Fixed recursive wrapper behaviour in the runtime patch sequence.
- Resolved `maximum recursion depth exceeded` errors caused by circular aliasing between runtime functions.

## v0.9 RC19

- Improved constructability-driven reinforcement optimisation.
- Restricted impractical automatic arrangements with excessive small bars distributed along faces.
- Improved reinforcement arrangement descriptions for Excel and DXF output.
- Added constructability-related schedule fields.

## v0.9 RC16 to RC18

- Improved automatic reinforcement catalogue generation.
- Improved rectangular and circular section scheduling.
- Added rationalisation fields for base cage, local additional reinforcement and adopted arrangement.
- Improved distinction between automatic-catalogue limitations and actual design limitations.
