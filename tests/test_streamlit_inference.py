import json
import unittest

import httpx

try:
    from openshell_lab import streamlit_inference
except ImportError:
    streamlit_inference = None


class StreamlitInferenceTests(unittest.IsolatedAsyncioTestCase):
    def require_client(self):
        self.assertIsNotNone(
            streamlit_inference,
            "openshell_lab.streamlit_inference must implement the Lab 5 contract",
        )
        return streamlit_inference

    def test_request_uses_managed_route_without_model_or_credentials(self):
        client = self.require_client()
        request = client.build_chat_request(
            [{"role": "user", "content": "hello"}]
        )

        self.assertEqual(
            "https://inference.local/v1/chat/completions", client.MODEL_URL
        )
        self.assertEqual(
            {"messages", "temperature", "max_completion_tokens"}, set(request)
        )
        self.assertEqual(1.0, request["temperature"])
        self.assertEqual(1000, request["max_completion_tokens"])
        self.assertFalse(
            {"model", "api_key", "authorization", "headers"}.intersection(
                request
            )
        )

    def test_empty_and_oversized_prompts_are_rejected(self):
        client = self.require_client()
        for prompt in ("", "x" * 4001):
            with self.subTest(length=len(prompt)):
                with self.assertRaises(ValueError):
                    client.build_chat_request(
                        [{"role": "user", "content": prompt}]
                    )

    def test_history_is_limited_to_twenty_messages(self):
        client = self.require_client()
        messages = [
            {"role": "user", "content": str(index)} for index in range(21)
        ]
        with self.assertRaises(ValueError):
            client.build_chat_request(messages)

    def test_messages_require_known_roles_and_nonempty_string_content(self):
        client = self.require_client()
        invalid_messages = (
            [{"role": "tool", "content": "hello"}],
            [{"role": "user", "content": None}],
            [{"role": "user", "content": "   "}],
            [{"role": "user", "content": "hello", "name": "operator"}],
        )
        for messages in invalid_messages:
            with self.subTest(messages=messages):
                with self.assertRaises(ValueError):
                    client.build_chat_request(messages)

    async def test_successful_response_returns_assistant_content(self):
        client = self.require_client()
        captured = []

        async def handler(request):
            captured.append(request)
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {"message": {"role": "assistant", "content": "hello back"}}
                    ]
                },
            )

        result = await client.call_managed_inference(
            [{"role": "user", "content": "hello"}],
            transport=httpx.MockTransport(handler),
        )

        self.assertEqual("hello back", result)
        self.assertEqual(1, len(captured))
        self.assertEqual(
            "https://inference.local/v1/chat/completions",
            str(captured[0].url),
        )
        self.assertNotIn("authorization", captured[0].headers)
        self.assertEqual(
            {
                "messages": [{"role": "user", "content": "hello"}],
                "temperature": 1.0,
                "max_completion_tokens": 1000,
            },
            json.loads(captured[0].content),
        )

    async def test_http_errors_are_not_presented_as_model_content(self):
        client = self.require_client()

        async def handler(_request):
            return httpx.Response(403, json={"error": "provider detail"})

        with self.assertRaises(httpx.HTTPStatusError):
            await client.call_managed_inference(
                [{"role": "user", "content": "hello"}],
                transport=httpx.MockTransport(handler),
            )

    async def test_malformed_json_is_rejected(self):
        client = self.require_client()

        async def handler(_request):
            return httpx.Response(200, content=b"not-json")

        with self.assertRaisesRegex(ValueError, "valid JSON"):
            await client.call_managed_inference(
                [{"role": "user", "content": "hello"}],
                transport=httpx.MockTransport(handler),
            )

    async def test_missing_or_non_string_content_is_rejected(self):
        client = self.require_client()
        payloads = (
            {"choices": [{"message": {"role": "assistant"}}]},
            {"choices": [{"message": {"content": ["not", "text"]}}]},
            {"choices": [{"message": {"content": "   "}}]},
        )
        for payload in payloads:
            with self.subTest(payload=payload):
                async def handler(_request, response_payload=payload):
                    return httpx.Response(200, json=response_payload)

                with self.assertRaisesRegex(ValueError, "assistant content"):
                    await client.call_managed_inference(
                        [{"role": "user", "content": "hello"}],
                        transport=httpx.MockTransport(handler),
                    )

    async def test_response_larger_than_one_mib_is_rejected(self):
        client = self.require_client()

        async def handler(_request):
            return httpx.Response(200, content=b"x" * (client.MAX_RESPONSE_BYTES + 1))

        with self.assertRaisesRegex(ValueError, "exceeds 1 MiB"):
            await client.call_managed_inference(
                [{"role": "user", "content": "hello"}],
                transport=httpx.MockTransport(handler),
            )

    def test_public_error_message_is_constant_and_sanitized(self):
        client = self.require_client()
        error = RuntimeError("upstream token sk-example-secret was rejected")

        message = client.public_error_message(error)

        self.assertEqual(
            "Managed inference is temporarily unavailable. Please try again.",
            message,
        )
        self.assertNotIn("sk-example-secret", message)


if __name__ == "__main__":
    unittest.main()
