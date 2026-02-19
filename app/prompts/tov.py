"""
Convert numerical TOV parameters (0-1) into natural language instructions for the AI.
This keeps prompt behavior consistent and debuggable.
"""

# Buckets for each dimension to avoid overly granular wording
FORMALITY_BANDS = [
    (0.0, 0.25, "very casual and conversational; use contractions, light language."),
    (0.25, 0.5, "casual but professional; friendly tone, avoid jargon."),
    (0.5, 0.75, "professional and polished; clear and respectful."),
    (0.75, 1.01, "formal and businesslike; avoid slang, use full forms."),
]

WARMTH_BANDS = [
    (0.0, 0.25, "Keep tone neutral and factual; minimal personal flair."),
    (0.25, 0.5, "Slightly personable; one brief personal touch is fine."),
    (0.5, 0.75, "Warm and personable; show genuine interest, use a human touch."),
    (0.75, 1.01, "Very warm and empathetic; prioritize connection and rapport."),
]

DIRECTNESS_BANDS = [
    (0.0, 0.25, "Soft and indirect; lead with value, hint at the ask."),
    (0.25, 0.5, "Balanced; mention the purpose by the end but don't push."),
    (0.5, 0.75, "Clear and direct; state purpose and value proposition plainly."),
    (0.75, 1.01, "Very direct; get to the point quickly, clear call-to-action."),
]


def _band(value: float, bands: list[tuple[float, float, str]]) -> str:
    for lo, hi, text in bands:
        if lo <= value < hi:
            return text
    return bands[-1][2]


def tov_to_instructions(formality: float, warmth: float, directness: float) -> str:
    """Produce a short paragraph of tone instructions for the model."""
    f = _band(max(0, min(1, formality)), FORMALITY_BANDS)
    w = _band(max(0, min(1, warmth)), WARMTH_BANDS)
    d = _band(max(0, min(1, directness)), DIRECTNESS_BANDS)
    return (
        "Tone of voice:\n"
        f"- Formality: {f}\n"
        f"- Warmth: {w}\n"
        f"- Directness: {d}\n"
        "Write in first person, as the outreach sender. Keep messages concise and suitable for LinkedIn."
    )
