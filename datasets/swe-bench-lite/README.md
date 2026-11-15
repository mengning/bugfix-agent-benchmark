# SWE-bench Lite

## Two evaluation layers

This repository has two evaluation layers represented by three runnable ID
files from the official Lite `test` split:

| Layer | File | Size | What it can support |
| --- | --- | ---: | --- |
| Standard comparison | `full-300.txt` | 300 | The complete official Lite denominator, when every patch is generated and graded by the official harness. |
| Diagnostic selection | `screened-v2.txt` | 84 | Case-reviewed pool for diagnostic experiments; **not** an official leaderboard score or a verified Bugfix-only suite. |
| Diagnostic selection (reviewed alias) | `reviewed-v2.txt` | 84 | The same IDs in the same order; retained as an explicit paper-review entry point. |

The 300 IDs were frozen from the upstream Lite `test` records downloaded on
2026-10-21. The ignored source file used here was
`.benchmark/datasets/swe-bench-lite-all.jsonl` (SHA-256
`33cdcfe52d3e374ddd147cf7f5ab931db5c51579b8c873748955078db93016c8`).
Download them again from the [official dataset](https://huggingface.co/datasets/SWE-bench/SWE-bench_Lite)
with `python3 scripts/fetch_swe_bench.py --all` before a new run; record the
upstream revision and harness version with the result.

`case-inventory-v2.jsonl` records an entry for **all 300** cases, including
why each was selected or held. Its fields track the four research dimensions:
repository context, repair obstacle, issue information, and verification
evidence. `repair_obstacle: null` deliberately means **not yet reviewed**;
the script does not infer semantic difficulty from keywords. The `review_status`
field distinguishes seven earlier paper-screened examples, 77 newly reviewed
inclusions, zero cases left at surface screening only, and 33 review holds.
No case has been claimed as independently reproduced here. The earlier seven
are detailed in `diagnostic-v1.jsonl`; 110 additional decisions, including
holds, are recorded in `case-reviews-v2.jsonl`.

The surface screen requires upstream target and regression tests, symptom and
reproduction wording in the Issue, and no feature-request wording at the start
of the title. It also honors documented manual holds. This is a **triage rule**,
not proof that the task is a Bugfix, that tests align with the Issue, or that
the historical environment is reproducible. Across the 300 records, 84 are
paper-reviewed and selected; 33 were held after review. The other 183 have
rule-based exclusion reasons in the inventory, not Agent failure statuses.
Those 183 were not individually paper-reviewed. The 84 include 25 Django and 9 SymPy
tasks; report repository distribution
alongside any diagnostic result rather than implying a balanced sample.

Regenerate and check the selection from downloaded official records:

```bash
python3 scripts/build_swe_lite_selection.py \
  --dataset-file .benchmark/datasets/swe-bench-lite-all.jsonl
python3 scripts/fetch_swe_bench.py \
  --instances-file datasets/swe-bench-lite/screened-v2.txt \
  --output .benchmark/datasets/swe-bench-lite-screened-v2.jsonl
```

`reviewed-v2.txt` is currently identical to `screened-v2.txt`. Paper review
checks the Issue and named target-test evidence; it does not replace historical
environment reproduction or inspection of every test body. Several included
records explicitly flag where the named test's assertions still need checking.

The existing runner accepts `full-300.txt`, `screened-v2.txt`, or
`reviewed-v2.txt` with
the matching downloaded case file. Use the official SWE-bench harness for
scoring. Never divide resolved cases by 84 and compare that percentage to a
published 300-case result. Before calling v2 a final capability benchmark,
inspect the flagged target-test bodies, reproduce historical environments,
and audit the 183 rule-excluded cases for potential false negatives.

`sample-10.txt` and `sample-30.txt` contain cross-project integration samples
selected from the official SWE-bench Lite test split. They are intended for
validating Agent and evaluation integrations, not for publishing an official
SWE-bench score. The complete upstream test split contains 300 cases and is
downloaded with `scripts/fetch_swe_bench.py --all`.

The repository stores instance IDs only. Use `scripts/fetch_swe_bench.py` to
download case records from the official dataset source.

`original-cases.txt` is a separate, three-case research selection of real
upstream tasks. The [dataset survey](../../docs/BUGFIX_DATASET_SURVEY.md)
explains why each repository and defect was chosen and which capability claims
the public tests do or do not support. These cases have not been independently
reproduced in this repository; do not report their selection as a new benchmark
or mix their results with repository-owned Bugfix-v1 scores.

To fetch their official records without committing upstream patches:

```bash
python3 scripts/fetch_swe_bench.py \
  --instances-file datasets/swe-bench-lite/original-cases.txt \
  --output .benchmark/datasets/swe-bench-lite-original-cases.jsonl
```

## Diagnostic v1: capability-oriented selection

`diagnostic-v1.txt` is the ordered, runnable seven-case selection from the
official Lite `test` split. `diagnostic-v1.jsonl` records each case's four
selection dimensions: repository context, repair obstacle, issue information,
and verification evidence. It also records the capability hypothesis and the
claim that the case **cannot** support. The pinned upstream `repo`, `base_commit`,
and test counts are checked against downloaded official records. This selection
is not an independently validated benchmark or an official 300-case score.

| Role | IDs | Interpretation |
| --- | --- | --- |
| Core (5) | Astropy 12907, Django 12700, Seaborn 3010, Flask 4045, Pylint 5859 | Five distinct repair obstacles; report each case and obstacle separately. |
| Information controls (2) | Pytest 7373, Django 13551 | The issue names the mechanism or solution; success cannot establish independent diagnosis. |

The core set is deliberately small and capability-oriented, not a random or
representative sample of all Bugfix issues. We excluded Requests 1963 from v1:
its seven upstream `FAIL_TO_PASS` test identifiers include several authentication
and cookie tests that do not obviously match the redirect-state report. That
test-to-claim relationship needs manual review before the case can support a
state-reasoning conclusion. Feature requests in the integration samples are
also not silently relabeled as Bugfix cases.

To fetch and validate the fixed selection:

```bash
python3 scripts/fetch_swe_bench.py \
  --instances-file datasets/swe-bench-lite/diagnostic-v1.txt \
  --output .benchmark/datasets/swe-bench-lite-diagnostic-v1.jsonl
python3 scripts/report_diagnostic.py \
  --dataset-file .benchmark/datasets/swe-bench-lite-diagnostic-v1.jsonl
```

To generate patches with a CLI-compatible Agent available in the current
environment, use the existing runner. Replace the example `--agent-command`
with the CLI entry point of the Agent under test; all Agents receive the same
official issue and base commit, and return patches in the same format.

```bash
python3 scripts/run_swe_bench_agent.py \
  --dataset-file .benchmark/datasets/swe-bench-lite-diagnostic-v1.jsonl \
  --instances-file datasets/swe-bench-lite/diagnostic-v1.txt \
  --agent-command "python3 -m bugfix_agent.evaluate" \
  --model-name bugfix-agent \
  --run-id diagnostic-v1-bugfix-agent
```

`results/diagnostic-v1-bugfix-agent/predictions.jsonl` contains Agent patches,
**not scores**. For local official grading, use the SWE-bench Docker harness on
a supported host. `--allow-empty` counts empty Agent patches as failures rather
than dropping those cases:

```bash
python3 scripts/grade_swe_bench.py \
  --instances-file datasets/swe-bench-lite/diagnostic-v1.txt \
  --patch-dir results/diagnostic-v1-bugfix-agent/patches \
  --model-name bugfix-agent \
  --run-id diagnostic-v1-bugfix-agent \
  --allow-empty
python3 scripts/report_diagnostic.py \
  --dataset-file .benchmark/datasets/swe-bench-lite-diagnostic-v1.jsonl \
  --score-file results/diagnostic-v1-bugfix-agent/score.json
```

The last command refuses a patch-generation summary and separates core cases
from information controls. Seven-case rates must not be compared with the
300-case SWE-bench Lite leaderboard. Do not add upstream test patches, gold
patches, or harness expectations to an Agent's prompt or workspace.
