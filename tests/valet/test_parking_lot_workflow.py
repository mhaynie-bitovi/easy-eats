import uuid

import pytest
from temporalio.client import WorkflowUpdateFailedError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from valet.models import ParkingLotInput
from valet.parking_lot_workflow import ParkingLotWorkflow


@pytest.mark.asyncio
async def test_request_space_assigns_space():
    task_queue_name = str(uuid.uuid4())

    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=task_queue_name,
            workflows=[ParkingLotWorkflow],
        ):
            handle = await env.client.start_workflow(
                ParkingLotWorkflow.run,
                ParkingLotInput(spaces=None),
                id=str(uuid.uuid4()),
                task_queue=task_queue_name,
            )

            space = await handle.execute_update(
                ParkingLotWorkflow.request_space, arg="TEST-ABC123"
            )
            assert space == "1"

            space2 = await handle.execute_update(
                ParkingLotWorkflow.request_space, arg="TEST-DEF456"
            )
            assert space2 == "2"


@pytest.mark.asyncio
async def test_release_space_frees_space():
    task_queue_name = str(uuid.uuid4())

    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=task_queue_name,
            workflows=[ParkingLotWorkflow],
        ):
            handle = await env.client.start_workflow(
                ParkingLotWorkflow.run,
                ParkingLotInput(spaces=None),
                id=str(uuid.uuid4()),
                task_queue=task_queue_name,
            )

            await handle.execute_update(
                ParkingLotWorkflow.request_space, arg="TEST-ABC123"
            )

            await handle.execute_update(
                ParkingLotWorkflow.release_space, arg="TEST-ABC123"
            )

            status = await handle.query(ParkingLotWorkflow.get_status)
            assert status["1"] is None


@pytest.mark.asyncio
async def test_get_status_returns_space_map():
    task_queue_name = str(uuid.uuid4())

    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=task_queue_name,
            workflows=[ParkingLotWorkflow],
        ):
            handle = await env.client.start_workflow(
                ParkingLotWorkflow.run,
                ParkingLotInput(spaces=None),
                id=str(uuid.uuid4()),
                task_queue=task_queue_name,
            )

            status = await handle.query(ParkingLotWorkflow.get_status)
            assert len(status) == 100
            assert all(v is None for v in status.values())

            await handle.execute_update(
                ParkingLotWorkflow.request_space, arg="TEST-ABC123"
            )

            status = await handle.query(ParkingLotWorkflow.get_status)
            assert status["1"] == "TEST-ABC123"


@pytest.mark.asyncio
async def test_lot_full_raises_error():
    task_queue_name = str(uuid.uuid4())

    # Start with only 2 spaces to make it easy to fill
    spaces = {"1": "CAR-A", "2": "CAR-B"}

    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=task_queue_name,
            workflows=[ParkingLotWorkflow],
        ):
            handle = await env.client.start_workflow(
                ParkingLotWorkflow.run,
                ParkingLotInput(spaces=spaces),
                id=str(uuid.uuid4()),
                task_queue=task_queue_name,
            )

            with pytest.raises(WorkflowUpdateFailedError):
                await handle.execute_update(
                    ParkingLotWorkflow.request_space, arg="CAR-C"
                )
