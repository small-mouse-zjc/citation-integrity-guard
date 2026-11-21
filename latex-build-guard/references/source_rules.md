# 源码结构与宏包规则

`check-source` 对 LaTeX 源码做静态结构检查，帮助在编译前发现明显问题。

## 主文件 vs 子文件

- 主文件须有 `\documentclass{...}`、`\begin{document}` / `\end{document}`。
- 子文件（chapter1.tex 等）通常只有内容，无 documentclass，由 `\input{}` / `\include{}` 引入。
- 引擎检查 `\input/\include` 引用的子文件是否在 `sub_files` 中提供；缺失标 `missing_subfile`。

## 导言区与宏包顺序

常见顺序约束：
- `amsmath`/`amssymb` 等数学包应在 `hyperref` **之前**；
- `cite`/`natbib`/`cleveref` 与 `hyperref` 有特定顺序要求（cleveref 通常在 hyperref 之后）；
- `fontenc`/`inputenc`（pdfLaTeX）与 `fontspec`（XeLaTeX）不要混用。

引擎对 `amsmath`/`xcolor` 在 hyperref 之后的情况给 warning（易引发连锁错误），其余靠 Agent 结合发行版判断。

## 常见命令误用

- `\input{file}` 不需 `.tex` 后缀，`\include{file}` 会另起页；
- 行内公式 `$...$`，独立 `\[...\]` 或 `equation` 环境，不要用 `$$...$$`（LaTeX 中不规范）；
- 表格 `&` 分隔列，`\\` 换行，列格式数须与列数匹配；
- `%` 注释会吞掉行尾换行，命令后紧跟中文需注意。

## 花括号平衡

引擎做粗略的花括号计数（忽略注释行）。不平衡标 `brace_balanced=false`。注意：命令参数、`{}` 分组、可选参数 `[]` 都参与，计数相等不代表一定正确，但不等几乎一定有问题。

## 未知宏包

引擎内置常见宏包白名单。不在名单里的标 `uncommon_package` warning，须确认该宏包存在且已安装——不要当成错误，但要在复现记录里注明。
