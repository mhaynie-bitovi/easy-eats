import argparse
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
    parser = argparse.ArgumentParser(description="Valet parking load simulator")
    parser.add_argument(
        "--quiet", action="store_true", help="Suppress per-workflow output"
    )
    args = parser.parse_args()

    client = await Client.connect("localhost:7233")

    print("Simulator running (Ctrl+C to stop) ...")

    while True:
        license_plate = generate_license_plate()
        trip_duration = random.randint(5, 30)

        valet_zone_location = Location(
            kind=LocationKind.VALET_ZONE,
            id=str(random.randint(1, NUM_VALET_ZONES)),
        )

        handle = await client.start_workflow(
            ValetParkingWorkflow.run,
            ValetParkingInput(
                license_plate=license_plate,
                trip_duration_seconds=trip_duration,
                valet_zone_location=valet_zone_location,
            ),
            id=f"valet-{license_plate}",
            task_queue="valet",
        )

        if not args.quiet:
            print(f"Started workflow {handle.id} (trip: {trip_duration}s)")

        await asyncio.sleep(random.uniform(1, 5))


if __name__ == "__main__":
    asyncio.run(main())
