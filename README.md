# Bugfix Agent Benchmark

一个独立维护的 Bugfix Agent 评测仓库，包含缺陷用例、批处理 runner 和补丁评分器。用户选择被测 Agent，运行一条命令，得到修复 patch、测试证据和用例通过率。

Benchmark 是普通项目仓库，不是另一个 Agent。在 DevStar 中，把它作为 Bugfix Agent 的项目上下文，在该实例的 Web Terminal 中运行评测；不创建 Issue 或 PR。

## 快速开始：在 DevStar 中评测

### 1. 准备仓库与实例

1. 在 DevStar 使用 **迁移外部仓库**，导入 `https://github.com/mengning/bugfix-agent-benchmark.git`。
2. 打开导入后的仓库，进入 **设置 → AI 设置**，配置模型 Provider、Base URL、Model 和 API Key。
3. 在同一仓库的 **Agent Team** 中启动 Bugfix Agent，等待实例运行中且在线/已注册。
4. 打开这个实例的 **Web Terminal**，进入挂载的 `bugfix-agent-benchmark` 仓库根目录。

需要配套版本：Benchmark 支持 `--adapter devstar-runtime`，Bugfix Agent 支持 `/evaluate-case`，DevStar 提供下文的实例派发和结果读取接口。容器需要 Python 3.9+ 和 Git。当前链路已在本地完成三个 Bugfix-v1 用例的验证；配套改动发布前，仅导入 GitHub 仓库不能保证线上平台支持这些接口。

### 2. 运行内置数据集

在 Benchmark 根目录执行：

```bash
python3 scripts/run_agent_benchmark.py \
  --manifest datasets/bugfix-v1/manifest.jsonl \
  --adapter devstar-runtime
```

命令按顺序处理三个用例，自动创建唯一运行编号。无需手动创建测试仓库、填写 `repository_id` 或输入 Token。模型调用会消耗所配置 Provider 的额度。

先测试一个用例时，在上述命令末尾加上 `--case pagination-boundary`。

### 3. 查看结果

每个用例会输出准备工作区、等待 Agent、验证补丁和最终状态。全部通过时，末尾输出类似：

```text
run=<run-id> passed=3/3 pass_rate=100.0%
url-host-validation: passed
tenant-cache-isolation: passed
pagination-boundary: passed
```

实际结果取决于 Agent 和模型。将输出中的运行编号替换到下面命令：

```bash
python3 -m json.tool results/<run-id>/score.json
python3 -m json.tool results/<run-id>/cases/pagination-boundary/result.json
```

`patches/` 保存修复 diff，`cases/<case-id>/logs/` 保存独立验证的测试日志。全部通过返回退出码 `0`，存在未通过用例返回 `1`。

## 测评什么

主数据集 **Bugfix-v1** 包含三个仓库维护的最小缺陷项目：

| 用例 | 原始缺陷 | 修复后检查 | 保持不变的功能 |
| --- | --- | --- | --- |
| `url-host-validation` | 将 `evil-example.com` 误判为合法主机 | 拒绝后缀伪装域名 | 精确域名、真实子域名、非法 URL 处理 |
| `tenant-cache-isolation` | 不同租户复用同一资源 ID 的权限缓存 | 按租户隔离权限 | 同租户缓存复用、其他资源未命中 |
| `pagination-boundary` | 每页多取一条，相邻页面重叠 | 满页之间不重复 | 空结果、非法参数处理 |

源码和测试位于 `datasets/bugfix-v1/fixtures/`；问题描述、源码位置和验证命令位于 `datasets/bugfix-v1/manifest.jsonl`。分数范围是这三个公开用例，不代表大型真实项目的整体修复能力。

另外两类资源分开使用：

- `datasets/smoke/`：提供已知补丁，检查评分器，不计作 Agent 能力分数。
- `datasets/swe-bench-lite/`：保存业界用例 ID 选择，下载与官方评分用于可选对照。Bugfix-v1 不依赖它，也不需要官方 harness 或 Docker-in-Docker。

## 文件架构

