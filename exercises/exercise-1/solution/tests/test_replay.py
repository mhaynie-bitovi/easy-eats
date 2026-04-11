import pytest

from temporalio.worker import Replayer, WorkflowHistory

from valet.valet_parking_workflow import ValetParkingWorkflow


@pytest.mark.asyncio
async def test_replay_valet_v1():
    """Replay a captured V1 workflow history to verify determinism.

    This test loads a previously captured workflow execution history
    and replays it against the current workflow code. If the workflow
    code has changed in a non-deterministic way, this test will fail.
    """
    with open("history/valet_v1_history.json", "r") as f:
        history_json = f.read()

    replayer = Replayer(workflows=[ValetParkingWorkflow])
    await replayer.replay_workflow(
        WorkflowHistory.from_json("valet_v1_history", history_json)
    )
