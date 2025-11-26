from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field

class TeamType(str, Enum):
    HARDWARE = "hardware"
    SOFTWARE = "software"

class TaskStatus(str, Enum):
    DONE = "done"
    IN_PROGRESS = "in_progress"
    NOT_STARTED = "not_started"
    PENDING = "pending"
    BLOCKED = "blocked"

class Task(BaseModel):
    id: str = Field(..., description="The unique identifier for the task")
    name: str = Field(..., description="The name of the person")
    team: TeamType = Field(..., description="The team of the person")

    dependencies: List[str] = Field(..., description="The dependencies of the task")
    status: TaskStatus = Field(..., description="The status of the task")
    expected_duration: int = Field(..., description="The expected duration of the task in days")
    actual_duration: float 
    progress: float = 0.0 

    # Volatility : Measure of how much the task is likely to change
    volatility: float = 0.0 # 0.0 means the task is not likely to change, 1.0 means the task is likely to change a lot

    # Switch_cost : Penalty for switching to a different task, for efficiency decreases by switching cost for humans 
    switch_cost: int = 1 # 1 means no penalty for switching, 5 means a lot of penalty for switching
    
    # 1f1b logic: 
    is_feedback_task: bool = False # True if "Backward Pass" 

    
