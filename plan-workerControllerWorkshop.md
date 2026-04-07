# Plan: Worker Controller Workshop Exercise (Minikube)

Build a hands-on workshop exercise where attendees deploy the valet worker to minikube using the Temporal Worker Controller, then practice deploying code changes (replay-safe and non-replay-safe), observing progressive rollouts, and performing rollbacks/emergency remediation.

## TL;DR

Containerize the existing valet worker, deploy it to minikube alongside a self-hosted Temporal Server and the Worker Controller, then guide attendees through two deployment exercises (AllAtOnce for replay-safe, Progressive for non-replay-safe), a rollback, and emergency remediation. All local — no cloud dependencies.

## Decisions

- **Self-hosted Temporal** in minikube via official `temporalio/helm-charts` (PostgreSQL backend, no Elasticsearch). Avoids attendees needing Temporal Cloud accounts.
- **No Skaffold** — use `eval $(minikube docker-env)` + `docker build` + raw k8s manifests + `kubectl apply`. Keeps the focus on the worker controller, not build tooling.
- **Makefile** wraps common commands (build, deploy, load) for convenience.
- **Pinned workflow behavior** — all workflows pin to their starting version, demonstrating safe side-by-side execution during progressive rollouts.
- **Load simulator runs locally** via `kubectl port-forward` — attendees see output directly in their terminal.
- **`imagePullPolicy: IfNotPresent`** in the TemporalWorkerDeployment so minikube uses locally-built images without a registry.

## Steps

### Phase 1: Infrastructure files (new files to create)

1. **`Dockerfile`** — Multi-stage Python image. Copies `src/`, `pyproject.toml`, `requirements.txt`. Installs deps. Entrypoint runs `python -m valet.worker`. Slim base image (python:3.14-slim).

2. **`k8s/temporal-server-values.yaml`** — Helm values for deploying Temporal Server into minikube. PostgreSQL only, single replicas, no Elasticsearch, resource limits tuned for minikube. Must be Temporal Server ≥ v1.29.1 for worker versioning support.

3. **`k8s/temporal-connection.yaml`** — `TemporalConnection` CRD that points to the in-cluster Temporal frontend service (`temporal-frontend.temporal.svc.cluster.local:7233`). No TLS (self-hosted, in-cluster).

4. **`k8s/valet-worker.yaml`** — `TemporalWorkerDeployment` CRD for the valet worker. Initial strategy: `AllAtOnce`. References the TemporalConnection. Sets `temporalNamespace: default`, `replicas: 1`, `imagePullPolicy: IfNotPresent`. Template spec includes the valet worker container.

5. **`k8s/valet-worker-progressive.yaml`** — Variant of the above with `Progressive` strategy and workshop-friendly short pause durations (`rampPercentage: 25 / pauseDuration: 30s`, `rampPercentage: 75 / pauseDuration: 30s`). Used in Exercise 2.

6. **`Makefile`** — Targets:
   - `setup` — start minikube, install Temporal Server helm chart, install Worker Controller CRDs + controller
   - `build` — builds Docker image inside minikube's Docker daemon (via `eval $(minikube docker-env)`)
   - `deploy` — `kubectl apply` the connection + worker deployment
   - `status` — `kubectl get twd` + `kubectl get deployments`
   - `logs` — controller logs
   - `port-forward` — forward temporal frontend to localhost:7233
   - `load` — run load simulator locally
   - `clean` — tear down everything

### Phase 2: Worker code changes for versioning

7. **Update `src/valet/worker.py`** — Read env vars `TEMPORAL_ADDRESS` (default `localhost:7233`), `TEMPORAL_NAMESPACE` (default `default`), `TEMPORAL_DEPLOYMENT_NAME`, `TEMPORAL_WORKER_BUILD_ID`. When deployment name + build ID are set, configure `WorkerDeploymentConfig(version=WorkerDeploymentVersion(...), use_worker_versioning=True)` and pass as `deployment_config=` to `Worker()`. Falls back to unversioned mode when env vars are absent (keeps local `python -m valet.worker` working).