```text
datasets/
  bugfix-v1/
    manifest.jsonl             用例定义和可执行验证命令
    fixtures/                  缺陷源码与测试
    README.md                  用例范围
  smoke/                       评分器自检用例与已知补丁
  swe-bench-lite/               可选上游用例 ID 列表
scripts/
  run_agent_benchmark.py        主入口：调用 Agent、收集 patch、评分
  fetch_swe_bench.py            下载可选上游数据
  run_swe_bench_agent.py        为上游用例生成 patch
  grade_swe_bench.py            对接可选官方 harness
src/bugfix_benchmark/
  catalog.py / models.py        解析 manifest，定义用例与结果
  workspace.py                 复制 fixture 或克隆外部源码
  runtime_adapter.py           调用当前 DevStar 实例，等待结果
  agent_runner.py              通过命令行接入其他 Agent
  verifier.py                  重建基线、应用 patch、执行测试
  runner.py / cli.py           已有 patch 验证与结果汇总
docs/DATASETS.md                数据来源、版本和维护规范
tests/                         runner、adapter 和评分器测试
```

## Runtime 调用链路

```text
Web Terminal 批处理命令
  → 读取 manifest，为 case 准备独立源码目录
  → 用当前实例凭据投递 /evaluate-case
  → Bugfix Agent 经统一 Runtime 接收任务，在该目录修复
  → Agent 回传包含 patch 的 artifact
  → runner 获取 patch，评分器重建原始源码并独立验证
  → 保存单例结果，汇总 score.json
```

Adapter 使用平台注入的 `DEVSTAR_TOKEN` 和 `DEVSTAR_PLATFORM_URL`（或 `DEVSTAR_BASE_URL`），通过 HTTP 调用：

| 请求 | 作用 |
| --- | --- |
| `POST /-/agent-services/instances/dispatch` | 发送 `target_self=true` 的 `/evaluate-case` 任务，携带用例和工作目录 |
| `GET /-/agent-services/events/{event_id}/result` | 轮询任务状态，读取成功结果中的 `artifact.patch` |

被测对象是**当前终端所属的 Bugfix Agent 实例**。要测另一个实例，就打开另一个实例的终端运行命令。平台按项目提供模型配置，终端不需另填模型 Key。

Benchmark 和 Agent 模板代码处于同一实例容器中，职责分开：Benchmark 提供评测上下文，模板保存 Agent 实现。每个 case 使用临时源码目录，不直接修改用例原文件。评分器随后重建该目录，按原始代码复验 patch，不采用 Agent 自报的“测试通过”。这是工作目录隔离，不是每个 case 独立的安全容器。

## 数据定义与扩展

Manifest 支持 JSONL（每行一个用例）或 JSON 数组。分页用例的格式如下：

```json
{
  "case_id": "pagination-boundary",
  "repository": "bugfix-v1/pagination",
  "source_path": "datasets/bugfix-v1/fixtures/pagination",
  "base_commit": "fixture-v1",
  "problem_statement": "page_slice 多取下一页的一条数据。每页最多返回 page_size 条，并保留空结果和非法参数处理。",
  "fail_to_pass": [
    "python3 -m unittest -v tests.test_paging.PagingTests.test_full_pages_do_not_overlap"
  ],
  "pass_to_pass": [
    "python3 -m unittest -v tests.test_paging.PagingTests.test_empty_result",
    "python3 -m unittest -v tests.test_paging.PagingTests.test_invalid_arguments"
  ],
  "protected_paths": ["tests"]
}
```

| 字段 | 含义 |
| --- | --- |
| `case_id` | 稳定、唯一的用例编号，也是输出文件名的来源 |
| `repository` | 源码项目标识，不是 DevStar 仓库 ID |
| `source_path` | 内置源码相对 Benchmark 根目录的位置 |
| `source_url` | 外部源码 Git 地址；使用外部源码时替代 `source_path` |
| `base_commit` | 外部仓库固定提交；本地 fixture 用版本标识，实际内容由 Benchmark 提交固定 |
| `problem_statement` | 提供给 Agent 的缺陷描述与期望行为 |
| `fail_to_pass` | 基线应失败、修复后应通过的可执行命令 |
| `pass_to_pass` | 基线和修复后都应通过的回归命令 |
| `protected_paths` | 不允许 patch 修改的测试文件或目录 |

