# IA

IA es un proyecto de asistente inteligente tipo chat, pensado como una base sólida para construir un agente conversacional moderno con Python y JavaScript.

La idea principal es contar con una estructura limpia, reutilizable y fácil de extender para:

- conversación con usuario
- integración con modelos de IA
- historial de mensajes
- interfaz web moderna
- despliegue sencillo en local o en la nube

## Stack

- Python 3.12+
- FastAPI
- Uvicorn
- JavaScript vanilla
- HTML/CSS
- dotenv

## Características

- Chat web con interfaz moderna
- API REST para enviar mensajes
- Respuesta local por defecto si no hay API key
- Preparado para integración con OpenAI o modelos compatibles
- Arquitectura simple y escalable
- Soporte para historial de conversación por sesión

## Estructura del proyecto

```text
IA/
├── app.py
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
├── LICENSE
├── static/
│   ├── index.html
│   ├── style.css
│   └── script.js
└── utils/
    └── __init__.py
```

## Instalación

### 1) Clonar el repositorio

```bash
git clone https://github.com/javiersands15/IA.git
cd IA
```

### 2) Crear entorno virtual

```bash
python -m venv .venv
```

En Windows:

```bash
.venv\Scripts\activate
```

En macOS/Linux:

```bash
source .venv/bin/activate
```

### 3) Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4) Configurar variables de entorno

Copia el archivo de ejemplo:

```bash
copy .env.example .env
```

o en Linux/macOS:

```bash
cp .env.example .env
```

Edita `.env` con tu clave si quieres usar modelo externo:

```env
OPENAI_API_KEY=tu_clave_aqui
MODEL_NAME=gpt-4o-mini
```

## Ejecutar la aplicación

```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

Luego abre:

```text
http://localhost:8000
```

La interfaz web estará disponible en la raíz del proyecto.

## API

### Endpoint de salud

```http
GET /api/health
```

Respuesta ejemplo:

```json
{
  "status": "ok",
  "service": "IA assistant",
  "mode": "demo"
}
```

### Endpoint de chat

```http
POST /api/chat
```

Body:

```json
{
  "message": "Hola, necesito ayuda con mi proyecto",
  "session_id": "demo-session"
}
```

Respuesta:

```json
{
  "reply": "¡Claro! Te puedo ayudar con ...",
  "session_id": "demo-session",
  "mode": "demo"
}
```

## Modo demo y modo real

El proyecto funciona sin clave API en modo demo, devolviendo respuestas útiles basadas en reglas simples y contexto local.

Si agregas una clave de OpenAI, el backend puede intentar integrar un modelo real para conversaciones más avanzadas.

## Roadmap

### Fase 1: base funcional
- [x] API de chat
- [x] interfaz web
- [x] respuestas demo
- [x] historial de sesión

### Fase 2: inteligencia real
- [ ] integración con modelos externos
- [ ] contexto persistente
- [ ] memoria de conversación
- [ ] autenticación de usuarios

### Fase 3: experiencia profesional
- [ ] dashboard de análisis
- [ ] agentes especializados
- [ ] almacenamiento de conversaciones
- [ ] despliegue en nube

## Contribuciones

Las contribuciones son bienvenidas. Puedes abrir issues, proponer mejoras o enviar pull requests con nuevas funcionalidades.

## Licencia

Este proyecto está licenciado bajo la licencia MIT. Consulta el archivo [LICENSE](LICENSE) para más información.

## Autor

Desarrollado por Javier Sands.
