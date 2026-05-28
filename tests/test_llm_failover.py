"""
测试 LLM 双模型 Failover 机制

测试项：
1. DeepSeek 超时/5xx 时自动切换到通义千问
2. 认证错误（401）不触发切换
3. 双模型都不可用时抛出 RuntimeError
4. get_available_providers 正确返回已配置的模型列表
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
def test_providers_both_configured(mock_settings):
    mock_settings.DEEPSEEK_API_KEY = "sk-deepseek"
    mock_settings.QWEN_API_KEY = "sk-qwen"
    providers = get_available_providers()
    assert "deepseek" in providers and "qwen" in providers
    print(f"PASS: 双模型配置返回 {providers}")


@patch("app.services.llm_client.settings")
def test_providers_only_deepseek(mock_settings):
    mock_settings.DEEPSEEK_API_KEY = "sk-deepseek"
    mock_settings.QWEN_API_KEY = ""
    providers = get_available_providers()
    assert providers == ["deepseek"]
    print(f"PASS: 仅 DeepSeek 配置返回 {providers}")


@patch("app.services.llm_client.settings")
def test_providers_none_configured(mock_settings):
    mock_settings.DEEPSEEK_API_KEY = ""
    mock_settings.QWEN_API_KEY = ""
    providers = get_available_providers()
    assert providers == []
    print(f"PASS: 无配置返回空列表 {providers}")


async def test_chat_completion_failover_to_qwen():
    with patch("app.services.llm_client.get_available_providers", return_value=["deepseek", "qwen"]), \
         patch("app.services.llm_client._get_deepseek_client") as mock_ds, \
         patch("app.services.llm_client._get_qwen_client") as mock_qw:

        mock_ds_client = MagicMock()
        mock_ds.return_value = mock_ds_client
        mock_ds_client.chat.completions.create = AsyncMock(side_effect=APITimeoutError(request=_MOCK_REQ))

        mock_qw_client = MagicMock()
        mock_qw.return_value = mock_qw_client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Qwen response"))]
        mock_qw_client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await chat_completion(messages=[{"role": "user", "content": "hello"}])
        assert result == "Qwen response"
        print("PASS: DeepSeek 超时后自动切换到 Qwen 并成功返回")


async def test_chat_completion_auth_no_failover():
    with patch("app.services.llm_client.get_available_providers", return_value=["deepseek", "qwen"]), \
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


async def test_chat_completion_both_unavailable():
    from openai import APITimeoutError
    with patch("app.services.llm_client.get_available_providers", return_value=["deepseek", "qwen"]), \
         patch("app.services.llm_client._get_deepseek_client") as mock_ds, \
         patch("app.services.llm_client._get_qwen_client") as mock_qw:

        mock_ds_client = MagicMock()
        mock_ds.return_value = mock_ds_client
        mock_ds_client.chat.completions.create = AsyncMock(side_effect=APITimeoutError(request=_MOCK_REQ))

        mock_qw_client = MagicMock()
        mock_qw.return_value = mock_qw_client
        mock_qw_client.chat.completions.create = AsyncMock(side_effect=APITimeoutError(request=_MOCK_REQ))

        try:
            await chat_completion(messages=[{"role": "user", "content": "hello"}])
            assert False
        except APITimeoutError:
            print("PASS: 双模型都不可用时抛出异常（最后一个提供商的原始异常）")


if __name__ == "__main__":
    print("=" * 60)
    print("LLM 双模型 Failover 测试")
    print("=" * 60)

    print("\n--- 测试 1: _should_failover 判断逻辑 ---")
    test_should_failover_timeout()
    test_should_failover_rate_limit()
    test_should_failover_5xx()
    test_should_failover_4xx()
    test_should_failover_auth()
    test_should_failover_connection()

    print("\n--- 测试 2: get_available_providers ---")
    test_providers_both_configured()
    test_providers_only_deepseek()
    test_providers_none_configured()

    print("\n--- 测试 3: chat_completion failover 行为 ---")
    asyncio.run(test_chat_completion_failover_to_qwen())
    asyncio.run(test_chat_completion_auth_no_failover())
    asyncio.run(test_chat_completion_both_unavailable())

    print("\n" + "=" * 60)
    print("所有 LLM Failover 测试通过!")
    print("=" * 60)
