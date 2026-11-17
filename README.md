# Bugfix Agent Benchmark

基于 DevStar 评测 Agent 代码修复能力的基准框架：固定拉取 SWE-bench Lite 题目与基准源码，调用待测 Agent 生成补丁，再使用 SWE-bench 官方评分器独立验证。

**主流程：准备两个环境 → 固定代码与数据版本 → 生成全部补丁 → 官方评分 → 查看结果。**

---

## 版本与基准范围

| 项目 | 固定配置 |
| --- | --- |
| **数据集** | SWE-bench Lite `test`（共 300 题） |
| **数据集版本（revision）** | `b0dde1093fe417d83b7184254edf8199c1f0dff5` |
| **官方评分器** | `swebench==4.1.0` |
| **本框架版本** | `v0.1.0` |
| **示例 Agent 版本** | Bugfix Agent `v0.1.0`（仓库地址：`https://devstar.cn/devstar-agents/bugfix-agent`） |

> **参考基线**：使用示例 Bugfix Agent `v0.1.0` 搭配 `DeepSeek-V4.1-Flash-1017`在本框架上的参考成绩为 **（70.0% RESOLVED）**。详细数据与口径说明见 [Bugfix Agent 仓库说明](<https://devstar.cn/devstar-agents/bugfix-agent>)。

---

## 一、准备环境

评测分为 **生成补丁** 与 **官方评分** 两个阶段，建议使用两个独立环境（评分数据包含标准答案和测试补丁，不应放在 Agent 可访问的工作区中）。

| 环境 | 职责 | 最低要求 |
| --- | --- | --- |
| **生成环境**（DevStar Agent 实例） | 拉取题目描述、调用 Agent 生成补丁 | Python 3.9+、Git、可访问 GitHub/数据集与源码 |
| **评分环境**（独立机器/容器） | 运行官方测试并给出最终评分 | **Python 3.10+**、运行中的 Docker、可拉取 SWE-bench 官方镜像 |

### 在 DevStar 中配置生成环境

1. **导入本仓库**：在 DevStar 选择 **迁移外部仓库**，导入本仓库地址。
2. **配置模型**：进入导入后仓库的 **设置 → AI 设置**，配置你有权使用的模型服务与 API Key。
3. **启动待测 Agent**：在仓库的 **Agent Team** 中启动待测 Bugfix Agent，确认实例状态为**在线**。
   - 若使用平台内置的示例 Bugfix Agent，请核对当前环境对应 `v0.1.0` 版本；
   - 若评测自定义 Agent，需确保其支持 `/evaluate-case` 指令，并接入 DevStar 实例派发与结果接口。
4. **进入终端并锁定框架版本**：打开该 Agent 实例的 **Web Terminal**，进入 `bugfix-agent-benchmark` 根目录，切换到固定 Release 版本：

   ```bash
   git fetch --tags
   git checkout <BENCHMARK_TAG>
   ```

---

## 二、拉取数据并生成全量补丁

在 **DevStar Agent 的 Web Terminal** 中执行（确保与评分数据隔离）：

```bash
# 1. 安装数据拉取依赖
python3 -m pip install -e '.[datasets]'

# 2. 按固定 revision 下载 300 题（仅含题目描述和基准信息，不含测试答案）
python3 scripts/fetch_swe_bench.py \
  --revision b0dde1093fe417d83b7184254edf8199c1f0dff5 \
  --instances-file datasets/swe-bench-lite/full-300.txt \
  --output .benchmark/datasets/swe-bench-lite-test.jsonl

# 3. 运行全量 300 题生成补丁
python3 scripts/run_swe_bench_agent.py \
  --dataset-file .benchmark/datasets/swe-bench-lite-test.jsonl \
  --adapter devstar-runtime \
  --model-name bugfix-agent \
  --run-id swe-lite-full
```

> **提示**：
> - `--model-name` 仅作为结果记录标签，实际模型由 DevStar 的 AI 设置决定。
> - 若想先跑 1 题快速验证通路是否正常，可在第 3 步命令中追加 `--max-cases 1` 并改用独立 `--run-id`。
> - **中断续跑**：确认原进程已停止后，用相同参数在末尾追加 `--resume`（已生成非空补丁的题目会自动跳过）；若需重试失败任务，先确认 DevStar 中对应事件已停止，再使用 `--resume --retry-failed`。

---

## 三、运行官方评分

在**独立评分环境**中检出同一 `<BENCHMARK_TAG>` 版本的本仓库，将生成环境产出的 `results/swe-lite-full/` 目录复制过来，然后执行：

```bash
# 1. 安装评分器并检查 Docker
python3 -m pip install -e '.[datasets]' 'swebench==4.1.0'
docker info

# 2. 下载包含测试套件的官方评分数据（勿复制到 Agent 工作区）
python3 scripts/fetch_swe_bench.py \
  --revision b0dde1093fe417d83b7184254edf8199c1f0dff5 \
  --instances-file datasets/swe-bench-lite/full-300.txt \
  --output .benchmark/datasets/agent-input.jsonl \
  --scoring-output .benchmark/scoring/swe-bench-lite-test.json

# 3. 执行官方评分（可根据机器 CPU/内存适当调大 --max-workers）
python3 scripts/grade_swe_bench.py \
  --dataset .benchmark/scoring/swe-bench-lite-test.json \
  --instances-file results/swe-lite-full/instances.txt \
  --patch-dir results/swe-lite-full/patches \
  --model-name bugfix-agent \
  --run-id swe-lite-full \
  --max-workers 1 \
  --allow-empty

# 4. 查看评分汇总
python3 -m json.tool results/swe-lite-full/score.json
```

评分器会拉取或复用官方测试镜像、应用补丁并运行目标测试与回归测试：`resolved` 表示通过，`unresolved` 表示已评分但未全部通过；空补丁与评分异常会单独记录。

---

## 四、查看与记录结果

| 产出路径 | 说明 |
| --- | --- |
| `results/swe-lite-full/run.json` | Agent 生成状态、数据文件 SHA-256 与运行参数 |
| `results/swe-lite-full/patches/` | 逐题生成的修复补丁 |
| `results/swe-lite-full/score.json` | 官方评分汇总（`passed`、`total`、`pass_rate`）与逐题状态 |
| `logs/evaluation/swe-lite-full/` | 官方评分完整测试输出与逐题 `report.json` |

对外发布或对比测评结果时，建议一并记录：**Benchmark 版本、Agent 版本、DevStar 版本、模型与供应商、单题调用预算、数据集 revision、评分器版本（`swebench==4.1.0`）**。

---

## 开发与自检

运行仓库内置单元测试：

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

通过命令行 adapter 接入其他外部 Agent 的说明，见 [数据与接入说明](docs/DATASETS.md)。
