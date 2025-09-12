# ./models.py
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any, Union
from enum import Enum
from datetime import datetime

class TaskCreatedBy(str, Enum):
    AI = "ai"
    USER = "user"

class TaskStatus(str, Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

class Subtask(BaseModel):
    content: str
    isDone: bool = False

class Task(BaseModel):
    organizationId: str
    departmentId: Optional[str] = None
    createdBy: TaskCreatedBy = TaskCreatedBy.AI
    title: str
    description: Optional[str] = ""
    assignedToId: str
    reportToId: Optional[str] = None
    status: TaskStatus = TaskStatus.TODO
    priority: Priority = Priority.MEDIUM
    highQualityCompletion: bool = False
    deadline: Optional[str] = None
    subtasks: List[Subtask] = []

class ActionItem(BaseModel):
    description: str
    assignee: str = "Unknown"

class Attendee(BaseModel):
    name: str
    id: Optional[str] = None
    userName: Optional[str] = None
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None  # This should be Optional[str], not required str
    department: Optional[str] = None  # This should be Optional[str], not required str
    matchConfidence: Optional[Union[str, float]] = None  # Allow both string and float
    
    @validator('matchConfidence')
    def convert_match_confidence_to_string(cls, v):
        """Convert matchConfidence to string if it's a number"""
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return str(v)
        return v
    
    @validator('role', 'department', pre=True)
    def convert_none_to_empty_string(cls, v):
        """Convert None values to empty strings for required string fields"""
        return "" if v is None else v

class MeetingSummary(BaseModel):
    organizationId: str
    departmentId: Optional[str] = None
    createdById: str = "ai"
    title: str
    summary: str
    meetingDate: str
    attendees: List[Union[Attendee, Dict[str, Any]]] = []
    actionItems: List[Union[ActionItem, Dict[str, Any]]] = []
    
    @validator('attendees', pre=True)
    def process_attendees(cls, v):
        """Convert attendee dicts to Attendee objects and handle None values"""
        if not v:
            return []
        
        processed_attendees = []
        for attendee in v:
            if isinstance(attendee, dict):
                # Fix None values and type issues
                attendee_copy = attendee.copy()
                
                # Convert None to empty string for role and department
                if attendee_copy.get('role') is None:
                    attendee_copy['role'] = ""
                if attendee_copy.get('department') is None:
                    attendee_copy['department'] = ""
                
                # Convert matchConfidence to string if it's a number
                if attendee_copy.get('matchConfidence') is not None:
                    match_conf = attendee_copy['matchConfidence']
                    if isinstance(match_conf, (int, float)):
                        attendee_copy['matchConfidence'] = str(match_conf)
                
                processed_attendees.append(Attendee(**attendee_copy))
            else:
                processed_attendees.append(attendee)
        
        return processed_attendees

class GeneratedContent(BaseModel):
    organizationId: str
    departmentId: Optional[str] = None
    createdForId: str
    type: str  # "email" or "document"
    content: str
    subject: Optional[str] = None
    recipientEmail: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None