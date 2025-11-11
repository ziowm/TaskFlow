"""
Test priority-based task distribution with FIFO ordering
"""
import time
import redis
from datetime import datetime


def test_priority_ordering():
    """Test that tasks are retrieved in priority order (highest first)"""
    # Connect to Redis
    client = redis.from_url('redis://localhost:6379', decode_responses=True)
    
    # Clear any existing tasks
    client.delete('tasks:pending')
    
    # Add tasks with different priorities
    # Lower priority tasks added first
    client.zadd('tasks:pending', {'task-low': 1 * 1000000})
    time.sleep(0.001)  # Small delay to ensure different timestamps
    client.zadd('tasks:pending', {'task-high': 10 * 1000000})
    time.sleep(0.001)
    client.zadd('tasks:pending', {'task-medium': 5 * 1000000})
    
    # Retrieve tasks - should come out in priority order (high, medium, low)
    result1 = client.zpopmax('tasks:pending', count=1)
    result2 = client.zpopmax('tasks:pending', count=1)
    result3 = client.zpopmax('tasks:pending', count=1)
    
    assert result1[0][0] == 'task-high', f"Expected task-high, got {result1[0][0]}"
    assert result2[0][0] == 'task-medium', f"Expected task-medium, got {result2[0][0]}"
    assert result3[0][0] == 'task-low', f"Expected task-low, got {result3[0][0]}"
    
    print("✓ Priority ordering test passed")


def test_fifo_within_priority():
    """Test that tasks with same priority are processed in FIFO order"""
    # Connect to Redis
    client = redis.from_url('redis://localhost:6379', decode_responses=True)
    
    # Clear any existing tasks
    client.delete('tasks:pending')
    
    # Add multiple tasks with same priority but different timestamps
    priority = 5
    
    # Simulate the score calculation from api/server.py
    # Score = priority * 1000000 + (1000000 - timestamp_microseconds)
    # Earlier timestamps get higher scores for FIFO ordering
    
    base_time_1 = int(datetime.utcnow().timestamp() * 1000000)
    score_1 = priority * 1000000 + (1000000 - (base_time_1 % 1000000))
    client.zadd('tasks:pending', {'task-1': score_1})
    
    time.sleep(0.001)  # Ensure different timestamps
    
    base_time_2 = int(datetime.utcnow().timestamp() * 1000000)
    score_2 = priority * 1000000 + (1000000 - (base_time_2 % 1000000))
    client.zadd('tasks:pending', {'task-2': score_2})
    
    time.sleep(0.001)
    
    base_time_3 = int(datetime.utcnow().timestamp() * 1000000)
    score_3 = priority * 1000000 + (1000000 - (base_time_3 % 1000000))
    client.zadd('tasks:pending', {'task-3': score_3})
    
    # Retrieve tasks - should come out in submission order (FIFO)
    result1 = client.zpopmax('tasks:pending', count=1)
    result2 = client.zpopmax('tasks:pending', count=1)
    result3 = client.zpopmax('tasks:pending', count=1)
    
    # With inverted timestamps, earlier submissions have higher scores
    # So ZPOPMAX should return them in FIFO order: task-1, task-2, task-3
    assert result1[0][0] == 'task-1', f"Expected task-1, got {result1[0][0]}"
    assert result2[0][0] == 'task-2', f"Expected task-2, got {result2[0][0]}"
    assert result3[0][0] == 'task-3', f"Expected task-3, got {result3[0][0]}"
    
    print("✓ FIFO within priority test passed")


if __name__ == '__main__':
    try:
        test_priority_ordering()
        test_fifo_within_priority()
        print("\n✓ All priority distribution tests passed!")
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        exit(1)
    except redis.ConnectionError:
        print("\n✗ Could not connect to Redis. Make sure Redis is running on localhost:6379")
        exit(1)
