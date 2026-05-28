"""
测试 LLM 三模型 Failover 机制

测试项：
1. DeepSeek 超时/5xx 时自动切换到 MiMo
2. MiMo 失败时自动切换到 Qwen
3. 认证错误（401）不触发切换
4. 三模型都不可用时抛出异常
5. get_available_providers 正确返回已配置的模型列表（按优先级顺序）
"""

import sys
import asyncio
import httpx
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.services.llm_client import (
    _should_failover,
    get_available_providers,
    chat_completion,
)
from openai import APITimeoutError, RateLimitError, AuthenticationError, APIError

_MOCK_REQ = httpx.Request("GET", "http://test")
_MOCK_RESP = lambda code: httpx.Response(code, request=_MOCK_REQ)


def test_should_failover_timeout():
    err = APITimeoutError(request=_MOCK_REQ)
    assert _should_failover(err) is True
    print("PASS: APITimeoutError 触发 failover")


def test_should_failover_rate_limit():
    err = RateLimitError("rate limit", response=_MOCK_RESP(429), body={})
    assert _should_failover(err) is True
    print("PASS: RateLimitError 触发 failover")


def test_should_failover_5xx():
    err = APIError("Internal server error", request=_MOCK_REQ, body={})
    err.status_code = 500
    assert _should_failover(err) is True
    print("PASS: APIError 5xx 触发 failover")


def test_should_failover_4xx():
    err = APIError("Bad request", request=_MOCK_REQ, body={})
    err.status_code = 400
    assert _should_failover(err) is False
    print("PASS: APIError 4xx 不触发 failover")


def test_should_failover_auth():
    err = AuthenticationError("Invalid API key", response=_MOCK_RESP(401), body={})
    assert _should_failover(err) is False
    print("PASS: AuthenticationError 不触发 failover")


def test_should_failover_connection():
    err = ConnectionError("Connection refused")
    assert _should_failover(err) is True
    print("PASS: ConnectionError 触发 failover")


@patch("app.services.llm_client.settings")
def test_providers_all_configured(mock_settings):
    mock_settings.DEEPSEEK_API_KEY = "sk-deepseek"
    mock_settings.MIMO_API_KEY = "sk-mimo"
    mock_settings.QWEN_API_KEY = "sk-qwen"
    providers = get_available_providers()
    assert providers == ["deepseek", "mimo", "qwen"], f"三模型顺序错误: {providers}"
    print(f"PASS: 三模型配置返回正确顺序 {providers}")


@patch("app.services.llm_client.settings")
def test_providers_only_deepseek_mimo(mock_settings):
    mock_settings.DEEPSEEK_API_KEY = "sk-deepseek"
    mock_settings.MIMO_API_KEY = "sk-mimo"
    mock_settings.QWEN_API_KEY = ""
    providers = get_available_providers()
    assert providers == ["deepseek", "mimo"], f"顺序错误: {providers}"
    print(f"PASS: DeepSeek+MiMo 配置返回 {providers}")


@patch("app.services.llm_client.settings")
def test_providers_only_deepseek(mock_settings):
    mock_settings.DEEPSEEK_API_KEY = "sk-deepseek"
    mock_settings.MIMO_API_KEY = ""
    mock_settings.QWEN_API_KEY = ""
    providers = get_available_providers()
    assert providers == ["deepseek"]
    print(f"PASS: 仅 DeepSeek 配置返回 {providers}")


@patch("app.services.llm_client.settings")
def test_providers_none_configured(mock_settings):
    mock_settings.DEEPSEEK_API_KEY = ""
    mock_settings.MIMO_API_KEY = ""
    mock_settings.QWEN_API_KEY = ""
    providers = get_available_providers()
    assert providers == []
    print(f"PASS: 无配置返回空列表 {providers}")


async def test_failover_deepseek_to_mimo():
    """DeepSeek 超时 → MiMo 成功响应"""
    with patch("app.services.llm_client.get_available_providers", return_value=["deepseek", "mimo", "qwen"]), \
         patch("app.services.llm_client._get_deepseek_client") as mock_ds, \
         patch("app.services.llm_client._get_mimo_client") as mock_mimo:

        mock_ds_client = MagicMock()
        mock_ds.return_value = mock_ds_client
        mock_ds_client.chat.completions.create = AsyncMock(side_effect=APITimeoutError(request=_MOCK_REQ))

        mock_mimo_client = MagicMock()
        mock_mimo.return_value = mock_mimo_client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="MiMo response"))]
        mock_mimo_client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await chat_completion(messages=[{"role": "user", "content": "hello"}])
        assert result == "MiMo response"
        print("PASS: DeepSeek 超时 → MiMo 自动切换成功")


