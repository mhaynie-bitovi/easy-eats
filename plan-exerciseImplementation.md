# Exercise Implementation Plan

Three 30-minute hands-on exercises for a Temporal worker versioning workshop. Each exercise has `practice/` and `solution/` folders. The solution of each exercise is the starting point (practice code) for the next.

---

## Directory Structure

```
exercises/
  WORKSHOP.md                  # Full attendee-facing instructions
  load_simulator.py            # Shared load script, copied into each exercise folder
  exercise-1/
    practice/                  # Copy of src/valet (V1 code, unmodified)
    solution/                  # V1 code + notify_owner patched + replay test
  exercise-2/
    practice/                  # Copy of exercise-1/solution
    solution/                  # V2 deployed with worker versioning (auto-upgrade + pinned)
  exercise-3/
    practice/                  # Copy of exercise-2/solution
    solution/                  # V3 deployed on k8s with Worker Controller
```

Each `practice/` and `solution/` folder mirrors `src/valet/` plus a `tests/` subfolder, containing the relevant workflow, activity, model, worker, and test files. Exercises import from their own folder so they're self-contained.

**Load simulator:** A single `load_simulator.py` script is used across all 3 exercises (duplicated into each exercise folder for isolation). It starts `ValetParkingWorkflow` instances with random trip durations at a steady rate. The script is identical everywhere — it doesn't change between exercises. This keeps focus on the learning objectives rather than the workshop environment.

---

## Baseline (V1) — Starting State

The V1 code is a plain **unversioned** baseline:
- `ValetParkingWorkflow`: request_space → move_car (to space) → sleep → move_car (back) → release_space
- `ParkingLotWorkflow`: singleton with update handlers, continue-as-new
- **No `versioning_behavior` set on either workflow** (the decorator has no versioning arg)
- **No `WorkerDeploymentConfig` in `worker.py`** — the worker is plain/unversioned
- This mirrors real-world starting state: teams begin unversioned and opt in later

---

## No Standalone "Exercise 0"

The target audience is intermediate/expert Temporal devs — a standalone "familiarize yourself with the workflow" exercise would feel thin. Instead:
- **Slides/content before Exercise 1** should walk through the valet workflow architecture (the two workflows, the activity flow, the parking lot singleton) so learners arrive already oriented.
- **Exercise 1 Part A** serves as hands-on familiarization: the learner reads the workflow code, runs it via the load simulator, and writes a replay test. That IS the orientation — it just has a concrete deliverable (the replay test) instead of being purely exploratory.
- If Exercise 1 feels too long at ~30 min, make Part A easier (more fill-in-the-blank, less blank skeleton) rather than splitting it into a separate exercise.

---

## Exercise 1: Patching a Non-Deterministic Change + Replay Testing

**Time:** ~30 minutes
**Theme:** "Product wants us to notify the car owner when their car is being retrieved."
**Skills:** Replay testing, identifying NDEs, using `workflow.patched()`

### What the Learner Does

#### Part A — Run V1, capture a history, and write a replay test (~10 min)

**Context provided in practice folder:**
- Full V1 codebase
- A skeleton replay test file (`tests/test_replay.py`) with a `TODO` comment

**Learner steps:**
1. Examine the V1 `ValetParkingWorkflow` to understand the command sequence.
2. Start the worker in one terminal:

```bash
python -m valet.worker
```

3. In a separate terminal, start the load simulator:

```bash
python -m valet.load_simulator
```

4. Wait for a workflow to complete (trip durations are short). Then stop the load simulator and export a completed workflow's history:

```bash
temporal workflow show --workflow-id valet-<plate> --output json > history/valet_v1_history.json
```

   This is the same process you'd use to capture a production history for replay testing. The JSON file becomes your "known-good" replay fixture.

4. Complete the replay test skeleton using `Replayer` from `temporalio.worker`:

```python
from temporalio.worker import Replayer, WorkflowHistory

async def test_replay_valet_v1():
    with open("history/valet_v1_history.json", "r") as f:
        history_json = f.read()
    replayer = Replayer(workflows=[ValetParkingWorkflow])
    await replayer.replay_workflow(
        WorkflowHistory.from_json("valet_v1_history", history_json)
    )
```

5. Run the test — it passes, confirming the replay infrastructure works.

