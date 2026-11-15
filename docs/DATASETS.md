# Dataset Policy

## Dataset classes

### Smoke fixtures

`datasets/smoke/` contains repository-owned fixtures that verify the benchmark
runner, patch replay, and regression checks. Smoke results are not Bugfix Agent
benchmark scores.

### Bugfix-v1

`datasets/bugfix-v1/` contains three original, repository-owned source
fixtures with a reproducible failing test, passing regression tests, and a
protected `tests/` directory per case. These cases are scored by
`src/bugfix_benchmark/verifier.py`, not by the SWE-bench harness. Keep
Bugfix-v1 scores separate from official SWE-bench results. Case descriptions,
scope, and limitations are in `datasets/bugfix-v1/README.md`.

### SWE-bench Lite

`datasets/swe-bench-lite/` stores selected `instance_id` values from the
official SWE-bench Lite test split. Case records are downloaded at runtime from:

- Dataset: <https://huggingface.co/datasets/SWE-bench/SWE-bench_Lite>
- Harness: <https://github.com/SWE-bench/SWE-bench>

The public repository does not copy upstream gold patches, test patches, or
source repositories. Their licenses and usage terms remain governed by their
respective upstream projects.

`sample-10.txt` and `sample-30.txt` are integration selections. They do not
represent the full SWE-bench Lite suite and must not be reported as official
leaderboard scores. `scripts/fetch_swe_bench.py --all` downloads the complete
300-case test split into the ignored `.benchmark/` directory.

`full-300.txt` freezes the complete Lite `test` ID set for official comparison.
`screened-v2.txt` is an 84-case **provisional** diagnostic pool produced by
`scripts/build_swe_lite_selection.py`; `reviewed-v2.txt` currently contains
the same 84 IDs. `case-inventory-v2.jsonl` gives a selection or hold reason
for every one of the 300 upstream cases: 84 paper-reviewed inclusions,
33 review holds, and 183 rule-based exclusions that have not been individually
reviewed. Some included records still flag target-test assertion checks.
The [dataset README](../datasets/swe-bench-lite/README.md) defines the rules,
provenance, distribution, and reporting limits. Neither the 84-case pool nor
the older seven-case set can be compared as a Lite leaderboard result.

`diagnostic-v1.txt` is a separate seven-case capability-oriented selection.
Its reviewed labels and inference limits are in `diagnostic-v1.jsonl`; the
[dataset README](../datasets/swe-bench-lite/README.md) gives the runnable flow.
Only official SWE-bench harness results may be used for its score breakdown.
Core cases and issue-information controls must be reported separately. This
selection does not replace or approximate the full 300-case leaderboard.

`original-cases.txt` is a separate research selection of three upstream cases.
The [survey](BUGFIX_DATASET_SURVEY.md) records their repository context,
defect mechanism, capability hypotheses, and limits of those interpretations.
The selection is not an independently reproduced or statistically representative
Bugfix benchmark; it uses the same official-data acquisition path as other
SWE-bench Lite selections.

### Cross-source case research

[The multi-source selection rationale](MULTI_SOURCE_SELECTION.md) compares
the construction goals of issue-to-patch, historical bug-pair, CI-derived,
and specialized benchmark sources. The case-candidates.jsonl file under
datasets/cross-source records evidence and selection purposes for the first
candidates. This is a research inventory, not a runnable manifest or a scored
dataset: no case has yet passed source-specific historical baseline and
reference-fix replay.

The [scenario-oriented candidate design](SCENARIO_BENCHMARK_DESIGN.md)
reorganizes the research inventory by defect mechanism, task span, and
operational context. Its 176-case pool includes 84 existing Lite paper reviews
and external metadata-screened records; no case is promoted to a cross-source
scored suite by that expansion. The `long_task_proxy` label is based on
reference-patch file count and issue length, not a validated Agent horizon.

## Reproducibility requirements

Every public evaluation set must record:

1. dataset name, version, and provenance (upstream or repository-owned);
2. stable case identifiers and source revision or committed fixture version;
3. failing and passing baseline checks;
4. protected paths and independent scoring rules;
5. acquisition script when cases are downloaded from upstream;
6. scorer or official harness version used for the run.

Generated datasets, cloned repositories, predictions, logs, and scores belong
under `.benchmark/` or `results/` and are not committed.

## Adding another dataset

Add a directory under `datasets/` with a README describing provenance. For
repository-owned cases, commit minimal source fixtures and tests; for upstream
cases, keep selection metadata here and add a deterministic acquisition script
under `scripts/`. Keep dataset-specific grading separate from Agent invocation.
