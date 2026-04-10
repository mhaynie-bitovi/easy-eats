# Temporal Worker Versioning Workshop

Three hands-on exercises to learn Temporal worker versioning, from replay testing to Kubernetes-based deployments with the Worker Controller.

**Prerequisites:**
- [Temporal CLI](https://docs.temporal.io/cli#install)
- Python 3.12+
- This repo cloned and `pip install -r requirements.txt` completed
- For Exercise 3: [minikube](https://minikube.sigs.k8s.io/docs/start/), [kubectl](https://kubernetes.io/docs/tasks/tools/), [Helm](https://helm.sh/docs/intro/install/), [Docker](https://docs.docker.com/get-docker/)

---

## Exercises

| # | Topic | Time | Folder |
|---|---|---|---|
| 1 | [Patching a Non-Deterministic Change + Replay Testing](exercise-1/README.md) | ~30 min | `exercise-1/` |
| 2 | [Deploying Changes with Worker Versioning](exercise-2/README.md) | ~30 min | `exercise-2/` |
| 3 | [Deploying on K8s with the Worker Controller](exercise-3/README.md) | ~30 min | `exercise-3/` |

---

## Cleanup

```bash
# Stop the load simulator (Ctrl+C)

# Tear down k8s resources (Exercise 3)
cd exercises/exercise-3/practice
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
