import asyncio
import random
from datetime import datetime, timezone

from temporalio import activity

from valet.models import MoveCarInput, MoveCarOutput


@activity.defn
async def move_car(input: MoveCarInput) -> MoveCarOutput:
    start_time = datetime.now(timezone.utc).isoformat()

    print(
        f"Moving car {input.license_plate} "
        f"from {input.from_location} to {input.to_location}"
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
