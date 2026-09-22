from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="IA Assistant", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")

conversation_store: Dict[str, List[str]] = {}


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default-session"


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    mode: str


def build_demo_reply(message: str) -> str:
    msg = message.lower().strip()

    if not msg:
        return "No he recibido un mensaje útil. Puedes escribirme algo como: \"ayúdame a planear un proyecto\"."

    if "hola" in msg or "buenas" in msg or "hey" in msg:
        return "¡Hola! Soy tu asistente IA. ¿En qué puedo ayudarte hoy?"

    if "ayuda" in msg or "proyecto" in msg or "idea" in msg:
        return "Claro. Podemos definir objetivos, arquitectura, stack tecnológico y pasos de ejecución para tu proyecto. ¿Quieres que te ayude a estructurarlo paso a paso?"

    if "codigo" in msg or "programar" in msg or "desarrollo" in msg:
        return "Puedo ayudarte con lógica, arquitectura, APIs, frontend, backend y organización del proyecto. ¿Quieres que te proponga una solución concreta?"

    if "ia" in msg or "inteligencia" in msg:
        return "La inteligencia artificial puede ayudarte a automatizar tareas, analizar datos, responder preguntas y crear flujos inteligentes. Podemos empezar con una base funcional y luego escalarla."

    if "gracias" in msg:
        return "¡Con gusto! Estoy aquí para ayudarte cuando quieras."

    return (
        "He recibido tu mensaje. Como esta es una base inicial de IA, puedo ayudarte a estructurar ideas, proyectos, flujos y soluciones técnicas. "
        "Si me dices tu objetivo concreto, te respondo con una propuesta más útil."
    )


@app.get("/api/health")
def healthcheck():
    return {
        "status": "ok",
        "service": "IA assistant",
        "mode": "demo" if not OPENAI_API_KEY else "openai",
    }


@app.get("/", response_class=HTMLResponse)
def serve_index():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    session_id = request.session_id or "default-session"

    if session_id not in conversation_store:
        conversation_store[session_id] = []

    conversation_store[session_id].append(request.message)

    if OPENAI_API_KEY:
        try:
            import httpx

            headers = {
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            }

            payload = {
                "model": MODEL_NAME,
                "messages": [
                    {"role": "system", "content": "Eres un asistente IA útil, claro y profesional."},
                    {"role": "user", "content": request.message},
                ],
                "temperature": 0.7,
            }

            response = httpx.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=30,
            )

            response.raise_for_status()
            data = response.json()
            reply = data["choices"][0]["message"]["content"].strip()
            return ChatResponse(reply=reply, session_id=session_id, mode="openai")

        except Exception:
            pass

    reply = build_demo_reply(request.message)
    return ChatResponse(reply=reply, session_id=session_id, mode="demo")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
