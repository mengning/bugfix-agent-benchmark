# 跨来源 Bugfix Benchmark：选题目的与证据逻辑

状态：研究与候选集 v0（2026-10-21）。本文件定义如何选题，**不宣称候选题已经复现、可运行或获得可比较分数**。具体候选和证据见 [case-candidates.jsonl](../datasets/cross-source/case-candidates.jsonl)。

## 研究问题

我们要测量的是：Agent 在什么仓库情境、收到多少问题信息时，能识别什么修复障碍，交付怎样的补丁，并由什么独立证据确认结果？“来自著名数据集”“语言不同”或“测试能运行”都不足以让一道题入选。

目标是构建跨来源的能力诊断集，同时保留每个来源自己的官方对照集。跨来源诊断集的结果须按任务入口、语言、能力障碍和验证协议分层报告；不得将不同数据集的原始通过数直接相加为行业排名。

## 为什么研究这些来源

以下信息来自各项目的官方仓库、数据页或论文；来源仅是候选池，**不是承诺每个来源都必须贡献相同数量的题**。

| 来源 | 原始选题目的与构造 | 借鉴的原则 | 纳入时必须检查的偏差 |
| --- | --- | --- | --- |
| [SWE-bench](https://arxiv.org/abs/2310.06770)、[Verified](https://www.swebench.com/verified) | 从真实 GitHub Issue 与修复 PR 构建仓库级任务；Verified 强调人工核查可解性与描述质量 | 自然语言 Issue、修复前代码、独立目标测试组成完整 Agent 任务 | 题目未必全是 Bugfix；热门 Python 仓库和历史公开解法会影响外推 |
| [SWE-bench-Live](https://github.com/microsoft/SWE-bench-Live) | 用较新的任务与持续更新降低静态题库污染 | 冻结公开时间、Agent 可见输入和一次性评测协议 | 不得把隐藏测试、修复补丁或评分反馈交给 Agent |
| [SWE-bench Pro V2](https://github.com/scaleapi/SWE-bench_Pro-os/blob/main/v2/README.md) | 面向更长、更复杂的真实软件工程任务 | 发布前要求 gold patch 通过、空补丁失败；全新环境重放模型补丁 | 复杂任务并不自动等于 Bugfix；需排除功能开发与歧义题 |
| [SWE-bench Multilingual](https://www.swebench.com/multilingual)、[Multi-SWE-bench](https://github.com/multi-swe-bench/multi-swe-bench) | 扩展 Python 之外的仓库级 Issue 修复；后者采用专家审查 | 跨语言、跨构建系统检查能力迁移；人工核查测试与题意 | 两套来源可能共享仓库或 Issue；去重后才能声称新增证据 |
| [SWE-bench Multimodal](https://www.swebench.com/multimodal) | 将截图等非文本证据纳入软件问题 | 单独测量视觉证据理解 | 纯文本 Agent 不能因无图像输入而被当作普通 Bugfix 失败 |
| [Defects4J](https://github.com/rjust/defects4j) | 可复现的 Java 真实缺陷；Issue 关联、单提交修复、人工清理无关改动、稳定触发测试 | 修复前/后版本和明确 fail→pass 是有效性闸门 | 原始 APR 测试任务不等于自然语言 Issue-to-PR；须单独定义 Agent 输入 |
| [BugsInPy](https://github.com/soarsmu/BugsInPy) | Python 真实缺陷的版本对及相关测试，支持受控调试与修复研究 | 把版本、依赖和触发测试作为可复现元数据 | 新增测试可能只在修复版存在；移植到错误版时不可泄漏修复 |
| [BugsJS](https://github.com/BugsJS/bug-dataset) | JavaScript 项目的 buggy、fixed-only-test-change、fixed 三版本，保存 Issue 与测试信息 | 显式区分原始错误版、只移植测试版和完整修复版 | Issue 保存在 protobuf；解码前不能声称题意与测试对齐 |
| [Bears](https://github.com/bears-bugs/bears-benchmark)、[BugSwarm](https://github.com/BugSwarm/bugswarm) | 从 CI 失败/成功构建寻找真实缺陷与环境 | 把历史 CI 失败与可复现性作为候选发现线索 | 构建转绿不必然意味着修了原报告的语义缺陷 |
| [BugsCpp](https://github.com/Suresoft-GLaDOS/bugscpp)、[GoBench](https://github.com/goodmorning-coder/gobench) | 分别提供 C/C++ 缺陷和 Go 并发缺陷等专门场景 | 引入原集缺少的内存安全、并发等障碍 | 专题集的测试目标可能不是通用 Issue-to-PR；需要独立验证器 |
| [QuixBugs](https://github.com/jkoppel/QuixBugs) | 人工注入的小程序缺陷 | 可作算法修复压力或 Runner 控制题 | 不是真实仓库 Issue，不能混入真实开发任务的成功率 |

## 选题的底层逻辑

先过质量闸门，再判断增量解释力，**不按来源、语言或题型预定配额**。

质量闸门：核对原始 case ID 与来源版本、合法可访问的修复前仓库、Agent 可见的原始问题输入、独立目标测试、原始错误版失败与修复版通过、可复建环境、数据许可与泄漏边界。任何一项缺失就保留在候选/暂缓层，不进入可评分集。空补丁必须不能通过目标测试；环境错误与补丁错误分开记录。Defects4J 的 [官方约束](https://github.com/rjust/defects4j#the-bugs)和 Pro V2 的[发布闸门](https://github.com/scaleapi/SWE-bench_Pro-os/blob/main/v2/README.md)给出了可借鉴的验证方式，但不是跨来源统一评分器。

增量解释力：每题写出相对于已入选题新增的能力证据。比较维度是：

1. 仓库情境：语言、领域、架构、依赖/构建、状态与权限边界；
2. 缺陷机制：边界值、跨模块状态、并发、资源/环境退化、安全契约、兼容性、数据表示等；
3. 信息条件：仅症状、可复现步骤、定位线索、直接给出根因或修复方案，以及文本/图像模态；
4. 修复操作：局部实现、跨文件修改、API/配置迁移、需要保留旧行为的回归张力；
5. 验证证据：目标与回归测试是否对齐，单元/集成/端到端层级，稳定性及隐藏测试；
6. 时间与污染：Issue/修复的公开时间、已有公开答案、Agent 是否可能见过 gold patch。

“代表性”在此首先指机制覆盖与对照解释力，不是统计意义上代表所有真实缺陷。若要声称总体分布代表性，必须另定义目标总体与抽样框，不能用这份有目的的选题集直接推断。

每题必须回答：为什么选这个仓库？为什么选这个缺陷而非同类题？它观察 Agent 的哪一步？目标测试到底断言了什么？若通过，哪些替代解释仍存在？若失败，如何排除环境和接口问题？清单中的 selection_purpose、unique_evidence、inference_limit 与 next_gate 必须可核查；缺一则不标为可评分。

## 数据集组织与报告

- datasets/cross-source/case-candidates.jsonl 是候选审查记录，不是可运行清单。记录可信证据和阻塞闸门；不复制上游 gold patch、隐藏测试或仓库源码。
- datasets/swe-bench-lite/full-300.txt 继续用于 SWE-bench Lite 官方对照；现有 84 题诊断清单也不自动进入跨来源最终集。
- 同一 repo + issue/PR + base commit 跨来源出现时只算一个独立缺陷，保留多个来源指针。
- 报告先给每来源协议下的原始结果，再按上述维度作条件分析。需要汇总时必须公布权重与分母；不得把 APR 测试输入、Issue-to-PR 输入和视觉输入混称同一种任务。

## 现阶段可证实与不能宣称的事

当前仅核实了首批候选的官方标识、部分 Issue/测试线索，尚未在各来源的历史环境执行 fail→pass 校验。例如 BugsInPy black-1 的目标测试只在修复版出现，必须先安全移植为隐藏 oracle；BugsJS Bower-1 的 Issue 还需解码核对；BugsCpp cpp_peglib-1 的目标测试与缺陷描述尚未证明对齐。这些是具体的下一道工作闸门，而不是已完成的评分。

本报告由 AI 辅助检索和整理；正式发表前须复核上游版本、许可和逐例测试断言。

规模化的情境分类与 176 题候选池另见 [Bugfix 能力情境候选池 v1](SCENARIO_BENCHMARK_DESIGN.md)。本文件保留跨来源选题的质量闸门与逐例证据逻辑；候选池扩张不会把未回放的题自动升级为可评分题。

## 第二批跨来源案例：为什么选、为什么暂缓

本批不是按语言凑数。新增的 Tornado WebSocket 生命周期回归、fmt 分配器传播、glslang 小整数索引生成码、WireMock CLI 超时配置，分别检验版本兼容、C++ 类型语义、编译器中间表示与配置到行为的贯通。它们的原始 Issue 与数据集目标测试至少在题意层面对齐，因此进入 `nominated`；仍须历史环境复现才能进入可评分集。完整 ID、证据和下一道闸门在候选清单。

另外三类题保留为 `hold`，因为它们暴露的是选题质量问题，而非 Agent 能力：Pkl 的 Issue 创建晚于修复 PR，须核查是否属于事后包装；Windows SDL 的 ARM64 `__chkstk` 报告与列出的显示模式目标测试不明显对齐；GoBench 的 etcd 死锁和数据竞争有真实栈与 Docker 环境，但尚缺不泄漏答案的修复前问题输入，且并发 oracle 需要重复运行并区分超时/竞争检测的假阴性。把这些题直接计分会污染结论。

这也形成一个可用于后续选题的判别式：`独立问题输入 × 历史错误状态 × 对齐的目标 oracle × 可复建环境 × 新增能力证据`。任一项为零，题目只能用于研究或环境验证，不能进入正式 Bugfix 成功率分母。不同来源的 `issue_to_patch`、`historical_bug_pair` 与 `historical_concurrency_bug` 仍需分层报告；上述判别式是准入逻辑，不是跨数据集加权得分公式。
