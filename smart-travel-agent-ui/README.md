# Smart Travel Agent UI

The React client uses OpenUI React Lang to render assistant messages as they stream
from the FastAPI backend. Streamlit remains available separately in the backend
project; its `app.py` is unchanged.

## Run locally

Start the API from the backend project directory:

```bash
.venv/bin/uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

In another terminal, start the React client:

```bash
npm install
npm run dev
```

The client expects the API at `http://localhost:8000`. Set
`VITE_API_BASE_URL` to use a different API address. The backend accepts browser
requests from `http://localhost:5173` and `http://127.0.0.1:5173` by default;
override this comma-separated allowlist with `FRONTEND_ORIGINS`.

The API exposes `GET /api/health` and `POST /api/chat/stream`. Chat state is
checkpointed in memory by session ID and is not persistent across server restarts.
