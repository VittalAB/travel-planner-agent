# Smart Travel Agent

A conversational travel-planning application with a Python backend and a
separate React frontend. The backend also includes a Streamlit interface that
can be run on its own.

## Features

- Plans trips and answers travel questions through a LangChain agent powered by
  `openai/gpt-oss-120b` on Groq.
- Searches the web for current travel information using DuckDuckGo.
- Looks up date-specific flight options using `fast-flights` and Google Flights.
  Prices are indicative and can change before booking.
- Adds the current date and time in India Standard Time to each agent model
  request; the agent can also retrieve it with its date tool.
- Keeps conversation state in memory by session ID. State is not persistent
  across backend restarts.
- Provides a streaming FastAPI endpoint for the React client and an alternate
  Streamlit chat interface.

## Repository layout

Run backend commands from `smart-travel-agent/` and frontend commands from
`smart-travel-agent-ui/`.

```text
travel_agent/                      # Git repository root
├── .gitignore
├── smart-travel-agent/            # Python backend
│   ├── app.py                     # Streamlit chat interface
│   ├── server.py                  # FastAPI health and streaming chat API
│   ├── requirements.txt
│   ├── core/
│   │   ├── agent.py               # LangChain agent and in-memory checkpointing
│   │   ├── constants.py
│   │   ├── log_manager.py
│   │   ├── prompts.py             # Agent and intent-classifier prompts
│   │   ├── schemas/
│   │   │   └── schemas.py         # Search and flight input validation
│   │   ├── state.py               # Trip constraint and agent state types
│   │   ├── tools.py               # Web search, flights, and current date tools
│   │   ├── middleware/
│   │   │   ├── date_context.py    # Injects current India time into requests
│   │   │   └── gaurdrail.py       # Travel-intent classifier middleware
│   │   └── token_budget.py        # Token estimation and limiting middleware
│   └── tests/
│       ├── test_flight_tool.py
│       ├── test_guardrail.py
│       └── test_token_budget.py
└── smart-travel-agent-ui/         # React 19 frontend, built with Vite
    ├── index.html
    ├── package.json
    └── src/
        ├── App.jsx                # Chat UI, streaming, session and transcript
        ├── main.jsx               # React entry point
        ├── openui.jsx             # Assistant Markdown rendering
        └── styles.css
```

The intent classifier and token-budget middleware are present in the backend,
but are not currently registered in the agent's middleware pipeline. The
active agent middleware is the current-date context middleware.

## Requirements

- Python 3.10 or newer
- Node.js and npm
- A Groq API key

## Configuration

Create `smart-travel-agent/.env` and set your key:

```dotenv
GROQ_API_KEY=your_groq_api_key
```

Optional backend settings:

```dotenv
LOG_LEVEL=INFO
FRONTEND_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

`FRONTEND_ORIGINS` is a comma-separated CORS allowlist. Its default allows the
Vite development server on `localhost:5173` and `127.0.0.1:5173`.

For the frontend, create `smart-travel-agent-ui/.env.local` only if the API is
not at its default address:

```dotenv
VITE_API_BASE_URL=http://localhost:8000
```

Do not commit `.env` files, API keys, Streamlit secrets, or credentials. Keep
only non-sensitive example configuration in any `.env.example` files.

## Run the application

### React frontend and FastAPI backend

In the first terminal, install and start the backend:

```bash
cd smart-travel-agent
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

In a second terminal, install and start the frontend:

```bash
cd smart-travel-agent-ui
npm install
npm run dev
```

Open the Vite URL printed in the terminal (usually `http://localhost:5173`).
The frontend streams chat responses from the backend using Server-Sent Events.

### Streamlit interface

From `smart-travel-agent/`, with the Python dependencies installed and
environment configured, run:

```bash
streamlit run app.py
```

The Streamlit interface invokes the same travel agent directly and does not
require the FastAPI server or React client.

## API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/health` | Returns `{"status":"ok"}` when the API is available. |
| `POST` | `/api/chat/stream` | Streams assistant text as `token`, then `done`; failures are sent as `error` events. |

Example request body:

```json
{
  "session_id": "session-example",
  "message": "Plan a 5-day trip to Switzerland from Delhi"
}
```

The request requires a non-empty `session_id` (up to 128 characters) and
`message` (up to 20,000 characters). The frontend stores its session ID and
transcript in browser `sessionStorage`; the agent's conversation checkpoint is
held in backend process memory.

## Tests

Run the backend tests from `smart-travel-agent/`:

```bash
python -m unittest discover -s tests
```

Build the React frontend from `smart-travel-agent-ui/`:

```bash
npm run build
```
