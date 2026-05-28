"""
测试 AI 评估引擎降级链

测试项：
1. AI 评分正常路径（LLM 返回 JSON）
2. JSON 解析失败 → 启发式规则评分
3. LLM 调用失败 → 启发式规则评分
4. 启发式评分返回完整的六维评分和五点反馈
5. 无有效回答时启发式评分给出低分
"""

import sys
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.services.evaluator import evaluate_interview, _heuristic_evaluation


# ===== 测试 1: 启发式评分完整性 =====

def test_heuristic_full_scores():
    dialogue = [
        {"role": "user", "content": "React 的 Virtual DOM 是怎么工作的？我认为是通过 diff 算法比较新旧节点树的变化。"},
        {"role": "user", "content": "在项目中我使用过 Redux 做状态管理，也接触过 TypeScript 的类型系统。"},
        {"role": "user", "content": "我们团队协作开发时，通过 Git 进行版本控制，定期进行 code review。"},
        {"role": "user", "content": "上线后出现过性能问题，我通过 Chrome DevTools 分析了渲染瓶颈并优化了组件。"},
        {"role": "user", "content": "对于分布式系统，我了解 CAP 定理，在实际项目中处理过数据一致性的问题。"},
    ]
    keywords = ["React", "TypeScript", "Redux", "JavaScript", "Git", "Docker"]
    
    scores, feedback = _heuristic_evaluation(dialogue, keywords)
    
    required_dims = ["技术深度", "逻辑表达", "专业知识广度", "应变与解决问题能力", "沟通与协作素养", "项目实践能力"]
    for dim in required_dims:
        assert dim in scores, f"缺少维度: {dim}"
        assert 0 <= scores[dim] <= 100, f"{dim} 分数超出范围: {scores[dim]}"
    
    required_feedback = ["总体评价", "核心优势", "薄弱环节", "详细分析", "改进建议"]
    for key in required_feedback:
        assert key in feedback, f"缺少反馈字段: {key}"
        assert len(feedback[key]) > 10, f"反馈内容过短: {key}"
    
    print(f"PASS: 启发式评分完整 - 分数: {scores}")
    print(f"      反馈字段齐全: {list(feedback.keys())}")


def test_heuristic_empty_response():
    """无任何有效回答时应给出低分"""
    dialogue = []
    keywords = ["React"]
    
    scores, feedback = _heuristic_evaluation(dialogue, keywords)
    
    avg = sum(scores.values()) / len(scores)
    assert avg < 30, f"无回答时平均分应低于 30，实际: {avg}"
    assert "未进行任何有效互动" in feedback["总体评价"] or "暂无" in feedback["总体评价"]
    print(f"PASS: 无回答时给出低分 - 平均分: {avg:.1f}")


def test_heuristic_short_response():
    """少于 3 轮时应给出较低的分数"""
    dialogue = [
        {"role": "user", "content": "好的"},
    ]
    keywords = ["React", "TypeScript"]
    
    scores, feedback = _heuristic_evaluation(dialogue, keywords)
    
    avg = sum(scores.values()) / len(scores)
    assert avg < 50, f"简短回答时平均分应低于 50，实际: {avg}"
    print(f"PASS: 简短回答时给出较低分 - 平均分: {avg:.1f}")


def test_heuristic_rich_response():
    """多轮详细回答应给出合理分数"""
    dialogue = [
        {"role": "user", "content": "React 的 useState 是通过闭包和链表实现的，每次渲染会创建新的状态。"},
        {"role": "user", "content": "在项目中我使用 TypeScript 定义接口，通过泛型实现可复用的组件库。"},
        {"role": "user", "content": "团队协作使用 Git 分支管理，通过 PR 流程进行代码审查。"},
        {"role": "user", "content": "上线部署使用 Docker 容器化，通过 Nginx 反向代理处理请求。"},
        {"role": "user", "content": "性能优化方面，我使用 React.memo 和 useMemo 减少不必要的重渲染。"},
        {"role": "user", "content": "数据库设计时考虑了索引优化，使用 EXPLAIN 分析查询计划。"},
    ]
    keywords = ["React", "TypeScript", "Git", "Docker", "MySQL", "Nginx"]
    
    scores, feedback = _heuristic_evaluation(dialogue, keywords)
    
    avg = sum(scores.values()) / len(scores)
    assert avg >= 40, f"丰富回答时平均分应至少 40，实际: {avg}"
    assert "React" in feedback["总体评价"] or "技术" in feedback["总体评价"]
    print(f"PASS: 丰富回答时给出合理分 - 平均分: {avg:.1f}")


# ===== 测试 2: 降级链验证 =====

async def test_evaluate_no_api_key_fallback():
    """API Key 未配置时应降级为启发式评分"""
    with patch("app.services.evaluator.settings") as mock_settings:
        mock_settings.DEEPSEEK_API_KEY = ""
        
        dialogue = [{"role": "user", "content": "React 通过 Virtual DOM 实现高效渲染。"}]
        keywords = ["React"]
        
        scores, feedback = await evaluate_interview(dialogue, keywords)
        
        required_dims = ["技术深度", "逻辑表达", "专业知识广度", "应变与解决问题能力", "沟通与协作素养", "项目实践能力"]
        for dim in required_dims:
            assert dim in scores, f"缺少维度: {dim}"
        
        print(f"PASS: API Key 未配置时降级为启发式评分 - 分数: {scores}")


async def test_evaluate_json_parse_error_fallback():
    """LLM 返回非 JSON 时应降级为启发式评分"""
    with patch("app.services.evaluator.settings") as mock_settings, \
         patch("app.services.evaluator.chat_completion") as mock_chat:
        
        mock_settings.DEEPSEEK_API_KEY = "sk-test"
        mock_chat.return_value = "这不是有效的 JSON 格式"
        
        dialogue = [{"role": "user", "content": "React 的原理是什么？"}]
        keywords = ["React"]
        
        scores, feedback = await evaluate_interview(dialogue, keywords)
        
        assert "技术深度" in scores, "应返回启发式评分结果"
        assert "核心优势" in feedback, "应包含反馈字段"
        print(f"PASS: JSON 解析失败降级为启发式评分 - 分数: {scores}")


async def test_evaluate_llm_error_fallback():
    """LLM 调用失败时应降级为启发式评分"""
    with patch("app.services.evaluator.settings") as mock_settings, \
         patch("app.services.evaluator.chat_completion") as mock_chat:
        
        mock_settings.DEEPSEEK_API_KEY = "sk-test"
        mock_chat.side_effect = RuntimeError("LLM 服务不可用")
        
        dialogue = [{"role": "user", "content": "React 的原理是什么？"}]
        keywords = ["React"]
        
        scores, feedback = await evaluate_interview(dialogue, keywords)
        
        assert "技术深度" in scores, "应返回启发式评分结果"
        print(f"PASS: LLM 调用失败降级为启发式评分 - 分数: {scores}")


if __name__ == "__main__":
    print("=" * 60)
    print("AI 评估引擎降级链测试")
    print("=" * 60)
    
    print("\n--- 测试 1: 启发式评分完整性 ---")
    test_heuristic_full_scores()
    test_heuristic_empty_response()
    test_heuristic_short_response()
    test_heuristic_rich_response()
    
    print("\n--- 测试 2: 降级链验证 ---")
    asyncio.run(test_evaluate_no_api_key_fallback())
    asyncio.run(test_evaluate_json_parse_error_fallback())
    asyncio.run(test_evaluate_llm_error_fallback())
    
    print("\n" + "=" * 60)
    print("所有 AI 评估降级链测试通过!")
    print("=" * 60)