新增数据集时，在 `datasets/<dataset-name>/` 放置 manifest、来源说明和最小源码 fixture，通过 `--manifest` 选择。外部项目使用 `source_url` 和固定提交，由 runner 自动克隆；当前 runner 不自动安装各项目依赖，需提前准备测试工具和依赖。

验证命令应针对确定的测试。评分器依据退出码判定，环境缺依赖也可能产生非零退出码，因此维护用例时必须检查基线日志，确认失败来自预期缺陷。SWE-bench 测试标识不是可执行命令，不能直接填入本评分器的命令列表。

新增 Agent 通过 adapter 接入，保持用例与评分规则一致。详见[数据维护规范](docs/DATASETS.md)。

## 评分规则与结果

一个 case 同时满足以下条件才计为 `passed`：

1. 原始源码上，每条 FAIL_TO_PASS 命令失败，每条 PASS_TO_PASS 命令通过。
2. patch 非空，不修改受保护测试或生成文件，并能成功应用。
3. 应用 patch 后，每条 FAIL_TO_PASS 命令通过。
4. 每条 PASS_TO_PASS 命令仍通过。

总分是 `pass_rate = passed / total`。JSON 保存 0 到 1 的比例，终端以百分数展示。调用失败保留在分母中，应同时报告失败类型，不把通信故障解读成修复能力结论。

```text
results/<run-id>/
  score.json                   总数、通过数、失败数、通过率、各用例结果
  patches/<case-id>.patch       Agent 修复补丁
  cases/<case-id>/
    case.json                  发给 Agent 的用例内容
    artifact.json              成功获取的 patch、adapter 与调用元数据
    result.json                状态、失败原因、测试证据
    agent.patch                交给评分器的补丁
    workspace/                 评分后的源码目录
    logs/                      基线、补丁应用、修复和回归测试日志
```

调用失败时 patch 文件为空，可能没有 artifact 或测试日志。结果保存在运行环境，不会自动提交或上传。`results/` 和 `.benchmark/` 已被 Git 忽略；分享结果前检查日志、路径和源码是否包含敏感信息。

| 状态 | 含义 |
| --- | --- |
| `passed` | 修复与回归测试满足要求 |
| `agent_failed` | 准备或调用 Agent 阶段异常，先读 `failure_reason` |
| `no_patch` | 评分器收到空补丁；批处理 adapter 拒绝空产物时记录为 `agent_failed` |
| `workspace_failed` | 评分阶段无法准备源码 |
| `baseline_invalid` | 基线不符合定义，检查测试、依赖、源码版本 |
| `patch_rejected` | 修改了受保护或生成文件 |
| `patch_apply_failed` | 无法应用到原始源码 |
| `fail_to_pass_failed` | 缺陷测试仍失败 |
| `pass_to_pass_failed` | 已有功能发生回归 |

### 常用参数

| 参数 | 用途 / 默认值 |
| --- | --- |
| `--manifest` | 必填，选择数据集 |
| `--adapter devstar-runtime` | 调用当前 DevStar 实例；脚本默认是 `command`，平台模式必须显式指定 |
| `--case <case-id>` | 指定用例，可重复指定 |
| `--max-cases N` | 运行筛选后的前 N 个 |
| `--run-id <name>` | 自定义运行编号，默认自动生成，不可复用已有结果目录 |
| `--results-dir <path>` | 默认 `results` |
| `--repository-root <path>` | fixture 路径解析根目录，默认当前目录 |
| `--agent-timeout <seconds>` | 每个 Agent 任务等待上限，默认 900 秒 |
| `--command-timeout <seconds>` | 每条验证命令超时，默认 600 秒 |

## 常见问题

