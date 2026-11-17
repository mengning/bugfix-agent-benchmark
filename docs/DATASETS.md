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

运行器支持通过 `--adapter` 接入不同形态的 Agent，目前提供 **DevStar 实例模式** 与 **命令行模式** 两种方式。

### 方式 1：接入 DevStar 中的 Agent（`--adapter devstar-runtime`）

适用于已在 DevStar 平台部署并以 Agent Team 实例形式运行的 Agent。

#### 接入要求
1. **Agent 侧**：支持接收 `/evaluate-case` 任务，读取派发的用例信息与临时工作区，并在结果 `artifact` 中返回匹配的 `case_id` 与非空 `patch`（标准 unified diff）。
2. **平台侧**：DevStar 实例环境需注入 `DEVSTAR_TOKEN` 与 `DEVSTAR_PLATFORM_URL`（或 `DEVSTAR_BASE_URL`），并提供以下接口：
   - `POST /-/agent-services/instances/dispatch`：向当前实例（`target_self=true`）派发 `/evaluate-case` 任务。
   - `GET /-/agent-services/events/{event_id}/result`：轮询任务状态并读取结果中的 `artifact`。

#### 运行命令
在已启动待测 Agent 实例的 **Web Terminal** 中执行：

```bash
python3 scripts/run_swe_bench_agent.py \
  --dataset-file .benchmark/datasets/swe-bench-lite-test.jsonl \
  --adapter devstar-runtime \
  --model-name <your-agent-name> \
  --run-id <your-run-id>