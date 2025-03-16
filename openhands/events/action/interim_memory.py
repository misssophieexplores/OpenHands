from dataclasses import dataclass
from typing import Any, ClassVar

from openhands.core.logger import openhands_logger as logger
from openhands.core.schema import ActionType
from openhands.events.action import BrowseInteractiveAction
from openhands.events.action.action import ActionSecurityRisk


@dataclass
class InterimMemoryAction(BrowseInteractiveAction):
    browser_actions: str  # Can be "store_interim_memory",
    thought: str = ''
    browsergym_send_msg_to_user: str = ''
    action: str = ActionType.INTERIM_MEMORY
    runnable: ClassVar[bool] = True
    security_risk: ActionSecurityRisk | None = None
    content: str = '' 

    @property
    def message(self) -> str:
        """Formats the message based on the action type."""
        if self.browser_actions == 'store_interim_memory':
            return f"I added to interim memory: '{self.content}'."
        elif self.browser_actions == 'retrieve_interim_memory':
            return "I retrieved the interim memory."
        return "Invalid interim memory action."

    def __str__(self) -> str:
        """Formats logging output."""
        ret = "**InterimMemoryAction**\n"
        if self.thought:
            ret += f"THOUGHT: {self.thought}\n"
        ret += f"INTERIM_MEMORY_ACTION: {self.browser_actions}\nCONTENT: {self.content}"
        return ret


# ===========================
# Define the Available Actions
# ===========================


def store_interim_memory(content: str) -> InterimMemoryAction:
    """Appends new text to interim memory."""
    return InterimMemoryAction(browser_actions="store_interim_memory", content=content)

# Retrieve function remains the same
def retrieve_interim_memory() -> InterimMemoryAction:
    """Retrieves the full interim memory."""
    return InterimMemoryAction(browser_actions="retrieve_interim_memory")
