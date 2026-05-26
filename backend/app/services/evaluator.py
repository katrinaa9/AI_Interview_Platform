"""
AI 面试评估引擎

将面试对话历史发送给 DeepSeek，生成结构化的六维雷达评分和五点文本评价。

输出格式（严格 JSON）：
{
  "radar_scores": {
    "技术深度": 72,
    "逻辑表达": 68,
    "专业知识": 75,
    "应变能力": 60,
    "沟通与协作": 78,
    "项目实践能力": 70
  },
  "ai_feedback": {
    "总体评价": "...",
    "核心优势": "...",
    "薄弱环节": "...",
    "详细分析": "...",
    "改进建议": "..."
  }
}

若 DeepSeek 不可用，降级为基于规则的启发式评分（候选人导向，非系统导向）。
"""

import json
import logging
from typing import Tuple, Dict
from app.services.llm_client import chat_completion
from app.config import settings

logger = logging.getLogger(__name__)

# ===== 评估 Prompt 模板（增强版：六维度 + 五点反馈） =====

EVALUATION_SYSTEM_PROMPT = """你是一位资深的技术面试评估专家。你需要根据候选人的完整面试对话记录，给出专业的评估报告。

## 评估维度（每个维度满分 100）

1. **技术深度**：候选人对技术原理、底层机制的理解深度，能否回答深层次追问
2. **逻辑表达**：回答的逻辑清晰度、结构化表达能力，能否有条理地阐述复杂问题
3. **专业知识广度**：对所属技术栈的覆盖广度、概念准确性和知识面的宽度
4. **应变与解决问题能力**：面对不熟悉的问题时的思维路径、灵活度和应对策略
5. **沟通与协作素养**：技术表达的可理解性、团队协作意识、角色认知和冲突处理能力
6. **项目实践能力**：实际项目经验的丰富度，对项目全流程（选型/架构/落地/优化）的理解

## 输出要求
请严格按照以下 JSON 格式输出，不要输出任何 JSON 之外的内容：

```json
{
  "radar_scores": {
    "技术深度": <0-100的整数>,
    "逻辑表达": <0-100的整数>,
    "专业知识广度": <0-100的整数>,
    "应变与解决问题能力": <0-100的整数>,
    "沟通与协作素养": <0-100的整数>,
    "项目实践能力": <0-100的整数>
  },
  "ai_feedback": {
    "总体评价": "<2-3句话，对候选人面试表现的整体概括>",
    "核心优势": "<2-3条，分点列出候选人的主要亮点，每条包含具体依据>",
    "薄弱环节": "<2-3条，分点指出候选人最需要提升的方向，需针对候选人本身而非项目>",
    "详细分析": "<从技术深度、逻辑表达、专业知识、应变能力、沟通协作、项目实践六个角度各用1-2句话做具体分析>",
    "改进建议": "<3-5条具体可行的学习建议，用编号列出，每条给出可操作的方向>"
  }
}
```

## 评分原则
- 70分为合格线（平均水平）
- 60-69：略低于平均
- 70-79：中规中矩
- 80-89：表现良好
- 90-100：极其出色
- 基于回答的实质内容和深度打分，而非对话长度
- **如果候选人在面试中几乎没有有效回答（如一句话未说或仅有"嗯""好的"等无意义回复），各维度应如实给出低分（10-30分），不可补全或抬高分数**
- 每个维度都必须给出具体分数，不得留空或标记为无法评估
"""

# ===== 启发式降级评分（DeepSeek 不可用时，候选人导向的智能评估） =====

