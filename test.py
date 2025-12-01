from models import Task, TeamType, TaskStatus, ProjectStage, TaskCategory, MileStone
from graph_manager import DependencyGraph
from f1b_optimizer import Optimizer
from datetime import datetime
from typing import Tuple
import time

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

def check_project_completion(graph: DependencyGraph) -> Tuple[bool, int, int]:
    if not graph.tasks:
        return False, 0, 0 
    total_tasks = len(graph.tasks)
    done_sum = 0
    for t in graph.tasks.values():
        if t.status == TaskStatus.DONE:
            done_sum += 1
    return done_sum == total_tasks, done_sum, total_tasks 

def check_readiness_details(graph: DependencyGraph, task: Task) -> str:
    """
    Check the readiness details of a task
    """
    # 1. if task is done or in progress
    if task.status == TaskStatus.DONE: 
        return "[dim]Done[/]"
    if task.status == TaskStatus.WAITING_FOR_VALIDATION:
        return "[bold yellow]Wait Validation.[/]"
    if task.status == TaskStatus.IN_PROGRESS:
        return "[bold green]In Progress (Active)[/]"
    
    #2. if task is pending, check if all dependencies are done
    blockers = []
    for dep in task.dependencies:
        dep_task = graph.get_task(dep)
        if not dep_task: 
            continue
        if dep_task.status == TaskStatus.DONE or dep_task.status == TaskStatus.WAITING_FOR_VALIDATION:
            continue
        # if status is not done, check if milestone is reached 
        is_milestone_reached = False

        if dep_task.milestone and len(dep_task.milestone) > 0:
            milestone = dep_task.milestone[0]
            if milestone.trigger_process and dep_task.progress >= milestone.trigger_process:
                is_milestone_reached = True
        
        if not is_milestone_reached:
            current_status = f"{int(dep_task.progress * 100)}%"
            blockers.append(f"{dep_task.id}({current_status})")
    
    if blockers:
        return f"[red]Wait: {', '.join(blockers)}[/]"
    return "[bold green]Ready.[/]"

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
        console.print(Panel("All modules completed. 'add' to add new issue.", style="green"))
        return 

    rec_text = optimizer.run_scheduler(current_time_step=1) 

    if rec_text is None:
        rec_text = " [System Warning] Optimizer returned no output (Check Logic)."

    console.print(Panel(rec_text, title="Decision", border_style="yellow"))

    table = Table(title="Real-time Task Status Board", expand=True)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Team", style="green") 
    table.add_column("Related", style="magenta")
    table.add_column("Role", style="white") 
    table.add_column("Risk", justify="right", style="red")
    table.add_column("Progress")
    table.add_column("Status")
    table.add_column("Ready?", style="bold white")

    task_sorted_by_stage = sorted(graph.tasks.values(), key=lambda t: (t.status == TaskStatus.DONE, t.id))

    for t in task_sorted_by_stage:
        risk = optimizer.calculate_scrap_risk_score(t)
        risk_str = f"{risk:.0f}%" if risk > 0 else "-"

        related_str = ""
        if t.team == TeamType.SOFTWARE and t.dependencies:
            # SW validates the HW
            related_str = f"Validates: {', '.join(t.dependencies)}"
        elif t.team == TeamType.HARDWARE and t.dependencies:
            # HW has dependencies
            related_str = f"Prereq: {', '.join(t.dependencies)}"

        if t.category == TaskCategory.SUPPORT:
            role_str = f"[bold magenta]SUPPORT[/]"
            team_str = f"[magenta]{t.team.value.upper()}[/]"
        else:
            role_str = t.stage.value.split('.')[1].strip()
            team_str = t.team.value.upper()
        
        bars = "▮" * int(t.progress * 10)
        empty = "┈" * (10 - int(t.progress * 10))
        prog_color = "green" if t.progress == 1.0 else "yellow"
        prog_vis = f"[{prog_color}]{bars}[/][dim]{empty}[/][white] {int(t.progress*100)}%[/]"
        
        if t.status == TaskStatus.DONE:
            status_vis = "[green]DONE[/]"
        elif t.status == TaskStatus.WAITING_FOR_VALIDATION:
            status_vis = "[bold yellow]WAIT VALID[/]"
        elif t.status == TaskStatus.IN_PROGRESS:
            status_vis = "[bold blue]IN PROGRESS[/]"
        else:
            status_vis = "[bold red]BLOCKED[/]"
        
        table.add_row(
            t.id, team_str, related_str, role_str, risk_str, prog_vis, status_vis, 
            check_readiness_details(graph, t) 
        )
        
    console.print(table)
    console.print("\n")

