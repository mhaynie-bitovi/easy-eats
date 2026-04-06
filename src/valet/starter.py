import asyncio
import random

from temporalio.client import Client
from temporalio.common import WorkflowIDConflictPolicy

from valet.models import (
    Location,
    LocationKind,
    NUM_VALET_ZONES,
    ParkingLotInput,
    ValetParkingInput,
)
from valet.parking_lot_workflow import ParkingLotWorkflow
from valet.utils import generate_license_plate
from valet.valet_workflow import ValetParkingWorkflow


async def main() -> None:
    license_plate = generate_license_plate()
    print(f"Starting valet parking workflow for {license_plate}")

    client = await Client.connect("localhost:7233")

    # Ensure parking lot workflow is running
    await client.start_workflow(
        ParkingLotWorkflow.run,
        ParkingLotInput(spaces=None),
        id="parking-lot",
        task_queue="valet",
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
    )

    valet_zone_location = Location(
        kind=LocationKind.VALET_ZONE,
        id=str(random.randint(1, NUM_VALET_ZONES)),
    )

    result = await client.execute_workflow(
        ValetParkingWorkflow.run,
        ValetParkingInput(
            license_plate=license_plate,
            trip_duration_seconds=10,
            valet_zone_location=valet_zone_location,
        ),
        id=f"valet-{license_plate}",
        task_queue="valet",
    )

    print(f"Result: {result}")


if __name__ == "__main__":
    asyncio.run(main())
