# 验证与运行

本文档是 Paper Radar 验证命令、运行流程和测试入口的权威来源。

## 原则

- 每次任务只运行与当前任务最相关的最小验证子集。
- 如果跳过验证，必须说明原因。
- 不要在多个文档中重复维护命令；其他文档只链接或简短引用本文件。
- 涉及外部 API 的命令可能产生网络请求、写入 `data/` 和 `logs/`，运行前检查 `config/sources.yaml`。

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

## 本地抓取

运行主流程：

```bash
uv run python -m src.main
```

该命令会根据 `config/sources.yaml` 启用的来源进行抓取，可能写入：

- `data/papers.sqlite`
- `data/raw/`
- `data/exports/`
- `logs/`

## 诊断

检查本地数据库和候选集状态：

```bash
uv run python -m src.diagnostics
```

## 周候选池报告

从候选 JSONL 生成 Markdown 报告：

```bash
uv run python -m src.report.weekly_candidates
```

默认读取 `data/exports/` 中当前周或最新的 `candidates_*.jsonl`，并输出到 `data/reports/`。

## 跳过验证的可接受原因

- 本次只修改文档，且没有改变命令、代码路径、配置语义或运行产物。
- 相关验证需要外部网络或 API key，而本次任务不需要触发实际抓取。
- 另一个并行线程正在修改会影响验证结果的文件；需要等待合并或确认后再运行。
