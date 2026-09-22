from pathlib import Path
from typing import Dict, List, Optional
import ast
import operator
import os
import re
import unicodedata

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
load_dotenv(BASE_DIR / ".env")

app = FastAPI(title="IA Assistant", version="1.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")
conversation_store: Dict[str, List[Dict[str, str]]] = {}


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=12000)
    session_id: Optional[str] = Field(default="default-session", max_length=100)


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    mode: str


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower())
    return "".join(char for char in text if unicodedata.category(char) != "Mn")


# Only arithmetic expressions are accepted. No eval() is used.
_ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def safe_calculate(expression: str) -> Optional[float]:
    expression = expression.replace("×", "*").replace("÷", "/").replace(",", ".").strip()
    if len(expression) > 80 or not re.fullmatch(r"[0-9+\-*/().%\s]+", expression):
        return None

    try:
        tree = ast.parse(expression, mode="eval")

        def evaluate(node: ast.AST) -> float:
            if isinstance(node, ast.Expression):
                return evaluate(node.body)
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                return node.value
            if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPERATORS:
                left = evaluate(node.left)
                right = evaluate(node.right)
                if isinstance(node.op, ast.Pow) and abs(right) > 100:
                    raise ValueError("exponente demasiado grande")
                return _ALLOWED_OPERATORS[type(node.op)](left, right)
            if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPERATORS:
                return _ALLOWED_OPERATORS[type(node.op)](evaluate(node.operand))
            raise ValueError("expresión no permitida")

        result = evaluate(tree)
        if abs(result) > 1e100:
            return None
        return result
    except (SyntaxError, ValueError, ZeroDivisionError, TypeError, OverflowError):
        return None


def format_number(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.10f}".rstrip("0").rstrip(".")


def extract_math(message: str) -> Optional[str]:
    normalized = normalize(message)
    match = re.search(r"(?:cuanto es|cuanto son|calcula|calcular|resuelve|resultado de)\s+([0-9+\-*/().%\s×÷,]+)", normalized)
    if match:
        return match.group(1).strip()

    compact = message.strip()
    if re.fullmatch(r"[0-9+\-*/().%\s×÷,]+", compact) and any(char in compact for char in "+-*/%×÷"):
        return compact
    return None


def build_demo_reply(message: str) -> str:
    normalized = normalize(message).strip()
    math_expression = extract_math(message)
    if math_expression:
        result = safe_calculate(math_expression)
        if result is not None:
            return f"El resultado es **{format_number(result)}**."
        return "No pude calcular esa expresión. Comprueba que esté escrita, por ejemplo: 5 + 5."

    if not normalized:
        return "Escribe un mensaje y te responderé."
    if any(word in normalized for word in ("quien es tu creador", "quien te creo", "quien te creo", "quien te hizo", "tu creador")):
        return "Fui creado por **Javier Sands** como parte del proyecto IA. Actualmente estoy funcionando en modo demo."
    if normalized in {"ok", "okay", "vale", "entendido", "perfecto"}:
        return "¡Perfecto! ¿Qué te gustaría hacer ahora?"
    if any(word in normalized.split() for word in ("hola", "buenas", "hey")):
        return "¡Hola! Soy tu asistente IA. ¿En qué puedo ayudarte hoy?"
    if any(word in normalized for word in ("ayuda", "proyecto", "idea")):
        return "Claro. Puedo ayudarte a definir objetivos, arquitectura, tecnologías y pasos concretos para tu proyecto."
    if any(word in normalized for word in ("codigo", "programar", "desarrollo")):
        return "Puedo ayudarte con frontend, backend, APIs, errores y organización del código. Cuéntame qué quieres construir."
    if any(word in normalized for word in ("ia", "inteligencia artificial")):
        return "Podemos construir una IA por etapas: chat, memoria, herramientas, documentos y después voz o imágenes."
    if "gracias" in normalized:
        return "¡De nada! Estoy aquí para ayudarte."
    return f"He entendido tu mensaje: “{message}”. Estoy en modo demo. Puedo responder preguntas básicas, hacer cálculos y ayudarte a planear proyectos."


def recent_messages(session_id: str) -> List[Dict[str, str]]:
    return conversation_store.setdefault(session_id, [])[-12:]


def openai_reply(session_id: str, message: str) -> Optional[str]:
    if not OPENAI_API_KEY:
        return None
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": "Eres un asistente IA útil, claro y profesional. Responde en español salvo que el usuario pida otro idioma."},
            *recent_messages(session_id),
            {"role": "user", "content": message},
        ],
        "temperature": 0.7,
    }
    try:
        response = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError):
        return None


@app.get("/api/health")
def healthcheck():
    return {"status": "ok", "service": "IA assistant", "mode": "openai" if OPENAI_API_KEY else "demo"}


@app.get("/", response_class=HTMLResponse)
def serve_index():
    return HTMLResponse((STATIC_DIR / "index.html").read_text(encoding="utf-8"))


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    session_id = (request.session_id or "default-session").strip() or "default-session"
    message = request.message.strip()
    history = conversation_store.setdefault(session_id, [])
    history.append({"role": "user", "content": message})

    reply = openai_reply(session_id, message)
    mode = "openai" if reply else "demo"
    if not reply:
        reply = build_demo_reply(message)

    history.append({"role": "assistant", "content": reply})
    return ChatResponse(reply=reply, session_id=session_id, mode=mode)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
