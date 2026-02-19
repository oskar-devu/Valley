from pydantic import BaseModel, ConfigDict, Field, field_validator


def clamp_0_1(v: float) -> float:
    return max(0.0, min(1.0, v))


class TovConfigIn(BaseModel):
    formality: float = Field(0.5, ge=0, le=1, description="0=casual, 1=formal")
    warmth: float = Field(0.5, ge=0, le=1, description="0=neutral, 1=warm")
    directness: float = Field(0.5, ge=0, le=1, description="0=subtle, 1=direct")

    @field_validator("formality", "warmth", "directness", mode="before")
    @classmethod
    def clamp(cls, v: float) -> float:
        if isinstance(v, (int, float)):
            return clamp_0_1(float(v))
        return v


class GenerateSequenceRequest(BaseModel):
    prospect_url: str = Field(..., min_length=10, max_length=512)
    tov_config: TovConfigIn = Field(default_factory=TovConfigIn)
    company_context: str = Field(..., min_length=1, max_length=2000)
    sequence_length: int = Field(3, ge=1, le=10)

    @field_validator("prospect_url")
    @classmethod
    def normalize_linkedin_url(cls, v: str) -> str:
        v = v.strip()
        if "linkedin.com/in/" not in v:
            raise ValueError("prospect_url must be a LinkedIn profile URL (e.g. https://linkedin.com/in/username)")
        if not v.startswith("http"):
            v = "https://" + v
        return v


class MessageOutput(BaseModel):
    step: int
    content: str
    thinking_process: dict | None = None
    confidence_score: float | None = None


class ProspectAnalysisOutput(BaseModel):
    summary: str
    role_or_industry: str | None = None
    signals: list[str] = Field(default_factory=list)
    raw_data: dict | None = None


class GenerateSequenceResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    sequence_id: str
    prospect_analysis: ProspectAnalysisOutput
    messages: list[MessageOutput]
    thinking_process_summary: str | None = None
    model_used: str | None = None
    token_usage: dict | None = None
