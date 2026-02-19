from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.schemas.generate import GenerateSequenceRequest, GenerateSequenceResponse
from app.services.generate import GenerateSequenceService

router = APIRouter(prefix="/api", tags=["api"])


@router.post("/generate-sequence", response_model=GenerateSequenceResponse)
async def generate_sequence(
    body: GenerateSequenceRequest,
    session: AsyncSession = Depends(get_session),
) -> GenerateSequenceResponse:
    """Generate a personalized messaging sequence for a LinkedIn prospect."""
    try:
        service = GenerateSequenceService(session)
        return await service.run(body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Sequence generation failed. Please try again.") from e
