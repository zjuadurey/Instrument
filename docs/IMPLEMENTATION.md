# Implementation notes

## Supported contract

Input is a finite JSON IR. The full-map oracle is limited to 3 qubits by default. The checker handles the listed local rules and complete classical renaming, but not quantum wire permutations, general phi nodes, procedure summaries, arbitrary CFGs, or witness-preserving minimization. A compiler-under-test callback must preserve or explicitly adapt the declared JSON interface. The included injected fault is a test fixture, not a discovered bug in an external compiler.

## Reproducibility

This release was implemented from the algorithm descriptions in the supplied PDF. It is a new implementation; it is not the original code or logs used to produce any pre-existing experimental results. The included microbenchmarks use generated, deterministic inputs, and their outputs are recorded separately from any published results.

Input schemas are demonstrated by the JSON fixtures in `examples/` and validated before analysis. Unsupported operations produce errors. Quantum wire zero is the most significant tensor factor. Quantum inputs in the oracle range over the entire operator basis, so validation is not limited to an all-zero or product input state.

## Guarantees and validation

Passing tests is evidence about the tested implementation, not a machine-checked proof of the general mathematical claims. Symbolic identities use exact SymPy arithmetic. Numerical comparisons report maximum entrywise residuals with a declared tolerance; they are not exact certificates or diamond-norm bounds. The fixed-family statistical path checks only declared classical output categories and never establishes universal equivalence from a lack of alarms.

Inverse-pair insertion, disjoint gate swaps, diagonal-before-measurement witnesses with dead-wire checks, complete classical SSA renaming, cp/inst/eff modes, operator-basis validation, a compiler callback, injected-fault examples, and fixed-sample family-wise error budgeting.

## Development

`python -m pytest -q` runs regression checks. `python benchmarks/microbench.py` regenerates the committed measurements and figures. Keep raw measurements, code changes, and figures in the same commit when updating the evaluation.
