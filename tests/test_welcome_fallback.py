"""
测试面试开场白降级

测试项：
1. LLM 生成失败时降级为模板
2. 技术面模板包含关键词和自我介绍邀请
3. 压力面试模板包含挑战性语气
4. 轻松面试模板包含亲切语气
"""

import sys
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.services.prompt_builder import build_welcome_message, build_simple_welcome


async def test_welcome_llm_success():
    with patch("app.services.prompt_builder.settings") as mock_settings:
        mock_settings.DEEPSEEK_API_KEY = "sk-test"
        
        with patch("app.services.prompt_builder._llm_chat", return_value="你好，我是面试官，很高兴和你交流。"):
            welcome = await build_welcome_message(
                keywords=["React", "TypeScript"],
                interview_type="technical",
            )
            assert len(welcome) > 10, "LLM 生成的开场白应有合理长度"
            print(f"PASS: LLM 生成开场白成功 - 长度: {len(welcome)} 字符")


async def test_welcome_llm_fail_fallback_to_template():
    with patch("app.services.prompt_builder.settings") as mock_settings:
        mock_settings.DEEPSEEK_API_KEY = "sk-test"
        
        with patch("app.services.prompt_builder._llm_chat", side_effect=RuntimeError("LLM 不可用")):
            welcome = await build_welcome_message(
                keywords=["React", "TypeScript", "FastAPI"],
                interview_type="technical",
            )
            assert "React" in welcome, "模板应包含技术关键词"
            assert "TypeScript" in welcome, "模板应包含技术关键词"
            assert "自我介绍" in welcome or "介绍" in welcome, "模板应邀请自我介绍"
            print(f"PASS: LLM 失败降级到模板: {welcome[:80]}...")


async def test_welcome_pressure_type():
    welcome = await build_welcome_message(
        keywords=["Docker", "Kubernetes"],
        interview_type="pressure",
    )
    assert "Docker" in welcome or "Kubernetes" in welcome, "应包含技术关键词"
    assert "挑战性" in welcome or "压力" in welcome or "挑战" in welcome, "压力面试模板应有挑战性语气"
    print(f"PASS: 压力面试模板: {welcome[:80]}...")


async def test_welcome_friendly_type():
    welcome = await build_welcome_message(
        keywords=["Python", "Django"],
        interview_type="friendly",
    )
    assert "Python" in welcome or "Django" in welcome, "应包含技术关键词"
    assert "轻松" in welcome or "聊" in welcome, "轻松面试模板应有亲切语气"
    print(f"PASS: 轻松面试模板: {welcome[:80]}...")


def test_simple_welcome():
    welcome = build_simple_welcome(
        keywords=["React", "TypeScript", "Node.js"],
        interview_type="technical",
    )
    assert "React" in welcome, "简易开场白应包含技术关键词"
    assert "自我介绍" in welcome or "介绍" in welcome, "应邀请自我介绍"
    print(f"PASS: 简易开场白: {welcome[:80]}...")


if __name__ == "__main__":
    print("=" * 60)
    print("面试开场白降级测试")
    print("=" * 60)
    
    print("\n--- 测试 1: LLM 成功生成 ---")
    asyncio.run(test_welcome_llm_success())
    
    print("\n--- 测试 2: LLM 失败降级模板 ---")
    asyncio.run(test_welcome_llm_fail_fallback_to_template())
    
    print("\n--- 测试 3: 压力面试模板 ---")
    asyncio.run(test_welcome_pressure_type())
    
    print("\n--- 测试 4: 轻松面试模板 ---")
    asyncio.run(test_welcome_friendly_type())
    
    print("\n--- 测试 5: 简易开场白 ---")
    test_simple_welcome()
    
    print("\n" + "=" * 60)
    print("所有开场白降级测试通过!")
    print("=" * 60)
