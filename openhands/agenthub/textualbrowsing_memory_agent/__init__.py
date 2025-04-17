# openhands/agenthub/visualbrowisng_memory_agent
from openhands.agenthub.textualbrowsing_memory_agent.textualbrowsing_memory_agent import (
    TextualBrowsingMemoryAgent,
)
from openhands.controller.agent import Agent

Agent.register('TextualBrowsingMemoryAgent', TextualBrowsingMemoryAgent)
# openhands/agenthub/visualbrowisng_interim_memory_agent/visualbrowsing_memory_agent.py