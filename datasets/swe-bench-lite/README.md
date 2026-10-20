# SWE-bench Lite

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
