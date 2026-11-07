# StockMinds — Week 3 Handin & Handover Notes

> **Target audience:** the teammate picking up Week 4 (API & dashboard).
> **Date:** 2026-11-04
> **Branch:** `week3-learning` (off `v2-ATA`), pushed to `origin` as a backup — **not merged anywhere.**
> **Status:** Learning loop built and fully tested (376/376 passing). **Not yet proven against a real live LLM call** — see "Known limits" below.

---

## 1. What Week 3 adds, in plain English

Before this week, the system could run each trading day: ingest data, build features, let each agent decide, place orders, fill them, and classify each closed trade into one post-mortem label (win or loss, and why). What it could **not** do yet was *learn* — turn those classified trades into rules that change next week's prompts.

Week 3 adds exactly that "learning loop," in three pieces:

1. **A nightly checker (`src/learning/memory_manager.py`)** — every night, it looks at the heuristics (rules) each agent currently has, checks whether tonight's candidates match any of them, and separately checks whether older "did this rule work?" questions can now be answered (because enough days have passed to see the stock's actual return). Based on how well a rule has done, it promotes it (testing → active → reinforced) or retires it (deprecated). This part never calls an AI model — it's just deterministic bookkeeping.
2. **A weekly reviewer (`src/learning/engine.py`)** — once a week, for each of the five LLM personas (never the rules-only baseline), it gathers that persona's recently-closed trades, builds a prompt describing exactly what happened, and asks the real LLM to propose a small number of new rules ("SEEK" rules to look for, "AVOID" rules to steer clear of). It checks each proposed rule makes sense before saving it.
3. **Richer post-mortems (`src/learning/forensics.py`, extended)** — the existing classifier (already working since Week 2) now also records a handful of extra numbers for every closed trade (how far it ran against you, how far it ran in your favor, how much profit was given back, etc.) and some extra descriptive tags, plus a second pass that looks at what happened to the stock **after** the agent sold, since that can't be known at the moment of closing.

Everything above is wired into the nightly/weekly scheduler (`scheduler.py`), with no change to any job's existing timing.

---

## 2. Database changes (migrations 0005, 0006, 0007)

All three are additive only — nothing in the existing schema changed, and `db/schema.sql` itself was not touched (it stays frozen as migration 0001; every change since Day 1 has gone through a new numbered migration file, and this week kept that rule).

| Migration | What it adds | Why |
|---|---|---|
| **0005** | A uniqueness rule on `heuristic_applications(heuristic_id, decision_id)` | Stops the same rule from being recorded as "fired" twice on the same decision, even if the nightly job is accidentally run twice or two copies run at once. |
| **0006** | A `purpose` column on `llm_calls` | Lets you tell apart the nightly decision calls from the weekly reflection calls when looking at the `llm_calls` table — decision calls are left blank, reflection calls are tagged `'reflection'`. |
| **0007** | Two new columns on `reflection_runs`: `last_exit_date_reviewed` and `last_position_id_in_that_exit_order` | This is the fix described in §4 below — the "bookmark" of which trades have already been reviewed had to change from "last position ID" to "last trade that closed, in the order it closed," because those two orderings aren't the same thing. The old column is kept filled in too, so nothing that only reads it breaks. |

---

## 3. New Python packages this week needs

- **`apscheduler`** — already listed in `requirements.txt`; it's what runs the nightly/weekly jobs on a schedule. If you get `ModuleNotFoundError: No module named 'apscheduler'` on a fresh machine, just `pip install -r requirements.txt`.
- **`pytest-asyncio`** — **not currently listed in `requirements.txt`**, but `pytest.ini` turns on `asyncio_mode = strict`, which needs this package to even be present or pytest's own config check fails before any test runs. If a fresh environment shows `pytest.PytestConfigWarning: Unknown config option: asyncio_mode` as a hard crash, run `pip install pytest-asyncio`. Worth adding it to `requirements.txt` properly at some point — flagging it here so Week 4 doesn't lose time on it.

---

## 4. The one tricky bug this week, explained simply

A position's database ID is handed out when it's **opened** (entered), not when it's closed. Most of the time that doesn't matter, because trades close roughly in the order they were opened. But it isn't guaranteed — a slow, long-holding persona (like Jhunjhunwala, who can hold for months) can open a trade with a low ID that doesn't close for a long time, while a fast persona opens and closes several trades with higher IDs in the meantime.

The first version of the weekly reviewer used "ID order" as its bookmark for "which trades have I already reviewed." That meant one single long-held open position — even though it hadn't closed yet — could permanently block the reviewer from ever looking at any trade that closed after it, because the reviewer would stop as soon as it hit that one still-open position in ID order.

**Fix:** the reviewer now only ever looks at trades that are actually closed, and walks them in the order they **closed** (by exit date, then ID), not the order they were opened. Open positions are simply never in the list at all — they can't block anything. The bookmark is now "the last closed trade I got past, in closing order," which is what the new migration-0007 columns store.

One more wrinkle, documented in the code and tested: if a closed trade's post-mortem classification hasn't finished yet (rare, since that normally happens instantly when a position closes), the reviewer also pauses there rather than skipping past it — otherwise that trade could become permanently unreachable once a later trade gets reviewed first. This costs a short delay in the rare case it happens, but nothing is ever silently lost.

---

## 5. The weekly reviewer's LLM settings — check these carefully

The weekly reviewer uses its **own** separate settings, not the same ones the nightly decision-maker uses:

