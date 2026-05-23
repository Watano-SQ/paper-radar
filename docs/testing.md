# 验证与运行

本文档是 Paper Radar 验证命令、运行流程和测试入口的权威来源。

## 原则

- 每次任务只运行与当前任务最相关的最小验证子集。
- 如果跳过验证，必须说明原因。
- 不要在多个文档中重复维护命令；其他文档只链接或简短引用本文件。
- 涉及外部 API 的命令可能产生网络请求、写入 `data/` 和 `logs/`，运行前检查 `config/sources.yaml`。
- V0.6.5 起，默认运行路径由 `config/app.yaml` 和 runtime 环境变量解析；默认本地路径保持不变。
- V0.7 起，周候选池报告默认使用 `config/scoring.yaml` 做透明规则评分和 lane balance。
- V0.7.1 起，可通过 score audit 报告检查真实候选池上的评分校准表现。
- V0.7.2 起，可先运行 source preview 检查启用/禁用来源、计划查询和限额；主流程默认不会用空结果覆盖当前候选导出。

## 环境准备

```bash
uv sync --extra dev
```

如果不使用 `uv`，需要人类补充替代安装流程。

## 测试

运行完整测试：

```bash
uv run --extra dev pytest -q
```

运行单个测试文件：

```bash
uv run --extra dev pytest -q tests/test_store.py
```

运行 runtime 路径相关测试：

```bash
uv run --extra dev pytest -q tests/test_runtime_config.py tests/test_weekly_candidates.py tests/test_diagnostics.py
```

运行 scoring / report 相关测试：

```bash
uv run --extra dev pytest -q tests/test_scoring.py tests/test_weekly_candidates.py
```

运行 score audit 相关测试：

```bash
uv run --extra dev pytest -q tests/test_score_audit.py tests/test_scoring.py tests/test_weekly_candidates.py
```

运行 source preview / empty export 相关测试：

```bash
uv run --extra dev pytest -q tests/test_main_pipeline.py tests/test_runtime_config.py
```

## 本地抓取

预览来源配置和计划查询，不访问网络、不写入抓取产物：

```bash
uv run python -m src.main --source-preview
```

`--dry-run` 是同一预览路径的别名：

```bash
uv run python -m src.main --dry-run
```

运行主流程：

```bash
uv run python -m src.main
```

该命令会根据 `config/sources.yaml` 启用的来源进行抓取，可能写入：

- `data/papers.sqlite`
- `data/raw/`
- `data/exports/`
- `logs/`

如果本次运行没有收集到任何候选，V0.7.2 起默认会跳过当前 candidate export 写入，避免覆盖已有导出。只有明确需要空 JSONL 文件时才使用：

```bash
uv run python -m src.main --allow-empty-export
```

可显式指定配置目录：

```bash
uv run python -m src.main --config-dir config
```

## 诊断

检查本地数据库和候选集状态：

```bash
uv run python -m src.diagnostics
```

可显式指定配置目录：

```bash
uv run python -m src.diagnostics --config-dir config
```

## 周候选池报告

从候选 JSONL 生成 Markdown 报告：

```bash
uv run python -m src.report.weekly_candidates
```

默认读取 `data/exports/` 中当前周或最新的 `candidates_*.jsonl`，并输出到 `data/reports/`。
V0.7 起，默认会对候选项执行规则评分、lane balance，并在报告中写入 candidate level、radar score、score reasons 和 penalties。

可显式指定配置目录：

```bash
uv run python -m src.report.weekly_candidates --config-dir config
```

生成 reject/downrank 调试日志：

```bash
uv run python -m src.report.weekly_candidates --write-reject-log
```

使用旧的元数据完整度排序近似路径：

```bash
uv run python -m src.report.weekly_candidates --no-scoring
```

也可继续显式指定输入输出：

```bash
uv run python -m src.report.weekly_candidates --export-file data/exports/candidates_2026-W21.jsonl --output-dir data/reports
```

## Score Audit

从候选 JSONL 生成评分校准报告：

```bash
uv run python -m src.report.score_audit
```

默认读取当前周或最新的 candidate export，并输出到 `data/reports/score_audit_<YYYY-WW>.md`。

可显式指定配置目录、输入、输出和 lane limit：

```bash
uv run python -m src.report.score_audit --config-dir config
uv run python -m src.report.score_audit --export-file data/exports/candidates_2026-W21.jsonl
uv run python -m src.report.score_audit --output-dir data/reports
uv run python -m src.report.score_audit --per-lane 20
uv run python -m src.report.score_audit --compare-no-scoring
```

## Runtime 路径配置

默认本地输出路径维护在 `config/app.yaml`。相对路径按项目根目录解析，绝对路径保持不变。

支持的环境变量覆盖：

- `PAPER_RADAR_CONFIG_DIR`
- `PAPER_RADAR_DATA_DIR`
- `PAPER_RADAR_REPORTS_DIR`
- `PAPER_RADAR_EXPORTS_DIR`
- `PAPER_RADAR_LOGS_DIR`
- `PAPER_RADAR_DATABASE_PATH`

`config/app.yaml` 中的 `obsidian` 段目前只是未来兼容脚手架；当前命令不会写入 Obsidian vault。

## Scoring 配置

默认 scoring 配置维护在 `config/scoring.yaml`。如果该文件缺失，代码会使用保守默认配置，不会导致命令崩溃。

可配置内容包括：

- metadata、freshness、source quality、content signal 权重；
- `S_candidate`、`A_candidate`、`B_candidate`、`C_candidate` 阈值；
- lane balance 的每 lane 最大数量、活跃 lane 最小数量和全局最大数量；
- hard reject 行为；
- reject log 每个 reason 的最大条目数；
- review/survey 和 benchmark-only signal 词表。

候选级别只用于候选池报告，不代表最终阅读等级。

## 跳过验证的可接受原因

- 本次只修改文档，且没有改变命令、代码路径、配置语义或运行产物。
- 相关验证需要外部网络或 API key，而本次任务不需要触发实际抓取。
- 另一个并行线程正在修改会影响验证结果的文件；需要等待合并或确认后再运行。
