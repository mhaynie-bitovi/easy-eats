import asyncio
import os
import random
from datetime import datetime, timezone

from temporalio import activity
from temporalio.client import Client, WithStartWorkflowOperation
from temporalio.common import WorkflowIDConflictPolicy

from valet.models import (
    MoveCarInput,
    MoveCarOutput,
    NotifyOwnerInput,
    NotifyOwnerOutput,
    ParkingLotInput,
    ReleaseParkingSpaceInput,
    ReleaseParkingSpaceOutput,
    RequestParkingSpaceInput,
    RequestParkingSpaceOutput,
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
async def request_parking_space(input: RequestParkingSpaceInput) -> RequestParkingSpaceOutput:
    temporal_address = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
    temporal_namespace = os.environ.get("TEMPORAL_NAMESPACE", "default")
    client = await Client.connect(temporal_address, namespace=temporal_namespace)
    start_op = WithStartWorkflowOperation(
        ParkingLotWorkflow.run,
        ParkingLotInput(parking_spaces=None),
        id="parking-lot",
        task_queue="valet",
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
    )
    parking_space_number = await client.execute_update_with_start_workflow(
        ParkingLotWorkflow.request_parking_space,
        input.license_plate,
        start_workflow_operation=start_op,
    )
    return RequestParkingSpaceOutput(parking_space_number=parking_space_number)


@activity.defn
async def release_parking_space(input: ReleaseParkingSpaceInput) -> ReleaseParkingSpaceOutput:
    temporal_address = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
    temporal_namespace = os.environ.get("TEMPORAL_NAMESPACE", "default")
    client = await Client.connect(temporal_address, namespace=temporal_namespace)
    start_op = WithStartWorkflowOperation(
        ParkingLotWorkflow.run,
        ParkingLotInput(parking_spaces=None),
        id="parking-lot",
        task_queue="valet",
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
    )
    await client.execute_update_with_start_workflow(
        ParkingLotWorkflow.release_parking_space,
        input.license_plate,
        start_workflow_operation=start_op,
    )
    return ReleaseParkingSpaceOutput()


@activity.defn
async def notify_owner(input: NotifyOwnerInput) -> NotifyOwnerOutput:
    activity.logger.info(
        f"Notifying owner of {input.license_plate}: {input.message}"
    )
    return NotifyOwnerOutput(notified=True)
