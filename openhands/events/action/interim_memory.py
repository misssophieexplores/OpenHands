from dataclasses import dataclass
from typing import Any, ClassVar

from openhands.core.logger import openhands_logger as logger
from openhands.core.schema import ActionType
from openhands.events.action import BrowseInteractiveAction
from openhands.events.action.action import ActionSecurityRisk


@dataclass
class InterimMemoryAction(BrowseInteractiveAction):
    browser_actions: str  # Can be "store_interim_memory", "update_interim_memory", or "retrieve_interim_memory"
    thought: str = ''
    browsergym_send_msg_to_user: str = ''
    action: str = ActionType.INTERIM_MEMORY
    runnable: ClassVar[bool] = True
    security_risk: ActionSecurityRisk | None = None
    key: str = ''
    value: Any = None  # Optional (needed for store & update)

    @property
    def message(self) -> str:
        """Formats the message based on the action type."""
        if self.browser_actions == 'store_interim_memory':
            return f"I stored the key '{self.key}' with value '{self.value}' in interim memory."
        elif self.browser_actions == 'update_interim_memory':
            return f"I updated the key '{self.key}' to new value '{self.value}' in interim memory."
        elif self.browser_actions == 'retrieve_interim_memory':
            return f"I retrieved the key '{self.key}' from interim memory."
        return 'Invalid interim memory action.'

    def __str__(self) -> str:
        """Formats logging output."""
        ret = '**InterimMemoryAction**\n'
        if self.thought:
            ret += f'THOUGHT: {self.thought}\n'
        ret += f'INTERIM_MEMORY_ACTION: {self.browser_actions}'
        if self.key is not None:
            ret += '\nKEY: {self.key}\n'
        if self.value is not None:
            ret += f'VALUE: {self.value}\n'
        return ret


# ===========================
# Define the Available Actions
# ===========================


def store_interim_memory(key: str, value: Any) -> InterimMemoryAction:
    """Stores a key-value pair in interim memory."""
    logger.info(f"[INTERIM MEMORY] Storing key='{key}' with value='{value}'")
    return InterimMemoryAction(browser_actions='store', key=key, value=value)


def update_interim_memory(key: str, value: Any) -> InterimMemoryAction:
    """Updates an existing key-value pair in interim memory."""
    logger.info(f"[INTERIM MEMORY] Updating key='{key}' to new value='{value}'")
    return InterimMemoryAction(browser_actions='update', key=key, value=value)


def retrieve_interim_memory(key: str) -> InterimMemoryAction:
    """Retrieves a stored value from interim memory."""
    logger.info(f"[INTERIM MEMORY] Retrieving key='{key}' from interim memory")
    return InterimMemoryAction(browser_actions='retrieve', key=key)
