# daily_digest

### The 1F1B Scheduling Engine for Robotics

This is a project management operating system designed for hardware/software co-development. It adapts the 1F1B (One Forward, One Backward) pipelining strategy from Deep Learning to manage engineering risk, prevent cascading failures, and maximize development velocity.

The Philosophy: Why 1F1B?

Traditional project management (Waterfall/Agile) is inefficient in hardware development because it creates "physical debt" that software must validate.

Forward Pass (Hardware): Creates state. Every finished HW component is Risk Inventory (unvalidated debt).

Backward Pass (Software): Calculates gradients. Validating HW removes the risk and clears the inventory.

VRAM Limit (Risk Budget): Just as a GPU runs out of memory, an engineering team runs out of capacity to handle unvalidated hardware. When this limit is reached, production must stop.

## Key Features

1. Risk Inventory Limiter (The Safety Valve)

We define a MAX_RISK_INVENTORY (e.g., 2.5 units).

Every time a HW task finishes (DONE), it enters WAITING_FOR_VALIDATION state, filling up the inventory.

If Inventory > Limit: The system triggers a HARD STOP on all new Fabrication (Forward) tasks.

To Resume: You must complete SW Validation (Backward) tasks to clear the inventory.

2. Bottleneck-First Sorting (The Speed Engine)

Unlike traditional tools that sort by date, PipeSync v2 sorts Forward tasks by Bottleneck Impact.

Logic: sort(key= -downstream_block_count)

Effect: The task blocking the most downstream people is always at the top, regardless of its individual risk. We prioritize Flow 

3. Swarming/Supporting Mode (The Crisis Protocol)

When the Risk Inventory is full, the HW team doesn't just sit idle.

Trigger: Risk Inventory Saturated.

Action: The system recommends Support Tasks for the Hardware team.

Example: "SW-1 is stuck. HW Team, stop building Arm-2 and build a Test Jig for SW-1."

This accelerates the Backward Pass, clearing risk faster.

4. Concurrency & Micro-batching

Milestones: SW doesn't wait for HW to be 100% DONE. If HW hits a "Interface Frozen" milestone, SW becomes Ready.

Result: HW Fabrication and SW Baseline Development run concurrently, reducing pipeline bubbles.

## The Logic Flow

graph TD
    A[Start Tick] --> B{Risk Inventory Full?}
    
    %% Normal Flow
    B -- NO --> C[Check Backward Queue]
    C --> D{SW Tasks Ready?}
    D -- YES --> E[P1: Execute Backward (SW)]
    D -- NO --> F[P3: Execute Forward (HW)]
    F --> G[Sort by Bottleneck Impact]
    
    %% Crisis Flow
    B -- YES (Crisis) --> H[Block Forward Pass]
    H --> I[Find Critical SW Bottleneck]
    I --> J[P2: Trigger Swarming/Support]
    J --> K[Assign HW to Support SW]


## Task States & Lifecycle

This introduces a strict lifecycle to ensure risk accounting:

PENDING: Task created.

IN_PROGRESS: Work started.

WAITING_FOR_VALIDATION (HW Only): HW is physically done, but SW hasn't signed off. Risk counts against inventory here.

DONE (Risk Free):

SW: Validation complete. Clears its own risk.

HW: Only becomes DONE when ALL linked SW validators are DONE.

## Usage Guide

Initialization

Set your organization's risk tolerance.

Set Max Risk Inventory (Risk Budget) (2.5): 2.0


The Dashboard

The UI is divided into actionable sections by priority:

[P1: BACKWARD]: SW Team's priority. Clear these to free up the budget.

[P2: SWARMING/SUPPORT]: Emergency tasks for HW team to help SW team.

[P3: FORWARD]: HW Team's backlog. Sorted by impact.

[Risk Inventory]: The health bar of your project.

Commands

add: Wizard to create tasks.

Smart Input: Asks "HW or SW team?" first.

Auto-Link: If SW, asks "Which HW are you validating?"

Swarming: Automatically suggests Support tasks if the system is blocked.

update: Update progress/status.

Toxic Inheritance: Warns if you try to start a high-risk task without clearing dependencies.

The Loop: When you finish a Support task, it prompts you to finish the blocked SW task.

## Example Scenario (The Loop)

Saturation: HW team builds Leg and Arm. Inventory hits 100%.

Block: System locks Head Fabrication.

Swarm: System suggests: Build Test Jig for Leg FW.

Support: HW team builds the Jig (DONE).

Accelerate: SW team uses the Jig, finishes Leg FW quickly (DONE).

Release: Leg HW becomes DONE. Inventory drops to 50%.

Resume: System unlocks Head Fabrication.

## Installation

No external dependencies required other than rich and networkx

    %% pip install rich networkx pydantic
    python test.py


PipeSync v2 is not just a scheduler; it is a Risk Governance System that aligns engineering velocity with engineering integrity.
