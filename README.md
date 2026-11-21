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

## 一、准备 DevStar 评测环境

在 DevStar 导入本仓库，进入仓库的 **设置 → AI 设置** 配置模型服务和 API Key。示例 Agent 镜像的模型 ID 填 `deepseek-flash`。

- 在 **Agent Team** 启动 Bugfix Agent `v0.1.0`，打开 Agent Web Terminal。
- 将 [评分 DevContainer 配置](.devcontainer/devcontainer.json) 放到 DevStar 上 Benchmark 仓库的默认分支。在仓库的 **开发容器** 页面创建容器，并打开 Web Terminal。已创建的容器需重新创建才能应用挂载。

评分镜像已安装 Python、Docker CLI 和 SWE-bench，通过 `/var/run/docker.sock` 连接 DevStar 服务器的 Docker 服务。请在管理员信任的评分容器中使用此配置，并将评分工作区及数据集缓存与 Agent 隔离。

在评分终端检查 Docker 连接：

```bash
docker info --format 'Docker Server {{.ServerVersion}}'
```

两个终端进入同一 Benchmark 提交的仓库根目录，使用 [默认配置](configs/swe-bench-lite.json) 完成下列步骤。

## 二、运行测评

### 1. 准备 300 道题（评分终端）

```bash
python3 scripts/fetch_swe_bench.py
```

通过两个容器的共享交接目录，将 `.benchmark/datasets/swe-bench-lite-test.jsonl` 复制到 Agent 工作区的同一相对路径。

### 2. 生成补丁（Agent 终端）

```bash
python3 scripts/run_swe_bench_agent.py
```

Benchmark 直接启动 Agent 子进程并使用 DevStar 注入的模型配置。中断后可在原命令末尾加 `--resume`。需要在生成阶段执行目标仓库测试时，请在生成容器准备与基准提交兼容的依赖。

### 3. 官方评分（评分终端）

通过共享交接目录，将 `results/swe-lite-full/instances.txt` 和 `results/swe-lite-full/patches/` 复制到评分工作区的同一相对路径。在评分终端运行：

```bash
python3 scripts/grade_swe_bench.py
```

脚本根据题目清单准备评分数据，由官方评分器通过 Docker 复用或拉取测试镜像。结果写入 `results/swe-lite-full/score.json`，逐题测试日志位于 `logs/run_evaluation/swe-lite-full/bugfix-agent/`。

默认参数统一保存在 [`configs/swe-bench-lite.json`](configs/swe-bench-lite.json)。传入 `--config <路径>` 可覆盖默认配置，显式命令行参数优先。接入自定义 Agent 见 [数据与接入说明](docs/DATASETS.md)。

## 开发与自检

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```
