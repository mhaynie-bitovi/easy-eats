from temporalio import activity


@activity.defn
async def capture_payment() -> bool:
    return True