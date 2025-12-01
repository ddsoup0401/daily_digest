import networkx as nx
import json 
from typing import List, Dict, Optional
from models import Task, TaskStatus, TeamType
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
    
    def get_task(self, task_id: str) -> Optional[Task]:
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
            if task.status == TaskStatus.DONE or task.status == TaskStatus.IN_PROGRESS or task.status == TaskStatus.WAITING_FOR_VALIDATION:
                continue
            
            pred = list(self.graph.predecessors(task_id))
            dependencies_met = True

            for dep in pred:
                if dep not in self.tasks:
                    dependencies_met = False
                    break
                dep_task = self.tasks[dep]

                # case 1: dependency is done
                if dep_task.status == TaskStatus.DONE or dep_task.status == TaskStatus.WAITING_FOR_VALIDATION:
                    continue

                # case 2: milestone is reached
                if dep_task.milestone and len(dep_task.milestone) > 0: 
                    milestone = dep_task.milestone[0] 
                    if milestone.trigger_process and dep_task.progress >= milestone.trigger_process:
                        continue
                
                # case 3: if dependency is not done or milestone is not reached, set dependencies_met to False and break
                dependencies_met = False
                break  

            # if dependencies_met is True, add the task to the ready_tasks list
            if dependencies_met:
                ready_tasks.append(task)
        
        return ready_tasks 

    def update_task_progress(self, task_id: str, progress: float, status_str: str):
        """
        Update progress and status for a task.
        if HW task is done, maintain the volatility 
        once the related SW task is done, change the volatility of the dependent HW task(s) to 0.0 
        """
        if task_id in self.tasks:
            self.tasks[task_id].progress = progress
            try: 
                current_task = self.tasks[task_id]
                new_status = TaskStatus(status_str)
                current_task.status = new_status

                if new_status == TaskStatus.DONE and current_task.team == TeamType.HARDWARE:
                    successors = list(self.graph.successors(task_id))
                    sw_successors = []
                    for s in successors:
                        if s not in self.tasks:
                            continue
                        task = self.tasks[s]
                        if task.team == TeamType.SOFTWARE:
                            sw_successors.append(task)

                    all_validators_done = True
                    for sw in sw_successors:
                        if sw.status != TaskStatus.DONE:
                            all_validators_done = False
                            break
                    # all dependent SW tasks are done
                    if all_validators_done:
                        current_task.status = TaskStatus.DONE
                        current_task.volatility = 0.0
                    else:
                        current_task.status = TaskStatus.WAITING_FOR_VALIDATION
                else:
                    # SW or other tasks are directly updated to the new status
                    current_task.status = new_status
                    
                if new_status == TaskStatus.DONE and current_task.team == TeamType.SOFTWARE:
                    current_task.volatility = 0.0

                    for dep in current_task.dependencies:
                        if dep in self.tasks:
                            hw_task = self.tasks[dep]
                            if hw_task.team == TeamType.HARDWARE:
                                successors = list(self.graph.successors(dep))
                                sw_successors = []
                                for s in successors:
                                    if s not in self.tasks:
                                        continue
                                    task = self.tasks[s]
                                    if task.team == TeamType.SOFTWARE:
                                        sw_successors.append(task)

                                all_validators_done = True
                                for sw in sw_successors:
                                    if sw.status != TaskStatus.DONE:
                                        all_validators_done = False
                                        break
                                if all_validators_done:
                                    hw_task.status = TaskStatus.DONE
                                    hw_task.volatility = 0.0
                
                current_task.updated_at = datetime.now()
            except ValueError:
                pass
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
            task = self.get_task(desc)
            if task and (task.progress > 0.0 or task.status == TaskStatus.DONE):
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
    