def create_task_wizard(graph: DependencyGraph, optimizer: Optimizer):
    rprint("[bold white on blue] --- Add New Task --- [/]")
    
    rprint("Select Owner Team:")
    rprint(" 1. Hardware Team")
    rprint(" 2. Software Team")

    try: 
        team_idx = int(Prompt.ask("Number", default="1"))
        if team_idx == 1:
            team = TeamType.HARDWARE
        elif team_idx == 2:
            team = TeamType.SOFTWARE
        else:
            team = TeamType.HARDWARE        
    except: 
        team = TeamType.HARDWARE

    is_support = False
    default_task_name = None
    if team == TeamType.HARDWARE:
        recommendation = optimizer.get_swarming_recommendation()
        if recommendation:
            rprint(f"\n[bold orange3] ALERT: Supporting Recommended![/]")
            rprint(f"Target SW: {recommendation[0]} ({recommendation[1]})")
            if Confirm.ask("Create this Support Task?", default=True):
                is_support = True
                default_task_name = recommendation[1]
            
        if not is_support:
            if Confirm.ask("Is this a Supporting Task? (HW helping SW)", default=False):
                is_support = True
    
    tid = get_input("Task ID")
    if graph.get_task(tid): 
        rprint("[red]Task ID already exists.[/]"); return
    
    name = get_input("Task Name", default=default_task_name)
    component_id = get_input("Component Name", default="Leg")

    if is_support:
        stage = ProjectStage.FABRICATION 
        category = TaskCategory.SUPPORT
    else:
        category = TaskCategory.CRITICAL
        stage_choices = [s.value for s in ProjectStage]
        rprint("Stage Selection:")
        for i, s in enumerate(stage_choices): 
            rprint(f" {i+1}. {s}")
        try: 
            idx = int(Prompt.ask("Number", default="3")) - 1
            stage = ProjectStage(stage_choices[idx])
        except: 
            stage = ProjectStage.FABRICATION
    
    exp_time = FloatPrompt.ask("Expected Time", default=4.0)

    dependencies = []
    if team == TeamType.SOFTWARE and category == TaskCategory.CRITICAL:
        target = get_input("Target HW Task ID to Validate")
        if target: 
            dependencies.append(target)
    else:
        deps = get_input("Dependencies (comma separated)", default="")
        deps = deps.replace('(', '').replace(')', '')
        dependencies = [d.strip() for d in deps.split(',') if d.strip()]

    milestones = []
    if team == TeamType.HARDWARE and category == TaskCategory.CRITICAL:
        if Confirm.ask("Add Milestone for Concurrent SW Start?", default=True):
            pct = FloatPrompt.ask("Trigger Percentage (0.0-1.0)", default=0.5)
            milestones.append(MileStone(name="Interface Frozen", trigger_process=pct))
    
    new_task = Task(
        id=tid, name=name, team=team, assigner="User",
        component_id=component_id, stage=stage,
        expected_duration=exp_time, dependencies=dependencies,
        volatility=0.1, category=category, milestone=milestones
    )
    if graph.add_task(new_task): 
        rprint("[green]Added![/]"); time.sleep(1)
    else: 
        rprint("[red]Error.[/]"); time.sleep(2)

