from typing import List, Dict
from models import Task, TeamType, TaskStatus
import heapq

class Optimizer:
    def __init__(self, graph_manager):
        self.gm = graph_manager
    
    def calculate_parallel_score(self, prev_task: Task, next_task: Task) -> float:
        """
        Calculate the potential for parallel operations for two tasks
        To calculate the score: 
        Score = (time_gain * Stability * 5) - (Switch_cost * 1) 
        - weight : 5 for time_gain and Stability, 1 for Switch_cost
        - time_gain : How much time can be saved by parallelizing the tasks
        - Stability : How much the tasks are likely to change
        - Switch_cost : How much it costs to switch to a different task

        ==> If Score > 0, then the tasks can be parallelized 
        ==> If Score < 0, then the tasks cannot be parallelized
        """
        threshold = 0.7 
        if prev_task.progress < threshold:
            return -1.0 

        # Calculate the time gain 
        time_gain = prev_task.expected_time * (1.0 - prev_task.progress)
        stability = 1.0 - prev_task.volatility
        switch_cost = next_task.context_cost
        score = (time_gain * stability * 5) - (switch_cost * 1)
        return score
    
    def run_1f1b_schedule(self, current_time_step):
        """
        Run the 1F1B schedule for the current time step to determine the optimal task to work on
        """
        recommendation = [] # List of recommended tasks to work on
        feedback_queue = [] # Backward Passes (High Priority)
        forward_queue = []  # Forward Passes (Normal Priority)

        ready_tasks = self.gm.get_ready_tasks()
        # this is adapted from the 1f1b logic 
        for task_id in ready_tasks:
            if task_id.is_feedback_task:
                feedback_queue.append(task_id)
            else:
                forward_queue.append(task_id)
        
        # Decide the next action for the hardware team 
        hw_recommendation = self._decide_next_action(
            TeamType.HARDWARE, 
            feedback_queue, 
            forward_queue
        )
        
        # TODO: Add the logic for the software team and other teams
        
        return hw_recommendation

    def _decide_next_action(self, team_type, feedback_queue: List[Task], forward_queue: List[Task]):
        """
        Decide the next action for the given team type
        - feedback_queue : List of feedback tasks
        - forward_queue : List of forward tasks
        - return : List of recommended tasks to work on
        """
        # 1f1b logic: 
        # - Feedback tasks are prioritized over forward tasks
        # - Forward tasks are prioritized based on the score
        if feedback_queue:
            task = feedback_queue[0]
            return f("Stop new design and start working on {task.name} for team {task.team.value}")
        if forward_queue:
            best_task = None
            max_score: float = -float('inf')
            for task in forward_queue:
                score = score = task.expected_time - task.switch_cost/2 
                if score > max_score:
                    max_score = score
                    best_task = task
            if best_task:
                return f"Start {best_task.name} for Team {best_task.team.value}."
        return "Coffee Break ~~~"