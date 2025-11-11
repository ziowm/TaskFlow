from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, Any
from enum import Enum
import json


class TaskStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Task:
    task_id: str
    payload: dict
    priority: int
    status: TaskStatus
    submitted_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    worker_id: Optional[str] = None
    
    def to_redis_hash(self) -> dict:
        """Convert task to Redis hash format"""
        return {
            'task_id': self.task_id,
            'payload': json.dumps(self.payload),
            'priority': str(self.priority),
            'status': self.status.value,
            'submitted_at': self.submitted_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else '',
            'completed_at': self.completed_at.isoformat() if self.completed_at else '',
            'result': json.dumps(self.result) if self.result is not None else '',
            'error': self.error if self.error else '',
            'worker_id': self.worker_id if self.worker_id else ''
        }
    
    @classmethod
    def from_redis_hash(cls, data: dict) -> 'Task':
        """Create task from Redis hash data"""
        return cls(
            task_id=data['task_id'],
            payload=json.loads(data['payload']),
            priority=int(data['priority']),
            status=TaskStatus(data['status']),
            submitted_at=datetime.fromisoformat(data['submitted_at']),
            started_at=datetime.fromisoformat(data['started_at']) if data.get('started_at') else None,
            completed_at=datetime.fromisoformat(data['completed_at']) if data.get('completed_at') else None,
            result=json.loads(data['result']) if data.get('result') else None,
            error=data.get('error') if data.get('error') else None,
            worker_id=data.get('worker_id') if data.get('worker_id') else None
        )
