import os
import logging
import uuid
from datetime import datetime
from flask import Flask, request, jsonify, Response, render_template
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from shared.redis_client import RedisClient
from shared.models import Task, TaskStatus
from shared.metrics import registry, QUEUE_DEPTH, DLQ_DEPTH
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
import redis

# ── App init ──────────────────────────────────────────────────────────────
app = Flask(__name__)

# ── Config ────────────────────────────────────────────────────────────────
REDIS_URL   = os.getenv('REDIS_URL', 'redis://localhost:6379')
API_PORT    = int(os.getenv('API_PORT', '5000'))
LOG_LEVEL   = os.getenv('LOG_LEVEL', 'INFO')
API_KEY     = os.getenv('API_KEY', '')          # empty = auth disabled (dev mode)
MAX_BODY_KB = int(os.getenv('MAX_BODY_KB', '32'))
MAX_PRIORITY = 100
MAX_PAYLOAD_FIELDS = 20

# ── Logging ───────────────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ── Rate limiter ──────────────────────────────────────────────────────────
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=[],          # no global limit — set per-route
    storage_uri=REDIS_URL,      # store counters in Redis so limits survive restarts
)

# ── Redis ─────────────────────────────────────────────────────────────────
redis_client = RedisClient(REDIS_URL)

try:
    redis_client.connect()
    logger.info(f"Connected to Redis at {REDIS_URL}")
except redis.ConnectionError as e:
    logger.error(f"Failed to connect to Redis: {e}")
    logger.warning("API will start but Redis operations will fail until connection is established")


# ── Security helpers ──────────────────────────────────────────────────────

def _check_api_key():
    """Return a 401 response if API_KEY is set and the request doesn't match."""
    if not API_KEY:
        return None  # auth disabled in dev mode
    auth = request.headers.get('Authorization', '')
    token = auth.removeprefix('Bearer ').strip()
    if token != API_KEY:
        ip = get_remote_address()
        logger.warning(f"AUTH FAIL  {ip}  {request.method} {request.path}")
        return jsonify({"error": "Invalid or missing API key"}), 401
    return None


def _check_payload_size():
    """Reject requests whose body exceeds MAX_BODY_KB."""
    limit = MAX_BODY_KB * 1024
    if request.content_length and request.content_length > limit:
        logger.warning(f"PAYLOAD TOO LARGE  {get_remote_address()}  {request.content_length} bytes")
        return jsonify({"error": f"Request body too large (max {MAX_BODY_KB}KB)"}), 413
    return None


def _log_request(status: int):
    """Structured access log for write endpoints."""
    logger.info(f"REQUEST  {get_remote_address()}  {request.method} {request.path}  {status}")


@app.route('/', methods=['GET'])
def dashboard():
    """Serve the TaskFlow dashboard — inject API key so the UI can auth automatically."""
    return render_template('dashboard.html', api_key=API_KEY)


@app.route('/tasks', methods=['POST'])
@limiter.limit("30 per minute")
@limiter.limit("5 per second")
def submit_task():
    """Submit a new task to the queue."""
    # Security checks
    denied = _check_api_key() or _check_payload_size()
    if denied:
        _log_request(denied[1])
        return denied

    try:
        data = request.get_json(silent=True)

        if not data:
            _log_request(400)
            return jsonify({"error": "Request body is required"}), 400

        if 'payload' not in data:
            _log_request(400)
            return jsonify({"error": "Field 'payload' is required"}), 400

        if not isinstance(data['payload'], dict):
            _log_request(400)
            return jsonify({"error": "Field 'payload' must be a dictionary"}), 400

        if len(data['payload']) > MAX_PAYLOAD_FIELDS:
            _log_request(400)
            return jsonify({"error": f"Payload too many fields (max {MAX_PAYLOAD_FIELDS})"}), 400

        priority = data.get('priority', 0)

        if not isinstance(priority, int):
            _log_request(400)
            return jsonify({"error": "Field 'priority' must be an integer"}), 400

        if not (0 <= priority <= MAX_PRIORITY):
            _log_request(400)
            return jsonify({"error": f"Priority must be between 0 and {MAX_PRIORITY}"}), 400
        
        # Generate unique task ID
        task_id = str(uuid.uuid4())
        
        # Create Task object with status "pending" and current timestamp
        task = Task(
            task_id=task_id,
            payload=data['payload'],
            priority=priority,
            status=TaskStatus.PENDING,
            submitted_at=datetime.utcnow()
        )
        
        # Store task in Redis
        try:
            client = redis_client.get_client()
            
            # Store task in Redis hash (task:{task_id})
            task_key = f"task:{task_id}"
            client.hset(task_key, mapping=task.to_redis_hash())
            
            # Calculate score as: priority * 1000000 + (1000000 - timestamp_microseconds)
            # This ensures:
            # 1. Higher priority tasks are processed first (higher priority = higher score)
            # 2. Within same priority, earlier submissions are processed first (FIFO)
            #    by inverting the timestamp component (earlier time = higher score)
            timestamp_microseconds = int(task.submitted_at.timestamp() * 1000000) % 1000000
            score = priority * 1000000 + (1000000 - timestamp_microseconds)
            
            # Add task to Redis sorted set (tasks:pending) with composite score
            # ZPOPMAX will retrieve highest score (highest priority, earliest timestamp)
            client.zadd('tasks:pending', {task_id: score})
            
            logger.info(f"Task {task_id} submitted with priority {priority}")
            _log_request(201)
            return jsonify({
                "task_id": task_id,
                "status": "pending"
            }), 201
            
        except (redis.ConnectionError, redis.TimeoutError) as e:
            logger.error(f"Redis connection error while submitting task: {e}")
            return jsonify({"error": "Service temporarily unavailable"}), 503
            
    except Exception as e:
        logger.error(f"Unexpected error in submit_task: {e}")
        return jsonify({"error": "Internal server error"}), 500


