import json
import os, traceback
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google import genai
from google.genai import types

from schemas import PageCopyResponse
from agents.copywriter import generate_page_copy

app = FastAPI(title="Layout Agent - The Promptastics")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

# ============================================================================
# 1. CATÁLOGO DE BLOQUES Y REGLAS
# ============================================================================
AVAILABLE_BLOCKS = [
    "text-block",
    "left-image-block",
    "right-image-block",
    "inventory-card-block",
    "contact-form-block",
    "breadcrumbs-block",
    "hero-image-block"
]

PAGE_TYPES_RULES = {
    "FINANCE": {"forbidden": ["inventory-card-block"], "label": "Financing Center"},
    "ABOUT": {"forbidden": ["inventory-card-block"], "label": "About Us"},
    "CONTACT": {"forbidden": ["inventory-card-block"], "label": "Contact & Location"},
    "CATALOG": {"forbidden": [], "label": "General Catalog / Inventory"},
    "MODEL_SPECIFIC": {"forbidden": [], "label": "New Launch / Specific Model"}
}

# ============================================================================
# 2. MOTOR DE INTERPRETACIÓN (Gemini)
# ============================================================================
class GeminiInterpreter:
    def __init__(self, genai_client: genai.Client):
        self.client = genai_client
        self.model_name = "gemini-3.6-flash"

    def interpret(self, prompt: str) -> Dict[str, Any]:
        system_instruction = """
        You are the web architecture agent for car dealerships.
        Your job is to interpret natural language requests and propose the page layout.

        MANDATORY RULE:
        - EVERY generated structure or page MUST HAVE A TITLE (field 'page_title'). NEVER leave it empty.

        SELECTION RULES FOR BLOCKS:
        1. IF the user prompt mentions "inventory", "stock", "vehicles", "catalog", "models", "trim levels", or "versions":
        - You MUST include "inventory-card-block" in the 'blocks' list.
        2. IF the page type is "MODEL_SPECIFIC" AND mentions inventory or available units/trims:
        - Always combine "hero-image-block", "inventory-card-block", and "contact-form-block".

        Available blocks in the catalog:
        - "text-block": Explanatory or introductory text.
        - "left-image-block": Image on the left, text on the right.
        - "right-image-block": Text on the left, image on the right.
        - "inventory-card-block": Vehicle/model grid (Must be used when user asks for inventory, stock, or model listings).
        - "contact-form-block": Interactive contact form.
        - "breadcrumbs-block": Breadcrumbs / Secondary navigation.
        - "hero-image-block": Main banner with hero image and title.

        Allowed page types: "FINANCE", "ABOUT", "CONTACT", "CATALOG", "MODEL_SPECIFIC".

        Return ONLY a strict JSON with this format:
        {
        "page_title": "Clear and Relevant Page Title",
        "page_type": "PAGE_TYPE",
        "summary": "Executive summary of what this layout will contain",
        "blocks": ["block-1", "block-2"]
        }
        """

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=f"Solicitud del usuario: '{prompt}'",
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                    temperature=0.2
                )
            )
            return json.loads(response.text)
        except Exception as e:
            print(f"Error en Gemini Interpreter: {e}")
            return {
                "page_title": "Página Automotriz",
                "page_type": "CATALOG",
                "summary": "Estructura estándar generada por contingencia",
                "blocks": ["text-block"]
            }

# ============================================================================
# 3. VALIDACIÓN DE ESQUEMA
# ============================================================================
class SchemaValidator:
    @staticmethod
    def validate(interpretation: Dict[str, Any], raw_prompt: str) -> Dict[str, Any]:
        title = interpretation.get("page_title", "").strip()
        if not title:
            title = f"Página Automotriz - {raw_prompt[:25].capitalize()}..."

        p_type = interpretation.get("page_type", "CATALOG")
        if p_type not in PAGE_TYPES_RULES:
            p_type = "CATALOG"

        forbidden = PAGE_TYPES_RULES[p_type]["forbidden"]
        raw_blocks = interpretation.get("blocks", [])
        
        applied_rules = []
        clean_blocks = []

        for b in raw_blocks:
            if b not in AVAILABLE_BLOCKS:
                applied_rules.append(f"Bloque desconocido descartado: '{b}'")
                continue
            if b in forbidden:
                applied_rules.append(f"Bloque '{b}' removido por regla de categoría [{p_type}]")
                continue
            clean_blocks.append(b)

        if not clean_blocks:
            clean_blocks = ["text-block"]
            applied_rules.append("Se asignó 'text-block' por lista vacía tras validación")

        return {
            "page_title": title,
            "page_type": p_type,
            "page_type_label": PAGE_TYPES_RULES[p_type]["label"],
            "summary": interpretation.get("summary", "Sin descripción disponible."),
            "blocks": clean_blocks,
            "applied_rules": applied_rules
        }

