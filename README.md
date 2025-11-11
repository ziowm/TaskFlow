# Distributed Task Scheduler

A scalable, priority-based distributed task scheduling system built with Python Flask, Redis, and Docker. The system enables asynchronous task processing across multiple worker nodes with automatic failover and retry capabilities.

## System Architecture

The system consists of three main components:

```
┌─────────────┐
│   Clients   │
└──────┬──────┘
       │ HTTP REST API
       ▼
┌─────────────────────┐
│ Task Scheduler API  │
│   (Flask/Python)    │
└──────┬──────────────┘
       │ Redis Protocol
       ▼
┌─────────────────────┐
│   Redis Queue       │
│  (Message Broker)   │
└──────┬──────────────┘
       │ Redis Protocol
       ▼
┌─────────────────────┐
│   Worker Nodes      │
│  (Multiple Instances)│
└─────────────────────┘
```

### Components

- **Task Scheduler API**: Flask REST API for task submission and status queries
- **Redis Queue**: Message broker using sorted sets for priority-based task distribution
- **Worker Nodes**: Independent processes that retrieve and execute tasks

### Key Features

- Priority-based task scheduling (higher priority tasks processed first)
- FIFO ordering within same priority level
- Horizontal scaling by adding more worker instances
- Automatic task timeout and retry mechanism
- Graceful shutdown handling
- Docker containerization for easy deployment

## Setup and Installation

### Prerequisites

- Docker and Docker Compose
- Python 3.11+ (for local development)

### Quick Start with Docker

1. Clone the repository:
```bash
git clone <repository-url>
cd distributed-task-scheduler
```

2. Start the system:
```bash
docker-compose up
```

This will start:
- Redis on port 6379
- Task Scheduler API on port 5000
- 3 Worker nodes (default configuration)

3. Verify the system is running:
```bash
curl http://localhost:5000/health
```

Expected response:
```json
{
  "status": "healthy",
  "redis_connected": true
}
```

### Local Development Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Start Redis:
```bash
docker run -d -p 6379:6379 redis:7-alpine
```

3. Start the API:
```bash
export REDIS_URL=redis://localhost:6379
python -m api.server
```

4. Start a worker (in a separate terminal):
```bash
export REDIS_URL=redis://localhost:6379
python -m worker.main
```

## Usage Examples

### Submitting Tasks

#### Example 1: Math Operation Task

```bash
curl -X POST http://localhost:5000/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "payload": {
      "task_type": "math",
      "operation": "add",
      "a": 10,
      "b": 5
    },
    "priority": 5
  }'
```

Response:
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending"
}
```

#### Example 2: Data Processing Task

```bash
curl -X POST http://localhost:5000/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "payload": {
      "task_type": "data_processing",
      "data": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
      "operation": "average"
    },
    "priority": 10
  }'
```

#### Example 3: Text Processing Task

```bash
curl -X POST http://localhost:5000/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "payload": {
      "task_type": "text_processing",
      "text": "Hello World",
      "operation": "uppercase"
    },
    "priority": 3
  }'
```

#### Example 4: Default Task Handler

```bash
curl -X POST http://localhost:5000/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "payload": {
      "message": "Custom task data",
      "user_id": 123
    },
    "priority": 1
  }'
```

### Querying Task Status

```bash
curl http://localhost:5000/tasks/{task_id}
```

Response for completed task:
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "priority": 5,
  "submitted_at": "2025-11-10T10:30:00.000000",
  "started_at": "2025-11-10T10:30:01.000000",
  "completed_at": "2025-11-10T10:30:02.000000",
  "result": "{\"operation\": \"add\", \"a\": 10, \"b\": 5, \"result\": 15, \"processed_by\": \"worker-1\"}",
  "worker_id": "worker-1"
}
```

Response for failed task:
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "failed",
  "priority": 5,
  "submitted_at": "2025-11-10T10:30:00.000000",
  "started_at": "2025-11-10T10:30:01.000000",
  "completed_at": "2025-11-10T10:30:02.000000",
  "error": "ValueError: Cannot divide by zero",
  "worker_id": "worker-1"
}
```

## Environment Variables

### Task Scheduler API

| Variable | Description | Default |
|----------|-------------|---------|
| `REDIS_URL` | Redis connection string | `redis://localhost:6379` |
| `API_PORT` | Port to bind the API server | `5000` |
| `LOG_LEVEL` | Logging verbosity (DEBUG, INFO, WARNING, ERROR) | `INFO` |

### Worker Node

| Variable | Description | Default |
|----------|-------------|---------|
| `REDIS_URL` | Redis connection string | `redis://localhost:6379` |
| `WORKER_ID` | Unique worker identifier | System hostname |
| `POLL_INTERVAL` | Seconds between task polls | `1` |
| `TASK_TIMEOUT` | Max seconds for task execution | `300` |
| `MONITOR_INTERVAL` | Seconds between timeout checks | `10` |
| `LOG_LEVEL` | Logging verbosity (DEBUG, INFO, WARNING, ERROR) | `INFO` |

## Scaling Workers

### Using Docker Compose

