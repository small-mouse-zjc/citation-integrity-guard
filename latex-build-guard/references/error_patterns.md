# 编译错误分类与修复策略

`classify-errors` 把编译日志里的每条 error 归类到已知模式，给出根因方向。核心原则：**看全所有错误，级联先修根因**。

## 错误分类表

| category | 典型日志 | 根因方向 | 修复策略 |
|---------|---------|---------|---------|
| undefined_control | Undefined control sequence | 命令未定义 | 检查拼写；加载对应宏包；自定义命令是否在使用前定义 |
| missing_file | Can't find file / Emergency stop | 缺 .tex/.cls/.sty/图片 | 核对路径；安装模板类文件；补图片文件 |
| missing_package | File xxx.sty not found | 缺宏包 | 安装宏包；换用已有包；检查发行版完整性 |
| missing_font | Font not found / Missing character | 缺字体 | 安装字体；改用系统已有字体（如 Latin Modern） |
| unclosed_group | Runaway argument / Missing } | 花括号/环境未闭合 | 补齐 } 或 \end{}；检查注释吞掉命令 |
| math_error | Missing $ inserted / Bad math delimiter | 数学环境定界错 | 行内用 $...$，独立用 \[...\] 或 equation 环境 |
| reference_undefined | Reference/Citation undefined | 引用未解析 | 补 label/bib 条目；多编译 2-3 轮；检查 cleveref 顺序 |
| float_overflow | Float too large / Overfull hbox | 浮动体/盒子溢出 | 调整列宽 p{}；缩放图片；改 [H] 位置；拆分宽表 |
| table_error | Misplaced \noalign / Extra alignment tab | 表格列数不匹配 | 列格式数 = 每行 & 数+1；合并单元格用 \multicolumn |
| package_conflict | Option clash / Package Error | 宏包冲突 | 调整加载顺序；合并冲突宏包选项；去重复加载 |
| permission | Permission denied / Read-only | 目录写权限 | 检查输出目录权限；换可写目录 |

## 级联错误

`cascading=true`（多条错误集中在同一 category）时，通常是**一个根因引发连锁报错**。例如漏一个 `\usepackage{amsmath}` 会导致多个数学命令 Undefined。此时：
1. 只修根因（加载 amsmath）；
2. 重新编译；
3. 不要逐条打补丁。

## 行号定位

日志里的 `l.123` 是 TeX 认为出错的行号，可能因宏展开而指向宏内部。若 snippet 看不出问题，向上检查调用处。每条错误引擎给 `tex_line` 与 `snippet`，Agent 据此回源码定位。

## 编译轮次与引用收敛

含 `\ref`/`\cite` 的文档需要多遍编译（pdflatex × 2-3，或 latexmk 自动）。`reference_undefined` 常是轮次不够而非真缺 label——先确认 label 存在，再增轮次。
