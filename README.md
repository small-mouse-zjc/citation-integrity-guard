# Citation Integrity Guard · 引用一致性守门人

一个面向「参考文献与引用管理」任务的 Agent Skill。核心思想：把基础 Agent 最容易出错的**去重、编号同步、格式转换**固化为确定性脚本，做到准确、可解释、可回溯；对无法判断的项显式标注，绝不臆造。

**公开仓库**：https://github.com/small-mouse-zjc/citation-integrity-guard （无需登录可访问）

## 目录结构

```
citation-integrity/
  SKILL.md                          # 技能本体（含 YAML frontmatter）
  README.md                         # 本文件
  GITHUB_URL.txt                    # 作品公开链接
  scripts/
    citation_engine.py              # 确定性处理引擎（9 子命令，纯标准库）
  references/
    dedup_rules.md                  # 去重判据与置信度表
    format_gb7714.md                # GB/T 7714—2015 映射规则
    apa_mapping.md                  # APA 7th 扩展映射（规范可扩展证据）
    output_contract.md              # 输出字段契约
    verification_checklist.md       # 来源与论断核验清单
    failure_patterns.md             # 10 类失败模式案例（可分享经验）
    vocab.md                        # 可复用词表（预印本前缀/字段别名/类型标识/信号词）
  examples/
    minimal_example.md              # 最小调用示例
    smoke_input.json                # 示例输入
    smoke_output.json               # 示例输出（标注为示例，非正式案例结果）
    testset.json                    # 14 道边界回归测试题集（可复用）
    selftest.py                     # 33 项自验收测试（覆盖率证据）
```

## 快速开始

```bash
# 环境：Python 3.8+，无第三方依赖
python scripts/citation_engine.py --help
python scripts/citation_engine.py pipeline examples/smoke_input.json
```

## 功能

| 动作 | 对应题面关注点 | 命令 |
|------|----------------|------|
| 文献库原文解析（BibTeX/RIS/CNKI） | 格式转换/省请求 | `ingest` |
| 文献去重与条目归并（含预印本线索标注） | 收得净 | `normalize` |
| 编号连锁更新 + 可编辑正文改写 | 编得顺 | `renumber` |
| 格式转换（GB/T 7714—2015，附 APA 扩展） | 格式转换 | `format --standard apa` |
| 双向一致性 + 首次出现顺序核验 | 编得顺 | `verify` |
| 引用落点定位（需引论断句 + 候选） | 挂得对 | `place` |
| 论断核验预筛（元数据/编造线索/主题错配） | 对得上 | `claims` |
| 修复前后逐项对照 | 增益可验证 | `compare` |
| 全流程 + 紧凑摘要省 token | 全部/额度 | `pipeline [--compact]` |

## 设计亮点（相对基础 Agent 的增益来源）

1. **四问全覆盖**：从原来缺"挂得对/对得上"两问，到 `place`+`claims` 落地确定性预筛，逐句判断降为可疑项复核。
2. **可解释去重**：四级判据 + 置信度 + 人类可读证据；version_variant 等疑似重复进 `needs_review`，避免静默丢失与误并。
3. **可编辑交付**：`renumber` 输出 `rewritten_manuscript` 与逐条 `rewrite_changes`，稿件可直接继续编辑。
4. **确定性格式**：GB/T 7714 渲染规则固定（中英文作者"等/et al."、卷期页、类型标识），APA 作为规范可扩展证据。
5. **增益可验证**：`compare` 给出修复前后问题项逐项增减；`summary` 一行紧凑结论。
6. **诚实边界**：字段缺失、DOI 失败、版本歧义、可疑编造一律标注，不臆造文献或元数据，不冒充学术判断。
7. **纯标准库可复用**：无网络、无依赖、带 14 道测试题集 + 10 类失败模式 + 可复用词表。

## 额度与预算（64 请求 / 900 秒）

`ingest` 自动解析省手工转换请求 → `claims` 只把可疑项交模型 → `pipeline --compact` 省输出 token。早存诚实部分结果，三案例复用同一流程。

## 提交前检查清单

- [ ] `GITHUB_URL.txt` 第一行已填公开仓库链接（未登录浏览器可打开）。
- [ ] 仓库文件齐备、路径有效、无符号链接。
- [ ] 文本文件 ≤ 50 个、单个 ≤ 500KB、总计 ≤ 2MB。
- [ ] `SKILL.md` 的 `name` / `description` frontmatter 有效。
- [ ] `examples/smoke_output.json` 已标注为示例，未被当作正式答案。

## 适用边界

内置格式化以 GB/T 7714—2015 顺序编码制为主；其他规范按映射表扩展。脚本不联网，DOI 真实性需结合平台工具或模型核验并给可回溯依据。本技能不替代作者的学术判断。
