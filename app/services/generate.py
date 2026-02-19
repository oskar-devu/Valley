"""
Orchestrates: prospect resolution -> profile analysis -> sequence generation -> persistence.
"""
import logging
from datetime import datetime
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Prospect, MessageSequence, SequenceMessage, AIGeneration
from app.schemas.generate import (
    GenerateSequenceRequest,
    GenerateSequenceResponse,
    MessageOutput,
    ProspectAnalysisOutput,
)
from app.services.ai import AIService

logger = logging.getLogger(__name__)


def _normalize_linkedin_url(url: str) -> str:
    u = url.strip()
    if not u.startswith("http"):
        u = "https://" + u
    return u.rstrip("/")


def _slug_from_url(url: str) -> str:
    path = urlparse(url).path or ""
    parts = [p for p in path.split("/") if p]
    return parts[-1] if parts else "unknown"


async def get_or_create_prospect(session: AsyncSession, prospect_url: str) -> Prospect:
    url = _normalize_linkedin_url(prospect_url)
    result = await session.execute(select(Prospect).where(Prospect.linkedin_url == url))
    prospect = result.scalars().one_or_none()
    if prospect is None:
        prospect = Prospect(linkedin_url=url)
        session.add(prospect)
        await session.flush()
    return prospect


class GenerateSequenceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.ai = AIService()

    async def run(self, body: GenerateSequenceRequest) -> GenerateSequenceResponse:
        # 1) Get or create prospect
        prospect = await get_or_create_prospect(self.session, body.prospect_url)

        # 2) Analyze profile (AI)
        profile_data, analysis_in_tok, analysis_out_tok = await self.ai.analyze_prospect(
            body.prospect_url,
            body.company_context,
        )

        prospect.profile_data = profile_data
        prospect.analyzed_at = datetime.utcnow()
        await self.session.flush()

        # 3) Build prospect analysis for response
        analysis_out = ProspectAnalysisOutput(
            summary=profile_data.get("summary", ""),
            role_or_industry=profile_data.get("role_or_industry"),
            signals=profile_data.get("signals") or [],
            raw_data=profile_data.get("raw_data"),
        )

        # 4) Generate sequence (AI)
        tov = body.tov_config
        seq_data, seq_in_tok, seq_out_tok = await self.ai.generate_sequence(
            prospect_analysis=profile_data,
            company_context=body.company_context,
            formality=tov.formality,
            warmth=tov.warmth,
            directness=tov.directness,
            sequence_length=body.sequence_length,
        )

        # 5) Persist sequence and messages
        tov_snapshot = {
            "formality": tov.formality,
            "warmth": tov.warmth,
            "directness": tov.directness,
        }
        sequence = MessageSequence(
            prospect_id=prospect.id,
            tov_config=tov_snapshot,
            company_context=body.company_context,
            sequence_length=body.sequence_length,
        )
        self.session.add(sequence)
        await self.session.flush()

        messages_list = seq_data.get("messages") or []
        for m in messages_list:
            msg = SequenceMessage(
                sequence_id=sequence.id,
                step_number=int(m.get("step", 0)),
                content=m.get("content", ""),
                thinking_process={"reasoning": m.get("thinking_process")} if m.get("thinking_process") else None,
                confidence_score=float(m["confidence_score"]) if m.get("confidence_score") is not None else None,
            )
            self.session.add(msg)

        # 6) Token tracking / AI generation record
        total_in = analysis_in_tok + seq_in_tok
        total_out = analysis_out_tok + seq_out_tok
        cost = AIService.estimate_cost(total_in, total_out) if (total_in or total_out) else None
        ai_gen = AIGeneration(
            sequence_id=sequence.id,
            model_used=settings.openai_model,
            input_tokens=total_in,
            output_tokens=total_out,
            cost_estimate=cost,
        )
        self.session.add(ai_gen)
        await self.session.flush()

        # 7) Build response
        message_outputs = [
            MessageOutput(
                step=m.get("step", i + 1),
                content=m.get("content", ""),
                thinking_process={"reasoning": m.get("thinking_process")} if m.get("thinking_process") else None,
                confidence_score=float(m["confidence_score"]) if m.get("confidence_score") is not None else None,
            )
            for i, m in enumerate(messages_list)
        ]
        token_usage = {"input_tokens": total_in, "output_tokens": total_out, "cost_estimate_usd": cost}

        return GenerateSequenceResponse(
            sequence_id=sequence.id,
            prospect_analysis=analysis_out,
            messages=message_outputs,
            thinking_process_summary=seq_data.get("thinking_summary"),
            model_used=settings.openai_model,
            token_usage=token_usage,
        )
