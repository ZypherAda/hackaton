import json
import os, traceback
import requests
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()
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

    def _map_blocks_with_content(self, blocks: List[str], copy_data: PageCopyResponse) -> List[Dict[str, Any]]:
        sections = copy_data.sections
        widgets = []

        if "breadcrumbs-block" in blocks:
            widgets.append({
                "widget_type": "breadcrumbs-block",
                "title": "Navegación",
                "content": "",
                "image_url": None
            })

        if "hero-image-block" in blocks:
            widgets.append({
                "widget_type": "hero-image-block",
                "title": "Hero Banner",
                "content": "",
                "image_url": "https://placehold.co/1200x500?text=Hero+Auto"
            })

        # 2. Asignar un widget específico para CADA sección redactada por el Copywriter
        image_toggle = "right-image-block"

        for idx, sec in enumerate(sections):
            header = sec.header.strip() if hasattr(sec, "header") else ""
            
            body_text = getattr(sec, "body", getattr(sec, "content", getattr(sec, "text", "")))
            body = body_text.strip() if isinstance(body_text, str) else str(body_text)

            # Regla de asignación por tipo de sección:
            if idx == 0:
                widget_type = "text-block"  # Introducción
            elif idx == len(sections) - 1:
                widget_type = "text-block"  # Conclusión
            else:
                # Alternar entre right-image-block y left-image-block para las características
                widget_type = image_toggle
                image_toggle = "left-image-block" if image_toggle == "right-image-block" else "right-image-block"

            widgets.append({
                "widget_type": widget_type,
                "title": header,
                "content": body,
                "image_url": "https://placehold.co/600x400?text=Auto" if "image" in widget_type else None
            })

        # 3. Bloque de contacto al final si correspondía
        if "contact-form-block" in blocks:
            widgets.append({
                "widget_type": "contact-form-block",
                "title": "Ponte en Contacto",
                "content": "Request your test drive or personalized quote.",
                "image_url": None
            })

        return widgets

    async def run(self, user_prompt: str) -> Dict[str, Any]:
        raw = self.interpreter.interpret(user_prompt)
        validated = self.validator.validate(raw, user_prompt)

        copy_data: PageCopyResponse = await generate_page_copy(user_prompt)

        assembled_widgets = self._map_blocks_with_content(validated["blocks"], copy_data)

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

class QARequestDTO(BaseModel):
    url: str

# ============================================================================
# 5. ENDPOINT PRINCIPAL
# ============================================================================

@app.post("/api/generate-page")
async def generate_page(dto: PromptDTO):
    if not dto.prompt.strip():
        raise HTTPException(status_code=400, detail="The prompt cannot be empty.")
    
    return await orchestrator.run(dto.prompt)

