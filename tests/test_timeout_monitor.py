"""
Test timeout monitoring functionality
"""
import time
import redis
from datetime import datetime, timedelta
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from worker.timeout_monitor import TimeoutMonitor


def test_timeout_detection():
    """Test that timed-out tasks are detected and moved back to pending"""
    # Connect to Redis
    client = redis.from_url('redis://localhost:6379', decode_responses=True)
    
    # Clear any existing tasks
    client.delete('tasks:pending')
    client.delete('tasks:processing')
    client.delete('task:test-timeout-1')
    
    # Create a task that appears to be processing and timed out
    task_id = 'test-timeout-1'
    priority = 5
    submitted_at = datetime.utcnow()
    
    # Create task hash
    task_data = {
        'task_id': task_id,
        'payload': '{"test": "data"}',
        'priority': str(priority),
        'status': 'processing',
        'submitted_at': submitted_at.isoformat(),
        'started_at': (submitted_at - timedelta(seconds=400)).isoformat(),  # Started 400s ago
        'worker_id': 'test-worker-1'
    }
    client.hset(f'task:{task_id}', mapping=task_data)
    
    # Add to processing queue with timeout in the past (simulating timeout)
    timeout_timestamp = (datetime.utcnow() - timedelta(seconds=10)).timestamp()
    client.zadd('tasks:processing', {task_id: timeout_timestamp})
    
    # Verify task is in processing queue
    processing_tasks = client.zrange('tasks:processing', 0, -1)
    assert task_id in processing_tasks, "Task should be in processing queue"
    
    # Create timeout monitor and run one check
    monitor = TimeoutMonitor(client, monitor_interval=10)
    monitor.check_timed_out_tasks()
    
    # Verify task was moved back to pending
    pending_tasks = client.zrange('tasks:pending', 0, -1)
    assert task_id in pending_tasks, "Task should be moved to pending queue"
    
    # Verify task is no longer in processing
    processing_tasks = client.zrange('tasks:processing', 0, -1)
    assert task_id not in processing_tasks, "Task should be removed from processing queue"
    
    # Verify task status was reset
    task_status = client.hget(f'task:{task_id}', 'status')
    assert task_status == 'pending', f"Task status should be 'pending', got '{task_status}'"
    
    # Verify worker_id was cleared
    worker_id = client.hget(f'task:{task_id}', 'worker_id')
    assert worker_id == '', f"Worker ID should be cleared, got '{worker_id}'"
    
    # Cleanup
    client.delete('tasks:pending')
    client.delete('tasks:processing')
    client.delete(f'task:{task_id}')
    
    print("✓ Timeout detection test passed")


def test_no_false_positives():
    """Test that tasks still within timeout are not moved"""
    # Connect to Redis
    client = redis.from_url('redis://localhost:6379', decode_responses=True)
    
    # Clear any existing tasks
    client.delete('tasks:pending')
    client.delete('tasks:processing')
    client.delete('task:test-active-1')
    
    # Create a task that is processing but not timed out
    task_id = 'test-active-1'
    priority = 5
    submitted_at = datetime.utcnow()
    
    # Create task hash
    task_data = {
        'task_id': task_id,
        'payload': '{"test": "data"}',
        'priority': str(priority),
        'status': 'processing',
        'submitted_at': submitted_at.isoformat(),
        'started_at': submitted_at.isoformat(),
        'worker_id': 'test-worker-1'
    }
    client.hset(f'task:{task_id}', mapping=task_data)
    
    # Add to processing queue with timeout in the future (not timed out)
    timeout_timestamp = (datetime.utcnow() + timedelta(seconds=300)).timestamp()
    client.zadd('tasks:processing', {task_id: timeout_timestamp})
    
    # Create timeout monitor and run one check
    monitor = TimeoutMonitor(client, monitor_interval=10)
    monitor.check_timed_out_tasks()
    
    # Verify task is still in processing queue
    processing_tasks = client.zrange('tasks:processing', 0, -1)
    assert task_id in processing_tasks, "Task should still be in processing queue"
    
    # Verify task is not in pending
    pending_tasks = client.zrange('tasks:pending', 0, -1)
    assert task_id not in pending_tasks, "Task should not be in pending queue"
    
    # Verify task status is still processing
    task_status = client.hget(f'task:{task_id}', 'status')
    assert task_status == 'processing', f"Task status should be 'processing', got '{task_status}'"
    
    # Cleanup
    client.delete('tasks:pending')
    client.delete('tasks:processing')
    client.delete(f'task:{task_id}')
    
    print("✓ No false positives test passed")


if __name__ == '__main__':
    try:
        test_timeout_detection()
        test_no_false_positives()
        print("\n✓ All timeout monitor tests passed!")
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        exit(1)
    except redis.ConnectionError:
        print("\n✗ Could not connect to Redis. Make sure Redis is running on localhost:6379")
        exit(1)
