import pytest
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from valet.valet_parking_workflow import ValetParkingWorkflow


@pytest.mark.asyncio
async def test_replay_valet_v1():
    # Load a captured workflow history from disk.
    # This JSON was exported from a completed V1 workflow using:
    #   temporal workflow show --workflow-id <id> --output json > history/valet_v1_history.json
    with open("history/valet_v1_history.json", "r") as f:
        history_json = f.read()

    # The Replayer re-executes the workflow code against the recorded history.
    # If the code produces a different sequence of commands than what the
    # history contains, it raises a non-determinism error (NDE).
    replayer = Replayer(workflows=[ValetParkingWorkflow])
    await replayer.replay_workflow(
        WorkflowHistory.from_json("valet_v1_history", history_json)
    )
