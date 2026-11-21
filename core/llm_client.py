"""Zero-cost multi-provider LLM router (Gemini Free Tier / Groq / OpenRouter).

Uses environment variables ONLY. If no LLM API key is configured, returns None so
the calling module executes its built-in deterministic editorial intelligence engine
(guaranteeing 100% Autonomous autonomous operation even with zero keys).
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, Optional

import requests

from core.config import get_logger

logger = get_logger("llm_client")


def _extract_json_block(text: str) -> Optional[Dict[str, Any]]:
    """Extract a JSON object from an LLM response (handles markdown code fences)."""
    if not text:
        return None
    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
    if fence:
        cleaned = fence.group(1)
    else:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            cleaned = cleaned[start : end + 1]
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return None


class ZeroCostLLMClient:
    """Routes structured JSON completions across free-tier LLM providers if configured."""

    def __init__(self) -> None:
        self.gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.groq_key = os.getenv("GROQ_API_KEY", "").strip()
        self.openrouter_key = os.getenv("OPENROUTER_API_KEY", "").strip()

    @property
    def is_available(self) -> bool:
        return bool(self.gemini_key or self.groq_key or self.openrouter_key)

    def active_provider(self) -> str:
        if self.gemini_key:
            return "gemini-free"
        if self.groq_key:
            return "groq-free"
        if self.openrouter_key:
            return "openrouter-free"
        return "native-editorial-engine"

    def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.65,
        timeout: int = 35,
    ) -> Optional[Dict[str, Any]]:
        """Try configured free-tier providers in priority order; return parsed JSON or None."""
        if self.gemini_key:
            result = self._call_gemini(system_prompt, user_prompt, temperature, timeout)
            if result is not None:
                return result

        if self.groq_key:
            result = self._call_openai_compat(
                base_url="https://api.groq.com/openai/v1/chat/completions",
                api_key=self.groq_key,
                model="llama-3.3-70b-versatile",
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                timeout=timeout,
            )
            if result is not None:
                return result

        if self.openrouter_key:
            result = self._call_openai_compat(
                base_url="https://openrouter.ai/api/v1/chat/completions",
                api_key=self.openrouter_key,
                model="meta-llama/llama-3.3-70b-instruct:free",
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                timeout=timeout,
            )
            if result is not None:
                return result

        return None

    def _call_gemini(
        self, system_prompt: str, user_prompt: str, temperature: float, timeout: int
    ) -> Optional[Dict[str, Any]]:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-2.0-flash:generateContent?key={self.gemini_key}"
        )
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "responseMimeType": "application/json",
            },
        }
        try:
            resp = requests.post(url, json=payload, timeout=timeout)
            if resp.status_code == 200:
                data = resp.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                return _extract_json_block(text)
            if resp.status_code in (400, 401, 403):
                logger.warning("Gemini key rejected (HTTP %s); disabling for this run and using native engine.", resp.status_code)
                self.gemini_key = ""
            else:
                logger.warning("Gemini request returned HTTP %s; falling back.", resp.status_code)
        except Exception as exc:
            logger.warning("Gemini completion error (%s); falling back.", type(exc).__name__)
        return None

    def _call_openai_compat(
        self,
        base_url: str,
        api_key: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        timeout: int,
    ) -> Optional[Dict[str, Any]]:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        try:
            resp = requests.post(base_url, headers=headers, json=payload, timeout=timeout)
            if resp.status_code == 200:
                data = resp.json()
                text = data["choices"][0]["message"]["content"]
                return _extract_json_block(text)
            if resp.status_code in (401, 403):
                logger.warning("LLM key rejected (HTTP %s); disabling endpoint for this run.", resp.status_code)
                if api_key == self.groq_key:
                    self.groq_key = ""
                if api_key == self.openrouter_key:
                    self.openrouter_key = ""
            else:
                logger.warning("LLM endpoint returned HTTP %s; falling back.", resp.status_code)
        except Exception as exc:
            logger.warning("LLM completion error (%s); falling back.", type(exc).__name__)
        return None
