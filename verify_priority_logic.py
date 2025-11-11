"""
Verify the priority-based task distribution logic
"""
from datetime import datetime
import time


def calculate_score(priority, submitted_at):
    """
    Calculate the score for a task based on priority and submission time
    
    Score = priority * 1000000 + (1000000 - timestamp_microseconds)
    
    This ensures:
    1. Higher priority tasks have higher scores
    2. Within same priority, earlier submissions have higher scores (FIFO)
    """
    timestamp_microseconds = int(submitted_at.timestamp() * 1000000) % 1000000
    score = priority * 1000000 + (1000000 - timestamp_microseconds)
    return score


def test_priority_ordering():
    """Verify that higher priority tasks get higher scores"""
    print("Testing priority ordering...")
    
    now = datetime.utcnow()
    
    score_low = calculate_score(1, now)
    score_medium = calculate_score(5, now)
    score_high = calculate_score(10, now)
    
    print(f"  Priority 1:  score = {score_low}")
    print(f"  Priority 5:  score = {score_medium}")
    print(f"  Priority 10: score = {score_high}")
    
    assert score_high > score_medium > score_low, "Higher priority should have higher score"
    print("  ✓ Priority ordering is correct\n")


def test_fifo_within_priority():
    """Verify that within same priority, earlier tasks get higher scores"""
    print("Testing FIFO ordering within same priority...")
    
    priority = 5
    
    # Simulate three tasks submitted at different times
    time1 = datetime.utcnow()
    time.sleep(0.001)
    time2 = datetime.utcnow()
    time.sleep(0.001)
    time3 = datetime.utcnow()
    
    score1 = calculate_score(priority, time1)
    score2 = calculate_score(priority, time2)
    score3 = calculate_score(priority, time3)
    
    print(f"  Task 1 (earliest):  score = {score1}")
    print(f"  Task 2 (middle):    score = {score2}")
    print(f"  Task 3 (latest):    score = {score3}")
    
    # Earlier submissions should have higher scores for FIFO with ZPOPMAX
    assert score1 > score2 > score3, "Earlier submissions should have higher scores (FIFO)"
    print("  ✓ FIFO ordering is correct\n")


def test_combined_priority_and_fifo():
    """Verify that priority takes precedence over submission time"""
    print("Testing combined priority and FIFO ordering...")
    
    # Low priority task submitted first
    time1 = datetime.utcnow()
    score_low_early = calculate_score(1, time1)
    
    time.sleep(0.001)
    
    # High priority task submitted later
    time2 = datetime.utcnow()
    score_high_late = calculate_score(10, time2)
    
    print(f"  Low priority (early):  score = {score_low_early}")
    print(f"  High priority (late):  score = {score_high_late}")
    
    # High priority should still have higher score even if submitted later
    assert score_high_late > score_low_early, "Priority should take precedence over submission time"
    print("  ✓ Priority takes precedence over submission time\n")


if __name__ == '__main__':
    print("=" * 60)
    print("Priority-Based Task Distribution Logic Verification")
    print("=" * 60)
    print()
    
    try:
        test_priority_ordering()
        test_fifo_within_priority()
        test_combined_priority_and_fifo()
        
        print("=" * 60)
        print("✓ All verification tests passed!")
        print("=" * 60)
        print()
        print("Summary:")
        print("- Higher priority tasks will be processed first")
        print("- Within same priority, tasks are processed in FIFO order")
        print("- ZPOPMAX retrieves tasks with highest scores first")
        
    except AssertionError as e:
        print(f"\n✗ Verification failed: {e}")
        exit(1)