def _heuristic_evaluation(
    dialogue: list[dict],
    keywords: list[str],
) -> Tuple[Dict[str, int], Dict[str, str]]:
    """
    基于规则的智能评分（完全不调用 AI，作为紧急降级方案）。

    核心原则：评分从0起步，基于对话实际内容增量加分。
    - 无任何有效互动 → 各维度接近 0~10 分
    - 有实质回答 → 逐步提升至合理水平
    """
    user_messages = [m for m in dialogue if m.get("role") == "user"]
    total_rounds = len(user_messages)

    # 汇总候选人的全部回答内容
    total_content = ""
    for m in user_messages:
        total_content += m.get("content", "") + " "
    total_content = total_content.strip()

    # 内容长度（字符数）作为基础活跃度指标
    content_length = len(total_content)

    # 技术关键词命中统计
    tech_keywords = set(k.lower() for k in keywords)
    tech_mention_count = 0
    for kw in tech_keywords:
        if kw.lower() in total_content.lower():
            tech_mention_count += 1

    # ===== 六维评分：0 起步，基于实际内容增量 =====
    # 评分公式: base + round_bonus + content_bonus + signal_bonus
    # 无实质内容时各维度在 8~18 区间

    # 1. 技术深度：基于轮次、技术关键词命中、内容深度
    tech_depth_base = 15
    tech_depth = min(95, tech_depth_base
                     + total_rounds * 6           # 每轮 +6
                     + min(tech_mention_count * 5, 35)  # 技术命中最多 +35
                     + min(content_length // 60, 20))   # 内容长度最多 +20

    # 2. 逻辑表达：基于平均回答长度和结构化程度
    avg_len = content_length / max(total_rounds, 1)
    logic_base = 12
    logic = min(95, logic_base
                + total_rounds * 5              # 每轮 +5
                + min(int(avg_len / 12), 28)    # 平均长度最多 +28
                + min(content_length // 100, 22))  # 总长度最多 +22

    # 3. 专业知识广度：基于关键词覆盖和回答丰富度
    expertise_base = 15
    expertise = min(95, expertise_base
                    + min(len(keywords) * 3, 25)    # 关键词数量最多 +25
                    + tech_mention_count * 4         # 命中关键词 +4/个
                    + total_rounds * 5               # 每轮 +5
                    + min(content_length // 80, 18))

    # 4. 应变能力：需要多轮才能体现
    adaptability_base = 10
    if total_rounds >= 5:
        adaptability = min(90, adaptability_base + 30 + total_rounds * 6 + min(content_length // 120, 18))
    elif total_rounds >= 3:
        adaptability = min(80, adaptability_base + 20 + total_rounds * 6 + min(content_length // 120, 12))
    elif total_rounds >= 1:
        adaptability = min(65, adaptability_base + 12 + total_rounds * 5 + min(content_length // 180, 10))
    else:
        adaptability = adaptability_base  # 无回答 → 基底线

    # 5. 沟通协作素养：分析回答中是否有团队协作相关信号
    collaboration_signals = ["团队", "合作", "协作", "沟通", "讨论", "分工",
                             "同事", "伙伴", "我们一起", "leader", "带领",
                             "协调", "配合", "跨部门", "协作开发"]
    collab_base = 12
    collab_signal_bonus = 0
    for signal in collaboration_signals:
        if signal in total_content:
            collab_signal_bonus += 5
    communication = min(95, collab_base
                        + min(collab_signal_bonus, 35)
                        + total_rounds * 4
                        + min(content_length // 120, 18))

    # 6. 项目实践能力：分析是否有项目/实战相关描述
    project_signals = ["项目", "上线", "部署", "架构", "优化", "性能", "从零",
                       "搭建", "重构", "迁移", "生产环境", "实际",
                       "需求", "技术选型", "落地", "迭代"]
    project_base = 12
    project_signal_bonus = 0
    for signal in project_signals:
        if signal in total_content:
            project_signal_bonus += 5
    project_ability = min(95, project_base
                          + min(project_signal_bonus, 35)
                          + total_rounds * 4
                          + min(content_length // 120, 18))

    scores = {
        "技术深度": int(tech_depth),
        "逻辑表达": int(logic),
        "专业知识广度": int(expertise),
        "应变与解决问题能力": int(adaptability),
        "沟通与协作素养": int(communication),
        "项目实践能力": int(project_ability),
    }

    # ===== 候选人导向的反馈生成 =====
    avg_score = sum(scores.values()) / len(scores)
    kw_str = "、".join(keywords[:4]) if keywords else "通用技术"

    # 根据实际内容质量调整反馈语气
    if total_rounds == 0:
        overall = (
            f"候选人未进行任何有效互动，无法获得有意义的评估数据。"
            f"综合评分 {avg_score:.0f} 分（满分100），建议完成完整面试流程后再进行评估。"
        )
        strengths = ["暂无明显优势（面试未进行有效互动）"]
        weaknesses = ["面试过程中未给出任何实质性回答，无法评估真实技术水平"]
        suggestions = [
            "1. 建议重新进行完整面试流程，至少回答 5 轮以上技术问题",
            "2. 在面试中积极展示技术能力、项目经验和解决问题的思路",
            "3. 准备充分的项目案例，能够从架构、实现、优化等多角度展开讲解",
        ]
    elif total_rounds <= 2:
        overall = (
            f"候选人进行了 {total_rounds} 轮简单互动，内容较为有限。"
            f"综合评分 {avg_score:.0f} 分（满分100）。"
            f"因对话轮次过少，无法全面评估候选人的真实技术水平，"
            f"建议进行更充分的面试后再做判断。"
        )
        strengths_parts = []
        if tech_mention_count >= 2:
            strengths_parts.append(f"能够涉及 {kw_str} 中的技术概念")
        if content_length > 50:
            strengths_parts.append("有一定的基础表达能力")
        if not strengths_parts:
            strengths_parts.append("态度配合，愿意参与面试流程")
        strengths = strengths_parts

        weaknesses = [
            "面试轮次过少，无法充分展示技术深度和项目经验",
            "建议在后续面试中主动展开技术细节，而非简单应答",
        ]

        suggestions = [
            f"1. 深入学习 {keywords[0] if keywords else '核心技术'} 的底层原理，准备好被深挖",
            "2. 准备 2-3 个代表性项目案例，从需求分析到架构设计到上线效果全面复盘",
            "3. 参加更多模拟面试，锻炼在有限时间内清晰表达技术观点的能力",
        ]
    else:
        # 正常评估（3+ 轮）
        overall = (
            f"候选人具备 {kw_str} 领域的基础知识和实践经验，"
            f"综合评分为 {avg_score:.0f} 分（满分100）。"
            f"{'整体表现达到了预期水平。' if avg_score >= 70 else '仍有提升空间，建议针对性补强。'}"
        )
        strengths_parts = []
        if tech_mention_count >= 3:
            strengths_parts.append(f"能够主动涉及多个技术领域（{kw_str}），展现出较广的技术视野")
        if content_length / max(total_rounds, 1) > 80:
            strengths_parts.append("回答较为详细具体，具有较好的技术表达能力")
        if project_signal_bonus > 8:
            strengths_parts.append("展现出一定的项目实战经验，对开发流程有实际理解")
        if not strengths_parts:
            strengths_parts.append(f"对 {kw_str} 领域有基础了解，沟通态度积极")
        strengths = strengths_parts

        weaknesses_parts = []
        if tech_mention_count < 3:
            weaknesses_parts.append(f"对 {kw_str} 中部分关键技术的阐述可以更加深入")
        if content_length / max(total_rounds, 1) < 60:
            weaknesses_parts.append("部分回答可以更加详细，展示更完整的思考过程")
        if project_signal_bonus < 8:
            weaknesses_parts.append("项目实践方面的展示不够充分，建议补充更多实战案例")
        if not weaknesses_parts:
            weaknesses_parts.append("建议在技术底层原理和极端场景处理方面进一步积累经验")
        weaknesses = weaknesses_parts

        suggestions = [
            f"1. 持续深入学习 {keywords[0] if keywords else '核心技术'} 的底层原理与源码实现",
            "2. 通过系统性参与实际项目积累架构设计和性能优化经验",
        ]
        if total_rounds < 8:
            suggestions.append("3. 建议多参加真实面试场景的模拟，锻炼在压力下的清晰表达能力")
        suggestions.append(
            f"4. 关注 {keywords[1] if len(keywords) > 1 else '相关技术'} 领域的行业最佳实践与技术趋势"
        )
        suggestions.append(
            "5. 定期整理和复盘项目经验，培养'用数据说话'的量化成果意识"
        )

    # 构建反馈
    score_level = (
        "深入扎实" if avg_score >= 85 else
        "良好" if avg_score >= 75 else
        "中等偏上" if avg_score >= 65 else
        "基础水平" if avg_score >= 50 else
        "有待提升" if avg_score >= 30 else
        "暂无有效评估数据"
    )

    feedback = {
        "总体评价": overall,
        "核心优势": "\n".join(f"- {s}" for s in strengths),
        "薄弱环节": "\n".join(f"- {w}" for w in weaknesses),
        "详细分析": (
            f"技术深度：{scores['技术深度']}分——{'对核心技术有较深入理解' if scores['技术深度'] >= 70 else '技术基础较扎实，需加强深层原理学习' if scores['技术深度'] >= 50 else '暂未展示足够的技术深度'}。\n"
            f"逻辑表达：{scores['逻辑表达']}分——{'表达条理清晰、结构化程度好' if scores['逻辑表达'] >= 70 else '表达基本清晰，可进一步提升结构化能力' if scores['逻辑表达'] >= 50 else '暂未展示充分的逻辑表达能力'}。\n"
            f"专业知识广度：{scores['专业知识广度']}分——{'技术栈覆盖较广' if scores['专业知识广度'] >= 70 else '专业知识有一定基础，可扩展广度' if scores['专业知识广度'] >= 50 else '暂未展示充分的知识广度'}。\n"
            f"应变能力：{scores['应变与解决问题能力']}分——{'面对追问反应敏捷' if scores['应变与解决问题能力'] >= 70 else '在基础问题上表现稳定' if scores['应变与解决问题能力'] >= 50 else '暂未获得充分评估数据'}。\n"
            f"沟通协作：{scores['沟通与协作素养']}分——{'展现出良好的团队协作意识' if scores['沟通与协作素养'] >= 70 else '沟通态度积极' if scores['沟通与协作素养'] >= 50 else '暂未展示团队协作相关素养'}。\n"
            f"项目实践：{scores['项目实践能力']}分——{'项目经验丰富且能深入讲解' if scores['项目实践能力'] >= 70 else '具备一定的项目实践基础' if scores['项目实践能力'] >= 50 else '暂未展示充分的项目实践经验'}。"
        ),
        "改进建议": "\n".join(suggestions),
    }

    return scores, feedback


# ===== 核心评估函数 =====

async def evaluate_interview(
    dialogue_history: list[dict],
    keywords: list[str],
) -> Tuple[Dict[str, int], Dict[str, str]]:
    """
    调用 DeepSeek API 对面试进行六维评估。

    Args:
        dialogue_history: 完整对话历史 [{"role": "user/assistant", "content": "..."}]
        keywords: 简历技术栈关键词

    Returns:
        (radar_scores, ai_feedback):
        - radar_scores: {"技术深度": 72, "逻辑表达": 68, ...}  共6个维度
        - ai_feedback: {"总体评价": "...", "核心优势": "...", "薄弱环节": "...", ...}
    """
    # 序列化对话为可读文本
    dialogue_text_parts = []
    for msg in dialogue_history:
        role_label = "候选人" if msg.get("role") == "user" else "面试官"
        dialogue_text_parts.append(
            f"[{role_label}]: {msg.get('content', '')}"
        )
    dialogue_text = "\n\n".join(dialogue_text_parts)

    # 统计对话信息
    user_messages = [m for m in dialogue_history if m.get("role") == "user"]
    total_rounds = len(user_messages)
    tech_str = "、".join(keywords) if keywords else "通用技术"

    round_note = ""
    if total_rounds <= 2:
        round_note = (
            "(注意: 本次面试对话轮次较少。"
            "如果候选人几乎没有实质回答，请如实给出低分（10-30分）。"
            "所有维度都必须给出具体分数，不得留空或标记为无法评估。)"
        )

    user_prompt = (
        f"## 候选人的技术栈\n{tech_str}\n\n"
        f"## 对话统计\n- 候选人发言轮次：{total_rounds}\n"
        f"- 面试官发言轮次：{len(dialogue_history) - total_rounds}\n"
        f"{round_note}\n\n"
        f"## 完整面试对话记录\n{dialogue_text}\n\n"
        f"请根据以上对话，输出评估 JSON。"
    )

    messages = [
        {"role": "system", "content": EVALUATION_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    # 尝试调用 DeepSeek
    if not settings.DEEPSEEK_API_KEY:
        logger.warning("DeepSeek API Key 未配置，使用启发式降级评估")
        return _heuristic_evaluation(dialogue_history, keywords)

    try:
        response = await chat_completion(
            messages=messages,
            temperature=0.3,
            max_tokens=2048,
        )

        # 提取 JSON
        json_str = response.strip()
        if json_str.startswith("```"):
            lines = json_str.split("\n")
            json_str = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])

        evaluation = json.loads(json_str)

        scores = evaluation.get("radar_scores", {})
        feedback = evaluation.get("ai_feedback", {})

        # 校验必填维度（6个维度）
        required_dims = [
            "技术深度", "逻辑表达", "专业知识广度",
            "应变与解决问题能力", "沟通与协作素养", "项目实践能力",
        ]
        fallback_count = 0
        for dim in required_dims:
            if dim not in scores or scores[dim] is None:
                scores[dim] = 20  # 缺失维度给低分，而非默认及格
                fallback_count += 1
            elif not isinstance(scores[dim], (int, float)) or scores[dim] < 0 or scores[dim] > 100:
                scores[dim] = 20
                fallback_count += 1
            else:
                scores[dim] = int(scores[dim])

        # 校验必填反馈字段（5个字段）
        required_feedback = ["总体评价", "核心优势", "薄弱环节", "详细分析", "改进建议"]
        for key in required_feedback:
            if key not in feedback or not feedback[key]:
                feedback[key] = "评估生成中，暂无此维度详情"

        logger.info(
            f"AI 评估完成: dims={list(scores.keys())}, "
            f"avg={sum(scores.values()) / len(scores):.1f}"
        )
        return scores, feedback

    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"AI 评估 JSON 解析失败: {e}")
        return _heuristic_evaluation(dialogue_history, keywords)

    except (ValueError, RuntimeError) as e:
        logger.warning(f"AI 评估调用失败，降级为启发式: {e}")
        return _heuristic_evaluation(dialogue_history, keywords)

    except Exception as e:
        logger.exception(f"AI 评估异常: {e}")
        return _heuristic_evaluation(dialogue_history, keywords)