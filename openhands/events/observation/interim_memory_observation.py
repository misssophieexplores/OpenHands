from openhands.events.observation.observation import Observation
from dataclasses import dataclass, field
from typing import ClassVar, Dict
from openhands.events.event import EventSource


@dataclass
class InterimMemoryObservation(Observation):
    """Custom observation type for storing retrieved interim memory content."""

    memory_content: str = ""
    runnable: ClassVar[bool] = False 
    observation: ClassVar[str] = "interim_memory"
    def __post_init__(self):
        """Ensure the `Observation` superclass is correctly initialized."""
        super().__init__(content=str(self.memory_content)) 
        self._source = EventSource.ENVIRONMENT  
    def __str__(self):
        return f"**InterimMemoryObservation**\nRetrieved Memory:\n{self.content}"