8. **Update `src/valet/activities.py`** — The `request_space` and `release_space` activities create their own `Client.connect("localhost:7233")`. Change to read `TEMPORAL_ADDRESS` and `TEMPORAL_NAMESPACE` from env vars so they work inside k8s.

### Phase 3: Exercise code changes (manual edit instructions in WORKSHOP.md)

9. **Exercise 1 — Replay-safe change** — The workshop guide walks attendees through manually editing the `move_car` activity to add a "distance_driven" log line and change the random distance range from `0.1–2.0` to `0.5–5.0` miles. Activity-internal change — does not affect workflow command sequence.

10. **Exercise 2 — Non-replay-safe change** — The workshop guide walks attendees through manually adding a new `notify_owner` activity to `ValetParkingWorkflow` between the sleep and the return `move_car`. Includes step-by-step instructions for adding the new activity function in `activities.py`, new `NotifyOwnerInput`/`NotifyOwnerOutput` in `models.py`, and registration in `worker.py`. This changes the workflow's command sequence — existing in-flight workflows would fail if replayed on new code.

### Phase 4: Workshop exercise guide (markdown document)

11. **`exercises/WORKSHOP.md`** — Step-by-step attendee-facing instructions:

#### Part 0: Prerequisites & Setup
- Install: minikube, kubectl, helm, docker, python 3.14
- `make setup` — starts minikube, deploys Temporal Server, installs Worker Controller
- Wait for all pods ready

#### Part 1: Deploy v1
- Examine the valet workflow code, understand the workflow steps
- `make build TAG=v1` — build and tag Docker image
- `make deploy` — apply TemporalConnection + TemporalWorkerDeployment
- `kubectl get twd` — observe the deployment register as current version
- `kubectl get deployments` — see the controller-created versioned Deployment
- Open Temporal Web UI (port-forward) — see the worker in the Workers tab

#### Part 2: Generate load
- In a separate terminal: `make port-forward`
- In a third terminal: `make load` (runs `python -m valet.load_simulator`)
- Observe workflows being created in Temporal UI — sleeping for various durations, some completing
- Note: many workflows will be in-flight (sleeping), making them long-running

#### Part 3: Exercise 1 — Replay-safe change (AllAtOnce)
- Follow the manual edit instructions to modify the `move_car` activity:
  - In `src/valet/activities.py`, find the `move_car` activity
  - Add a log line: `activity.logger.info(f"distance_driven: {distance}")`
  - Change the random distance range from `random.uniform(0.1, 2.0)` to `random.uniform(0.5, 5.0)`
