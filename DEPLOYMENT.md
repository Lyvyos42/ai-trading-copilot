# Deployment Guide — 100% Free Stack

## Architecture (all free, no credit card required)

| Layer | Service | Cost |
|-------|---------|------|
| Frontend | Vercel | Free |
| Backend API | Render.com | Free (750 h/mo) |
| Database | Neon.tech | Free (0.5 GB PostgreSQL) |
| Market Data | Yahoo Finance (yfinance) | Free — no key needed |
| AI Agents | Anthropic Claude | Pay-per-use (your key) |

---

## Step 1 — Database on Neon.tech

1. Go to **https://neon.tech** → Sign Up (GitHub login works)
2. Create a new project → name it `trading-copilot`
3. After creation, click **Connection Details** and copy the **psql** connection string:
   ```
   postgresql://user:pass@ep-xxx.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```
4. Change the prefix to `postgresql+asyncpg://` (needed for the async Python driver):
   ```
   postgresql+asyncpg://user:pass@ep-xxx.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```
5. Save this URL — you'll need it in Step 2.

> Tables are auto-created on first startup (the lifespan handler runs `Base.metadata.create_all`).

---

## Step 2 — Backend on Render.com

1. Go to **https://render.com** → Sign Up (GitHub login works)
2. Click **New → Web Service**
3. Connect your GitHub repo (push the `ai-trading-copilot/` folder to a GitHub repo first)
4. Configure:
   - **Name**: `ai-trading-copilot-api`
   - **Root Directory**: `backend`
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Plan**: Free
5. Under **Environment Variables**, add:

   | Key | Value |
   |-----|-------|
   | `DATABASE_URL` | Your Neon connection string from Step 1 |
   | `ANTHROPIC_API_KEY` | `sk-ant-api03-fhBXeAf8...` (your key) |
   | `JWT_SECRET` | Run `python -c "import secrets; print(secrets.token_hex(32))"` locally and paste the output |
   | `ALLOWED_ORIGINS` | `https://neural-edge-website.vercel.app` (your Vercel URL) |
   | `ENVIRONMENT` | `production` |

6. Click **Create Web Service** — Render will build and deploy.
7. Once live, your backend URL will be:
   ```
   https://ai-trading-copilot-api.onrender.com
   ```

---

## Step 3 — Frontend on Vercel (neural-edge-website)

1. Go to your Vercel project: **Settings → Environment Variables**
   (https://vercel.com/cantorlivmarian-1859s-projects/neural-edge-website/settings/environment-variables)

2. Add these two variables (set for **Production** environment):

   | Key | Value |
   |-----|-------|
   | `NEXT_PUBLIC_API_URL` | `https://ai-trading-copilot-api.onrender.com` |
   | `NEXT_PUBLIC_WS_URL` | `wss://ai-trading-copilot-api.onrender.com` |

3. Push the `frontend/` folder to GitHub (same repo, or a new one).
4. In Vercel, connect the repo and set **Root Directory** to `frontend`.
5. Click **Deploy**.

---

## Step 4 — Push code to GitHub

If you don't have a GitHub repo yet:

```bash
cd C:\Users\Liv\ai-trading-copilot
git init
git add .
git commit -m "Initial commit — AI Trading Copilot"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/ai-trading-copilot.git
git push -u origin main
```

Then connect the repo to both Render and Vercel.

---

## Demo login (auto-seeded on first start)

```
Email:    demo@tradingcopilot.ai
Password: demo1234
Tier:     pro
```

---

## Free tier limits to be aware of

- **Render free**: Service sleeps after 15 min of inactivity. First request after sleep takes ~30 s to wake up. This is fine for demos; upgrade to Starter ($7/mo) for always-on.
- **Neon free**: 0.5 GB storage, 190 compute hours/month. More than enough for this app.
- **Vercel free**: Unlimited deployments for personal/hobby projects.
- **Anthropic**: You pay per token. Each signal generation costs roughly $0.002–$0.01 with Claude Sonnet. Claude Opus (used by the Trader agent) costs ~5× more — switch it to Sonnet in `backend/app/agents/trader.py` if you want to minimize costs.
