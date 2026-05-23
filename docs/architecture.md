# 当前架构

本文档记录 Paper Radar 的当前真实架构，不记录理想架构或一次性执行计划。

## 仓库用途

Paper Radar 用于合规地收集跨学科学术材料元数据，把不同官方 API / 公开接口返回的记录规范化为统一 `PaperItem`，写入本地 SQLite，并导出可后续筛选的候选集。

仓库同时维护项目连续性文档，帮助中断后恢复当前事实、设计边界和执行规则。

## 当前主流程

1. `config/topics.yaml` 定义兴趣 lane、关键词和 arXiv 分类。
2. `config/sources.yaml` 定义来源启用状态、请求限额、延迟、API key 环境变量名和 enrichment 开关。
3. `config/app.yaml` 定义默认本地运行路径、导出文件名模板和报告文件名模板。
4. `config/scoring.yaml` 定义周候选池报告的规则评分、阈值、lane balance 和 reject log 行为。
5. `src.app.config` 加载 runtime config，解析 `AppPaths`；相对路径默认按项目根目录解析，绝对路径保持不变。
6. `src/main.py` 可先用 source preview 离线展示启用/禁用来源、计划查询、限额和估算最大记录数；该路径不访问网络也不写入抓取产物。
7. `src/main.py` 创建 `PaperStore`，按来源构造查询。
8. 已启用的来源客户端抓取原始数据，并默认保存原始响应到 `data/raw/<source>/<YYYY-WW>/`；raw 目录可通过 runtime config 改变。
9. 来源客户端将原始记录规范化为 `PaperItem`。
10. `PaperStore` 将条目 upsert 到 SQLite，并记录来源、查询、抓取状态。
11. Crossref 和 Semantic Scholar 可作为 enrichment 源处理已有条目，不作为默认发现源。
12. `src.pipeline.dedup` 对当前收集条目和历史库做弱去重，疑似重复写入 `possible_duplicates`。
13. `src.pipeline.export` 默认导出 `data/exports/candidates_<YYYY-WW>.jsonl`，目录和文件名模板可通过 runtime config 改变；如果本次收集为空，V0.7.2 起默认跳过导出以避免覆盖当前候选池，除非显式允许空导出。
14. `src.report.weekly_candidates` 从 JSONL 导出生成周候选池 Markdown 报告，默认使用 V0.7 规则评分、near-duplicate title suppression、lane balance 和可选 reject/downrank log。
15. `src.report.score_audit` 从 JSONL 导出生成评分校准报告，复用同一 scoring、near-duplicate title suppression 和 lane balance 逻辑，不修改 JSONL 或 SQLite。
16. `src.diagnostics` 可读取 SQLite 和 exports 状态。

## 主要模块与职责

- `config/`：维护兴趣方向、来源开关、请求限额、外部服务环境变量名和本地 runtime 路径。
- `config/app.yaml`：维护默认本地输出路径、数据库路径、文件名模板和未来 Obsidian 配置脚手架；当前不实现 Obsidian 写入。
- `config/scoring.yaml`：维护周候选池报告的规则评分权重、候选级别阈值、lane balance、reject 行为和报告细节设置。
- `src/app/config.py`：加载 `config/app.yaml`、`config/sources.yaml`、`config/topics.yaml`、`config/scoring.yaml`，解析 `AppPaths` 和 `RuntimeConfig`。
- `src/app/runtime.py`：根据 runtime 文件名模板构造候选导出路径和周报路径。
- `src/main.py`：主编排入口，负责离线 source preview、运行来源、运行 enrichment、去重和导出；`run_pipeline(runtime)` 可由 CLI 以外的代码调用，并返回 `PipelineResult`。
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
- `src/report/score_audit.py`：从候选 JSONL 生成 score audit Markdown 校准报告。
- `src/ranking/scoring.py`：规则评分、repository-like penalty 和候选级别计算。
- `src/ranking/balance.py`：duplicate canonical ID 处理、near-duplicate title suppression、lane balance、selected/rejected/downranked 决策。
- `src/ranking/rejects.py`：reject/downrank Markdown log 渲染。
- `tests/`：pytest 测试。

## 数据流

```text
config/app.yaml + config/topics.yaml + config/sources.yaml + config/scoring.yaml
  -> src.app.config builds RuntimeConfig and AppPaths
  -> src.main builds SourceQuery values
  -> source clients fetch official/public APIs
  -> runtime.paths.raw_dir/<source>/<YYYY-WW>/ stores raw responses
  -> source clients normalize RawItem to PaperItem
  -> PaperStore upserts SQLite rows
  -> enrichment clients optionally update existing items
  -> weak dedup records possible_duplicates
  -> export_jsonl writes runtime-configured JSONL candidate export when collected_ids is non-empty or empty export is explicitly allowed
  -> report scores and balances exported candidates at report time
  -> optional reject/downrank log is written under runtime reports dir
  -> optional score audit reports scoring behavior under runtime reports dir
  -> diagnostics reads local outputs
```

