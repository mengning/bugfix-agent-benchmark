# SWE-bench Lite

`sample-10.txt` and `sample-30.txt` contain cross-project integration samples
selected from the official SWE-bench Lite test split. They are intended for
validating Agent and evaluation integrations, not for publishing an official
SWE-bench score. The complete upstream test split contains 300 cases and is
downloaded with `scripts/fetch_swe_bench.py --all`.

The repository stores instance IDs only. Use `scripts/fetch_swe_bench.py` to
download case records from the official dataset source.
