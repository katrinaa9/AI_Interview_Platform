"""
三模型 LLM 客户端（DeepSeek 主 + MiMo 备 + Qwen 备）

Failover 优先级顺序：
1. DeepSeek（第一优先级，成本最优）
2. MiMo v2.5（第二优先级，小米模型）
3. Qwen（第三优先级，通义千问）

Failover 策略：
- 当前优先级模型请求失败（超时/5xx/连接错误），自动切换到下一优先级
- 认证错误（API Key 无效）不触发 Failover，直接抛出
- 所有模型都不可用时，抛出 RuntimeError

MiMo 通过 OpenAI 兼容接口调用，Qwen 通过 DashScope OpenAI 兼容接口调用，均无需额外 SDK。
"""

import logging
import time
from typing import AsyncGenerator, Optional
from openai import AsyncOpenAI, APIError, AuthenticationError, RateLimitError, APITimeoutError, APIConnectionError
from app.config import settings

logger = logging.getLogger(__name__)

# 模型配置
DEFAULT_MAX_TOKENS = 1024
DEFAULT_TEMPERATURE = 0.65
EVAL_MAX_TOKENS = 2048
WELCOME_MAX_TOKENS = 256

DEEPSEEK_MODEL = "deepseek-chat"

# 可触发 Failover 的异常类型（超时、服务端错误、连接问题）
FAILOVER_EXCEPTIONS = (APITimeoutError, RateLimitError, APIConnectionError, ConnectionError, TimeoutError)

# 三客户端单例
_deepseek_client: Optional[AsyncOpenAI] = None
_mimo_client: Optional[AsyncOpenAI] = None
_qwen_client: Optional[AsyncOpenAI] = None


def _get_deepseek_client() -> Optional[AsyncOpenAI]:
    global _deepseek_client
    if _deepseek_client is None:
        if not settings.DEEPSEEK_API_KEY:
            return None
        _deepseek_client = AsyncOpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
            timeout=45.0,
            max_retries=1,
        )
        logger.info(f"DeepSeek 客户端已初始化: {settings.DEEPSEEK_BASE_URL}")
    return _deepseek_client


def _get_mimo_client() -> Optional[AsyncOpenAI]:
    global _mimo_client
    if _mimo_client is None:
        if not settings.MIMO_API_KEY:
            return None
        _mimo_client = AsyncOpenAI(
            api_key=settings.MIMO_API_KEY,
            base_url=settings.MIMO_BASE_URL,
            timeout=45.0,
            max_retries=1,
        )
        logger.info(f"MiMo 客户端已初始化: {settings.MIMO_BASE_URL} | model={settings.MIMO_MODEL_NAME}")
    return _mimo_client


def _get_qwen_client() -> Optional[AsyncOpenAI]:
    global _qwen_client
    if _qwen_client is None:
        if not settings.QWEN_API_KEY:
            return None
        _qwen_client = AsyncOpenAI(
            api_key=settings.QWEN_API_KEY,
            base_url=settings.QWEN_BASE_URL,
            timeout=45.0,
            max_retries=1,
        )
        logger.info(f"通义千问客户端已初始化: {settings.QWEN_BASE_URL} | model={settings.QWEN_MODEL_NAME}")
    return _qwen_client


def get_available_providers() -> list[str]:
    """返回已配置的 provider 列表（按优先级顺序：DeepSeek → MiMo → Qwen）"""
    providers = []
    if settings.DEEPSEEK_API_KEY:
        providers.append("deepseek")
    if settings.MIMO_API_KEY:
        providers.append("mimo")
    if settings.QWEN_API_KEY:
        providers.append("qwen")
    return providers


async def close_http_client():
    global _deepseek_client, _mimo_client, _qwen_client
    if _deepseek_client is not None:
        await _deepseek_client.close()
        _deepseek_client = None
    if _mimo_client is not None:
        await _mimo_client.close()
        _mimo_client = None
    if _qwen_client is not None:
        await _qwen_client.close()
        _qwen_client = None
    logger.info("LLM 客户端连接池已关闭")


def _should_failover(exc: Exception) -> bool:
    if isinstance(exc, AuthenticationError):
        return False
    if isinstance(exc, FAILOVER_EXCEPTIONS):
        return True
    if isinstance(exc, APIError) and exc.status_code is not None and exc.status_code >= 500:
        return True
    return False


