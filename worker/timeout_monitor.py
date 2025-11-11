import logging
import time
import redis
from datetime import datetime
from typing import Optional
import json


class TimeoutMonitor:
    """Monitor and handle timed-out tasks in the processing queue"""
    
    def __init__(self, redis_client, monitor_interval: int = 10):
        """
        Initialize timeout monitor
        
        Args:
            redis_client: Redis client instance
            monitor_interval: Seconds between monitoring checks (default: 10)
        """
        self.redis = redis_client
        self.monitor_interval = monitor_interval
        self.logger = logging.getLogger(__name__)
        self.shutdown_requested = False
        
        self.logger.info(f"Timeout monitor initialized with interval={monitor_interval}s")
    
    def check_timed_out_tasks(self):
        """
        Query tasks:processing sorted set for tasks with timeout score < current time
        Move timed-out tasks back to tasks:pending with original priority
        Reset task status to "pending" and clear worker_id
        Log timeout events with task ID and worker ID
        """
        try:
            current_time = datetime.utcnow().timestamp()
            
            # Query tasks:processing sorted set for tasks with timeout score < current time
            timed_out_tasks = self.redis.zrangebyscore(
                'tasks:processing',
                '-inf',
                current_time,
                withscores=True
            )
            
            if not timed_out_tasks:
                return
            
            self.logger.info(f"Found {len(timed_out_tasks)} timed-out task(s)")
            
            for task_id, timeout_score in timed_out_tasks:
                try:
                    # Retrieve task details to get original priority and worker_id
                    task_data = self.redis.hgetall(f'task:{task_id}')
                    
                    if not task_data:
                        self.logger.warning(f"Task {task_id} not found in Redis hash, removing from processing queue")
                        self.redis.zrem('tasks:processing', task_id)
                        continue
                    
                    original_priority = int(task_data.get('priority', 0))
                    worker_id = task_data.get('worker_id', 'unknown')
                    submitted_at_str = task_data.get('submitted_at', '')
                    
                    # Log timeout event with task ID and worker ID
                    self.logger.warning(
                        f"Task {task_id} timed out (worker: {worker_id}, priority: {original_priority})"
                    )
                    
                    # Calculate score for tasks:pending (same as submission logic)
                    # priority * 1000000 + (1000000 - timestamp_microseconds)
                    if submitted_at_str:
                        submitted_at = datetime.fromisoformat(submitted_at_str)
                        timestamp_microseconds = int(submitted_at.timestamp() * 1000000) % 1000000
                        score = original_priority * 1000000 + (1000000 - timestamp_microseconds)
                    else:
                        # Fallback if no submission timestamp
                        score = original_priority * 1000000
                    
                    # Use pipeline for atomic operations
                    pipe = self.redis.pipeline()
                    
                    # Reset task status to "pending" and clear worker_id
                    pipe.hset(f'task:{task_id}', 'status', 'pending')
                    pipe.hset(f'task:{task_id}', 'worker_id', '')
                    pipe.hset(f'task:{task_id}', 'started_at', '')
                    
                    # Move timed-out task back to tasks:pending with original priority
                    pipe.zadd('tasks:pending', {task_id: score})
                    
                    # Remove from tasks:processing
                    pipe.zrem('tasks:processing', task_id)
                    
                    # Execute pipeline
                    pipe.execute()
                    
                    self.logger.info(f"Task {task_id} moved back to pending queue for retry")
                    
                except Exception as e:
                    self.logger.error(f"Error handling timed-out task {task_id}: {e}", exc_info=True)
                    
        except redis.RedisError as e:
            self.logger.error(f"Redis error during timeout check: {e}")
            raise
    
    def run(self):
        """
        Run monitoring loop every 10 seconds
        Handle Redis connection errors in monitoring process
        """
        self.logger.info("Starting timeout monitoring loop")
        
        retry_attempt = 0
        backoff_delays = [1, 2, 4, 8, 16, 30]
        
        while not self.shutdown_requested:
            try:
                # Check for timed-out tasks
                self.check_timed_out_tasks()
                
                # Reset retry counter on successful operation
                retry_attempt = 0
                
                # Sleep for monitor interval
                time.sleep(self.monitor_interval)
                
            except (redis.ConnectionError, redis.TimeoutError) as e:
                # Handle Redis connection errors in monitoring process
                retry_attempt += 1
                delay = backoff_delays[min(retry_attempt - 1, len(backoff_delays) - 1)]
                
                self.logger.error(
                    f"Redis connection error in timeout monitor (attempt {retry_attempt}): {e}. "
                    f"Retrying in {delay}s..."
                )
                
                time.sleep(delay)
                
            except redis.RedisError as e:
                self.logger.error(f"Redis error in timeout monitoring loop: {e}")
                time.sleep(self.monitor_interval)
        
        self.logger.info("Timeout monitoring loop stopped")
    
    def stop(self):
        """Request shutdown of monitoring loop"""
        self.logger.info("Timeout monitor shutdown requested")
        self.shutdown_requested = True
