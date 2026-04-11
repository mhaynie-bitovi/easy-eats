import asyncio
import logging
import os

from temporalio.client import Client
from temporalio.worker import Worker

from valet.activities import (
    move_car,
    notify_owner,
    release_parking_space,
    request_parking_space,
)
from valet.parking_lot_workflow import ParkingLotWorkflow
from valet.valet_parking_workflow import ValetParkingWorkflow


async def main():
    logging.basicConfig(level=logging.INFO)

    temporal_address = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
    temporal_namespace = os.environ.get("TEMPORAL_NAMESPACE", "default")

    client = await Client.connect(temporal_address, namespace=temporal_namespace)

    worker = Worker(
        client,
        task_queue="valet",
        workflows=[ValetParkingWorkflow, ParkingLotWorkflow],
        # TODO(Part C.2): Add notify_owner to this activities list.
        activities=[move_car, request_parking_space, release_parking_space, notify_owner],
    )

    print("Worker running ...")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
