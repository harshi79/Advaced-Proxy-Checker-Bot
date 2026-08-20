# advanced proxy checker bot

A fast asynchronous Telegram proxy checker built with Python, `aiogram`, `aiohttp`, and FastAPI.

The public bot surface is intentionally small:

- `/start` opens the image-backed welcome menu.
- `/prxy` checks one line, multiple lines, or a replied text file.
- A cancel **button** is shown while a job is running; there is no public `/cancel` command.
- `/restart` is owner-only and clears queued jobs without touching active sessions.
- `GET /health` returns `{"status":"ok"}` for Render health checks.

Only working proxies are written to the result file. Dead proxies are never attached.

## supported input

The parser accepts mixed lists containing formats such as:

```text
1.2.3.4:8080
http://1.2.3.4:8080
https://1.2.3.4:443
socks4://1.2.3.4:1080
socks5://1.2.3.4:1080
username:password@1.2.3.4:8080
1.2.3.4:8080:username:password
[2001:db8::10]:8080
```

It removes blank lines, comments, malformed entries, and exact duplicates. Explicit schemes are respected. Bare `host:port` entries are probed as HTTP, SOCKS5, and SOCKS4 with bounded concurrency.

## behavior

1. A user sends `/prxy`, includes proxy lines, or replies to a text document with `/prxy`.
2. The bot downloads and parses the input before checking starts.
3. The maximum document size is **20 MB**.
4. A single progress message is updated periodically with total, checked, working, and remaining counts.
5. The cancel button deletes the progress message and stops new checks. Requests already in flight are allowed to finish, then their working results are sent as a text file.
6. Completed jobs show a summary and attach a normalized `working_proxies_<job-id>.txt` file.

Checking is bounded by a global semaphore, per-request timeout, and retry count so several large jobs cannot create an unbounded number of connections.

## local setup

Python 3.11 or newer is recommended.

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# put the BotFather token in .env
uvicorn app.main:app --host 0.0.0.0 --port 10000
```

Without `RENDER_EXTERNAL_URL` or `WEBHOOK_URL`, the app uses Telegram long polling. With either value, it uses webhook mode at `/telegram/webhook`.

The default check endpoint is `https://api.ipify.org?format=json`. It can be replaced with a stable endpoint suitable for your authorized proxy inventory. `HEADER_ECHO_URL` is optional; when set, the checker performs an additional header probe and records a basic transparent/anonymous/unknown classification internally.

## docker

```bash
docker build -t advanced-proxy-checker-bot .
docker run --rm -p 10000:10000 --env-file .env advanced-proxy-checker-bot
```

## render

`render.yaml` defines a free Docker web service and uses `/health` as its health check.

1. Create a Render Blueprint from this repository.
2. Set the secret `BOT_TOKEN` environment variable.
3. Render supplies `RENDER_EXTERNAL_URL`; webhook mode is enabled automatically.
4. If a custom public URL is used, set `WEBHOOK_URL` instead.

The Render free plan is a single-instance deployment. The in-process queue and bounded worker pool are designed for that shape. For multiple instances, move the queue and job state to a shared Redis/PostgreSQL service before scaling horizontally.

## configuration

See `.env.example`. Important values:

| variable | default | purpose |
| --- | ---: | --- |
| `OWNER_ID` | `7728424218` | only account allowed to run `/restart` |
| `CHECK_TIMEOUT_SECONDS` | `8` | per-attempt timeout |
| `CHECK_RETRIES` | `1` | retry count after an unsuccessful attempt |
| `CHECK_CONCURRENCY` | `100` | global concurrent proxy checks |
| `PROGRESS_UPDATE_SECONDS` | `1.2` | progress edit interval |
| `WORKER_COUNT` | `2` | queued job workers |
| `MAX_FILE_BYTES` | `20 MB` | fixed in code as requested |

Use the checker only with proxy infrastructure or lists you are authorized to test. The target URL is configured server-side rather than accepted as an arbitrary user destination.
