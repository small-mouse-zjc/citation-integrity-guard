# 最小调用示例（示意，非真实案例结果）

下面用一份虚构的沉积学 AI 实验材料演示完整流程。**示意输出不是平台正式案例结果**，真实任务须读取 `/input/case.json` 与事实底稿。

## 输入 input.json

```json
{
  "case_id": "demo-methods",
  "section_text": "步骤：先预处理薄片图像再训练CNN。实验设置：Python3.10、GPU、随机种子42。参数：学习率为0.001，批量大小为32。数据集：DataX v2，按8:2划分。与基线UNet对比，用F1指标。复现代码见github，命令python train.py，数据官网下载。限制：在少样本场景失效。",
  "sources": {
    "config.yaml": "lr: 0.001\nbatch_size: 32\nseed: 42",
    "train.log": "epoch 100 f1 0.88"
  },
  "params": [
    {"name":"学习率","value":0.001,"unit":"","scope":"优化器","source":"config.yaml"},
    {"name":"批量大小","value":32,"unit":"张","scope":"训练","source":"config.yaml"}
  ],
  "gaps": [],
  "limitations": ["在少样本场景失效"],
  "draft": "（Agent 撰写的方法章节草稿，此处省略）"
}
```

## 调用

```bash
python scripts/methods_engine.py pipeline input.json > result.json
```

## 示意输出（节选，非真实结果）

```json
{
  "case_id": "demo-methods",
  "status": "ok",
  "result": {
    "completeness": {"present_count": 6, "complete": true},
    "value_verification": {"claim_count": 2, "unsupported_count": 0, "all_supported": true},
    "reproducibility": {"reproducible": true, "missing": []},
    "gap_probe": {"question_count": 0, "generic_limitations": []},
    "parameter_table": {"param_count": 2, "all_sourced": true}
  },
  "evidence": {
    "source_location": {"学习率为0.001": ["config.yaml"], "批量大小为32": ["config.yaml"]}
  },
  "uncertainty": {"gap_count": 0, "note": "数值语义一致性须核对原文"}
}
```

## Agent 后续要做的事

脚本只给结构化结果，Agent 须：
1. 核对数值语义——"学习率 0.001"是否真与 config 的 `lr` 同一参数、同一条件；
2. 把步骤写成有序可执行序列（每步输入/操作/输出/判断条件）；
3. 训练/验证/测试分开描述，参数表与正文数值对齐；
4. 确认复现六项真实可用（种子是否含各库、命令是否可复制）；
5. 把"在少样本场景失效"补成具体场景（样本数阈值、下降幅度、适用范围）；
6. 装配章节成稿 + `result.json`，每条数值附来源定位。
