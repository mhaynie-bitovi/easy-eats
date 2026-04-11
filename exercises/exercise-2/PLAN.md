# Exercise 2 README Rewrite Plan

## Theme

"In Exercise 1, you used patching to safely deploy a workflow change. Now let's deploy changes using Worker Versioning — where Temporal's infrastructure handles routing instead of conditional code paths."

## Setup: Clean Slate

Restart the Temporal dev server at the start of Exercise 2 so there are no leftover workflow executions from Exercise 1. All code changes happen before any workers or workflows start — every workflow in this exercise is versioned from birth.

---

## Narrative Arc (four parts, three versions)

### Part A: Enable Worker Versioning + Deploy Version 1.0 (~12 min)

- **Goal:** Configure worker versioning infrastructure and deploy the first versioned worker.
- **Code changes (before starting any workers):**
  - Add `VersioningBehavior.PINNED` to `ValetParkingWorkflow` (should run on the same code version from start to finish)
  - Add `VersioningBehavior.AUTO_UPGRADE` to `ParkingLotWorkflow` (immortal singleton with continue-as-new)
  - Add `WorkerDeploymentConfig` to `worker.py` (reads `TEMPORAL_DEPLOYMENT_NAME` and `TEMPORAL_WORKER_BUILD_ID` from env)
- **CLI work:**
  - `make start-worker BUILD_ID=1.0`
  - `temporal worker deployment set-current --deployment-name valet --build-id 1.0`
- **Run load simulator**, observe workflows flowing through the versioned 1.0 worker.
- **Teaches:**
  - How to configure versioning: deployment name, build ID, `WorkerDeploymentConfig`
  - How to set `VersioningBehavior` on workflow definitions
  - CLI commands: `set-current`, `describe`

### Part B: Deploy a Breaking Change — No Patching Needed (~15 min)

- **Motivation:** "Product wants billing at the end of the valet workflow. This adds a new activity — a non-replay-safe change. In Exercise 1, you'd have needed a patch. With PINNED versioning, you don't."
- **Code changes:**
  - Call `bill_customer` activity at the end of the workflow (models, activity definition, imports, and worker registration are already in place)
  - Remove `workflow.patched("add-notify-owner")` guard — no longer needed, since PINNED means old workflows never replay on new code
- **CLI work:**
  - Start 2.0 worker alongside 1.0: `make start-worker BUILD_ID=2.0`
  - Set 2.0 as current: `temporal worker deployment set-current --deployment-name valet --build-id 2.0`
- **Observe:**
  - New workflows start on 2.0 with billing. In-flight 1.0 workflows stay pinned to 1.0 — they complete on the 1.0 worker with no billing, no patching, no replay issues.
  - Once 1.0 workflows drain, shut down the 1.0 worker.
- **"Aha moment":** "You just deployed a non-replay-safe change with zero patching. Version isolation replaced the `workflow.patched()` guard from Exercise 1."
- **Sunset v1.0:**
  - Once v1.0 workflows have drained, shut down the 1.0 worker.
  - Sunset the v1.0 deployment version via CLI (e.g., `temporal worker deployment version set-draining`).
  - Verify with `temporal worker deployment describe` — v1.0 should no longer appear as an active version.
  - **Teaches:** How to cleanly decommission a deployment version once its workflows have drained.
- **Teaches:**
  - What Worker Deployments and Deployment Versions are — now visible with two versions running side by side
  - Rainbow deployment model: multiple versions coexist, Temporal routes traffic between them
  - How PINNED eliminates the need for patching when workflows should complete on the version they started on
  - How and when to sunset old deployment versions

### Part B Discussion Sidebar: The Decision Matrix

Present this table (from Temporal docs) to frame when each behavior applies:

| Workflow Duration | Uses CaN? | Recommended Behavior | Patching Required? |
|---|---|---|---|
| Short (completes before next deploy) | N/A | PINNED | Never |
| Medium (spans multiple deploys) | No | AUTO_UPGRADE | Yes |
| Long (weeks to years) | Yes | PINNED + upgrade on CaN | Never |
| Long (weeks to years) | No | AUTO_UPGRADE + patching | Yes |

- `ValetParkingWorkflow` → PINNED. Each parking transaction should complete on the code version it started on — no mid-execution surprises. No patching needed.
- `ParkingLotWorkflow` is immortal with CaN → AUTO_UPGRADE. It migrates to 2.0 automatically on the next workflow task. No code changes to ParkingLotWorkflow in this exercise, so no replay safety concerns.
- AUTO_UPGRADE *does* still require patching for non-replay-safe changes — we'll revisit this in Part D when we need to make a breaking change to ParkingLotWorkflow.

### Part C: Emergency Rollback & Remediation (~10 min)

- **Motivation:** "Things don't always go smoothly. Let's see what happens when a bad deploy makes it to production — and how Worker Versioning gives you tools to respond immediately."
- **Scenario:** The team deploys v3.0 with a bug in the `bill_customer` activity — for example, the developer adds a reference to a field that doesn't exist on the input dataclass (like `input.tip_percentage`), causing an `AttributeError`. The activity fails on every attempt and retries forever. Workflows that reach the billing step get stuck.
- **Code changes (introduce the bug intentionally):**
  - Modify the `bill_customer` activity to include the buggy line. This should be a small, realistic mistake — one line that causes an exception.
