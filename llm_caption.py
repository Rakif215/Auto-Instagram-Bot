"""
llm_caption.py — Generates Instagram captions using Groq (primary) with
Gemini as fallback. Both are free-tier compatible.
"""

import json
import logging
from config import GROQ_API_KEY, GEMINI_API_KEY, GEMINI_MODEL

logger = logging.getLogger(__name__)

CAPTION_PROMPT = """You are an expert geopolitical analyst and social media editor for a neutral, professional news page.

Given this news headline and source, output a response STRICTLY following this exact template. You MUST include these two exact tags in your output: [CAPTION] and [HASHTAGS].

[CAPTION]
Write a detailed, engaging, multi-paragraph story (100-200 words). Explain the context, who is involved, and why it matters globally. Maintain a neutral, factual, and strictly objective tone. Format with normal line breaks for readability. 
CRITICAL RULE: You MUST stick EXACTLY to the facts implied by the headline. DO NOT invent or hallucinate casualties, locations, or dates that are not explicitly mentioned or universally known context for this exact event.
End the last paragraph with: 'Source: {source}'

[HASHTAGS]
#worldnews #breakingnews #geopolitics (add 5-7 more highly relevant tags here)

Headline: {headline}
Source: {source}

Rules:
- You MUST output the tags [CAPTION] and [HASHTAGS] exactly as shown.
- DO NOT output any introductory or conversational text."""

FILTER_PROMPT = """You are a strict news filter for a combat and war reporting page.
Is the following headline STRICTLY about an active military conflict, war, airstrikes, armed rebellion, or an immediate threat of violent war between nations?

Answer strictly with "true" if it involves active military/war action.
Answer "false" if it is about general foreign politics (like elections), diplomacy without an active war, sports, entertainment, or domestic crime.

Headline: {headline}
Answer (true/false ONLY):"""


import re

def _parse_response(raw: str, source: str) -> dict:
    """Extract sections based on the [TAG] markers using Regex for robustness."""
    text = raw.strip()
    logger.debug(f"Raw LLM output:\n{text}")
    
    caption = ""
    hashtags = "#worldnews #breakingnews #globalupdate #news #aljazeera"
    search_query = "news"
    
    try:
        # Use regex to find tags even if LLM adds bolding, colons, or different casing
        caption_match = re.search(r'\[\s*CAPTION\s*\][^\n]*(.*?)(?:\[\s*HASHTAGS\s*\]|$)', text, re.IGNORECASE | re.DOTALL)
        if caption_match:
            caption = caption_match.group(1).strip()
            
        hashtags_match = re.search(r'\[\s*HASHTAGS\s*\][^\n]*(.*?)$', text, re.IGNORECASE | re.DOTALL)
        if hashtags_match:
            hashtags = hashtags_match.group(1).strip()
            
        if not caption:
            caption = text[:300]
            
    except Exception as e:
        logger.error(f"Failed to parse LLM text: {e}")
        caption = text[:300]
        
    return {
        "caption": caption,
        "hashtags": hashtags,
    }


def _groq_caption(headline: str, source: str) -> dict:
    from groq import Groq
    client = Groq(api_key=GROQ_API_KEY)
    prompt = CAPTION_PROMPT.format(headline=headline, source=source)
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=300,
        temperature=0.7,
    )
    raw = response.choices[0].message.content
    logger.info("Caption generated via Groq.")
    return _parse_response(raw, source)


def _gemini_caption(headline: str, source: str) -> dict:
    import google.generativeai as genai
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(GEMINI_MODEL)
    prompt = CAPTION_PROMPT.format(headline=headline, source=source)
    response = model.generate_content(prompt)
    logger.info("Caption generated via Gemini.")
    return _parse_response(response.text, source)


def generate_caption(headline: str, source: str = "Al Jazeera") -> dict:
    """
    Generate caption + hashtags. Tries Groq first, falls back to Gemini.
    Returns {'caption': str, 'hashtags': str}.
    """
    if GROQ_API_KEY:
        try:
            return _groq_caption(headline, source)
        except Exception as e:
            logger.warning(f"Groq failed ({e}), trying Gemini...")

    if GEMINI_API_KEY:
        try:
            return _gemini_caption(headline, source)
        except Exception as e:
            logger.error(f"Gemini also failed: {e}")

    raise RuntimeError("Both Groq and Gemini failed. Check your API keys.")


def is_relevant_news(headline: str) -> bool:
    """
    Uses LLM to determine if the headline is strictly about war, conflict, or geopolitics.
    Returns True if relevant, False if it's sports, entertainment, etc.
    """
    prompt = FILTER_PROMPT.format(headline=headline)
    
    # Try Groq first
    if GROQ_API_KEY:
        try:
            from groq import Groq
            client = Groq(api_key=GROQ_API_KEY)
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=10,
                temperature=0.1,
            )
            ans = response.choices[0].message.content.strip().lower()
            return "true" in ans
        except Exception as e:
            logger.warning(f"Groq filter failed ({e}), trying Gemini...")

    # Fallback to Gemini
    if GEMINI_API_KEY:
        try:
            import google.generativeai as genai
            genai.configure(api_key=GEMINI_API_KEY)
            model = genai.GenerativeModel(GEMINI_MODEL)
            response = model.generate_content(prompt)
            ans = response.text.strip().lower()
            return "true" in ans
        except Exception as e:
            logger.error(f"Gemini filter failed: {e}")
            
    # Default to True if APIs fail, so we don't accidentally drop good news
    return True
