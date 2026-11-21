# 可复用词表（Vocabulary）

独立维护、供他人复用的识别模式词表。脚本内已内联等价规则保证零依赖；本文件为可维护副本，更新时同步 `translation_guard.py` 常量。纯 UTF-8 文本。

## 1. 化学式（CHEM_RE，保护）

```
CO2/CO₂  H2O/H₂O  CH4/CH₄  NaCl  SiO2/SiO₂  CaCO3/CaCO₃  Fe2O3/Fe₂O₃  SO4/SO₄
```
按需扩展（如 Al2O3、MgO、K2O）。

## 2. 单位（UNIT_RE，保护）

```
% ％ mD md kg km² km2 km cm mm μm um nm ℃ °C GPa MPa Pa mg μg g mL L mmol mol ms min h s yr year/years 倍 次 层 口 个 m
```
注意：单位前必须有数字；后向断言 `(?![A-Za-z])` 避免切到英文单词。

## 3. 引用标记（CITE_RE，保护）

```
[1]  [1,3-5]  [1，2]  [@smith2020]
```

## 4. 公式（FORMULA_RE，保护）

```
[A-Za-zα-ωΑ-Ω][A-Za-z0-9α-ωΑ-Ω_^]*\s*=\s*[^。；;，,.]{2,40}
```
在句号/分号/逗号/英文句点处截断，不跨句。

## 5. 否定词（NEG_WORDS，核验）

```
英文：not no never neither nor without hardly
中文：不 未 无 非 没有 并非 不能 无法
```

## 6. 限定词（LIMIT_WORDS，核验）

```
英文：only mainly primarily approximately about significantly slightly may might likely suggest possible
中文：仅 主要 约 大约 显著 略微 可能 表明 提示 倾向于
```

## 7. 术语抽取停用词（STOP）

英文虚词：the a an of and or in on for to with by is are was were be been being this that these those we our their its it as at from into using used use based which who whom whose can could would should may might will shall have has had do does did not no than then thus there here where when while via per

中文虚词：的 了 和 与 及 在 是 为 对 中 该 这 其 并 等 也 而 从 以 于 上 下 将 把 被 通过 基于 我们 本文 作者

## 8. 段号与占位符约定

- 段号：`P1/P2/…` 或自定义 id，稳定不变。
- 占位符：`⟦{段号}_{序号:03d}⟧`，如 `⟦P1_003⟧`。
