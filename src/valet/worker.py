import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from valet.activities import (
    find_nearest_valet_zone,
    move_car,
    release_space,
    request_space,
)
from valet.parking_lot_workflow import ParkingLotWorkflow
from valet.valet_workflow import ValetParkingWorkflow


async def main():
    client = await Client.connect("localhost:7233")
    worker = Worker(
        client,
        task_queue="valet",
        workflows=[ValetParkingWorkflow, ParkingLotWorkflow],
        activities=[move_car, request_space, release_space, find_nearest_valet_zone],
    )

    print("Worker running ...")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
