# AGENTS.md

## 仓库说明

Paper Radar 是一个合规的跨学科学术材料元数据抓取项目。仓库的目标不只是保存代码，也保存项目连续性：让中断后回来的人能恢复当前事实、设计边界、历史取舍和下一步行动。

当前真实主流程：

1. 通过 `config/topics.yaml` 定义兴趣 lane 和关键词/分类。
2. 通过 `config/sources.yaml` 控制各来源是否启用、请求限额、延迟和 API key 环境变量名。
3. 通过 `config/app.yaml` 控制本地运行路径、导出文件名模板和报告文件名模板。
4. 可通过 `src.main --source-preview` 或 `--dry-run` 离线检查启用/禁用来源、计划查询、限额和估算最大记录数。
5. 运行 `src.main` 后，启用的发现源抓取元数据并规范化为 `PaperItem`。
6. 元数据默认写入 `data/papers.sqlite`，原始响应默认写入 `data/raw/`，抓取状态写入 `crawl_runs`；这些路径由 runtime config 解析。
7. 可选 enrichment 源在已有条目基础上补全元数据。
8. 运行弱去重后默认导出 `data/exports/candidates_<YYYY-WW>.jsonl`；如果本次未收集任何候选，默认跳过导出以避免覆盖当前候选池，除非显式使用 `--allow-empty-export`。
9. weekly report 从 JSONL 候选池读取数据，按 `config/scoring.yaml` 做透明规则评分和 lane balance，生成候选池报告；可选生成 reject/downrank log。
10. score audit 从 JSONL 候选池读取数据，复用 scoring 和 lane balance，生成校准诊断报告。
11. 可通过 diagnostics 工具检查本地状态。

当前已经实现：

- `PaperItem` 统一数据模型；
- DOI、arXiv ID、标题规范化与 `canonical_id` 生成；
- OpenAlex、arXiv、PubMed、bioRxiv、medRxiv 来源客户端；
- Crossref、Semantic Scholar enrichment 客户端；
- SQLite 存储层，包含 `papers`、`paper_sources`、`crawl_runs`、`possible_duplicates`；
- 中央 runtime 配置层，包含 `AppPaths`、`RuntimeConfig` 和 `config/app.yaml`；
- 透明规则评分、lane balance、reject/downrank log；
- 原始响应保存、JSONL 导出、空导出保护、source preview、弱去重、诊断命令、周候选池 Markdown 报告、score audit Markdown 报告；
- pytest 测试入口。

当前不能声称已经实现：

- 不是机器学习推荐系统或最终阅读清单生成器；
- 不是完整阅读工作流系统；
- 不下载 PDF 全文；
- 不做 LLM 摘要；
- 不做 Telegram / Email 推送；
- 不做 Zotero / Obsidian / Anki 集成；
- 不抓 Google Scholar；
- 不做违反网站条款的 HTML scraping；
- OpenReview、CORE、IEEE 当前只在配置中保留占位或禁用项，不能声称已有可用抓取实现；
- GitHub Actions 定时抓取尚未建立。

## 必要检查

验证命令的权威来源维护在 `docs/testing.md`。

- 每次任务只运行与当前任务最相关的最小验证子集。
- 如果跳过验证，必须说明原因。
- 如果新增或修改验证命令、运行流程、预期产物或环境设置，应先更新 `docs/testing.md`，其他文档只做简短引用。

## 红线

- 不要声称代码没有实现的能力。
- 不要把计划中行为描述成当前现实。
- 不要进行无关的大型重构。
- 不要引入与项目目标无关的重型基础设施。
- 不要暴露密钥、API key、私人邮箱或敏感内容。
- 不要删除或重建数据，除非任务明确需要且风险已说明。
- 不要把 `docs/archive/` 中的归档内容重新当作当前事实源。
- 不要把一次性任务计划写进根文档、README 或架构文档。
- 不要把运行产物、缓存、日志、数据库文件作为长期事实源。
- 不要根据旧文件名、旧 README 片段或未提交实验推断当前能力。

## 参考文件

当前保留文档：

