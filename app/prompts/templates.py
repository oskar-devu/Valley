PROFILE_ANALYSIS_PROMPT = """You are analyzing a LinkedIn prospect for a sales outreach sequence.

LinkedIn profile URL: {prospect_url}
Company context (what we do / who we help): {company_context}

Because we cannot access real LinkedIn data, infer a plausible B2B prospect profile from the URL (e.g. username/slug) and company context. Produce a short analysis that would be used to personalize messages.

Respond with a JSON object only, no markdown, with this exact structure:
{{
  "summary": "2-3 sentence summary of the prospect (role, industry, relevance to our offer).",
  "role_or_industry": "Job title or industry if inferrable.",
  "signals": ["list", "of", "personalization", "signals", "we", "might", "use"],
  "raw_data": {{}}
}}

Be concise. If the URL gives no real info, create a generic but realistic B2B prospect."""

SEQUENCE_GENERATION_PROMPT = """You are writing a personalized LinkedIn outreach sequence for a sales rep.

## Prospect analysis
{prospect_analysis}

## Company context
{company_context}

## Tone of voice
{tov_instructions}

## Task
Generate a sequence of exactly {sequence_length} short messages (e.g. connection request, follow-up 1, follow-up 2). Each message should feel natural for LinkedIn and respect the tone above.

For each message you must provide:
1. Your reasoning (thinking process) in 1-2 sentences: why this angle, why this length, what you're optimizing for.
2. The actual message text (what the rep would send).
3. A confidence score from 0 to 1 for how well this message fits the prospect and TOV.

Respond with a JSON object only, no markdown, with this exact structure:
{{
  "thinking_summary": "One paragraph summarizing your overall approach to this sequence.",
  "messages": [
    {{
      "step": 1,
      "thinking_process": "Your reasoning for this message.",
      "content": "The exact message text.",
      "confidence_score": 0.85
    }}
  ]
}}

Ensure "messages" has exactly {sequence_length} items. Keep each message under 300 characters for connection requests and under 500 for follow-ups."""
