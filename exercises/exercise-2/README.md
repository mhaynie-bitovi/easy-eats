# Exercise 2: Worker Versioning

**Time:** ~45 minutes
**Theme:** "In Exercise 1, you used patching to safely deploy a workflow change. Now let's deploy changes using Worker Versioning — where Temporal's infrastructure handles routing instead of conditional code paths."
**Skills:** Worker Deployments, deployment versions, `PINNED` vs `AUTO_UPGRADE`, `WorkerDeploymentConfig`, emergency rollback, upgrade-on-continue-as-new

---

## Setup: Clean Slate

If your Temporal dev server is still running from Exercise 1, stop it (Ctrl+C) and restart it so there are no leftover workflow executions:

```bash
temporal server start-dev
```

> **Note:** Keep this running for the entire exercise. All code changes in this exercise happen before any workers or workflows start — every workflow will be versioned from birth.

---

## Part A — Enable Worker Versioning + Deploy Version 1.0 (~12 min)

**Goal:** Configure worker versioning infrastructure and deploy the first versioned worker.

1. Navigate to the exercise folder:

```bash
cd exercises/exercise-2/practice
```

2. Review the starting code. This is the Exercise 1 solution — `ValetParkingWorkflow` already calls `notify_owner` (guarded by `workflow.patched("add-notify-owner")`). The `bill_customer` activity and its models are already defined — you'll use them later.

