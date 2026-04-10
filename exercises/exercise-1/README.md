# Exercise 1: Patching a Non-Deterministic Change + Replay Testing

**Time:** ~30 minutes
**Theme:** "Product wants us to notify the car owner when their car is being retrieved."
**Skills:** Replay testing, identifying non-determinism errors (NDEs), using `workflow.patched()`

---

## Part A — Run V1, capture a history, and write a replay test (~10 min)

1. Navigate to the exercise folder:

```bash
cd exercises/exercise-1/practice
```

2. Examine the V1 `ValetParkingWorkflow` in `valet/valet_workflow.py`. Note the command sequence:
   - `request_space` → `move_car` (to space) → `sleep` → `move_car` (back) → `release_space`

3. Start the Temporal dev server (in a **dedicated terminal**):

```bash
temporal server start-dev
```

4. Start the worker (in a **new terminal**):

```bash
cd exercises/exercise-1/practice
PYTHONPATH=. python -m valet.worker
```

5. Start the load simulator (in a **new terminal**):

```bash
cd exercises/exercise-1/practice
PYTHONPATH=. python -m valet.load_simulator
```

6. Wait for a workflow to complete (trip durations are 5–30 seconds). Then **stop the load simulator** (Ctrl+C) and export a completed workflow's history:

```bash
temporal workflow show --workflow-id valet-<plate> --output json > history/valet_v1_history.json
```

> **Tip:** The workflow ID follows the format `valet-<STATE>-<PLATE>` (e.g., `valet-CA-1ABC123`). Use `temporal workflow list` to find a completed workflow ID.

7. Open `tests/test_replay.py` — it has a `TODO` skeleton. Complete the replay test:

```python
from temporalio.worker import Replayer, WorkflowHistory
from valet.valet_workflow import ValetParkingWorkflow

@pytest.mark.asyncio
async def test_replay_valet_v1():
    with open("history/valet_v1_history.json", "r") as f:
        history_json = f.read()

    replayer = Replayer(workflows=[ValetParkingWorkflow])
    await replayer.replay_workflow(
        WorkflowHistory.from_json("valet_v1_history", history_json)
    )
```

8. Run the test — it should **pass**, confirming the replay infrastructure works:

```bash
PYTHONPATH=. python -m pytest tests/test_replay.py -v
```

---

## Part B — Make the NDE-inducing change & see it fail (~8 min)

Now add the `notify_owner` feature **without** patching to see what a non-determinism error looks like.

1. Add new dataclasses to `valet/models.py`:

```python
@dataclass
class NotifyOwnerInput:
    license_plate: str
    message: str


@dataclass
class NotifyOwnerOutput:
    notified: bool
```

2. Add a new activity to `valet/activities.py`:

```python
from valet.models import NotifyOwnerInput, NotifyOwnerOutput

@activity.defn
async def notify_owner(input: NotifyOwnerInput) -> NotifyOwnerOutput:
    activity.logger.info(
        f"Notifying owner of {input.license_plate}: {input.message}"
    )
    await asyncio.sleep(0.5)
    return NotifyOwnerOutput(notified=True)
```

3. Insert the activity call into `valet/valet_workflow.py` **after** `workflow.sleep()` and **before** the return `move_car`:

```python
# After sleep:
await workflow.execute_activity(
    notify_owner,
    NotifyOwnerInput(
        license_plate=input.license_plate,
        message="Your car is being retrieved!",
    ),
    start_to_close_timeout=timedelta(seconds=10),
)
```

   Don't forget to add `notify_owner` and `NotifyOwnerInput` to the imports.

4. Run the replay test — **it fails** with a non-determinism error:

```bash
PYTHONPATH=. python -m pytest tests/test_replay.py -v
```

> **This is the "aha" moment.** The old workflow history doesn't have a `notify_owner` command, but the new code expects one. The command sequence doesn't match → non-determinism error.

---

## Part C — Patch it (~8 min)

1. Wrap the new activity call with `workflow.patched()`:

```python
if workflow.patched("add-notify-owner"):
    await workflow.execute_activity(
        notify_owner,
        NotifyOwnerInput(
            license_plate=input.license_plate,
            message="Your car is being retrieved!",
        ),
        start_to_close_timeout=timedelta(seconds=10),
    )
```

2. Register `notify_owner` in the worker's activities list in `valet/worker.py`.

3. Run the replay test — **it passes**:

```bash
PYTHONPATH=. python -m pytest tests/test_replay.py -v
```

> Old histories skip the patched block. New executions run it. The `workflow.patched()` marker tells the replayer "this code was added after the history was captured."

---

## Part D — Discussion: ties to auto-upgrade (~4 min)

**Instructor-led discussion (no code changes):**

- With auto-upgrade (the default `VersioningBehavior`), in-flight workflows get picked up by new workers and replayed.
- The patch is what makes this safe — old histories take the old path.
- Foreshadow: "Patching works, but there's a cleaner approach. That's Exercise 2."

> **Emergency remediation sidebar:** If a bad change was deployed without a patch, `temporal workflow reset` can replay a failed workflow from a known-good point. Replay tests are the safety net that catches this **before** production.
