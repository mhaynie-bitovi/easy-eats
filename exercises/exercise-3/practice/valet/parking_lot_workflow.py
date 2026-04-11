from temporalio import workflow
from temporalio.common import VersioningBehavior
from temporalio.exceptions import ApplicationError

with workflow.unsafe.imports_passed_through():
    from valet.models import ParkingLotInput, ParkingLotOutput


@workflow.defn(versioning_behavior=VersioningBehavior.AUTO_UPGRADE)
class ParkingLotWorkflow:

    def __init__(self) -> None:
        self.parking_spaces: dict[str, str | None] = {
            str(i): None for i in range(1, 31)
        }
        self._should_continue_as_new = False

    @workflow.run
    async def run(self, input: ParkingLotInput) -> ParkingLotOutput:
        self.parking_spaces = input.parking_spaces or self.parking_spaces

        await workflow.wait_condition(lambda: self._should_continue_as_new)

        workflow.continue_as_new(ParkingLotInput(parking_spaces=self.parking_spaces))

    @workflow.update
    async def request_parking_space(self, plate: str) -> str:
        for parking_space, occupant in self.parking_spaces.items():
            if occupant is None:
                self.parking_spaces[parking_space] = plate
                workflow.logger.info(f"Assigned parking space {parking_space} to {plate}")
                self._check_continue_as_new()
                return parking_space

        raise ApplicationError("Parking lot is full")

    @workflow.update
    async def release_parking_space(self, plate: str) -> None:
        for parking_space, occupant in self.parking_spaces.items():
            if occupant == plate:
                self.parking_spaces[parking_space] = None
                workflow.logger.info(f"Released parking space {parking_space} from {plate}")
                self._check_continue_as_new()
                return

        raise ApplicationError(f"No parking space found for plate {plate}")

    @workflow.query
    def get_status(self) -> dict[str, str | None]:
        return self.parking_spaces

    def _check_continue_as_new(self) -> None:
        if (
            workflow.info().is_continue_as_new_suggested()
            or workflow.info().get_current_history_length() >= 500
        ):
            self._should_continue_as_new = True
