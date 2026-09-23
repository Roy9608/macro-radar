# AGENTS.md — deployment contract for AI agents (and humans in a hurry)

If you are an AI agent asked to "set up this repo locally", this file is the contract.
Everything here has been executed and verified; the expected outputs are real.
Where the repository does not state something, this file says so instead of guessing.

## 0. What this repo is (one paragraph)

A macro-event sentinel: it turns Fed events (FOMC / CPI / NFP / PCE) into card-style
briefs and delivers them (email first; PushPlus optional in China).
It has two halves — a **research leg** (an AI agent that reads public sources under
five hard rules, see `docs/03`) and a **delivery leg** (templates + a script,
deterministic). This repo contains the delivery leg plus the method; the research leg
is described, not shipped, because it needs a live agent.
One sentence governs every design decision in it: **research may be fuzzy, delivery
must be exact.**

Where the pieces live:

```
README.md / README.zh-CN.md   the two entry points (both complete on their own)
demo/render_card.py          fixture JSON -> card HTML (stdlib only; zh/en; red-up/green-up)
demo/fixtures/daily-{en,zh}.json   the two fixtures the demo renders
demo/output/*.html           rendered cards — the README labels these "git-visible results"
templates/                   the design system: card (shared) / daily / t1 / weekly
scripts/send.py              delivery: SMTP + PushPlus + subscriber CSV, with --dry-run
tools/tz_convert.py          timezone conversion, schedule-fit check, calendar integrity
tools/build_calendar.py      event-calendar builder
data/                        calendar.json, fedwatch_history.json, subscribers.example.csv
                             (the shipped example code consumes only calendar.json; the research
                             leg appends fedwatch_history.json, and only the weekly report reads it)
config/smtp.example.json     SMTP config template (the real config/smtp.json is never committed;
                             .gitignore also covers data/subscribers.csv and config/alerts.json)
samples/                     four real production cards (2026-09), not mockups
assets/                      the two README card images; assets/README.md states they were drawn
                             from the same fixtures (not browser screenshots), are not guaranteed
                             pixel-identical to the HTML, and must be regenerated whenever the
                             card style changes
docs/                        01 architecture · 02 design system · 03 research discipline · 04 delivery
```

## 1. Prove it runs (no network, no keys) — 2 commands

```bash
python demo/render_card.py --all
python scripts/send.py --html demo/output/daily-en.html --dry-run
```

Expected (the recorded run of 2026-09; the byte counts come from the fixtures):

```
daily-en.json  ->  demo/output/daily-en.html  (7038 bytes, locale=en)
daily-zh.json  ->  demo/output/daily-zh.html  (7092 bytes, locale=zh)
{"ok": true, "dry_run": true, "html_bytes": 7038, "push_targets": 0, "mail_targets": 0, "note": "dry-run：未发送任何消息"}
```

Python 3.8+ / standard library only. No install, no build, no virtualenv needed.

Confirm the run by the **traces** — the two cards are written and the dry-run object prints
`ok: true`; §4 states the criterion in full. The byte counts are fixture-dependent —
if a fixture or a template is edited they change, and stale numbers in any document are a defect
(§5, last row). The first command writes into `demo/output/`, which the README calls git-visible
results: do not leave unrelated edits there.

**Stop here if the user only asked to "look at it".**

Not stated in this repository — do not assert any of it:
- whether `scripts/send.py` can return exit code 0 with zero matched recipients;
- the dry-run object for the Chinese card (the recorded run above used the English one);
- anything about the live system's real configuration, subscriber list, schedule, or host
  beyond the defaults the README names.

## 2. Ask the user these 5 things before going further

Do not guess. Each one changes behaviour:

