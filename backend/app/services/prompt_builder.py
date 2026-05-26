"""
面试 Prompt 构建器 —— 基于 interview_config.yaml 的阶段配置生成系统提示词和欢迎消息。

核心改进：
- 从 YAML 配置文件读取面试阶段定义（可热更新）
- 系统提示词根据当前轮次动态匹配阶段指令
- 开场白：优先 LLM 生成，不可用时使用增强模板
"""

import logging
from typing import Optional
from app.config import settings
from app.services.llm_client import chat_completion as _llm_chat
from app.services.interview_config import (
    get_config,
    get_progress_hint,
)

logger = logging.getLogger(__name__)

# ========== 面试类型配置 ==========

INTERVIEW_TYPES = {
    "technical": {
        "label": "基础技术面",
        "focus": "编程语言基础、数据结构与算法、计算机网络、操作系统、数据库等核心计算机基础知识",
    },
    "pressure": {
        "label": "压力面试",
        "focus": "高压追问、技术深度挑战、边界条件分析、架构决策批判性思考、抗压能力",
    },
    "friendly": {
        "label": "轻松聊天",
        "focus": "职业发展规划、项目经验交流、技术兴趣探索、团队协作",
    },
}

# 兼容旧代码：从配置文件读取的默认最大轮次
# 实际值在 get_system_prompt() 中从配置动态获取
_FALLBACK_MAX_TURNS = 15

# ===================================================================
# 系统提示词模板（使用配置文件的阶段指令）
# ===================================================================

_SYSTEM_PROMPT_TEMPLATE = """你是一位资深技术面试官，负责对候选人进行 {interview_label}。

## 你的角色
- 专业、严谨、善于引导候选人展示真实技术水平和综合素质
- 面试风格：{style_instruction}
- 面试考察重点：{focus_areas}

## 候选人背景
候选人简历中的技术栈关键词：{keywords}
{position_guidance}

## 面试流程规则

{phase_specific_instructions}

## 全局规则
{global_instructions}

## 当前对话信息
- 总轮次限制：{max_turns} 轮
- 当前轮次：第 {turn} 轮
{progress_hint}

## 对话风格
{conversation_tone}

## 输出格式
- 使用自然流利的中文
- 直接输出你要对候选人说的话
- 不要输出任何标记、标签或格式符号"""

_STYLE_INSTRUCTIONS = {
    "technical": "客观严谨，以知识考察为核心，注重技术深度和工程实践的结合",
    "pressure": "具有挑战性和压迫感，追问边界条件和异常场景，考察候选人在压力下的思维深度和抗压能力",
    "friendly": "轻松自然但保持面试的专业性，关注候选人的职业发展和项目经验，像同行交流",
}

_CONVERSATION_TONES = {
    "technical": "使用专业但易懂的技术语言，保持面试官的专业距离感但不过于冷漠。适当使用'换个角度思考'、'深入一层的话'等引导追问。",
    "pressure": "语气坚定但礼貌，追问时不给候选人喘息空间但保持基本尊重。适当使用'有没有考虑过...'、'如果上线后出问题你会怎么排查'、'我觉得你的方案有明显缺陷，你反思一下'等压力追问。",
    "friendly": "语气亲切平和，像同行之间的技术交流。适当分享共鸣或肯定，营造轻松的对话氛围同时保持专业。",
}

# ========== 开场白 LLM Prompt ==========

_WELCOME_LLM_PROMPT = """你是一位经验丰富的技术面试官，需要为候选人定制开场白。

候选人简历中的技术栈：{keywords}
{position_context}
面试类型：{interview_label}

请生成一段3-5句的开场白，要求：
1. 简要介绍自己是面试官，说明本次是{interview_label}
2. 提及候选人的关键技术栈（至少提到2-3个），表达你已了解其背景
3. {position_requirement}
4. 语言专业、亲切、自然

只输出开场白内容，不要输出任何其他文字。"""


# ===================================================================
# 公共函数
# ===================================================================

