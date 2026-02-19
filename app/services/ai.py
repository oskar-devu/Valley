"""
AI service: profile analysis and sequence generation with token tracking and error handling.
"""
import json
import logging
from typing import Any

from openai import AsyncOpenAI
from openai import APIError as OpenAIAPIError

from app.config import settings
from app.prompts import tov_to_instructions
from app.prompts.templates import PROFILE_ANALYSIS_PROMPT, SEQUENCE_GENERATION_PROMPT

logger = logging.getLogger(__name__)


# Approximate cost per 1K tokens (USD) for gpt-4o-mini as of 2024
INPUT_COST_PER_1K = 0.00015
OUTPUT_COST_PER_1K = 0.0006


def _estimate_cost(input_tokens: int, output_tokens: int) -> float:
    return (input_tokens / 1000.0) * INPUT_COST_PER_1K + (output_tokens / 1000.0) * OUTPUT_COST_PER_1K


def _parse_json_from_content(content: str) -> dict[str, Any]:
    """Extract JSON from model output; handle markdown code blocks."""
    text = content.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return json.loads(text)


async def _chat(
    client: AsyncOpenAI,
    system: str,
    user: str,
    model: str | None = None,
) -> tuple[dict[str, Any], int, int]:
    """Call OpenAI chat, return parsed JSON, input_tokens, output_tokens."""
    model = model or settings.openai_model
    resp = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.6,
    )
    choice = resp.choices[0]
    content = choice.message.content or "{}"
    usage = getattr(resp, "usage", None)
    input_tokens = usage.prompt_tokens if usage else 0
    output_tokens = usage.completion_tokens if usage else 0
    try:
        data = _parse_json_from_content(content)
    except json.JSONDecodeError as e:
        logger.warning("AI returned invalid JSON: %s", e)
        data = {"error": content, "summary": "Parse failed", "messages": [], "signals": []}
    return data, input_tokens, output_tokens


class AIService:
    def __init__(self) -> None:
        self._client: AsyncOpenAI | None = None

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            if not settings.openai_api_key:
                raise ValueError("OPENAI_API_KEY is not set")
            self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        return self._client

    async def analyze_prospect(
        self,
        prospect_url: str,
        company_context: str,
    ) -> tuple[dict[str, Any], int, int]:
        """Returns (profile_data dict, input_tokens, output_tokens)."""
        system = "You output only valid JSON. No markdown, no explanation."
        user = PROFILE_ANALYSIS_PROMPT.format(
            prospect_url=prospect_url,
            company_context=company_context,
        )
        try:
            data, inp, out = await _chat(self._get_client(), system, user)
            return data, inp, out
        except OpenAIAPIError as e:
            logger.exception("OpenAI API error during profile analysis: %s", e)
            # Fallback: minimal analysis so the pipeline can continue
            fallback = {
                "summary": "Profile analysis unavailable (API error). Proceeding with generic B2B prospect.",
                "role_or_industry": None,
                "signals": ["B2B decision maker"],
                "raw_data": {"error": str(e)},
            }
            return fallback, 0, 0

    async def generate_sequence(
        self,
        prospect_analysis: dict[str, Any],
        company_context: str,
        formality: float,
        warmth: float,
        directness: float,
        sequence_length: int,
    ) -> tuple[dict[str, Any], int, int]:
        """Returns (response with thinking_summary + messages, input_tokens, output_tokens)."""
        tov_instructions = tov_to_instructions(formality, warmth, directness)
        analysis_str = json.dumps(prospect_analysis, indent=2)
        system = "You output only valid JSON. No markdown, no explanation."
        user = SEQUENCE_GENERATION_PROMPT.format(
            prospect_analysis=analysis_str,
            company_context=company_context,
            tov_instructions=tov_instructions,
            sequence_length=sequence_length,
        )
        try:
            data, inp, out = await _chat(self._get_client(), system, user)
            return data, inp, out
        except OpenAIAPIError as e:
            logger.exception("OpenAI API error during sequence generation: %s", e)
            fallback = {
                "thinking_summary": "Generation failed due to API error.",
                "messages": [
                    {
                        "step": i + 1,
                        "thinking_process": "Fallback message.",
                        "content": f"Hi, I'd love to connect and share how we help with {company_context[:50]}...",
                        "confidence_score": 0.5,
                    }
                    for i in range(sequence_length)
                ],
            }
            return fallback, 0, 0

    @staticmethod
    def estimate_cost(input_tokens: int, output_tokens: int) -> float:
        return _estimate_cost(input_tokens, output_tokens)
