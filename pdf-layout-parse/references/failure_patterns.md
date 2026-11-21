# 失败模式案例（Failure Patterns）

面向复用者：记录科研 PDF 解析的高频失败场景、根因与本合同技能的确定性处置。每条"输入特征 → 错误表现 → 正确处置 → 可核验证据"。非正式评测案例。

## F1 · 双栏正文被拼成一句

- **输入特征**：双栏论文，左右栏同一 y 各有一行文本。
- **常见错误**：按 y 排序时把左右栏同 y 行拼成"左句右句"，语义断裂。
- **正确处置**：`detect_columns` 判栏，`order` 按 (y, 栏序) 交错，同 y 先 L 后 R。
- **证据**：`column_reports[].columns=2`、`order_violations=[]`、`ordered[].column` 标注。

## F2 · 跨栏标题被塞进某一栏

- **输入特征**：横跨中缝的大标题/图表/公式。
- **常见错误**：按 x0 归栏，把跨栏标题归进左栏，顺序错乱。
- **正确处置**：横跨 gutter 的行判为 X（跨栏块），作为全局锚点按 y 插入。
- **证据**：`ordered[0].column=X`（标题在最前）。

## F3 · 页码/期刊名混进正文

- **输入特征**：页脚页码、跨页重复期刊名。
- **常见错误**：逐字提取把它们当正文首行/末行。
- **正确处置**：跨页重复边缘文本 + 纯页码识别 → `dropped` 附 reason。
- **证据**：`clean.header_texts` / `clean.footer_texts` / `dropped[].reason`。

## F4 · 断行把小节标题吞进正文

- **输入特征**：公式行/正文行紧邻下一节标题（字号更大、y 间距大）。
- **历史缺陷（本技能已修）**：早期合并只看 y 间距与句末标点，把"公式 (1)"与"2 Methods"拼成"(1)2 Methods"，公式编号丢失。
- **正确处置**：合并增加字号接近（差<1.5）与间距<0.6 行高两道保护，标题不与正文合并。
- **证据**：`formulas[].number` 正确识别、`clean.lines` 中标题独立成行。

## F5 · 双栏正文被误判为表格

- **输入特征**：双栏左右同 y 两行短文本，横向分离。
- **历史缺陷（本技能已修）**：早期只看"≥2 片段 + 间距>12"就把正文当表格。
- **正确处置**：用行片段数众数筛行——真表格各行列数一致（如 3 列），混入正文行 2 列，众数过滤剔除。
- **证据**：`tables[].rows` 只含真表格行，正文不含在 Markdown 内。

## F6 · ASCII 字母被误改为希腊字母（保真大忌）

- **输入特征**：英文句子 "The loss function is L = - Σ p log q"。
- **历史缺陷（本技能已修）**：早期 GREEK_FIX 映射把 a→α、s→σ、o→ο，输出"Thε λoσσ φunction iσ"，科学含义全毁。
- **正确处置**：只保留原文真实 Unicode 希腊字母（如 Σ），绝不替换 ASCII 字母；OCR 修正映射默认关闭。
- **证据**：`formulas[].rendered` 中 "function" 完整、Σ 保留。

## F7 · 无文字层扫描件被当成空文档

- **输入特征**：扫描论文/图片型 PDF，`get_text` 返回空。
- **常见错误**：把 0 行结果当成功交付。
- **正确处置**：`extract` 检测 `line_count=0` → `status=needs_review` + note 提示 OCR，不伪造内容。
- **证据**：`extract.status` / `extract.note`。

## F8 · 加密/损坏 PDF 导致崩溃

- **输入特征**：文件不存在、加密、损坏。
- **历史缺陷（本技能已修）**：早期 `pymupdf.open` 未捕获异常，直接抛栈。
- **正确处置**：捕获异常返回 `cannot_open_pdf` + `type(e).__name__`，结构化说明。
- **证据**：`extract.error` / `extract.fallback`。

## F9 · 表格缺字段被臆造补齐

- **输入特征**：合并单元格留空、字段缺失。
- **正确处置**：空单元格留空，不继承上一行；跨页续表给候选不自动合并；一律 `needs_review`。
- **证据**：`tables[].grid[].cells` 空串、`continuations` 候选。

## F10 · 覆盖率低却报告成功

- **输入特征**：断行合并吞字、提取丢段，输出字数远少于正文。
- **正确处置**：`verify.coverage = out_chars/body_chars`，<90% 进 problems，`consistent=false`。
- **证据**：`verification.coverage` / `verification.problems`。

## 复用建议

1. `extract` 导出 layout（无 PyMuPDF 则用平台工具导中间表示）。
2. `clean` 后先看 `dropped`/`unreadable`，确认页眉页脚剔除、乱码标注。
3. `order` 后看 `column_reports`/`order_violations`，确认栏序正确。
4. `sections`/`tables`/`formulas`/`captions` 逐项核对结构。
5. `verify` 覆盖率 + `evidence_index` 形成可验证闭环，写进 `result.summary`。
