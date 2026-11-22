# 数据集与 Agent 接入说明

本文说明本框架的数据组织方式、隔离原则，以及如何接入待测的 Bugfix Agent。

---

## 一、数据集与防泄漏设计

本仓库主要基于 **SWE-bench Lite (`test`)** 进行评测：

* **固定题目与顺序**：`datasets/swe-bench-lite/full-300.txt` 固定了全部 300 个用例 ID 及执行顺序。
* **不提交上游题库正文**：仓库内不直接存放参考补丁与测试用例内容，题目数据统一由 `scripts/fetch_swe_bench.py` 从上游拉取，评分结果由官方评分器运行生成。

为防止测试答案泄漏给待测 Agent，拉取脚本将数据严格拆分为两份：

| 数据类型 | 生成参数 | 包含内容 | 存放位置要求 |
| --- | --- | --- | --- |
| **生成数据**（Agent 输入） | `--output` | 仅包含 Issue 描述、仓库与基准提交等公开字段，**不含参考修复与测试补丁** | 放在 Agent 可访问的工作区（如 `.benchmark/datasets/`） |
| **评分数据**（Harness 输入） | `--scoring-output` | 包含参考补丁与官方测试套件的完整记录 | **仅保存在独立评分环境**，严禁放入 Agent 工作区 |

---

## 二、接入自己的 Agent

Benchmark 以子进程启动配置中的 Agent 命令，并通过以下环境变量传递输入和产物路径。

| 环境变量 | 用途 |
| --- | --- |
| `BENCHMARK_CASE_ID` | 题目 ID |
| `BENCHMARK_CASE_FILE` | 题目 JSON 文件路径 |
| `BENCHMARK_WORKSPACE` | 基准源码目录 |
| `BENCHMARK_ARTIFACT_FILE` | 补丁产物 JSON 文件路径 |

Agent 将包含非空 `patch` 的 JSON 写入产物路径，以退出码 `0` 结束。补丁使用 unified diff 格式。

用 [默认配置](../configs/swe-bench-lite.json) 作为模板，将 `agent.command` 改成你的 Agent 命令，按需配置 `agent.env_map`、`dataset.instances_file` 和 `run.run_id`。无需映射模型变量时，可把 `agent.env_map` 设为 `{}`。在三个阶段的命令上使用同一个 `--config <路径>`，并按 README 交接文件。

显式参数优先于自定义配置，自定义配置只需包含要覆盖的字段。可以运行各脚本的 `--help` 查看参数。
