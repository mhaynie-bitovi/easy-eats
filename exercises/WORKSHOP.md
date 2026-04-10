# Temporal Worker Versioning Workshop

Three hands-on exercises to learn Temporal worker versioning, from replay testing to Kubernetes-based deployments with the Worker Controller.

**Prerequisites:**
- [Temporal CLI](https://docs.temporal.io/cli#install)
- Python 3.12+
- This repo cloned and `pip install -r requirements.txt` completed
- For Exercise 3: [minikube](https://minikube.sigs.k8s.io/docs/start/), [kubectl](https://kubernetes.io/docs/tasks/tools/), [Helm](https://helm.sh/docs/intro/install/), [Docker](https://docs.docker.com/get-docker/)

---

## Exercise 1: Patching a Non-Deterministic Change + Replay Testing

**Time:** ~30 minutes
**Theme:** "Product wants us to notify the car owner when their car is being retrieved."
**Skills:** Replay testing, identifying non-determinism errors (NDEs), using `workflow.patched()`

### Part A — Run V1, capture a history, and write a replay test (~10 min)

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

### Part B — Make the NDE-inducing change & see it fail (~8 min)

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

### Part C — Patch it (~8 min)

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

### Part D — Discussion: ties to auto-upgrade (~4 min)

**Instructor-led discussion (no code changes):**

- With auto-upgrade (the default `VersioningBehavior`), in-flight workflows get picked up by new workers and replayed.
- The patch is what makes this safe — old histories take the old path.
- Foreshadow: "Patching works, but there's a cleaner approach. That's Exercise 2."

> **Emergency remediation sidebar:** If a bad change was deployed without a patch, `temporal workflow reset` can replay a failed workflow from a known-good point. Replay tests are the safety net that catches this **before** production.

---

## Exercise 2: Deploying Changes with Worker Versioning

**Time:** ~30 minutes
**Theme:** Deploy the patched notify_owner change, then a larger structural change, using worker versioning CLI commands.
**Skills:** Build IDs, deployment versions, auto-upgrade behavior, pinned versions, trampolining via continue-as-new

### Part A — Deploy with auto-upgrade (~12 min)

1. Navigate to the exercise folder:

```bash
cd exercises/exercise-2/practice
```

2. Start the **unversioned** V1 worker and the load simulator:

```bash
PYTHONPATH=. python -m valet.worker &
PYTHONPATH=. python -m valet.load_simulator
```

   Let several workflows start. Then **stop** the V1 worker and the load simulator.

3. **Configure worker versioning.** Make three changes:

   **a.** Add `versioning_behavior` to both workflows.

   In `valet/valet_workflow.py`:
   ```python
   from temporalio.common import VersioningBehavior

   @workflow.defn(versioning_behavior=VersioningBehavior.AUTO_UPGRADE)
   class ValetParkingWorkflow:
   ```

   In `valet/parking_lot_workflow.py`:
   ```python
   from temporalio.common import VersioningBehavior

   @workflow.defn(versioning_behavior=VersioningBehavior.AUTO_UPGRADE)
   class ParkingLotWorkflow:
   ```

   **b.** Add `WorkerDeploymentConfig` to `valet/worker.py`:

   ```python
   from temporalio.common import WorkerDeploymentVersion
   from temporalio.worker import Worker, WorkerDeploymentConfig

   deployment_name = os.environ.get("TEMPORAL_DEPLOYMENT_NAME")
   build_id = os.environ.get("TEMPORAL_WORKER_BUILD_ID")

   deployment_config = None
   if deployment_name and build_id:
       deployment_config = WorkerDeploymentConfig(
           version=WorkerDeploymentVersion(
               deployment_name=deployment_name,
               build_id=build_id,
           ),
           use_worker_versioning=True,
       )

   worker = Worker(
       client,
       task_queue="valet",
       ...
       deployment_config=deployment_config,
   )
   ```

4. Start the **versioned** V1 worker:

```bash
TEMPORAL_DEPLOYMENT_NAME=valet-deploy TEMPORAL_WORKER_BUILD_ID=v1 PYTHONPATH=. python -m valet.worker
```

5. Set V1 as the current version:

```bash
temporal worker deployment set-current \
  --deployment-name valet-deploy \
  --build-id v1
```

6. Start the load simulator again. Watch workflows flow through V1.

7. Deploy the V2 worker (the patched code from Exercise 1):

```bash
TEMPORAL_DEPLOYMENT_NAME=valet-deploy TEMPORAL_WORKER_BUILD_ID=v2 PYTHONPATH=. python -m valet.worker
```

8. Set V2 as current:

```bash
temporal worker deployment set-current \
  --deployment-name valet-deploy \
  --build-id v2
```

9. **Observe**: New workflows go to V2 (expected). In-flight V1 workflows **also auto-upgrade to V2** when they reach their next task. The `workflow.patched("add-notify-owner")` guard from Exercise 1 makes this safe.

10. Once all V1 workflows complete, shut down the V1 worker.

> **Key takeaway:** Auto-upgrade + patching is the happy path. Versioning controls rollout; patching ensures replay compatibility.

### Part B — Deploy with pinned versions (~12 min)

**Scenario:** "Product wants to add billing at the end of the workflow. Rather than writing patch logic, we'll use pinned versions — old workflows finish on old code, new workflows run on new code. No patching needed."

1. Apply the provided V3 code changes (add these to your files):

   **Models** (`valet/models.py`):
   ```python
   @dataclass
   class BillCustomerInput:
       license_plate: str
       duration_seconds: int
       total_distance: float

   @dataclass
   class BillCustomerOutput:
       amount: float
   ```

   Update `ValetParkingOutput`:
   ```python
   @dataclass
   class ValetParkingOutput:
       total_bill: float | None = None
   ```

   **Activity** (`valet/activities.py`):
   ```python
   @activity.defn
   async def bill_customer(input: BillCustomerInput) -> BillCustomerOutput:
       minutes = input.duration_seconds / 60
       amount = 5.0 + (0.50 * minutes) + (2.0 * input.total_distance)
       amount = round(amount, 2)
       activity.logger.info(
           f"Billing {input.license_plate}: ${amount} "
           f"({minutes:.1f} min, {input.total_distance:.1f} mi)"
       )
       return BillCustomerOutput(amount=amount)
   ```

   **Workflow** (`valet/valet_workflow.py`) — capture move_car results and add billing at the end:
   ```python
   move_to_space_result = await workflow.execute_activity(move_car, ...)
   # ... (sleep, notify_owner) ...
   move_to_valet_result = await workflow.execute_activity(move_car, ...)
   # ... (release_space) ...

   bill_result = await workflow.execute_activity(
       bill_customer,
       BillCustomerInput(
           license_plate=input.license_plate,
           duration_seconds=input.trip_duration_seconds,
           total_distance=(
               move_to_space_result.distance_driven
               + move_to_valet_result.distance_driven
           ),
       ),
       start_to_close_timeout=timedelta(seconds=10),
   )

   return ValetParkingOutput(total_bill=bill_result.amount)
   ```

   **Worker** (`valet/worker.py`): Register `bill_customer` in the activities list.

2. Change `ValetParkingWorkflow` versioning behavior to `PINNED`:

```python
@workflow.defn(versioning_behavior=VersioningBehavior.PINNED)
class ValetParkingWorkflow:
```

3. Deploy the V3 worker:

```bash
TEMPORAL_DEPLOYMENT_NAME=valet-deploy TEMPORAL_WORKER_BUILD_ID=v3 PYTHONPATH=. python -m valet.worker
```

4. Set V3 as current:

```bash
temporal worker deployment set-current \
  --deployment-name valet-deploy \
  --build-id v3
```

5. **Observe**: New workflows go to V3 with billing. In-flight V2 workflows **stay pinned to V2** — they keep running on the V2 worker.

6. Use `temporal task-queue describe` to monitor V2 draining. Notice: `ParkingLotWorkflow` is pinned to V2 and **never drains** — it's a singleton that runs forever via continue-as-new.

### Part C — Trampolining the ParkingLotWorkflow (~6 min)

**The problem:** `ParkingLotWorkflow` is pinned to V2. Its continue-as-new cycles keep it on V2 forever. You can't shut down the V2 worker.

1. Verify the problem: query the parking lot workflow's deployment version.

2. `ParkingLotWorkflow` should use `AUTO_UPGRADE` versioning behavior (it was already set to `AUTO_UPGRADE`). Discuss why this is the right choice for singleton/immortal workflows.

3. The next time `ParkingLotWorkflow` does continue-as-new (triggered by the 500-event threshold or `is_continue_as_new_suggested()`), the new run lands on V3.

4. Verify: the parking lot workflow is now running on V3.

5. Safely shut down the V2 worker.

> **Key takeaway:** Long-running/immortal workflows should use `AUTO_UPGRADE` + continue-as-new as their version migration strategy. Design `continue_as_new` input to carry serializable state.

> **Emergency remediation sidebar:**
> - **Rollback:** Remove V2's assignment rule, put V1 back as current. New tasks go to V1.
> - **Reset failed workflows:** `temporal workflow reset --workflow-id <id> --event-id <safe-point>`
> - **Batch reset:** `temporal workflow reset --query 'WorkflowType="ValetParkingWorkflow" AND CloseStatus=3'`

---

## Exercise 3: Deploying on K8s with the Worker Controller

**Time:** ~30 minutes
**Theme:** "You've been managing versioning by hand. The Worker Controller automates all of that."
**Skills:** TemporalWorkerDeployment CRD, AllAtOnce vs Progressive rollout, rollback, emergency remediation

### Pre-Setup

Ensure the following are running/available:
- Minikube running with 4 CPUs / 4 GB RAM
- Temporal dev server running on the host (`localhost:7233`)
- Worker Controller installed (CRDs + controller pod)
- V1, V2, V3 container images pre-built in minikube's Docker daemon
- `kubectl` and `temporal` CLI available

```bash
# Start Temporal dev server (dedicated terminal)
make temporal-server

# Setup minikube and Worker Controller (new terminal)
make setup
```

### Part A — Deploy V1 and generate load (~8 min)

1. Navigate to the exercise folder:

```bash
cd exercises/exercise-3/practice
```

2. Examine the k8s manifests:
   - `k8s/temporal-connection.yaml` — points to the host Temporal server
   - `k8s/valet-worker.yaml` — `TemporalWorkerDeployment` with `AllAtOnce` strategy

3. Build and deploy V1:

```bash
make build TAG=v1
kubectl apply -f k8s/temporal-connection.yaml
kubectl apply -f k8s/valet-worker.yaml
```

4. Verify:

```bash
kubectl get twd          # TemporalWorkerDeployment shows up
kubectl get deployments  # Controller created a versioned Deployment
kubectl get pods         # Worker pods are Running
```

5. Start the load simulator:

```bash
make load
```

   Check the Temporal UI at [http://localhost:8233](http://localhost:8233) — workflows are flowing.

   **Leave the load simulator running.**

### Part B — Replay-safe change with AllAtOnce (~8 min)

**Scenario:** Change `move_car` activity internals (add logging, adjust distance range). This is an activity-only change — it doesn't affect the workflow command sequence, so it's safe to replay.

1. Make the code change in `valet/activities.py`:
   - Change `random.uniform(0.1, 2.0)` → `random.uniform(0.5, 5.0)`
   - Add `activity.logger.info(f"distance_driven: {distance_driven}")` after the calculation

2. Build and deploy:

```bash
make build TAG=v2
kubectl patch twd valet-worker --type merge \
  -p '{"spec":{"template":{"spec":{"containers":[{"name":"valet-worker","image":"valet-worker:v2"}]}}}}'
```

3. Watch the rollout:

```bash
kubectl get twd -w
```

   With `AllAtOnce`, V2 immediately becomes current. Existing in-flight workflows continue fine — activity internals don't affect replay.

4. Observe V1 draining:

```bash
kubectl get deployments
```

   V1 Deployment scales down as workflows complete; V2 serves all traffic.

### Part C — Non-replay-safe change with Progressive (~8 min)

**Scenario:** Add the `notify_owner` activity to the workflow (same NDE change from Exercise 1, deployed via k8s).

1. Switch to Progressive rollout strategy:

```bash
kubectl apply -f k8s/valet-worker-progressive.yaml
```

2. The V3 image (with `notify_owner`) is already built. Deploy it:

```bash
kubectl patch twd valet-worker --type merge \
  -p '{"spec":{"template":{"spec":{"containers":[{"name":"valet-worker","image":"valet-worker:v3"}]}}}}'
```

3. Watch the progressive rollout:

```bash
kubectl get twd -w
```

   - V3 starts at **rampPercentage: 25%** (pauses 30s)
   - Then ramps to **75%** (pauses 30s)
   - Then reaches **100%**

4. Check Deployments:

```bash
kubectl get deployments
```

   Both V2 and V3 Deployments run simultaneously:
   - **V2 workers** serve existing in-flight workflows
   - **V3 workers** serve new workflow executions

5. Verify in Temporal UI — new workflows include `notify_owner`, old ones don't.

### Part D — Rollback & emergency remediation (~6 min)

**Scenario 1 — Rollback:** "notify_owner has a bug!"

```bash
kubectl patch twd valet-worker --type merge \
  -p '{"spec":{"template":{"spec":{"containers":[{"name":"valet-worker","image":"valet-worker:v2"}]}}}}'
```

Watch the rollback:
```bash
kubectl get twd -w
```

The controller creates a new version (effectively v4 = old v2 code) and routes traffic to it. V3-pinned workflows complete on their v3 workers, then v3 scales down.

**Scenario 2 — Bad deploy:**

```bash
# Build a broken image (add raise RuntimeError("startup crash") to worker.py main())
make build TAG=v5-bad
kubectl patch twd valet-worker --type merge \
  -p '{"spec":{"template":{"spec":{"containers":[{"name":"valet-worker","image":"valet-worker:v5-bad"}]}}}}'
```

Observe:
```bash
kubectl get pods -w
```

- New pods **crash-loop**
- The version **never becomes Registered** — the worker can't connect to Temporal
- **New workflows keep going to the previous working version** — the controller protects running workflows

Fix by deploying a corrected image or rolling back:
```bash
kubectl patch twd valet-worker --type merge \
  -p '{"spec":{"template":{"spec":{"containers":[{"name":"valet-worker","image":"valet-worker:v2"}]}}}}'
```

> **Key takeaway:** The Worker Controller protects production. A bad deploy never becomes current. Rollback is just another `kubectl patch`.

---

## Cleanup

```bash
# Stop the load simulator (Ctrl+C)

# Tear down k8s resources (Exercise 3)
make clean

# Stop the Temporal dev server (Ctrl+C in its terminal)
```

---

## Quick Reference

### Temporal CLI Cheat Sheet

| Command | Description |
|---|---|
| `temporal server start-dev` | Start local dev server |
| `temporal workflow list` | List workflows |
| `temporal workflow show --workflow-id <id> --output json` | Export workflow history |
| `temporal workflow reset --workflow-id <id> --event-id <n>` | Reset workflow to event |
| `temporal worker deployment set-current --deployment-name <name> --build-id <id>` | Set current worker version |
| `temporal task-queue describe --task-queue valet` | Describe task queue versions |

### kubectl Cheat Sheet

| Command | Description |
|---|---|
| `kubectl get twd` | List TemporalWorkerDeployments |
| `kubectl get twd -w` | Watch TWD status changes |
| `kubectl get deployments` | List Kubernetes Deployments |
| `kubectl get pods` | List pods |
| `kubectl get pods -w` | Watch pod status changes |
| `kubectl apply -f <file>` | Apply a manifest |
| `kubectl patch twd <name> --type merge -p '<json>'` | Patch a TWD |

### What Went Wrong? Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| Replay test fails with "non-determinism" | Added/removed/reordered commands without patching | Wrap the change with `workflow.patched("change-id")` |
| Worker won't start | Missing activity registration | Add activity to the Worker's `activities=[]` list |
| Workflows stuck on old version | `ParkingLotWorkflow` is `PINNED` and immortal | Change to `AUTO_UPGRADE`; it migrates on next continue-as-new |
| `kubectl patch` has no effect | YAML syntax error in `-p` flag | Check JSON quoting; use single quotes around JSON |
| Pods in CrashLoopBackOff | Worker code has a runtime error | Check logs: `kubectl logs <pod-name>` |
| New workflows still going to old version | Didn't set new build ID as current | Run `temporal worker deployment set-current` |
| `ModuleNotFoundError` when running worker | Missing `PYTHONPATH` | Run with `PYTHONPATH=. python -m valet.worker` |
