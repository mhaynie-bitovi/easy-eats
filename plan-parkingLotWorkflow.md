# Plan: Parking Lot Workflow

A single long-running `ParkingLotWorkflow` manages all parking space assignments. Valet workflows request and release spaces via workflow updates — fully serialized, no race conditions, no external state store.

## ParkingLotWorkflow

Lives in `src/valet/parking_lot_workflow.py`.

- **Workflow ID:** `parking-lot` (singleton)
- **Task queue:** `valet` (same worker)
- **State:** `dict[str, str | None]` — space number (as string) → license plate (`None` = free). Initialized with spaces `"1"`–`"100"`. String keys avoid JSON round-trip issues (Temporal's default serializer converts int keys to strings).

### Update handlers

- `request_space(plate: str) -> str` — finds first free space, assigns it to the plate, returns the space number (as string). Raises `ApplicationError` if the lot is full.
- `release_space(plate: str)` — frees the space assigned to the given plate.

### Query handler

- `get_status() -> dict[str, str | None]` — returns the current space map. Useful for UI/debugging.

### Main loop

```python
async def run(self, input: ParkingLotInput) -> ParkingLotOutput:
    # Initialize or restore state
    self.spaces = input.spaces or {str(i): None for i in range(1, 101)}
    self._should_continue_as_new = False

    # Stay alive until continue-as-new is requested
    await workflow.wait_condition(lambda: self._should_continue_as_new)
    workflow.continue_as_new(ParkingLotInput(spaces=self.spaces))
```

### Continue-as-new

After each update handler completes, check `workflow.info().is_continue_as_new_suggested()`. If true, set `self._should_continue_as_new = True`. The main loop's `wait_condition` picks up the flag and calls `workflow.continue_as_new(self.spaces)`. This avoids calling `continue_as_new()` from an update handler, which would raise `ContinueAsNewError` and fail the update.

In-flight updates complete before continue-as-new executes, so no assignments are lost. Updates arriving during the transition retry against the new run automatically.

## ValetParkingWorkflow changes

The valet workflow calls activities that send updates to the parking lot workflow (workflows can't send updates directly to other workflows):

1. **`request_space` activity** — sends `request_space` update to `parking-lot` workflow → returns assigned space number (string)
2. **`move_car`** — from `input.valet_zone_location` (valet zone) → assigned space (`Location(kind=LocationKind.PARKING_SPACE, id=space_number)`). Note: `MoveCarInput.from_location`/`to_location` change from `str` to `Location` — the `move_car` activity must be updated accordingly. This replaces the existing hardcoded `"pickup_zone"`/`"spot_A1"` strings.
3. **`workflow.sleep(trip_duration)`** — wait for owner's trip
4. **`find_nearest_valet_zone` activity** — supposedly finds the nearest valet zone based on the terminal the owner landed at, but really just randomly picks a valet zone (1–`NUM_VALET_ZONES`). Returns a `FindNearestValetZoneOutput` containing the `Location`.
5. **`move_car`** — from assigned space → return valet zone from step 4
6. **`release_space` activity** — sends `release_space` update to `parking-lot` workflow

## Activities additions

New activities live in `src/valet/activities.py` (alongside existing `move_car`):

- `request_space(input: RequestSpaceInput) -> RequestSpaceOutput` — creates a Temporal client, gets an external workflow handle for `parking-lot`, executes the `request_space` update, returns the space number (as string).
- `release_space(input: ReleaseSpaceInput) -> ReleaseSpaceOutput` — creates a Temporal client, gets an external workflow handle for `parking-lot`, executes the `release_space` update.
- `find_nearest_valet_zone(input: FindNearestValetZoneInput) -> FindNearestValetZoneOutput` — randomly picks a valet zone (1–`NUM_VALET_ZONES`). Simulates finding the nearest zone for the returning owner.

## Data model additions

All models live in `src/valet/models.py`.

- `LocationKind` — `StrEnum` with values `PARKING_SPACE` and `VALET_ZONE`.
- `Location` — `kind: LocationKind`, `id: str`. Serializable dataclass used as `from_location`/`to_location` in `MoveCarInput`. String IDs keep things uniform with the parking lot's string keys.
- `NUM_VALET_ZONES` — hardcoded constant (e.g., `3`). Used by starters/simulator and `find_nearest_valet_zone`.
- `RequestSpaceInput` — `license_plate: str`
- `RequestSpaceOutput` — `space_number: str`
- `ReleaseSpaceInput` — `license_plate: str`
- `ReleaseSpaceOutput` — empty dataclass
- `FindNearestValetZoneInput` — empty dataclass
- `FindNearestValetZoneOutput` — `location: Location`
- `ParkingLotInput` — `spaces: dict[str, str | None] | None` (workflow input, `None` on first start). String keys for JSON round-trip safety.
- `ParkingLotOutput` — empty dataclass (workflow never completes normally, but needed for type consistency)
- `ValetParkingInput` gains a `valet_zone_location: Location` field (the valet zone where the car was dropped off)
- `MoveCarInput` — `from_location` and `to_location` change from `str` to `Location`
- `ValetParkingOutput` — already exists (empty dataclass)

## Worker changes

`src/valet/worker.py` stays in place. Register `ParkingLotWorkflow` (from `valet.parking_lot_workflow`) alongside `ValetParkingWorkflow` (from `valet.valet_workflow`), plus all activities from `valet.activities`. All on the same `valet` task queue.

## Starter/simulator changes

Both the starter and simulator ensure the parking lot workflow is running before starting valet workflows, using `WorkflowIDConflictPolicy.USE_EXISTING` for idempotency:
```python
await client.start_workflow(
    ParkingLotWorkflow.run,
    ParkingLotInput(spaces=None),
    id="parking-lot",
    task_queue="valet",
    id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
)
```
This starts the workflow if it doesn't exist, or silently returns the existing handle if it's already running. No separate check needed.

Starter and simulator randomly pick a valet zone when creating `ValetParkingInput`:
```python
valet_zone_location = Location(kind=LocationKind.VALET_ZONE, id=str(random.randint(1, NUM_VALET_ZONES)))
```

## Continue-as-new details

- Update handlers set `self._should_continue_as_new = True` when `is_continue_as_new_suggested()` returns true
- The main loop's `wait_condition(lambda: self._should_continue_as_new)` unblocks, then calls `workflow.continue_as_new(ParkingLotInput(spaces=self.spaces))`
- The space map is wrapped in `ParkingLotInput` and passed as the workflow input to the new run
- History resets while state is preserved — prevents unbounded history growth from many update events
- Good candidate for demonstrating continue-as-new in a workshop since the simulator generates a steady stream of updates

## Test changes

- Fix existing `test_valet_parking_workflow` — update `ValetParkingInput` to include `valet_zone_location`, mock/register new activities (`request_space`, `release_space`, `find_nearest_valet_zone`)
- Add `test_parking_lot_workflow` (in `tests/valet/test_parking_lot_workflow.py`) — test `request_space` update assigns a space, `release_space` update frees it, `get_status` query returns current state, and lot-full raises `ApplicationError`

## File structure (new/changed)

```
src/
  valet/
    __init__.py
    activities.py              # move_car (updated), request_space, release_space, find_nearest_valet_zone (new)
    models.py                  # existing + LocationKind, Location, ParkingLotInput/Output, new input/output types
    parking_lot_workflow.py    # new — ParkingLotWorkflow
    starter.py                 # updated
    simulator.py               # updated
    utils.py                   # unchanged
    valet_workflow.py          # renamed from workflow.py
    worker.py                  # updated — registers both workflows
tests/
  valet/
    test_workflow.py           # updated
    test_parking_lot_workflow.py  # new
```

## Verification

1. Start `ParkingLotWorkflow` — stays running, shows 100 empty spaces (numbered 1–100) via query
2. Start valet workflows — spaces get assigned and released
3. Run simulator — lot fills and empties over time
4. Temporal UI — parking-lot workflow shows update events and space state via query
5. After many updates — continue-as-new triggers, history resets, state carries over
