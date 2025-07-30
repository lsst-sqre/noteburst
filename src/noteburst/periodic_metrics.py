"""A script for publishing periodic app metrics."""

import asyncio

import sentry_sdk
from safir.metrics import ArqEvents, publish_queue_stats
from safir.sentry import before_send_handler

from .config import config

# If SENTRY_DSN is not in the environment, this will do nothing
sentry_sdk.init(
    traces_sample_rate=config.sentry_traces_sample_rate,
    before_send=before_send_handler,
)


def publish_periodic_metrics() -> None:
    """Publish queue statistics events.

    This should be run on a schedule.
    """

    async def publish() -> None:
        manager = config.metrics.make_manager()
        try:
            await manager.initialize()
            arq_events = ArqEvents()
            await arq_events.initialize(manager)
            await publish_queue_stats(
                queue=config.queue_name,
                arq_events=arq_events,
                redis_settings=config.arq_redis_settings,
            )
        finally:
            await manager.aclose()

    asyncio.run(publish())
