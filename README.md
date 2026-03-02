# TaskFlow

A distributed task scheduling system built with Python, Redis, and Docker. Submit jobs via REST API or the live web dashboard, and a pool of worker nodes picks them up, processes them, and reports back — with automatic retries, a dead letter queue, and Prometheus metrics built in.

**Live demo:** [taskflow-api-moiz.fly.dev](https://taskflow-api-moiz.fly.dev)

---

## What it does

- **Priority queue** — tasks run highest-priority first, FIFO within the same priority
- **Multi-worker** — multiple worker nodes pull from the queue independently, no coordination needed
- **Auto-retry + DLQ** — failed tasks retry up to 3 times automatically, then land in a dead letter queue where you can inspect and replay them
- **Timeout recovery** — tasks that stall get reclaimed and re-queued
- **Prometheus metrics** at `/metrics` — queue depth, throughput, task duration histogram
- **Web dashboard** — submit tasks, watch them process in real time, inspect results, manage the DLQ
- **API key authentication** — write endpoints require a bearer token; key stored as an env secret, never in code
- **Rate limiting** — per-IP limits backed by Redis (survives restarts); 30 submissions/min, returns JSON 429 on breach
- **Payload validation** — size cap (32KB), field count limit, priority range enforcement

---

## Architecture

```
Client / Dashboard
       │
       ▼ HTTP REST
┌─────────────────┐
│   Flask API     │  ← /tasks, /stats, /metrics, /tasks/dead
└────────┬────────┘
         │ Redis protocol
         ▼
┌─────────────────┐
│  Redis Queue    │  ← sorted set (priority + FIFO score)
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌────────┐ ┌────────┐  ← N worker nodes (scale with docker-compose --scale)
│ Worker │ │ Worker │
└────────┘ └────────┘
```

---

## Running locally

**Prerequisites:** Docker, Docker Compose

```bash
git clone https://github.com/ziowm/TaskFlow.git
cd TaskFlow
docker-compose up
```

This starts Redis, the API on `http://localhost:8080`, and 3 worker replicas. Open `http://localhost:8080` for the dashboard.

Scale workers up or down:
```bash
docker-compose up --scale worker=10
```

---

## Security

### Authentication
Write endpoints require an API key passed as a bearer token:

```bash
Authorization: Bearer <your-api-key>
```

Read endpoints (`GET /tasks/:id`, `/stats`, `/health`, `/metrics`) are public. The dashboard handles auth automatically — the key is injected server-side and never exposed in HTML source.

Set the key via environment variable:
```bash
export API_KEY=your-secret-key           # local
flyctl secrets set API_KEY=your-key      # Fly.io
```

### Rate limits (per IP, stored in Redis)

| Endpoint | Limit |
|----------|-------|
| `POST /tasks` | 30/min, 5/sec |
| `POST /tasks/:id/retry` | 20/min |
| `GET /tasks/:id` | 120/min |
| `GET /tasks/dead` | 60/min |

Exceeding a limit returns `429 Too Many Requests` with a JSON error body.

### Other protections
- **Payload size cap** — requests over 32KB are rejected with 413
- **Field count limit** — payloads with more than 20 fields are rejected
- **Priority range enforcement** — priority must be 0–100
- **Structured request logging** — every write attempt logs IP, method, path, and status code

---

## API

### Submit a task
```bash
curl -X POST http://localhost:8080/tasks \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your-api-key>" \
  -d '{"payload": {"task_type": "math", "operation": "add", "a": 5, "b": 3}, "priority": 5}'
```

### Check task status
```bash
curl http://localhost:8080/tasks/<task_id>
```

### List dead letter queue
```bash
curl http://localhost:8080/tasks/dead
```

### Replay a dead task
```bash
curl -X POST http://localhost:8080/tasks/<task_id>/retry \
  -H "Authorization: Bearer <your-api-key>"
```

### Live stats
```bash
curl http://localhost:8080/stats
```

### Prometheus metrics
```bash
curl http://localhost:8080/metrics
```

---

## Task types

| Type | Required fields | What it does |
|------|----------------|--------------|
| `math` | `operation`, `a`, `b` | add / subtract / multiply / divide / power / modulo / sqrt |
| `fibonacci` | `n` | Returns first n Fibonacci numbers (max 500) |
| `prime_check` | `n` | Checks primality, returns prime factors if composite |
| `matrix_multiply` | `a`, `b` | Multiplies two matrices (max 20×20) |
| `data_processing` | `data`, `operation` | sum / average / max / min / median / std / range on a number list |
| `sort` | `data`, `algorithm` | Sorts a list via `bubble`, `merge`, or `quick` — reports comparison count |
| `text_processing` | `text`, `operation` | uppercase / lowercase / reverse / word_count / word_frequency / palindrome_check / caesar_cipher |
| `send_email` | `to`, `subject`, `body` | Simulated email send — returns a fake message ID |
| `resize_image` | `filename`, `width`, `height` | Simulated image resize — returns dimensions and estimated file size |
| `generate_report` | `report_type`, `period` | Generates fake analytics report (sales / traffic / performance / inventory) |
| `random_fail` | `fail_rate` | Fails randomly at the given rate (0.0–1.0). Good for testing DLQ. |
| `slow_task` | `duration_seconds` | Sleeps for N seconds. Good for testing the timeout monitor. |
| `error_demo` | `error_type` | Triggers specific errors on demand for testing |

---

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | `redis://localhost:6379` | Redis connection string |
| `API_PORT` | `8080` | API server port |
| `API_KEY` | *(empty — auth disabled)* | Bearer token required on write endpoints |
| `MAX_BODY_KB` | `32` | Max request body size in KB |
| `POLL_INTERVAL` | `1` | Seconds between worker polls |
| `TASK_TIMEOUT` | `300` | Seconds before a stalled task is reclaimed |
| `LOG_LEVEL` | `INFO` | DEBUG / INFO / WARNING / ERROR |

---

## Project structure

```
TaskFlow/
├── api/
│   ├── server.py          # Flask REST API + dashboard route
│   └── templates/
│       └── dashboard.html # Web dashboard
├── worker/
│   ├── main.py            # Worker polling loop
│   ├── task_handlers.py   # All task type implementations
│   └── timeout_monitor.py # Reclaims stalled tasks
├── shared/
│   ├── models.py          # Task dataclass + Redis serialization
│   ├── redis_client.py    # Redis connection wrapper
│   └── metrics.py         # Prometheus metric definitions
├── tests/
├── docker-compose.yml
├── fly.api.toml           # Fly.io config for API
└── fly.worker.toml        # Fly.io config for worker
```

---

## Built with

Python · Flask · Redis · Docker · Prometheus · Fly.io
