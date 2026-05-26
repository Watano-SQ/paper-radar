# Paper Radar Curation Guidelines

## 1. Purpose

Paper Radar 的目标不是生成“客观最优论文榜单”，而是为一个跨学科泛读者生成可审查的候选池。

当前用户不是某个单一专业领域的研究者。用户希望通过泛读逐步建立对以下领域的问题地图：

- embodied AI / robotics / vision-language-action
- symbol grounding / neuro-symbolic AI / semantics
- cognitive linguistics / metaphor / embodied cognition
- philosophy of mind / consciousness / self / imagination
- phenomenology-like questions around experience, language, perception, and world-structure
- AI, cognition, language, and literary imagination 的交叉地带

因此，curation 的目标不是简单判断“论文是否权威”，而是判断候选条目对用户当前知识结构的用途。

## 2. Boundary Between Paper Radar and Curation

Paper Radar 本体负责粗筛：

- 收集论文元数据
- 去重
- 基础降噪
- 标记 source、venue、abstract、score、penalties
- 生成 weekly report / score audit / reject log

Curation 负责精筛：

- 判断候选对用户是否有阅读价值
- 判断应以何种姿态处理该候选
- 区分“可靠知识入口”“前沿样本”“思想素材”“边缘理论”“暂不适合”“噪声”
- 给出简短理由和风险提示

不要把 curation 的判断全部硬编码进 `scoring.py` 或 `scoring.yaml`。  
代码层评分只能做粗筛；最终判断应由自然语言规范和人工/LLM 审查完成。

## 3. Reading Posture Categories

每条候选不应只给分数，而应归入一种阅读姿态。

### A. Knowledge-Structure Entry

适合认真读，用来建立一个领域的问题地图。

典型特征：

- 主题和用户长期兴趣高度相关；
- 摘要清楚说明研究问题、背景和贡献；
- 不要求用户已经掌握大量专业数学细节；
- 能帮助用户理解一个领域“在问什么问题”。

例子类型：

- symbol grounding 与 compositionality 的理论/实证论文；
- VLA / robotic manipulation / embodied AI 的综述性或问题导向论文；
- cognitive science / philosophy of mind 中问题边界清楚的论文或博士论文。

### B. Frontier Technical Sample

适合作为前沿样本略读，不必完全读懂技术细节。

典型特征：

- 是正规的 arXiv / 会议 / 期刊技术论文；
- 技术门槛较高，但主题能反映领域前沿趋势；
- 用户可读 title / abstract / introduction / discussion 来理解问题，不必深挖公式或实验细节。

例子类型：

- VLA model architecture；
- robot manipulation with 3D representations；
- tactile sensing for manipulation；
- model predictive control 与 AI 的交叉论文。

### C. Conceptual / Speculative Stimulus

可作为思想素材扫读，但不能直接当作可靠知识来源。

典型特征：

- 题目或摘要提出有趣的概念、隐喻、理论框架；
- 与 consciousness、symbol、meaning、self、worldline、ontology、semiotics、experience 等主题相关；
- 可能来自 Zenodo / OSF / personal manuscript / repository；
- 学术共同体认可度不明；
- 方法边界可能不清楚，但能激发问题意识或文学/哲学联想。

这类条目不应被自动删除。  
尤其在 `language_symbol` 和 `humanities_social` lane 中，这类条目可能对用户有启发价值。

但必须明确标注：

- speculative
- low reliability as knowledge source
- useful as idea material only
- do not treat as established scholarship

### D. Peripheral / Low-Reliability Theory

边缘理论或低可信材料。可保留为观察对象，但不建议进入本周重点阅读。

典型特征：

- 摘要呈现宏大统一理论姿态；
- 横跨意识、宇宙、AI、物理、本体论、信息、符号等多个大概念；
- 缺少清楚的问题边界、方法、证据或学术语境；
- 过度使用 totalizing language，如 “unified theory”“ultimate basis”“complete framework”“solves hard problem”；
- 来自 Zenodo / repository-like source；
- 更像个人理论手稿、项目宣言或体系化构想。

处理原则：

- 不自动等同于垃圾；
- 但不能当作可靠学术入口；
- 可以列为“扫读 / 观念素材 / 暂存”；
- 若候选池过多，应优先压低这类条目。

### E. Not Suitable Now

暂不适合当前用户阅读。

典型特征：

- 主题可能正规，但技术门槛过高；
- 依赖大量数学、物理、控制理论、泛函分析、微分几何、优化理论、PDE、MPC、Lyapunov、CBF 等前置知识；
- 即使论文质量高，用户目前也难以通过泛读获得有效理解；
- 与用户当前问题地图关系间接。

这类条目不应被判为“低质量”，而应标注为：

- technically valid but not currently accessible
- background radar only
- not a reading candidate now

尤其适用于 `math_physics_cs` 中大量控制理论、优化、数学物理论文。

