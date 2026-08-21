import json
import os, traceback
from typing import List, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google import genai
from google.genai import types

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
    "inventory-card-block"
]

PAGE_TYPES_RULES = {
    "FINANCE": {"forbidden": ["inventory-card-block"], "label": "Centro de Financiamiento"},
    "ABOUT": {"forbidden": ["inventory-card-block"], "label": "Acerca de Nosotros"},
    "CONTACT": {"forbidden": ["inventory-card-block"], "label": "Contacto y Ubicación"},
    "CATALOG": {"forbidden": [], "label": "Catálogo / Inventario General"},
    "MODEL_SPECIFIC": {"forbidden": [], "label": "Lanzamiento / Modelo Específico"}
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
        Eres el agente de arquitectura web de 'The Promptastics' para concesionarias de autos.
        Tu trabajo es interpretar la solicitud en lenguaje natural y proponer el layout.

        REGLA OBLIGATORIA MANDATORIA:
        - TODA estructura o página generada DEBE TENER UN TÍTULO OBLIGATORIAMENTE (campo 'page_title'). NUNCA lo dejes vacío.

        Bloques disponibles en el catálogo:
        - "text-block": Texto explicativo o introductorio.
        - "left-image-block": Imagen a la izquierda, texto a la derecha.
        - "right-image-block": Texto a la izquierda, imagen a la derecha.
        - "inventory-card-block": Grilla de vehículos/modelos.

        Tipos de página permitidos: "FINANCE", "ABOUT", "CONTACT", "CATALOG", "MODEL_SPECIFIC".

        Devuelve ÚNICAMENTE un JSON estricto con este formato:
        {
          "page_title": "Título Claro y Relevante de la Página",
          "page_type": "TIPO_DE_PAGINA",
          "summary": "Resumen ejecutivo de lo que contendrá este diseño",
          "blocks": ["bloque-1", "bloque-2"]
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
            print(f"Error en Gemini: {e}")
            return {
                "page_title": "Página Automotriz",
                "page_type": "CATALOG",
                "summary": "Estructura estándar generada por contingencia",
                "blocks": ["text-block"]
            }

# ============================================================================
# 3. VALIDACIÓN DE ESQUEMA (Garantiza título y reglas de bloque)
# ============================================================================
class SchemaValidator:
    @staticmethod
    def validate(interpretation: Dict[str, Any], raw_prompt: str) -> Dict[str, Any]:
        title = interpretation.get("page_title", "").strip()
        # Garantizamos que NUNCA exista una página sin título
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
# 4. ORQUESTADOR
# ============================================================================
class AgentOrchestrator:
    def __init__(self, interpreter: GeminiInterpreter, validator: SchemaValidator):
        self.interpreter = interpreter
        self.validator = validator

    def run(self, user_prompt: str) -> Dict[str, Any]:
        raw = self.interpreter.interpret(user_prompt)
        validated = self.validator.validate(raw, user_prompt)

        return {
            "preview": {
                "page_title": validated["page_title"],
                "page_type": validated["page_type"],
                "page_type_label": validated["page_type_label"],
                "summary": validated["summary"]
            },
            "layout": {
                "blocks": validated["blocks"],
                "total_blocks": len(validated["blocks"])
            },
            "validation_logs": validated["applied_rules"]
        }

interpreter = GeminiInterpreter(client)
validator = SchemaValidator()
orchestrator = AgentOrchestrator(interpreter, validator)

class PromptDTO(BaseModel):
    prompt: str

@app.post("/api/generate-page")
async def generate_page(dto: PromptDTO):
    if not dto.prompt.strip():
        raise HTTPException(status_code=400, detail="El prompt no puede estar vacío.")
    return orchestrator.run(dto.prompt)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)