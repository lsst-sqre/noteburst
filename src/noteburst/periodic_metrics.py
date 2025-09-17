"""A script for publishing periodic app metrics."""

import asyncio

from safir.metrics.arq import ArqEvents, publish_queue_stats
from safir.sentry import initialize_sentry

import noteburst

from .config.metrics import config

initialize_sentry(release=noteburst.__version__)


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
            for queue in config.queue_names:
                await publish_queue_stats(
                    queue=queue,
                    arq_events=arq_events,
                    redis_settings=config.arq_redis_settings,
                )
        finally:
            await manager.aclose()

    asyncio.run(publish())
