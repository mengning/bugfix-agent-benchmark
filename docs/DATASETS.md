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
