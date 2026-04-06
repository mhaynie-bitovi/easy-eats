# Versioning Workshop Exercises — Brainstorming

Modeled on the learning objectives of the Workflow/Worker Versioning Courses (LMS). Targeting intermediate/expert Temporal devs. Focus mostly on worker versioning, but covers/reviews patching — it's still a critical skill with auto-upgrade behavior.

Called-out areas of interest:
- Workflow replay testing
- Patching workflows with auto-upgrade behavior
- Pinned workflows (vs auto-upgrade)
- Upgrade-on-Continue-as-New strategy ("trampolining")
- Emergency remediation techniques
- Worker Controller

Learning Objectives
- from replay workshop description
  - deployment practices
  - worker routing
  - emergency remediation techniques
- from lms courses
  - workflow versioning
    - Apply an appropriate Versioning strategy to modify your Workflows
      - Understand which types of changes can safely be deployed without versioning
      - Explain how to define and use versioning to support incompatible changes to a Workflow
      - Distinguish between the supported Versioning implementations
      - Implement a Versioned Workflow
    - Understand how Temporal Event and Command Mapping applies to Workflow Versioning
      - Search for Workflow Versions and verify the correct Queues are being polled
      - Modify a Workflow using Patch Versioning
      - Verify correct implementations of Versioning strategies
    - Download a Workflow Execution History in JSON format for use in compatibility tests
      - Demonstrate how to restart Workers and migrate Workflow Versions
      - Make changes in production and gracefully update your Executions
      - Test compatibility with past Executions and previous Versions using Workflow Replay
  - worker versioning
    - Understand Worker Versioning Architecture and Deployment Strategies
      - Distinguish between Worker Deployments and Worker Deployment Versions in your application architecture
      - Explain the differences between rainbow, blue-green, and rolling deployment strategies and justify why Worker Versioning uses the rainbow approach for Temporal applications
      - Configure Worker Versioning parameters including enabling versioning, defining deployment names and Build IDs, and setting default versioning behaviors for your Workers
      - Configure Traffic Routing and Rollout Management
    - Configure routing strategies using Current Version and Ramping Version to control how new and existing Workflows are distributed across different Worker Deployment Versions
      - Execute deployment Workflows using CLI commands to inspect current state, activate deployment versions, and monitor rollout progress through the complete Worker Versioning lifecycle
      - Handle Emergency Situations and Production Testing
    - Execute emergency rollbacks by quickly removing Ramping Versions during incidents or moving your Workflow from problematic versions to safer ones
      - Execute emergency remediation procedures using the update-options CLI command to move Workflows between versions during critical incidents involving bugs, security vulnerabilities, or urgent fixes
      - Evaluate safe sunsetting procedures that account for active Workflows, query requirements, and proper timing to avoid data loss or service disruption during version retirement
      - Implement pre-deployment testing strategies using versioningOverride to pin test Workflows to pending versions while production traffic continues normally on current versions

---

## Exercise 1: Patching an NDE + Replay Testing

### Recommended Scenario: Add a `notify_owner` Activity

**Business motivation:** "Product wants us to text the car owner when their car is being retrieved from the lot."

**The change:** Insert a new `notify_owner` activity call between `workflow.sleep()` (step 3) and `find_nearest_valet_zone` (step 4) in `ValetParkingWorkflow.run`. This is a textbook NDE — existing workflows that have already passed the sleep point expect `find_nearest_valet_zone` as the next command, but replay will now see `notify_owner` instead.

**Why this scenario works well:**
- Most common real-world NDE pattern (adding a new activity)
- Business motivation is instantly understandable
- The sleep in the middle guarantees workflows are "stuck" at exactly the right point to trigger the NDE
- The fix with `workflow.patched()` is clean and shows the branching pattern clearly
- Naturally leads into the auto-upgrade discussion (Exercise 2)

### Exercise Flow

#### Part A — Capture a baseline history

1. Start the worker and use the load simulator to create several in-flight workflows
2. Wait for at least one workflow to complete
3. Export the completed workflow's history as JSON via Temporal CLI (`temporal workflow show --output json > history.json`) or programmatically via the SDK
4. This becomes the "replay fixture" — the known-good V1 history

#### Part B — Write a replay test (passes)

