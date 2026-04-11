from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from valet.activities import (
        move_car,
        release_parking_space,
        request_parking_space,
        notify_owner
    )
    from valet.models import (
        Location,
        LocationKind,
        MoveCarInput,
        ReleaseParkingSpaceInput,
        RequestParkingSpaceInput,
        ValetParkingInput,
        ValetParkingOutput,
        NotifyOwnerInput
    )


@workflow.defn
class ValetParkingWorkflow:

    @workflow.run
    async def run(self, input: ValetParkingInput) -> ValetParkingOutput:
        workflow.logger.info(
            f"Starting valet parking for {input.license_plate}"
        )

        # Request a parking space
        parking_space_result = await workflow.execute_activity(
            request_parking_space,
            RequestParkingSpaceInput(license_plate=input.license_plate),
            start_to_close_timeout=timedelta(seconds=10),
        )

        assigned_parking_space = Location(
            kind=LocationKind.PARKING_SPACE, id=parking_space_result.parking_space_number
        )

        # TODO(Part C.1): Wrap the notify_owner call with:
        #   if workflow.patched("add-notify-owner"):

        # TODO(Part B.1): Add notify_owner activity call here.
        #   Call workflow.execute_activity() with notify_owner and NotifyOwnerInput.
        #   Don't forget to add notify_owner and NotifyOwnerInput to the imports above.
        # Notify the owner their car has been parked
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
        await workflow.execute_activity(
            move_car,
            MoveCarInput(
                license_plate=input.license_plate,
                from_location=input.valet_zone_location,
                to_location=assigned_parking_space,
            ),
            start_to_close_timeout=timedelta(seconds=10),
        )

        workflow.logger.info(
            f"Car {input.license_plate} parked in parking space {parking_space_result.parking_space_number}."
        )

        # In production, this wait would be replaced by a Signal from the car owner
        # indicating they're ready for their car to be retrieved.
        # Here we simulate the owner's trip with a hardcoded timer.
        await workflow.sleep(input.trip_duration_seconds)

        # Move car from parking space back to the original valet zone
        await workflow.execute_activity(
            move_car,
            MoveCarInput(
                license_plate=input.license_plate,
                from_location=assigned_parking_space,
                to_location=input.valet_zone_location,
            ),
            start_to_close_timeout=timedelta(seconds=10),
        )

        # Release the parking space
        await workflow.execute_activity(
            release_parking_space,
            ReleaseParkingSpaceInput(license_plate=input.license_plate),
            start_to_close_timeout=timedelta(seconds=10),
        )

        workflow.logger.info(
            f"Car {input.license_plate} returned to valet zone {input.valet_zone_location.id}."
        )

        return ValetParkingOutput()
