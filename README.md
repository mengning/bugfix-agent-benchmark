


# Bugfix Agent Benchmark

基于 DevStar 评测 Agent 代码修复能力的基准框架：在 Agent 容器内调用待测 Agent 生成 SWE-bench Lite（300 题）补丁，再通过 Benchmark 开发容器接入 DevStar 服务器 Docker 运行官方评分。

---

## 版本与基准范围

| 项目 | 配置 |
| --- | --- |
| **数据集** | SWE-bench Lite `test`（300 题，固定顺序见 [full-300.txt](datasets/swe-bench-lite/full-300.txt)） |
| **数据集版本（revision）** | `b0dde1093fe417d83b7184254edf8199c1f0dff5` |
| **默认配置文件** | `configs/swe-bench-lite.json` |
| **官方评分器** | `swebench==4.1.0` |
| **本框架版本** | `v0.1.0` |
| **示例 Agent 版本** | [Bugfix Agent `v0.1.0`](https://devstar.cn/devstar-agents/bugfix-agent)（提交 `d899c02da93d3161fd6eb51566c8a3a216a67e84`） |

> **参考基线**：示例 Bugfix Agent `v0.1.0` 搭配 `DeepSeek-V4.1-Flash-1017`（单题上限 32 次调用）单次全量运行通过 **210 / 300（70.0%）**。详情见 [Bugfix Agent 仓库说明](https://devstar.cn/devstar-agents/bugfix-agent)。

---

## 一、DevStar 容器分工

补丁生成与官方评分在 DevStar 上使用两个独立容器，也防止生成阶段接触评分数据与缓存：

| 入口 | 容器配置来源 | 用途 |
| --- | --- | --- |
| `Agent Team → Bugfix Agent 实例 → >_` | Bugfix Agent 仓库模板 | 打开 Benchmark 工作区，由 Benchmark 直接启动 Agent 子进程生成补丁 |
| `Benchmark 仓库 → 开发容器 → Web Terminal` | 本仓库 `.devcontainer` | 接入 DevStar 服务器 Docker，导出题库并运行 SWE-bench 官方评分 |

两容器通过管理员配置的共享交接目录传递题目输入和补丁产物；包含参考补丁和测试补丁的评分数据仅保留在开发容器中。

---

## 二、准备环境与版本

1. **导入仓库与配置模型**：在 DevStar 选择 **迁移外部仓库** 导入本仓库，进入 **设置 → AI 设置** 配置模型服务与 API Key（示例 Agent `v0.1.0` 要求模型 ID 填 `deepseek-flash`）。
2. **打开两个终端**：
   - **Agent 终端**：进入 `Agent Team → Bugfix Agent v0.1.0 → >_`（或你的自定义 Agent 实例）。
   - **评分终端**：进入 `Benchmark 仓库 → 开发容器 → Web Terminal`，确认 Python ≥ 3.10 且 `docker info` 返回服务器 `Server` 信息。
3. **检出 `v0.1.0` 并确认评分依赖**：在两个终端各自的 `bugfix-agent-benchmark` 根目录执行：

```bash
git fetch --no-tags https://github.com/mengning/bugfix-agent-benchmark.git refs/tags/v0.1.0 && git checkout --detach FETCH_HEAD
```

若 `.devcontainer` 镜像未预装评分依赖，在 **评分终端** 执行：

```bash
python3 -m venv .venv && . .venv/bin/activate && pip install -e '.[datasets]' 'swebench==4.1.0'
```

---

## 三、执行全量 300 题测评

以下 3 条命令的默认参数（数据集 revision、300 题清单、Agent 入口、产物目录与环境变量映射）均读取自 `configs/swe-bench-lite.json`：

### 1. 准备题目｜评分终端

```bash
python3 scripts/fetch_swe_bench.py
```

按固定 revision 导出 300 道不含答案的题目到 `.benchmark/datasets/swe-bench-lite-test.jsonl`。通过共享交接目录将该文件复制到 **Agent 终端** 相同相对路径。

### 2. 生成补丁｜Agent 终端

```bash
python3 scripts/run_swe_bench_agent.py
```

使用 DevStar 注入的模型配置逐题拉起 Agent 子进程生成补丁，产出写入 `results/swe-lite-full/`。运行结束后，将 `results/swe-lite-full/instances.txt` 与 `results/swe-lite-full/patches/` 复制到 **评分终端** 相同相对路径。

### 3. 官方评分｜评分终端

```bash
python3 scripts/grade_swe_bench.py
```

评分脚本根据本轮 `instances.txt` 准备官方评分数据，通过 DevStar 服务器 Docker 自动拉取缺少的镜像并运行测试容器，最终输出 `results/swe-lite-full/score.json`。

> **常用选项**：
> - 中断续跑：在第 2 步后追加 `--resume`；
> - 指定其他配置或自定义 Agent：使用 `--config <路径>`、`--agent-command '<命令>'` 或对应命令行参数覆盖默认值（见 `docs/DATASETS.md`）。

---

## 四、查看结果与自检

在 **评分终端** 查看总分（关注 `passed`、`total` 与 `pass_rate`，以官方 `resolved` 状态为准）：

```bash
python3 -m json.tool results/swe-lite-full/score.json
```

| 产出路径 | 说明 |
| --- | --- |
| `results/swe-lite-full/score.json` | 官方评分汇总与逐题状态 |
| `results/swe-lite-full/run.json` | 本轮运行参数与逐题补丁生成状态 |
| `results/swe-lite-full/patches/` | 逐题生成的修复补丁 |
| `results/swe-lite-full/cases/` | 逐题输入、Agent 产物与执行记录 |
| `logs/run_evaluation/swe-lite-full/<model-name>/<instance_id>/` | SWE-bench 4.1.0 逐题 `report.json` 与 `test_output.txt` |

运行框架内置单元测试：

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

自定义 Agent 接入约定与离线数据快照用法见 [数据与接入说明](docs/DATASETS.md)。
