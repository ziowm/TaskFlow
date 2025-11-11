import os
import sys
import logging
import socket
import time
import signal
import threading
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import redis

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.redis_client import RedisClient
from shared.models import Task, TaskStatus
from worker.timeout_monitor import TimeoutMonitor
from worker.task_handlers import (
    execute_math_operation,
    execute_data_processing,
    execute_text_processing,
    execute_task_with_error_demo
)


class WorkerNode:
    """Worker node that processes tasks from Redis queue"""
    
    def __init__(self):
        """Initialize worker with configuration from environment variables"""
        # Load configuration from environment variables
        self.redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        self.worker_id = os.getenv('WORKER_ID', socket.gethostname())
        self.poll_interval = float(os.getenv('POLL_INTERVAL', '1'))
        self.task_timeout = int(os.getenv('TASK_TIMEOUT', '300'))
        self.monitor_interval = int(os.getenv('MONITOR_INTERVAL', '10'))
        
        # Set up logging configuration
        log_level = os.getenv('LOG_LEVEL', 'INFO')
        logging.basicConfig(
            level=getattr(logging, log_level),
            format=f'%(asctime)s - Worker[{self.worker_id}] - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        self.logger = logging.getLogger(__name__)
        
        # Create Redis client connection
        self.redis_client = RedisClient(self.redis_url)
        self.redis = None
        
        # Shutdown flag
        self.shutdown_requested = False
        self.current_task_id: Optional[str] = None
        
        # Timeout monitor (will be initialized after Redis connection)
        self.timeout_monitor: Optional[TimeoutMonitor] = None
        self.monitor_thread: Optional[threading.Thread] = None
        
        # Register SIGTERM signal handler
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)
        
        self.logger.info(f"Worker initialized: ID={self.worker_id}, Poll Interval={self.poll_interval}s, Timeout={self.task_timeout}s")
    
    def _handle_shutdown(self, signum, frame):
        """
        Handle shutdown signals (SIGTERM, SIGINT)
        
        Args:
            signum: Signal number
            frame: Current stack frame
        """
        signal_name = 'SIGTERM' if signum == signal.SIGTERM else 'SIGINT'
        self.logger.info(f"Received {signal_name}, initiating graceful shutdown...")
        self.shutdown_requested = True
        
        # Stop timeout monitor if running
        if self.timeout_monitor:
            self.timeout_monitor.stop()
        
        # If processing a task, log that we'll complete it first
        if self.current_task_id:
            self.logger.info(f"Completing current task {self.current_task_id} before shutdown")
    
    def connect_redis(self):
        """Establish Redis connection"""
        self.redis = self.redis_client.connect()
        self.logger.info("Connected to Redis")
    
    def connect_with_backoff(self):
        """
        Connect to Redis with exponential backoff on failure
        
        Implements exponential backoff: 1s, 2s, 4s, 8s, 16s, 30s max
        """
        retry_attempt = 0
        backoff_delays = [1, 2, 4, 8, 16, 30]
        
        while not self.shutdown_requested:
            try:
                self.connect_redis()
                return
            except redis.ConnectionError as e:
                retry_attempt += 1
                delay = backoff_delays[min(retry_attempt - 1, len(backoff_delays) - 1)]
                self.logger.error(f"Redis connection error (attempt {retry_attempt}): {e}. Retrying in {delay}s...")
                time.sleep(delay)
    
    def poll_for_task(self) -> Optional[Task]:
        """
        Poll Redis sorted set for highest priority task
        
        Returns:
            Task object if available, None otherwise
        """
        try:
            # Poll Redis sorted set using ZPOPMAX on tasks:pending
            result = self.redis.zpopmax('tasks:pending', count=1)
            
            # Handle case when no tasks are available
            if not result:
                return None
            
            # Extract task_id from result
            task_id, priority = result[0]
            
            # Retrieve task details from Redis hash after claiming task
            task_data = self.redis.hgetall(f'task:{task_id}')
            
            if not task_data:
                self.logger.warning(f"Task {task_id} not found in Redis hash")
                return None
            
            # Convert to Task object
            task = Task.from_redis_hash(task_data)
            self.logger.info(f"Retrieved task {task_id} with priority {priority}")
            
            return task
            
        except redis.RedisError as e:
            self.logger.error(f"Redis error during task polling: {e}")
            raise
    
    def execute_task(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute task logic based on payload
        
        This method routes tasks to appropriate handlers based on the 'task_type'
        field in the payload. If no task_type is specified, uses a default handler.
        
        Args:
            payload: Task data from client
            
        Returns:
            Result dictionary to store in Redis
            
        Raises:
            Exception: Any error during execution
        """
        self.logger.info(f"Executing task with payload: {payload}")
        
        # Route to appropriate handler based on task_type
        task_type = payload.get('task_type', 'default')
        
        try:
            if task_type == 'math':
                result = execute_math_operation(payload)
            elif task_type == 'data_processing':
                result = execute_data_processing(payload)
            elif task_type == 'text_processing':
                result = execute_text_processing(payload)
            elif task_type == 'error_demo':
                result = execute_task_with_error_demo(payload)
            elif task_type == 'default':
                # Default handler: echo payload with metadata
                time.sleep(0.1)
                result = {
                    "status": "processed",
                    "input": payload,
                    "processed_by": self.worker_id
                }
            else:
                raise ValueError(f"Unknown task_type: {task_type}")
            
            # Add worker metadata to result
            result['processed_by'] = self.worker_id
            return result
            
        except Exception as e:
            self.logger.error(f"Task execution failed: {e}")
            raise
    
    def process_task(self, task: Task):
        """
        Process a task through its complete workflow
        
        Args:
            task: Task to process
        """
        task_id = task.task_id
        self.current_task_id = task_id
        
        try:
            # Update task status to "processing" with worker ID and started_at timestamp
            started_at = datetime.utcnow()
            self.redis.hset(f'task:{task_id}', 'status', TaskStatus.PROCESSING.value)
            self.redis.hset(f'task:{task_id}', 'worker_id', self.worker_id)
            self.redis.hset(f'task:{task_id}', 'started_at', started_at.isoformat())
            
            # Add task to tasks:processing sorted set with timeout score
            timeout_timestamp = (started_at + timedelta(seconds=self.task_timeout)).timestamp()
            self.redis.zadd('tasks:processing', {task_id: timeout_timestamp})
            
            self.logger.info(f"Task {task_id} status updated to processing")
            
            # Execute task handler function with payload
            result = self.execute_task(task.payload)
            
            # On success: update status to "completed", store result, set completed_at timestamp
            completed_at = datetime.utcnow()
            self.redis.hset(f'task:{task_id}', 'status', TaskStatus.COMPLETED.value)
            self.redis.hset(f'task:{task_id}', 'result', json.dumps(result))
            self.redis.hset(f'task:{task_id}', 'completed_at', completed_at.isoformat())
            
            # Remove task from tasks:processing sorted set after completion
            self.redis.zrem('tasks:processing', task_id)
            
            self.logger.info(f"Task {task_id} completed successfully")
            
        except Exception as e:
            # On failure: catch exceptions, update status to "failed", store error message
            self.logger.error(f"Task {task_id} failed: {e}", exc_info=True)
            
            completed_at = datetime.utcnow()
            self.redis.hset(f'task:{task_id}', 'status', TaskStatus.FAILED.value)
            self.redis.hset(f'task:{task_id}', 'error', str(e))
            self.redis.hset(f'task:{task_id}', 'completed_at', completed_at.isoformat())
            
            # Remove task from tasks:processing sorted set after completion
            self.redis.zrem('tasks:processing', task_id)
            
        finally:
            self.current_task_id = None
    
    def run(self):
        """Main polling loop with Redis error handling"""
        self.logger.info("Starting task polling loop")
        retry_attempt = 0
        backoff_delays = [1, 2, 4, 8, 16, 30]
        
        while not self.shutdown_requested:
            try:
                # Poll for task
                task = self.poll_for_task()
                
                # Reset retry counter on successful operation
                retry_attempt = 0
                
                if task is None:
                    # No tasks available, sleep for poll interval
                    time.sleep(self.poll_interval)
                    continue
                
                # Process the task
                self.process_task(task)
                
            except (redis.ConnectionError, redis.TimeoutError) as e:
                # Catch Redis connection errors during polling
                retry_attempt += 1
                delay = backoff_delays[min(retry_attempt - 1, len(backoff_delays) - 1)]
                
                # Log connection errors with retry attempt number
                self.logger.error(f"Redis connection error (attempt {retry_attempt}): {e}. Retrying in {delay}s...")
                
                # Implement exponential backoff
                time.sleep(delay)
                
                # Try to reconnect
                try:
                    self.connect_redis()
                    self.logger.info("Reconnected to Redis")
                    retry_attempt = 0
                except redis.ConnectionError:
                    pass  # Will retry in next iteration
                    
            except redis.RedisError as e:
                self.logger.error(f"Redis error in polling loop: {e}")
                time.sleep(self.poll_interval)
        
        self.logger.info("Polling loop stopped")


def main():
    """Main entry point for worker node"""
    worker = WorkerNode()
    
    try:
        # Connect to Redis with backoff
        worker.connect_with_backoff()
        worker.logger.info("Worker node started")
        
        # Initialize and start timeout monitor as separate thread
        worker.timeout_monitor = TimeoutMonitor(
            redis_client=worker.redis,
            monitor_interval=worker.monitor_interval
        )
        worker.monitor_thread = threading.Thread(
            target=worker.timeout_monitor.run,
            name="TimeoutMonitor",
            daemon=True
        )
        worker.monitor_thread.start()
        worker.logger.info("Timeout monitor thread started")
        
        # Run main polling loop
        worker.run()
        
    except KeyboardInterrupt:
        worker.logger.info("Keyboard interrupt received")
        worker.shutdown_requested = True
        
    finally:
        # Stop timeout monitor
        if worker.timeout_monitor:
            worker.timeout_monitor.stop()
            worker.logger.info("Timeout monitor stopped")
        
        # Wait for monitor thread to finish (with timeout)
        if worker.monitor_thread and worker.monitor_thread.is_alive():
            worker.monitor_thread.join(timeout=5)
            if worker.monitor_thread.is_alive():
                worker.logger.warning("Timeout monitor thread did not stop gracefully")
        
        # Close Redis connections cleanly
        if worker.redis_client:
            worker.redis_client.close()
            worker.logger.info("Redis connection closed")
        
        worker.logger.info("Worker node shutdown complete")
        
        # Exit with status code 0
        sys.exit(0)


if __name__ == '__main__':
    main()
