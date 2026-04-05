import asyncio

from temporalio.client import Client

from valet.models import ValetParkingInput
from valet.utils import generate_license_plate
from valet.workflow import ValetParkingWorkflow


async def main() -> None:
    license_plate = generate_license_plate()
    print(f"Starting valet parking workflow for {license_plate}")

    client = await Client.connect("localhost:7233")
    result = await client.execute_workflow(
        ValetParkingWorkflow.run,
        ValetParkingInput(
            license_plate=license_plate,
            trip_duration_seconds=10,
        ),
        id=f"valet-{license_plate}",
        task_queue="valet",
    )

    print(f"Result: {result}")


if __name__ == "__main__":
    asyncio.run(main())