def _build_phase_instructions(turn: int, config: dict) -> tuple[str, str]:
    """
    根据轮次构建阶段专属指令和全局指令。

    Returns:
        (phase_instructions, global_instructions)
    """
    global_instructions = config.get("global_instructions", "")

    # 获取当前阶段的详细指令
    from app.services.interview_config import get_phase_for_turn
    phase = get_phase_for_turn(turn, config)

    if phase:
        phase_name = phase["name"]
        phase_instructions = phase.get("instructions", "")
        return (
            f"### 当前阶段：{phase_name}\n{phase_instructions}",
            global_instructions,
        )

    # 超过最大轮次
    if turn > config.get("max_turns", 15):
        return (
            "### 面试结束\n面试已超过最大轮次，请立即总结并结束面试。",
            global_instructions,
        )

    return (
        "### 开场\n请根据候选人背景自然开启面试流程。",
        global_instructions,
    )


def get_system_prompt(
    keywords: list[str],
    interview_type: str = "technical",
    turn: int = 1,
    max_turns: int | None = None,
    position_name: str | None = None,
) -> str:
    """
    构建面试系统 Prompt（每次对话请求时调用）。

    从 interview_config.yaml 读取阶段配置，根据当前轮次匹配对应的阶段指令。

    Args:
        keywords: 简历技术栈关键词
        interview_type: 面试类型 (technical/pressure/friendly)
        turn: 当前轮次（用户已发送的消息数+1）
        max_turns: 最大对话轮次（None 时从配置文件读取）
        position_name: 求职岗位名称（None 时使用通用面试方向）
    """
    type_config = INTERVIEW_TYPES.get(interview_type, INTERVIEW_TYPES["technical"])
    keywords_str = "、".join(keywords) if keywords else "通用软件开发"

    # 从配置文件读取阶段配置
    config = get_config()
    if max_turns is None:
        max_turns = config.get("max_turns", _FALLBACK_MAX_TURNS)

    # 构建阶段指令
    phase_instructions, global_instructions = _build_phase_instructions(turn, config)

    # 生成进度提示
    progress_hint = get_progress_hint(turn, max_turns)

    # ---- 岗位分析：生成针对性提问指导 ----
    if position_name:
        try:
            from app.services.position_analyzer import (
                analyze_position,
                get_position_focus,
                get_position_questioning_guide,
            )
            pos_data = analyze_position(position_name)
            focus = get_position_focus(pos_data)
            questioning_guide = get_position_questioning_guide(pos_data)
            position_guidance = (
                f"\n## 求职目标岗位\n"
                f"候选人求职岗位为 **{position_name}**，请围绕该岗位的核心能力要求进行面试。\n\n"
                f"### 岗位核心考察方向\n{focus}\n\n"
                f"### 岗位定向提问指导\n{questioning_guide}"
            )
            logger.info(f"System Prompt 已注入岗位定向指导 | position={position_name}")
        except Exception as e:
            logger.warning(f"岗位分析失败，使用通用面试方向: {e}")
            position_guidance = ""
    else:
        position_guidance = ""

    return _SYSTEM_PROMPT_TEMPLATE.format(
        interview_label=type_config["label"],
        style_instruction=_STYLE_INSTRUCTIONS.get(interview_type, _STYLE_INSTRUCTIONS["technical"]),
        focus_areas=type_config["focus"],
        keywords=keywords_str,
        position_guidance=position_guidance,
        turn=turn,
        max_turns=max_turns,
        phase_specific_instructions=phase_instructions,
        global_instructions=global_instructions,
        progress_hint=progress_hint,
        conversation_tone=_CONVERSATION_TONES.get(interview_type, _CONVERSATION_TONES["technical"]),
    )


def build_messages(
    system_prompt: str,
    dialogue_history: list[dict[str, str]],
    rag_context: str = "",
) -> list[dict[str, str]]:
    """构建完整的对话消息序列（System Prompt + RAG 上下文 + 历史对话）。"""
    if rag_context:
        augmented_prompt = (
            f"{system_prompt}\n\n"
            f"## 题库参考（可参考但不强制使用，请优先基于对话上下文自适应提问）\n{rag_context}"
        )
    else:
        augmented_prompt = system_prompt

    messages: list[dict[str, str]] = [
        {"role": "system", "content": augmented_prompt},
    ]

    for msg in dialogue_history:
        role = "assistant" if msg["role"] in ("interviewer", "system", "assistant") else "user"
        messages.append({"role": role, "content": msg.get("content", "")})

    return messages


