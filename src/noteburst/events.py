"""App metrics events."""

from typing import override

from safir.dependencies.metrics import EventDependency, EventMaker
from safir.metrics import EventManager, EventPayload

__all__ = [
    "EnqueueNotebookExecutionFailure",
    "EnqueueNotebookExecutionSuccess",
    "Events",
    "events_dependency",
]


class EnqueueNotebookExecutionSuccess(EventPayload):
    """An nbexec task was successfully enqueued."""

    username: str


class EnqueueNotebookExecutionFailure(EventPayload):
    """An nbexec task failed to be enqueued."""

    username: str


class Events(EventMaker):
    """A container for app metrics event publishers."""

    @override
    async def initialize(self, manager: EventManager) -> None:
        """Create event publishers."""
        self.enqueue_nbexec_success = await manager.create_publisher(
            "enqueue_nbexec_success", EnqueueNotebookExecutionSuccess
        )
        self.enqueue_nbexec_failure = await manager.create_publisher(
            "enqueue_nbexec_failure", EnqueueNotebookExecutionFailure
        )


events_dependency = EventDependency(Events())
"""Provides an container that holds event publishers."""
