import argparse
import asyncio
import random

from temporalio.client import Client

from valet.models import ValetParkingInput
from valet.utils import generate_license_plate
from valet.workflow import ValetParkingWorkflow


async def main() -> None:
    parser = argparse.ArgumentParser(description="Valet parking load simulator")
    parser.add_argument(
        "--quiet", action="store_true", help="Suppress per-workflow output"
    )
    args = parser.parse_args()

    client = await Client.connect("localhost:7233")

    print("Simulator running (Ctrl+C to stop) ...")

    while True:
        license_plate = generate_license_plate()
        trip_duration = random.randint(60, 300)

        handle = await client.start_workflow(
            ValetParkingWorkflow.run,
            ValetParkingInput(
                license_plate=license_plate,
                trip_duration_seconds=trip_duration,
            ),
            id=f"valet-{license_plate}",
            task_queue="valet",
        )

        if not args.quiet:
            print(f"Started workflow {handle.id} (trip: {trip_duration}s)")

        await asyncio.sleep(random.uniform(2, 10))


if __name__ == "__main__":
    asyncio.run(main())
