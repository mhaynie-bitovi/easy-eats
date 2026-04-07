# Plan: Valet Parking Temporal Workshop (V1)

Create a V1 valet parking workflow as the starting codebase for a versioning workshop. A long-running workflow tracks each car from airport arrival through parking, waiting, retrieval, and departure. A load simulator keeps many concurrent workflows in flight — perfect for demonstrating why versioning matters (no clean break to push new code). Intentionally simple so attention stays on versioning strategies.

## Workflow Design

**ValetParkingWorkflow** — one instance per car:
1. `move_car` activity — move car from pickup zone to assigned parking spot
2. `workflow.sleep(trip_duration)` — simulates owner's trip (passed as input, e.g., 60-300s)
3. `move_car` activity — move car from parking spot back to pickup zone

Single `move_car` activity with parameterizable start/end locations. Parking and retrieval are the same operation — just moving a car from point A to point B.

Car info (license plate, owner, trip duration) is captured as workflow input — no need for a check-in activity. Keeping V1 minimal also leaves room for exercises to **add** a new activity (e.g., `notify_owner`, `charge_parking_fee`) as the NDE change to patch around.

No signals needed — each workflow is fully self-contained. The sleep makes workflows naturally long-running so there are always in-flight instances during exercises. `workflow.sleep()` is also deterministic and replay-safe, which is relevant to the patching topic.

## Data Model

All workflow/activity inputs and outputs are `@dataclass` classes defined in `models.py`. This is a new pattern for this project (existing modules use primitives), but appropriate for the workshop scope. Temporal Python SDK serializes `@dataclass` automatically.

- `ValetParkingInput` — workflow input: `license_plate: str`, `owner_name: str`, `trip_duration_seconds: int`
- `MoveCarInput` — activity input: `license_plate: str`, `from_location: str`, `to_location: str`
- `MoveCarOutput` — activity output: `license_plate: str`, `from_location: str`, `to_location: str`, `distance_driven: float`, `start_time: str`, `end_time: str`
- `ValetParkingOutput` — workflow output: `license_plate: str`

`MoveCarOutput` extends beyond `MoveCarInput` with operational data: `distance_driven` (random realistic value), `start_time` and `end_time` (ISO timestamps recorded by the activity).

## Steps

### Phase 1: Core module
1. `src/valet/__init__.py` — empty
2. `src/valet/models.py` — `ValetParkingInput`, `ValetParkingOutput`, `MoveCarInput`, `MoveCarOutput` dataclasses
3. `src/valet/activities.py` — `move_car` activity decorated with `@activity.defn`. Takes `MoveCarInput`, returns `MoveCarOutput`. Records `start_time`/`end_time` as ISO timestamps, generates random `distance_driven` (e.g., 0.1–2.0 miles). Uses `print()` for logging.
4. `src/valet/workflow.py` — `ValetParkingWorkflow` class:
   - Import `models.py` and `activities.py` inside `workflow.unsafe.imports_passed_through()` block
   - `run(self, input: ValetParkingInput) -> ValetParkingOutput`
   - First `move_car`: pickup_zone → parking spot (e.g., `"spot_A1"`)
   - `workflow.sleep(input.trip_duration_seconds)`
   - Second `move_car`: parking spot → pickup_zone
   - Each `execute_activity` call needs `start_to_close_timeout=timedelta(seconds=10)` — no `task_queue` override (inherits from worker)
   - Use `workflow.logger.info()` for all logging inside the workflow (replay-safe; `print()` fires on every replay which would be confusing during versioning exercises)
5. `src/valet/utils.py` — `generate_license_plate()` function: produces randomized US license plates (e.g., `"CA-7XYZ123"`). Used by starter and simulator.

### Phase 2: Worker and starters *(depends on Phase 1)*
6. `src/valet/worker.py` — worker on task queue `"valet"`, registers `ValetParkingWorkflow` + `move_car` activity. Pattern from `billing_worker.py`. Entry point: `if __name__ == "__main__"`.
7. `src/valet/starter.py` — starts one workflow with a generated license plate and short trip duration, calls `client.execute_workflow()` (blocking — waits for result), prints result. Workflow ID: `valet-{license_plate}`. Entry point: `if __name__ == "__main__"`.
8. `src/valet/simulator.py` — load generator:
   - Simple sequential loop: generate plate → `client.start_workflow()` (fire-and-forget, non-blocking) → `asyncio.sleep(random 2-10s)` → repeat
   - Randomized trip durations (60-300s)
   - Prints each started workflow ID by default
   - `--quiet` CLI flag (via `argparse`) to suppress per-workflow output
   - Runs indefinitely (Ctrl+C to stop)
   - Entry point: `if __name__ == "__main__"`

### Phase 3: Tests *(parallel with Phase 2)*
9. `tests/valet/__init__.py` + `tests/valet/test_workflow.py` — integration test using `WorkflowEnvironment.start_time_skipping()`:
   - Start workflow with short trip duration → assert it completes and returns expected `ValetParkingOutput`
   - Random UUID for task queue and workflow ID (pattern from `tests/helloworld/test_run_workflow.py`)
   - `@pytest.mark.asyncio` decorator (matches existing test pattern even though `asyncio_mode = "auto"`)

## Relevant files (existing patterns to reuse)
- `src/billing/billing_worker.py` — worker setup with multiple activities
- `src/billing/payment/payment_workflow.py` — multi-step workflow with `workflow.unsafe.imports_passed_through()`, `execute_activity` with `start_to_close_timeout`
- `src/billing/payment/payment_workflow_starter.py` — starter pattern with `client.execute_workflow()`
- `src/helloworld/workflows.py` — simple workflow with `unsafe.imports_passed_through()`
- `tests/helloworld/test_run_workflow.py` — async test with `WorkflowEnvironment.start_time_skipping()`, mocked activity pattern

## Verification
1. `python -m valet.worker` starts without errors
2. `python -m valet.starter` completes a single end-to-end workflow and prints result
3. `python -m valet.simulator` shows multiple concurrent workflows being started (workflow IDs printed); `--quiet` suppresses output
4. `pytest tests/valet/` passes (time-skipping makes sleep instant)
5. Temporal Web UI: workflows visible with `valet-{license_plate}` IDs, showing move_car activities and sleep timer

## Decisions
- **Task queue:** `"valet"` — single queue, single worker type
- **Workflow ID:** `valet-{license_plate}` — deterministic, easy to find in UI
- **No `task_queue` on `execute_activity`** — inherits from worker (simpler than billing pattern)
- **Logging:** `workflow.logger` in workflow, `print()` elsewhere — replay-safe logging matters during versioning exercises
- **`MoveCarOutput` kept** with extra fields: `distance_driven`, `start_time`, `end_time`
- **Simulator uses `start_workflow`** (non-blocking) not `execute_workflow` — enables rapid concurrent workflow creation
- **Simulator `--quiet` flag** via argparse to suppress per-workflow output
- **Existing code untouched** — existing modules stay as-is for reference
- **No new dependencies** — activities use stdlib only (random, datetime)
- **No `--count`/`--interval` flags** on simulator — keep it simple
- **No workflow execution timeout** — workshop environment is ephemeral
