import asyncio
import random
from datetime import datetime, timezone

from temporalio import activity
from temporalio.client import Client

from valet.models import (
    FindNearestValetZoneInput,
    FindNearestValetZoneOutput,
    Location,
    LocationKind,
    MoveCarInput,
    MoveCarOutput,
    NUM_VALET_ZONES,
    ReleaseSpaceInput,
    ReleaseSpaceOutput,
    RequestSpaceInput,
    RequestSpaceOutput,
)


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
    handle = client.get_workflow_handle("parking-lot")
    space_number = await handle.execute_update(
        "request_space", arg=input.license_plate
    )
    return RequestSpaceOutput(space_number=space_number)


@activity.defn
async def release_space(input: ReleaseSpaceInput) -> ReleaseSpaceOutput:
    client = await Client.connect("localhost:7233")
    handle = client.get_workflow_handle("parking-lot")
    await handle.execute_update("release_space", arg=input.license_plate)
    return ReleaseSpaceOutput()


@activity.defn
async def find_nearest_valet_zone(
    input: FindNearestValetZoneInput,
) -> FindNearestValetZoneOutput:
    zone_id = str(random.randint(1, NUM_VALET_ZONES))
    return FindNearestValetZoneOutput(
        location=Location(kind=LocationKind.VALET_ZONE, id=zone_id)
    )
