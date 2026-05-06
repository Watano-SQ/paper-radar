# Paper Radar

Paper Radar 是一个合规的跨学科学术材料元数据抓取项目。

当前版本是 V0.5：从官方 API / 公开接口抓取论文或学术材料的元数据，统一成 `PaperItem`，写入 SQLite，做少量 DOI / 引用元数据补全，标记疑似重复，并导出 JSONL 候选集。

## 当前能做什么

V0.5 已实现：

- 定义统一数据模型 `PaperItem`
- 规范化 DOI、arXiv ID、标题，并生成 `canonical_id`
- 使用 SQLite 保存论文元数据
- 使用 `papers`、`paper_sources`、`crawl_runs`、`possible_duplicates` 记录主数据、来源、运行状态和疑似重复
- 从 OpenAlex 按关键词抓取近期论文元数据
- 从 arXiv 官方 API 按关键词和分类抓取近期预印本元数据
- 解析 OpenAlex 的 `abstract_inverted_index`
- 解析 arXiv Atom XML
- 使用 Crossref 按 DOI 做 enrichment
- 使用 Semantic Scholar 按 DOI 或 arXiv ID 做 enrichment
- 保存原始 API 响应到 `data/raw/`
- 导出候选集 JSONL 到 `data/exports/`
- 提供 pytest 覆盖 ID 规范化、模型序列化、OpenAlex abstract 还原、SQLite upsert、crawl runs、enrichment normalize、弱去重

## Enrichment 的边界

Crossref 和 Semantic Scholar 在当前版本中是 enrichment source，不是发现源。

这意味着：

- Crossref 只处理数据库里已有 DOI 的条目
- Crossref 默认不做 keyword discovery
- Crossref 默认不做 title search
- Semantic Scholar 只处理已有 DOI 或 arXiv ID 的条目
- Semantic Scholar 默认不做 title search
- Semantic Scholar 默认要求 `S2_API_KEY`；如果开启但没有 key，会跳过并记录 warning
- enrichment 失败只会记录日志和 `crawl_runs`，不会中断整体流程

## 当前不做什么

V0.5 明确不做：

- 不抓 Google Scholar
- 不做违反网站条款的 HTML scraping
- 不下载 PDF 全文
- 不做 LLM 摘要
- 不做推荐排序
- 不做 Telegram / Email 推送
- 不做 Zotero / Obsidian / Anki 集成
- 暂不实现 PubMed、bioRxiv、OpenReview、CORE、IEEE
- 暂不启用 GitHub Actions 定时抓取

## 你需要做什么

### 1. 配置兴趣方向

编辑：

```bash
config/topics.yaml
```

项目用 `lane` 表示兴趣通道。每个 lane 可以配置：

- `keywords`：给 OpenAlex 和 arXiv keyword 查询使用
- `arxiv_categories`：给 arXiv 分类查询使用

### 2. 配置抓取限额

编辑：

```bash
config/sources.yaml
```

当前 OpenAlex / arXiv 默认值故意较小，方便先验证流程：

- OpenAlex：每个 lane 只取 1 个关键词，每个 query 取 10 条
- arXiv：每个 lane 取 1 个关键词和 1 个分类，每个 query 取 10 条

你可以后续逐步调大：

```yaml
per_query_limit: 20
max_total: 100
max_queries_per_lane: 2
```

### 3. 开启或关闭 enrichment

Crossref 和 Semantic Scholar 默认可以保持关闭。需要时在 `config/sources.yaml` 中开启：

```yaml
crossref:
  enabled: true

semantic_scholar:
  enabled: true
```

关闭时设为：

```yaml
enabled: false
```

### 4. 设置环境变量

建议设置 `CONTACT_EMAIL`，用于 OpenAlex 和 Crossref 的 polite pool：

```powershell
$env:CONTACT_EMAIL="your_email@example.com"
```

如果要启用 Semantic Scholar enrichment，建议设置 API key：

```powershell
$env:S2_API_KEY="your_semantic_scholar_api_key"
```

可选：

```powershell
$env:OPENALEX_API_KEY="your_openalex_api_key"
```

默认配置下，Semantic Scholar 的 `require_api_key: true`。没有 `S2_API_KEY` 时，即使 `semantic_scholar.enabled: true`，程序也会跳过 Semantic Scholar enrichment，避免无 key 模式连续请求导致 429。

### 5. 本地运行

推荐使用 `uv` 管理依赖和运行命令。第一次使用：

```bash
uv sync --extra dev
```

运行抓取：

```bash
uv run python -m src.main
```

### 6. 运行测试

```bash
uv run --extra dev pytest -q
```

### 7. 检查本地数据状态

运行只读 diagnostics 命令：

```bash
uv run python -m src.diagnostics
```

它会输出：

- `papers` 数量
- `paper_sources` 数量
- `crawl_runs` 按 source/status 分组
- `possible_duplicates` 数量
- 最新 JSONL export 文件路径

## 输出文件

运行后会生成：

- `data/raw/<source>/<YYYY-WW>/...`：原始 API 响应文件
- `data/papers.sqlite`：SQLite 数据库
- `data/exports/candidates_<YYYY-WW>.jsonl`：统一格式候选集
- `logs/crawl_<YYYY-WW>.log`：抓取日志

这些运行产物默认不会提交到 Git，仓库只保留目录占位文件。

## 数据库结构

当前表：

- `papers`：按 `canonical_id` 存储论文主记录
- `paper_sources`：记录每条论文来自哪个 source、哪个 query、对应 raw 文件路径
- `crawl_runs`：记录每个 source/query 或 enrichment item 的运行状态
- `possible_duplicates`：记录疑似重复，不自动合并

## 后续路线

建议按这个顺序推进：

1. 让 V0.5 在小限额下稳定运行几轮
2. 调整 topics 和 source 限额
3. 增强 Crossref / Semantic Scholar 的字段覆盖和错误处理
4. 增加 GitHub Actions 每周定时运行
5. 增加 PubMed / bioRxiv / medRxiv / OpenReview / CORE / IEEE
6. 再考虑 LLM 摘要、推送、Zotero / Obsidian 集成

## 当前阶段的判断

这个项目现在适合做一件事：稳定、合规地收集和补全候选论文元数据。

它还不是推荐系统，也不是阅读工作流系统。现在最重要的是让数据层可靠，先积累结构干净、来源可追溯、可重复导出的候选集。
