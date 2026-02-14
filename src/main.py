"""
AI Agents System
================
Main entry point for the AI agents system.
"""

import os
import time
import signal
import sys
from datetime import datetime
from loguru import logger
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    level=os.getenv("LOG_LEVEL", "INFO")
)
logger.add(
    "/app/logs/agents_{time:YYYY-MM-DD}.log",
    rotation="00:00",
    retention="30 days",
    level="DEBUG"
)


class AgentSystem:
    """Main agent system orchestrator."""
    
    def __init__(self):
        self.running = True
        self.agents = []
        
        # Handle graceful shutdown
        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)
    
    def _shutdown(self, signum, frame):
        """Graceful shutdown handler."""
        logger.info("Shutdown signal received, stopping agents...")
        self.running = False
    
    def register_agent(self, agent):
        """Register a new agent."""
        self.agents.append(agent)
        logger.info(f"Registered agent: {agent.__class__.__name__}")
    
    def run(self):
        """Main loop."""
        logger.info("=" * 50)
        logger.info("AI Agents System Started")
        logger.info(f"Environment: {os.getenv("ENVIRONMENT", "development")}")
        logger.info(f"Registered agents: {len(self.agents)}")
        logger.info("=" * 50)
        
        while self.running:
            try:
                # TODO: Add your agent logic here
                # Example: run scheduled tasks, process queues, etc.
                
                logger.debug(f"Heartbeat: {datetime.now().isoformat()}")
                time.sleep(60)  # Heartbeat every 60 seconds
                
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                time.sleep(5)  # Wait before retry
        
        logger.info("AI Agents System Stopped")


def main():
    """Entry point."""
    system = AgentSystem()
    
    # TODO: Register your agents here
    # Example:
    # from src.agents.my_agent import MyAgent
    # system.register_agent(MyAgent())
    
    system.run()


if __name__ == "__main__":
    main()
