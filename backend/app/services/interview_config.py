"""
面试阶段配置加载器

从 interview_config.yaml 读取面试阶段定义，提供结构化配置数据。
支持运行时热更新和默认值降级。
"""

import logging
import os
from pathlib import Path
from typing import Optional
import yaml

logger = logging.getLogger(__name__)

# 配置文件路径（相对于本模块）
_CONFIG_PATH = Path(__file__).parent / "interview_config.yaml"

# 默认配置（当 YAML 文件缺失或解析失败时使用）
_DEFAULT_CONFIG: dict = {
    "max_turns": 15,
    "phases": [
        {
            "name": "简历介绍与自我介绍",
            "rounds": [1, 2],
            "description": "开场破冰",
            "instructions": "引导候选人做自我介绍，简单了解背景后自然过渡。",
        },
        {
            "name": "技术能力考察",
            "rounds": [3, 8],
            "description": "技术考察",
            "instructions": "围绕技术栈深入提问，从基础概念到项目实战逐步递进。",
        },
        {
            "name": "压力面试",
            "rounds": [9, 11],
            "description": "压力追问",
            "instructions": "高压追问，质疑回答，考察抗压能力和思维深度。",
        },
        {
            "name": "职业素养与人品考察",
            "rounds": [12, 13],
            "description": "素养人品评估",
            "instructions": "考察责任心、诚信度、团队精神、价值观等软素质。",
        },
        {
            "name": "公司情况询问与期望了解",
            "rounds": [14, 15],
            "description": "双向沟通与收尾",
            "instructions": "介绍公司、了解期望、给出评价、感谢参与。",
        },
    ],
    "global_instructions": "保持专业、自然、尊重候选人。",
}

# 运行时缓存
_cached_config: Optional[dict] = None
_cached_mtime: float = 0


def _load_raw_config() -> dict:
    """从 YAML 文件加载原始配置，失败时返回默认配置"""
    try:
        if not _CONFIG_PATH.exists():
            logger.warning(f"配置文件不存在: {_CONFIG_PATH}，使用默认配置")
            return _DEFAULT_CONFIG.copy()

        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        if not config or not isinstance(config, dict):
            logger.warning("配置文件为空或格式错误，使用默认配置")
            return _DEFAULT_CONFIG.copy()

        # 校验必要字段
        if "max_turns" not in config:
            config["max_turns"] = _DEFAULT_CONFIG["max_turns"]
        if "phases" not in config or not config["phases"]:
            config["phases"] = _DEFAULT_CONFIG["phases"]

        return config

    except yaml.YAMLError as e:
        logger.error(f"YAML 解析失败: {e}，使用默认配置")
        return _DEFAULT_CONFIG.copy()
    except Exception as e:
        logger.error(f"加载配置文件异常: {e}，使用默认配置")
        return _DEFAULT_CONFIG.copy()


def get_config(force_reload: bool = False) -> dict:
    """
    获取面试阶段配置（带缓存，仅文件修改后自动刷新）。

    Args:
        force_reload: 强制重新加载（管理员修改配置后调用）

    Returns:
        {
            "max_turns": 15,
            "phases": [
                {"name": "...", "rounds": [1, 2], "description": "...", "instructions": "..."},
                ...
            ],
            "global_instructions": "..."
        }
    """
    global _cached_config, _cached_mtime

    if not force_reload and _cached_config is not None:
        try:
            current_mtime = _CONFIG_PATH.stat().st_mtime if _CONFIG_PATH.exists() else 0
            if current_mtime <= _cached_mtime:
                return _cached_config
        except OSError:
            pass

    _cached_config = _load_raw_config()
    try:
        _cached_mtime = _CONFIG_PATH.stat().st_mtime if _CONFIG_PATH.exists() else 0
    except OSError:
        _cached_mtime = 0

    logger.debug(f"配置已加载: max_turns={_cached_config['max_turns']}, phases={len(_cached_config['phases'])}")
    return _cached_config


def get_phase_for_turn(turn: int, config: Optional[dict] = None) -> dict | None:
    """
    根据当前轮次找到对应阶段。

    Returns:
        {"name": "技术能力考察", "rounds": [3, 8], ...} 或 None
    """
    if config is None:
        config = get_config()

    for phase in config.get("phases", []):
        rounds = phase.get("rounds", [])
        if len(rounds) == 2 and rounds[0] <= turn <= rounds[1]:
            return phase

    return None


def get_progress_hint(turn: int, max_turns: int) -> str:
    """
    根据当前轮次生成面试进度提示文本。

    Args:
        turn: 当前轮次（1-based）
        max_turns: 最大轮次
    """
    remaining = max_turns - turn
    config = get_config()
    phase = get_phase_for_turn(turn, config)

    if remaining <= 0:
        return (
            "THE INTERVIEW MUST END NOW. 面试已达到预定轮次上限。"
            "请在本轮直接进行面试总结：简短评价候选人的整体表现，感谢参与，"
            "告知后续流程，并自然地结束面试。不要再提任何新问题。这是最后一轮。"
        )

    if remaining == 1:
        return (
            f"这是倒数第1轮（共{max_turns}轮）。必须在接下来2轮内完成收尾。"
            "不要再深入新技术话题。开始总结面试并邀请候选人提问。"
        )

    if remaining == 2:
        return (
            f"还剩约2轮（共{max_turns}轮）。请在接下来2轮内自然过渡到收尾阶段。"
        )

    if phase:
        phase_name = phase["name"]
        desc = phase.get("description", "")
        instructions = phase.get("instructions", "")

        # 截取前200字符的关键指令
        short_instructions = instructions[:200] + "..." if len(instructions) > 200 else instructions
        return (
            f"当前阶段：{phase_name}（{desc}）\n\n"
            f"阶段指导：\n{short_instructions}"
        )

    return f"当前处于第{turn}轮，请根据对话上下文自然地继续面试。"


def update_config_file(new_content: str) -> tuple[bool, str]:
    """
    更新配置文件内容（管理员编辑接口调用）。

    Args:
        new_content: 新的 YAML 内容字符串

    Returns:
        (success, message)
    """
    try:
        # 先验证 YAML 格式
        parsed = yaml.safe_load(new_content)
        if not isinstance(parsed, dict):
            return False, "配置内容必须是有效的 YAML 字典格式"

        if "max_turns" not in parsed:
            return False, "缺少 max_turns 字段"

        if "phases" not in parsed or not isinstance(parsed["phases"], list):
            return False, "缺少 phases 字段或格式不正确"

        # 写入文件
        with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
            f.write(new_content)

        # 强制刷新缓存
        get_config(force_reload=True)

        logger.info(f"面试配置已更新: max_turns={parsed['max_turns']}")
        return True, "配置更新成功"

    except yaml.YAMLError as e:
        return False, f"YAML 格式错误: {e}"
    except Exception as e:
        logger.exception(f"配置文件写入失败: {e}")
        return False, f"写入失败: {e}"


def get_config_file_path() -> str:
    """返回配置文件绝对路径（供前端展示）"""
    return str(_CONFIG_PATH.resolve())