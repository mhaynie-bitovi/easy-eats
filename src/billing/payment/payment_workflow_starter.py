import asyncio
import uuid

from temporalio.client import Client

from billing.payment.payment_workflow import PaymentWorkflow


async def main () -> None:
    print("Starting payment workflow")

    client = await Client.connect("localhost:7233")
    result = await client.execute_workflow(
        PaymentWorkflow.run,
        id=f"payment-{str(uuid.uuid4())}",
        task_queue='billing'
    )

    print(f"Result: {result}")

if __name__ == "__main__":
    asyncio.run(main())