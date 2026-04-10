import uuid

import pytest
from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from valet.models import (
    Location,
    LocationKind,
    MoveCarInput,
    MoveCarOutput,
    ReleaseSpaceInput,
    ReleaseSpaceOutput,
    RequestSpaceInput,
    RequestSpaceOutput,
    ValetParkingInput,
    ValetParkingOutput,
)
from valet.valet_workflow import ValetParkingWorkflow


@activity.defn(name="move_car")
async def mock_move_car(input: MoveCarInput) -> MoveCarOutput:
    return MoveCarOutput(distance_driven=1.0, start_time="t0", end_time="t1")


@activity.defn(name="request_space")
async def mock_request_space(input: RequestSpaceInput) -> RequestSpaceOutput:
    return RequestSpaceOutput(space_number="42")


@activity.defn(name="release_space")
async def mock_release_space(input: ReleaseSpaceInput) -> ReleaseSpaceOutput:
    return ReleaseSpaceOutput()


@pytest.mark.asyncio
async def test_valet_parking_workflow():
    task_queue_name = str(uuid.uuid4())

    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=task_queue_name,
            workflows=[ValetParkingWorkflow],
            activities=[
                mock_move_car,
                mock_request_space,
                mock_release_space,
            ],
        ):
            result = await env.client.execute_workflow(
                ValetParkingWorkflow.run,
                ValetParkingInput(
                    license_plate="TEST-1ABC234",
                    trip_duration_seconds=120,
                    valet_zone_location=Location(
                        kind=LocationKind.VALET_ZONE, id="1"
                    ),
                ),
                id=str(uuid.uuid4()),
                task_queue=task_queue_name,
            )

            assert result == ValetParkingOutput()