- `REFLECTION_LLM_PROVIDER` (default: `gemini`) and `REFLECTION_LLM_MODEL` (default: `gemini-3.8-flash`)
- `REFLECTION_LLM_FALLBACK_PROVIDER` (default: `groq`) and `REFLECTION_LLM_FALLBACK_MODEL` (default: `openai/gpt-oss-120b`)

**Before Week 4 relies on this working, double-check the model names are still valid for your API keys.** Model names get deprecated or renamed by providers without warning (this has already happened once before, to the nightly decision model). If the reviewer starts failing, checking whether `REFLECTION_LLM_MODEL` / `REFLECTION_LLM_FALLBACK_MODEL` still exist on your account is the first thing to try.

---

## 6. How to run the smoke test

`scripts/smoke_test_reflection.py` is a manual script (never run automatically by the test suite) that proves the whole weekly-review loop works against the **real** LLM, using fake trade data in a **throwaway temporary database** — it never opens or touches `storage/portfolio.db`.

```bash
python -m scripts.smoke_test_reflection
```

It seeds one persona (Simons) with four fake closed trades, calls the real reviewer, and prints: the exact prompt sent, the raw LLM answer, which proposed rules passed validation and which were rejected (and why), and the resulting database rows. It never prints an API key — if no key is configured it exits cleanly and names only the missing setting, never a value.

---

## 7. Known limits — read before trusting this in production

1. **The weekly loop has not yet produced a real result.** The one real run made so far hit external failures on *both* providers, not a bug in our code:
   - Gemini returned `503 UNAVAILABLE` ("This model is currently experiencing high demand... try again later") — described by Google as usually temporary.
   - The Groq fallback then returned `403 Access denied. Please check your network settings.` — that specific wording points to a network/firewall restriction on the machine it was run from, not a bad API key (a bad key gives a different error, 401).
   The script itself handled this correctly (logged the failure, wrote nothing, didn't crash), but **nobody has yet seen what heuristics the real LLM actually proposes.** Rerunning the smoke test — ideally from a different network, or just retrying since the Gemini error is transient — should be the first thing done before relying on this.
2. **No real trades have closed yet** in the live `storage/portfolio.db` through this new code. Everything described above is proven in tests and in the one (failed) smoke-test attempt, not against real trading history. `agent_memory` and `heuristic_applications` are empty in the real database.
3. **The same-day-candle issue** (found in Week 1): Upstox doesn't publish the current trading day's daily candle by the time the evening ingestion job runs. This is already guarded against (`features/builder.py`'s `check_data_freshness`, a 5% staleness tolerance before a run is refused) — just noting it's still a live constraint, not something Week 3 changed.
4. **`BROAD_MARKET_DRAG` still uses a VIX-level proxy, not real Nifty 50 data, even though real Nifty trend data now exists.** When this classifier was first written, `macro_daily.nifty50_trend`/`nifty500_trend` were always empty, so it approximated "the whole market was falling" with "VIX was elevated for most of the trade." Since Week 2, `sync_macro.py` actually computes real `nifty50_trend`/`nifty500_trend` values — but `forensics.py`'s `BROAD_MARKET_DRAG` check (and its own code comment) was never updated to use them. This is a real, fixable gap, not a bug — just flagging it as unfinished cleanup.

---

## 8. What's ready for Week 4

Per `docs/Plan_v3.md`, Week 4 is the FastAPI + dashboard layer. The route files already exist as empty stubs matching the plan exactly:

```
src/api/routes/leaderboard.py   # GET /api/leaderboard
src/api/routes/portfolio.py     # GET /api/agents/{id}/portfolio
src/api/routes/activity.py      # GET /api/agents/{id}/activity
src/api/routes/baseline.py      # GET /api/compare/baseline
src/api/routes/memory.py        # GET /api/agents/{id}/memory   <- this is the one Week 3's
                                 #    work actually feeds, once the loop has run for real
src/api/routes/health.py        # GET /api/health
```

`memory.py` is the endpoint most directly built by this week's work — it would read `agent_memory` (the heuristics, their status/confidence/times-triggered/times-successful) and `heuristic_applications` (fired/resolved/outcome). Both tables are empty in the real database right now (see §7.2), so whoever builds this endpoint should either rerun the smoke test to get a few real rows to develop against, or seed fake rows the way `scripts/smoke_test_reflection.py` does.

Two other Week-3-adjacent pieces that `docs/Plan_v3.md` also lists under "Week 3" were **not** built this time and are still empty stubs: `src/evaluation/performance.py` (Sharpe ratio, drawdown, alpha) and `src/evaluation/comparison.py` (LLM-vs-baseline-vs-Nifty paired comparison). These will matter for the dashboard's comparison page eventually, but don't block the API/dashboard skeleton itself.

---

## 9. Command cheat-sheet

```bash
# Full test suite (should show 376 passing)
pytest tests/ -q

# This week's test files only
pytest tests/unit/test_heuristic_triggers.py tests/unit/test_reflection_engine.py tests/unit/test_forensics_extended.py tests/unit/test_scheduler_jobs.py -q

# Manual smoke test against the REAL configured LLM (temp database only, 1-3 real calls)
python -m scripts.smoke_test_reflection

# Start the scheduler daemon (includes the new jobs: Mon-Fri 22:30 and Sun 10:00)
python scheduler.py
```

---

*Branch `week3-learning`, pushed to `origin` as a backup copy. Not merged into `v2-ATA` or `main`. `storage/portfolio.db` is untouched by any of this week's work.*
