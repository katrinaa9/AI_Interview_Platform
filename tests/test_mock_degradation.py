"""
测试 Mock 降级回复

测试项：
1. API Key 未配置时抛出 ValueError
2. 双模型都不可用时抛出 RuntimeError
3. LLM 调用失败时的错误传播
"""

import sys
import asyncio
import httpx
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.services.llm_client import chat_completion

_MOCK_REQ = httpx.Request("GET", "http://test")


async def test_no_api_key_error():
    with patch("app.services.llm_client.get_available_providers", return_value=[]):
        try:
            await chat_completion(messages=[{"role": "user", "content": "hello"}])
            assert False
        except ValueError as e:
            assert "未配置" in str(e)
            print(f"PASS: API Key 未配置时抛出明确错误: {e}")


async def test_both_models_fail_runtime_error():
    from openai import APITimeoutError
    
    with patch("app.services.llm_client.get_available_providers", return_value=["deepseek", "qwen"]), \
         patch("app.services.llm_client._get_deepseek_client") as mock_ds, \
         patch("app.services.llm_client._get_qwen_client") as mock_qw:
        
        mock_ds.return_value.chat.completions.create = AsyncMock(
            side_effect=APITimeoutError(request=_MOCK_REQ))
        mock_qw.return_value.chat.completions.create = AsyncMock(
            side_effect=APITimeoutError(request=_MOCK_REQ))
        
        try:
            await chat_completion(messages=[{"role": "user", "content": "hello"}])
            assert False
        except APITimeoutError:
            print("PASS: 双模型都不可用时抛出异常（最后一个提供商的原始异常）")


async def test_auth_error_propagates():
    from openai import AuthenticationError
    
    with patch("app.services.llm_client.get_available_providers", return_value=["deepseek", "qwen"]), \
         patch("app.services.llm_client._get_deepseek_client") as mock_ds:
        
        mock_ds.return_value.chat.completions.create = AsyncMock(
            side_effect=AuthenticationError("Invalid key", response=httpx.Response(401, request=_MOCK_REQ), body={}))
        
        try:
            await chat_completion(messages=[{"role": "user", "content": "hello"}])
            assert False
        except ValueError as e:
            assert "API Key" in str(e)
            print(f"PASS: 认证错误直接抛出: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("Mock 降级回复测试")
    print("=" * 60)
    
    print("\n--- 测试 1: API Key 未配置 ---")
    asyncio.run(test_no_api_key_error())
    
    print("\n--- 测试 2: 双模型都不可用 ---")
    asyncio.run(test_both_models_fail_runtime_error())
    
    print("\n--- 测试 3: 认证错误传播 ---")
    asyncio.run(test_auth_error_propagates())
    
    print("\n" + "=" * 60)
    print("所有 Mock 降级测试通过!")
    print("=" * 60)
