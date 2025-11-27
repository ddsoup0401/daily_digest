from typing import Optional
from models import Task, TeamType, TaskCategory, ProjectStage

class Optimizer:
    def __init__(self, graph_manager):
        self.gm = graph_manager
    
    def classify_task_direction(self, task: Task) -> str: 
        """
        Classify the task into either Forward Pass or Backward Pass  
        """
        if task.stage == ProjectStage.BRINGUP:
            return "BACKWARD"
        if task.stage == ProjectStage.FABRICATION:
            return "FORWARD"
        if task.stage == ProjectStage.TESTING:
            return "BACKWARD"
        if task.stage == ProjectStage.ARCHITECTURE:
            return "FORWARD"
        if task.stage == ProjectStage.BASELINE:
            return "FORWARD"
        return "FORWARD"
    
    def calculate_scrap_risk_score(self, task: Task) -> float:
        """
        Calculate the scrap risk score for a task (based on volatility of self and dependencies)
        if the risk score is high, the task is more likely to be cancelled.
        """
        risk_score = 0.0

        # default = getattr(task, 'category', TaskCategory.CRITICAL)
        # if default == TaskCategory.INFRASTRUCTURE:
        #     return 0.0  
        task_category = task.category
        if task_category == TaskCategory.INFRASTRUCTURE:
            return 0.0
        
        for dep in task.dependencies:
            dep_task = self.gm.get_task(dep)
            if dep_task: 
                risk_score += dep_task.volatility * 100 
        
        return min(risk_score, 100)

    def run_scheduler(self, assigner_filter: Optional[str] = None, current_time_step: Optional[int] = None) -> str:
        """
        Run the scheduler to schedule the tasks --> this is the main algorithm 
        """
        # 1. Get all the tasks that are ready to be scheduled
        backward_queue = [] # Priority 1. Backward (BringUp / Calibration)
        forward_queue = [] # Priority 2. Forward (Fabrication / Design)
        infrastructure_queue = [] # Priority 3. Infrastructure (Infrastructure)

        ready_tasks = self.gm.get_ready_tasks()

        for task in ready_tasks: 
            direction = self.classify_task_direction(task)

            if direction == "BACKWARD":
                backward_queue.append(task)
            elif task.category == TaskCategory.INFRASTRUCTURE:
                infrastructure_queue.append(task)
            else:
                forward_queue.append(task)
        
        report = []
        has_critical_task = False 

        # ========================== BACKWARD PASS ==========================
        if backward_queue:
            has_critical_task = True
            report.append("Critical task detected in backward pass... pausing scheduler...")
            report.append(f"Critical task: {backward_queue[0].name}. Rescheduling after critical task is completed...")

            for i, task in enumerate(backward_queue):
                report.append(f"Task {i+1}: {task.name} - {task.team.value}")
                report.append("Action: Perform the task...")
            report.append("")

        # ========================== FORWARD PASS ==========================
        if forward_queue:
            report.append("Forward pass tasks detected... scheduling forward pass...")
            # Sort the forward queue from lowest to highest scrap risk score to minimize the risk of cancellation
            forward_queue.sort(key=lambda t: self.calculate_scrap_risk_score(t))

            for i, task in enumerate(forward_queue):
                prefix = f" {i+1}."

                if has_critical_task:
                    report.append(f"{prefix}[BLOCKED] **{task.name}**")
                    report.append(f"{prefix}Action: Waiting for critical task to be completed...")
                    continue

                is_micro_batch_start = any(
                    self.gm.get_task(p).progress < 1.0 for p in task.dependencies if self.gm.get_task(p)
                )
                tag = "Micro-batch start" if is_micro_batch_start else "Normal start"

                scrap_risk = self.calculate_scrap_risk_score(task)

                if scrap_risk > 80:  # high risk task - task should be ON HOLD
                    report.append(f"{prefix}[HIGH RISK] **{task.name}** (Risk of being cancelled: {scrap_risk:.1f}%)")
                    report.append(f"{prefix}Action: ON HOLD the task...")
                    continue

                elif scrap_risk > 50:  # medium risk task - task should be performed TENTATIVELY
                    report.append(f"{prefix}[MEDIUM RISK] **{task.name}** (Risk of being cancelled: {scrap_risk:.1f}%)")
                    report.append(f"{prefix}Action: {tag}")
                    continue
                else: 
                    # if scrap risk is low, check if the task is a micro-batch start
                    action_tag = "Micro-batch start" if is_micro_batch_start else "Normal start"
                    report.append(f"{prefix}[LOW RISK] **{task.name}** (Risk of being cancelled: {scrap_risk:.1f}%)")
                    report.append(f"{prefix}Action: {tag}")
            report.append("")

        # ========================== INFRASTRUCTURE PASS ==========================
        if infrastructure_queue:
            report.append("Infrastructure tasks detected... scheduling infrastructure tasks...")
            for i, task in enumerate(infrastructure_queue):
                report.append(f"   {i+1}. **{task.name}**")
                report.append("   Action: Schedule the task...")
                report.append("   Risk of being cancelled: 0.0% (Infrastructure tasks are not considered for risk analysis)")
            report.append("")

        if not report:
            return "No tasks ready to schedule. All tasks are waiting on dependencies."

        return "\n".join(report)