- Review the change — it only modifies activity internals
- Build new image: `make build TAG=v2`
- Update the image in the TemporalWorkerDeployment: `kubectl patch twd valet-worker ...` (sets new image tag)
- Watch: `kubectl get twd -w` — observe AllAtOnce strategy immediately make v2 current
- Check: old workflows continue fine (activity internals don't affect replay)
- `kubectl get deployments` — see v1 Deployment scaling down as workflows drain, v2 serving all traffic

#### Part 4: Exercise 2 — Non-replay-safe change (Progressive)
- First, switch rollout strategy to Progressive: `kubectl apply -f k8s/valet-worker-progressive.yaml`
- Follow the manual edit instructions to add a `notify_owner` activity:
  - In `src/valet/models.py`, add `NotifyOwnerInput` and `NotifyOwnerOutput` dataclasses
  - In `src/valet/activities.py`, add a `notify_owner` activity function
  - In `src/valet/valet_workflow.py`, add `await workflow.execute_activity(notify_owner, ...)` between the sleep and the return `move_car` call
  - In `src/valet/worker.py`, register the new activity
- Build: `make build TAG=v3`
- Update image: `kubectl patch twd valet-worker ...` (image → v3)
- Watch: `kubectl get twd -w` — observe progressive rollout:
  - v3 starts at rampPercentage: 25%, then 75%, then 100%
  - Both v2 and v3 Deployments run simultaneously
  - v2 workers serve existing in-flight workflows (which would break on v3 worker replay)
  - v3 workers serve new workflow executions
- `kubectl get deployments` — multiple versioned Deployments visible
- Temporal UI — new workflows have the `notify_owner` activity, old ones don't

#### Part 5: Rollback
- Simulate a problem with v3: "oh no, notify_owner has a bug"
- Roll back by setting image back to v2: `kubectl patch twd valet-worker ...`
- Watch: controller creates a new version (v4 = old v2 code), routes traffic to it
- New workflows go to v4 (old code), v3 pinned workflows complete on v3, then v3 scales down
- Verify in Temporal UI — new workflows no longer have `notify_owner`

#### Part 6: Emergency remediation
- Deploy a "bad" version that crashes on startup (e.g., introduce a syntax error): `make build TAG=v5-bad`, deploy
- Watch: controller creates the new Deployment, but pods crash-loop
- The version never becomes Registered because the worker can't connect
- New workflows keep going to the previous working version (safe!)
- Fix: deploy a corrected image: `make build TAG=v5-fixed`, patch the TWD
- Or: roll back to v4 by reverting the image tag
- Key takeaway: the controller protects running workflows — a bad deploy doesn't break anything

## Relevant files

### Existing (to modify)
- `src/valet/worker.py` — Add env var reading + `WorkerDeploymentConfig` setup. Currently hardcodes `localhost:7233`.
- `src/valet/activities.py` — Change `Client.connect("localhost:7233")` calls in `request_space`/`release_space` to use env vars.

### New files to create
- `Dockerfile` — Python multi-stage build for the valet worker
- `k8s/temporal-server-values.yaml` — Helm values for self-hosted Temporal in minikube
- `k8s/temporal-connection.yaml` — TemporalConnection CRD instance
- `k8s/valet-worker.yaml` — TemporalWorkerDeployment CRD (AllAtOnce)
- `k8s/valet-worker-progressive.yaml` — TemporalWorkerDeployment CRD (Progressive)
- `Makefile` — Build/deploy/status/cleanup convenience targets
- `exercises/WORKSHOP.md` — Attendee-facing step-by-step guide (includes inline manual edit instructions for each exercise)

### Reference (from worker controller repo)
- `WorkerDeploymentConfig` / `WorkerDeploymentVersion` from `temporalio.worker` — Python SDK versioning API
- `TemporalWorkerDeployment` / `TemporalConnection` CRDs — controller API
- Worker controller sets `TEMPORAL_ADDRESS`, `TEMPORAL_NAMESPACE`, `TEMPORAL_DEPLOYMENT_NAME`, `TEMPORAL_WORKER_BUILD_ID` automatically

## Verification

1. `make setup` completes — Temporal Server pods Running, Worker Controller pod Running, CRDs installed (`kubectl get crd | grep temporal`)
2. `make build TAG=v1 && make deploy` — `kubectl get twd` shows valet-worker with a registered version; `kubectl get pods` shows valet-worker pods running
3. `make load` starts creating workflows visible in Temporal UI (port 8080)
4. After v2 deploy (replay-safe): `kubectl get twd` shows v2 as current, v1 draining. Existing workflows complete normally.
5. After v3 deploy (non-replay-safe): `kubectl get twd` shows progressive rollout stepping through percentages. Two Deployment sets visible. New workflows have `notify_owner` activity.
6. After rollback: new workflows revert to old behavior. No workflow failures.
7. After bad deploy: pods crash-loop but traffic stays on previous version. No workflow failures. Fix deploy resolves crash.

## Further Considerations

1. **Temporal Server Helm chart version** — Need to verify the latest `temporalio/helm-charts` deploys Server ≥ v1.29.1 with worker versioning enabled. May need to set `server.config.workerVersioning.enabled: true` or equivalent. Recommend testing the full setup end-to-end before the workshop.

2. **Minikube resources** — Self-hosted Temporal + PostgreSQL + Worker Controller + worker pods will need ≥ 4 CPU / 8GB RAM allocated to minikube. Should document `minikube start --cpus=4 --memory=8192` in prerequisites.

3. **Exercise delivery format** — Using manual edit instructions inline in the workshop guide. This is more resilient to upstream code changes and teaches attendees what they're actually changing. If the code stabilizes later, patch files or git branches could be added as a convenience.