3. **Make three code changes** (follow the `TODO(Part A)` comments in each file):

   **a.** In `valet/valet_parking_workflow.py` — import `VersioningBehavior` and add `versioning_behavior=VersioningBehavior.PINNED` to `@workflow.defn`:

   ```python
   from temporalio.common import VersioningBehavior

   @workflow.defn(versioning_behavior=VersioningBehavior.PINNED)
   class ValetParkingWorkflow:
   ```

   > **Why PINNED?** Each parking transaction should complete on the code version it started on. No mid-execution surprises, no patching needed.

   **b.** In `valet/parking_lot_workflow.py` — import `VersioningBehavior` and add `versioning_behavior=VersioningBehavior.PINNED` to `@workflow.defn`:

   ```python
   from temporalio.common import VersioningBehavior

   @workflow.defn(versioning_behavior=VersioningBehavior.PINNED)
   class ParkingLotWorkflow:
   ```

   > **Why PINNED here too?** `ParkingLotWorkflow` is an immortal singleton that uses continue-as-new. With PINNED, each CaN run stays on its version, and the *next* run after CaN picks up the latest Current Version automatically. This means we can make non-replay-safe changes without patching — the version boundary is the CaN boundary. (We'll see this in action in Part D.)

   **c.** In `valet/worker.py` — import `WorkerDeploymentVersion` and `WorkerDeploymentConfig`, create the deployment config from environment variables, and pass it to the `Worker`:

   ```python
   from temporalio.common import WorkerDeploymentVersion
   from temporalio.worker import Worker, WorkerDeploymentConfig

   # ... inside main(), after creating the client:

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
       # ... existing config ...
       deployment_config=deployment_config,
   )
   ```

4. Start the versioned 1.0 worker (in a **new terminal**):

```bash
make start-worker BUILD_ID=1.0
```

5. Register version 1.0 as the **Current Version** for the deployment:

```bash
temporal worker deployment set-current-version \
    --deployment-name valet-deploy \
    --build-id 1.0
```

6. Inspect the deployment to confirm:

```bash
temporal worker deployment describe --name valet-deploy
```

   You should see version 1.0 listed as the Current Version.

7. Start the load simulator (in a **new terminal**):

```bash
make load
```

8. Open the Temporal Web UI at [http://localhost:8233](http://localhost:8233) and watch workflows flow through the versioned 1.0 worker.

> **What you've learned:**
> - **Worker Deployment:** A named group (e.g., `valet-deploy`) that contains versioned workers.
> - **Worker Deployment Version:** A specific build (e.g., `1.0`) within a deployment, identified by a build ID.
> - **`WorkerDeploymentConfig`:** How the worker tells Temporal which deployment and build ID it belongs to.
> - **`set-current-version`:** How you tell Temporal which version should receive new workflow tasks.

---

## Part B — Deploy a Breaking Change — No Patching Needed (~15 min)

**Motivation:** "Product wants billing at the end of the valet workflow. This adds a new activity — a non-replay-safe change. In Exercise 1, you'd have needed a patch. With PINNED versioning, you don't."

1. **Make three code changes** to `valet/valet_parking_workflow.py` (follow the `TODO(Part B)` comments):

   **a.** Remove the `workflow.patched("add-notify-owner")` guard — call `notify_owner` unconditionally:

   ```python
   # Before (Exercise 1 patched version):
   if workflow.patched("add-notify-owner"):
       await workflow.execute_activity(notify_owner, ...)

   # After (no patch needed with PINNED):
   await workflow.execute_activity(notify_owner, ...)
   ```

   > With PINNED versioning, old workflows never replay on new code. The patch guard from Exercise 1 is no longer needed.

   **b.** Capture the return values from both `move_car` calls:

   ```python
   move_to_parking_space_result = await workflow.execute_activity(move_car, ...)
   # ... (sleep) ...
   move_to_valet_result = await workflow.execute_activity(move_car, ...)
   ```

   **c.** Add `bill_customer` at the end of the workflow (import `bill_customer` and `BillCustomerInput` at the top):

   ```python
   bill_result = await workflow.execute_activity(
       bill_customer,
       BillCustomerInput(
           license_plate=input.license_plate,
           duration_seconds=input.trip_duration_seconds,
           total_distance=(
               move_to_parking_space_result.distance_driven
               + move_to_valet_result.distance_driven
           ),
       ),
       start_to_close_timeout=timedelta(seconds=10),
   )

   return ValetParkingOutput(total_bill=bill_result.amount)
   ```

2. Start a 2.0 worker **alongside** the running 1.0 worker (in a **new terminal**):

```bash
make start-worker BUILD_ID=2.0
```

3. Set 2.0 as the Current Version:

```bash
temporal worker deployment set-current-version \
    --deployment-name valet-deploy \
    --build-id 2.0
```

4. **Observe in the Temporal Web UI:**
   - **New workflows** start on version 2.0 — they include billing.
   - **In-flight 1.0 workflows** stay pinned to version 1.0 — they complete on the 1.0 worker with no billing, no patching, no replay issues.

   > **This is the "aha" moment.** You just deployed a non-replay-safe change with zero patching. Version isolation replaced the `workflow.patched()` guard from Exercise 1.

5. Wait for all 1.0 workflows to complete (trip durations are 5–30 seconds), then **stop the 1.0 worker** (Ctrl+C in its terminal).

6. Verify the deployment state:

```bash
temporal worker deployment describe --name valet-deploy
```

7. **Clean up v1.0** — once drained and the worker is stopped, delete the old version:

```bash
temporal worker deployment delete-version \
    --deployment-name valet-deploy \
    --build-id 1.0 \
    --skip-drainage
```

> **What you've learned:**
> - **Rainbow deployment model:** Multiple versions coexist. Temporal routes traffic between them — new workflows go to the Current Version, and in-flight workflows stay on their pinned version.
> - **PINNED eliminates patching:** When workflows should complete on the version they started on, you never need `workflow.patched()` to maintain replay compatibility.
> - **Sunsetting a version:** When a version has drained (no more workflows), stop its worker and delete the version.

### Discussion: The Decision Matrix

When should you use PINNED vs AUTO_UPGRADE?

| Workflow Duration | Uses CaN? | Recommended Behavior | Patching Required? |
|---|---|---|---|
| Short (completes before next deploy) | N/A | PINNED | Never |
| Medium (spans multiple deploys) | No | AUTO_UPGRADE | Yes |
| Long (weeks to years) | Yes | PINNED + upgrade on CaN | Never |
| Long (weeks to years) | No | AUTO_UPGRADE + patching | Yes |

In our codebase:
- `ValetParkingWorkflow` → **PINNED**. Each parking transaction completes within seconds to minutes. No patching needed.
- `ParkingLotWorkflow` → **PINNED** + upgrade on CaN. It's an immortal singleton with continue-as-new. Each CaN run stays on its version, and the next run starts on the Current Version. No patching needed.

> **When would you use AUTO_UPGRADE?** For medium-duration workflows (spanning multiple deploys) that don't use continue-as-new. AUTO_UPGRADE automatically migrates in-flight workflows to the new version on their next workflow task — but non-replay-safe changes still require patching.

---

## Part C — Emergency Rollback & Remediation (~10 min)

**Motivation:** "Things don't always go smoothly. Let's see what happens when a bad deploy makes it to production — and how Worker Versioning gives you tools to respond immediately."

**Scenario:** A developer deploys v3.0 with a bug in the `bill_customer` activity — they reference a field that doesn't exist on the input dataclass.

1. **Introduce the bug.** In `valet/activities.py`, add this line to the beginning of `bill_customer`:

   ```python
   @activity.defn
   async def bill_customer(input: BillCustomerInput) -> BillCustomerOutput:
       tip = input.tip_percentage  # BUG: tip_percentage doesn't exist on BillCustomerInput
       # ... rest of the function
   ```

   This will cause an `AttributeError` every time billing runs.

2. Start a 3.0 worker (in a **new terminal**):

```bash
make start-worker BUILD_ID=3.0
```

3. Set 3.0 as current:

```bash
temporal worker deployment set-current-version \
    --deployment-name valet-deploy \
    --build-id 3.0
```

4. **Watch the damage** in the Temporal Web UI or worker logs — new workflows start on 3.0, but crash at the billing step. The activity retries forever.

### Step 1 — Instant rollback (stop the bleeding)

5. Set v2.0 back as current — no code redeploy needed:

```bash
temporal worker deployment set-current-version \
    --deployment-name valet-deploy \
    --build-id 2.0
```

**Immediately**, new workflows are routed to v2.0 with working billing. But in-flight v3.0 workflows are still pinned to v3.0 — they're stuck.

### Step 2 — Evacuate in-flight v3.0 workflows to v2.0

6. Find the stuck v3.0 workflows. Look for running workflows in the Web UI that show activity failures, or list them:

```bash
temporal workflow list --query 'ExecutionStatus="Running"'
```

7. For each stuck workflow, reassign it to v2.0:

```bash
temporal workflow update-options \
    --workflow-id <workflow-id> \
    --versioning-override-behavior pinned \
    --versioning-override-deployment-name valet-deploy \
    --versioning-override-build-id 2.0
```

   > **Why is this replay-safe?** The workflow code between v2.0 and v3.0 is identical — the bug is in the activity implementation, not the workflow definition. The v2.0 worker replays the workflow history, reaches the billing step, and calls the working v2.0 `bill_customer`. Failed activity attempts in history don't cause replay errors — the workflow just sees "activity not yet completed" and retries.

8. **Observe:** the previously-stuck workflows now complete successfully on v2.0.

### Step 3 — Fix the bug and deploy v3.1

9. **Fix the bug.** Remove the `tip = input.tip_percentage` line you added in step 1.

10. Start a v3.1 worker (in a **new terminal**):

```bash
make start-worker BUILD_ID=3.1
```

11. Set v3.1 as current:

```bash
temporal worker deployment set-current-version \
    --deployment-name valet-deploy \
    --build-id 3.1
```

New workflows now flow through v3.1 with working billing.

### Step 4 — Clean up

12. **Stop the v3.0 worker** (Ctrl+C).

13. Delete the broken v3.0 version:

```bash
temporal worker deployment delete-version \
    --deployment-name valet-deploy \
    --build-id 3.0 \
    --skip-drainage
```

14. Once v2.0 has fully drained, stop the v2.0 worker and delete v2.0 as well:

```bash
temporal worker deployment delete-version \
    --deployment-name valet-deploy \
    --build-id 2.0 \
    --skip-drainage
```

> **What you've learned:**
> - **`set-current-version` as an instant rollback** — no code redeploy needed, new workflows immediately go to the safe version.
> - **Fix-forward with a patch version** (v3.1) rather than permanently rolling back.
> - **`update-options` to evacuate workflows** — surgically move pinned workflows from a broken version to a working one.
> - **Blast radius containment with PINNED** — only workflows that started on v3.0 are affected. They can be individually moved.
> - **Activity-only bugs are safe to move** — the workflow definition didn't change, so there's no history divergence when v2.0 replays v3.0 workflows.

---

## Part D — Upgrade on Continue-as-New (~8 min)

**Goal:** Make a non-replay-safe change to `ParkingLotWorkflow` without patching.

**Motivation:** "We need to add a short drain delay to `ParkingLotWorkflow` before it does continue-as-new — this lets in-flight updates finish before the state snapshot. This adds a `workflow.sleep()` call, which changes the command sequence — a non-replay-safe change. With AUTO_UPGRADE, you'd need to patch. But because `ParkingLotWorkflow` is PINNED and uses continue-as-new, the current run stays on old code and the next run after CaN starts on new code — no patching needed."

1. **Make one code change** in `valet/parking_lot_workflow.py` (follow the `TODO(Part D)` comment):

   Add a 1-second drain delay before continue-as-new:

   ```python
   from datetime import timedelta

   # Inside run(), after wait_condition:
   await workflow.sleep(timedelta(seconds=1))
   workflow.continue_as_new(ParkingLotInput(parking_spaces=self.parking_spaces))
   ```

2. Start a v4.0 worker (in a **new terminal**):

```bash
make start-worker BUILD_ID=4.0
```

3. Set v4.0 as current:

```bash
temporal worker deployment set-current-version \
    --deployment-name valet-deploy \
    --build-id 4.0
```

4. **Observe:** `ParkingLotWorkflow`'s current run continues on v3.1 code (PINNED — it stays on its version). When it eventually hits the history threshold and performs continue-as-new, the **new run** starts on v4.0 with the drain delay — no patching needed.

   New `ValetParkingWorkflow` instances immediately start on v4.0.

5. Wait for all v3.1 workflows to drain (both `ValetParkingWorkflow` and `ParkingLotWorkflow`). Once `ParkingLotWorkflow` has migrated to v4.0, **stop the v3.1 worker** (Ctrl+C) and clean up:

```bash
temporal worker deployment delete-version \
    --deployment-name valet-deploy \
    --build-id 3.1 \
    --skip-drainage
```

6. Stop the load simulator (Ctrl+C) and stop the v4.0 worker when you're satisfied.

> **What you've learned:**
> - **Upgrade-on-CaN pattern:** For long-lived PINNED workflows that use continue-as-new, each run stays on its version, and the next run after CaN picks up the latest code. No patching needed.
> - **CaN is the version boundary.** Design your `continue_as_new` input to carry all necessary state so the new version can start cleanly.
> - **PINNED + CaN vs AUTO_UPGRADE:** If `ParkingLotWorkflow` were AUTO_UPGRADE instead, this change would have required a `workflow.patched()` guard — just like Exercise 1. PINNED + CaN eliminates that entirely.
