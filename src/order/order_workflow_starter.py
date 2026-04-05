import asyncio

from temporalio.client import Client

from order.order_workflow import OrderWorkflow


async def main():
    client = await Client.connect("localhost:7233")

    result = await client.execute_workflow(
        OrderWorkflow.run,
        id='order-1',
        task_queue='order'
    )

    print(f"Result: {result}")

if __name__ == "__main__":
    asyncio.run(main())