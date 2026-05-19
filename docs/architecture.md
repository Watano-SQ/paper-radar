# 当前架构

本文档记录 Paper Radar 的当前真实架构，不记录理想架构或一次性执行计划。

## 仓库用途

Paper Radar 用于合规地收集跨学科学术材料元数据，把不同官方 API / 公开接口返回的记录规范化为统一 `PaperItem`，写入本地 SQLite，并导出可后续筛选的候选集。

仓库同时维护项目连续性文档，帮助中断后恢复当前事实、设计边界和执行规则。

## 当前主流程

1. `config/topics.yaml` 定义兴趣 lane、关键词和 arXiv 分类。
2. `config/sources.yaml` 定义来源启用状态、请求限额、延迟、API key 环境变量名和 enrichment 开关。
3. `src/main.py` 加载配置，创建 `PaperStore`，按来源构造查询。
4. 已启用的来源客户端抓取原始数据，并保存原始响应到 `data/raw/<source>/<YYYY-WW>/`。
5. 来源客户端将原始记录规范化为 `PaperItem`。
6. `PaperStore` 将条目 upsert 到 SQLite，并记录来源、查询、抓取状态。
7. Crossref 和 Semantic Scholar 可作为 enrichment 源处理已有条目，不作为默认发现源。
8. `src.pipeline.dedup` 对当前收集条目和历史库做弱去重，疑似重复写入 `possible_duplicates`。
9. `src.pipeline.export` 导出 `data/exports/candidates_<YYYY-WW>.jsonl`。
10. `src.diagnostics` 可读取 SQLite 和 exports 状态；`src.report.weekly_candidates` 可从 JSONL 导出生成周候选池 Markdown 报告。

## 主要模块与职责

- `config/`：维护兴趣方向、来源开关、请求限额和外部服务环境变量名。
- `src/main.py`：主编排入口，负责加载配置、运行来源、运行 enrichment、去重和导出。
- `src/models/paper.py`：统一论文元数据模型 `PaperItem`。
- `src/sources/`：外部来源客户端。当前包含 OpenAlex、arXiv、PubMed、bioRxiv、medRxiv、Crossref、Semantic Scholar。
- `src/pipeline/normalize.py`：规范化和最终化 `PaperItem`。
- `src/pipeline/store.py`：SQLite 存储层和表结构初始化。
- `src/pipeline/dedup.py`：疑似重复检测。
- `src/pipeline/export.py`：JSONL 候选集导出。
- `src/pipeline/logging_utils.py`：日志初始化。
- `src/pipeline/rate_limit.py`：简单请求延迟控制。
- `src/utils/`：日期、HTTP、ID 和文本工具。
- `src/diagnostics.py`：本地数据状态诊断。
- `src/report/weekly_candidates.py`：从候选 JSONL 生成周候选池 Markdown 报告。
- `tests/`：pytest 测试。

## 数据流

```text
config/topics.yaml + config/sources.yaml
  -> src.main builds SourceQuery values
  -> source clients fetch official/public APIs
  -> data/raw/<source>/<YYYY-WW>/ stores raw responses
  -> source clients normalize RawItem to PaperItem
  -> PaperStore upserts SQLite rows
  -> enrichment clients optionally update existing items
  -> weak dedup records possible_duplicates
  -> export_jsonl writes data/exports/candidates_<YYYY-WW>.jsonl
  -> diagnostics/report tools read local outputs
```

## 存储结构

当前 SQLite 表由 `src/pipeline/store.py` 初始化：

- `papers`：按 `canonical_id` 存储论文主记录。
- `paper_sources`：记录条目来源、source id、source query、抓取时间和 raw path。
- `crawl_runs`：记录每个 source/query 或 enrichment item 的运行状态。
- `possible_duplicates`：记录疑似重复，不自动合并。

运行产物：

- `data/papers.sqlite`：本地数据库，默认不提交。
- `data/raw/`：原始 API 响应，默认不提交具体抓取文件。
- `data/exports/*.jsonl`：候选集导出，默认不提交 JSONL。
- `data/reports/*.md`：周候选池报告输出，由报告命令生成，默认不提交；仓库只保留 `data/reports/.gitkeep`。
- `logs/*.log`：运行日志，默认不提交。

## 重要边界

- OpenAlex、arXiv、PubMed、bioRxiv、medRxiv 是发现源客户端，但是否运行由 `config/sources.yaml` 控制。
- Crossref、Semantic Scholar 当前是 enrichment 源，不是默认发现源。
- `possible_duplicates` 只记录疑似重复，不自动合并记录。
- 原始响应、数据库、导出和日志是运行产物，不是长期项目事实源。
- 当前文档事实源在保留文档中；`docs/archive/` 只提供历史上下文。

## 已知未完成部分

- OpenReview、CORE、IEEE 未实现可用客户端。
- GitHub Actions 定时抓取尚未建立。
- 多个并行活跃设计说明/执行计划的规则尚未建立，默认只允许一个当前活跃组合。
- 数据保留策略和发布流程需要人类补充。

## 当前非目标或限制

- 不抓 Google Scholar。
- 不做违反网站条款的 HTML scraping。
- 不下载 PDF 全文。
- 不做 LLM 摘要。
- 不做推荐排序。
- 不做 Telegram / Email 推送。
- 不做 Zotero / Obsidian / Anki 集成。
- 不把一次性执行计划写入 README、架构文档或根规则。
