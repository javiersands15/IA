from pathlib import Path
from typing import Dict, List, Optional
import os

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

app = FastAPI(title="IA Assistant", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serves /style.css and /script.js. Without this mount the browser cannot load
# the chat JavaScript, so the form appears to do nothing.
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


def build_demo_reply(message: str) -> str:
    msg = message.lower().strip()

    if not msg:
        return "Escribe un mensaje y te responderé."
    if any(word in msg for word in ("hola", "buenas", "hey")):
        return "¡Hola! Soy tu asistente IA. ¿En qué puedo ayudarte hoy?"
    if any(word in msg for word in ("ayuda", "proyecto", "idea")):
        return "Claro. Puedo ayudarte a definir objetivos, arquitectura, tecnologías y pasos concretos para tu proyecto."
    if any(word in msg for word in ("código", "codigo", "programar", "desarrollo")):
        return "Puedo ayudarte con frontend, backend, APIs, errores y organización del código. Cuéntame qué quieres construir."
    if any(word in msg for word in ("ia", "inteligencia artificial")):
        return "Podemos construir una IA por etapas: chat, memoria, herramientas, documentos y después voz o imágenes."
    if "gracias" in msg:
        return "¡De nada! Estoy aquí para ayudarte."
    return f"He entendido tu mensaje: “{message}”. Estoy en modo demo, pero puedo ayudarte a planearlo y convertirlo en pasos concretos."


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
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError):
        return None


@app.get("/api/health")
def healthcheck():
    return {
        "status": "ok",
        "service": "IA assistant",
        "mode": "openai" if OPENAI_API_KEY else "demo",
    }


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
