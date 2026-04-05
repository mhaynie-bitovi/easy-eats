import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from valet.activities import move_car
from valet.workflow import ValetParkingWorkflow


async def main():
    client = await Client.connect("localhost:7233")
    worker = Worker(
        client,
        task_queue="valet",
        workflows=[ValetParkingWorkflow],
        activities=[move_car],
    )

    print("Worker running ...")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
