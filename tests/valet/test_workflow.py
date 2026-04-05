import uuid

import pytest
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from valet.activities import move_car
from valet.models import ValetParkingInput, ValetParkingOutput
from valet.workflow import ValetParkingWorkflow


@pytest.mark.asyncio
async def test_valet_parking_workflow():
    task_queue_name = str(uuid.uuid4())

    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=task_queue_name,
            workflows=[ValetParkingWorkflow],
            activities=[move_car],
        ):
            result = await env.client.execute_workflow(
                ValetParkingWorkflow.run,
                ValetParkingInput(
                    license_plate="TEST-1ABC234",
                    trip_duration_seconds=120,
                ),
                id=str(uuid.uuid4()),
                task_queue=task_queue_name,
            )

            assert result == ValetParkingOutput()
