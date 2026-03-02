from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry

registry = CollectorRegistry()

TASKS_TOTAL = Counter(
    'taskflow_tasks_total',
    'Total number of tasks by final status',
    ['status'],
    registry=registry,
)

TASK_DURATION = Histogram(
    'taskflow_task_duration_seconds',
    'Time spent processing a task',
    buckets=[0.1, 0.5, 1, 2, 5, 10, 30, 60, 120, 300],
    registry=registry,
)

QUEUE_DEPTH = Gauge(
    'taskflow_queue_depth',
    'Number of tasks currently in the pending queue',
    registry=registry,
)

DLQ_DEPTH = Gauge(
    'taskflow_dlq_depth',
    'Number of tasks in the dead letter queue',
    registry=registry,
)