async def build_welcome_message(
    keywords: list[str],
    interview_type: str = "technical",
    position_name: str | None = None,
) -> str:
    """生成面试开场白。优先 LLM，不可用时用模板。

    Args:
        keywords: 技术栈关键词列表
        interview_type: 面试类型
        position_name: 求职岗位名称（用于生成岗位定向的开场白）
    """
    type_config = INTERVIEW_TYPES.get(interview_type, INTERVIEW_TYPES["technical"])
    keywords_str = "、".join(keywords) if keywords else "通用软件开发"

    # 构建岗位相关的上下文
    if position_name:
        try:
            from app.services.position_analyzer import analyze_position
            pos_data = analyze_position(position_name)
            position_context = f"候选人求职目标岗位：{position_name}\n"
            position_requirement = (
                f"自然地邀请候选人做自我介绍，可以提及你对该岗位（{position_name}）"
                f"的核心能力要求有所关注"
            )
            logger.info(f"开场白已注入岗位上下文 | position={position_name}")
        except Exception as e:
            logger.warning(f"岗位信息获取失败: {e}")
            position_context = ""
            position_requirement = "自然地邀请候选人做自我介绍"
    else:
        position_context = ""
        position_requirement = "自然地邀请候选人做自我介绍"

    if settings.DEEPSEEK_API_KEY:
        try:
            welcome_messages = [
                {"role": "user", "content": _WELCOME_LLM_PROMPT.format(
                    keywords=keywords_str,
                    position_context=position_context,
                    position_requirement=position_requirement,
                    interview_label=type_config["label"],
                )}
            ]
            welcome_text = await _llm_chat(messages=welcome_messages, temperature=0.7, max_tokens=256)
            if welcome_text and welcome_text.strip():
                return welcome_text.strip()
        except Exception as e:
            logger.warning(f"LLM 开场白生成失败，降级: {e}")

    # 模板降级
    position_prefix = f"我看到你的求职目标是 **{position_name}**，" if position_name else ""
    templates = {
        "technical": (
            f"你好！我是今天的AI面试官，很高兴能和你进行这次技术面试。"
            f"{position_prefix}我注意到你的技术栈涵盖了 {keywords_str} 等领域，"
            f"我会围绕这些方向和你深入交流。请先简单介绍一下你自己，包括你的技术专长和项目经验。"
        ),
        "pressure": (
            f"你好，我是今天负责压力面试的面试官。"
            f"{position_prefix}我看到你的简历涉及 {keywords_str}，今天的面试会比较有挑战性——"
            f"我会对你的技术深度的边界进行追问。准备好了吗？请先做一下自我介绍。"
        ),
        "friendly": (
            f"嗨！欢迎参加今天的面试，轻松聊一聊就好。"
            f"{position_prefix}我看到你在 {keywords_str} 方面有不错的经验，我对你的项目经历很感兴趣。"
            f"先简单介绍一下你自己吧，聊聊你做过的有意思的项目！"
        ),
    }
    return templates.get(interview_type, templates["technical"])


def build_simple_welcome(keywords: list[str], interview_type: str = "technical") -> str:
    """同步版简易开场白（不依赖 LLM）。"""
    type_config = INTERVIEW_TYPES.get(interview_type, INTERVIEW_TYPES["technical"])
    kw = keywords[:6] if keywords else ["软件开发"]
    kw_str = "、".join(kw)

    templates = {
        "technical": f"你好！我是今天的AI技术面试官。我注意到你的技术背景涉及 {kw_str} 等方向，我会围绕这些领域和你深入交流。请先简单介绍一下你自己。",
        "pressure": f"你好，我是今天的面试官。你的简历涵盖了 {kw_str}，今天的面试会比较有挑战性。准备好了吗？请先做一下自我介绍。",
        "friendly": f"嗨！欢迎来聊天。你提到擅长 {kw_str}，很有趣的方向。先简单介绍下你自己吧！",
    }
    return templates.get(interview_type, templates["technical"])


# ======== 兼容旧导入 ==============

def get_max_turns() -> int:
    """获取当前配置的最大轮次（提供给 interview.py 使用）"""
    config = get_config()
    return config.get("max_turns", _FALLBACK_MAX_TURNS)

# 模块级常量：启动时从配置文件读取一次
# interview.py 通过 get_max_turns() 获取实时值，此常量仅为兼容旧导入
DEFAULT_MAX_TURNS = _FALLBACK_MAX_TURNS