### F. Noise / Duplicate / Repository Residue

不建议进入人工阅读。

典型特征：

- 明显重复标题；
- OpenAlex / arXiv mirror 重复；
- Zenodo 多 DOI 版本重复；
- 期刊介绍页、项目说明页、数据集文件、Excel 数据、仓储 metadata；
- 摘要缺失且无法判断内容；
- 与 lane 关键词只是表面匹配；
- 标题异常、乱码、明显非论文记录。

处理原则：

- 这类可以明确排除；
- 若只是 mirror duplicate，应保留质量更高或更直接的版本，通常优先 arXiv 或正式 publisher version；
- 不要让重复项占据 curated report。

## 4. Source and Venue Handling

### 4.1 arXiv

arXiv 条目通常可作为技术前沿样本，但不自动等于高质量。

优先级较高的 arXiv 条目：

- 摘要清楚；
- 问题意识明确；
- 与用户主线相关；
- introduction 可能帮助用户建立问题地图。

需要谨慎的 arXiv 条目：

- 过度数学化；
- 只解决非常窄的技术优化；
- 和用户兴趣仅由一个关键词弱连接。

### 4.2 OpenAlex

OpenAlex 是元数据聚合来源，不代表论文质量。  
OpenAlex 可能聚合：

- 正式期刊论文；
- arXiv mirror；
- Zenodo 条目；
- repository 条目；
- 会议论文；
- 学位论文；
- 项目材料。

Curation 时必须结合 venue、URL、DOI、abstract 判断条目类型。

### 4.3 Zenodo / OSF / Figshare / Repository-like Sources

Repository-like 条目不应一律删除。

它们可能是：

- 预印本；
- 数据集；
- 软件；
- 项目说明；
- 版本化手稿；
- 个人理论文本；
- 补充材料。

处理原则：

1. 如果是数据集 / Excel / 纯 repository metadata：通常归为 Noise。
2. 如果是清楚的论文手稿，但未经同行评审：归为 Conceptual / Speculative Stimulus 或 Peripheral Theory。
3. 如果主题高度贴合用户兴趣，可保留为思想素材，但必须标低可信。
4. 如果只是正式论文的重复镜像，优先保留正式版本或 arXiv 版本。
5. 不应因为 Zenodo 一词自动排除；但也不应让 Zenodo 条目冒充可靠学术入口。

## 5. Lane-Specific Guidelines

### 5.1 core_embodied_ai

此 lane 当前质量较高。优先保留：

- robot manipulation
- vision-language-action models
- tactile sensing
- 3D representation for manipulation
- embodied world models
- vision-language navigation
- spatial grounding
- perception-action loop

适合用户的原因：

- 能连接 AI、认知、语言指令、行动、空间感知、具身性；
- 即使不懂全部技术细节，也能通过 abstract / introduction 理解研究问题。

降优先级：

- 纯工具库；
- 自动泊车、无人机检测、侧信道安全等窄工程应用；
- 与 embodied cognition / action grounding 关系较弱的机器人应用。

### 5.2 language_symbol

此 lane 不应只按“主流可靠性”筛选，因为用户对语言、符号、意义、意识、隐喻框架、认知语言学、现象学式问题有强兴趣。

优先保留：

- symbol grounding
- compositionality
- neuro-symbolic AI
- semantics
- cognitive linguistics
- language evolution
- embodied meaning
- relation between symbol, perception, and action

特殊处理：

- speculative symbol / meaning / consciousness 条目可以保留为思想素材；
- 但必须区分“思想刺激”与“可靠知识”；
- 不要因为 Zenodo 自动删除；
- 也不要因为标题诱人就归为知识入口。

推荐输出中应明确标注：

- reliable knowledge entry
- technical formal logic item
- speculative idea material
- low-reliability macro-theory
- duplicate / repository residue

### 5.3 humanities_social

此 lane 应优先保留能连接用户长期兴趣的问题型材料：

- imagination and self
- philosophy of mind
- consciousness
- phenomenology
- temporality and spatiality
- cognition and culture
- metaphor / literary imagination / world-structure

谨慎处理：

- 泛泛哲学史论文；
- 过于宏大的个人理论；
- 缺少学术共同体语境的 Zenodo 手稿；
- 只因 cognitive science 字段命中而进入的弱相关条目。

### 5.4 neuro_cognitive

当前 OpenAlex + predictive coding neuroscience 的结果质量不稳定。  
优先保留：

- 正式期刊或可靠预印本；
- predictive coding / active inference / neural coding / cognitive architecture；
- 能帮助用户理解认知科学问题地图的论文。

谨慎处理：

- Zenodo 上的统一心智理论；
- 个人理论手稿；
- 心理学/教育数据集；
- 只在 abstract 中泛泛提到 predictive processing 的材料。

如果该 lane 长期质量不足，可考虑后续小规模启用 PubMed，但不应在 curation 阶段自行改 source config。

