from dataclasses import dataclass, field

from browsergym.utils.obs import flatten_axtree_to_str

from openhands.core.schema import ActionType, ObservationType
from openhands.events.observation.observation import Observation
import traceback


@dataclass
class BrowserOutputObservation(Observation):
    """This data class represents the output of a browser."""

    url: str
    trigger_by_action: str
    interim_memory: str = ''
    include_interim_memory: bool = False
    screenshot: str = field(repr=False, default='')  # don't show in repr
    set_of_marks: str = field(default='', repr=False)  # don't show in repr
    error: bool = False
    observation: str = ObservationType.BROWSE
    goal_image_urls: list = field(default_factory=list)
    # do not include in the memory
    open_pages_urls: list = field(default_factory=list)
    active_page_index: int = -1
    dom_object: dict = field(default_factory=dict, repr=False)  # don't show in repr
    axtree_object: dict = field(default_factory=dict, repr=False)  # don't show in repr
    extra_element_properties: dict = field(
        default_factory=dict, repr=False
    )  # don't show in repr
    last_browser_action: str = ''
    last_browser_action_error: str = ''
    focused_element_bid: str = ''

    def __post_init__(self):
        from openhands.memory.interim_memory import InterimMemory
        self.interim_memory = InterimMemory.retrieve()
        self.post_process_interim_memory()
        # print('BrowserOutputObservation: interim memory retrieved:', self.interim_memory)
        # print('BrowserOutputObservation instantiated at:')
        # traceback.print_stack(limit=5)  # Print where the instance is created


    
    @property
    def message(self) -> str:
        return 'Visited ' + self.url

    def __str__(self) -> str:
        if 'store_interim_memory' in self.last_browser_action or 'retrieve_interim_memory' in self.last_browser_action:
            self.include_interim_memory = True

        ret = (
            '**BrowserOutputObservation**\n'
            f'URL: {self.url}\n'
            f'Error: {self.error}\n'
            f'Open pages: {self.open_pages_urls}\n'
            f'Active page index: {self.active_page_index}\n'
            f'Last browser action: {self.last_browser_action}\n'
            f'Last browser action error: {self.last_browser_action_error}\n'
            f'Focused element bid: {self.focused_element_bid}\n'
        )
        ret += '--- Agent Observation ---\n'
        ret += self.get_agent_obs_text()
        return ret

    def get_agent_obs_text(self) -> str:
        """Get a concise text that will be shown to the agent."""
        if self.trigger_by_action == ActionType.BROWSE_INTERACTIVE:
            # update the interim memory:

            text = f'[Current URL: {self.url}]\n'
            text += f'[Focused element bid: {self.focused_element_bid}]\n\n'
            if self.error:
                text += (
                    '================ BEGIN error message ===============\n'
                    'The following error occurred when executing the last action:\n'
                    f'{self.last_browser_action_error}\n'
                    '================ END error message ===============\n'
                )
            else:
                text += '[Action executed successfully.]\n'
            if self.include_interim_memory:
                text += (
                    f'\n================ BEGIN Interim Memory ================\n'
                    f'{self.interim_memory}\n'
                    f'================ END Interim Memory ================\n'
                )
            try:
                # We do not filter visible only here because we want to show the full content
                # of the web page to the agent for simplicity.
                # FIXME: handle the case when the web page is too large
                cur_axtree_txt = self.get_axtree_str(filter_visible_only=False)
                text += (
                    f'============== BEGIN accessibility tree ==============\n'
                    f'{cur_axtree_txt}\n'
                    f'============== END accessibility tree ==============\n'
                )
            except Exception as e:
                text += (
                    f'\n[Error encountered when processing the accessibility tree: {e}]'
                )
            return text

        elif self.trigger_by_action == ActionType.BROWSE:
            text = f'[Current URL: {self.url}]\n'
            if self.error:
                text += (
                    '================ BEGIN error message ===============\n'
                    'The following error occurred when trying to visit the URL:\n'
                    f'{self.last_browser_action_error}\n'
                    '================ END error message ===============\n'
                )
            text += '============== BEGIN webpage content ==============\n'
            text += self.content
            text += '\n============== END webpage content ==============\n'
            return text
        else:
            raise ValueError(f'Invalid trigger_by_action: {self.trigger_by_action}')

    def get_axtree_str(self, filter_visible_only: bool = False) -> str:
        cur_axtree_txt = flatten_axtree_to_str(
            self.axtree_object,
            extra_properties=self.extra_element_properties,
            with_clickable=True,
            skip_generic=False,
            filter_visible_only=filter_visible_only,
        )
        return cur_axtree_txt
    
    def post_process_interim_memory(self):
        """Removes the error flag for interim memory actions, if any."""
        # TODO: logic to find errors with interim memory actions
        if (
            isinstance(self.last_browser_action, str) and 
            (
                self.last_browser_action.strip().startswith("store_interim_memory(")
                or self.last_browser_action.strip().startswith("retrieve_interim_memory(")
            )
        ):
            self.error = False
            self.last_browser_action_error = ''


