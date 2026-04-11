import asyncio
import logging
import os

from temporalio.client import Client
from temporalio.worker import Worker
from temporalio.worker.workflow_sandbox import SandboxedWorkflowRunner, SandboxRestrictions

# TODO(Part A): Import WorkerDeploymentVersion and WorkerDeploymentConfig:
# from temporalio.common import WorkerDeploymentVersion
# from temporalio.worker import WorkerDeploymentConfig

from valet.activities import (
    bill_customer,
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

    # TODO(Part A): Create a WorkerDeploymentConfig from the env vars and pass it
    #   to the Worker below.

    worker = Worker(
        client,
        task_queue="valet",
        workflows=[ValetParkingWorkflow, ParkingLotWorkflow],
        activities=[move_car, request_parking_space, release_parking_space, notify_owner, bill_customer],
        # TODO(Part A): Add deployment_config=deployment_config here.
        workflow_runner=SandboxedWorkflowRunner(
            # Prevent the sandbox from re-reading workflow code from disk on each run.
            # Without this, a running worker would pick up file edits without a restart.
            restrictions=SandboxRestrictions.default.with_passthrough_modules("valet")
        ),
    )

    print("Worker running ...")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
