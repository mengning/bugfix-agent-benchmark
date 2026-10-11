# Dataset Policy

## Dataset classes

### Smoke fixtures

`datasets/smoke/` contains repository-owned fixtures that verify the benchmark
runner, patch replay, and regression checks. Smoke results are not Bugfix Agent
benchmark scores.

### SWE-bench Lite

`datasets/swe-bench-lite/` stores selected `instance_id` values from the
official SWE-bench Lite test split. Case records are downloaded at runtime from:

- Dataset: <https://huggingface.co/datasets/SWE-bench/SWE-bench_Lite>
- Harness: <https://github.com/SWE-bench/SWE-bench>

The public repository does not copy upstream gold patches, test patches, or
source repositories. Their licenses and usage terms remain governed by their
respective upstream projects.

`sample-10.txt` is an integration sample across ten upstream repositories. It
does not represent the full SWE-bench Lite suite and must not be reported as an
official leaderboard score.

## Reproducibility requirements

Every public evaluation set must record:

1. upstream dataset name and split;
2. immutable case identifier;
3. repository and base commit supplied by the upstream dataset;
4. acquisition script;
5. scorer or official harness version used for the run.

Generated datasets, cloned repositories, predictions, logs, and scores belong
under `.benchmark/` or `results/` and are not committed.

## Adding another dataset

Add a directory under `datasets/` containing only selection metadata and a
README describing provenance. Add a deterministic acquisition script under
`scripts/`. Keep dataset-specific grading separate from Agent invocation.
