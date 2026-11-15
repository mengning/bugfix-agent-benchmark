# Bugfix-v1

This is a repository-owned Bugfix Agent evaluation set. Each case is an
isolated, deliberately buggy Python project. The manifest gives the Agent the
problem statement and gives the scorer executable `fail_to_pass` and
`pass_to_pass` checks. Tests are protected from Agent patches.

| Case | Bug class | Failing check | Regression checks |
| --- | --- | --- | --- |
| `url-host-validation` | Hostname suffix spoofing | Reject `evil-example.com` | Exact host, subdomain, malformed URL |
| `tenant-cache-isolation` | Cross-tenant cache leakage | Isolate identical resource IDs by tenant | Same-tenant reuse, other resource miss |
| `pagination-boundary` | Off-by-one page slicing | Avoid overlap of adjacent full pages | Empty result, invalid arguments |

Run all three through `scripts/run_agent_benchmark.py` with
`--manifest datasets/bugfix-v1/manifest.jsonl`. `score.json` counts a case
only if its original failing check becomes green and its previously green
checks remain green. A patch that modifies `tests/` or generated log/result
files is rejected. With `--adapter devstar-runtime`, the runner dispatches
`/evaluate-case` to the current DevStar Agent instance and reads its patch
artifact. With `--adapter command`, it invokes a configured Agent CLI.
Neither evaluation route creates Issues or PRs. See the repository
[README](../../README.md) for Web Terminal steps and required versions.

These are transparent starter cases, not hidden tests or an industry-wide
leaderboard. Public cases can be overfit. Expand the suite with independently
reviewed projects, difficulty tiers, and held-out tests before using scores
to claim broad Agent quality.
