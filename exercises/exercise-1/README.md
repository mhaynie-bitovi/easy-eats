# Exercise 1: Patching a Non-Deterministic Change + Replay Testing

**Time:** ~30 minutes
**Theme:** "Product wants us to send the car owner a confirmation when their car is parked."
**Skills:** Replay testing, identifying non-determinism errors (NDEs), using `workflow.patched()`

---

## Part A — Run V1, capture a history, and write a replay test (~10 min)

1. Navigate to the exercise folder:

```bash
cd exercises/exercise-1/practice
```

2. Examine the V1 `ValetParkingWorkflow` in `valet/valet_parking_workflow.py`. Note the command sequence:
   - `request_parking_space` → `move_car` (to parking space) → `sleep` → `move_car` (back) → `release_parking_space`
   - The `sleep` simulates the owner's trip — workflows will be "in flight" during this window.

3. Start the Temporal dev server (in a **dedicated terminal**):

```bash
temporal server start-dev
```

> **Note:** Keep this running for the entire exercise.

4. Start the worker (in a **new terminal** from the same directory):

```bash
make start-worker
```

> **Note:** Keep this worker running — you'll be instructed when to restart it later.

5. Start the load simulator (in a **new terminal** from the same directory):

```bash
make load
```

6. Wait for a workflow to complete (trip durations are 5–30 seconds). Then **stop the load simulator** (Ctrl+C) and export a completed workflow's history:

```bash
temporal workflow show --workflow-id <workfolw-id> --output json > history/valet_v1_history.json
```

> **Tip:** The workflow ID follows the format `valet-<STATE>-<PLATE>` (e.g., `valet-CA-1ABC123`). You can copy a workflow ID from the Temporal Web UI at [http://localhost:8233](http://localhost:8233), or use `temporal workflow list` to find one.

7. Open `tests/test_replay.py` and review the replay test. It loads the history you just captured and replays it against the current workflow code. If the code produces a different command sequence than the history, the test fails with a non-determinism error (NDE).

8. Run the test — it should **pass**, confirming the replay infrastructure works:

```bash
make test
```

---

## Part B — Make the NDE-inducing change & see it fail (~8 min)

Product wants us to send the car owner a notification when their car is about to be parked. A `notify_owner` activity and its models (`NotifyOwnerInput`, `NotifyOwnerOutput`) are already defined in `valet/activities.py` and `valet/models.py`. Your job is to call it from the workflow.

1. Insert the activity call into `valet/valet_parking_workflow.py` **after** `request_parking_space` and **before** the first `move_car`:

```python
# After request_parking_space, before move_car:
await workflow.execute_activity(
    notify_owner,
    NotifyOwnerInput(
        license_plate=input.license_plate,
        message="Your car is being parked!",
    ),
    start_to_close_timeout=timedelta(seconds=10),
)
```

   Don't forget to add `notify_owner` and `NotifyOwnerInput` to the imports.

2. Run the replay test — **it fails** with a non-determinism error:

```bash
make test
```

> **This is the "aha" moment.** The old workflow history doesn't have a `notify_owner` command after `request_parking_space`, but the new code expects one. The command sequence doesn't match → non-determinism error.

---

## Part C — Patch it (~8 min)

1. Wrap the new activity call with `workflow.patched()`:

```python
if workflow.patched("add-notify-owner"):
    await workflow.execute_activity(
        notify_owner,
        NotifyOwnerInput(
            license_plate=input.license_plate,
            message="Your car is being parked!",
        ),
        start_to_close_timeout=timedelta(seconds=10),
    )
```

2. Register `notify_owner` in the worker's activities list in `valet/worker.py`.

3. Run the replay test — **it passes**:

```bash
make test
```

> Old histories skip the patched block. New executions run it. The `workflow.patched()` marker tells the replayer "this code was added after the history was captured."

---

## Part D — See it in action (~6 min)

Now let's watch the patched workflow handle both in-flight (old) and brand-new executions. We'll use the starter script (`make starter`), which kicks off a **single** workflow per invocation, making it easy to track exactly which executions should take the pre-patch vs post-patch path.

1. Make sure the **old (unpatched) worker is still running**. Start a workflow in a **new terminal**:

```bash
make starter
```

   Note the workflow ID printed to the terminal (e.g. `valet-CA-1ABC123`). This is your **pre-patch workflow**. It has a 30-second trip, so it will sit in `sleep` for a bit — leave it in flight.

2. **Stop the old worker** (Ctrl+C) and restart it with the patched code:

```bash
make start-worker
```

3. Watch the first workflow complete in the Temporal Web UI at [http://localhost:8233](http://localhost:8233). It completes **without** `notify_owner` — `workflow.patched()` returned `False` during replay (no marker in the history) and skipped the notification block.

4. Now start a **second** workflow:

```bash
make starter
```

   Note this workflow ID — this is your **post-patch workflow**.

5. Watch this second workflow in the Temporal Web UI. It **includes** `notify_owner` right after `request_parking_space` — `workflow.patched()` returned `True` during live execution and wrote a marker event into the history.

6. Stop the worker when you're satisfied (Ctrl+C).

> This is the auto-upgrade model in action: a single patched worker fleet safely processes both old and new workflows without any routing or versioning configuration.

---

## Part E — Discussion: ties to auto-upgrade (~4 min)

**Instructor-led discussion (no code changes):**

- With auto-upgrade (the default `VersioningBehavior`), in-flight workflows get picked up by new workers and replayed.
- The patch is what makes this safe — old histories take the old path.
- Foreshadow: "Patching works, but there's a cleaner approach. That's Exercise 2."

> **Emergency remediation sidebar:** If a bad change was deployed without a patch, `temporal workflow reset` can replay a failed workflow from a known-good point. Replay tests are the safety net that catches this **before** production.