## 存储结构

当前 SQLite 表由 `src/pipeline/store.py` 初始化：

- `papers`：按 `canonical_id` 存储论文主记录。
- `paper_sources`：记录条目来源、source id、source query、抓取时间和 raw path。
- `crawl_runs`：记录每个 source/query 或 enrichment item 的运行状态。
- `possible_duplicates`：记录疑似重复，不自动合并。

运行产物：

- `data/papers.sqlite`：默认本地数据库，默认不提交；可通过 runtime config 改变。
- `data/raw/`：默认原始 API 响应目录，默认不提交具体抓取文件；可通过 runtime config 改变。
- `data/exports/*.jsonl`：默认候选集导出目录，默认不提交 JSONL；可通过 runtime config 改变。
- `data/reports/*.md`：默认周候选池报告输出目录，由报告命令生成，默认不提交；仓库只保留 `data/reports/.gitkeep`；可通过 runtime config 改变。
- `data/reports/rejected_candidates_*.md`：可选 reject/downrank 调试日志，默认不提交；可通过 runtime config 文件名模板改变。
- `data/reports/score_audit_*.md`：score audit 校准报告，默认不提交；可通过 runtime config 文件名模板改变。
- `logs/*.log`：默认运行日志目录，默认不提交；可通过 runtime config 改变。

## Runtime 配置

V0.6.5 引入 `RuntimeConfig` 和 `AppPaths`，把路径解析集中在 `src.app.config`。默认本地行为保持不变，但以下路径可在 `config/app.yaml` 中调整：

- `app.data_dir`
- `app.raw_dir`
- `app.exports_dir`
- `app.reports_dir`
- `app.logs_dir`
- `app.database_path`

相对路径默认解析到项目根目录下。绝对路径保持绝对路径。`PAPER_RADAR_CONFIG_DIR` 可切换配置目录；`PAPER_RADAR_DATA_DIR`、`PAPER_RADAR_REPORTS_DIR`、`PAPER_RADAR_EXPORTS_DIR`、`PAPER_RADAR_LOGS_DIR`、`PAPER_RADAR_DATABASE_PATH` 可覆盖主要运行路径。

`config/app.yaml` 中的 `obsidian` 段只是未来兼容脚手架。当前不会写入 Obsidian vault，也没有 Obsidian 插件实现。

## 规则评分与候选级别

V0.7 引入轻量、透明、可配置的 report-stage 规则评分层。评分只读取 JSONL 候选项中已有字段，不访问外部 API，不改变 SQLite schema，也不改变 JSONL export 格式。
V0.7.3 根据 2026-W21 真实周运行校准默认 topics 和 scoring：每个 lane 的首位 keyword 更窄，`S_candidate` 阈值提高，摘要存在本身的加分降低，缺失摘要惩罚加重。
V0.7.4 在 report-stage selection 中加入近重复标题抑制，并为 Zenodo-like / repository-like 记录增加可配置 penalty。被标题近重复规则压下的候选会进入 downranked，原因是 `Near-duplicate title`；这不修改 SQLite、JSONL export 或 source crawling。

评分结果包含：

- `S_candidate`
- `A_candidate`
- `B_candidate`
- `C_candidate`
- `reject`

这些只是周候选池报告中的候选级别，不是最终阅读等级。最终阅读清单或 13 项 weekly radar 仍需要后续人工或 LLM 筛选流程。

lane balance 会按配置限制每个 lane 的最大入选数量，并尝试为活跃 lane 保留最低候选数量。被硬拒绝、低于阈值、重复 canonical ID 或因 balance 未入选的候选可写入 reject/downrank log。

## Score Audit

V0.7.1 引入 `src.report.score_audit`，用于真实周运行后的评分校准。该命令读取已有 JSONL export，复用 runtime scoring 和 lane balance，输出 compact Markdown audit。报告包含 candidate level counts、lane/source stats、score component totals、penalty counts、near-threshold candidates、top/bottom selected candidates、rejected/downranked summary 和 deterministic calibration notes。

score audit 是分析层，不改变 source crawling、不修改 SQLite schema、不修改 JSONL export 格式，也不使用外部 API。

## 重要边界

- OpenAlex、arXiv、PubMed、bioRxiv、medRxiv 是发现源客户端，但是否运行由 `config/sources.yaml` 控制。
- Crossref、Semantic Scholar 当前是 enrichment 源，不是默认发现源。
- `possible_duplicates` 只记录疑似重复，不自动合并记录。
- source 客户端不负责发现项目根目录；需要写入 raw response 时只使用调用方传入的 `raw_dir`。
- V0.7 scoring 是规则评分，不是 LLM 排名或机器学习推荐系统。
- V0.7.1 score audit 是校准报告，不是推荐模型。
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
- 不做 LLM 推荐排序。
- 不做 Telegram / Email 推送。
- 不做 Zotero / Obsidian / Anki 集成。
- 不把一次性执行计划写入 README、架构文档或根规则。
