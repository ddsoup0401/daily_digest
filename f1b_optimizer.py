from typing import List, Optional, Tuple
from models import Task, TeamType, TaskCategory, ProjectStage, TaskStatus

class Optimizer:
    def __init__(self, graph_manager, max_risk_inventory: float = 2.5):
        self.gm = graph_manager
        self.max_risk_inventory = max_risk_inventory # max risk inventory for the project

    
    def classify_task_direction(self, task: Task) -> str: 
        """
        Classify the task into either Forward Pass or Backward Pass  
        """
        if task.category == TaskCategory.SUPPORT:
            return "SUPPORT"
        if task.team == TeamType.HARDWARE:
            return "FORWARD"
        return "BACKWARD"
    
    def calculate_scrap_risk_score(self, task: Task) -> float:
        """
        Calculate the scrap risk score for a task (based on volatility of self and dependencies)
        if the risk score is high, the task is more likely to be cancelled.
        """
        risk_score = 0.0

        task_category = task.category
        if task_category == TaskCategory.INFRASTRUCTURE:
            return 0.0
        
        if task.team == TeamType.SOFTWARE:
            return 0.0
        
        for dep in task.dependencies:
            dep_task = self.gm.get_task(dep)
            if dep_task: 
                risk_score += dep_task.volatility * 100 
        
        return min(risk_score, 100)
    
    def calculate_risk_inventory(self) -> float: 
        """
        Calculate the risk inventory for the project (sum of volatility of all incomplete HW tasks)
        """
        current_risk_inventory = 0.0
        for task in self.gm.get_all_tasks():
            if task.team == TeamType.HARDWARE: 
                if task.status == TaskStatus.DONE:
                    continue
                if task.category in [TaskCategory.SUPPORT, TaskCategory.INFRASTRUCTURE]:
                    continue
                risk = task.volatility 
                current_risk_inventory += risk
        return current_risk_inventory

    def calculate_downstream_dependencies(self, task_id: str) -> int:
        """
        Calculate the number of downstream dependencies for a task --> used for sorting the forward queue
        """ 
        downstream_dependencies = 0
        for id in self.gm.tasks:
            task = self.gm.get_task(id)
            if task and task.dependencies and task_id in task.dependencies:
                if task.status != TaskStatus.DONE:
                    downstream_dependencies += 1
        return downstream_dependencies
    
    def get_swarming_recommendation(self) -> Optional[Tuple[str, str]]:
        """
        Returns (Target SW Name, Recommended Action String) if supporting is needed.
        Used by both the Report and the Task Creation Wizard.
        """
        backward_queue = []
        for task in self.gm.get_ready_tasks():
            if self.classify_task_direction(task) == "BACKWARD":
                backward_queue.append(task)
        
        target_sw = self.get_swarming_backward_task(backward_queue)
        if target_sw:
            target_hw_name = "Hardware"
            for dep in target_sw.dependencies:
                hw = self.gm.get_task(dep)
                if hw: 
                    target_hw_name = hw.name
                    break
            
            recommendation = f"Build Test Jig for '{target_sw.name}' (Validates {target_hw_name})"
            return (target_sw.name, recommendation)
        return None
     
    def get_swarming_backward_task(self, backward_queue: List[Task]) -> Optional[Task]:
        """
        choose swarming backward task from the backward queue
        """ 
        if not backward_queue:
            return None
        
        def get_target_hw_impact(sw_task: Task) -> int:
            max_impact = -1
            # SW task's dependencies are the target HW
            for hw_id in sw_task.dependencies:
                hw_task = self.gm.get_task(hw_id)
                if hw_task and hw_task.team == TeamType.HARDWARE:
                    # Calculate the structural importance of the target HW
                    impact = self.calculate_downstream_dependencies(hw_id)
                    if impact > max_impact:
                        max_impact = impact
            return max_impact

        sorted_backward_queue = sorted(backward_queue, key=get_target_hw_impact, reverse=True)
        return sorted_backward_queue[0]

    def run_scheduler(self, assigner_filter: Optional[str] = None, current_time_step: Optional[int] = None) -> str:
        """
        Run the scheduler to schedule the tasks --> this is the main algorithm 
        """
        # 1. Get all the tasks that are ready to be scheduled
        backward_queue = [] # Priority 1. Backward (BringUp / Calibration)
        forward_queue = [] # Priority 2. Forward (Fabrication / Design)
        infrastructure_queue = [] # Priority 3. Infrastructure (Infrastructure)
        support_queue = [] 
        ready_tasks = self.gm.get_ready_tasks()

        for task in ready_tasks: 
            direction = self.classify_task_direction(task)

            if direction == "BACKWARD":
                backward_queue.append(task)
            elif direction == "SUPPORT":
                support_queue.append(task)
            elif direction == "FORWARD":
                forward_queue.append(task)
            elif task.category == TaskCategory.INFRASTRUCTURE:
                infrastructure_queue.append(task)
            
        report = []
        # ========================== risk inventory check ==========================
        current_inventory = self.calculate_risk_inventory()
        is_risk_inventory_exceeded = current_inventory >= self.max_risk_inventory
        sat_percent = (current_inventory / self.max_risk_inventory) * 100
        status_icon = "🔴" if is_risk_inventory_exceeded else "🟢"
        report.append(f"{status_icon} [Risk Inventory] {current_inventory:.1f} / {self.max_risk_inventory} ({sat_percent:.0f}%)")

        # ========================== BACKWARD PASS ==========================
        if backward_queue:
            report.append("[P1: BACKWARD] Software Validation")
            backward_queue.sort(key=lambda t: -self.calculate_downstream_dependencies(t.id)) 

            for t in backward_queue:
                is_mb = any(
                    self.gm.get_task(p).progress < 1.0 
                    for p in t.dependencies if self.gm.get_task(p)
                )
                tag = " (Micro-batch)" if is_mb else ""
                report.append(f"   - **{t.name}**{tag} -> {t.id} -> Action: VALIDATE")
            report.append("")

        # ========================== SUPPORT PASS ==========================
        if support_queue or is_risk_inventory_exceeded:
            report.append("[P2: SUPPORT] Support Tasks")
            if support_queue:
                for t in support_queue:
                     report.append(f"   - **{t.name}** -> {t.id} -> Action: ASSIST SW Team")
            
            if is_risk_inventory_exceeded and not support_queue and backward_queue:
                target_sw = self.get_swarming_backward_task(backward_queue)
                if target_sw:
                    # find the target HW name for reporting
                    target_hw_name = "Unknown HW"
                    for dep in target_sw.dependencies:
                        hw = self.gm.get_task(dep)
                        if hw: 
                            target_hw_name = hw.name
                            break
                        
                    report.append(f"     [Action Required] Risk Full! HW Team must help.")
                    report.append(f"     Target SW: '{target_sw.name}' ({target_sw.id}) (Validates bottleneck '{target_hw_name}')")
                    report.append(f"     Recommended: '{target_sw.id} -> Build Test for {target_hw_name}'")
            report.append("")

        # ========================== FORWARD PASS ==========================
        if forward_queue:
            if is_risk_inventory_exceeded:
                report.append(f"[P3: FORWARD] Fabrication BLOCKED (Risk Budget Full)")
                report.append(f"      Reason: System unstable. Execute Support tasks.")
            else:
                report.append("[P3: FORWARD] Fabrication & Design")
                # Sort the forward queue from lowest to highest scrap risk score to minimize the risk of cancellation
                forward_queue.sort(key=lambda t: -self.calculate_downstream_dependencies(t.id))

                for t in forward_queue:
                    impact = self.calculate_downstream_dependencies(t.id)
                    scrap_risk = self.calculate_scrap_risk_score(t)

                    is_micro_batch = any(
                        self.gm.get_task(p).progress < 1.0 
                        for p in t.dependencies if self.gm.get_task(p)
                    )

                    prefix = f"   - **{t.name}** ({t.id}) (Unblocks: {impact})"

                    if scrap_risk > 80:
                        report.append(f"{prefix} [RISK: {scrap_risk:.0f}%] -> Action: HOLD (Too Volatile)")
                    elif scrap_risk > 50:
                        action_tag = "Micro-batch TENTATIVE" if is_micro_batch else "TENTATIVE Start"
                        report.append(f"{prefix} [RISK: {scrap_risk:.0f}%] -> Action: {action_tag}")
                    else:
                        action_tag = "Micro-batch START" if is_micro_batch else "Normal START"
                        report.append(f"{prefix} -> Action: {action_tag}")
                        
            report.append("")

        # ========================== INFRASTRUCTURE PASS ==========================
        if infrastructure_queue and (not report or report[-1].startswith("🔒")):
            report.append("[P4: INFRASTRUCTURE] Infrastructure Tasks")
            for t in infrastructure_queue:
                report.append(f"   - **{t.name}** -> {t.id} -> Action: SCHEDULE")
            report.append("")
        
        if not report: 
            return "System Idle."

        return "\n".join(report)
