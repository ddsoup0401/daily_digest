import networkx as nx
import json 
from typing import List, Dict, Optional
from models import Task, TaskStatus
from datetime import datetime        
                                           
class DependencyGraph:
    def __init__(self, storage_file="tasks.json"):
        self.graph = nx.DiGraph() # Directed Graph to represent the dependencies between tasks
        self.tasks: Dict[str, Task] = {} # Mapping of task ID to Task object
        self.storage_file = storage_file 
        self.load_file()

    def add_task(self, task: Task):
        """
        Add a task to the graph & connect it to its dependencies
        """ 
        temp_graph = self.graph.copy()
        temp_graph.add_node(task.id)

        for dep in task.dependencies:
            if dep in self.tasks:
                temp_graph.add_edge(dep, task.id)
        
        # Check and prevent infinite loops (eg. A -> B ; B -> A)
        try:
            list(nx.find_cycle(temp_graph))
            return False # Cycle detected
        except nx.NetworkXNoCycle:
            pass

        self.tasks[task.id] = task
        self.graph = temp_graph
        self.save_file()
        return True
    
    def get_task(self, task_id: str):
        """
        Get a task by its ID
        """
        return self.tasks.get(task_id)
    
    def get_all_tasks(self) -> List[Task]:
        """
        Return all tasks in the graph
        """
        return list(self.tasks.values())
                  
    def get_ready_tasks(self) -> List[Task]:
        """
        Return tasks whose dependencies are: 
        1. PENDING or NOT_STARTED or IN_PROGRESS
        2. if pending, all dependencies must be done or milestones are met (if any)
        """
        ready_tasks = []

        for task_id in self.graph.nodes():
            if task_id not in self.tasks:
                continue
            task = self.tasks[task_id]

            # If the task is already done or in progress, skip it
            if task.status in [TaskStatus.DONE, TaskStatus.IN_PROGRESS]:
                continue
            
            pred = list(self.graph.predecessors(task_id))
            dependencies_met = True

            for dep in pred:
                if dep not in self.tasks:
                    dependencies_met = False
                    break
                dep_task = self.tasks[dep]

                # case 1: dependency is done
                if dep_task.status == TaskStatus.DONE:
                    continue

                # case 2: milestone is reached
                if dep_task.milestone and len(dep_task.milestone) > 0: 
                    milestone = dep_task.milestone[0] 
                    if milestone.trigger_process and dep_task.progress >= milestone.trigger_process:
                        continue
                
                dependencies_met = False
                break  

            if dependencies_met:
                ready_tasks.append(task)
        
        return ready_tasks 

    def update_task_progress(self, task_id: str, progress: float, status_str: str):
        """
        Update progress and status for a task.
        """
        if task_id in self.tasks:
            self.tasks[task_id].progress = progress
            self.tasks[task_id].status = TaskStatus(status_str)
            self.tasks[task_id].updated_at = datetime.now()
            self.save_file()

    def update_task_volatility(self, task_id: str, new_volatility: float):
        """
        Update the volatility for a task
        """
        if task_id in self.tasks:
            self.tasks[task_id].volatility = new_volatility
            self.save_file()
    
    def reset_downstream_tasks(self, task_id: str):
        """
        Reset the downstream tasks of a task
        """
        descendants = list(nx.descendants(self.graph, task_id))
        reset_tasks = []

        for desc in descendants:
            if desc not in self.tasks:
                continue
            task = self.tasks[desc]

            if task.status == TaskStatus.DONE or task.progress > 0.0: 
                task.progress = 0.0
                task.status = TaskStatus.PENDING
                task.updated_at = datetime.now()
                reset_tasks.append(task.id)
        
        if reset_tasks:
            self.save_file()

        return reset_tasks

    # ================ File Operations ================
    def save_file(self):
        """
        Save the tasks to the storage file
        """
        data = {tid: t.model_dump(mode='json') for tid, t in self.tasks.items()}
        with open(self.storage_file, 'w') as f:
            json.dump(data, f, indent=2)

    def load_file(self):
        """
        Load the tasks from the storage file
        """
        try:
            with open(self.storage_file, 'r') as f:
                data = json.load(f)
                for tid, t_data in data.items():
                    task = Task(**t_data)
                    self.tasks[tid] = task
                    self.graph.add_node(tid, data=task)
                    for dep in task.dependencies:
                        if dep in self.tasks:
                            self.graph.add_edge(dep, tid)
        except FileNotFoundError:
            pass
    