@app.route('/tasks/<task_id>', methods=['GET'])
@limiter.limit("120 per minute")
def get_task_status(task_id):
    """
    Get the status of a task
    
    Args:
        task_id: Unique task identifier
    
    Returns:
        200: Task status with all fields
        404: Task not found
        503: Redis connection error
    """
    try:
        client = redis_client.get_client()
        
        # Retrieve task data from Redis hash
        task_key = f"task:{task_id}"
        task_data = client.hgetall(task_key)
        
        # Return HTTP 404 if task does not exist
        if not task_data:
            return jsonify({"error": "Task not found"}), 404
        
        # Parse task from Redis
        task = Task.from_redis_hash(task_data)
        
        # Format response with all task fields
        response = {
            "task_id": task.task_id,
            "status": task.status.value,
            "priority": task.priority,
            "submitted_at": task.submitted_at.isoformat()
        }
        
        # Add optional fields if present
        if task.started_at:
            response["started_at"] = task.started_at.isoformat()
        
        if task.completed_at:
            response["completed_at"] = task.completed_at.isoformat()
        
        # Include result or error if task is completed/failed
        if task.result is not None:
            response["result"] = task.result
        
        if task.error:
            response["error"] = task.error
        
        if task.worker_id:
            response["worker_id"] = task.worker_id
        
        # Return HTTP 200 with task status
        return jsonify(response), 200
        
    except (redis.ConnectionError, redis.TimeoutError) as e:
        logger.error(f"Redis connection error while retrieving task {task_id}: {e}")
        return jsonify({"error": "Service temporarily unavailable"}), 503
        
    except Exception as e:
        logger.error(f"Unexpected error in get_task_status for task {task_id}: {e}")
        return jsonify({"error": "Internal server error"}), 500


@app.route('/tasks/dead', methods=['GET'])
@limiter.limit("60 per minute")
def list_dead_tasks():
    """
    List all tasks in the dead letter queue

    Returns:
        200: {"tasks": [...], "count": int}
        503: Redis connection error
    """
    try:
        client = redis_client.get_client()

        # Get all dead task IDs ordered by failure time (most recent first)
        dead_task_ids = client.zrevrange('tasks:dead', 0, -1)

        tasks = []
        for task_id in dead_task_ids:
            task_data = client.hgetall(f'task:{task_id}')
            if not task_data:
                continue
            task = Task.from_redis_hash(task_data)
            tasks.append({
                'task_id': task.task_id,
                'status': task.status.value,
                'priority': task.priority,
                'retry_count': task.retry_count,
                'max_retries': task.max_retries,
                'error': task.error,
                'submitted_at': task.submitted_at.isoformat(),
                'completed_at': task.completed_at.isoformat() if task.completed_at else None,
            })

        return jsonify({'tasks': tasks, 'count': len(tasks)}), 200

    except (redis.ConnectionError, redis.TimeoutError) as e:
        logger.error(f"Redis connection error in list_dead_tasks: {e}")
        return jsonify({"error": "Service temporarily unavailable"}), 503

    except Exception as e:
        logger.error(f"Unexpected error in list_dead_tasks: {e}")
        return jsonify({"error": "Internal server error"}), 500


