# Cross-source Bugfix case review

Start with [the selection rationale](../../docs/MULTI_SOURCE_SELECTION.md).
case-candidates.jsonl contains case-level evidence and next validation gates,
not a runnable or scored benchmark. IDs remain in the source's namespace. Do
not pass a gold patch, fixed-version test implementation, or hidden test
metadata to the Agent.

Statuses: nominated means the case and its proposed diagnostic purpose have
source evidence but still require baseline replay; hold means even the
Issue-to-test relation or input contract has not been confirmed. A case
becomes runnable only after the source-specific environment proves
empty/baseline failure, reference-fix pass, and no answer leakage. That
promotion has not occurred here. No cross-source score should be computed
from this file.

Current review: 17 concrete cases from nine source families (counting
SWE-bench-Live MultiLang and Windows separately): 11 nominated and 6 hold.
The added cases deliberately change the failure mechanism, not just the
programming language:

| Source | Case evidence added | Why it changes the capability question |
| --- | --- | --- |
| BugsInPy | tornado-1 | API lifecycle regression after a version change |
| SWE-bench-Live/MultiLang | fmt-4490, glslang-4006, pkl-1165, wiremock-3130 | allocator semantics, generated IR, escaping, and CLI configuration |
| SWE-bench-Live/Windows | SDL-11761 | Windows ARM64 build failure; held because listed target test does not clearly match the issue |
| GoBench/GoReal | etcd-10492, etcd-4876 | blocking deadlock versus nonblocking data race; both held pending a non-leaking problem input and repeated replay |

The Pkl case is also held: its Issue was opened after the repair PR, making
the natural-language input chronology suspect. `nominated` is still not
`runnable`; none of these added cases has passed historical fail-to-pass
replay here.

## Scenario-oriented expansion

[The scenario design](../../docs/SCENARIO_BENCHMARK_DESIGN.md) treats defect
mechanism, task span, and operational context as independent axes.
`scenario-pool-v1.jsonl` is a 176-case research pool merged from the 84
paper-reviewed Lite cases, this 17-case review list, and 82 metadata-screened
external records, with duplicate IDs merged. The manually selected external
IDs and their specific purposes are in `scenario-seeds-v1.tsv`; rebuild them
with `python3 scripts/build_scenario_pool.py`. The pool contains no gold patch
or target-test implementation. It is **not** an executable manifest, and its
size is not an evaluation denominator.
