# Exercise 2: Deploying Changes with Worker Versioning

**Time:** ~30 minutes
**Theme:** Deploy the patched notify_owner change, then a larger structural change, using worker versioning CLI commands.
**Skills:** Build IDs, deployment versions, auto-upgrade behavior, pinned versions, trampolining via continue-as-new

---

## Part A — Deploy with auto-upgrade (~12 min)

1. Navigate to the exercise folder:

```bash
cd exercises/exercise-2/practice
```

2. Start the **unversioned** V1 worker and the load simulator:

```bash
make worker &
make load
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
make versioned-worker BUILD_ID=v1
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
make versioned-worker BUILD_ID=v2
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

---

## Part B — Deploy with pinned versions (~12 min)

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
make versioned-worker BUILD_ID=v3
```

4. Set V3 as current:

```bash
temporal worker deployment set-current \
  --deployment-name valet-deploy \
  --build-id v3
```

5. **Observe**: New workflows go to V3 with billing. In-flight V2 workflows **stay pinned to V2** — they keep running on the V2 worker.

6. Use `temporal task-queue describe` to monitor V2 draining. Notice: `ParkingLotWorkflow` is pinned to V2 and **never drains** — it's a singleton that runs forever via continue-as-new.

---

## Part C — Trampolining the ParkingLotWorkflow (~6 min)

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
