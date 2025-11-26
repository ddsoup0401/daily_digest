import networkx as nx
from typing import List, Dict

from numpy.random import f
from models import Task, TaskStatus

class DependencyGraph:
    def __init__(self):
        self.graph = nx.DiGraph() # Directed Graph to represent the dependencies between tasks
        self.tasks: Dict[str, Task] = {} # Mapping of task ID to Task object
        
    def add_task(self, task: Task):
        """
        Add a task to the graph
        """
        self.tasks[task.id] = task
        self.graph.add_node(task.id, data=task)
        for dependency in task.dependencies:
            if dependency in self.tasks:
                self.graph.add_edge(dependency, task.id)
                  
    def get_ready_task(self, task_id: str) -> Task:
        """
        Get a ready task to be worked on
        """
        ready_tasks = []
        for task_id in self.graph.nodes(data=True):
            if self.tasks[task_id].status != TaskStatus.PENDING:
                continue
            predecessors = list(self.graph.predecessors(task_id))
            all_done = True
            for pred_id in predecessors:
                if self.tasks[pred_id].status != TaskStatus.DONE:
                    all_done = False
                    break
            
            if all_done:
                ready_tasks.append(task_id)
        return ready_tasks   
    
    