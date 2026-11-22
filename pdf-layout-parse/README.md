# PDF Layout Parse · 科研 PDF 版面解析完成器

面向「文献文档解析」任务的 Agent Skill。**端到端完成器**：直接读取平台真实 PDF（`/input/case.json` 指向），多后端自动提取，用确定性几何规则替代模型心算，交付逐字保真、顺序正确、结构清晰、每段可回原文区块的结果并装配 `/app/output/result.json`；读不出的部分诚实标注，不猜字补齐、不伪造平台分数。

**公开仓库**：https://github.com/small-mouse-zjc/citation-integrity-guard/tree/main/pdf-layout-parse （提交前填写，无需登录可访问）

## 目录结构

```
pdf-layout-parse/
  SKILL.md                       # 技能本体（含 YAML frontmatter）
  README.md                      # 本文件
  GITHUB_URL.txt                 # 作品公开链接
  scripts/
    pdf_layout_engine.py         # 端到端解析引擎（11子命令含solve完成器，主体纯标准库）
  references/
    output_contract.md           # 输入输出字段契约
    reading_order_rules.md       # 分栏与阅读顺序规则
    table_structure.md           # 表格结构重建规则
    evidence_contract.md         # 证据定位与自检契约
    failure_patterns.md          # 失败模式案例
    vocab.md                     # 可复用词表
  examples/
    minimal_example.md           # 最小调用示例
    layout_sample.json           # 带坐标样例（标注示例）
    smoke_input.json             # 示例输入
    smoke_output.json            # 示例输出（标注示例）
    testset.json                 # 10 道边界测试题集
    selftest.py                  # 38 项自验收测试（含solve端到端/双栏/上下标回归）
```

## 快速开始

```bash
# 环境：Python 3.8+，主体纯标准库；extract 多后端自动回退（PyMuPDF→pdfplumber→pdfminer）
python scripts/pdf_layout_engine.py --help
# 一步到位：真实 case/PDF → 解析 → 装配 /app/output/result.json（推荐）
python scripts/pdf_layout_engine.py solve /input/case.json --out /app/output
# 或分步：先提取带坐标中间表示，再跑全流程
python scripts/pdf_layout_engine.py extract paper.pdf --case-id C1 > layout.json
python scripts/pdf_layout_engine.py pipeline layout.json > result.json
python scripts/pdf_layout_engine.py pipeline layout.json --compact > summary.json
```

## 功能（题面四问）

| 动作 | 题面关注点 | 命令 |
|------|-----------|------|
| **端到端**：真实 case/PDF → result.json 装配 | 全部 | `solve` |
| PDF→带坐标中间表示(多后端自动) / 无文字层判定 | 提得全 | `extract` |
| 逐字保真、页眉页脚剔除、断行、乱码标注 | 提得全 | `clean` |
| 双/多栏分栏 + 跨栏识别 + 逐栏整段读取 | 排得对 | `order` |
| 章节层级与结构树 | 拆得清 | `sections` |
| 表格行列/单元格重建、合并单元格、跨页续表 | 拆得清 | `tables` |
| 希腊字母/上下标(span size还原)/公式编号保真 | 拆得清 | `formulas` |
| 图表题注识别与配对 | 提得全 | `captions` |
| 页码+区块证据索引、覆盖率自检 | 核得回 | `evidence` / `verify` |
| 全流程 + 紧凑摘要 | 全部/额度 | `pipeline [--compact]` |

## 设计亮点（相对基础 Agent 的增益）

1. **逐字保真**：spans 拼接原文，断行只补换行不改字，覆盖率自检 ≥90%。
2. **双栏逐栏整段**：跨栏锚点分区后，同一区间先完整读左栏再完整读右栏（真实双栏段落整栏连续，绝不逐行左右交错打断段落），`order_violations` 自检。
3. **表格众数筛行**：用行片段数众数剔除混入的正文行，避免把双栏正文误判成表格。
4. **符号保真**：只保留原文真实希腊字母，绝不把 ASCII 字母误改为希腊字母。
5. **证据闭环**：每块回页码+bbox+区块类型，乱码/页眉页脚/扫描件如实标注。
6. **真实入口不中断**：`solve` 从真实 case/PDF 到交付物一步完成，多后端自动回退解除"无 PyMuPDF 就断"的风险；装配回执 `delivery` 可核验落盘。
7. **可复用**：主体纯标准库、带 10 道边界题集 + 四问独立缺陷矩阵 + 失败模式 + 词表。

## 提交前检查清单

- [ ] `GITHUB_URL.txt` 第一行填公开链接，未登录可打开并找到作品。
- [ ] 资源全为 UTF-8 文本，≤50 文件 / 单文件≤500KB / 总≤2MB，无软链。
- [ ] **提交目录内无 Dockerfile / 二进制文件**（上次 92127 就是因 Dockerfile 预检被拒）。
- [ ] `SKILL.md` frontmatter 的 `name`/`description` 有效。
- [ ] `smoke_output.json` 标注为示例，未被当作正式答案。
- [ ] selftest 全过、bundle 零凭证残留。

## 适用边界

按结构元素识别图表公式，不解释科学含义；无文字层需 OCR（引擎如实判定标注）；分栏/跨页表候选交人工确认；不联网、不臆造。


## 冲分证据（可复现）

- 四问：提得全 / 排得对 / 拆得清 / 核得回
- 公平对照：`python scripts/compare_engine.py examples/benchmark.json`（clean + 四问独立缺陷矩阵，可复现）。
- 只度量 Skill 检查机制的可运行证据，不编造平台质量分；真实对照由平台给出。
- 自验收：`python examples/selftest.py`（含对照可复现验证）。
