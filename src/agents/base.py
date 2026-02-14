"""Base agent class."""

from abc import ABC, abstractmethod
from loguru import logger


class BaseAgent(ABC):
    """Base class for all agents."""
    
    def __init__(self, name: str):
        self.name = name
        self.logger = logger.bind(agent=name)
    
    @abstractmethod
    async def run(self):
        """Main agent execution logic."""
        pass
    
    @abstractmethod
    async def stop(self):
        """Cleanup on shutdown."""
        pass
