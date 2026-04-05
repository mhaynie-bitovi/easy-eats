from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from valet.activities import move_car
    from valet.models import MoveCarInput, ValetParkingInput, ValetParkingOutput


@workflow.defn
class ValetParkingWorkflow:

    @workflow.run
    async def run(self, input: ValetParkingInput) -> ValetParkingOutput:
        workflow.logger.info(
            f"Starting valet parking for {input.license_plate}"
        )

        # Move car from pickup zone to parking spot
        await workflow.execute_activity(
            move_car,
            MoveCarInput(
                license_plate=input.license_plate,
                from_location="pickup_zone",
                to_location="spot_A1",
            ),
            start_to_close_timeout=timedelta(seconds=10),
        )

        workflow.logger.info(
            f"Car {input.license_plate} parked. "
            f"Waiting {input.trip_duration_seconds}s for owner's trip."
        )

        # Wait for the owner's trip
        await workflow.sleep(input.trip_duration_seconds)

        # Move car from parking spot back to pickup zone
        await workflow.execute_activity(
            move_car,
            MoveCarInput(
                license_plate=input.license_plate,
                from_location="spot_A1",
                to_location="pickup_zone",
            ),
            start_to_close_timeout=timedelta(seconds=10),
        )

        workflow.logger.info(f"Car {input.license_plate} returned to pickup zone.")

        return ValetParkingOutput()
