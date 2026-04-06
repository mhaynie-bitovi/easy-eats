import asyncio
import random
from datetime import datetime, timezone

from temporalio import activity
from temporalio.client import Client, WithStartWorkflowOperation
from temporalio.common import WorkflowIDConflictPolicy

from valet.models import (
    FindNearestValetZoneInput,
    FindNearestValetZoneOutput,
    Location,
    LocationKind,
    MoveCarInput,
    MoveCarOutput,
    NUM_VALET_ZONES,
    ParkingLotInput,
    ReleaseSpaceInput,
    ReleaseSpaceOutput,
    RequestSpaceInput,
    RequestSpaceOutput,
)
from valet.parking_lot_workflow import ParkingLotWorkflow


@activity.defn
async def move_car(input: MoveCarInput) -> MoveCarOutput:
    start_time = datetime.now(timezone.utc).isoformat()

    print(
        f"Moving car {input.license_plate} "
        f"from {input.from_location.kind}:{input.from_location.id} "
        f"to {input.to_location.kind}:{input.to_location.id}"
    )

    distance_driven = round(random.uniform(0.1, 2.0), 2)

    # Simulate driving time
    await asyncio.sleep(random.uniform(1.0, 5.0))

    end_time = datetime.now(timezone.utc).isoformat()

    return MoveCarOutput(
        distance_driven=distance_driven,
        start_time=start_time,
        end_time=end_time,
    )


@activity.defn
async def request_space(input: RequestSpaceInput) -> RequestSpaceOutput:
    client = await Client.connect("localhost:7233")
    start_op = WithStartWorkflowOperation(
        ParkingLotWorkflow.run,
        ParkingLotInput(spaces=None),
        id="parking-lot",
        task_queue="valet",
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
    )
    space_number = await client.execute_update_with_start_workflow(
        ParkingLotWorkflow.request_space,
        input.license_plate,
        start_workflow_operation=start_op,
    )
    return RequestSpaceOutput(space_number=space_number)


@activity.defn
async def release_space(input: ReleaseSpaceInput) -> ReleaseSpaceOutput:
    client = await Client.connect("localhost:7233")
    start_op = WithStartWorkflowOperation(
        ParkingLotWorkflow.run,
        ParkingLotInput(spaces=None),
        id="parking-lot",
        task_queue="valet",
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
    )
    await client.execute_update_with_start_workflow(
        ParkingLotWorkflow.release_space,
        input.license_plate,
        start_workflow_operation=start_op,
    )
    return ReleaseSpaceOutput()


@activity.defn
async def find_nearest_valet_zone(
    input: FindNearestValetZoneInput,
) -> FindNearestValetZoneOutput:
    zone_id = str(random.randint(1, NUM_VALET_ZONES))
    return FindNearestValetZoneOutput(
        location=Location(kind=LocationKind.VALET_ZONE, id=zone_id)
    )