- **Deploy v3.0:**
  - Start 3.0 worker: `make start-worker BUILD_ID=3.0`
  - Set 3.0 as current: `temporal worker deployment set-current --deployment-name valet --build-id 3.0`
  - Watch new workflows start on 3.0. After a few seconds, notice activity failures in the Temporal UI or worker logs — the billing activity is failing and retrying.
- **Step 1 — Instant rollback (stop the bleeding):**
  - Set v2.0 back as current: `temporal worker deployment set-current --deployment-name valet --build-id 2.0`
  - **Immediately**, no new workflows are routed to v3.0. New workflows start on v2.0 with working billing.
  - In-flight v3.0 workflows are still pinned to v3.0 — they're stuck at billing with no rescue yet.
- **Step 2 — Evacuate in-flight v3.0 workflows to v2.0:**
  - Use `temporal workflow update-options` to reassign v3.0 workflows to v2.0. This changes their pinned deployment version so the v2.0 worker picks them up.
  - **Why this is replay-safe:** The workflow code between v2.0 and v3.0 is identical — the bug is in the activity implementation, not the workflow definition. The v2.0 worker replays the workflow, reaches the billing step, and calls the working v2.0 activity. Failed activity attempts in history don't affect determinism — the workflow just sees "activity not yet completed" and retries.
  - Observe: the previously-stuck workflows now complete successfully on v2.0.
- **Step 3 — Fix the bug and deploy v3.1:**
  - Revert the buggy line in `bill_customer` (fix the `AttributeError`).
  - Start a v3.1 worker: `make start-worker BUILD_ID=3.1`
  - Set v3.1 as current: `temporal worker deployment set-current --deployment-name valet --build-id 3.1`
  - New workflows now flow through v3.1 with working billing.
- **Step 4 — Clean up:**
  - Shut down the v3.0 worker.
  - Sunset the v3.0 deployment version (same CLI as we used for v1.0 earlier).
- **Teaches:**
  - `set-current` as an instant rollback mechanism — no code redeploy needed
  - Fix-forward with a patch version (v3.1) rather than permanently rolling back
  - `update-options` to evacuate in-flight workflows from a broken version
  - Blast radius containment with PINNED: only workflows that started on v3.0 are affected, and they can be surgically moved
  - Why activity-only bugs are safe to move between versions (no workflow history divergence)
  - Sunsetting a broken deployment version after remediation

### Part D: Upgrade on Continue-as-New (~8 min)

- **Goal:** Make a non-replay-safe change to `ParkingLotWorkflow` without patching.
- **Motivation:** "We need to make a breaking change to ParkingLotWorkflow. Since it's AUTO_UPGRADE, we'd normally need to patch. But since it already uses continue-as-new, there's a cleaner option: switch to PINNED + upgrade on CaN. Each run stays on its version, and the new run after CaN starts on the new version."
- **Code changes:** Switch ParkingLotWorkflow from AUTO_UPGRADE to PINNED, add upgrade-on-CaN check, make the non-replay-safe change (TBD — specific change to ParkingLotWorkflow).
- **Deploy v4.0:**
  - Start 4.0 worker: `make start-worker BUILD_ID=4.0`
  - Set 4.0 as current: `temporal worker deployment set-current --deployment-name valet --build-id 4.0`
- **Observe:** ParkingLotWorkflow finishes its current run on v3.1 code, performs CaN, and the new run starts on v4.0 with the updated code — no patching needed.
- **Teaches:**
  - The upgrade-on-CaN pattern for long-lived workflows that use continue-as-new
  - When to switch from AUTO_UPGRADE to PINNED + upgrade on CaN
  - Why this eliminates patching for workflows that already use CaN

---

## Learning Objectives

1. Distinguish between Worker Deployments and Worker Deployment Versions
2. Understand why Temporal uses a "rainbow" deployment model (multiple versions coexisting)
3. Understand when to use AUTO_UPGRADE vs PINNED versioning behaviors
4. Configure worker versioning: deployment name, build ID, `WorkerDeploymentConfig`
5. Add `VersioningBehavior` to workflow definitions
6. Use CLI to set Current Version and inspect deployment state
7. Deploy a new version alongside an existing one and observe traffic routing
8. Perform an emergency rollback using `set-current` and evacuate workflows using `update-options`
9. Sunset old or broken deployment versions
10. See how PINNED versioning eliminates the need for patching when workflows should complete on the version they started on
11. Understand the decision matrix for choosing PINNED vs AUTO_UPGRADE
12. Understand the upgrade-on-continue-as-new pattern for long-lived workflows

---

## Key Design Decisions

- **Clean slate:** Restart Temporal server at the start — no unversioned workflow orphan problem
- **All code changes before first worker start** — every workflow is versioned from birth
- **Four versions (1.0, 2.0, 3.0→3.1, 4.0)** — 1.0 is the baseline, 2.0 adds billing, 3.0 is the bad deploy, 3.1 is the fix-forward, 4.0 is the CaN upgrade
- **PINNED is the hero:** The "aha moment" is deploying a breaking change with zero patching
- **AUTO_UPGRADE is the supporting character:** Used for ParkingLotWorkflow, explained via the decision matrix
- **Explicitly remove `workflow.patched()`** in Part B — switching from patching to pinned is the narrative climax
- **Emergency rollback in Part C** — shows the operational safety net that versioning provides; the bug is in the activity (not the workflow), so `update-options` is replay-safe
- **Sunsetting appears twice** — once for v1.0 (happy path drain) and once for v3.0 (emergency cleanup), reinforcing the concept
- **Trampolining in Part D** — completes the picture by showing how CaN-based workflows can avoid patching entirely
