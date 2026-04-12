# Exercise 3: Deploying on K8s with the Worker Controller

**Time:** ~30 minutes
**Theme:** "You've been managing versioning by hand. The Worker Controller automates all of that."
**Skills:** TemporalWorkerDeployment CRD, Progressive rollout, rainbow deployments, rollback, emergency remediation

---

## Pre-Setup

Ensure `minikube`, `kubectl`, `helm`, and the `temporal` CLI are installed and available.

1. In a dedicated terminal, start the Temporal dev server:

```bash
temporal server start-dev
```

> **Note:** Starting a fresh dev server means we're working with a clean slate — no history from previous exercises. The code picks up where Exercise 2 left off, but we'll number our builds from 1.0 again so it's easy to track where we are in this exercise.

2. In a new terminal, navigate to the exercise directory and run setup (starts minikube, installs the Worker Controller CRDs and controller, and applies the Temporal connection config):

```bash
cd exercises/exercise-3/practice
make setup
```

---

## Part A — Deploy 1.0 and generate load (~8 min)

1. Ensure you're still in the `exercises/exercise-3/practice` directory from Pre-Setup.

2. Examine the k8s manifests:
   - `k8s/temporal-connection.yaml` — points to the host Temporal server
   - `k8s/valet-worker.yaml` — `TemporalWorkerDeployment` with `AllAtOnce` strategy

> **Note:** The initial manifest uses `AllAtOnce` — every replica cuts over immediately. This is fine for the first deploy, but for non-replay-safe changes you'll want a `Progressive` strategy so old and new versions coexist safely. We'll switch to that in Part B.

3. Build and deploy 1.0:

```bash
make build tag=1.0
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

---

## Part B — Non-replay-safe change with Progressive rollout (~14 min)

**Scenario:** Add a notification when the owner's car is being retrieved. This adds a new activity call to the workflow sequence — a non-replay-safe change. With worker versioning (`PINNED` behavior), each version runs its own code, so the Worker Controller will keep 1.0 workers alive for in-flight workflows while ramping up 2.0 for new ones.

> **Why Progressive?** A Progressive rollout introduces the new version gradually — starting with a small percentage of new workflow executions, pausing to let you verify things are healthy, then ramping up. Meanwhile, in-flight workflows stay pinned to their original version. This is the **rainbow deployment model**: multiple versions coexist, each serving the workflows that belong to it.

1. Switch to Progressive rollout strategy. Examine `k8s/valet-worker-progressive.yaml` first — note the `steps` defining the ramp schedule:

```bash
kubectl apply -f k8s/valet-worker-progressive.yaml
```

2. Make the code change in `valet/valet_parking_workflow.py` — add a `notify_owner` call after the sleep (when the car is being retrieved), right before the move back to the valet zone:

   ```python
   await workflow.sleep(input.trip_duration_seconds)

   # Notify the owner their car is being retrieved
   await workflow.execute_activity(
       notify_owner,
       NotifyOwnerInput(
           license_plate=input.license_plate,
           message="Your car is being retrieved!",
       ),
       start_to_close_timeout=timedelta(seconds=10),
   )

   # Move car from parking space back to the original valet zone
   ```

3. Build and deploy 2.0:

```bash
make build tag=2.0
kubectl patch twd valet-worker --type merge \
  -p '{"spec":{"template":{"spec":{"containers":[{"name":"valet-worker","image":"valet-worker:2.0"}]}}}}'
```

4. Watch the progressive rollout unfold:

```bash
kubectl get twd -w
```

   - 2.0 starts at **rampPercentage: 25%** — only 25% of *new* workflow executions go to 2.0
   - After 30s, ramps to **75%**
   - After another 30s, reaches **100%** — 2.0 becomes the Current Version

5. While the rollout progresses, observe the rainbow deployment in another terminal:

```bash
kubectl get deployments
```

   Both 1.0 and 2.0 Deployments run simultaneously:
   - **1.0 workers** continue serving in-flight workflows pinned to version 1.0
   - **2.0 workers** serve new workflow executions (at whatever the current ramp percentage is)

6. Watch individual pods serving their respective versions:

```bash
kubectl get pods -l app=valet-worker --show-labels
```

7. Verify in the Temporal UI at [http://localhost:8233](http://localhost:8233):
   - New workflows include a "Your car is being retrieved!" notification before the return trip
   - Older in-flight workflows complete without it
   - Over time, 1.0 workers scale down as their pinned workflows finish

> **Key insight:** The Worker Controller orchestrates the entire rainbow deployment automatically. You didn't need to manually manage traffic routing, scale replicas, or coordinate draining — just update the image tag and the controller handles the rest.

---

## Part C — Rollback & emergency remediation (~8 min)

**Scenario 1 — Rollback:** "The retrieval notification has a bug!"

```bash
kubectl patch twd valet-worker --type merge \
  -p '{"spec":{"template":{"spec":{"containers":[{"name":"valet-worker","image":"valet-worker:1.0"}]}}}}'
```

Watch the rollback:

```bash
kubectl get twd -w
```

The controller creates a new version (effectively a new deployment of the 1.0 code) and routes new traffic to it. 2.0-pinned workflows complete on their 2.0 workers, then 2.0 scales down.

```bash
kubectl get deployments -w
```

Watch the 2.0 Deployment scale to zero as its pinned workflows drain.

**Scenario 2 — Bad deploy:**

```bash
# Build a broken image (add raise RuntimeError("startup crash") to worker.py main())
make build tag=bad
kubectl patch twd valet-worker --type merge \
  -p '{"spec":{"template":{"spec":{"containers":[{"name":"valet-worker","image":"valet-worker:bad"}]}}}}'
```

Observe:

```bash
kubectl get pods -w
```

- New pods **crash-loop**
- The version **never becomes Registered** — the worker can't connect to Temporal
- **New workflows keep going to the previous working version** — the controller protects production

Watch logs to see the controller's perspective:

```bash
make logs
```

Fix by deploying a corrected image or rolling back:

```bash
kubectl patch twd valet-worker --type merge \
  -p '{"spec":{"template":{"spec":{"containers":[{"name":"valet-worker","image":"valet-worker:1.0"}]}}}}'
```

> **Key takeaway:** The Worker Controller protects production. A bad deploy never becomes current. Rollback is just another `kubectl patch`.
