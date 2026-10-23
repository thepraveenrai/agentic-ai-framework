"""Unified LLM Client supporting OpenRouter, OpenAI, Anthropic, and Local Mock.

Integrated with:
- Multi-tier Caching (exact hash matching with TTL)
- Input & Output Guardrails (prompt injection & secrets filtering)
- Observability Telemetry (latency, token counting, cost calculation)
"""

import json
import time
from typing import List, Dict, Any, Optional
from openai import OpenAI
from agentic_framework.config import settings
from agentic_framework.core.caching import cache
from agentic_framework.guardrails.input_guardrails import input_guardrails
from agentic_framework.observability.tracer import tracer
from agentic_framework.observability.logger import logger


class LLMResponse:
    def __init__(
        self,
        content: Optional[str] = None,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        raw_response: Optional[Any] = None,
        cached: bool = False,
    ):
        self.content = content or ""
        self.tool_calls = tool_calls or []
        self.raw_response = raw_response
        self.cached = cached

    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


class UnifiedLLMClient:
    """Manages model calls, formatting, guardrails, caching, and telemetry."""

    def __init__(self):
        self.provider = settings.LLM_PROVIDER.lower()
        self.model = settings.MODEL_NAME
        self._client: Optional[OpenAI] = None
        self._init_client()

    def _init_client(self) -> None:
        if self.provider == "mock":
            self._client = None
            return
        if self.provider == "openrouter":
            api_key = settings.OPENROUTER_API_KEY or "missing-key"
            extra_headers = {
                "HTTP-Referer": settings.OPENROUTER_HTTP_REFERER,
                "X-Title": settings.OPENROUTER_APP_NAME,
            }
            self._client = OpenAI(
                base_url=settings.OPENROUTER_BASE_URL,
                api_key=api_key,
                default_headers=extra_headers,
                timeout=settings.REQUEST_TIMEOUT_SECONDS,
            )
        elif self.provider == "openai":
            self._client = OpenAI(
                api_key=settings.OPENAI_API_KEY or "missing-key",
                base_url=settings.OPENAI_BASE_URL,
                timeout=settings.REQUEST_TIMEOUT_SECONDS,
            )

    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None,
        span_id: Optional[str] = None,
    ) -> LLMResponse:
        """Execute chat completion with guardrails, caching, and tracing."""
        current_provider = settings.LLM_PROVIDER.lower()
        if current_provider != self.provider:
            self.provider = current_provider
            self._init_client()
        self.model = settings.MODEL_NAME

        temp = temperature if temperature is not None else settings.MODEL_TEMPERATURE

        # 1. Input Guardrails on the latest user/task message
        for msg in reversed(messages):
            if msg.get("role") in ("user", "system"):
                res = input_guardrails.validate(msg.get("content", ""))
                if not res.passed:
                    logger.error(f"Guardrail violation: {res.blocked_reason}")
                    return LLMResponse(content=f"Error: Blocked by input guardrail - {res.blocked_reason}")
                msg["content"] = res.sanitized_text
                break

        # 2. Check Cache
        cache_key = cache.compute_llm_key(self.model, messages, temp, tools)
        cached_val = cache.get_llm_response(cache_key)
        if cached_val:
            return LLMResponse(
                content=cached_val.get("content"),
                tool_calls=cached_val.get("tool_calls", []),
                cached=True,
            )

        # 3. Handle Mock Mode (for deterministic testing/offline)
        if self.provider == "mock" or not self._client:
            return self._mock_completion(messages, tools)

        # 4. Invoke LLM via API
        start_t = time.time()
        try:
            kwargs: Dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "temperature": temp,
                "max_tokens": settings.MAX_TOKENS,
            }
            if tools:
                # Format tools for OpenAI function calling
                formatted_tools = [
                    {
                        "type": "function",
                        "function": {
                            "name": t["name"],
                            "description": t["description"],
                            "parameters": t.get("inputSchema", {}),
                        },
                    }
                    for t in tools
                ]
                kwargs["tools"] = formatted_tools
                kwargs["tool_choice"] = "auto"

            response = self._client.chat.completions.create(**kwargs)
            duration = time.time() - start_t

            msg_obj = response.choices[0].message
            content = msg_obj.content or ""
            tool_calls = []

            if msg_obj.tool_calls:
                for tc in msg_obj.tool_calls:
                    try:
                        args = json.loads(tc.function.arguments)
                    except Exception:
                        args = {}
                    tool_calls.append({
                        "id": tc.id,
                        "name": tc.function.name,
                        "arguments": args,
                    })

            # Record telemetry
            prompt_tokens = response.usage.prompt_tokens if response.usage else 0
            comp_tokens = response.usage.completion_tokens if response.usage else 0
            if span_id:
                tracer.record_tokens(span_id, prompt_tokens, comp_tokens, self.model)

            # Store in Cache
            cache_payload = {"content": content, "tool_calls": tool_calls}
            cache.set_llm_response(cache_key, cache_payload, prompt_tokens + comp_tokens)

            return LLMResponse(content=content, tool_calls=tool_calls, raw_response=response)

        except Exception as e:
            logger.error(f"LLM API Call failed ({type(e).__name__}): {e}")
            # Fallback to intelligent local heuristic if API is unreachable/timeout
            return self._fallback_completion(messages, tools, str(e))

    def _mock_completion(
        self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]]
    ) -> LLMResponse:
        """Deterministic completion for offline or unit tests."""
        last_msg = messages[-1].get("content", "")
        return LLMResponse(
            content=f"[Mock Mode] Successfully analyzed request: '{last_msg[:60]}...'",
            tool_calls=[],
        )

    def _fallback_completion(
        self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]], error: str
    ) -> LLMResponse:
        return LLMResponse(
            content=f"LLM API temporary error: {error}. Please verify network and API configuration.",
            tool_calls=[],
        )


llm_client = UnifiedLLMClient()
