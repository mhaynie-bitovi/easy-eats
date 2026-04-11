from datetime import timedelta

from temporalio import workflow

# TODO(Part A.3a): Import VersioningBehavior:
#   from temporalio.common import VersioningBehavior

with workflow.unsafe.imports_passed_through():
    from valet.activities import (
        move_car,
        notify_owner,
        release_space,
        request_space,
    )
    from valet.models import (
        Location,
        LocationKind,
        MoveCarInput,
        NotifyOwnerInput,
        ReleaseSpaceInput,
        RequestSpaceInput,
        ValetParkingInput,
        ValetParkingOutput,
    )


# TODO(Part A.3a): Add versioning_behavior=VersioningBehavior.AUTO_UPGRADE to @workflow.defn
# TODO(Part B.2): Change to versioning_behavior=VersioningBehavior.PINNED
@workflow.defn
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

        # Notify the owner their car is being parked
        if workflow.patched("add-notify-owner"):
            await workflow.execute_activity(
                notify_owner,
                NotifyOwnerInput(
                    license_plate=input.license_plate,
                    message="Your car is being parked!",
                ),
                start_to_close_timeout=timedelta(seconds=10),
            )

        # Move car from valet zone to assigned parking space
        # TODO(Part B.1): Capture the result: move_to_space_result = await ...
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
        # TODO(Part B.1): Capture the result: move_to_valet_result = await ...
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

        # TODO(Part B.1): Add bill_customer activity call here.
        #   Call workflow.execute_activity() with bill_customer and BillCustomerInput.
        #   Use move_to_space_result.distance_driven + move_to_valet_result.distance_driven
        #   for total_distance. Return ValetParkingOutput(total_bill=bill_result.amount).
        #   Don't forget to add bill_customer and BillCustomerInput to the imports above.

        return ValetParkingOutput()
