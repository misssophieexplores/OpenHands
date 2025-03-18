from openhands.events.observation.observation import Observation
from dataclasses import dataclass, field
from typing import ClassVar, Dict
from openhands.events.event import EventSource
from openhands.core.schema import ObservationType

@dataclass
class InterimMemoryObservation(Observation):
    """Custom observation type for storing retrieved interim memory content."""

    memory_content: str = ""
    runnable: ClassVar[bool] = False 
    observation: ClassVar[str] = "interim_memory"
    # observation: str = ObservationType.AGENT_STATE_CHANGED
    last_browser_action: str = "" 
    error: bool = False
    def __post_init__(self):
        """Ensure the `Observation` superclass is correctly initialized."""
        super().__init__(content=str(self.memory_content)) 
        self._source = EventSource.ENVIRONMENT  
    def __str__(self):
        if self.last_browser_action.startswith("retrieve_interim_memory"):
            return f"**InterimMemoryObservation**\nRetrieved Memory:\n{self.memory_content}"
        elif self.last_browser_action.startswith("store_interim_memory"):
            return f"**InterimMemoryObservation**\nStored Memory Successfully."
        return f"**InterimMemoryObservation**\n(Unknown Interim Memory Action)"