#### Part B — Make the NDE-inducing change & see it fail (~8 min)

**Learner steps:**
1. Add `NotifyOwnerInput` and `NotifyOwnerOutput` dataclasses to `models.py`.
2. Add a `notify_owner` activity to `activities.py`:

```python
@activity.defn
async def notify_owner(input: NotifyOwnerInput) -> NotifyOwnerOutput:
    activity.logger.info(
        f"Notifying owner of {input.license_plate}: {input.message}"
    )
    await asyncio.sleep(0.5)
    return NotifyOwnerOutput(notified=True)
```

3. Insert the activity call into `valet_workflow.py` **after** `workflow.sleep()` and **before** the return `move_car`:

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

4. Run the replay test — **it fails** with a non-determinism error. This is the "aha" moment.

#### Part C — Patch it (~8 min)

**Learner steps:**
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

2. Run the replay test — **it passes**. Old histories skip the patched block; new executions run it.

#### Part D — Discussion: ties to auto-upgrade (~4 min)

Instructor-led discussion (no code changes):
- With auto-upgrade (the default `VersioningBehavior`), in-flight workflows get picked up by new workers and replayed.
- The patch is what makes this safe — old histories take the old path.
- Foreshadow: "Patching works, but there's a cleaner approach. That's Exercise 2."

### Emergency Remediation Sidebar (instructor-led, woven in)

- If a bad change was deployed without a patch: `temporal workflow reset` can replay a failed workflow from a known-good point.
- Replay tests are the safety net that catches this **before** production.

### Files Modified/Created

| File | Action |
|---|---|
| `models.py` | Add `NotifyOwnerInput`, `NotifyOwnerOutput` |
| `activities.py` | Add `notify_owner` activity |
| `valet_workflow.py` | Add patched `notify_owner` call after sleep |
| `worker.py` | Register `notify_owner` in activities list |
| `tests/test_replay.py` | New — replay test using `Replayer` |

### Solution Folder Contains

All V1 files plus the above changes applied. This becomes Exercise 2's practice folder.

---

## Exercise 2: Deploying Changes with Worker Versioning

**Time:** ~30 minutes
**Theme:** Deploy the patched notify_owner change, then a larger structural change, using worker versioning CLI commands.
**Skills:** Build IDs, assignment rules, auto-upgrade behavior, pinned versions, trampolining via continue-as-new

### What the Learner Does

#### Part A — Deploy with auto-upgrade (~12 min)

**Setup:** Learner starts the worker locally and runs the load simulator so dozens of `ValetParkingWorkflow` instances are in-flight (some sleeping).

**Learner steps:**
1. Start the V1 worker (unversioned) and the load simulator:

```bash
python -m valet.worker &
python -m valet.load_simulator
```

2. Stop the V1 worker. **Now configure worker versioning.** The learner makes three changes:

   **a. Add `versioning_behavior` to both workflows.**

   In `valet_workflow.py`:
   ```python
   from temporalio.common import VersioningBehavior

   @workflow.defn(versioning_behavior=VersioningBehavior.AUTO_UPGRADE)
   class ValetParkingWorkflow:
   ```

   In `parking_lot_workflow.py`:
   ```python
   from temporalio.common import VersioningBehavior

   @workflow.defn(versioning_behavior=VersioningBehavior.AUTO_UPGRADE)
   class ParkingLotWorkflow:
   ```

   **b. Add `WorkerDeploymentConfig` to `worker.py`.**

   ```python
   from temporalio.common import WorkerDeploymentVersion
   from temporalio.worker import Worker, WorkerDeploymentConfig

   # Read env vars for versioning (falls back to unversioned if not set)
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

   Discuss: `versioning_behavior` on workflows tells Temporal how to route tasks for that workflow type. `WorkerDeploymentConfig` on the worker tells Temporal which version this worker process represents. Both are required.

3. Start the **versioned** V1 worker with build ID:

```bash
TEMPORAL_DEPLOYMENT_NAME=valet-deploy TEMPORAL_WORKER_BUILD_ID=v1 python -m valet.worker
```

4. Use the CLI to set the initial version as current:

```bash
temporal worker deployment set-current \
  --deployment-name valet-deploy \
  --build-id v1
