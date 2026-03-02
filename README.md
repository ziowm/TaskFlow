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

## API

### Submit a task
```bash
curl -X POST http://localhost:8080/tasks \
  -H "Content-Type: application/json" \
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
curl -X POST http://localhost:8080/tasks/<task_id>/retry
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