# ============================================================================
# 6. ENDPOINT QA — delega al qa-service (Node.js, puerto 4000)
# ============================================================================
@app.post("/api/qa-check")
async def qa_check(dto: QARequestDTO):
    if not dto.url.strip():
        raise HTTPException(status_code=400, detail="La URL no puede estar vacía.")
    try:
        response = requests.post(
            "http://localhost:4000/api/full-analysis/run",
            json={"url": dto.url.strip()},
            timeout=30
        )
        response.raise_for_status()
        raw = response.json()

        desktop = raw.get("desktop", {})
        anchors  = desktop.get("anchors", [])
        buttons  = desktop.get("buttons", [])
        images   = desktop.get("images", [])
        h1_texts = desktop.get("h1Texts", [])
        cp_lines = desktop.get("cp", {}).get("lines", [])

        # Fetch image sizes (non-blocking — skipped if qa-service can't resolve)
        img_srcs = [img.get("src") for img in images[:10] if (img.get("src") or "").startswith("http")]
        img_sizes_map: Dict[str, Any] = {}
        if img_srcs:
            try:
                size_resp = requests.post(
                    "http://localhost:4000/api/link-reading/image-sizes",
                    json={"urls": img_srcs},
                    timeout=20
                )
                if size_resp.ok:
                    for s in size_resp.json().get("sizes", []):
                        img_sizes_map[s.get("url")] = s.get("bytes")
            except Exception:
                pass

        def _img_rating(b: Any) -> Dict[str, Any]:
            if b is None:
                return {"kb": None, "rating": "unknown", "reason": "Size could not be retrieved"}
            kb = round(b / 1024, 1)
            if kb <= 100:
                return {"kb": kb, "rating": "good", "reason": "Within recommended web budget (\u2264 100 KB)"}
            elif kb <= 300:
                return {"kb": kb, "rating": "acceptable", "reason": "Acceptable \u2014 consider optimizing for mobile users (101\u2013300 KB)"}
            else:
                return {"kb": kb, "rating": "large", "reason": f"Exceeds web performance guidelines \u2014 target < 200 KB per image (currently {kb} KB)"}

        link_items = [
            {
                "url": a.get("url"),
                "text": a.get("text"),
                "type": "relative" if a.get("isRelative") else "absolute",
                "status": a.get("status"),
                "ok": a.get("statusOk", False),
            }
            for a in anchors
        ]
        broken_items = [l for l in link_items if not l["ok"]]
        relative_count = sum(1 for l in link_items if l["type"] == "relative")

        result = {
            "url": dto.url.strip(),
            "h1": h1_texts,
            "text_lines": len(cp_lines),
            "links": {
                "total": len(link_items),
                "ok": len(link_items) - len(broken_items),
                "broken": len(broken_items),
                "relative": relative_count,
                "absolute": len(link_items) - relative_count,
                "broken_items": [{"url": l["url"], "text": l["text"], "status": l["status"], "type": l["type"]} for l in broken_items[:10]],
            },
            "buttons": [{"text": b.get("text"), "hasLink": b.get("hasLink")} for b in buttons],
            "images": {
                "total": len(images),
                "items": [
                    {"src": img.get("src"), "alt": img.get("alt", ""), **_img_rating(img_sizes_map.get(img.get("src")))}
                    for img in images[:10]
                ],
            },
        }

        # AI-generated plain-language summary via Gemini
        img_items = result["images"]["items"]
        kb_values = [i["kb"] for i in img_items if i["kb"] is not None]
        large_imgs = [i for i in img_items if i["rating"] == "large"]
        broken_count = result["links"]["broken"]
        h1_count = len(result["h1"])

        summary_input = (
            f"URL audited: {result['url']}\n"
            f"H1 tags found: {h1_count} — {result['h1']}\n"
            f"Editorial text: {result['text_lines']} lines\n"
            f"Links: {result['links']['total']} total, {result['links']['ok']} working, "
            f"{broken_count} broken, {result['links']['relative']} relative, {result['links']['absolute']} absolute\n"
            f"Buttons/CTAs: {len(result['buttons'])} — {[b['text'] for b in result['buttons']]}\n"
            f"Images: {result['images']['total']} found, "
            f"sizes {f'{min(kb_values)}–{max(kb_values)} KB' if kb_values else 'unknown'}, "
            f"{len(large_imgs)} oversized"
        )

        try:
            gemini_resp = client.models.generate_content(
                model="gemini-3.6-flash",
                contents=(
                    f"You are a friendly web quality analyst writing for a non-technical audience.\n"
                    f"Based on this QA audit data, write a concise summary of 3-4 sentences in English.\n"
                    f"Mention what is working well, any issues found, and one practical recommendation.\n"
                    f"Keep the tone clear, positive where appropriate, and avoid technical jargon.\n\n"
                    f"{summary_input}"
                ),
                config=types.GenerateContentConfig(temperature=0.4)
            )
            result["ai_summary"] = gemini_resp.text.strip()
        except Exception:
            result["ai_summary"] = None

        return result
    except requests.exceptions.ConnectionError:
        raise HTTPException(status_code=503, detail="QA Service (puerto 4000) no está corriendo.")
    except requests.exceptions.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Error del QA Service: {e}")
    except Exception as e:
        print(f"Error en qa-check: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)