```

5. Deploy the V2 worker (the patched code from Exercise 1) with a new build ID:

```bash
TEMPORAL_DEPLOYMENT_NAME=valet-deploy TEMPORAL_WORKER_BUILD_ID=v2 python -m valet.worker
```

6. Set V2 as the current version (with ramping or directly):

```bash
temporal worker deployment set-current \
  --deployment-name valet-deploy \
  --build-id v2
```

7. **Observe**: New workflows go to V2 (expected). In-flight V1 workflows **also auto-upgrade to V2** when they reach their next task. The `workflow.patched("add-notify-owner")` guard from Exercise 1 makes this safe.

8. Once all V1 workflows complete, shut down the V1 worker.

**Key teaching point:** Auto-upgrade + patching is the happy path. Versioning controls rollout; patching ensures replay compatibility.

#### Part B — Deploy with pinned versions (~12 min)

**Scenario:** "Product wants to add billing at the end of the workflow. Rather than writing patch logic, we'll use pinned versions — old workflows finish on old code, new workflows run on new code. No patching needed."

**Why pinned/rainbow is the better default:**
- No patch logic to write, review, or maintain
- No risk of getting the patch wrong and causing NDEs in production
- Clean separation — old code runs old workflows, new code runs new ones
- Patching is still a useful skill (especially understanding auto-upgrade behavior), but for planned deployments, rainbow is simpler and safer

**The change (provided, learner copies it in):**
- Add `BillCustomerInput`, `BillCustomerOutput` to `models.py`
- Add `bill_customer` activity to `activities.py`
- Add billing logic at the end of `ValetParkingWorkflow` — compute duration, call `bill_customer`, return a `ValetParkingOutput` with the bill amount
- No patching needed — pinned versions handle the transition

**Learner steps:**
1. Apply the provided V3 code changes.
2. Change `ValetParkingWorkflow` versioning behavior to `PINNED`:

```python
@workflow.defn(versioning_behavior=VersioningBehavior.PINNED)
class ValetParkingWorkflow:
```

3. Deploy the V3 worker:

```bash
TEMPORAL_DEPLOYMENT_NAME=valet-deploy TEMPORAL_WORKER_BUILD_ID=v3 python -m valet.worker
```

4. Set V3 as current:

```bash
temporal worker deployment set-current \
  --deployment-name valet-deploy \
  --build-id v3
