from datetime import timedelta

from temporalio import workflow
from temporalio.common import VersioningBehavior

with workflow.unsafe.imports_passed_through():
    from valet.activities import (
        move_car,
        release_space,
        request_space,
    )
    from valet.models import (
        Location,
        LocationKind,
        MoveCarInput,
        ReleaseSpaceInput,
        RequestSpaceInput,
        ValetParkingInput,
        ValetParkingOutput,
    )


@workflow.defn(versioning_behavior=VersioningBehavior.AUTO_UPGRADE)
class ValetParkingWorkflow:

    @workflow.run
    async def run(self, input: ValetParkingInput) -> ValetParkingOutput:
        workflow.logger.info(
            f"Starting valet parking for {input.license_plate}"
        )

        # Request a parking space
        space_result = await workflow.execute_activity(
            request_space,
            RequestSpaceInput(license_plate=input.license_plate),
            start_to_close_timeout=timedelta(seconds=10),
        )

        assigned_space = Location(
            kind=LocationKind.PARKING_SPACE, id=space_result.space_number
        )

        # Move car from valet zone to assigned parking space
        await workflow.execute_activity(
            move_car,
            MoveCarInput(
                license_plate=input.license_plate,
                from_location=input.valet_zone_location,
                to_location=assigned_space,
            ),
            start_to_close_timeout=timedelta(seconds=10),
        )

        workflow.logger.info(
            f"Car {input.license_plate} parked in space {space_result.space_number}. "
            f"Waiting {input.trip_duration_seconds}s for owner's trip."
        )

        # Wait for the owner's trip
        await workflow.sleep(input.trip_duration_seconds)

        # Move car from parking space back to the original valet zone
        await workflow.execute_activity(
            move_car,
            MoveCarInput(
                license_plate=input.license_plate,
                from_location=assigned_space,
                to_location=input.valet_zone_location,
            ),
            start_to_close_timeout=timedelta(seconds=10),
        )

        # Release the parking space
        await workflow.execute_activity(
            release_space,
            ReleaseSpaceInput(license_plate=input.license_plate),
            start_to_close_timeout=timedelta(seconds=10),
        )

        workflow.logger.info(
            f"Car {input.license_plate} returned to valet zone {input.valet_zone_location.id}."
        )

        return ValetParkingOutput()
