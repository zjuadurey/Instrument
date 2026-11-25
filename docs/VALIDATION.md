# Validation

Validated on 2026-11-24 with Python 3.12.14.

- Pytest: **13 passed**, zero failures or errors.
- Built and installed the package as a wheel.
- Ran the documented CLI example from outside the source directory.
- Ran the functional microbenchmark and generated JSON, PNG, and SVG outputs.
- Checked the generated figures and their data files.

The detailed test report is in `results/tests.xml`; the machine-readable summary is in `results/validation.json`. `requirements-validated.txt` records the complete validation environment, including transitive dependencies. These checks concern the bounded implementation and included fixtures. No quantum-hardware experiment or large-scale result reproduction was performed.
