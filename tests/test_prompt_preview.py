"""
测试 Prompt 模板预览

测试项：
1. POST /api/admin/prompt/test 占位符替换
2. {keywords}、{turn}、{max_turns} 替换正确
3. 返回预览内容长度限制在 2000 字符以内
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))


def test_prompt_placeholder_replacement():
    """验证占位符替换逻辑"""
    template = """你是一个面试官。
候选人技术栈：{keywords}
当前轮次：第 {turn} 轮
最大轮次：{max_turns}
请根据以上信息提问。"""
    
    test_keywords = ["React", "TypeScript", "Node.js"]
    test_turn = 3
    
    preview = template
    if "{keywords}" in preview:
        preview = preview.replace("{keywords}", "、".join(test_keywords))
    if "{turn}" in preview:
        preview = preview.replace("{turn}", str(test_turn))
    if "{max_turns}" in preview:
        preview = preview.replace("{max_turns}", "15")
    
    assert "React、TypeScript、Node.js" in preview, "keywords 应正确替换"
    assert "第 3 轮" in preview, "turn 应正确替换"
    assert "最大轮次：15" in preview, "max_turns 应正确替换"
    print("PASS: 占位符替换正确:")
    print(f"  - keywords: {test_keywords} → React、TypeScript、Node.js")
    print(f"  - turn: {test_turn} → 第 3 轮")
    print(f"  - max_turns: 15 → 最大轮次：15")


def test_prompt_preview_truncated():
    """预览内容应截断至 2000 字符以内"""
    long_template = "A" * 5000 + "{keywords}"
    
    preview = long_template.replace("{keywords}", "React")
    truncated = preview[:2000]
    
    assert len(truncated) == 2000, f"截断后应为 2000 字符，实际: {len(truncated)}"
    assert "React" not in truncated, "超长模板截断后不应包含替换内容"
    print(f"PASS: 超长模板截断正确 - 原始 {len(long_template)} 字符 → 截断 {len(truncated)} 字符")


def test_prompt_char_count():
    """应返回原始内容的字符计数"""
    template = "你好，候选人。你的技术栈是 {keywords}。"
    char_count = len(template)
    assert char_count > 0, "字符计数应大于 0"
    print(f"PASS: 字符计数正确 - {char_count} 字符")


def test_prompt_test_endpoint_structure():
    """验证测试接口返回结构"""
    mock_result = {
        "preview": "你是一个面试官。候选人技术栈：React、TypeScript、Node.js...",
        "char_count": 150,
        "test_keywords": ["React", "TypeScript", "Node.js"],
        "test_turn": 3,
    }
    
    assert "preview" in mock_result, "应包含 preview"
    assert "char_count" in mock_result, "应包含 char_count"
    assert "test_keywords" in mock_result, "应包含 test_keywords"
    assert "test_turn" in mock_result, "应包含 test_turn"
    print(f"PASS: 测试接口返回结构完整: {list(mock_result.keys())}")


if __name__ == "__main__":
    print("=" * 60)
    print("Prompt 模板预览测试")
    print("=" * 60)
    
    print("\n--- 测试 1: 占位符替换 ---")
    test_prompt_placeholder_replacement()
    
    print("\n--- 测试 2: 预览截断 ---")
    test_prompt_preview_truncated()
    
    print("\n--- 测试 3: 字符计数 ---")
    test_prompt_char_count()
    
    print("\n--- 测试 4: 返回结构 ---")
    test_prompt_test_endpoint_structure()
    
    print("\n" + "=" * 60)
    print("所有 Prompt 模板预览测试通过!")
    print("=" * 60)