5. Write a test using `Replayer` from `temporalio.worker` that replays the captured history against the current (unchanged) `ValetParkingWorkflow`
6. Run it — it passes, confirming the replay test infrastructure works

```python
# Sketch of what learners would write
async def test_replay_v1():
    replayer = Replayer(workflows=[ValetParkingWorkflow])
    await replayer.replay_workflow(
        WorkflowHistory.from_json("valet_v1_history", history_json)
    )
```

#### Part C — Make the NDE-inducing change (replay test fails)

7. Add `notify_owner` activity + model types to `activities.py` and `models.py`
8. Insert the activity call into `ValetParkingWorkflow.run` — right after the sleep, before `find_nearest_valet_zone`
9. Run the replay test — it fails with a non-determinism error. This is the "aha" moment.

#### Part D — Patch it (replay test passes again)

10. Wrap the new activity call in a `workflow.patched("notify-owner")` guard:

```python
# After sleep:
if workflow.patched("notify-owner"):
    await workflow.execute_activity(notify_owner, ...)

# Then continue with find_nearest_valet_zone as before
```

11. Run the replay test — it passes. Old histories skip the patched block; new executions run it.
12. Optionally discuss `deprecate_patch()` — once all V1 workflows have completed, you can remove the guard and call `deprecate_patch("notify-owner")` to block accidental replay of old histories.

#### Part E — Tie it to auto-upgrade (discussion/setup for Exercise 2)

13. Explain: with Worker Versioning's auto-upgrade behavior (the default), old in-flight workflows will be picked up by the new worker and replayed. This is exactly why patching matters even when you have worker versioning — auto-upgrade replays old histories with new code.
14. Ask: "What if we *didn't* want old workflows to auto-upgrade?" → foreshadow pinned versions (covered later).

### Alternative / Additional Scenarios

**Alt A: Reorder existing activities.** Move `find_nearest_valet_zone` to *before* the sleep (so the valet zone is pre-selected). This is an NDE but the patch is trickier — you need to store the result and conditionally skip the later call. Good for advanced learners.

**Alt B: Add `charge_parking_fee` at the end.** Insert a fee-calculation activity between `release_space` and the final return. Simpler insertion point (end of workflow), but fewer in-flight workflows are past this point, so the NDE is less dramatic with the simulator running. Could work as a warm-up before the `notify_owner` exercise.

