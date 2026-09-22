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

CREATOR_NAME = os.getenv("CREATOR_NAME", "Javier Sands").strip() or "Javier Sands"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini").strip() or "gpt-4o-mini"

app = FastAPI(title="IA Assistant", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

conversation_store: Dict[str, List[Dict[str, str]]] = {}


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=12000)
    session_id: Optional[str] = Field(default="default-session", max_length=100)


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    mode: str


def normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn").strip()


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


def calculate(expression: str) -> Optional[str]:
    expression = expression.replace("×", "*").replace("÷", "/").replace(",", ".").strip()
    if len(expression) > 100 or not re.fullmatch(r"[0-9+\-*/().%\s]+", expression):
        return None
    try:
        tree = ast.parse(expression, mode="eval")

        def evaluate(node: ast.AST) -> float:
            if isinstance(node, ast.Expression):
                return evaluate(node.body)
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                return float(node.value)
            if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPERATORS:
                left, right = evaluate(node.left), evaluate(node.right)
                if isinstance(node.op, ast.Pow) and abs(right) > 100:
                    raise ValueError
                return _ALLOWED_OPERATORS[type(node.op)](left, right)
            if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPERATORS:
                return _ALLOWED_OPERATORS[type(node.op)](evaluate(node.operand))
            raise ValueError

        result = evaluate(tree)
        if abs(result) > 1e100:
            return None
        return str(int(result)) if result.is_integer() else f"{result:.10f}".rstrip("0").rstrip(".")
    except (SyntaxError, ValueError, ZeroDivisionError, TypeError, OverflowError):
        return None


def local_reply(message: str) -> str:
    """Useful offline fallback; the real assistant uses OpenAI when configured."""
    text = normalize(message)
    math_match = re.search(r"(?:cuanto es|cuanto son|calcula|resultado de)\s+([0-9+\-*/().%\s×÷,]+)", text)
    expression = math_match.group(1) if math_match else (message if re.fullmatch(r"[0-9+\-*/().%\s×÷,]+", message.strip()) else None)
    if expression:
        result = calculate(expression)
        if result is not None:
            return f"El resultado es {result}."

    if re.search(r"(quien|quién).*(creo|creó|hizo)|creador|autor", text):
        return f"Fui creada por {CREATOR_NAME}. Soy el asistente de IA de este proyecto."
    if re.search(r"eres chat ?gpt|que chatbot|qué chatbot", text):
        return f"Soy IA Assistant, un asistente construido por {CREATOR_NAME}. Cuando la API está configurada, uso un modelo de OpenAI para responder."
    if "juan pablo duarte" in text:
        return "Juan Pablo Duarte fue un político, escritor y fundador de La Trinitaria. Es considerado el principal ideólogo y padre fundador de la República Dominicana, proclamada en 1844."
    if re.search(r"\b(hola|buenas|hey)\b", text):
        return "¡Hola! Soy IA Assistant. Puedo ayudarte a investigar, explicar, programar, planificar y resolver problemas."
    if text in {"ok", "okay", "vale", "perfecto", "gracias"}:
        return "¡Perfecto! ¿Qué necesitas hacer ahora?"
    return f"Estoy sin conexión con el modelo ahora mismo. Recibí: “{message}”. Configura OPENAI_API_KEY para activar respuestas inteligentes."


def openai_reply(session_id: str, message: str) -> Optional[str]:
    if not OPENAI_API_KEY:
        return None

    history = conversation_store.setdefault(session_id, [])[-20:]
    system_prompt = (
        f"Eres IA Assistant, el asistente personal creado por {CREATOR_NAME}. "
        f"Si preguntan quién te creó, responde claramente que tu creador es {CREATOR_NAME}. "
        "Eres útil, inteligente, preciso y natural. Responde siempre en español salvo que pidan otro idioma. "
        "Explica tus respuestas con el nivel de detalle adecuado. Si no sabes algo, dilo y no inventes. "
        "Puedes ayudar con historia, ciencia, programación, matemáticas, escritura, planificación y conversación."
    )
    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "system", "content": system_prompt}, *history, {"role": "user", "content": message}],
        "temperature": 0.7,
    }
    try:
        response = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
            json=payload,
            timeout=45,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return content.strip() if isinstance(content, str) and content.strip() else None
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError):
        return None


@app.get("/api/health")
def healthcheck():
    return {
        "status": "ok",
        "service": "IA Assistant",
        "mode": "openai" if OPENAI_API_KEY else "demo",
        "model": MODEL_NAME if OPENAI_API_KEY else None,
        "creator": CREATOR_NAME,
    }


@app.get("/", response_class=HTMLResponse)
def serve_index():
    return HTMLResponse((STATIC_DIR / "index.html").read_text(encoding="utf-8"))


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    session_id = (request.session_id or "default-session").strip() or "default-session"
    message = request.message.strip()
    history = conversation_store.setdefault(session_id, [])

    # Handle the creator question deterministically, even if the model is unavailable.
    if re.search(r"(quien|quién).*(creo|creó|hizo)|creador|autor", normalize(message)):
        reply = f"Fui creada por {CREATOR_NAME}. Soy IA Assistant, el asistente inteligente de este proyecto."
        mode = "local"
    else:
        reply = openai_reply(session_id, message)
        mode = "openai" if reply else "local"
        if not reply:
            reply = local_reply(message)

    history.extend([{"role": "user", "content": message}, {"role": "assistant", "content": reply}])
    del history[:-20]
    return ChatResponse(reply=reply, session_id=session_id, mode=mode)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
