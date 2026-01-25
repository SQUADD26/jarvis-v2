from abc import ABC, abstractmethod
from typing import Any
from jarvis.core.state import JarvisState, AgentResult
from jarvis.core.freshness import freshness
from jarvis.utils.logging import get_logger


class BaseAgent(ABC):
    """Base class for all Jarvis sub-agents."""

    name: str = "base"
    resource_type: str = "generic"

    def __init__(self):
        self.logger = get_logger(f"agent.{self.name}")

    async def execute(self, state: JarvisState) -> AgentResult:
        """Execute agent with freshness check."""
        user_id = state["user_id"]

        try:
            # Skip caching entirely if resource_type is None
            if self.resource_type is None:
                data = await self._execute(state)
                return AgentResult(
                    agent_name=self.name,
                    success=True,
                    data=data,
                    error=None
                )

            # Check if we need fresh data
            needs_refresh = state.get("needs_refresh", {}).get(self.resource_type, True)

            if not needs_refresh:
                # Try to get cached data
                cached = await freshness.get_cached(self.resource_type, user_id)
                if cached:
                    self.logger.debug(f"Using cached data for {self.resource_type}")
                    return AgentResult(
                        agent_name=self.name,
                        success=True,
                        data=cached,
                        error=None
                    )

            # Execute the actual agent logic
            data = await self._execute(state)

            # Cache the result
            await freshness.set_cache(self.resource_type, user_id, data)

            return AgentResult(
                agent_name=self.name,
                success=True,
                data=data,
                error=None
            )

        except Exception as e:
            self.logger.error(f"Agent execution failed: {e}")
            return AgentResult(
                agent_name=self.name,
                success=False,
                data=None,
                error=str(e)
            )

    @abstractmethod
    async def _execute(self, state: JarvisState) -> Any:
        """Implement actual agent logic."""
        pass

    async def refresh_cache(self, user_id: str) -> None:
        """Force refresh cache for this agent's resource."""
        await freshness.invalidate(self.resource_type, user_id)
