# Priority-Based Task Distribution Implementation

## Overview

This document describes the implementation of priority-based task distribution with FIFO ordering within the same priority level.

## Score Calculation

Tasks are stored in a Redis sorted set (`tasks:pending`) with a composite score that ensures both priority ordering and FIFO behavior:

```
score = priority * 1000000 + (1000000 - timestamp_microseconds)
```

### Components

1. **Priority Component**: `priority * 1000000`
   - Multiplied by 1,000,000 to ensure priority differences dominate the score
   - Higher priority values result in higher scores

2. **Timestamp Component**: `1000000 - timestamp_microseconds`
   - Uses the microsecond portion of the submission timestamp
   - Inverted (subtracted from 1,000,000) so earlier submissions get higher scores
   - Ensures FIFO ordering within the same priority level

## Examples

### Priority Ordering

```
Task A: priority=10, timestamp=500μs → score = 10,000,000 + 999,500 = 10,999,500
Task B: priority=5,  timestamp=500μs → score =  5,000,000 + 999,500 =  5,999,500
Task C: priority=1,  timestamp=500μs → score =  1,000,000 + 999,500 =  1,999,500

Processing order: A → B → C (highest priority first)
```

### FIFO Within Same Priority

```
Task A: priority=5, timestamp=100μs → score = 5,000,000 + 999,900 = 5,999,900
Task B: priority=5, timestamp=200μs → score = 5,000,000 + 999,800 = 5,999,800
Task C: priority=5, timestamp=300μs → score = 5,000,000 + 999,700 = 5,999,700

Processing order: A → B → C (FIFO - first submitted, first processed)
```

### Combined Behavior

```
Task A: priority=10, timestamp=900μs → score = 10,000,000 + 999,100 = 10,999,100
Task B: priority=5,  timestamp=100μs → score =  5,000,000 + 999,900 =  5,999,900
Task C: priority=5,  timestamp=200μs → score =  5,000,000 + 999,800 =  5,999,800

Processing order: A → B → C
- A is processed first (highest priority)
- B is processed before C (same priority, but B was submitted earlier)
```

## Implementation Details

### API (api/server.py)

When a task is submitted:
1. Generate unique task ID
2. Create Task object with current timestamp
3. Store task data in Redis hash (`task:{task_id}`)
4. Calculate composite score
5. Add task to sorted set with `ZADD tasks:pending {task_id} {score}`

### Worker (worker/main.py)

When polling for tasks:
1. Use `ZPOPMAX tasks:pending 1` to atomically retrieve and remove the highest score task
2. ZPOPMAX ensures:
   - Atomic operation (no race conditions)
   - Highest score task is retrieved first
   - Task is removed from queue immediately

## Requirements Satisfied

- **Requirement 3.1**: Redis sorted set maintains priority ordering
- **Requirement 3.2**: ZPOPMAX retrieves highest priority task
- **Requirement 3.3**: Higher priority values = higher priority processing
- **Requirement 3.4**: FIFO ordering within same priority level
- **Requirement 3.5**: Atomic task claiming prevents duplicate processing

## Verification

Run the verification script to test the logic:

```bash
python3 verify_priority_logic.py
```

This script demonstrates:
- Priority ordering (higher priority = higher score)
- FIFO ordering within same priority (earlier submission = higher score)
- Priority takes precedence over submission time
