from models import Task, TeamType, TaskStatus, ProjectStage, TaskCategory
from graph_manager import DependencyGraph
from f1b_optimizer import Optimizer
from datetime import datetime
import time
import sys

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, FloatPrompt, Confirm
from rich import print as rprint

console = Console()

def get_input(prompt_text, default=None): 
    if default is not None:
        return Prompt.ask(f"[bold cyan]{prompt_text}[/]", default=str(default))
    return Prompt.ask(f"[bold cyan]{prompt_text}[/]")

def check_project_completion(graph: DependencyGraph) -> bool:
    if not graph.tasks:
        return False, 0, 0 
    total_tasks = len(graph.tasks)
    done_tasks = sum(1 for t in graph.tasks.values() if t.status == TaskStatus.DONE)
    return done_tasks == total_tasks, done_tasks, total_tasks 

def display_project_status(graph: DependencyGraph, optimizer: Optimizer):
    """
    Display the project status in a table
    """
    console.clear()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    is_completed, done_tasks, total_tasks = check_project_completion(graph)

    header_color = "green" if is_completed else "navy_blue"
    title_text = "Project Completed" if is_completed else "Project In Progress" 

    console.print(Panel(
        f"[bold bright_white on {header_color}]{title_text}[/]\n"
        f"Current Time: {now}", 
        style=f"on {header_color}",
        title_align="left"
    ))

    if is_completed:
        print(Panel(Panel("All modules completed. 'add' to add new issue.", style="green")))
        return 

    rec_text = optimizer.run_scheduler(current_time_step=1) 

    if rec_text is None:
        rec_text = " [System Warning] Optimizer returned no output (Check Logic)."

    console.print(Panel(rec_text, title="Decision", border_style="yellow"))

    table = Table(title="Real-time Task Status Board", expand=True)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Module", style="green")
    table.add_column("Stage", style="white")
    table.add_column("Risk", justify="right", style="red")
    table.add_column("Progress")
    table.add_column("Status")

    task_sorted_by_stage = sorted(graph.tasks.values(), key=lambda t: (t.status == TaskStatus.DONE, t.id))

    for t in task_sorted_by_stage:
        risk = optimizer.calculate_scrap_risk_score(t)
        risk_str = f"{risk:.0f}%" if risk > 0 else "-"
        
        bars = "▮" * int(t.progress * 10)
        empty = "┈" * (10 - int(t.progress * 10))
        prog_color = "green" if t.progress == 1.0 else "yellow"
        prog_vis = f"[{prog_color}]{bars}[/][dim]{empty}[/][white] {int(t.progress*100)}%[/]"
        
        status_color = "green" if t.status == TaskStatus.DONE else "bright_yellow" if t.status == TaskStatus.IN_PROGRESS else "dim"
        
        table.add_row(
            t.id, t.component_id, t.stage.value.split('.')[1].strip(), 
            risk_str, prog_vis, f"[{status_color}]{t.status.name.upper()}[/]"
        )
        
    console.print(table)
    console.print("\n")

def create_task_wizard(graph: DependencyGraph):
    rprint("[bold white on blue] --- Add New Task --- [/]")
    tid = get_input("Task ID")

    if graph.get_task(tid): 
        return
    
    name = get_input("Task Name")
    component_id = get_input("Component Name", default="Leg")
    
    stage_choices = [s.value for s in ProjectStage]
    rprint("Stage Selection:")

    for i, s in enumerate(stage_choices): 
        rprint(f" {i+1}. {s}")

    try: idx = int(Prompt.ask("Number", default="3")) - 1; stage = ProjectStage(stage_choices[idx])
    except: stage = ProjectStage.FABRICATION

    team = TeamType.SOFTWARE if stage in [ProjectStage.BRINGUP, ProjectStage.TESTING] else TeamType.HARDWARE
    exp_time = FloatPrompt.ask("Expected Time", default=4.0)
    deps = get_input("Dependent Task ID (comma separated list, empty for none)", default="")
    dependencies = [d.strip() for d in deps.split(',') if d.strip()]

    new_task = Task(
        id=tid, name=name, team=team, assigner="User",
        component_id=component_id, stage=stage,
        expected_duration=exp_time, dependencies=dependencies,
        volatility=0.1, category=TaskCategory.CRITICAL
    )
    if graph.add_task(new_task): 
        rprint("[green]Added successfully.[/]"); time.sleep(1)
    else: 
        rprint("[red]Circular dependency error.[/]"); time.sleep(2)