```

5. **Observe**: New workflows go to V3 with billing. In-flight V2 workflows **stay pinned to V2** — they keep running on the V2 worker.

6. Use `temporal task-queue describe` to monitor V2 draining. Short-lived `ValetParkingWorkflow` instances finish quickly. But notice: `ParkingLotWorkflow` is pinned to V2 and **never drains** — it's a singleton that runs forever via continue-as-new.

#### Part C — Trampolining the ParkingLotWorkflow (~6 min)

**The problem:** `ParkingLotWorkflow` is pinned to V2. Its continue-as-new cycles keep it on V2 forever. You can't shut down the V2 worker.

**Learner steps:**
1. Verify the problem: query the parking lot workflow's deployment version.
2. Change `ParkingLotWorkflow` to `AUTO_UPGRADE` versioning behavior (it was already `AUTO_UPGRADE` but discuss why this is the right choice for singleton/immortal workflows).
3. The next time `ParkingLotWorkflow` does continue-as-new (triggered by the 500-event threshold or `is_continue_as_new_suggested()`), the new run lands on V3.
4. Verify: the parking lot workflow is now running on V3.
5. Safely shut down the V2 worker.

**Key teaching point:** Long-running/immortal workflows should use `AUTO_UPGRADE` + continue-as-new as their version migration strategy. Design `continue_as_new` input to carry serializable state.

### Emergency Remediation Sidebar

- **Rollback:** Remove V2's assignment rule, put V1 back as current. New tasks go to V1.
- **Reset failed workflows:** `temporal workflow reset --workflow-id <id> --event-id <safe-point>`
- **Batch reset:** `temporal workflow reset --query 'WorkflowType="ValetParkingWorkflow" AND CloseStatus=3'`

### Files Modified/Created

| File | Action |
|---|---|
| `valet_workflow.py` | Add `versioning_behavior=VersioningBehavior.AUTO_UPGRADE` (Part A); add billing logic at end; change to `PINNED` (Part B) |
| `parking_lot_workflow.py` | Add `versioning_behavior=VersioningBehavior.AUTO_UPGRADE` (Part A) |
| `worker.py` | Add `WorkerDeploymentConfig` + env var reading (Part A); register `bill_customer` (Part B) |
| `models.py` | Add `BillCustomerInput`, `BillCustomerOutput`; update `ValetParkingOutput` with optional `total_bill` field |
| `activities.py` | Add `bill_customer` activity |
| `tests/test_valet_workflow.py` | Update mocks and assertions for billing |

### Solution Folder Contains

All Exercise 1 solution files plus: versioning configuration on both workflows and the worker (from Part A), and the billing changes (from Part B). `ValetParkingWorkflow` is `PINNED`, `ParkingLotWorkflow` is `AUTO_UPGRADE`, worker has `WorkerDeploymentConfig`. This becomes Exercise 3's practice folder.

---

## Exercise 3: Deploying on K8s with the Worker Controller

**Time:** ~30 minutes
**Theme:** "You've been managing versioning by hand. The Worker Controller automates all of that."
**Skills:** TemporalWorkerDeployment CRD, AllAtOnce vs Progressive rollout, rollback, emergency remediation in k8s

### Pre-Setup (Instruqt does this)

- Minikube running with 4 CPUs / 4 GB RAM
- Temporal dev server running on the host (`localhost:7233`)
- Worker Controller installed (CRDs + controller pod)
- V1, V2, V3 container images pre-built in minikube's Docker daemon
- `kubectl` and `temporal` CLI available

### What the Learner Does

#### Part A — Deploy V1 and generate load (~8 min)

**Learner steps:**
1. Examine the provided k8s manifests:
   - `k8s/temporal-connection.yaml` — points to the host Temporal server
   - `k8s/valet-worker.yaml` — `TemporalWorkerDeployment` with `AllAtOnce` strategy

2. Deploy V1:

```bash
kubectl apply -f k8s/temporal-connection.yaml
kubectl apply -f k8s/valet-worker.yaml
```

3. Verify:

```bash
kubectl get twd          # TemporalWorkerDeployment shows up
kubectl get deployments  # Controller created a versioned Deployment
kubectl get pods         # Worker pods are Running
```

4. Start the load simulator:

```bash
python -m valet.load_simulator
```

5. Check the Temporal UI — workflows are flowing.

#### Part B — Replay-safe change with AllAtOnce (~8 min)

**Scenario:** Change `move_car` activity internals (add logging, adjust distance range). Activity-only change — does not affect workflow command sequence.

**Learner steps:**
1. Make the code change in `activities.py`:
   - Change `random.uniform(0.1, 2.0)` → `random.uniform(0.5, 5.0)`
   - Add `activity.logger.info(f"distance_driven: {distance_driven}")`

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

#### Part C — Non-replay-safe change with Progressive (~8 min)

**Scenario:** Add the `notify_owner` activity to the workflow (the same NDE change from Exercise 1, but now deployed via k8s).

**Learner steps:**
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

   - V3 ramps from 25% → 75% → 100% with 30s pauses at each step
   - Both V2 and V3 Deployments run simultaneously
   - V2 workers serve existing in-flight workflows
   - V3 workers serve new workflow executions

4. Verify in Temporal UI: new workflows include `notify_owner`, old ones don't.

#### Part D — Rollback & emergency remediation (~6 min)

**Scenario 1 — Rollback:** "notify_owner has a bug!"

```bash
kubectl patch twd valet-worker --type merge \
  -p '{"spec":{"template":{"spec":{"containers":[{"name":"valet-worker","image":"valet-worker:v2"}]}}}}'
```

The controller creates a new version with old V2 code, routes traffic to it. V3-pinned workflows complete, then V3 scales down.

**Scenario 2 — Bad deploy:** Deploy a crashing version:

```bash
make build TAG=v5-bad   # (pre-broken image, or learner adds a raise RuntimeError)
kubectl patch twd valet-worker --type merge \
  -p '{"spec":{"template":{"spec":{"containers":[{"name":"valet-worker","image":"valet-worker:v5-bad"}]}}}}'
