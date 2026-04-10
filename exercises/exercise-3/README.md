# Exercise 3: Deploying on K8s with the Worker Controller

**Time:** ~30 minutes
**Theme:** "You've been managing versioning by hand. The Worker Controller automates all of that."
**Skills:** TemporalWorkerDeployment CRD, AllAtOnce vs Progressive rollout, rollback, emergency remediation

---

## Pre-Setup

Ensure the following are running/available:
- Minikube running with 4 CPUs / 4 GB RAM
- Temporal dev server running on the host (`localhost:7233`)
- Worker Controller installed (CRDs + controller pod)
- V1, V2, V3 container images pre-built in minikube's Docker daemon
- `kubectl` and `temporal` CLI available

```bash
cd exercises/exercise-3/practice

# Start Temporal dev server (dedicated terminal)
make temporal-server

# Setup minikube and Worker Controller (new terminal)
make setup
```

---

## Part A — Deploy V1 and generate load (~8 min)

1. Ensure you're still in the `exercises/exercise-3/practice` directory from Pre-Setup.

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

---

## Part B — Replay-safe change with AllAtOnce (~8 min)

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

---

## Part C — Non-replay-safe change with Progressive (~8 min)

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

---

## Part D — Rollback & emergency remediation (~6 min)

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
