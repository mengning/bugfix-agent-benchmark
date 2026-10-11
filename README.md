# Bugfix Agent Benchmark

An independent, reproducible benchmark for evaluating patches produced by
Bugfix Agents. The benchmark keeps Agent invocation separate from scoring:

```text
benchmark case -> Agent patch -> clean workspace -> tests -> score
```

The repository never accepts an Agent's self-reported result as a score. Every
patch is replayed and verified independently.

## Evaluation layers

| Layer | Purpose | Counted as an Agent benchmark score |
| --- | --- | --- |
| Smoke fixture | Verify the local runner, patch replay, and regression checks | No |
| SWE-bench Lite | Evaluate real repository issues with the official harness | Yes |

The bundled SWE-bench Lite sample contains ten instance IDs for integration
testing. An official score requires the complete upstream evaluation set and
the official SWE-bench harness.

## Repository structure

```text
datasets/
  smoke/                       repository-owned runner fixture
  swe-bench-lite/              official instance selections only
docs/DATASETS.md               provenance and dataset policy
scripts/fetch_swe_bench.py     download selected official cases
scripts/grade_swe_bench.py     build predictions and invoke official harness
src/bugfix_benchmark/          dataset-neutral patch replay and scoring
tests/                         runner and integration tests
```

Generated repositories, datasets, patches, logs, and scores belong under
`.benchmark/` or `results/`. They are ignored by Git.

## Quick start: verify the runner

Requirements: Python 3.9+ and Git.

```bash
git clone https://github.com/mengning/bugfix-agent-benchmark.git
cd bugfix-agent-benchmark

PYTHONPATH=src python3 -m bugfix_benchmark run \
  --manifest datasets/smoke/manifest.jsonl \
  --repository-root . \
  --adapter patch-dir \
  --patch-dir datasets/smoke/patches \
  --results-dir results \
  --run-id smoke
```

Expected output:

```text
run=smoke passed=1/1 pass_rate=100.0%
python-average: passed
```

This result verifies the runner only. It is not a Bugfix Agent score because
the repository supplies the fixture and its known patch.

## Evaluate SWE-bench Lite patches

### 1. Install the dataset client

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e '.[datasets]'
```

### 2. Download the selected official cases

```bash
python3 scripts/fetch_swe_bench.py \
  --instances-file datasets/swe-bench-lite/sample-10.txt \
  --output .benchmark/datasets/swe-bench-lite-sample-10.jsonl
```

The download is sourced from `SWE-bench/SWE-bench_Lite`. Gold patches are
not stored in this repository.

### 3. Run an Agent

Give each case's `problem_statement` and repository at `base_commit` to
the Agent. Save the resulting unified diff as:

```text
patches/<instance_id>.patch
```

The benchmark is Agent-neutral. A local CLI, HTTP service, or development
platform may produce the patch as long as it follows this artifact contract.

### 4. Build official predictions and grade them

Install the official harness from
<https://github.com/SWE-bench/SWE-bench>, including its Docker requirements.
First inspect the generated command:

```bash
python3 scripts/grade_swe_bench.py \
  --instances-file datasets/swe-bench-lite/sample-10.txt \
  --patch-dir patches \
  --model-name my-bugfix-agent \
  --run-id sample-10 \
  --dry-run
```

Remove `--dry-run` to execute
`python -m swebench.harness.run_evaluation`. The official harness decides
whether each instance is resolved.

## Local manifest contract

The dataset-neutral runner accepts JSON arrays and JSONL. Each local case must
contain executable test commands:

```json
{
  "case_id": "python-average",
  "repository": "smoke/python-average",
  "source_path": "datasets/smoke/fixtures/python-average",
  "base_commit": "fixture",
  "problem_statement": "average truncates fractional results",
  "fail_to_pass": [
    "python3 -m unittest -v test_calc.CalcTests.test_average_keeps_fraction"
  ],
  "pass_to_pass": [
    "python3 -m unittest -v test_calc.CalcTests.test_average_empty_is_zero"
  ]
}
```

For repository-backed cases, use `source_url` and an immutable
`base_commit` instead of `source_path`.

The local runner passes a case only when:

1. every `FAIL_TO_PASS` command fails on the base workspace;
2. the Agent patch applies cleanly;
3. every `FAIL_TO_PASS` command passes after the patch;
4. every `PASS_TO_PASS` command still passes.

## Local results

```text
results/<run_id>/
  score.json
  patches/<case_id>.patch
  cases/<case_id>/
    result.json
    agent.patch
    workspace/
    logs/
```

Possible statuses include `passed`, `no_patch`,
`workspace_failed`, `baseline_invalid`,
`patch_apply_failed`, `fail_to_pass_failed`, and
`pass_to_pass_failed`.

## Dataset governance

See [Dataset Policy](docs/DATASETS.md) before adding or changing a dataset.
Public datasets must have documented provenance, immutable case identifiers,
an acquisition script, and an independent scorer. Machine-local paths,
credentials, generated logs, cloned repositories, and unpublished internal
fixtures are not accepted.

## Development checks

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 -m compileall -q src scripts tests
git diff --check
```

Dataset commands execute third-party code. Run untrusted cases inside the
isolation environment required by their upstream benchmark.