async def chat_completion(
    messages: list[dict[str, str]],
    model: str = DEEPSEEK_MODEL,
    temperature: float = DEFAULT_TEMPERATURE,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> str:
    providers = get_available_providers()
    if not providers:
        raise ValueError("未配置任何 LLM API Key，请在 .env 中设置 DEEPSEEK_API_KEY、MIMO_API_KEY 或 QWEN_API_KEY")

    last_error: Optional[Exception] = None

    for i, provider in enumerate(providers):
        try:
            return await _call_provider(provider, messages, model, temperature, max_tokens)
        except Exception as e:
            last_error = e
            # 非最后一个 provider 且可 failover 时，尝试下一个
            if i < len(providers) - 1 and _should_failover(e):
                logger.warning(f"[{provider}] 请求失败，切换到 {providers[i+1]} | 错误: {type(e).__name__}: {e}")
                continue
            raise

    if last_error:
        raise RuntimeError(f"所有 LLM 提供商均不可用: {last_error}") from last_error
    raise RuntimeError("LLM 服务不可用")


async def _call_provider(
    provider: str,
    messages: list[dict[str, str]],
    model: str,
    temperature: float,
    max_tokens: int,
) -> str:
    start = time.time()

    if provider == "deepseek":
        client = _get_deepseek_client()
        actual_model = model or DEEPSEEK_MODEL
    elif provider == "mimo":
        client = _get_mimo_client()
        actual_model = settings.MIMO_MODEL_NAME
    else:
        client = _get_qwen_client()
        actual_model = settings.QWEN_MODEL_NAME

    if client is None:
        raise ValueError(f"{provider} 客户端未初始化（API Key 未配置）")

    try:
        response = await client.chat.completions.create(
            model=actual_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False,
        )

        elapsed = time.time() - start
        content = response.choices[0].message.content or ""

        usage = response.usage
        if usage:
            logger.info(
                f"[{provider}] 非流式完成 | 模型={actual_model} | 耗时={elapsed:.1f}s | "
                f"tokens={usage.prompt_tokens}+{usage.completion_tokens}={usage.total_tokens}"
            )
        else:
            logger.info(f"[{provider}] 非流式完成 | 模型={actual_model} | 耗时={elapsed:.1f}s")

        return content.strip()

    except AuthenticationError as e:
        logger.error(f"[{provider}] 认证失败: {e}")
        raise ValueError(f"{provider} API Key 无效或已过期") from e

    except APITimeoutError as e:
        elapsed = time.time() - start
        logger.error(f"[{provider}] 请求超时 | 已等待={elapsed:.1f}s | {e}")
        raise

    except RateLimitError as e:
        logger.error(f"[{provider}] 频率限制: {e}")
        raise

    except APIError as e:
        elapsed = time.time() - start
        status_code = getattr(e, "status_code", "unknown")
        message = getattr(e, "message", str(e))
        logger.error(f"[{provider}] API错误 [{status_code}] | 耗时={elapsed:.1f}s | {message}")
        raise

    except Exception as e:
        elapsed = time.time() - start
        logger.exception(f"[{provider}] 调用异常 | 耗时={elapsed:.1f}s")
        raise RuntimeError(f"{provider} 服务异常: {str(e)}") from e


async def chat_completion_stream(
    messages: list[dict[str, str]],
    model: str = DEEPSEEK_MODEL,
    temperature: float = DEFAULT_TEMPERATURE,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> AsyncGenerator[str, None]:
    providers = get_available_providers()
    if not providers:
        raise ValueError("未配置任何 LLM API Key，请在 .env 中设置 DEEPSEEK_API_KEY、MIMO_API_KEY 或 QWEN_API_KEY")

    last_error: Optional[Exception] = None

    for i, provider in enumerate(providers):
        try:
            async for chunk in _stream_provider(provider, messages, model, temperature, max_tokens):
                yield chunk
            return
        except Exception as e:
            last_error = e
            # 非最后一个 provider 且可 failover 时，尝试下一个
            if i < len(providers) - 1 and _should_failover(e):
                logger.warning(f"[{provider}] 流式请求失败，切换到 {providers[i+1]} | 错误: {type(e).__name__}: {e}")
                continue
            raise

    if last_error:
        raise RuntimeError(f"所有 LLM 提供商均不可用: {last_error}") from last_error


async def _stream_provider(
    provider: str,
    messages: list[dict[str, str]],
    model: str,
    temperature: float,
    max_tokens: int,
) -> AsyncGenerator[str, None]:
    start = time.time()
    first_token_time: Optional[float] = None
    total_chunks = 0

    if provider == "deepseek":
        client = _get_deepseek_client()
        actual_model = model or DEEPSEEK_MODEL
    elif provider == "mimo":
        client = _get_mimo_client()
        actual_model = settings.MIMO_MODEL_NAME
    else:
        client = _get_qwen_client()
        actual_model = settings.QWEN_MODEL_NAME

    if client is None:
        raise ValueError(f"{provider} 客户端未初始化")

    try:
        stream = await client.chat.completions.create(
            model=actual_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices and len(chunk.choices) > 0:
                delta = chunk.choices[0].delta
                content = delta.content
                if content:
                    total_chunks += 1
                    if first_token_time is None:
                        first_token_time = time.time() - start
                        logger.info(
                            f"[{provider}] 流式首Token | 延迟={first_token_time:.2f}s | "
                            f"模型={actual_model}"
                        )
                    yield content

        elapsed = time.time() - start
        ttft_str = f"首Token={first_token_time:.2f}s | " if first_token_time else ""
        logger.info(
            f"[{provider}] 流式完成 | {ttft_str}"
            f"总耗时={elapsed:.1f}s | 产出={total_chunks} chunks"
        )

    except AuthenticationError as e:
        logger.error(f"[{provider}] 流式认证失败: {e}")
        raise ValueError(f"{provider} API Key 无效或已过期") from e

    except APITimeoutError as e:
        elapsed = time.time() - start
        logger.error(f"[{provider}] 流式超时 | 已等待={elapsed:.1f}s | {e}")
        raise

    except RateLimitError as e:
        logger.error(f"[{provider}] 流式频率限制: {e}")
        raise

    except APIError as e:
        elapsed = time.time() - start
        logger.error(f"[{provider}] 流式API错误 [{e.status_code}] | 耗时={elapsed:.1f}s | {e.message}")
        raise

    except Exception as e:
        elapsed = time.time() - start
        logger.exception(f"[{provider}] 流式调用异常 | 耗时={elapsed:.1f}s")
        raise RuntimeError(f"{provider} 服务异常: {str(e)}") from e
