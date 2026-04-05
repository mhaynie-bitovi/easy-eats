import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from order.order_workflow import OrderWorkflow


async def main():
    client = await Client.connect(
        "localhost:7233",
        namespace="default"
    )

    worker = Worker(
        client,
        task_queue="order",
        workflows=[OrderWorkflow],
        activities=[]
    )

    print("Worker running...")
    await worker.run()
    
    
if __name__ == "__main__":
    asyncio.run(main())