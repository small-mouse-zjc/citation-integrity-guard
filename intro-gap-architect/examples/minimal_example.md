# 最小调用示例（示意，非真实案例结果）

下面用一份虚构的沉积学引言材料演示完整流程。**示意输出不是平台正式案例结果**，真实任务须读取 `/input/case.json` 与事实底稿。

## 输入 input.json

```json
{
  "case_id": "demo-sedimentology",
  "background": "近年来，人工智能受到广泛关注。深度学习方法已被用于岩相识别[1]。但现有方法普遍存在标注成本高的问题。",
  "works": [
    {"id":"w1","title":"CNN碳酸盐岩薄片分类","authors":["Smith, A."],"year":2023,"source":"Sedimentology",
     "route":"深度学习路线","problem":"薄片岩相识别","method":"CNN","data_eval":"acc 0.92",
     "applicability":"碳酸盐岩薄片","limitations":"标注成本高","conclusion":"优于传统方法"},
    {"id":"w2","title":"GAN相建模","authors":["Li, H."],"year":2024,"source":"Fuel",
     "route":"深度学习路线","problem":"三维相建模","method":"GAN","data_eval":"F1 0.85",
     "limitations":"标注成本高"},
    {"id":"w3","title":"知识图谱相解释","authors":["张, 三"],"year":2025,"source":"沉积学报",
     "route":"知识路线","problem":"相解释推理","method":"知识图谱","data_eval":"prec 0.88",
     "limitations":"泛化能力弱"}
  ],
  "claims": [
    {"id":"c1","text":"提出分组比较驱动的研究空白推导方法","evidence_refs":["表2","图3"]},
    {"id":"c2","text":"在三个沉积学案例上验证有效性","evidence_refs":["表4"]}
  ],
  "evidence_index": {"表2":"分组矩阵结果","图3":"空白推导流程","表4":"案例验证结果"},
  "target_scenario": "弱监督 跨盆地 轻质部署",
  "contribution_links": [{"gap_type":"共同限制","claim_id":"c1"}]
}
```

## 调用

```bash
python scripts/intro_engine.py pipeline input.json > result.json
```

## 示意输出（节选，非真实结果）

```json
{
  "case_id": "demo-sedimentology",
  "status": "needs_attention",
  "result": {
    "background_check": {
      "holds_up": true,
      "hype_sentences": [{"line":1,"reason":"含泛化表述但已有具体锚点，可接受","has_anchor":true}],
      "concrete_anchor_count": 3
    },
    "related_work_matrix": {
      "group_count": 2,
      "groups": [
        {"group":"深度学习路线","count":2,"comparison":{"方法路线":[{"id":"w1","value":"CNN"},{"id":"w2","value":"GAN"}]}},
        {"group":"知识路线","count":1}
      ]
    },
    "research_gap": {
      "gaps": [
        {"type":"共同限制","gap":"标注成本高是多篇工作共有的限制",
         "supporting_works":["w1","w2"],"strength":"medium"}
      ]
    },
    "contribution_alignment": {"aligned_count":2,"unbacked":[],"inflated":[]},
    "gap_to_contribution": [{"gap":"标注成本高是多篇工作共有的限制","bridged":true}]
  },
  "uncertainty": {"needs_review":[],"note":"转述忠实度与空白成立性须核对原文"}
}
```

## Agent 后续要做的事

脚本只给结构化结果，Agent 须：
1. 核对 w1/w2 原文的"标注成本高"是否真为共同瓶颈（不是顺带一提）；
2. 用分组矩阵把相关工作写成"同维度比较"的连贯段落；
3. 把 `research_gap` 的推导链改写为"尽管 [w1][w2]……但均受限于……"的成文空白段；
4. 确认每条贡献的锚点（表2/图3/表4）在正文确实存在；
5. 装配四部件成稿 + `result.json`，每条结论附证据定位。
