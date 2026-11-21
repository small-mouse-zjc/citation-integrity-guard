# 段号对齐与证据契约（Alignment & Evidence）

对应题面"段落全"与"可核验"。

## 1. 稳定段号

- 每段一个 `id`（P1/P2/…或自定义），贯穿切段→翻译→对齐→证据。
- `section` / `page` / `kind` 作为定位元数据保留。
- 段号是段落级对齐的主键，不依赖文本内容（内容可改，段号不变）。

## 2. 切段与续段（segment）

- 按输入段落边界切分，记录 `char_count`。
- 跨页续段：上段末无句末标点、下段首为小写/无大写开头 → 标 `continuation_of`，提示这两段可能是同一段的跨页续接，翻译时应携带上下文。
- 重复段：归一化文本相同的段落标 `duplicate_of`，避免重复翻译。

## 3. 对齐核验（align）

- `missing`：原文有、译文无的段号（漏译）。
- `extra`：译文有、原文无的段号（多余/错位）。
- `out_of_order`：译文段号顺序与原文不一致处。
- `coverage` = 已译段数 / 原文段数；1.0 为全覆盖。

## 4. 证据索引（evidence）

每段译文一条证据：
```json
{
  "id":"P1",
  "source_location":{"section":"Abstract","page":1,"paragraph_id":"P1"},
  "source_head":"原文前60字",
  "translation_head":"译文前60字",
  "basis":[{"type":"glossary","source":"porosity","target":"孔隙度"},
           {"type":"protected:chemical","raw":"CO2"}],
  "translated":true,
  "needs_review":false
}
```

- `basis` 给出该段译法的可回溯依据：用到的锁定术语 + 被保护的事实元素。
- 缺译文 → `needs_review=true`，不臆造译文。

## 5. 与平台 output_contract 的映射

- "阅读/解析结果" ← 段落级双语对照（按段号对齐）。
- "证据与边界" ← `evidence_index` + `verification.needs_review`。
- "运行状态" ← `status` + `verification.issues`。

## 边界

段号依赖输入的段落划分；若上游 PDF 解析把段落切错，需先修正段落边界。续段/重复段为候选提示，不替作者决定合并与否。