| # | Question | Why it matters | Default if they don't care |
|---|---|---|---|
| 1 | Your timezone (UTC offset, e.g. `8`, `-4`, `5.5`)? | Event times and product schedules are timezone-bound | ask again; never assume Beijing |
| 2 | Up-colour convention: **red-up** or **green-up**? | East Asia (China incl. HK/Macao/Taiwan, Japan, Korea) uses red-up; US/Europe uses green-up. Opposite meanings on the same card is a real hazard | by locale: `zh` → red-up, `en` → green-up (this is what `color_convention: auto` does) |
| 3 | Delivery channel: email (SMTP) or WeChat (PushPlus)? | Email is the portable default; PushPlus needs a Chinese account + real-name verification and helps only inside mainland China. A webhook channel is a documented do-it-yourself extension, not shipped | email |
| 4 | Which local hours should the briefs fire? | Beijing 07:00 is 19:00 in New York and midnight in London — the same schedule is not equally usable everywhere | none — run the schedule-fit check in §3 and propose the flagged fixes |
| 5 | Who are the subscribers — and which channels does each get? | Never invent recipients; `channels` is a per-row column, so the list is really per-product, not one global list | leave the example CSV in place; do not send anything |

Never invent the user's timezone, colour convention, channel, sending hours, or subscriber list. Ask.

## 3. Localise (timezone / colours / schedule)

```bash
python tools/tz_convert.py --verify                      # calendar integrity: 105/105 consistent
python tools/tz_convert.py --utc-offset -4 --events      # upcoming events in the user's clock
python tools/tz_convert.py --utc-offset 1  --plan        # schedule fit: flags 00:00/02:00, suggests fixes
```

`105/105` describes the shipped `data/calendar.json` — once you edit that file, that number
has to be recomputed, not quoted. Every event keeps both `date_et` and `date_bj` plus an
`EST`/`EDT` marker, and `--verify` reconciles the pair — so a DST change needs no manual
editing, only a re-run.

The fit check's criterion is the user's own clock: **local 07:00–22:00 passes, anything else is
flagged**. `--iana` additionally wants a tz database (`pip install tzdata`); without one, use
`--utc-offset`.

- **Colours** live in the fixture: `"color_convention": "auto" | "cn" | "west"`.
  `auto` = red-up for `locale: zh`, green-up for `locale: en`.
- **Timezone label** lives in the fixture: `"timezone_label": "UTC-4 · New York"` — it is
  rendered into the card header so readers always know which clock they are on.
- **Schedules** are set in the host scheduler (cron / Task Scheduler / platform automations),
  in the user's *local* time. No code change is needed — see `docs/04`.
- **Three products get schedule entries; the flash does not.** The daily / T-1 / weekly briefs
  are cron-shaped, but the data flash is anchored to "release time + 30 min" and fired
  dynamically on CPI/NFP/PCE days, because any hard-coded local time for it breaks at a DST
  change. Do not add a flash entry to the scheduler.

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

A CSV is not needed for a one-off: `--mail <recipient>` and/or `--push <token>` address
recipients named on the command line, which is how `docs/04` §6 step ⑤ proves the mail leg
(have the user send one message to themselves first). `config/smtp.json` sits at
`<repo>/config/smtp.json` — resolved from `send.py`'s own location, so the scheduler's working
directory does not matter. `auth_code` is the provider's **app password / authorisation code,
not the account's login password** (`docs/04` §2.1).

`docs/04` §6 gives the acceptance for a system that is *landed*: one real message arrives in
the user's own inbox. Everything past that is only wiring up the schedule.

Success looks like `{"ok": true, "results": ["邮件 OK -> user@example.com"]}`.
**The criterion is the trace — the printed `ok: true` plus the per-target `results` — not the exit
code taken on its own, and not "the screen looked right".** A wrapper that returns 0 while nothing
was delivered is a documented failure in this author's `live-trading-bot-reliability`.

## 5. Failure modes → meaning

