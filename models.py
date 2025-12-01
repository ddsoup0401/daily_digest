from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field  # pyright: ignore[reportMissingImports]
from datetime import datetime 

class TeamType(str, Enum):
    HARDWARE = "hardware"
    SOFTWARE = "software"


class TaskStatus(str, Enum):
    DONE = "done"
    WAITING_FOR_VALIDATION = "waiting_for_validation" 
    IN_PROGRESS = "in_progress"
    PENDING = "pending"
    BLOCKED = "blocked"

# Used for Risk Analysis. 
class TaskCategory(str, Enum):
    CRITICAL = "Critical" # normal forward / backward 
    INFRASTRUCTURE = "Infrastructure" # tasks are labeled as infrastructure if it isn't related to the main functionality of the project, such as test code writing and documentation. 
    SUPPORT = "Support" # all others supporting major bottleneck  

class ProjectStage(str, Enum):
    ARCHITECTURE = "1. Architecture" # setting up the initial architecture & interfaces
    BASELINE = "2. Baseline Development" # HW : CAD & materials, SW : simulation & Mock control 
    FABRICATION = "3. Fabrication & Assembly" # HW : CNC, 3D printing, assembly
    BRINGUP = "4. Bring-Up & Calibration" # SW : Software integration & calibration
    TESTING = "5. Testing & Iteration" # SW : Test code writing & full system testing

class MileStone(BaseModel):
    name: str 
    trigger_process: float = 0.0 # if trigger_process is 1.0, trigger the next stage. 
    is_reached: bool = False # if the milestone is reached, set to True

class Task(BaseModel):
    id: str
    name: str
    team: TeamType
    assigner: str

    component_id: str
    stage: ProjectStage
    category: TaskCategory = TaskCategory.CRITICAL

    # dependencies: List of task IDs that this task depends on
    dependencies: List[str] = Field(default_factory=list, description="IDs of dependency tasks")

    # status: TaskStatus
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0
    expected_duration: float

    # Volatility : Measure of how much the task is likely to change
    volatility: float = 0.0 # 0.0 means stable, 1.0 means very volatile

    # milestone specific variables
    milestone: List[MileStone] = Field(default_factory=list, description="Milestone for the task")
    
    # human factors - switching cost
    switch_cost: int = 0 # 0 = no penalty, 1 = low penalty, 2 = medium penalty, 3 = high penalty, 4 = very high penalty, 5 = extreme penalty
    target_support_id: Optional[str] = None # if the task is a support task, the ID of the support task to be swarmed

    created_at: datetime = Field(default_factory=datetime.now, description="Timestamp when the task was created")
    updated_at: datetime = Field(default_factory=datetime.now, description="Timestamp when the task was last updated")