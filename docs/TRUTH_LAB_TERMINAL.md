# Strategy Truth Lab + Live Terminal

Two product surfaces in the GOLD MONOLITH terminal look. Frontend only; every
number on the Live Terminal is a mock, and the six Truth Lab verdicts are real
results from the research lab, served verbatim.

| Route | What it is |
|---|---|
| `/lab` | Strategy Truth Lab, "the anti-overfitting backtester" |
| `/terminal` | Live Terminal: validated signals with their record |

## What the product claims, and what it does not

- The tests are rule-based Python. A language model only turns the trader's
  words into rules, and the trader confirms those rules before anything runs.
- A verdict is a measured result on past data. Failures are shown.
- The big-move panel is timing only. Nothing on either page forecasts direction.
- Footer on both pages: "Information, not advice."

## Truth Lab flow

1. **Describe** - free text.
2. **Confirm** - the exact rules as understood, one per line, plus everything
   that had to be assumed. The trader can edit, remove or add rules. Nothing is
   tested until they confirm.
3. **Sealed test** - rules frozen; variants picked on the early years only; the
   later years opened once; luck correction; direction check.
4. **Verdict** - `PASS`, `NEAR MISS`, `REAL BUT NOT TRADABLE` or `FAILED`, each
   with its own icon and its label in words, the measured headline, and a
   plain-English "why".

Deep links: `/lab?example=<id>` opens a stored verdict;
`/lab?example=<id>&step=rules` opens the confirmation step.
Ids: `noise-area-ustec`, `amd`, `macd-ema200`, `friday-low`, `overnight-range`,
`crowd-fade`.

## API contract

Types and the client live in `frontend/lib/terminal-api.ts`. The backend
implements these under `/api/v1`:

| Method | Path | Request | Response |
|---|---|---|---|
| POST | `/lab/parse` | `{ text }` | `{ name, rules[], assumptions[] }` |
| POST | `/lab/run` | `{ rules[], asked?, name? }` | `{ job_id }` |
| GET | `/lab/{id}` | | `{ job_id, status, stages[], verdict, message? }` |
| GET | `/lab/library` | | `{ examples[] }` (addition) |
| GET | `/terminal/noise-bands?symbol=USTEC\|US500` | | bands, price, VWAP, events, state |
| GET | `/terminal/activity-windows` | | 30-minute slots + named windows, no direction |
| GET | `/terminal/signals` | | validated signals with tested and live record |
| GET | `/terminal/positioning` | | BTC / ETH long-short ratio, z vs 90 days |
| GET | `/terminal/odds` | | prediction-market odds, 7-day change |
| GET | `/terminal/calendar` | | today's events (addition) |

Notes for the backend:

- `rules[]` items are `{ id, text }`. `/lab/run` must test exactly the texts it
  receives.
- Job `status`: `queued`, `running`, `done`, `unavailable`, `error`.
  `stages[]` reports the five steps (`freeze`, `select`, `sealed`, `luck`,
  `direction`), each `pending`, `running` or `done`.
- Register `/lab/library` before `/lab/{id}` so the static path wins.
- Every terminal response carries `is_mock`, `source` and `as_of`. Send
  `is_mock: false` from the real service.
- Two endpoints were added to the original list: `/lab/library` (the library
  needs a source) and `/terminal/calendar` (the calendar strip).

### Switching from mocks to the backend

Set `NEXT_PUBLIC_TERMINAL_API_BASE` to the backend prefix, for example
`/api/be/api/v1` to go through the existing same-origin proxy. Default is
`/api/mock`.

## What is mocked

| Thing | Where | Status |
|---|---|---|
| Six verdicts | `frontend/lib/mock/truth_lab_examples.json` | REAL results, copied verbatim |
| Parser | `mockParse` in `frontend/lib/mock/lab.ts` | keyword match to the six; otherwise splits the sentence into clauses |
| Per-strategy "assumed" lines | `ASSUMPTIONS` in `lab.ts` | written by hand from each strategy's rules |
| Test run | `mockRun`, `mockJob` | no engine: returns the stored verdict only when the confirmed rules equal the tested ones, otherwise `unavailable` |
| Noise bands, price, VWAP | `mockNoiseBands` in `frontend/lib/mock/terminal.ts` | invented, seeded; position state derived from them with the real rule set |
| Big-move windows, calendar, odds, positioning | `terminal.ts` | invented |
| Signal live records | `mockSignals` | invented, not real track records |

The mock session is frozen at 13:40 New York. Both pages show a "Demo data"
tag in the status bar.

## Design

GOLD MONOLITH (owner's choice, 2026-11-14). The existing tokens in
`frontend/app/globals.css` are re-pointed inside a `.monolith` wrapper, so the
rest of the app is untouched.

- Gold `#E6A532`, near-black `#050505`, panels `#0F0F0F`.
- Manrope for text, JetBrains Mono with tabular digits for every number. Both
  are loaded with `next/font` for these two routes only.
- Scanlines at the reference strength, hairline dividers, no card gaps, square
  corners.
- Two colours were lifted for contrast: muted text `#8F8F8F` (was `#888888`)
  and negative `#D85A5A` (was `#CC4444`, 4.35:1 as text).
- Grids are sized to their item count: the library is 3 x 2, 2 x 3 or 1 x 6;
  the calendar is 6 x 1, 3 x 2, 2 x 3 or 1 x 6.

## Preview

```
cd frontend
npm ci
npm run dev -- -p 3111
```

Then open `http://localhost:3111/lab` and `http://localhost:3111/terminal`.
No backend is needed for these two pages.

Screenshots at 390, 1366 and 1920 px are in `design-shots/`.