# ============================================================================
# 4. ORQUESTADOR (Mapeo dinámico de Secciones + Bloques Layout)
# ============================================================================
class AgentOrchestrator:
    def __init__(self, interpreter: GeminiInterpreter, validator: SchemaValidator):
        self.interpreter = interpreter
        self.validator = validator

    def _map_blocks_with_content(
        self, blocks: List[str], copy_data: PageCopyResponse, page_title: str
    ) -> List[Dict[str, Any]]:
        sections = copy_data.sections
        widgets = []

        # 1. Breadcrumbs dinámicos
        if "breadcrumbs-block" in blocks:
            crumb_title = getattr(copy_data, "page_title", page_title)
            
            widgets.append({
                "widget_type": "breadcrumbs-block",
                "title": f"{crumb_title}",
                "content": "",
                "image_url": None
            })

        # 2. Hero Image: Asigna el título real generado
        if "hero-image-block" in blocks:
            # Usa el page_title del copywriter o el título validado por la IA
            hero_title = getattr(copy_data, "page_title", page_title)
            hero_summary = getattr(copy_data, "summary", "")

            widgets.append({
                "widget_type": "hero-image-block",
                "title": hero_title,      
                "content": hero_summary, 
                "image_url": "https://placehold.co/1200x500?text=Hero+Auto"
            })

        # 3. Mapeo dinámico de secciones explicativas
        image_toggle = "right-image-block"

        for idx, sec in enumerate(sections):
            header = sec.header.strip() if hasattr(sec, "header") else ""
            body_text = getattr(sec, "body", getattr(sec, "content", getattr(sec, "text", "")))
            body = body_text.strip() if isinstance(body_text, str) else str(body_text)

            if idx == 0:
                widget_type = "text-block"
            elif idx == len(sections) - 1:
                widget_type = "text-block"
            else:
                widget_type = image_toggle
                image_toggle = "left-image-block" if image_toggle == "right-image-block" else "right-image-block"

            widgets.append({
                "widget_type": widget_type,
                "title": header,
                "content": body,
                "image_url": "https://placehold.co/600x400?text=Auto" if "image" in widget_type else None
            })

        # 4. Inventory Card Block (si la IA lo solicitó)
        if "inventory-card-block" in blocks:
            widgets.append({
                "widget_type": "inventory-card-block",
                "title": "Inventario Disponible",
                "content": "Explora los modelos y versiones disponibles en stock.",
                "image_url": None
            })

        # 5. Formulario de contacto (si la IA lo solicitó)
        if "contact-form-block" in blocks:
            widgets.append({
                "widget_type": "contact-form-block",
                "title": "Contact Us",
                "content": "Request your test drive or personalized quote.",
                "image_url": None
            })

        return widgets

    async def run(self, user_prompt: str) -> Dict[str, Any]:
        raw = self.interpreter.interpret(user_prompt)
        validated = self.validator.validate(raw, user_prompt)

        copy_data: PageCopyResponse = await generate_page_copy(user_prompt)

        # Pasamos validated["page_title"] a la función para mapear el título en el hero
        assembled_widgets = self._map_blocks_with_content(
            validated["blocks"], copy_data, validated["page_title"]
        )

        real_block_list = [w["widget_type"] for w in assembled_widgets]

        return {
            "preview": {
                "page_title": validated["page_title"],
                "page_type": validated["page_type"],
                "page_type_label": validated["page_type_label"],
                "summary": validated["summary"]
            },
            "layout": {
                "blocks": real_block_list,
                "total_blocks": len(real_block_list)
            },
            "widgets": assembled_widgets,
            "validation_logs": validated["applied_rules"],
            "copywriter_content": copy_data.model_dump()
}

interpreter = GeminiInterpreter(client)
validator = SchemaValidator()
orchestrator = AgentOrchestrator(interpreter, validator)

class PromptDTO(BaseModel):
    prompt: str

# ============================================================================
# 5. ENDPOINT PRINCIPAL
# ============================================================================
@app.post("/api/generate-page")
async def generate_page(dto: PromptDTO):
    if not dto.prompt.strip():
        raise HTTPException(status_code=400, detail="The prompt cannot be empty.")
    
    return await orchestrator.run(dto.prompt)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)