def main():
    graph = DependencyGraph()
    rprint("[bold white on blue] --- Program Start Up --- [/]")
    risk_limit = FloatPrompt.ask("Set Max Risk Inventory (Risk Budget)", default=2.5)
    optimizer = Optimizer(graph, max_risk_inventory=risk_limit)
    
    if not graph.tasks:
        # HW completed -> Validation waiting (Inventory)
        graph.add_task(Task(id='HW-1', name='Leg Design', team=TeamType.HARDWARE, assigner='A', component_id='Leg', stage=ProjectStage.ARCHITECTURE, expected_duration=4.0, status=TaskStatus.WAITING_FOR_VALIDATION, progress=1.0, volatility=0.9))
        
        # HW in progress (Milestone reached)
        graph.add_task(Task(id='HW-2', name='Leg Fab', team=TeamType.HARDWARE, assigner='A', component_id='Leg', stage=ProjectStage.FABRICATION, expected_duration=8.0, dependencies=['HW-1'], status=TaskStatus.IN_PROGRESS, progress=0.6, volatility=0.9, milestone=[MileStone(name="MB", trigger_process=0.5)]))
        
        # SW waiting (HW-2 validation)
        graph.add_task(Task(id='SW-2', name='Leg FW', team=TeamType.SOFTWARE, assigner='B', component_id='Leg', stage=ProjectStage.BASELINE, expected_duration=8.0, dependencies=['HW-2'], status=TaskStatus.PENDING, progress=0.0, volatility=0.1))

    while True:
        display_project_status(graph, optimizer)
        cmd = Prompt.ask("Command", choices=["add", "update", "quit"], default="update")
        
        if cmd == "add":
            create_task_wizard(graph, optimizer)
        elif cmd == "update":
            tid = get_input("Update Task ID")
            task = graph.get_task(tid)
            if task:
                rprint(f"Status: [cyan]{task.status.name}[/], Progress: [cyan]{task.progress*100:.0f}%[/], Volatility: [red]{task.volatility}[/]")

                if Confirm.ask("Plan Change (Volatility Update)?", default=False):
                    new_vol = FloatPrompt.ask("New Volatility", default=task.volatility)
                    graph.update_task_volatility(tid, new_vol)
                    
                    task_risk_score = optimizer.calculate_scrap_risk_score(task)
                    rprint(f"[bold magenta] ► {tid} Volatility updated to: {new_vol:.2f}[/]")
                    rprint(f"[bold dim]    (Current Task's Scrap Risk Score remains {task_risk_score:.0f}%, as risk is calculated from its UPSTREAM dependencies.)[/]")

                    dependents = [t for t in graph.tasks.values() if tid in t.dependencies]
                    if dependents:
                        rprint("[bold yellow] ► Immediate Downstream Impact:[/]")
                        for dep_task in dependents:
                            dep_risk = optimizer.calculate_scrap_risk_score(dep_task)
                            rprint(f"    - {dep_task.id} ({dep_task.name}) New Scrap Risk: {dep_risk:.0f}%")
                    
                    if new_vol >= 0.8: 
                        rprint("[bold red] Warning: High Volatility. Downstream scrap risk is critical.[/]")
                        if Confirm.ask("Force reset all downstream tasks to 0%?", default=True):
                            reset_list = graph.reset_downstream_tasks(tid)
                            rprint(f"[bold yellow] Reset: {', '.join(reset_list)}[/]")
                        if Confirm.ask(f"Also reset this task ({tid}) to 0%?", default=True):
                            graph.update_task_progress(tid, 0.0, TaskStatus.PENDING.value)
                            rprint(f"[bold yellow] Self Reset: {tid} is now PENDING (0%)[/]")
                    else:
                        rprint("[green]Volatility updated.[/]")
                        
                elif Confirm.ask("Task Completed?", default=False):
                    graph.update_task_progress(tid, 1.0, TaskStatus.DONE.value)
                    
                    if task.team == TeamType.SOFTWARE:
                        rprint("[green]SW Completed! Target HW Risk Cleared.[/]")
                    else:
                        rprint("[yellow]HW Completed! Status -> WAITING FOR VALIDATION.[/]")
                        
                else:
                    new_prog = FloatPrompt.ask("New Progress", default=task.progress)
                    
                    current_risk = optimizer.calculate_scrap_risk_score(task)
                    if current_risk > 50 and new_prog > 0.0:
                        rprint(f"[bold red]VIOLATION: High Risk ({current_risk}%).[/]")
                        if Confirm.ask("Override safety and start?", default=False):
                            graph.update_task_volatility(tid, 0.8) 
                            rprint(f"[bold orange3] TOXIC INHERITANCE: {tid} Volatility set to 0.8[/]")
                        else:
                            continue 
                    graph.update_task_progress(tid, new_prog, TaskStatus.IN_PROGRESS.value)
                    rprint("[green]Update completed.[/]")
            else:
                rprint("[red]Not found.[/]")
            time.sleep(1)
        elif cmd == "quit":
            break

if __name__ == "__main__":
    main()