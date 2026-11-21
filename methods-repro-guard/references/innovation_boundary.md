# 创新边界：相对通用方案的不可替代性（写作09 方法与实验章节写作）

评分表"创新增益 15 分"要求论证相对"通用对话模型 / 现有工具"的边界与价值。本文按四问给出可核对的边界，避免空泛宣称。

## 1. 四问的确定性保证（通用模型难以稳定做到）

| 核心问题 | 通用模型常见失败 | 本 Skill 的确定性机制 |
|---|---|---|
| 写得全 | 关键步骤/参数/数据集遗漏 | 必需要素清单逐项检出 |
| 写得准 | 参数数值凭空补出无来源 | 数值溯源核对 |
| 做得着 | 版本/种子/命令不全无法复做 | 复现要素清单 |
| 说得住 | 材料缺口不显式标注 | 开放问题与待确认标注 |

关键差异：这些是**门禁与可回溯证据**，不是写在提示里的"建议核对"。易错动作固化为脚本判定，模型价值判断必须建立在其上。

## 2. 方法改进（非提示词堆砌）

1. **写作与核对分离**：先跑 `scripts/methods_engine.py` 得确定性检查，再做价值判断，最后成稿，避免"边写边心算"的自洽错觉。
2. **反例优先**：`needs_review` / `unbacked` / `missing` 等反例信号优先于"看起来完整"，材料不足时诚实降级为 `partial`/`needs_attention`，不伪造。
3. **公平对照可复现**：`scripts/compare_engine.py` 对同一输入给出四问机制对照，`examples/benchmark.json` 含干净案例与缺陷案例，任何人可重跑核对。
4. **省额度**：中间结果结构化、按需读取，把请求/token 预算留给价值判断。

## 3. 相对现有工具的边界

通用大模型能"写出"看似合理的文本，但不保证每条论断可回到来源、每个缺口由证据推出、每个数值有出处。本 Skill 把这些"可核验性"做成脚本可判定的结构，工具输出须经 Agent 结合原文做价值判断，两者互补而非替代。

## 4. 可复现路径

```bash
python scripts/methods_engine.py pipeline examples/smoke_input.json > result.json
python scripts/compare_engine.py examples/smoke_input.json         # 机制对照
python scripts/compare_engine.py examples/benchmark.json           # 干净+缺陷案例
python examples/selftest.py                                        # 自验收
```

边界声明：`compare` 只呈现可复现的检查机制证据，不编造平台质量分；真实对照与打分由组织方固定案例与白板给出。
