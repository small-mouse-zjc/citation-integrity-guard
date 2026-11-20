# Citation Integrity Guard · 引用一致性守门人

一个面向「参考文献与引用管理」任务的 Agent Skill。核心思想：把基础 Agent 最容易出错的**去重、编号同步、格式转换**固化为确定性脚本，做到准确、可解释、可回溯；对无法判断的项显式标注，绝不臆造。

## 目录结构

```
citation-integrity/
  SKILL.md                          # 技能本体（含 YAML frontmatter）
  README.md                         # 本文件
  GITHUB_URL.txt                    # 作品公开链接（提交前填写）
  scripts/
    citation_engine.py              # 确定性处理引擎（纯标准库）
  references/
    dedup_rules.md                  # 去重判据与置信度表
    format_gb7714.md                # GB/T 7714—2015 映射规则
    output_contract.md              # 输出字段契约
    verification_checklist.md       # 来源与论断核验清单
  examples/
    minimal_example.md              # 最小调用示例
    smoke_input.json                # 示例输入
    smoke_output.json               # 示例输出（标注为示例，非正式案例结果）
    selftest.py                     # 14 项自验收测试（覆盖率证据）
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
| 文献去重与条目归并 | 收得净 | `normalize` |
| 正文—文末编号连锁更新 | 编得顺 | `renumber` |
| 格式转换（GB/T 7714—2015） | 对得上 | `format` |
| 双向一致性核验 | 编得顺 | `verify` |
| 引用位置/论断匹配核验 | 挂得对 / 对得上 | 见核验清单（模型判断 + 证据） |

## 设计亮点（相对基础 Agent 的增益来源）

1. **可解释去重**：四级判据 + 置信度 + 人类可读证据，低置信疑似重复交人工确认，避免误并。
2. **编号闭包校验**：按正文首次出现重排，双向检查悬空引用与未引用条目，保证编号连续。
3. **确定性格式**：GB/T 7714 渲染规则固定，避免模型格式漂移。
4. **诚实边界**：字段缺失、DOI 失败、版本歧义一律标注，不编造文献或元数据。
5. **纯标准库可复用**：无网络、无依赖、带示例，他人可直接用于自己的稿件与学科。

## 提交前检查清单

- [ ] `GITHUB_URL.txt` 第一行已填公开仓库链接（未登录浏览器可打开）。
- [ ] 仓库文件齐备、路径有效、无符号链接。
- [ ] 文本文件 ≤ 50 个、单个 ≤ 500KB、总计 ≤ 2MB。
- [ ] `SKILL.md` 的 `name` / `description` frontmatter 有效。
- [ ] `examples/smoke_output.json` 已标注为示例，未被当作正式答案。

## 适用边界

内置格式化以 GB/T 7714—2015 顺序编码制为主；其他规范按映射表扩展。脚本不联网，DOI 真实性需结合平台工具或模型核验并给可回溯依据。本技能不替代作者的学术判断。
