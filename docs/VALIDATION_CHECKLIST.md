# Validation checklist

Use this checklist before tagging any modular release as stable.

## Input parsing

- [ ] Excel import works.
- [ ] Copy/paste import works.
- [ ] Decimal comma is parsed correctly.
- [ ] `Story`, `Storey`, `Piso`, `Floor`, `Level` are recognised.
- [ ] Two-node member/case pairs are reconstructed correctly.

## Default Portuguese engine

- [ ] Same governing cases as RC8/RC9.
- [ ] Same design actions.
- [ ] Same adopted reinforcement for control cases.
- [ ] Same global and module status.

## structuralcodes engines

- [ ] EC2 2004 runs.
- [ ] EC2 2023 runs.
- [ ] fib Model Code 2010 runs.
- [ ] Unavailable API modules are reported as unavailable, not as design failures.

## Exports

- [ ] Excel workbook opens without repair.
- [ ] PDF report exports in PT.
- [ ] PDF report exports in EN-UK.
- [ ] DXF column schedule preserves column line/storey ordering.
- [ ] Repository hyperlink is embedded in the programme name where supported.
