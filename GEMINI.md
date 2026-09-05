# AI Trading Copilot — Project Guidelines & Rules

## Core Behavioral & Quality Standards (STRICT)
1. **ZERO-EMOJI MANDATE**: Never use emojis anywhere in code, UI components, CSS, JavaScript, logs, or responses. When visual markers or iconography are needed, use clean, modern SVGs, Lucide vector icons, or precision geometric badges only.
2. **AUTONOMOUS FINISH & PERFECTION**: Never ship unfinished work, leave placeholders, or pause to ask for user opinions midway. Self-prompt, diagnose, iterate, and verify until everything works and looks visually and technically flawless.
3. **POST-TASK VERIFICATION RIGOR**: After finishing any task, systematically audit every page, check syntax, inspect runtime logs, and verify that no edge cases, files, or views were missed.

## Project Identity & Architecture

* **Name**: AI Trading Copilot Web Terminal
* **Type**: Full-Stack Multi-Agent Algorithmic Trading Platform
* **Production Deployments**:
  - Frontend: `https://app.quantneuraledge.com` (Vercel)
  - Backend: `https://ai-trading-copilot-api-xbvl.onrender.com` (Render)
* **Primary Source Directories**:
  - `frontend/`: Next.js 14.2.5 (App Router, React 18, Tailwind CSS, Lucide, TradingView charts).
  - `backend/`: FastAPI, SQLAlchemy, LangGraph, Python 3.11/3.14.

---

## Backend Engine & Agent Rules
1. **Pure Python Mode**: `python_engine_mode` is set to `True` in `backend/app/config.py`. All 9 agents (Technical, Quant, Risk, Trader, Order Flow, Macro, Regime, Correlation, Sentiment) execute pure mathematical and statistical calculations directly in Python. Never attempt blocking external LLM calls that introduce network latency.
2. **Auto-Scanner**: The batch screener endpoint is `POST /api/v1/scanner/scan-now`. It scans symbols in parallel without consuming the user's daily 2-signal AI quota. Supports both LONG and SHORT signals with confluence threshold of 60.
3. **Signal Lifecycle & Persistence**:
   - Every signal MUST have a non-null UUID (`signal_id`).
   - Active signal re-analysis MUST supersede previous active signals (`status = 'SUPERSEDED'`) rather than raising a 409 Conflict.
   - `list_signals` queries both user signals and unowned system signals (`or_(Signal.user_id == uid, Signal.user_id == None)`).
   - Any user can resolve outcomes (WIN/LOSS) for unowned signals.

---

## Frontend & UI Design Standards
Follow the `frontend-design` aesthetic principles for trading terminals:
* **Typography**: Monospace fonts (`Berkeley Mono`, `IBM Plex Mono`) for all numeric prices, pips, percentages, and metrics. Never use proportional fonts for numeric financial tables.
* **Palette**: High-contrast terminal aesthetic with cyber accents (`--bull` emerald, `--bear` crimson, `--primary` cyan).
* **Build Integrity**: Ensure `frontend/lib/supabase.ts` retains safe fallback URLs so Next.js static site generation (SSG) in `npm run build` compiles all 22 pages with zero environment mock errors.
