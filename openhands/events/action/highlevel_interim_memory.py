from typing import Any

from browsergym.core.action.highlevel import HighLevelActionSet

from openhands.events.action.interim_memory import InterimMemoryAction


def store_interim_memory(content: str):
    """Stores a key-value pair in interim memory."""
    return InterimMemoryAction(
        browser_actions='store_interim_memory', content=content
    )


def retrieve_interim_memory():
    """Retrieves a stored value from interim memory."""
    return InterimMemoryAction(browser_actions='retrieve_interim_memory')


class InterimMemoryActionSet(HighLevelActionSet):
    """Extends HighLevelActionSet to include interim memory actions."""

    def __init__(self, subsets=None, strict=False, multiaction=False):
        # Ensure the parent class initializes first
        super().__init__(subsets=subsets, strict=strict, multiaction=multiaction)

        # Register interim memory actions AFTER initialization
        if not hasattr(self, 'actions'):
            self.actions = {}

        self.actions.update(
            {
                'store_interim_memory': store_interim_memory,
                'retrieve_interim_memory': retrieve_interim_memory,
            }
        )