- **HTTP 404**：平台缺少上述 Runtime 接口，需部署配套版本。
- **缺少实例 Token 或平台 URL**：打开已启动 Bugfix Agent 的终端，不要在普通本地终端使用 Runtime adapter；不要公开凭据。
- **一直 waiting for Agent**：检查实例在线状态、模型配置和容器日志；到达 `--agent-timeout` 后记为失败。
- **修改后仍执行旧代码**：已有实例不会自动加载新模板进程，需要同步代码并更新/重启实例。
- **不能重用 run-id**：省略 `--run-id` 创建新目录，保留旧结果便于比较。

## 可选：命令行接入其他 Agent

命令 adapter 每个 case 启动一次进程，工作目录就是该 case 的源码目录，通过环境变量交接：

| 变量 | 作用 |
| --- | --- |
| `BENCHMARK_CASE_FILE` | 当前用例 JSON 的绝对路径 |
| `BENCHMARK_WORKSPACE` | 待修复源码目录 |
| `BENCHMARK_ARTIFACT_FILE` | Agent 必须写出的产物 JSON 路径 |
| `BENCHMARK_CASE_ID` | 当前用例编号 |

Agent 命令需退出码为 0，并写出 `{"patch": "diff --git ..."}` 格式的产物。命令不经 shell 解释，其中的模块或程序需能从 case 目录访问。先安装、配置对应 Agent，再执行；例如已安装 Bugfix Agent CLI 时：

```bash
python3 scripts/run_agent_benchmark.py \
  --manifest datasets/bugfix-v1/manifest.jsonl \
  --adapter command \
  --agent-command "python3 -m bugfix_agent.evaluate"
```

此路径的模型凭据由对应 CLI 配置，不使用平台自动注入的模型配置。

## 可选：SWE-bench 对照

上游数据下载、patch 生成和官方验证使用独立脚本。以选取 30 个 Lite 用例为例：

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e '.[datasets]'

python3 scripts/fetch_swe_bench.py \
  --instances-file datasets/swe-bench-lite/sample-30.txt \
  --output .benchmark/datasets/swe-bench-lite-sample-30.jsonl \
  --ids-output .benchmark/datasets/swe-bench-lite-sample-30.txt

python3 scripts/run_swe_bench_agent.py \
  --dataset-file .benchmark/datasets/swe-bench-lite-sample-30.jsonl \
  --instances-file .benchmark/datasets/swe-bench-lite-sample-30.txt \
  --agent-command "python3 -m bugfix_agent.evaluate" \
  --results-dir results \
  --run-id swe-lite-30

python3 scripts/grade_swe_bench.py \
  --instances-file results/swe-lite-30/instances.txt \
  --patch-dir results/swe-lite-30/patches \
  --model-name my-bugfix-agent \
  --run-id swe-lite-30 \
  --allow-empty \
  --dry-run
```

运行 Agent 前须按上一节安装并配置 CLI。最后一步先查看官方命令；实际评分需另行安装 [SWE-bench harness](https://github.com/SWE-bench/SWE-bench) 和 Docker 运行环境，再去掉 `--dry-run`。下载时使用 `--all` 可获取完整 Lite 测试集；生成 patch 时不指定选择文件，评分时使用该次运行生成的 `instances.txt`。官方对照与 Bugfix-v1 分数分别报告。

## 维护与自检

只检查评分器、不启动 Agent 时：

```bash
PYTHONPATH=src python3 -m bugfix_benchmark run \
  --manifest datasets/smoke/manifest.jsonl \
  --repository-root . \
  --adapter patch-dir \
  --patch-dir datasets/smoke/patches \
  --results-dir results
```

预期 `python-average: passed`，这是已知补丁自检，不是 Agent 分数。

开发检查：

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 -m compileall -q src scripts tests
```

提交源码、用例、测试和文档，不提交本地路径、密钥、克隆目录或运行产物。记录 Benchmark 提交、Agent 版本、模型及配置、运行参数，才能复现分数。测试会执行项目代码，未知来源的用例应在合适的隔离环境运行。
