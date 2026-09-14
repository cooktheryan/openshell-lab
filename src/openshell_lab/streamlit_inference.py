"""Bounded, credential-free managed inference for the Lab 5 application."""

from __future__ import annotations

import json

import httpx


MODEL_URL = "https://inference.local/v1/chat/completions"
MAX_PROMPT_CHARS = 4000
MAX_HISTORY_MESSAGES = 20
MAX_RESPONSE_BYTES = 1024 * 1024
REQUEST_TIMEOUT = 180.0

_ALLOWED_ROLES = frozenset({"system", "user", "assistant"})
_PUBLIC_ERROR = "Managed inference is temporarily unavailable. Please try again."


def build_chat_request(messages: list[dict[str, str]]) -> dict:
    """Validate chat history and build the OpenShell-managed request body."""
    if not isinstance(messages, list) or not messages:
        raise ValueError("at least one chat message is required")
    if len(messages) > MAX_HISTORY_MESSAGES:
        raise ValueError(
            f"chat history exceeds {MAX_HISTORY_MESSAGES} messages"
        )

    validated_messages: list[dict[str, str]] = []
    for message in messages:
        if not isinstance(message, dict) or set(message) != {"role", "content"}:
            raise ValueError("each chat message must contain only role and content")
        role = message["role"]
        content = message["content"]
        if role not in _ALLOWED_ROLES:
            raise ValueError("chat message role is not allowed")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("chat message content must be a non-empty string")
        if len(content) > MAX_PROMPT_CHARS:
            raise ValueError(
                f"chat message content exceeds {MAX_PROMPT_CHARS} characters"
            )
        validated_messages.append({"role": role, "content": content})

    return {
        "messages": validated_messages,
        "temperature": 1.0,
        "max_completion_tokens": 1000,
    }


async def call_managed_inference(
    messages: list[dict[str, str]],
    transport: httpx.AsyncBaseTransport | None = None,
) -> str:
    """Call OpenShell's managed inference route and return assistant text."""
    request_body = build_chat_request(messages)
    async with httpx.AsyncClient(
        transport=transport,
        trust_env=True,
        timeout=REQUEST_TIMEOUT,
    ) as client:
        async with client.stream("POST", MODEL_URL, json=request_body) as response:
            response.raise_for_status()
            body = bytearray()
            async for chunk in response.aiter_bytes():
                if len(body) + len(chunk) > MAX_RESPONSE_BYTES:
                    raise ValueError("managed inference response exceeds 1 MiB")
                body.extend(chunk)

    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ValueError("managed inference response is not valid JSON") from error

    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError("managed inference response has no assistant content") from error
    if not isinstance(content, str) or not content.strip():
        raise ValueError("managed inference response has no assistant content")
    return content


def public_error_message(error: Exception) -> str:
    """Return the sole user-visible error, without leaking upstream details."""
    del error
    return _PUBLIC_ERROR
