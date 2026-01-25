from jarvis.agents.calendar_agent import calendar_agent
from jarvis.agents.email_agent import email_agent
from jarvis.agents.web_agent import web_agent
from jarvis.agents.rag_agent import rag_agent

AGENTS = {
    "calendar": calendar_agent,
    "email": email_agent,
    "web": web_agent,
    "rag": rag_agent
}

__all__ = ["AGENTS", "calendar_agent", "email_agent", "web_agent", "rag_agent"]
