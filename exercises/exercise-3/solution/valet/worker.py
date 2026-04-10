import asyncio
import logging
import os

from temporalio.client import Client
from temporalio.common import WorkerDeploymentVersion
from temporalio.worker import Worker, WorkerDeploymentConfig

from valet.activities import (
    bill_customer,
    move_car,
    notify_owner,
    release_space,
    request_space,
)
from valet.parking_lot_workflow import ParkingLotWorkflow
from valet.valet_workflow import ValetParkingWorkflow


async def main():
    logging.basicConfig(level=logging.INFO)

    temporal_address = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
    temporal_namespace = os.environ.get("TEMPORAL_NAMESPACE", "default")
    deployment_name = os.environ.get("TEMPORAL_DEPLOYMENT_NAME")
    build_id = os.environ.get("TEMPORAL_WORKER_BUILD_ID")

    client = await Client.connect(temporal_address, namespace=temporal_namespace)

    deployment_config = None
    if deployment_name and build_id:
        deployment_config = WorkerDeploymentConfig(
            version=WorkerDeploymentVersion(
                deployment_name=deployment_name,
                build_id=build_id,
            ),
            use_worker_versioning=True,
        )
        print(
            f"Worker versioning enabled: deployment={deployment_name}, build_id={build_id}"
        )

    worker = Worker(
        client,
        task_queue="valet",
        workflows=[ValetParkingWorkflow, ParkingLotWorkflow],
        activities=[move_car, request_space, release_space, notify_owner, bill_customer],
        deployment_config=deployment_config,
    )

    print("Worker running ...")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
