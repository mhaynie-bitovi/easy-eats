from temporalio import workflow


# todo: use @dataclasses for input/output
@workflow.defn
class OrderWorkflow:

    @workflow.run
    async def run(self):
        workflow.logger.info("Executing OrderWorkflow")

        # 


"""
- billing 
    - user gets billed every month for subscription
    - user gets billed for single purchase
"""
