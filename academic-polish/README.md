# 学术语言润色守门/完成器（academic-polish）

写作02「学术语言润色」参赛 Skill。面向真实科研稿件，交付"润色后完整文本 + 逐句修改说明"，并守住原意、限定强度、数值与引用。

## 快速开始

```bash
# 自检
python examples/selftest.py

# 确定性检查（守门）
python scripts/polish_engine.py pipeline --compact examples/smoke_input.json

# 逐句成稿草稿（完成器）
python scripts/polish_engine.py render-draft examples/smoke_input.json

# 端到端一次交付（推荐）
python scripts/polish_engine.py solve /input/case.json --out /app/output

# 公平对照证据
python scripts/compare_engine.py examples/smoke_input.json
```

## 设计要点

- **完成器**：`solve` 从真实 case 出发，读材料 → 四问检查 → 逐句成稿 → 装配 `result.json` + `delivery` 回执。
- **四问机制**：改得对（硬错误检测）/ 说得像（术语回扫 + 语域诊断）/ 没改坏（守护元素 + 限定强度守恒）/ 讲得清（逐句原文-改文-理由）。
- **不臆造**：无真实润色文标〔待润色〕，无真实改文不做守恒核验，不确定进 `needs_review`。

## 目录

- `SKILL.md`：技能说明、触发边界、调用方式。
- `scripts/polish_engine.py`：主引擎。
- `scripts/compare_engine.py`：公平对照。
- `examples/`：selftest / benchmark / 最小示例 / 冒烟数据。
- `references/`：输出契约与规则文档。

纯 Python 标准库，无网络与第三方依赖，Python 3.8+ 可运行。
