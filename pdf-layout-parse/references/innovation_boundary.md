# 创新边界：相对通用方案的不可替代性（阅读01 文献文档解析）

评分表"创新增益 15 分"要求论证相对"通用对话模型 / 现有工具"的边界与价值。本文按四问给出可核对的边界，避免空泛宣称。

## 1. 四问的确定性保证（通用模型难以稳定做到）

| 核心问题 | 通用模型常见失败 | 本 Skill 的确定性机制 |
|---|---|---|
| 提得全 | 漏行/页眉页脚混入正文 | 字符覆盖率自检+乱码标注 |
| 排得对 | 双栏串栏/错行/段落拼接 | x0聚类双栏检测+按y交错阅读序 |
| 拆得清 | 表格行列/公式上下标希腊字母丢失 | 表格众数筛行+真实Unicode希腊字母保真 |
| 核得回 | 文字无法指回原文页码区块 | 逐行bbox证据索引 |

关键差异：这些是**门禁与可回溯证据**，不是写在提示里的"建议核对"。易错动作固化为脚本判定，模型价值判断必须建立在其上。

## 2. 方法改进（非提示词堆砌）

1. **写作与核对分离**：先跑 `scripts/pdf_layout_engine.py` 得确定性检查，再做价值判断，最后成稿，避免"边写边心算"的自洽错觉。
2. **反例优先**：`needs_review` / `unbacked` / `missing` 等反例信号优先于"看起来完整"，材料不足时诚实降级为 `partial`/`needs_attention`，不伪造。
3. **公平对照可复现**：`scripts/compare_engine.py` 对同一输入给出四问机制对照，`examples/benchmark.json` 含干净案例与缺陷案例，任何人可重跑核对。
4. **省额度**：中间结果结构化、按需读取，把请求/token 预算留给价值判断。

## 3. 相对现有工具的边界

通用大模型能"写出"看似合理的文本，但不保证每条论断可回到来源、每个缺口由证据推出、每个数值有出处。本 Skill 把这些"可核验性"做成脚本可判定的结构，工具输出须经 Agent 结合原文做价值判断，两者互补而非替代。

## 4. 可复现路径

```bash
python scripts/pdf_layout_engine.py pipeline examples/smoke_input.json > result.json
python scripts/compare_engine.py examples/smoke_input.json         # 机制对照
python scripts/compare_engine.py examples/benchmark.json           # 干净+缺陷案例
python examples/selftest.py                                        # 自验收
```

边界声明：`compare` 只呈现可复现的检查机制证据，不编造平台质量分；真实对照与打分由组织方固定案例与白板给出。
