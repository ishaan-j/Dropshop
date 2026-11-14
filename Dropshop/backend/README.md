# Backend (Python), shared by Layers 2–5

One Python project, split into packages with separate owners:

| Package | Layer | Owner doc |
|---|---|---|
| `app/` | 2. Backend: FastAPI, workers, orchestration | [app/LAYER.md](app/LAYER.md) |
| `agents/` | 3. AI and agents: Gemini, Sentient OS, Playwright | [agents/LAYER.md](agents/LAYER.md) |
| `data/` | 4. Database: Tiger Data + MongoDB Atlas | [data/LAYER.md](data/LAYER.md) |
| `finance/` | 5. Financial: Nessie + Solana client | [finance/LAYER.md](finance/LAYER.md) |

**Import rule:** only `app/` imports from `agents/`, `data/` and `finance/`. Those three never import each other.
Shared shapes live in `app/models.py`, and everyone imports from there.

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
uvicorn app.main:app --reload                         # http://localhost:8000/docs
arq app.workers.worker.WorkerSettings                 # background jobs (needs Redis)
```
