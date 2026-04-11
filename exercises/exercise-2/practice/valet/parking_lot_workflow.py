from temporalio import workflow
from temporalio.exceptions import ApplicationError

# TODO(Part A.3a): Import VersioningBehavior:
#   from temporalio.common import VersioningBehavior

with workflow.unsafe.imports_passed_through():
    from valet.models import ParkingLotInput, ParkingLotOutput


# TODO(Part A.3a): Add versioning_behavior=VersioningBehavior.AUTO_UPGRADE to @workflow.defn
@workflow.defn
class ParkingLotWorkflow:

    def __init__(self) -> None:
        self.spaces: dict[str, str | None] = {
            str(i): None for i in range(1, 31)
        }
        self._should_continue_as_new = False

    @workflow.run
    async def run(self, input: ParkingLotInput) -> ParkingLotOutput:
        self.spaces = input.spaces or self.spaces

        await workflow.wait_condition(lambda: self._should_continue_as_new)
        workflow.continue_as_new(ParkingLotInput(spaces=self.spaces))

    @workflow.update
    async def request_space(self, plate: str) -> str:
        for space, occupant in self.spaces.items():
            if occupant is None:
                self.spaces[space] = plate
                workflow.logger.info(f"Assigned space {space} to {plate}")
                self._check_continue_as_new()
                return space

        raise ApplicationError("Parking lot is full")

    @workflow.update
    async def release_space(self, plate: str) -> None:
        for space, occupant in self.spaces.items():
            if occupant == plate:
                self.spaces[space] = None
                workflow.logger.info(f"Released space {space} from {plate}")
                self._check_continue_as_new()
                return

        raise ApplicationError(f"No space found for plate {plate}")

    @workflow.query
    def get_status(self) -> dict[str, str | None]:
        return self.spaces

    def _check_continue_as_new(self) -> None:
        if (
            workflow.info().is_continue_as_new_suggested()
            or workflow.info().get_current_history_length() >= 500
        ):
            self._should_continue_as_new = True
