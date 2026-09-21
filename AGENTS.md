# AGENTS.md — deployment contract for AI agents (and humans in a hurry)

If you are an AI agent asked to "set up this repo locally", this file is the contract.
Everything here has been executed and verified; the expected outputs are real.

## 0. What this repo is (one paragraph)

A macro-event sentinel: it turns Fed events (FOMC / CPI / NFP / PCE) into card-style
briefs and delivers them (email first; PushPlus optional in China).
It has two halves — a **research leg** (an AI agent that reads public sources under
5 anti-fabrication rules, see `docs/03`) and a **delivery leg** (templates + a script,
deterministic). This repo contains the delivery leg plus the method; the research leg
is described, not shipped, because it needs a live agent.

## 1. Prove it runs (no network, no keys) — 2 commands

```bash
python demo/render_card.py --all
python scripts/send.py --html demo/output/daily-en.html --dry-run
```

Expected (verified 2026-09):

```
daily-en.json  ->  demo/output/daily-en.html  (7038 bytes, locale=en)
daily-zh.json  ->  demo/output/daily-zh.html  (7092 bytes, locale=zh)
{"ok": true, "dry_run": true, "html_bytes": 7038, "push_targets": 0, "mail_targets": 0, "note": "dry-run：未发送任何消息"}
```

If those two commands produce those outputs, the repo is healthy. **Stop here if the
user only asked to "look at it".**

Python 3.8+ / standard library only. No install, no build, no virtualenv needed.

## 2. Ask the user these 5 things before going further

Do not guess. Each one changes behaviour:

| # | Question | Why it matters | Default if they don't care |
|---|---|---|---|
| 1 | Your timezone (UTC offset, e.g. `8`, `-4`, `5.5`)? | Event times and product schedules are timezone-bound | ask again; never assume Beijing |
| 2 | Up-colour convention: **red-up** or **green-up**? | East Asia (China incl. HK/Macao/Taiwan, Japan, Korea) uses red-up; US/Europe uses green-up. Opposite meanings on the same card is a real hazard | by locale: `zh` → red-up, `en` → green-up (this is what `color_convention: auto` does) |
| 3 | Delivery channel: email (SMTP) or WeChat (PushPlus)? | Email is the portable default; PushPlus needs a Chinese account + real-name verification | email |
| 4 | Which local hours should the briefs fire? | Beijing 07:00 is 19:00 in New York and midnight in London | run `tools/tz_convert.py --utc-offset <tz> --plan` and propose the flagged fix |
| 5 | Who are the subscribers? | Never invent recipients | leave the example CSV in place; do not send anything |

## 3. Localise (timezone / colours / schedule)

```bash
python tools/tz_convert.py --verify                      # calendar integrity: 105/105 consistent
python tools/tz_convert.py --utc-offset -4 --events      # upcoming events in the user's clock
python tools/tz_convert.py --utc-offset 1  --plan        # schedule fit: flags 00:00/02:00, suggests fixes
```

- **Colours** live in the fixture: `"color_convention": "auto" | "cn" | "west"`.
  `auto` = red-up for `locale: zh`, green-up for `locale: en`.
- **Timezone label** lives in the fixture: `"timezone_label": "UTC-4 · New York"` — it is
  rendered into the card header so readers always know which clock they are on.
- **Schedules** are set in the host scheduler (cron / Task Scheduler / platform automations),
  in the user's *local* time. No code change is needed — see `docs/04`.

## 4. Wire up delivery (only if the user asks for real sending)

```bash
cp config/smtp.example.json config/smtp.json      # Windows: copy
cp data/subscribers.example.csv data/subscribers.csv
# fill in SMTP auth code + subscribers, then — dry-run first:
python scripts/send.py --html demo/output/daily-zh.html \
  --subscribers data/subscribers.csv --channel daily --dry-run
#   → {"ok": true, "dry_run": true, "push_targets": N, "mail_targets": M,
#      "subscribers": {"total": T, "enabled": E, "matched": N+M, "blank_rows_skipped": 0}}
# then for real:
python scripts/send.py --title "MacroRadar · daily" \
  --html demo/output/daily-zh.html --subscribers data/subscribers.csv --channel daily
```

Subscriber filtering (implemented in `scripts/send.py`): skip blank rows → keep `status=enabled`
→ keep rows whose `channels` contains `--channel` → a row with a `pushplus_token` goes to the
WeChat group, a row with an `email` goes to the mail group (a row with both gets both).
**An empty `channels` cell means "opted out of everything"** — never treat blank as "all".

Success looks like `{"ok": true, "results": ["邮件 OK -> user@example.com"]}` with exit code 0.
**Exit code 0 is the completion criterion** — not "the screen looked right".

## 5. Failure modes → meaning

| Symptom | Meaning | Action |
|---|---|---|
| `缺少 SMTP 配置: ...` + exit 1 | `config/smtp.json` absent | copy the example and fill it; the message names the exact path |
| `找不到订阅名单: ...` + exit 1 | `--subscribers` path wrong | check the path; the example CSV is `data/subscribers.example.csv` |
| `subscribers.matched` is lower than expected | a row is `disabled`, missing the channel in `channels`, or has an empty `channels` cell | inspect the CSV; blank channels = opted out |
| PushPlus `code=905` | account not real-name verified | user completes verification; do not retry in a loop |
| PushPlus token rejected / `code!=200` | token wrong or expired | tokens are passed via `--push` or the CSV — never written into a file that can be committed |
| `ZoneInfoNotFoundError` | no IANA tz database (common on Windows) | use `--utc-offset`, or `pip install tzdata` |
| SMTP `535` | auth code wrong / not an app password | regenerate the app password at the mail provider |
| Card bytes differ from this file by a few hundred | fixtures were edited (colours/TZ label change size) | recompute and update the numbers — **never leave stale numbers in the README** |

## 6. Ground rules for an agent working in this repo

1. **Do not restyle templates to taste.** The design system is the product; colour semantics
   (alert/warn/good/info) are fixed and `docs/02` is the spec.
2. **Do not remove the anti-fabrication rules** in `docs/03` when editing prompts — they are
   the point of the project, not boilerplate.
3. **Numbers in README/docs must come from an actual run.** If you change a fixture, re-run
   and update every byte count you can find.
4. **Never commit credentials.** `config/smtp.json`, subscriber tokens and alert tokens stay
   local; only `*.example.*` files belong in the repo.
5. **Silence is a valid outcome.** If there is no event, the correct behaviour is to send
   nothing — do not "fill" the schedule for the sake of activity.
