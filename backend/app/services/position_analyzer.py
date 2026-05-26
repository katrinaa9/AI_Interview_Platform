"""
岗位分析引擎 —— 从简历文本中识别求职岗位，输出职位核心能力和面试方向。

核心功能：
1. 从简历中提取求职岗位（通过关键词、分段上下文匹配）
2. 建立岗位-技术栈关联模型，定义每个岗位的核心技术权重体系
3. 为 Generate_question 模块提供岗位定向的问题生成指导
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ===================================================================
# 岗位定义：每个岗位包含核心能力要求、加权技术栈、常见面试方向
# ===================================================================

# 技术栈权重分级（用于给提取到的关键词排序和加权）
WEIGHT_CRITICAL = 1.2    # 岗位核心技术（最高优先级）
WEIGHT_IMPORTANT = 1.0   # 相关重要技术
WEIGHT_NICE_TO_HAVE = 0.8  # 加分项
WEIGHT_IRRELEVANT = 0.3  # 无关技术（仍保留但降权）


POSITIONS: dict = {
    "算法工程师": {
        "keywords": ["算法", "算法工程师", "机器学习工程师", "深度学习", "AI工程师",
                      "NLP", "计算机视觉", "推荐算法", "搜索算法", "数据挖掘",
                      "强化学习", "因果推断", "图神经网络"],
        "core_competencies": [
            "机器学习/深度学习理论基础",
            "概率统计与数学推导能力",
            "数据清洗与特征工程",
            "模型选型、训练、评估与调优",
            "算法工程化部署（模型压缩/量化/蒸馏）",
            "算法前沿论文阅读与复现能力",
        ],
        "tech_weights": {
            "PyTorch": WEIGHT_CRITICAL,
            "TensorFlow": WEIGHT_CRITICAL,
            "Python": WEIGHT_CRITICAL,
            "机器学习": WEIGHT_CRITICAL,
            "深度学习": WEIGHT_CRITICAL,
            "Scikit-learn": WEIGHT_IMPORTANT,
            "Pandas": WEIGHT_IMPORTANT,
            "NumPy": WEIGHT_IMPORTANT,
            "NLP": WEIGHT_IMPORTANT,
            "计算机视觉": WEIGHT_IMPORTANT,
            "大模型": WEIGHT_CRITICAL,
            "RAG": WEIGHT_IMPORTANT,
            "Docker": WEIGHT_IMPORTANT,
            "Kubernetes": WEIGHT_NICE_TO_HAVE,
            "Git": WEIGHT_IMPORTANT,
            "Linux": WEIGHT_IMPORTANT,
            "MySQL": WEIGHT_IMPORTANT,
            "Redis": WEIGHT_NICE_TO_HAVE,
        },
        "focus_areas": (
            "机器学习算法原理、深度学习框架（PyTorch/TensorFlow）、"
            "模型训练与调优、特征工程、算法工程化部署、"
            "大模型应用（RAG/Fine-tuning/Prompt Engineering）、数学基础（概率统计/线性代数）"
        ),
        "sample_questions": [
            "请解释Transformer模型的核心机制，以及它为什么比RNN更适合处理长序列？",
            "描述你在项目中遇到过的过拟合问题，你使用了哪些正则化技术来解决？",
            "大模型应用中，RAG和Fine-tuning各自的适用场景是什么？",
        ],
    },

    "前端开发": {
        "keywords": ["前端", "前端开发", "前端工程师", "Web前端", "React", "Vue",
                      "JavaScript", "TypeScript", "H5", "小程序"],
        "core_competencies": [
            "JavaScript/TypeScript 语言深度理解",
            "主流框架（React/Vue/Angular）精通至少一种",
            "前端工程化（Webpack/Vite/CI/CD）实操经验",
            "性能优化与跨浏览器兼容性处理",
            "前端安全（XSS/CSRF）与可访问性",
            "组件化设计模式与状态管理",
        ],
        "tech_weights": {
            "React": WEIGHT_CRITICAL,
            "Vue": WEIGHT_CRITICAL,
            "JavaScript": WEIGHT_CRITICAL,
            "TypeScript": WEIGHT_CRITICAL,
            "HTML5": WEIGHT_CRITICAL,
            "CSS3": WEIGHT_CRITICAL,
            "Webpack": WEIGHT_IMPORTANT,
            "Vite": WEIGHT_IMPORTANT,
            "Redux": WEIGHT_IMPORTANT,
            "Zustand": WEIGHT_IMPORTANT,
            "Next.js": WEIGHT_IMPORTANT,
            "Tailwind CSS": WEIGHT_IMPORTANT,
            "Ant Design": WEIGHT_NICE_TO_HAVE,
            "Node.js": WEIGHT_IMPORTANT,
            "GraphQL": WEIGHT_NICE_TO_HAVE,
            "Docker": WEIGHT_NICE_TO_HAVE,
            "Git": WEIGHT_IMPORTANT,
            "Figma": WEIGHT_NICE_TO_HAVE,
        },
        "focus_areas": (
            "JavaScript/TypeScript 深度、React/Vue 框架原理、"
            "前端工程化与性能优化、CSS 布局与响应式、"
            "浏览器渲染原理、前端安全与可访问性"
        ),
        "sample_questions": [
            "React中Virtual DOM的diff算法时间复杂度是多少？为什么？",
            "请解释浏览器从输入URL到页面渲染的完整过程。",
            "你如何调试一个在特定浏览器上才出现的布局问题？",
        ],
    },

    "后端开发": {
        "keywords": ["后端", "后端开发", "后端工程师", "服务端", "Java开发",
                      "Golang", "Python开发", "Node.js", "API开发"],
        "core_competencies": [
            "至少一门后端语言精通（Java/Python/Golang等）",
            "关系型数据库设计与优化（索引/查询/Schema）",
            "分布式系统设计模式（CAP/Paxos/Raft基础理解）",
            "高并发与性能调优实战",
            "API 接口设计与微服务架构",
            "系统安全（认证/授权/SQL注入防护）",
        ],
        "tech_weights": {
            "Java": WEIGHT_CRITICAL,
            "Python": WEIGHT_CRITICAL,
            "Golang": WEIGHT_CRITICAL,
            "Spring Boot": WEIGHT_CRITICAL,
            "MySQL": WEIGHT_CRITICAL,
            "Redis": WEIGHT_IMPORTANT,
            "Docker": WEIGHT_IMPORTANT,
            "Kubernetes": WEIGHT_IMPORTANT,
            "PostgreSQL": WEIGHT_IMPORTANT,
            "MongoDB": WEIGHT_NICE_TO_HAVE,
            "Kafka": WEIGHT_IMPORTANT,
            "微服务": WEIGHT_IMPORTANT,
            "Linux": WEIGHT_IMPORTANT,
            "Git": WEIGHT_IMPORTANT,
            "Nginx": WEIGHT_IMPORTANT,
            "CI/CD": WEIGHT_IMPORTANT,
        },
        "focus_areas": (
            "后端语言精通、数据库设计与优化、"
            "分布式系统与高并发、微服务架构设计、"
            "系统安全与性能调优"
        ),
        "sample_questions": [
            "请解释MySQL中InnoDB的MVCC机制是如何工作的？",
            "在高并发场景下，Redis缓存穿透、击穿、雪崩分别是什么意思？如何应对？",
            "如果你设计一个秒杀系统，你会如何保证库存不超卖？",
        ],
    },

    "全栈开发": {
        "keywords": ["全栈", "全栈开发", "全栈工程师", "Full Stack", "前后端"],
        "core_competencies": [
            "前后端技术栈的全面覆盖",
            "系统架构设计与技术选型能力",
            "数据库设计与API设计",
            "项目从零到一搭建的完整经验",
            "前端框架 + 后端框架的深度掌握",
        ],
        "tech_weights": {
            "React": WEIGHT_CRITICAL,
            "Vue": WEIGHT_CRITICAL,
            "TypeScript": WEIGHT_CRITICAL,
            "JavaScript": WEIGHT_CRITICAL,
            "Node.js": WEIGHT_CRITICAL,
            "Python": WEIGHT_CRITICAL,
            "Java": WEIGHT_IMPORTANT,
            "MySQL": WEIGHT_CRITICAL,
            "PostgreSQL": WEIGHT_IMPORTANT,
            "Redis": WEIGHT_IMPORTANT,
            "Docker": WEIGHT_CRITICAL,
            "Kubernetes": WEIGHT_IMPORTANT,
            "Git": WEIGHT_IMPORTANT,
            "Linux": WEIGHT_IMPORTANT,
            "微服务": WEIGHT_IMPORTANT,
            "CI/CD": WEIGHT_IMPORTANT,
            "GraphQL": WEIGHT_NICE_TO_HAVE,
            "MongoDB": WEIGHT_NICE_TO_HAVE,
        },
        "focus_areas": (
            "前后端全链路技术栈、系统架构能力、"
            "数据库设计与API设计、项目从零到一经验、"
            "技术选型与团队协作"
        ),
        "sample_questions": [
            "请描述一个你从零搭建的全栈项目，你的技术选型思路是什么？",
            "在前后端分离架构中，你如何处理认证与授权流程？",
            "如果你要为一个新项目选择技术栈，你的决策框架是什么？",
        ],
    },

    "DevOps/SRE": {
        "keywords": ["DevOps", "运维", "SRE", "基础设施", "云原生",
                      "CI/CD", "平台工程", "系统管理员"],
        "core_competencies": [
            "CI/CD 流水线设计与实现",
            "容器化与编排（Docker/Kubernetes）",
            "云平台（AWS/阿里云/Azure）使用经验",
            "监控告警系统搭建（Prometheus/Grafana）",
            "IaC（Terraform/Ansible）自动化运维",
            "网络与安全基础",
        ],
        "tech_weights": {
            "Docker": WEIGHT_CRITICAL,
            "Kubernetes": WEIGHT_CRITICAL,
            "Linux": WEIGHT_CRITICAL,
            "AWS": WEIGHT_CRITICAL,
            "阿里云": WEIGHT_CRITICAL,
            "CI/CD": WEIGHT_CRITICAL,
            "Jenkins": WEIGHT_IMPORTANT,
            "GitHub Actions": WEIGHT_IMPORTANT,
            "Terraform": WEIGHT_IMPORTANT,
            "Prometheus": WEIGHT_IMPORTANT,
            "Grafana": WEIGHT_IMPORTANT,
            "Nginx": WEIGHT_IMPORTANT,
            "Python": WEIGHT_IMPORTANT,
            "Shell": WEIGHT_IMPORTANT,
            "Git": WEIGHT_IMPORTANT,
            "MySQL": WEIGHT_NICE_TO_HAVE,
            "Redis": WEIGHT_NICE_TO_HAVE,
        },
        "focus_areas": (
            "CI/CD 流水线、Docker/Kubernetes 容器编排、"
            "云平台运维、监控与可观测性、"
            "基础设施即代码（IaC）、系统安全与网络"
        ),
        "sample_questions": [
            "Kubernetes中Pod的调度流程是怎样的？请解释调度器的核心算法。",
            "你如何为一个分布式系统设计监控告警策略？关键指标有哪些？",
            "描述一个你处理过的线上故障排查和恢复过程。",
        ],
    },
}

# 默认岗位（无法识别时使用）
DEFAULT_POSITION = {
    "name": "软件开发工程师",
    "core_competencies": [
        "编程语言基础扎实",
        "数据结构与算法基础",
        "至少熟悉一种主流框架",
        "基本的数据库操作能力",
        "团队协作与沟通能力",
    ],
    "tech_weights": {},
    "focus_areas": "编程基础、数据结构与算法、主流框架使用、数据库基础",
    "sample_questions": [],
}


# ===================================================================
# 岗位提取
# ===================================================================

def extract_position_from_text(text: str) -> Optional[str]:
    """
    从简历文本中识别求职岗位。

    策略：
    1. 搜索简历中明确标注的「求职意向/期望岗位/目标职位」关键词后的内容
    2. 若没有明确标注，扫描全文匹配职位关键词
    3. 返回最佳匹配的岗位名称，若无法识别返回 None

    Args:
        text: 简历全文

    Returns:
        岗位名称或 None
    """
    if not text:
        return None

    # ---- 策略 1: 精确匹配求职意向行 ----
    intent_patterns = [
        r"求职意向[：:]\s*(.+?)(?:\n|$)",
        r"期望岗位[：:]\s*(.+?)(?:\n|$)",
        r"目标职位[：:]\s*(.+?)(?:\n|$)",
        r"应聘岗位[：:]\s*(.+?)(?:\n|$)",
        r"求职岗位[：:]\s*(.+?)(?:\n|$)",
        r"意向职位[：:]\s*(.+?)(?:\n|$)",
        r"目标岗位[：:]\s*(.+?)(?:\n|$)",
    ]

    for pattern in intent_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            job_text = match.group(1).strip()
            if job_text:
                # 在职位库中匹配
                for position_name, config in POSITIONS.items():
                    for kw in config.get("keywords", []):
                        if kw in job_text:
                            logger.info(f"从求职意向行识别到岗位: {position_name} (匹配: {kw})")
                            return position_name
                logger.debug(f"求职意向 '{job_text}' 未匹配到已知岗位")

    # ---- 策略 2: 全文扫描职位关键词 ----
    # 统计每个职位的关键词命中次数（需至少命中2个关键词才算有效匹配）
    MIN_MATCH_THRESHOLD = 2
    position_hits: dict[str, int] = {}
    for position_name, config in POSITIONS.items():
        hits = 0
        for kw in config.get("keywords", []):
            hits += len(re.findall(re.escape(kw), text, re.IGNORECASE))
        if hits >= MIN_MATCH_THRESHOLD:
            position_hits[position_name] = hits

    if position_hits:
        # 返回命中次数最多的岗位
        best = max(position_hits, key=position_hits.get)  # type: ignore[arg-type]
        logger.info(f"全文扫描识别到岗位: {best} (命中 {position_hits[best]} 个关键词)")
        return best

    logger.info("未识别到明确岗位，将使用默认面试方向")
    return None


# ===================================================================
# 岗位分析
# ===================================================================

def analyze_position(position_name: Optional[str]) -> dict:
    """
    根据岗位名称返回结构化的面试能力模型。

    Args:
        position_name: 岗位名称，None 时返回默认岗位

    Returns:
        {
            "name": "算法工程师",
            "core_competencies": [...],
            "tech_weights": {"PyTorch": 1.2, ...},
            "focus_areas": "...",
            "sample_questions": [...]
        }
    """
    if position_name and position_name in POSITIONS:
        return {
            "name": position_name,
            **POSITIONS[position_name],
        }

    if position_name:
        logger.warning(f"未知岗位 '{position_name}'，使用默认模型")

    return {
        "name": DEFAULT_POSITION["name"],
        "core_competencies": DEFAULT_POSITION["core_competencies"],
        "tech_weights": DEFAULT_POSITION["tech_weights"],
        "focus_areas": DEFAULT_POSITION["focus_areas"],
        "sample_questions": DEFAULT_POSITION["sample_questions"],
    }


def apply_tech_weights(
    keywords: list[str],
    position: dict,
) -> list[tuple[str, float]]:
    """
    应用岗位权重对技术栈关键词进行加权排序。

    排序规则：
    1. 岗位核心技术（权重 1.2）→ 排最前
    2. 相关重要技术（权重 1.0）→ 中间
    3. 加分项/无关（0.8/0.3）→ 最后

    Args:
        keywords: 从简历提取的原始关键词列表
        position: analyze_position() 返回的岗位字典

    Returns:
        [(keyword, weight), ...] 按权重降序排列
    """
    tech_weights = position.get("tech_weights", {})

    weighted = []
    for kw in keywords:
        w = tech_weights.get(kw, WEIGHT_NICE_TO_HAVE)  # 未知技术给中等权重
        weighted.append((kw, w))

    # 按权重降序排序，同权重按字母序
    weighted.sort(key=lambda x: (-x[1], x[0]))

    return weighted


def get_position_focus(position: dict) -> str:
    """
    获取岗位的核心考察方向文本，供 System Prompt 使用。
    """
    name = position.get("name", "软件开发")
    focus = position.get("focus_areas", "")
    if focus:
        return f"{name}: {focus}"
    return name


def get_position_questioning_guide(position: dict) -> str:
    """
    为 System Prompt 生成针对特定岗位的提问指导文本。
    """
    name = position.get("name", "软件开发工程师")
    competencies = position.get("core_competencies", [])
    questions = position.get("sample_questions", [])

    parts = [f"本次面试针对的岗位：**{name}**"]
    parts.append(f"\n该岗位的核心能力要求：")
    for i, comp in enumerate(competencies, 1):
        parts.append(f"  {i}. {comp}")

    if questions:
        parts.append("\n参考提问方向（面试中使用实际对话上下文替换）：")
        for i, q in enumerate(questions, 1):
            parts.append(f"  {i}. {q}")

    return "\n".join(parts)