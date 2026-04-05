from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from billing.payment.auth.activities import authorize_payment_info
    from billing.payment.capture.activities import capture_payment

@workflow.defn
class PaymentWorkflow:

    @workflow.run
    async def run(self) -> str:
        print("Executing payment workflow")

        authResult = await workflow.execute_activity(
            authorize_payment_info,
            "some name",
            task_queue="billing",
            start_to_close_timeout=timedelta(seconds=5)
        )

        captureResult = await workflow.execute_activity(
            capture_payment,
            task_queue="billing",
            start_to_close_timeout=timedelta(seconds=5)
        )

        
        return ""
