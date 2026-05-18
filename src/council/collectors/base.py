"""Abstract base collector interface."""

from __future__ import annotations

import abc


class BaseCollector[T](abc.ABC):
    """Abstract base class for data collectors.

    Subclasses must implement :meth:`collect` to fetch data from a specific
    source and return strongly-typed result objects.
    """

    @abc.abstractmethod
    async def collect(self, query: str, max_results: int = 20) -> list[T]:
        """Collect data matching the given query.

        Args:
            query: Search query string.
            max_results: Maximum number of results to return.

        Returns:
            List of collected data items.
        """
        ...
