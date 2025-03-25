from typing import Any
from browsergym.core.action.highlevel import HighLevelActionSet
from openhands.memory.interim_memory import InterimMemory
from openhands.core.logger import openhands_logger as logger


class InterimMemoryActionSet(HighLevelActionSet):
    """Extends HighLevelActionSet to include interim memory actions."""

    def __init__(self, subsets=None, strict=False, multiaction=False, custom_actions=None):
        if subsets is None:
            subsets = ["custom"] 
        # Preserve existing custom actions while adding new ones
        if custom_actions is None:
            custom_actions = []
        custom_actions.extend([self.store_interim_memory, self.retrieve_interim_memory])
        if "custom" not in subsets:
            subsets.append("custom")

        super().__init__(subsets=subsets, strict=strict, multiaction=multiaction, custom_actions=custom_actions)
        logger.info(f"[HIGHLEVEL INTERIM MEMORY] Available high-level actions: {list(self.action_set.keys())}")



        if not hasattr(self, 'actions'):
            self.actions = {}

        self.actions.update(
            {

                'store_interim_memory': self.store_interim_memory,
                'retrieve_interim_memory': self.retrieve_interim_memory,
            }
        )
    def store_interim_memory(self, content: str):
        """Appends new content to interim memory.
        
        Examples:
            store_interim_memory("User's selected product: Product A")
        """
        InterimMemory.store(content)

    def retrieve_interim_memory(self):
        """Returns the stored interim memory.
        
        Examples:
            retrieve_interim_memory()
        """
        return InterimMemory.retrieve()