Scale to 5 workers:
```bash
docker-compose up --scale worker=5
```

Scale to 10 workers:
```bash
docker-compose up --scale worker=10
```

### Manual Scaling

Start additional worker containers:
```bash
docker run -e REDIS_URL=redis://redis:6379 \
  -e WORKER_ID=worker-custom-1 \
  --network distributed-task-scheduler_default \
  distributed-task-scheduler-worker
```

## Task Handler Development

### Creating Custom Task Handlers

Task handlers are functions that process task payloads. See `worker/task_handlers.py` for examples.

Basic handler structure:
```python
def execute_custom_task(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Custom task handler
    
    Args:
        payload: Task data from client
        
    Returns:
        Result dictionary to store in Redis
        
    Raises:
        Exception: Any error during execution
    """
    # Validate payload
    if 'required_field' not in payload:
        raise ValueError("Missing required field")
    
    # Process task
    result = process_data(payload['required_field'])
    
    # Return result
    return {
        "status": "success",
        "result": result
    }
```

### Registering Custom Handlers

1. Add your handler to `worker/task_handlers.py`
2. Import it in `worker/main.py`
3. Add routing logic in the `execute_task` method:

```python
if task_type == 'custom':
    result = execute_custom_task(payload)
```

## Priority System

Tasks are processed based on priority values:
- Higher priority values are processed first
- Priority range: any integer (typically 0-100)
- Tasks with the same priority are processed in FIFO order

Example priority usage:
- Critical alerts: priority 100
- User-facing operations: priority 50
- Background jobs: priority 10
- Cleanup tasks: priority 1

## Monitoring and Logging

### Viewing Logs

API logs:
```bash
docker-compose logs -f api
```

Worker logs:
```bash
docker-compose logs -f worker
```

All logs:
```bash
docker-compose logs -f
```

### Log Format

```
2025-11-10 10:30:00 - Worker[worker-1] - INFO - Task 550e8400 completed successfully
```

### Key Log Events

- Task submission and validation
- Task retrieval by workers
- Task execution start/completion
- Task failures with error details
- Timeout events
- Redis connection issues
- Graceful shutdown events

## Troubleshooting

### API Returns 503 Service Unavailable

**Cause**: Cannot connect to Redis

**Solution**:
1. Check Redis is running: `docker-compose ps redis`
2. Verify Redis health: `docker-compose exec redis redis-cli ping`
3. Check Redis URL configuration in API container

### Tasks Not Being Processed

**Cause**: No workers running or workers cannot connect to Redis

**Solution**:
1. Check worker status: `docker-compose ps worker`
2. View worker logs: `docker-compose logs worker`
3. Verify Redis connectivity from worker
4. Ensure workers are polling (check logs for "Retrieved task" messages)

### Task Stuck in Processing Status

**Cause**: Worker crashed or task exceeded timeout

**Solution**:
- Tasks automatically retry after timeout period (default 300 seconds)
- Check worker logs for crash information
- Verify timeout monitor is running
- Adjust `TASK_TIMEOUT` if tasks legitimately need more time

### High Task Latency

**Cause**: Insufficient worker capacity

**Solution**:
1. Scale up workers: `docker-compose up --scale worker=10`
2. Monitor worker logs to verify they're processing tasks
3. Check Redis performance with `redis-cli INFO stats`

### Worker Exits Immediately

**Cause**: Configuration error or Redis connection failure

**Solution**:
1. Check worker logs: `docker-compose logs worker`
2. Verify `REDIS_URL` environment variable
3. Ensure Redis is accessible from worker container
4. Check for Python dependency issues

### Tasks Failing with Validation Errors

**Cause**: Invalid payload format

**Solution**:
1. Review task handler requirements in `worker/task_handlers.py`
2. Ensure payload includes required fields
3. Check data types match handler expectations
4. Review failed task error message: `curl http://localhost:5000/tasks/{task_id}`

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test file
pytest tests/test_priority_distribution.py
```

### Manual Testing

1. Submit multiple tasks with different priorities
2. Verify high-priority tasks are processed first
3. Test task failure scenarios
4. Test worker scaling
5. Test graceful shutdown

## Production Deployment

### Recommendations

1. **Redis Persistence**: Enable AOF or RDB persistence
   ```yaml
   redis:
     command: redis-server --appendonly yes
   ```

2. **Resource Limits**: Set memory and CPU limits
   ```yaml
   worker:
     deploy:
       resources:
         limits:
           cpus: '1'
           memory: 512M
   ```

3. **Health Checks**: Configure container health checks
4. **Monitoring**: Integrate with Prometheus/Grafana
5. **Log Aggregation**: Use ELK stack or similar
6. **Reverse Proxy**: Use nginx for API
7. **TLS**: Enable HTTPS for API endpoints
8. **Authentication**: Add API authentication/authorization

### Security Considerations

- Validate all task payloads
- Implement rate limiting on API
- Use Redis authentication (requirepass)
- Run containers as non-root user
- Keep dependencies updated
- Monitor for suspicious task patterns

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Author

Built by Moiz - [GitHub](https://github.com/ziowm)
