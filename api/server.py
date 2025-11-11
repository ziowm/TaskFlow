import os
import logging
import uuid
from datetime import datetime
from flask import Flask, request, jsonify
from shared.redis_client import RedisClient
from shared.models import Task, TaskStatus
import redis

# Initialize Flask app
app = Flask(__name__)

# Load configuration from environment variables
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')
API_PORT = int(os.getenv('API_PORT', '5000'))
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# Set up logging configuration
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Redis client connection with error handling
redis_client = RedisClient(REDIS_URL)

try:
    redis_client.connect()
    logger.info(f"Successfully connected to Redis at {REDIS_URL}")
except redis.ConnectionError as e:
    logger.error(f"Failed to connect to Redis at {REDIS_URL}: {e}")
    logger.warning("API will start but Redis operations will fail until connection is established")


@app.route('/tasks', methods=['POST'])
def submit_task():
    """
    Submit a new task to the queue
    
    Request Body:
        {
            "payload": dict,
            "priority": int (optional, default: 0)
        }
    
    Returns:
        201: {"task_id": str, "status": "pending"}
        400: {"error": str} - validation error
        503: {"error": str} - Redis connection error
    """
    try:
        # Get request data
        data = request.get_json()
        
        # Validate request
        if not data:
            return jsonify({"error": "Request body is required"}), 400
        
        if 'payload' not in data:
            return jsonify({"error": "Field 'payload' is required"}), 400
        
        if not isinstance(data['payload'], dict):
            return jsonify({"error": "Field 'payload' must be a dictionary"}), 400
        
        # Get priority with default value
        priority = data.get('priority', 0)
        
        if not isinstance(priority, int):
            return jsonify({"error": "Field 'priority' must be an integer"}), 400
        
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
            
            # Return task ID and status with HTTP 201
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


if __name__ == '__main__':
    logger.info(f"Starting Task Scheduler API on port {API_PORT}")
    app.run(host='0.0.0.0', port=API_PORT, debug=False)
