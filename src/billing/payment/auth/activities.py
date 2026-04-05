from temporalio import activity


@activity.defn
async def authorize_payment_info(name: str) -> bool:
    return True