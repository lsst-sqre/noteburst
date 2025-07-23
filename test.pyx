import asyncio
import functools
from collections.abc import Callable, Coroutine

from arq import create_pool
from arq.connections import RedisSettings
from httpx import AsyncClient

# Here you can configure the Redis connection.
# The default is to connect to localhost:6379, no password.
REDIS_SETTINGS = RedisSettings()


def bwith_arq_metrics[**P, R](
    func: Callable[P, Coroutine[None, None, R]],
) -> Callable[P, Coroutine[None, None, R]]:
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        queue_name = kwargs.pop("_app_metrics_queue_name")
        function_name = kwargs.pop("_app_metrics_function_name")
        # ctx is always passed as the first positional argument
        breakpoint()
        func.arq_metrics_enabled = True
        return await func(*args, **kwargs)

    functools.update_wrapper(
        wrapper=wrapper,
        wrapped=func,
    )

    return wrapper


@bwith_arq_metrics
async def download_content(ctx, url):
    jobs = await ctx["redis"].queued_jobs()
    session: AsyncClient = ctx["session"]
    response = await session.get(url)
    print(f"{url}: {response.text:.80}...")
    return len(response.text)


async def startup(ctx):
    ctx["session"] = AsyncClient()


async def shutdown(ctx):
    await ctx["session"].aclose()


async def main():
    redis = await create_pool(REDIS_SETTINGS)
    for url in (
        "https://facebook.com",
        "https://microsoft.com",
        "https://github.com",
    ):
        await redis.enqueue_job(
            "download_content",
            url,
            _app_metrics_queue_name=redis.default_queue_name,
            _app_metrics_function_name="download_content",
        )


# WorkerSettings defines the settings to use when creating the work,
# It's used by the arq CLI.
# redis_settings might be omitted here if using the default settings
# For a list of all available settings, see https://arq-docs.helpmanual.io/#arq.worker.Worker
class WorkerSettings:
    functions = [download_content]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = REDIS_SETTINGS


if __name__ == "__main__":
    asyncio.run(main())