async def test_failover_deepseek_to_mimo_to_qwen():
    """DeepSeek 超时 → MiMo 超时 → Qwen 成功响应"""
    with patch("app.services.llm_client.get_available_providers", return_value=["deepseek", "mimo", "qwen"]), \
         patch("app.services.llm_client._get_deepseek_client") as mock_ds, \
         patch("app.services.llm_client._get_mimo_client") as mock_mimo, \
         patch("app.services.llm_client._get_qwen_client") as mock_qw:

        mock_ds_client = MagicMock()
        mock_ds.return_value = mock_ds_client
        mock_ds_client.chat.completions.create = AsyncMock(side_effect=APITimeoutError(request=_MOCK_REQ))

        mock_mimo_client = MagicMock()
        mock_mimo.return_value = mock_mimo_client
        mock_mimo_client.chat.completions.create = AsyncMock(side_effect=APITimeoutError(request=_MOCK_REQ))

        mock_qw_client = MagicMock()
        mock_qw.return_value = mock_qw_client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Qwen response"))]
        mock_qw_client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await chat_completion(messages=[{"role": "user", "content": "hello"}])
        assert result == "Qwen response"
        print("PASS: DeepSeek → MiMo → Qwen 三级切换成功")


async def test_chat_completion_auth_no_failover():
    """认证错误不应触发 failover"""
    with patch("app.services.llm_client.get_available_providers", return_value=["deepseek", "mimo", "qwen"]), \
         patch("app.services.llm_client._get_deepseek_client") as mock_ds:

        mock_ds_client = MagicMock()
        mock_ds.return_value = mock_ds_client
        mock_ds_client.chat.completions.create = AsyncMock(
            side_effect=AuthenticationError("Invalid key", response=_MOCK_RESP(401), body={}))

        try:
            await chat_completion(messages=[{"role": "user", "content": "hello"}])
            assert False
        except ValueError as e:
            assert "API Key 无效" in str(e)
            print("PASS: 认证错误不触发 failover，直接抛出异常")


async def test_chat_completion_all_unavailable():
    """三模型都不可用时抛出异常"""
    with patch("app.services.llm_client.get_available_providers", return_value=["deepseek", "mimo", "qwen"]), \
         patch("app.services.llm_client._get_deepseek_client") as mock_ds, \
         patch("app.services.llm_client._get_mimo_client") as mock_mimo, \
         patch("app.services.llm_client._get_qwen_client") as mock_qw:

        mock_ds_client = MagicMock()
        mock_ds.return_value = mock_ds_client
        mock_ds_client.chat.completions.create = AsyncMock(side_effect=APITimeoutError(request=_MOCK_REQ))

        mock_mimo_client = MagicMock()
        mock_mimo.return_value = mock_mimo_client
        mock_mimo_client.chat.completions.create = AsyncMock(side_effect=APITimeoutError(request=_MOCK_REQ))

        mock_qw_client = MagicMock()
        mock_qw.return_value = mock_qw_client
        mock_qw_client.chat.completions.create = AsyncMock(side_effect=APITimeoutError(request=_MOCK_REQ))

        try:
            await chat_completion(messages=[{"role": "user", "content": "hello"}])
            assert False
        except APITimeoutError:
            print("PASS: 三模型都不可用时抛出异常")


if __name__ == "__main__":
    print("=" * 60)
    print("LLM 三模型 Failover 测试")
    print("=" * 60)

    print("\n--- 测试 1: _should_failover 判断逻辑 ---")
    test_should_failover_timeout()
    test_should_failover_rate_limit()
    test_should_failover_5xx()
    test_should_failover_4xx()
    test_should_failover_auth()
    test_should_failover_connection()

    print("\n--- 测试 2: get_available_providers ---")
    test_providers_all_configured()
    test_providers_only_deepseek_mimo()
    test_providers_only_deepseek()
    test_providers_none_configured()

    print("\n--- 测试 3: chat_completion failover 行为 ---")
    asyncio.run(test_failover_deepseek_to_mimo())
    asyncio.run(test_failover_deepseek_to_mimo_to_qwen())
    asyncio.run(test_chat_completion_auth_no_failover())
    asyncio.run(test_chat_completion_all_unavailable())

    print("\n" + "=" * 60)
    print("所有 LLM Failover 测试通过!")
    print("=" * 60)