### 5.5 math_physics_cs

此 lane 当前不应作为用户的主要论文阅读来源。

用户当前反馈：数学/物理/控制理论类论文大多看不懂。  
因此该 lane 应被视为 background radar，而不是 main reading lane。

优先保留：

- 与 AI / cognition / robotics 有明确桥接关系的材料；
- introduction 可以帮助用户理解控制、优化、动力系统的问题意识；
- 不过度依赖专业数学细节的论文。

通常降为 Not Suitable Now：

- PDE control
- nonlinear control theory
- Lie superalgebra
- manifold optimization
- semi-smooth Newton method
- boundary control
- highly technical MPC / CBF / Lyapunov papers

注意：这类论文可能质量很高，但不适合当前用户泛读。

## 6. Curation Output Format

每次 curation 不要输出过长摘要。目标是辅助人工审查。

建议输出结构：

```markdown
# Curated Candidate Review: <week>

## Overall Diagnosis

- 本周候选池总体质量
- 哪些 lane 表现好
- 哪些 lane 噪声多
- 是否建议调整 topics / scoring / source
- 是否建议进入实际阅读

## Recommended Shortlist

列出最值得进入人工阅读候选的 5-10 条。

每条格式：

### <title>

- Lane:
- Source:
- Reading posture:
- Why it matters:
- Risk / limitation:
- Suggested action:

Reading posture 必须使用以下之一：

- Knowledge-Structure Entry
- Frontier Technical Sample
- Conceptual / Speculative Stimulus
- Peripheral / Low-Reliability Theory
- Not Suitable Now
- Noise / Duplicate / Repository Residue

## Lane-by-Lane Review

### core_embodied_ai

- Best candidates:
- Questionable candidates:
- Noise / duplicates:
- Configuration implications:

### language_symbol

- Best candidates:
- Speculative but interesting:
- Low-reliability / risky:
- Noise / duplicates:
- Configuration implications:

### humanities_social

同上。

### math_physics_cs

同上，但重点判断哪些是 Not Suitable Now。

### neuro_cognitive

同上。

## Configuration Recommendations

只提出建议，不直接修改配置：

- topics.yaml:
- scoring.yaml:
- sources.yaml:
- curator guideline changes:

## Do Not Do

除非用户明确要求，不要：

- 修改代码；
- 修改 config；
- 启用新 source；
- 删除运行产物；
- 提交；
- 下载 PDF；
- 做 LLM 摘要替代人工审查；
- 把 speculative 条目自动当作垃圾；
- 把 repository-like 条目自动当作可靠论文。
```

## 7. User-Specific Preferences

用户当前偏好和约束：

1. 用户不是单一专业领域研究者，而是跨学科泛读者。
2. 用户希望通过泛读逐步建立问题地图，而不是马上做严格文献综述。
3. 用户对语言、符号、意义、隐喻、认知语言学、现象学、心灵哲学、文学性想象、博尔赫斯式观念结构有明显兴趣。
4. 用户对 embodied AI、symbol grounding、AI 如何连接感知与行动感兴趣。
5. 用户当前不适合大量阅读高度数学化、物理化、控制理论化论文。
6. 用户不希望系统把过多判断硬编码进字段、权重和 if/else 规则。
7. 用户希望 Paper Radar 保持为粗筛系统，把更复杂的价值判断交给自然语言 curation 规范或独立 skill。
8. 用户愿意保留 speculative / unusual / edge-theory 条目，但需要知道它们的风险和阅读姿态。
9. 用户不希望被迫只读主流高可信论文；思想刺激性也是价值之一。
10. 用户更需要“这篇东西对我有什么用”的判断，而不是纯粹“这篇论文客观质量几分”。

## 8. First Curation Task Template

当需要审查某一周报告时，使用以下任务提示：

```markdown
请读取：

- data/reports/weekly_candidates_<week>.md
- data/reports/rejected_candidates_<week>.md
- data/reports/score_audit_<week>.md

不要修改任何文件。不要运行真实抓取。不要提交。

请根据 `docs/curation_guidelines.md` 输出一份 curated review。

要求：

1. 不要只按分数排序。
2. 不要把 Zenodo / OSF / repository-like 条目自动判为垃圾。
3. 不要把 speculative 条目当作可靠知识来源。
4. 区分“适合认真读”“适合略读”“适合作为思想素材”“暂不适合”“噪声”。
5. 特别关注 language_symbol 中的 symbol grounding、meaning、consciousness、semiotics、cognitive linguistics 相关条目。
6. 对 math_physics_cs 要判断其是否超出用户当前技术门槛。
7. 最后给出项目方向建议，而不是只给阅读清单。

输出：

- Overall Diagnosis
- Recommended Shortlist
- Lane-by-Lane Review
- Configuration Recommendations
- Whether to continue development, adjust config, or start using the report
```