def main():
    graph = DependencyGraph()
    optimizer = Optimizer(graph)
    
    # if not graph.tasks:
    #     # Demo Data
    #     graph.add_task(Task(id='HW-1', name='Leg CAD', team=TeamType.HARDWARE, assigner='Alice', component_id='Leg', stage=ProjectStage.ARCHITECTURE, expected_duration=4, status=TaskStatus.DONE, progress=1.0, volatility=0.1))
    #     graph.add_task(Task(id='HW-2', name='Leg Fabrication', team=TeamType.HARDWARE, assigner='Alice', component_id='Leg', stage=ProjectStage.FABRICATION, expected_duration=8, dependencies=['HW-1'], status=TaskStatus.IN_PROGRESS, progress=0.6, volatility=0.1))
    #     graph.add_task(Task(id='SW-1', name='Leg Firmware', team=TeamType.SOFTWARE, assigner='Bob', component_id='Leg', stage=ProjectStage.BASELINE, expected_duration=8, dependencies=['HW-1'], status=TaskStatus.IN_PROGRESS, progress=0.4, volatility=0.1))

    while True:
        display_project_status(graph, optimizer)
        cmd = Prompt.ask("Command", choices=["add", "update", "quit"], default="update")
        
        if cmd == "add":
            create_task_wizard(graph)
            
        elif cmd == "update":
            tid = get_input("Update Task ID")
            task = graph.get_task(tid)
            if task:
                rprint(f"Status: [cyan]{task.status.name}[/], Progress: [cyan]{task.progress*100:.0f}%[/], Volatility: [red]{task.volatility}[/]")
                
                # 1. Plan Change Scenario (Scrap Trigger)
                if Confirm.ask("Plan Change (Volatility Update)?", default=False):
                    new_vol = FloatPrompt.ask("New Volatility (0.0~1.0)", default=task.volatility)
                    graph.update_task_volatility(tid, new_vol)
                    
                    # CORE LOGIC: Cascading Reset Trigger
                    if new_vol >= 0.8: # Threshold: 0.8 or higher is considered "Scrap"
                        rprint("[bold red] Warning: Volatility is very high (High Volatility).[/]")
                        rprint("[red]All downstream tasks dependent on this task should be scrapped.[/]")
                        
                        if Confirm.ask("Force reset all downstream tasks to 0%?", default=True):
                            reset_list = graph.reset_downstream_tasks(tid)
                            if reset_list:
                                rprint(f"[bold yellow] The following tasks have been reset: {', '.join(reset_list)}[/]")
                            else:
                                rprint("[yellow]No downstream tasks to reset.[/]")
                        else:
                            rprint("[yellow]Skipping reset. (Risk Score only displayed in red)[/]")
                    else:
                        rprint("[green]Volatility updated. Risk Score recalculated.[/]")

                # 2. Progress Update
                elif Confirm.ask("Task completed?", default=False):
                    graph.update_task_progress(tid, 1.0, TaskStatus.DONE.value)
                    rprint("[green]Task completed![/]")
                else:
                    new_prog = FloatPrompt.ask("New Progress", default=task.progress)
                    graph.update_task_progress(tid, new_prog, TaskStatus.IN_PROGRESS.value)
                    rprint("[green]Update completed.[/]")
            else:
                rprint("[red]Not found.[/]")
            time.sleep(1.5)
            
        elif cmd == "quit":
            break

if __name__ == "__main__":
    main()