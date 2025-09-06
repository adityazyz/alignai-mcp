from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
import json

class TaskCreatedBy(str, Enum):
    AI = "ai"
    USER = "user"

class TaskStatus(str, Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"

class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class Subtask(BaseModel):
    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat() if v else None})
    
    content: str
    isDone: bool = False
    completedAt: Optional[datetime] = None

class Task(BaseModel):
    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat() if v else None})
    
    organizationId: str
    departmentId: Optional[str] = None
    createdBy: TaskCreatedBy = TaskCreatedBy.AI
    title: str
    description: Optional[str] = None
    assignedToId: str
    reportToId: Optional[str] = None
    status: TaskStatus = TaskStatus.TODO
    priority: Priority = Priority.MEDIUM
    highQualityCompletion: bool = False
    deadline: Optional[datetime] = None
    completedAt: Optional[datetime] = None
    subtasks: List[Subtask] = []
    
    def model_dump(self, **kwargs):
        """Override to ensure datetime serialization"""
        data = super().model_dump(**kwargs)
        # Convert datetime objects to ISO strings
        if data.get('deadline') and hasattr(data['deadline'], 'isoformat'):
            data['deadline'] = data['deadline'].isoformat()
        if data.get('completedAt') and hasattr(data['completedAt'], 'isoformat'):
            data['completedAt'] = data['completedAt'].isoformat()
        
        # Handle subtasks
        if data.get('subtasks'):
            for subtask in data['subtasks']:
                if subtask.get('completedAt') and hasattr(subtask['completedAt'], 'isoformat'):
                    subtask['completedAt'] = subtask['completedAt'].isoformat()
        
        return data

class MeetingSummary(BaseModel):
    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat() if v else None})
    
    organizationId: str
    departmentId: Optional[str] = None
    createdById: str
    title: str
    summary: str
    meetingDate: str  # Keep as string since it's already ISO format
    attendees: List[Dict[str, str]]  # [{name: str}] from RecallAI
    actionItems: List[Dict[str, Any]]  # [{description: str, assignee: str}]

class GeneratedContent(BaseModel):
    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat() if v else None})
    
    organizationId: str
    departmentId: Optional[str] = None
    createdForId: str
    type: str
    content: str
    subject: Optional[str] = None
    recipientEmail: Optional[str] = None