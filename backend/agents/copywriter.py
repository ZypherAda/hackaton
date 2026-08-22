import os
from google import genai
from google.genai import types
from schemas import PageCopyResponse

COPYWRITER_SYSTEM_PROMPT = """
You are an expert automotive copywriter. Your job is to generate persuasive, professional web content for dealership pages.

Rules:
1. IF the prompt mentions a specific vehicle (Make, Model, Year):
   - You MUST generate content tailored to that exact vehicle.
   - If missing details (e.g., year), infer a recent realistic model year or pick an iconic vehicle model randomly.
   - DEFAULT SECTIONS TO INCLUDE (unless requested otherwise):
     * Introduction
     * Exterior
     * Interior
     * Trims
     * Conclusion
2. IF the prompt is for a general page (Finance, About Us, Service Center, etc.):
   - Propose relevant sections dynamically based on the page context.
3. SECTION FORMAT:
   - Max 5 sections total.
   - Every section MUST have a distinct header (title).
   - Every section content MUST be between 1 and 2 paragraphs maximum.
"""

async def generate_page_copy(user_prompt: str) -> PageCopyResponse:
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    
    response = client.models.generate_content(
        model="gemini-3.6-flash",  # <--- Asegurar que usa gemini-3.6-flash
        contents=f"User Request: {user_prompt}",
        config=types.GenerateContentConfig(
            system_instruction=COPYWRITER_SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=PageCopyResponse,
            temperature=0.3
        )
    )
    
    return PageCopyResponse.model_validate_json(response.text)