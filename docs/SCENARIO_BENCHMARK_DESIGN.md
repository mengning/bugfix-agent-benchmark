# Bugfix 能力情境候选池 v1

状态：研究候选，不是可运行清单或评测成绩。逐题元数据见 [scenario-pool-v1.jsonl](../datasets/cross-source/scenario-pool-v1.jsonl)，人工补选理由见 [scenario-seeds-v1.tsv](../datasets/cross-source/scenario-seeds-v1.tsv)。本次由 AI 辅助检索与整理；正式发表前需复核上游版本、许可、原始 Issue、目标测试断言和历史环境。

## 分类对象是任务，不是语言或数据集

“缺陷”“长任务”“生产”不是互斥的三类。同一题可以同时是状态缺陷、跨模块修改和生产服务故障。因此候选记录三个正交轴，而不是按 SWE-bench/Java/Python 分箱：

| 轴 | 当前记录 | 可以支持的判断 | 不能直接支持的判断 |
| --- | --- | --- | --- |
| 缺陷机制 | `mechanism_family` + 更具体的 `defect_mechanism` | 边界、状态、兼容、并发、恢复、安全等修复障碍 | 仅凭标题证明根因或测试覆盖 |
| 任务跨度 | `reference_changed_files` + `task_span` | 参考补丁触及多个文件，可优先审查长链路题 | 文件数不等于 Agent 实际步数或认知难度；`long_task_proxy` 不是已认证长任务 |
| 运行情境 | `operational_context` | 服务、工具链、前端、科学库等环境差异 | “service” 标签不等于经过真实生产事故验证 |

长任务代理条件为：上游参考补丁至少触及 4 个文件，且上游问题文本不少于 500 字符。较短文本的多文件补丁只标 `multi_file_proxy`。这是筛选信号，不是最终能力标签；正式长任务还须人工确认修复必须跨组件，排除格式化、测试文件堆积和无关重构，并记录 Agent 实际轨迹长度。SWE-bench Lite 的本地公开记录不含参考补丁，所以其跨度是 `unknown`，不能据题名猜测。

“生产可靠性”优先看服务恢复、资源耗尽、并发、安全边界、权限和数据持久化，但这些仍需原始 Issue、故障条件和独立 oracle 对齐。`operational_context=service/security` 只是筛选入口，不等于正式生产分层。

## 候选池覆盖与缺口

当前冻结 176 个唯一 case ID：84 个已有 SWE-bench Lite 纸面审查题、82 个新近只经上游元数据筛选的题、4 个早期逐例候选，以及 6 个明确暂缓题。新增题来自 Multi-SWE-bench、SWE-bench-Live MultiLang 和 SWE-bench Pro；早期逐例候选还保留 Defects4J、BugsInPy、BugsJS、BugsCpp、GoBench 与 Windows 场景。数据集来源只是溯源字段，不作为测量维度或配额。

按参考补丁代理指标，目前 28 个 `long_task_proxy`、27 个 `multi_file_proxy`、27 个单文件参考补丁、94 个跨度未知。服务/安全情境候选为 30 个。**这些数是筛选池规模，不是通过质量闸门的有效样本数**。84 道 Lite 题及若干热门仓库仍造成来源倾斜；并发和内存安全也远少于状态、兼容与数据语义题。不能用 176 的总数宣称每个能力格子都有足够统计精度。

## 为什么这些来源提供不同证据

- SWE-bench Lite 的既有 84 题给出经过纸面核对的自然语言 Issue 与目标测试，可用于定位/修复诊断，但源码与目标测试仍须独立历史回放。
- Multi-SWE-bench 扩展到 Go、Rust、Java、JavaScript、TypeScript 等修复机制。其 `body` 往往是修复 PR 文本；本池明确标 `linked_prefixed_issue_required_pr_body_not_accepted`，不能直接作为 Agent 题面。
- SWE-bench-Live MultiLang 提供较新的问题和测试元数据，用来研究新近回归与多构建系统；其中部分目标测试集合很宽，超过 100 条的题标记 `broad_target_set_requires_test_audit`。
- SWE-bench Pro 提供更多跨文件候选和服务故障，但问题描述经过策展，必须核对原始 Issue/时间线，不能将多文件参考补丁直接等同于长时序 Agent 任务。
- Defects4J、BugsInPy、GoBench 等历史缺陷对提供受控故障对照，但输入形态不同于 Issue-to-PR，正式结果必须另报。

## 从候选到可评分的四道闸门

1. **任务真实性**：确认修复前公开的问题输入、仓库 base commit、缺陷而非功能开发；同一 `repo + issue/PR + base commit` 跨来源去重。
2. **Oracle 对齐**：人工读目标测试，确认它断言报告的问题；空补丁在错误版失败，参考修复版通过。大范围测试、测试名与题意不符、修复后才出现的 Issue 一律暂缓。
3. **环境可复建**：冻结工具链、依赖、容器镜像及超时；区分构建失败、测试随机失败、Agent 失败。并发题需重复运行，估计 oracle 本身的检测概率。
4. **答案隔离**：Agent 仅见题面与修复前工作区；参考补丁、移植后的隐藏测试及评分反馈不进入工作区。检查公开答案污染并记录模型/时间戳。

候选清单本身也不得挂载进被测 Agent 的 case 工作区：`selection_purpose`、类别标签和来源 PR 链接是研究员元数据，不是任务输入。尤其 Multi-SWE-bench 的原记录标题常是修复 PR 标题，本池在未核对原始 Issue 前不保存该标题。

上述闸门全部通过，才生成 source-specific 可运行 manifest。不同来源保持自己的执行器/评分协议；不把 Pro、Lite、历史 APR 的原始通过数直接相加为行业排名。

## 如何减少 Agent 结果的偶然性

正式对比时，先冻结 Agent 版本、模型、预算、工具权限和每题环境；每题至少重复 3 次，观察成功次数与失败原因。先报告每题成功比例，再按仓库和能力标签作分层汇总，同时给出分母与置信区间。仓库聚类的 bootstrap 可以避免一个仓库中的大量相似题虚增精度；随机种子、运行次序和超时上限也应公开。若要声称某类能力优劣，每个主要情境需有足够**通过四道闸门的独立题**，当前 28 个长任务代理题和 30 个服务/安全候选不满足这一条件。候选池扩张只能降低选题稀疏性，不能代替多次运行和独立环境验证。

## 复现候选清单

`scripts/build_scenario_pool.py` 从已审查的 Lite inventory、早期逐例候选及人工选定的外部 ID 表重建清单，并向官方数据接口核对 ID、base commit 和目标测试数量。脚本只保存题目摘要和计数，不写入 gold patch 或隐藏测试。外部数据会更新；用于论文或正式报告前，应冻结上游 dataset revision、脚本版本和生成时间，并复核新的差异。

```bash
python3 scripts/build_scenario_pool.py
PYTHONPATH=src python3 -m unittest discover -s tests -q
```
