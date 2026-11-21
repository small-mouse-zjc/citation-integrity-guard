# 最小调用示例（示意，非真实案例结果）

下面用一份论文与笔记材料演示完整流程。**示意输出不是平台正式案例结果**，真实任务须读取 `/input/case.json` 与真实 PDF。

## 输入 input.json

```json
{
  "case_id": "demo-note",
  "paper_sections": ["摘要", "引言", "方法", "结果", "结论"],
  "note_sections": ["摘要", "引言", "方法", "结果", "结论"],
  "card": {
    "question": "CNN能否从薄片图像识别碳酸盐岩岩相",
    "data": "500张碳酸盐岩薄片图像，8:2划分",
    "method_conditions": "ResNet-18，Python3.10/PyTorch1.13",
    "findings": "测试准确率0.92（§4，图5）",
    "limitations": "标注成本高，样本量小（§5）",
    "premises": "仅在碳酸盐岩、512×512分辨率条件下成立"
  },
  "notes": [
    {"id":"n1","text":"测试准确率0.92","anchor":"§4"},
    {"id":"n2","text":"方法为ResNet-18","anchor":"§3.2"}
  ],
  "valid_anchors": ["§4", "§3.2"],
  "knowledge_points": [
    {"label":"ResNet-18","definition":"18层残差网络","anchor":"§3.2","type":"method"},
    {"label":"岩相识别","definition":"从薄片判别岩石相","anchor":"§1","type":"task"}
  ]
}
```

## 调用

```bash
python scripts/notes_engine.py pipeline input.json > result.json
```

## 示意输出（节选，非真实结果）

```json
{
  "case_id": "demo-note",
  "status": "ok",
  "result": {
    "section_alignment": {"order_consistent": true, "missing_sections": [], "aligned": true},
    "card_fields": {"present_count": 6, "complete": true},
    "anchor_verification": {"anchored_count": 2, "all_anchored": true},
    "knowledge_normalization": {"entry_count": 2, "merged_count": 0}
  },
  "evidence": {
    "principles": {"对得上": "骨架跟随章节", "留得住": "含结论前提", "找得回": "全锚定", "用得上": "知识点已归一"},
    "missing_anchors": [], "bad_anchors": []
  },
  "uncertainty": {"missing_fields": [], "note": "笔记忠实度须结合原文复核"}
}
```

## Agent 后续要做的事

脚本只给结构化结果，Agent 须：
1. 读真实 PDF，按论文本身章节切分笔记骨架（不套模板）；
2. 抽取六字段，特别确认"结论前提"被记录；
3. 为每条关键笔记配具体锚点（页码/章节/图表）；
4. 归一知识点，中英同义（CNN/卷积神经网络）打标记不自动合并；
5. 输出可编辑笔记 + `result.json`，每条内容附来源定位；
6. 填 GITHUB_URL.txt（本题 +5 分），用免登录浏览器确认可打开。
