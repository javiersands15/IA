from pathlib import Path
from typing import Dict, List, Optional
import ast
import operator
import os
import random
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

app = FastAPI(title="IA Assistant", version="1.3.0")
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
    return "".join(char for char in text if unicodedata.category(char) != "Mn").strip()


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
        node = ast.parse(expression, mode="eval")

        def evaluate(n: ast.AST):
            if isinstance(n, ast.Expression):
                return evaluate(n.body)
            if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
                return float(n.value)
            if isinstance(n, ast.BinOp) and type(n.op) in _ALLOWED_OPERATORS:
                left = evaluate(n.left)
                right = evaluate(n.right)
                return _ALLOWED_OPERATORS[type(n.op)](left, right)
            if isinstance(n, ast.UnaryOp) and type(n.op) in _ALLOWED_OPERATORS:
                return _ALLOWED_OPERATORS[type(n.op)](evaluate(n.operand))
            raise ValueError("expresión no permitida")

        result = evaluate(node)
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
    patterns = [
        r"(?:cuanto|cuanto es|cuanto son|calcula|calcular|resuelve|resultado de)\s+([0-9+\-*/().%\s×÷,]+)",
        r"([0-9]+\s*[+\-*/%]\s*[0-9]+(?:\s*[+\-*/%]\s*[0-9]+)*)",
    ]
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            return match.group(1).strip()
    compact = message.strip()
    if re.fullmatch(r"[0-9+\-*/().%\s×÷,]+", compact) and any(ch in compact for ch in "+-*/%×÷"):
        return compact
    return None


def random_joke() -> str:
    jokes = [
        "¿Por qué el código no se cae? Porque siempre lleva su stack bien apoyado.",
        "¿Cómo se dice 'ya está' en Python? 'import done'.",
        "¿Qué le dijo una IA a otra? 'Necesitamos más contexto'.",
        "Un algoritmo fue a la fiesta y todos dijeron: '¡Qué bueno que viniste, tienes lógica!'",
    ]
    return random.choice(jokes)


def build_demo_reply(message: str) -> str:
    original = message.strip()
    normalized = normalize(original)
    math_expression = extract_math(original)
    if math_expression:
        result = safe_calculate(math_expression)
        if result is not None:
            return f"El resultado es {format_number(result)}."
        return "No pude calcular esa expresión. Prueba algo como: 5 + 5, 10 * 3 o 8 / 2."

    if not normalized:
        return "Escribe un mensaje y te responderé."

    if re.search(r"\b(quien|who)\b.*\b(te|you)\b.*\b(creo|hizo|creo|t creo|fabric|puso)\b|\bcreador\b|\bquien eres\b|\bquien es tu creador\b", normalized):
        return "Fui creado por Javier Sands como parte del proyecto IA. Estoy funcionando en modo demo, pero puedo ayudarte con conversaciones, ideas, cálculos y planificación."

    if re.search(r"\b(eres humano|eres una persona|eres real|que eres|quien eres)\b", normalized):
        return "Soy una asistente digital, una IA creada para conversar, ayudar y responder preguntas, pero no soy una persona real."

    if any(word in normalized for word in ("hola", "buenas", "buenos dias", "buenas tardes", "hey", "saludos")):
        return "¡Hola! Soy tu asistente IA. ¿En qué puedo ayudarte hoy?"

    if normalized in {"ok", "okay", "vale", "bien", "perfecto", "entendido"}:
        return "¡Perfecto! ¿Qué quieres hacer ahora?"

    if re.search(r"\b(como estas|como va|como te va|como estas hoy)\b", normalized):
        return "¡Muy bien! Estoy listo para ayudarte con ideas, planificación, cálculos o cualquier duda que tengas."

    if any(word in normalized for word in ("ayuda", "proyecto", "idea", "plan", "diseño", "arquitectura")):
        return "Claro. Podemos definir objetivos, stack tecnológico, arquitectura, tareas y un plan de ejecución paso a paso."

    if any(word in normalized for word in ("codigo", "codigo", "programar", "programacion", "desarrollo", "app", "web", "api")):
        return "Puedo ayudarte con lógica, APIs, frontend, backend, errores y organización del código. Cuéntame qué quieres construir."

    if any(word in normalized for word in ("ia", "inteligencia artificial", "modelo", "chatbot")):
        return "La inteligencia artificial puede ayudarte a automatizar tareas, responder preguntas, analizar texto, generar ideas y apoyarte en proyectos."

    if re.search(r"\b(chiste|broma|cuentame un chiste|dime un chiste)\b", normalized):
        return random_joke()

    if re.search(r"\b(gracias|thank you|mil gracias)\b", normalized):
        return "¡Con gusto! Estoy aquí para ayudarte cuando quieras."

    if re.search(r"\b(adios|hasta luego|chau|bye)\b", normalized):
        return "¡Hasta luego! Me quedaré lista para ayudarte en la próxima conversación."

    if re.search(r"\b(resumen|explicame|describe|que es|para que sirve)\b", normalized):
        return "Puedo ayudarte a resumir, explicar conceptos o convertir ideas complejas en pasos simples. Dime exactamente qué necesitas explicar."

    if re.search(r"\b(traduc|translate|ingles|spanish)\b", normalized):
        return "Puedo ayudarte a traducir frases cortas y a reformular textos en español o inglés. Escríbeme la frase exacta."

    if re.search(r"\b(nombre|como te llamas|te llamas)\b", normalized):
        return "Me llamo IA Assistant. Soy tu asistente virtual y estoy aquí para ayudarte."

    if re.search(r"\b(quiero|necesito|me gustaria|me gustaría)\b", normalized):
        return "Perfecto. Cuéntame qué quieres lograr y te ayudo a definir el mejor camino para conseguirlo."

    if re.search(r"\b(que puedes hacer|funciones|para que sirves)\b", normalized):
        return "Puedo responder preguntas, ayudarte a planear proyectos, hacer cálculos, explicar ideas, crear estructuras y apoyar tareas de programación."

    if re.search(r"\b(5\s*\*\s*5|5\+5|5\s*\+\s*5|cuanto es\s*5\s*\+\s*5|cuanto son\s*5\s*\+\s*5)\b", normalized):
        return "El resultado es 10."

    return (
        f"He entendido tu mensaje: “{original}”. "
        "Estoy en modo demo, pero puedo ayudarte con preguntas básicas, cálculos, ideas, proyectos y conversaciones simples."
    )


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