```

Observe:
- New pods crash-loop (`kubectl get pods -w`)
- The version **never becomes Registered** — the worker can't connect to Temporal
- **New workflows keep going to the previous working version** — the controller protects running workflows
- Fix by deploying a corrected image or rolling back

**Key takeaway:** The Worker Controller protects production. A bad deploy never becomes current. Rollback is just another `kubectl patch`.

### Files Modified/Created

This exercise is primarily operational (k8s commands, not code changes). The code changes from Exercises 1 and 2 are baked into the pre-built container images.

| File | Action |
|---|---|
| `k8s/temporal-connection.yaml` | Provided, learner applies it |
| `k8s/valet-worker.yaml` | Provided (AllAtOnce), learner applies & patches |
| `k8s/valet-worker-progressive.yaml` | Provided (Progressive), learner applies it |
| `activities.py` | Learner makes minor edit (activity-internal change for Part B) |

---

## Implementation Checklist

### Scaffolding & Shared Files

- [ ] Create `exercises/exercise-1/practice/` — copy of `src/valet/` + `tests/valet/` + `history/` dir (empty, learner captures into it)
- [ ] Create `exercises/exercise-1/practice/tests/test_replay.py` — skeleton with TODO
- [ ] Create `exercises/exercise-1/solution/` — V1 + notify_owner patched + replay test complete + captured history JSON
- [ ] Create `exercises/exercise-2/practice/` — copy of exercise-1 solution
- [ ] Create `exercises/exercise-2/solution/` — billing added, pinned versioning behavior
- [ ] Create `exercises/exercise-3/practice/` — copy of exercise-2 solution
- [ ] Create `exercises/exercise-3/solution/` — same code, no code changes needed (operational exercise)
- [ ] Pre-build Docker images for V1, V2, V3, V5-bad if needed for Instruqt

### Code Changes to Implement

- [ ] `NotifyOwnerInput`, `NotifyOwnerOutput` models
- [ ] `notify_owner` activity
- [ ] Patched workflow with `workflow.patched("add-notify-owner")`
- [ ] Replay test file
- [ ] Add `versioning_behavior=AUTO_UPGRADE` to both workflows (Exercise 2 Part A)
- [ ] Add `WorkerDeploymentConfig` + env var reading to `worker.py` (Exercise 2 Part A)
- [ ] `BillCustomerInput`, `BillCustomerOutput` models
- [ ] `bill_customer` activity
- [ ] Updated `ValetParkingWorkflow` with billing + PINNED behavior
- [ ] Updated `ValetParkingOutput` with `total_bill` field
- [ ] Updated mock tests for each exercise stage

### Workshop Guide

- [ ] Write `exercises/WORKSHOP.md` — full step-by-step attendee instructions for all 3 exercises
- [ ] Include command cheat sheets for `temporal` CLI and `kubectl`
- [ ] Include "What went wrong?" troubleshooting tips for common mistakes

---

## Key Design Decisions

1. **The notify_owner change bridges Exercises 1 and 2.** Exercise 1 introduces it as an NDE and patches it. Exercise 2 deploys it with worker versioning (auto-upgrade works because of the patch). Exercise 3 deploys it via k8s (Progressive rollout).

2. **The billing change in Exercise 2 motivates pinned/rainbow deployments as the better default.** Rather than framing it as "too big to patch," the point is that rainbow deployments are simpler and safer — no patch logic to write or maintain, no risk of getting it wrong. Patching is still a useful skill (Exercise 1), but for planned deployments, pinned versions are the recommended approach.

3. **ParkingLotWorkflow is the trampolining motivator.** It's a singleton that never completes, which creates a real problem when using pinned versions. The continue-as-new + auto-upgrade pattern resolves it. This pays off the `_check_continue_as_new()` design in the existing code.

4. **Exercise 3 is primarily operational, not code-writing.** Attendees focus on k8s deployment mechanics: `kubectl apply`, `kubectl patch`, observing controller behavior. The code is pre-built into container images. The only code change is a small activity-internal edit to demonstrate AllAtOnce.

5. **Emergency remediation is woven throughout** rather than being a standalone section:
   - Exercise 1: replay tests catch problems before deployment; `temporal workflow reset` as a recovery tool
   - Exercise 2: assignment rule rollback; batch reset of failed workflows
   - Exercise 3: controller protects against bad deploys; rollback via image tag change

6. **Each exercise folder is self-contained.** Learners work in `exercises/exercise-N/practice/` and can reference `exercises/exercise-N/solution/` for hints. The solution is copied to become the next exercise's practice folder.
