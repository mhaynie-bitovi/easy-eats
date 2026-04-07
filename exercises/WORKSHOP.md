# Worker Controller Workshop

Deploy the valet worker to minikube using the Temporal Worker Controller, then practice deploying code changes (replay-safe and non-replay-safe), observing progressive rollouts, and performing rollbacks.

---

## Prerequisites

- [minikube](https://minikube.sigs.k8s.io/docs/start/)
- [kubectl](https://kubernetes.io/docs/tasks/tools/)
- [Helm](https://helm.sh/docs/intro/install/)
- [Docker](https://docs.docker.com/get-docker/)
- Python 3.14+
- This repo cloned and `pip install -r requirements.txt` completed

---

## Part 0: Setup

Start minikube, deploy Temporal Server, and install the Worker Controller:

```bash
make setup
```

This will:
1. Start minikube with 4 CPUs / 8 GB RAM
2. Deploy Temporal Server (PostgreSQL backend) into the `temporal` namespace
3. Install the Worker Controller into the `temporal-worker-controller` namespace

Wait for all pods to be ready:

```bash
kubectl get pods -n temporal
kubectl get pods -n temporal-worker-controller
```

Verify the Worker Controller CRDs are installed:

```bash
kubectl get crd | grep temporal
```

You should see `temporalconnections.temporal.io` and `temporalworkerdeployments.temporal.io`.

---

## Part 1: Deploy v1

### Understand the workflow

Open `src/valet/valet_workflow.py` and read through the `ValetParkingWorkflow`:

1. **request_space** — Asks the parking lot workflow for a space
2. **move_car** — Drives the car from the valet zone to the assigned space
3. **sleep** — Waits for the owner's trip duration
4. **find_nearest_valet_zone** — Picks a return valet zone
5. **move_car** — Drives the car back to the valet zone
6. **release_space** — Returns the space to the parking lot

### Build the Docker image

```bash
make build TAG=v1
```

### Deploy

```bash
make deploy
```

### Verify

```bash
make status
```

You should see:
- A `TemporalWorkerDeployment` named `valet-worker`
- A Kubernetes Deployment created by the controller with versioned pods
- Pods in `Running` state

Open the Temporal Web UI:

```bash
make port-forward
```

Navigate to [http://localhost:8080](http://localhost:8080) and check the **Workers** tab — you should see the valet worker registered.

---

## Part 2: Generate load

In a **separate terminal**, ensure port-forwarding is running:

```bash
make port-forward
```

In a **third terminal**, start the load simulator:

```bash
make load
```

Watch workflows being created. The simulator starts a new `ValetParkingWorkflow` every 1–5 seconds, each with a random trip duration of 5–30 seconds. Many workflows will be in-flight (sleeping) at any given time, making them long-running.

Check the Temporal UI — you'll see workflows starting, sleeping, and completing.

**Leave the load simulator running for the rest of the workshop.**

---

## Part 3: Exercise 1 — Replay-safe change (AllAtOnce)

In this exercise, you'll make a change that only modifies activity internals — it doesn't affect the workflow's command sequence, so it's safe to replay existing workflows on the new code.

### Make the code change

Edit `src/valet/activities.py` and find the `move_car` activity:

**1. Add a log line** after the `distance_driven` calculation:

```python
distance_driven = round(random.uniform(0.1, 2.0), 2)

# Add this line:
activity.logger.info(f"distance_driven: {distance_driven}")
```

**2. Change the random distance range** from `0.1–2.0` to `0.5–5.0`:

```python
# Change this:
distance_driven = round(random.uniform(0.1, 2.0), 2)

# To this:
distance_driven = round(random.uniform(0.5, 5.0), 2)
```

Your final `move_car` activity should look like:

```python
@activity.defn
async def move_car(input: MoveCarInput) -> MoveCarOutput:
    start_time = datetime.now(timezone.utc).isoformat()

    print(
        f"Moving car {input.license_plate} "
        f"from {input.from_location.kind}:{input.from_location.id} "
        f"to {input.to_location.kind}:{input.to_location.id}"
    )

    distance_driven = round(random.uniform(0.5, 5.0), 2)
    activity.logger.info(f"distance_driven: {distance_driven}")

    # Simulate driving time
    await asyncio.sleep(random.uniform(1.0, 5.0))

    end_time = datetime.now(timezone.utc).isoformat()

    return MoveCarOutput(
        distance_driven=distance_driven,
        start_time=start_time,
        end_time=end_time,
    )
```

### Build and deploy

```bash
make build TAG=v2
```

Update the image in the TemporalWorkerDeployment:

```bash
kubectl patch twd valet-worker --type merge -p '{"spec":{"template":{"spec":{"containers":[{"name":"valet-worker","image":"valet-worker:v2"}]}}}}'
```

### Observe

Watch the rollout:

```bash
kubectl get twd -w
```

With the **AllAtOnce** strategy, v2 immediately becomes the current version. Since the change is replay-safe (only activity internals changed), existing in-flight workflows continue fine on v2 workers.

```bash
kubectl get deployments
```

You'll see the v1 Deployment scaling down as existing workflows drain, and v2 serving all traffic.

---

## Part 4: Exercise 2 — Non-replay-safe change (Progressive)

In this exercise, you'll add a new activity to the workflow — this changes the command sequence, so existing workflows would fail if replayed on new code. You'll use the **Progressive** rollout strategy so old and new versions run side-by-side.

### Switch to Progressive rollout strategy

```bash
kubectl apply -f k8s/valet-worker-progressive.yaml
```

### Make the code changes

#### 1. Add new models (`src/valet/models.py`)

Add these dataclasses at the end of the file:

```python
@dataclass
class NotifyOwnerInput:
    license_plate: str
    message: str


@dataclass
class NotifyOwnerOutput:
    notified: bool
```

#### 2. Add new activity (`src/valet/activities.py`)

Add the import to the imports from `valet.models`:

```python
from valet.models import (
    FindNearestValetZoneInput,
    FindNearestValetZoneOutput,
    Location,
    LocationKind,
    MoveCarInput,
    MoveCarOutput,
    NotifyOwnerInput,      # Add this
    NotifyOwnerOutput,     # Add this
    NUM_VALET_ZONES,
    ParkingLotInput,
    ReleaseSpaceInput,
    ReleaseSpaceOutput,
    RequestSpaceInput,
    RequestSpaceOutput,
)
```

Add the new activity function at the end of the file:

```python
@activity.defn
async def notify_owner(input: NotifyOwnerInput) -> NotifyOwnerOutput:
    activity.logger.info(
        f"Notifying owner of {input.license_plate}: {input.message}"
    )
    # Simulate notification delay
    await asyncio.sleep(0.5)
    return NotifyOwnerOutput(notified=True)
```

#### 3. Add activity call to workflow (`src/valet/valet_workflow.py`)

Add the imports:

```python
with workflow.unsafe.imports_passed_through():
    from valet.activities import (
        find_nearest_valet_zone,
        move_car,
        notify_owner,         # Add this
        release_space,
        request_space,
    )
    from valet.models import (
        FindNearestValetZoneInput,
        Location,
        LocationKind,
        MoveCarInput,
        NotifyOwnerInput,     # Add this
        ReleaseSpaceInput,
        RequestSpaceInput,
        ValetParkingInput,
        ValetParkingOutput,
    )
```

Add the activity call **after** the `workflow.sleep` and **before** the `find_nearest_valet_zone` call:

```python
        # Wait for the owner's trip
        await workflow.sleep(input.trip_duration_seconds)

        # Notify the owner their car is being retrieved  <-- ADD THIS BLOCK
        await workflow.execute_activity(
            notify_owner,
            NotifyOwnerInput(
                license_plate=input.license_plate,
                message="Your car is being retrieved!",
            ),
            start_to_close_timeout=timedelta(seconds=10),
        )

        # Find nearest valet zone for return
        valet_zone_result = await workflow.execute_activity(
```

#### 4. Register the activity in the worker (`src/valet/worker.py`)

Update the imports:

```python
from valet.activities import (
    find_nearest_valet_zone,
    move_car,
    notify_owner,         # Add this
    release_space,
    request_space,
)
```

Add `notify_owner` to the activities list in the Worker constructor:

```python
    worker = Worker(
        client,
        task_queue="valet",
        workflows=[ValetParkingWorkflow, ParkingLotWorkflow],
        activities=[move_car, request_space, release_space, find_nearest_valet_zone, notify_owner],
        deployment_config=deployment_config,
    )
```

### Build and deploy

```bash
make build TAG=v3
```

Update the image:

```bash
kubectl patch twd valet-worker --type merge -p '{"spec":{"template":{"spec":{"containers":[{"name":"valet-worker","image":"valet-worker:v3"}]}}}}'
```

### Observe the progressive rollout

```bash
kubectl get twd -w
```

You'll see:
- v3 starts at **rampPercentage: 25%** (pauses 30s)
- Then ramps to **75%** (pauses 30s)
- Then reaches **100%**

```bash
kubectl get deployments
```

Both v2 and v3 Deployments run simultaneously:
- **v2 workers** serve existing in-flight workflows (which would break if replayed on v3)
- **v3 workers** serve new workflow executions

Check the Temporal UI — new workflows include the `notify_owner` activity step, old ones don't.

---

## Part 5: Rollback

Simulate a problem: "Oh no, `notify_owner` has a bug!"

Roll back by setting the image back to v2:

```bash
kubectl patch twd valet-worker --type merge -p '{"spec":{"template":{"spec":{"containers":[{"name":"valet-worker","image":"valet-worker:v2"}]}}}}'
```

### Observe

```bash
kubectl get twd -w
```

The controller creates a new version (effectively v4 = old v2 code) and routes new traffic to it. v3-pinned workflows complete on their v3 workers, then v3 scales down.

Check the Temporal UI — new workflows no longer have the `notify_owner` activity.

---

## Part 6: Emergency remediation

### Deploy a bad version

Introduce a syntax error to simulate a broken build. For example, add `raise RuntimeError("startup crash")` as the first line of `main()` in `src/valet/worker.py`.

```bash
make build TAG=v5-bad
kubectl patch twd valet-worker --type merge -p '{"spec":{"template":{"spec":{"containers":[{"name":"valet-worker","image":"valet-worker:v5-bad"}]}}}}'
```

### Observe

```bash
kubectl get pods -w
```

The new pods **crash-loop**. The version never becomes Registered because the worker can't connect to Temporal.

```bash
kubectl get twd
```

New workflows **keep going to the previous working version** — the controller protects running workflows.

### Fix

Option A — deploy a corrected image:

```bash
# Undo the syntax error, then:
make build TAG=v5-fixed
kubectl patch twd valet-worker --type merge -p '{"spec":{"template":{"spec":{"containers":[{"name":"valet-worker","image":"valet-worker:v5-fixed"}]}}}}'
```

Option B — roll back to the previous working version:

```bash
kubectl patch twd valet-worker --type merge -p '{"spec":{"template":{"spec":{"containers":[{"name":"valet-worker","image":"valet-worker:v2"}]}}}}'
```

### Key takeaway

The Worker Controller protects running workflows — a bad deploy doesn't break anything. The broken version never becomes current, and traffic stays on the last working version.

---

## Cleanup

When you're done:

```bash
make clean
```

This tears down the worker deployment, Temporal Server, Worker Controller, and stops minikube.
