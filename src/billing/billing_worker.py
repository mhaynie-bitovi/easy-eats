import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from billing.payment.auth.activities import authorize_payment_info
from billing.payment.capture.activities import capture_payment
from billing.payment.payment_workflow import PaymentWorkflow


async def main():
    client = await Client.connect("localhost:7233")
    worker  = Worker(
        client,
        task_queue="billing",
        workflows=[
            PaymentWorkflow
        ],
        activities=[
            authorize_payment_info,
            capture_payment
        ],
    )

    print("Worker running ...")
    await worker.run()

    

if __name__ == "__main__":
    asyncio.run(main())