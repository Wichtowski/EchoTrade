from __future__ import annotations

import json

import httpx
import pytest
from core.services import ai
from fastapi import HTTPException
from libdb.models import AISettings
from libshared.config import settings
from openai import AsyncOpenAI


@pytest.mark.parametrize(
    "model,effort", [("gpt-6-luna", "low"), ("gpt-6.1-sol", "medium"), ("gpt-6-astra", "high")]
)
async def test_saved_model_controls_real_sdk_request(monkeypatch, model, effort):
    async def respond(request):
        body = json.loads(request.content)
        assert body["model"] == model
        assert body["reasoning"]["effort"] == effort
        assert body["store"] is False
        assert body["tools"][0]["type"] == "web_search"
        assert "api_key" not in body
        return httpx.Response(
            200,
            json={
                "id": "resp_test",
                "created_at": 1,
                "object": "response",
                "model": model,
                "status": "completed",
                "output": [
                    {
                        "id": "msg",
                        "type": "message",
                        "role": "assistant",
                        "status": "completed",
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps(
                                    {
                                        "commentary": "No holdings; no trade suggested.",
                                        "risks": [],
                                        "watchlist": [],
                                    }
                                ),
                                "annotations": [],
                            }
                        ],
                    }
                ],
            },
        )

    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    monkeypatch.setattr(
        ai,
        "AsyncOpenAI",
        lambda **kwargs: AsyncOpenAI(
            api_key="test-key",
            max_retries=0,
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)),
        ),
    )
    result = await ai.generate_research(
        {},
        AISettings(commentary_model=model, proposal_model=model, reasoning_effort=effort),
        "commentary",
    )
    assert result["model"] == model
    assert result["commentary"] == "No holdings; no trade suggested."


async def test_refusal_creates_no_result(monkeypatch):
    async def respond(request):
        return httpx.Response(
            200,
            json={
                "id": "resp_refused",
                "created_at": 1,
                "object": "response",
                "model": "gpt-6-luna",
                "status": "completed",
                "output": [
                    {
                        "id": "msg",
                        "type": "message",
                        "role": "assistant",
                        "status": "completed",
                        "content": [{"type": "refusal", "refusal": "Cannot provide this output"}],
                    }
                ],
            },
        )

    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    monkeypatch.setattr(
        ai,
        "AsyncOpenAI",
        lambda **kwargs: AsyncOpenAI(
            api_key="test-key",
            max_retries=0,
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)),
        ),
    )
    with pytest.raises(HTTPException, match="refused or incomplete"):
        await ai.generate_research(
            {}, AISettings(commentary_model="gpt-6-luna", reasoning_effort="low"), "commentary"
        )
