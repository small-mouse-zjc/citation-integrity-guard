# Translation Guard · 文献翻译守门人

面向「文献翻译」任务的 Agent Skill。既是端到端交付双语对照成稿的**完成器**（从真实 case 读材料→切段→建术语表→成稿→装配 result.json），也是把**术语一致性、段落完整性、事实关系保真、可核验性**做成确定性脚本的**核验器**——术语表真正执行、段号一一对应、数字公式引用不丢、每段能回原文。翻译措辞交给模型，缺译文标〔待翻译〕不臆造。

**公开仓库**：https://github.com/small-mouse-zjc/citation-integrity-guard/tree/main/translation-guard （提交前填写）

## 目录结构

```
translation-guard/
  SKILL.md                       # 技能本体
  README.md                      # 本文件
  GITHUB_URL.txt                 # 作品公开链接
  scripts/
    translation_guard.py         # 确定性翻译完成器+守门引擎（12 子命令，含 solve/render-draft，纯标准库）
  references/
    output_contract.md           # 输入输出字段契约
    glossary_format.md           # 术语表格式与锁定规则
    protection_rules.md          # 占位符保护与回填规则
    alignment_contract.md        # 段号对齐与证据契约
    verification_checklist.md    # 译文自检清单
    failure_patterns.md          # 失败模式案例
    vocab.md                     # 可复用词表
  examples/
    minimal_example.md / smoke_input.json / smoke_output.json
    testset.json                 # 10 道边界测试题集
    selftest.py                  # 61 项自验收测试（含成稿/适配/solve）
```

## 快速开始

```bash
python scripts/translation_guard.py --help
python scripts/translation_guard.py solve /input/case.json --out /app/output   # 端到端成稿+装配
python scripts/translation_guard.py render-draft examples/smoke_input.json > draft.json
python scripts/translation_guard.py pipeline examples/smoke_input.json --with-draft > result.json
python scripts/translation_guard.py pipeline examples/smoke_input.json --compact > summary.json
```

## 功能（题面四问）

| 动作 | 题面关注点 | 命令 |
|------|-----------|------|
| 术语候选抽取 + 人工术语表合并 | 术语稳 | `build_glossary` |
| 术语表编译成强制锁定提示串 | 术语稳 | `lock_terms` |
| 译名一致性验证 | 术语稳 | `check_terms` |
| 切段/稳定段号/续段/重复段 | 段落全 | `segment` |
| 原文—译文段落对齐 | 段落全 | `align` |
| 数字/公式/引用/化学式占位符保护 | 关系准 | `protect` |
| 占位符回填与篡改核对 | 关系准 | `restore` |
| 数字/否定/限定/引用/公式自检 | 关系准/可核验 | `verify` |
| 每段译文的证据与译法依据 | 可核验 | `evidence` |
| 用真实字段渲染双语对照成稿草稿 | 全部/成稿 | `render-draft` |
| 端到端完成器：适配→成稿→装配 result.json | 全部/交付 | `solve` |
| 全流程 + 紧凑摘要（`--with-draft` 成稿） | 全部/额度 | `pipeline [--compact] [--with-draft]` |

## 设计亮点

1. **端到端交付**：`solve` 从真实 case 读取材料（paragraphs/source_text/source_files）、渲染双语成稿、装配 result.json + delivery 回执，一次运行即可复核；无译文标〔待翻译〕不臆造。
2. **术语真执行**：`lock_terms` 生成强制提示串，`check_terms` 验证译名一致，不是"写在提示里"。
2. **事实零失真**：占位符保护 + 回填核对，数字被改/引用被删/化学式丢失都能定位到段号。
3. **段落闭环**：稳定段号贯穿切段→翻译→对齐→证据，漏段/重复/错位显式检出。
4. **诚实边界**：否定/限定词"疑似丢失"交人工，术语候选未定译名不强制替换，不臆造。
5. **可复用**：纯标准库、带 10 道边界题集 + 失败模式 + 可复用词表。

## 提交前检查清单

- [ ] `GITHUB_URL.txt` 第一行填公开子目录链接，未登录可打开并找到作品。
- [ ] 资源全为 UTF-8 文本，≤50 文件 / 单文件≤500KB / 总≤2MB，无软链。
- [ ] **提交目录内无 Dockerfile / 二进制文件**（确保不重蹈预检拒收）。
- [ ] `SKILL.md` frontmatter 有效；`smoke_output.json` 标注为示例。
- [ ] selftest 全过（61 项）、bundle 零凭证残留。

## 适用边界

不替代模型翻译措辞，但会从真实输入端到端成稿并装配交付；术语候选须确认译名；占位符覆盖数字单位/公式/引用/化学式，否定限定为疑似提示；不联网、缺译文与不确定处不臆造。


## 冲分证据（可复现）

- 四问：术语稳 / 段落全 / 关系准 / 可核验
- 公平对照：`python scripts/compare_engine.py examples/benchmark.json`（clean 验证不误报，defect 验证能检出，可复现）。
- 只度量 Skill 检查机制的可运行证据，不编造平台质量分；真实对照由平台给出。
- 自验收：`python examples/selftest.py`（含对照可复现验证）。
