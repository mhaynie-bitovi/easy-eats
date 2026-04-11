import asyncio
import random

from temporalio.client import Client

from valet.models import (
    Location,
    LocationKind,
    NUM_VALET_ZONES,
    ValetParkingInput,
)
from valet.utils import generate_license_plate
from valet.valet_parking_workflow import ValetParkingWorkflow


async def main() -> None:
    license_plate = generate_license_plate()
    print(f"Starting valet parking workflow for {license_plate}")

    client = await Client.connect("localhost:7233")

    valet_zone_location = Location(
        kind=LocationKind.VALET_ZONE,
        id=str(random.randint(1, NUM_VALET_ZONES)),
    )

    workflow_id = f"valet-{license_plate}"
    await client.start_workflow(
        ValetParkingWorkflow.run,
        ValetParkingInput(
            license_plate=license_plate,
            trip_duration_seconds=30,
            valet_zone_location=valet_zone_location,
        ),
        id=workflow_id,
        task_queue="valet",
    )

    print(f"Workflow started: {workflow_id}")


if __name__ == "__main__":
    asyncio.run(main())
