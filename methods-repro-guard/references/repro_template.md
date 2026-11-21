# 复现清单模板与限制具体化

## 复现清单六项（check-reproducibility）

| 项 | key | 写作要求 |
|----|-----|---------|
| 代码版本 | code_version | 仓库地址 + commit hash / release 版本号 |
| 运行环境 | env | Python/PyTorch/CUDA 版本、依赖安装方式 |
| 随机种子 | seed | 固定种子值，及 numpy/torch 等各自的设置 |
| 运行命令 | command | 可复制的完整训练/评测命令 |
| 数据获取 | data_access | 数据集来源、下载/申请方式、许可 |
| 划分细节 | split_detail | 划分比例、随机方式、分层策略、种子 |

### 清单示例（示意）

```
代码：github.com/xxx/method, commit a1b2c3d
环境：Python 3.10, PyTorch 1.13.1, CUDA 11.7；pip install -r requirements.txt
种子：numpy=42, torch=42, random=42
命令：python train.py --config configs/base.yaml --seed 42
数据：DataX v2.1，官网下载，划分 8:1:1 分层随机（seed=42）
```

脚本只检查这些关键词是否出现；Agent 须确保信息真实可用，缺的项写入 uncertainty。

## 限制具体化

套话限制（"存在一定局限""有待进一步研究"）会被 `probe-gaps` 标进 `generic_limitations`，必须改写为具体失效场景。

| 套话 | 具体化方向 | 示例改写 |
|------|-----------|---------|
| "存在一定局限" | 指明何种数据/条件/范围 | "当薄片分辨率低于 10 μm 时，纹理特征区分度下降，方法不再适用" |
| "有待进一步研究" | 指明未覆盖的场景 | "本方法在碳酸盐岩薄片验证，未覆盖碎屑岩，跨岩性迁移需重新校准" |
| "效果仍有提升空间" | 指明失效条件与边界 | "在样本量少于 50 时准确率下降约 12%，小样本场景需补充数据" |

具体化三要素：**条件**（何种输入/环境）+ **表现**（失效形式）+ **边界**（适用范围）。三者齐全才"说得住"。

## 与不确定性的关系

限制具体化只写章节正文；材料缺口（如数据集版本未知）走 `probe-gaps` 的 `open_questions` 交作者确认，两者不要混为一谈。