- `README.md`
- `docs/architecture.md`
- `docs/changes.md`
- `docs/testing.md`
- `docs/specs/_template.md`
- `docs/plans/_template.md`
- `data/AGENTS.md`

当前活跃设计说明：

- `docs/specs/v0.7.3-topics-scoring-calibration.md`

当前活跃执行计划：

- `docs/plans/v0.7.3-topics-scoring-calibration.md`

关键源码入口：

- `src/main.py`
- `src/app/config.py`
- `src/app/runtime.py`
- `src/models/paper.py`
- `src/pipeline/store.py`
- `src/pipeline/export.py`
- `src/pipeline/dedup.py`
- `src/diagnostics.py`
- `src/report/weekly_candidates.py`
- `src/report/score_audit.py`
- `src/ranking/`
- `src/sources/`
- `config/sources.yaml`
- `config/topics.yaml`
- `config/app.yaml`
- `config/scoring.yaml`
- `tests/`

参考文件列表必须随着活跃设计说明和执行计划组合变化而更新。

## 工作规则

- 建立事实时，优先依据代码、可运行命令和仓库文档，不要只依据推测。
- 改动应尽量局部，保持在当前任务边界内。
- 如果信息无法从代码或仓库文档中可靠得出，标记为“需要人类补充”，不要猜测。
- 保留文档是当前事实源。
- `docs/archive/` 只作为历史上下文。
- 如果任务改变了命令、文件布局、模块边界、数据结构、公开行为或长期工作流规则，必须更新对应的保留文档。
- 不要把一次性任务计划写进根文档。
- 任务意图放入 `docs/specs/`。
- 执行细节放入 `docs/plans/`。
- `docs/specs/` 与 `docs/plans/` 中，除 `_template.md` 外，只保留当前活跃的设计说明和执行计划组合。
- 被取代的设计说明和执行计划应移动到 `docs/archive/specs/` 与 `docs/archive/plans/`。
- 如果新的设计说明和执行计划取代旧的活跃组合，必须在同一变更中归档旧组合，并在 `docs/changes.md` 中记录取代关系。
- 如果项目确实需要多个并行活跃任务线，必须在 `AGENTS.md` 中明确并行规则、命名规则和事实源边界；否则默认只允许一个当前活跃组合。
- 执行计划正常完成后，不要把执行计划变成长期状态看板；持久结果和决策写入 `docs/changes.md`。

## 恢复协议

当项目中断后重新开始时：

1. 先读 `AGENTS.md`，恢复仓库规则和当前保留文档入口。
2. 再读 `docs/changes.md` 中最新且相关的条目，恢复近期决策和取代关系。
3. 再读 `docs/specs/` 中当前活跃设计说明，恢复任务意图和设计边界；如果不存在当前活跃设计说明，则记录“需要人类补充”。
4. 再读 `docs/plans/` 中当前活跃执行计划，恢复执行路线；如果不存在当前活跃执行计划，则记录“需要人类补充”。
5. 只有在需要理解历史原因、被拒绝方案或已取代设计时，才查 `docs/archive/`。
6. 不要从归档文件、旧文件名或过期计划中推断当前任务状态。
7. 如果执行计划中存在“如果中断”小节，优先读取该小节恢复上次停下的位置。
8. 如果无法判断当前状态，不要猜测，标记为“需要人类补充”。

## 文档同步规则

完成任何非平凡任务后，必须显式评估以下文件是否需要更新：

- `AGENTS.md`
- 相关的 `docs/specs/*.md`
- 相关的 `docs/plans/*.md`
- 归档或引用旧方案时，相关的 `docs/archive/specs/*.md` 或 `docs/archive/plans/*.md`
- 首次出现归档项或归档关系变化时，建立或更新 `docs/archive/INDEX.md`
- `docs/changes.md`
- `docs/architecture.md`
- 如果命令、验证流程、预期产物或环境设置改变，评估 `docs/testing.md`
- 如果贡献流程改变，评估 `.github/CONTRIBUTING.md`
- 如果目录级规则改变，评估相关局部 `AGENTS.md`
- 如果 README 中的入口说明、运行方式、能力边界或关键文档入口变化，评估 `README.md`

只更新事实源确实发生变化的文件。
