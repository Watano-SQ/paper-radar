# 变更与决策

> 本文档按照日期倒序记录，也即最新日期在前。

## 2026-05-19

### 决策

落地 V0.6 的最小有用版本，并同步保留文档。

- 为什么：
  - 当前使用场景需要从更多合规学术元数据来源构建候选池，特别是生命科学、医学和神经认知相关来源。
  - 周候选池需要先作为筛选输入，而不是直接形成阅读清单或 LLM 排名结果。
  - 根 `AGENTS.md` 已要求非平凡任务后同步长期事实源，避免 README、架构文档和测试入口互相漂移。

- 决定：
  - 新增 PubMed 发现源，通过 NCBI E-utilities 获取 PMID 和元数据，不抓取 HTML。
  - 新增 bioRxiv 和 medRxiv 发现源，通过官方 API 获取近期记录，并按 lane 关键词在本地过滤。
  - 新增 `src.report.weekly_candidates`，从 JSONL export 生成轻量 Markdown 候选池报告。
  - 保持 Crossref 和 Semantic Scholar 为 enrichment-only。
  - 保持新发现源默认关闭，由 `config/sources.yaml` 显式启用。
  - 报告 Markdown 属于运行产物，默认不提交；仓库只保留 `data/reports/.gitkeep`。

- 已实现：
  - `src/sources/pubmed.py`
  - `src/sources/biorxiv.py`
  - `src/report/weekly_candidates.py`
  - `tests/test_pubmed.py`
  - `tests/test_biorxiv.py`
  - `tests/test_weekly_candidates.py`
  - `config/sources.yaml` 中的 `pubmed`、`biorxiv`、`medrxiv` 保守默认配置。
  - `README.md`、`docs/architecture.md` 和本文档已同步当前事实。

- 已拒绝的替代方案：
  - 拒绝 PDF 下载、Zotero / Obsidian / Anki 集成、LLM 摘要或排序，因为这些不是 V0.6 边界。
  - 拒绝 publisher HTML scraping 和 Google Scholar scraping。
  - 拒绝为报告引入重型依赖或数据库扩展。

- 接受的风险或债务：
  - bioRxiv / medRxiv 当前使用简单关键词匹配过滤，后续可能需要更精细的 lane 匹配策略。
  - 未运行真实联网抓取验证；当前验证覆盖 mocked source normalization、过滤、报告生成和现有测试。
  - OpenReview、CORE、IEEE 仍只是未实现或禁用的未来方向。

- 验证：
  - `uv --cache-dir .uv-cache run --extra dev pytest -q` 通过，结果为 24 passed。
  - 默认 `uv run --extra dev pytest -q` 在当前本地沙箱中曾遇到 uv cache 权限问题，因此验证使用工作区本地 cache。

### 决策

建立轻量的断点恢复文档结构，并把保留文档定义为当前事实源。

- 为什么：
  - 项目会因为时间、精力、工具额度、课程或外部任务被中断，需要能快速恢复当前事实和设计判断。
  - 仓库已有代码、配置、测试和运行产物，但缺少统一的恢复入口、文档同步规则和决策日志。
  - 当前存在并行线程正在处理 README，因此需要避免覆盖并发修改，同时先建立其他事实源。

- 决定：
  - 新增根 `AGENTS.md` 作为仓库级工作规则入口。
  - 新增 `docs/architecture.md` 记录当前真实架构。
  - 新增 `docs/testing.md` 作为验证命令权威来源。
  - 新增 `docs/specs/_template.md` 和 `docs/plans/_template.md`。
  - 新增 `data/AGENTS.md`，约束运行数据、原始响应、导出和本地数据库的修改风险。
  - 当前尚无活跃设计说明和活跃执行计划；需要人类补充或在第一个明确任务中创建。

- 已实现：
  - 建立 `docs/specs/`、`docs/plans/`、`docs/archive/specs/`、`docs/archive/plans/` 目录。
  - 写入仓库级规则、恢复协议、文档同步规则、真实架构和验证命令。
  - 没有创建 `<当前任务名>.md` 占位文件。
  - 没有创建 `docs/archive/INDEX.md`，因为当前没有归档项。
  - 没有创建 `.github/CONTRIBUTING.md`，因为当前未发现贡献流程或自动化协作约束。
  - 未修改 `README.md`，因为用户说明另一个线程正在更改该文件。

- 已拒绝的替代方案：
  - 拒绝创建重型项目管理系统，因为当前需求是轻量事实源机制。
  - 拒绝强行创建活跃设计说明或执行计划，因为当前没有明确第一个任务。
  - 拒绝把归档索引提前建成空表，因为当前尚无归档关系。
  - 拒绝覆盖 README，因为存在并行修改风险。

- 接受的风险或债务：
  - README 可能暂时与新文档入口不完全同步，需要并行线程完成后重新评估。
  - 当前没有活跃设计说明/执行计划，恢复时需要人类补充下一步任务意图。
  - 数据保留策略、报告产物是否提交和发布流程仍需要人类补充。

- 后续：
  - 等 README 并行修改完成后，评估是否补充关键文档入口、当前能力边界和最小运行方式。
  - 第一个明确任务开始时，在 `docs/specs/` 和 `docs/plans/` 中创建真实任务命名的活跃组合。
  - 首次归档活跃组合时，建立 `docs/archive/INDEX.md` 并记录取代关系。