**Alt C: Change activity return type.** Modify `MoveCarOutput` to add a new field (e.g., `fuel_used: float`). This does *not* cause an NDE (Temporal's JSON codec handles new fields gracefully). Include this as a "trick question" to teach learners which changes are safe vs. which are not.

### What to Provide vs. What Learners Write

| Provided (starter code) | Learners write |
|---|---|
| Full V1 codebase (as-is in repo) | Replay test using `Replayer` |
| Pre-captured V1 history JSON (or instructions to capture it) | `notify_owner` activity + models |
| Load simulator already running | Patched workflow code |
| Stub/skeleton for replay test file | `deprecate_patch` cleanup (optional) |

### Key Teaching Points

- **Replay tests are cheap insurance** — they catch NDEs before deployment, not in production
- **`workflow.patched()` is a branch, not a migration** — old histories take the old path, new executions take the new path
- **Auto-upgrade makes patching mandatory** — without pinning, the new worker will replay old histories
- **Not all changes are NDEs** — adding fields to dataclasses, changing activity internals, changing timeouts are all safe. Only changes to the *sequence of commands* cause NDEs.

---

## Exercise 2: Deploying Changes with Worker Versioning

Builds directly on Exercise 1's patched `notify_owner` change. The learner already has code that works — now they learn how to *deploy* it safely with worker versioning, and explore the different routing behaviors.

### Narrative Arc

Three acts that each introduce a versioning concept:

1. **Auto-upgrade + patching** (the default, and the most common real-world pattern)
2. **Pinned versions** (for when you *can't* or *don't want to* patch)
3. **Upgrade-on-Continue-as-New / trampolining** (for long-running singleton workflows like `ParkingLotWorkflow`)

Plus an emergency remediation scenario woven in.

### Act 1: Auto-Upgrade (Default Behavior)

**Setup:** The load simulator is running. Dozens of `ValetParkingWorkflow` instances are in-flight, sitting at various points (some waiting in `workflow.sleep`, some mid-activity).

**What learners do:**

1. **Add a build ID to the V1 worker.** Modify `worker.py` to set `build_id="v1"` and `use_worker_versioning=True`. Deploy it. Point out: this is *opt-in* per task queue — until you set a build ID, versioning is off.

2. **Create assignment rules via CLI.** Use `temporal task-queue versioning` commands to set the initial assignment rule for the `valet` task queue, routing to build ID `v1`.

3. **Deploy the V2 worker** (the patched `notify_owner` code from Exercise 1) with `build_id="v2"`. Add a new assignment rule making `v2` the default build ID. *Don't* shut down V1 yet.

4. **Observe auto-upgrade behavior.** New workflows go to V2 (expected). But in-flight V1 workflows *also* get routed to V2 when they reach their next task — because auto-upgrade is the default. This is where the patching from Exercise 1 pays off: the `workflow.patched("notify-owner")` guard lets old histories replay cleanly on V2 code.

5. **Show what happens *without* the patch.** (Optional brief detour.) Remove the `workflow.patched()` guard, deploy V2 without it, watch an in-flight workflow fail with an NDE error in the Temporal UI. Roll it back. Reinforces: auto-upgrade makes patching mandatory, not optional.

6. **Shut down V1 worker.** Once all in-flight V1 workflows have completed (or immediately, since auto-upgrade already rerouted them), decommission the V1 worker. Discuss: in practice, you'd monitor the task queue to confirm no tasks are still routed to V1.

**Key teaching point:** Auto-upgrade is the happy path. Patching + versioning work *together* — versioning controls deployment rollout, patching ensures replay compatibility.

### Act 2: Pinned Versions

**Scenario:** "Product wants a major overhaul — restructure `ValetParkingWorkflow` to support VIP priority parking. VIP cars skip the line and get assigned premium spaces. The workflow structure changes substantially enough that patching is impractical."

**What the change looks like (provided, not written by learners):**

- A `check_vip_status` activity is added early in the workflow
- Based on VIP status, the workflow takes a completely different branch (different activity sequence, different space request logic)
- This restructuring changes the command sequence in a way that isn't cleanly patchable — too many branches

**What learners do:**

1. **Deploy V3 as pinned.** Set a new assignment rule for build ID `v3` with the `--pinned` flag: new workflows go to V3, but *existing* in-flight workflows stay pinned to their current build ID (V2).

2. **Run V2 and V3 workers side-by-side.** Observe that new workflows get the VIP logic on V3, while in-flight V2 workflows continue running on V2 workers undisturbed. No patching needed — old code runs old workflows, new code runs new workflows.

3. **Monitor draining.** Use `temporal task-queue describe` to see how many workflows are still pinned to V2. Discuss: you have to keep the V2 worker running until all V2 workflows complete. For `ValetParkingWorkflow` with trip durations of 5–300 seconds, this drains quickly. But what about `ParkingLotWorkflow`?

4. **The problem: `ParkingLotWorkflow` is pinned to V2 and *never completes*.** It's a singleton that runs forever (until continue-as-new). Pinned means it will stay on V2 indefinitely. You can't shut down V2 workers because the parking lot is still running there. This is the natural segue to Act 3.

**Key teaching point:** Pinning is the safe option when changes are too large to patch, but it requires running multiple worker versions simultaneously, and long-running / immortal workflows create a draining problem.

### Act 3: Upgrade-on-Continue-as-New (Trampolining)

**The problem from Act 2:** `ParkingLotWorkflow` is pinned to V2, keeps doing continue-as-new back to V2, and will *never* drain to V3 on its own.

**What learners do:**

1. **Understand the problem.** Query the parking lot workflow's current build ID via the Temporal UI or CLI. Confirm it's stuck on V2. Each continue-as-new cycle starts a new run — but the assignment rule keeps it pinned to V2.

2. **Add a redirect rule.** Use `temporal task-queue versioning` to add a *redirect rule* from V2 → V3. This means: next time `ParkingLotWorkflow` does continue-as-new, the new run will be assigned to V3 instead of V2.

3. **Trigger continue-as-new.** Use the load simulator to push enough updates through the parking lot to trigger `_check_continue_as_new()` (the 500-event threshold). Or, for the exercise, lower the threshold temporarily. When continue-as-new fires, the new run starts on V3.

4. **Verify.** Query the parking lot workflow again — it's now running on V3. The V2 worker can be safely shut down.

5. **Discuss the pattern.** This is "trampolining": the workflow bounces through continue-as-new to land on a new version. For workflows like `ParkingLotWorkflow` that pass state via `ParkingLotInput(spaces=self.spaces)`, the state seamlessly transfers to the new version. The key requirement: the new version must be able to deserialize the old version's continue-as-new input.

**Key teaching point:** Redirect rules + continue-as-new = version upgrade for immortal workflows. Design long-running workflows with this in mind: pass serializable state through continue-as-new input.

### Emergency Remediation Sidebar

Weave in during Act 1 or Act 2 — wherever the instructor prefers:

**Scenario:** "Oops — V2 was deployed with auto-upgrade, but the patch has a bug. In-flight workflows are failing."

**Techniques to demonstrate:**

- **Roll back the assignment rule.** Remove V2's assignment rule or add a new rule pointing back to V1. New tasks go to V1. But already-dequeued tasks on V2 will still fail.
- **Reset workflows.** Use `temporal workflow reset` to replay specific failed workflows from a known-good point. Show that replay tests (from Exercise 1) could have caught this before deployment.
- **Batch reset.** If many workflows are affected, use `temporal workflow reset --query` with a visibility query to reset all affected workflows at once.
- **Terminate + re-start as last resort.** For workflows with no recoverable state, terminate and restart. Discuss why this is destructive and when it's justified.

### Summary: What Each Act Teaches

| Act | Versioning Concept | Workflow | Key Lesson |
|---|---|---|---|
| 1 | Auto-upgrade + patching | `ValetParkingWorkflow` | Default behavior; patching is still required |
| 2 | Pinned versions | `ValetParkingWorkflow` | Safe for big changes; creates draining obligation |
| 3 | Trampolining | `ParkingLotWorkflow` | Redirect rules + continue-as-new for immortal workflows |
| Sidebar | Emergency remediation | Either | Reset, rollback, and batch operations |

The two workflows map perfectly to the two main versioning strategies: `ValetParkingWorkflow` (short-lived, completes naturally) for auto-upgrade vs. pinned, and `ParkingLotWorkflow` (long-running singleton with continue-as-new) for trampolining.

---

## Exercise 3: Deploying on K8s with the Worker Controller

The narrative payoff: Exercise 2 had learners manually running CLI commands to create assignment rules, redirect rules, and monitor draining. Exercise 3 shows them that the Worker Controller *automates all of that* — they declare desired state, the operator handles the rest.

### Premise

"You've been managing versioning by hand. Now let's see how this works in a real deployment. The Worker Controller manages assignment rules, redirect rules, and worker scaling for you — you just tell it what version to deploy."

### What's Pre-Installed in Instruqt

- Minikube cluster running
- Temporal cluster deployed in k8s (temporal-server, temporal-ui, etc.)
- Worker Controller installed (CRDs registered, controller pod running)
- `kubectl` configured, `temporal` CLI available
- The V1 valet worker container image pre-built and available (e.g., in a local registry or pre-loaded into minikube)

### Exercise Flow

#### Step 1: Explore what's already running

Learners orient themselves in the k8s environment:

```
kubectl get pods
kubectl get workerdeployments
temporal task-queue describe --task-queue valet
```

Nothing valet-related is deployed yet — they'll do that.

#### Step 2: Deploy V1 via WorkerDeployment CRD

Learners apply a provided YAML manifest (with a few blanks to fill in) that creates a `WorkerDeployment` for the valet worker:

- Points to the V1 container image
- Specifies task queue `valet`
- Sets build ID `v1`
- Declares it as the current default version

They `kubectl apply` it and observe:
- The controller creates a Kubernetes Deployment for the V1 worker pods
- The controller automatically creates an assignment rule on the `valet` task queue pointing to `v1`
- Worker pods come up and start polling

They start the load simulator (either as a pod or from their terminal) to get workflows flowing.

#### Step 3: Deploy V2 (auto-upgrade)

Mirrors Exercise 2 Act 1, but automated. Learners:

1. Build (or are given) a V2 container image containing the patched `notify_owner` code from Exercises 1–2
2. Update the `WorkerDeployment` YAML — change the image tag, set build ID to `v2`, set the rollout strategy to auto-upgrade (the default)
3. `kubectl apply` the updated manifest

Then observe the controller's behavior:
- A *new* Deployment is created for V2 worker pods
- The assignment rule is updated: new workflows → V2
- V1 workers are kept alive (the controller doesn't kill them immediately)
- In-flight workflows auto-upgrade to V2 (because patching from Exercise 1 makes this safe)
- Once V1 has no remaining tasks, the controller scales V1 pods to zero / removes them

The key "aha": what took 4–5 CLI commands in Exercise 2 is now a single `kubectl apply`.

#### Step 4: Deploy V3 (pinned — the VIP change)

Mirrors Exercise 2 Act 2. Learners:

1. Are given a V3 image with the VIP priority parking changes
2. Update the manifest — build ID `v3`, rollout strategy set to **pinned**
3. `kubectl apply`

Observe:
- V3 Deployment created, V3 pods come up
- New workflows go to V3
- V2 workflows stay on V2 — the controller keeps V2 pods running and doesn't set redirect rules
- `kubectl get workerdeployments -o wide` (or similar) shows both V2 and V3 active with workflow counts

#### Step 5: The ParkingLotWorkflow problem (trampolining)

Same problem as Exercise 2 Act 3 — `ParkingLotWorkflow` is pinned to V2 and won't drain. But now the resolution is different:

Learners add a redirect rule to the `WorkerDeployment` spec (or apply a separate redirect CRD — depends on the controller's API). The controller:
- Creates a redirect rule V2 → V3 on the task queue
- When `ParkingLotWorkflow` does its next continue-as-new, it trampolines to V3
- After the redirect completes, the controller observes V2 has no remaining workflows and drains V2 pods

This connects the dots: the continue-as-new pattern in `ParkingLotWorkflow._check_continue_as_new()` is *designed* for this exact operational scenario.

#### Step 6: Emergency rollback

"V3 has a bug in VIP logic — cars are being double-assigned to premium spaces."

Learners:
1. Update the manifest to roll back the default version to V2 (or V2.1 — a hotfix image)
2. `kubectl apply`
3. Observe the controller update assignment rules, new workflows go to the safe version
4. Optionally use `temporal workflow reset --query` to recover failed V3 workflows (same technique from Exercise 2, reinforced here)

The point: rollback in k8s is the same workflow as any other version change — update the manifest, apply it. The controller handles the rule changes.

### What Learners Produce vs. What's Provided

| Provided | Learners do |
|---|---|
| Pre-built container images (V1, V2, V3) | Fill in WorkerDeployment YAML fields (task queue, build ID, strategy) |
| WorkerDeployment YAML template with blanks | `kubectl apply` each version |
| Controller + Temporal cluster running | Observe behavior via `kubectl` and `temporal` CLI |
| Load simulator as a script or pod | Interpret controller logs / status output |
| Cheat sheet of `kubectl` and `temporal` commands | Trigger the trampolining scenario |

Since we're assuming minimal k8s knowledge, keep the `kubectl` interactions to `apply`, `get`, `describe`, and `logs`. No debugging k8s networking or volumes.

### Key Teaching Points

1. **Declarative > imperative.** Exercise 2's manual CLI commands become a single YAML manifest that the controller reconciles continuously. If the controller dies and restarts, it re-converges to the desired state.

2. **The controller doesn't replace your understanding.** You still need to know *why* auto-upgrade requires patching, *why* pinned creates a draining obligation, *why* immortal workflows need trampolining. The controller automates the mechanics, not the decision-making.

3. **Rollback is just another deploy.** No special rollback command — change the manifest, apply it. The controller handles rule transitions the same way in both directions.

4. **Continue-as-new is the upgrade seam for long-running workflows.** The `_check_continue_as_new()` pattern in `ParkingLotWorkflow` isn't just about history size — it's the mechanism that enables version migration. Design for it from the start.

### Open Questions

- What's the actual CRD schema for the Worker Controller? The field names above (`WorkerDeployment`, rollout strategy, etc.) are illustrative — need to confirm the exact API.
- Should the exercise show `kubectl logs` on the controller pod? Could be instructive to see the controller's reconciliation loop in action, but adds noise if we're keeping k8s minimal.
- Does the final step include cleaning up / tearing down? Or does the Instruqt environment just reset?
