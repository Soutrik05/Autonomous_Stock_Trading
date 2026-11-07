# Running the StockMinds backend and testing it in the browser (Windows)

## 1. Start the server

Open a terminal (Command Prompt, PowerShell, or Git Bash) in the repo root
(`C:\Users\KIIT0001\Desktop\Autonomous_Stock_Trading`) and run:

**Command Prompt:**
```bat
set PYTHONPATH=src
python -m uvicorn api.main:app --reload --port 8000
```

**PowerShell:**
```powershell
$env:PYTHONPATH = "src"
python -m uvicorn api.main:app --reload --port 8000
```

**Git Bash:**
```bash
PYTHONPATH=src python -m uvicorn api.main:app --reload --port 8000
```

Wait for this line, which means it's ready:
```
INFO:     Application startup complete.
```

Leave this terminal open — the server keeps running in it. Press `Ctrl+C` there to stop it.

(Note: `uvicorn src.api.main:app` — the command you might see suggested elsewhere — does **not**
work in this repo; it must be `api.main:app` with `src` on `PYTHONPATH`, exactly as above.)

## 2. Try it in the browser

With the server running, open any of these URLs directly in your browser:

- **Interactive docs (try every endpoint by hand):** http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/api/health
- Leaderboard: http://127.0.0.1:8000/api/leaderboard
- NAV series: http://127.0.0.1:8000/api/agents/nav
- Simons' positions: http://127.0.0.1:8000/api/agents/simons/positions
- Simons' heuristics: http://127.0.0.1:8000/api/agents/simons/memory
- Baseline comparison: http://127.0.0.1:8000/api/baseline/comparison?persona=simons
- Activity feed: http://127.0.0.1:8000/api/activity?limit=20
- Watchlist funnel: http://127.0.0.1:8000/api/funnel
- Backtest runs: http://127.0.0.1:8000/api/backtest/runs

The `/docs` page is the easiest way to explore: click any endpoint, click **Try it out**, click
**Execute**, and the real response appears below — no separate tool needed.

## 3. Point the dashboard at it

The dashboard (`dashboard/`) defaults to mock data. To make it call this real server instead,
open its dev console (`F12` in the browser tab running `npm run dev`) and run:

```js
localStorage.setItem('stockminds_use_mock_data', 'false')
```

then reload the page. The header's status pill should turn green ("online") within 15 seconds —
that's it polling `GET /api/health`.

## 4. Run the backend's own test suite

```bash
cd Autonomous_Stock_Trading
python -m pytest tests -q
```

This runs entirely against temporary databases — it never touches
`storage/ledger/portfolio.db` or anything under `storage/backtest/`.