@app.route('/tasks/<task_id>/retry', methods=['POST'])
@limiter.limit("20 per minute")
def retry_dead_task(task_id):
    """
    Re-enqueue a dead task back into the pending queue

    Returns:
        200: {"task_id": str, "status": "pending"}
        404: Task not found or not in dead state
        503: Redis connection error
    """
    denied = _check_api_key()
    if denied:
        _log_request(denied[1])
        return denied

    try:
        client = redis_client.get_client()

        task_data = client.hgetall(f'task:{task_id}')
        if not task_data:
            return jsonify({"error": "Task not found"}), 404

        task = Task.from_redis_hash(task_data)

        if task.status.value != 'dead':
            return jsonify({"error": f"Task is not in dead state (current: {task.status.value})"}), 400

        # Reset retry count and re-enqueue
        timestamp_microseconds = int(task.submitted_at.timestamp() * 1000000) % 1000000
        score = task.priority * 1000000 + (1000000 - timestamp_microseconds)

        pipe = client.pipeline()
        pipe.hset(f'task:{task_id}', 'status', 'pending')
        pipe.hset(f'task:{task_id}', 'retry_count', '0')
        pipe.hset(f'task:{task_id}', 'worker_id', '')
        pipe.hset(f'task:{task_id}', 'started_at', '')
        pipe.hset(f'task:{task_id}', 'completed_at', '')
        pipe.hset(f'task:{task_id}', 'error', '')
        pipe.zadd('tasks:pending', {task_id: score})
        pipe.zrem('tasks:dead', task_id)
        pipe.execute()

        logger.info(f"Task {task_id} manually retried from DLQ")
        return jsonify({"task_id": task_id, "status": "pending"}), 200

    except (redis.ConnectionError, redis.TimeoutError) as e:
        logger.error(f"Redis connection error in retry_dead_task: {e}")
        return jsonify({"error": "Service temporarily unavailable"}), 503

    except Exception as e:
        logger.error(f"Unexpected error in retry_dead_task: {e}")
        return jsonify({"error": "Internal server error"}), 500


@app.route('/stats', methods=['GET'])
def stats():
    """
    Return live queue stats from Redis directly.
    More reliable than Prometheus counters which are per-process.
    """
    try:
        client = redis_client.get_client()

        # Count tasks by status by scanning task keys
        counts = {s.value: 0 for s in TaskStatus}
        cursor = 0
        while True:
            cursor, keys = client.scan(cursor, match='task:*', count=200)
            for key in keys:
                status = client.hget(key, 'status')
                if status and status in counts:
                    counts[status] += 1
            if cursor == 0:
                break

        return jsonify({
            'queue_depth': client.zcard('tasks:pending'),
            'processing':  client.zcard('tasks:processing'),
            'dlq_depth':   client.zcard('tasks:dead'),
            'completed':   counts.get('completed', 0),
            'failed':      counts.get('failed', 0),
            'dead':        counts.get('dead', 0),
        }), 200

    except (redis.ConnectionError, redis.TimeoutError) as e:
        logger.error(f"Redis error in stats: {e}")
        return jsonify({"error": "Service temporarily unavailable"}), 503

    except Exception as e:
        logger.error(f"Unexpected error in stats: {e}")
        return jsonify({"error": "Internal server error"}), 500


@app.route('/metrics', methods=['GET'])
def metrics():
    """Prometheus metrics endpoint"""
    try:
        client = redis_client.get_client()
        QUEUE_DEPTH.set(client.zcard('tasks:pending'))
        DLQ_DEPTH.set(client.zcard('tasks:dead'))
    except Exception:
        pass  # Emit stale metrics rather than failing the scrape
    return Response(generate_latest(registry), mimetype=CONTENT_TYPE_LATEST)


@app.route('/health', methods=['GET'])
def health_check():
    """
    Check the health of the API and Redis connection
    
    Returns:
        200: {"status": "healthy", "redis_connected": true}
        503: {"status": "unhealthy", "redis_connected": false}
    """
    # Check Redis connection status
    redis_connected = redis_client.is_connected()
    
    if redis_connected:
        return jsonify({
            "status": "healthy",
            "redis_connected": True
        }), 200
    else:
        return jsonify({
            "status": "unhealthy",
            "redis_connected": False
        }), 503


@app.errorhandler(429)
def ratelimit_handler(e):
    ip = get_remote_address()
    logger.warning(f"RATE LIMITED  {ip}  {request.method} {request.path}")
    return jsonify({"error": "Too many requests — slow down", "retry_after": str(e.description)}), 429


if __name__ == '__main__':
    logger.info(f"Starting Task Scheduler API on port {API_PORT}")
    app.run(host='0.0.0.0', port=API_PORT, debug=False)