| Symptom | Meaning | Action |
|---|---|---|
| `缺少 SMTP 配置: ...` + exit 1 | `config/smtp.json` absent | copy the example and fill it; the message names the exact path |
| `找不到订阅名单: ...` + exit 1 | `--subscribers` path wrong | check the path; the example CSV is `data/subscribers.example.csv` |
| `subscribers.matched` is lower than expected | a row is `disabled`, missing the channel in `channels`, or has an empty `channels` cell | inspect the CSV; blank channels = opted out |
| PushPlus `code=905` | account not real-name verified | user completes verification; do not retry in a loop |
| PushPlus token rejected / `code!=200` | token wrong or expired | tokens are passed via `--push` or the CSV — never written into a file that can be committed |
| `ZoneInfoNotFoundError` | no IANA tz database (common on Windows) | use `--utc-offset`, or `pip install tzdata` |
| `邮件 ERROR (<recipient>): <provider text>` | auth code wrong / not an app password | regenerate the app password at the mail provider |
| The flash lands at the wrong hour (or twice) around a DST change | The flash was given a fixed local time | Remove the flash entry from the scheduler — it is anchored to the release and fired dynamically (§3) |
| The same figure changes between two renders of one event | That bar or release had not closed / been published yet | Render only from closed / published data |
| The job works by hand but fails from the scheduler | The scheduler's working directory is not the repo root | Start the schedule entry with `cd <repo> &&`, as the shipped cron examples do |
| One subscriber gets the same event twice | Two product lines both claimed it | Do not widen a product's scope to cover the gap (§6, rule 2) |
| Card bytes differ from this file by a few hundred | fixtures were edited (colours/TZ label change size) | recompute and update the numbers — **never leave stale numbers in the README** |

## 6. Ground rules for an agent working in this repo

1. **Do not restyle templates to taste.** The design system is the product; colour semantics
   (alert/warn/good/info) are fixed and `docs/02` is the spec.
2. **Do not remove or widen the five hard rules** in `docs/03` when editing prompts —
   they are the point of the project, not boilerplate. Nor widen a product's scope: the four
   products are defined so they never overlap, which is what keeps a single event from being
   pushed twice.
3. **Silence is a valid outcome.** If there is no event, the correct behaviour is to send
   nothing — do not "fill" the schedule for the sake of activity.
4. **Numbers in README/docs must come from an actual run.** If you change a fixture, re-run
   and update every byte count you can find.
5. **Never commit credentials.** `config/smtp.json`, subscriber tokens and alert tokens stay
   local; only `*.example.*` files belong in the repo.
6. **Never write identifying data into any file here.** No subscriber identities, no email
   addresses, no server paths or hostnames, no personal names, no company names — not in
   templates, not in docs, not in commit messages. The sanitisation is published as a feature
   of this repo, so a single leaked value breaks the claim it makes.
7. **Never invent facts, numbers, commands, or file paths.** If something is needed and the
   repo does not state it, write that it is not stated here rather than producing a plausible
   value — the same standard `docs/03` applies to the research leg.
8. **Do not add prose that teaches the reader how to verify something.** Verification belongs
   in a runnable command or in `docs/`; the README stays a map. A capable agent re-derives
   method on its own — what it cannot invent is your fixtures and your commands.
9. **Keep both READMEs complete.** `README.md` and `README.zh-CN.md` must each be readable on
   their own; an English stub with the detail only in Chinese, or the reverse, is a defect.
10. **Do not overclaim.** The README has a section on what this repo does *not* claim, and a
    table naming the established projects it does not depend on. Do not turn "a deliberate
    trade-off" into "better than them", and do not add performance, coverage or reliability
    numbers that no run produced.
11. **Change each thing in exactly one place.** Styles belong to `templates/` (and the token
    table at the top of `demo/render_card.py`), subscribers to the CSV, events to
    `data/calendar.json`. Editing one value in two places — a colour in a template *and* in a
    generated report, a recipient in the CSV *and* in a prompt — is the class of bug `docs/01`
    §4 designs the repo to avoid.
