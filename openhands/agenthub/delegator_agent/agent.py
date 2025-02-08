from openhands.controller.agent import Agent
from openhands.controller.state.state import State
from openhands.events.action import (
    Action,
    AgentDelegateAction,
    AgentFinishAction,
    BrowseInteractiveAction,
)
from openhands.events.observation import AgentDelegateObservation, Observation


class DelegatorAgent(Agent):
    VERSION = '2.1'
    current_delegate: str = ''
    initial_step_done: bool = False  # Track if initial step has run

    def step(self, state: State) -> Action:
        """Dynamically chooses which browsing agent to delegate to, but first executes a predefined step."""

        # Execute initial navigation step before agent delegation
        if not self.initial_step_done:
            self.initial_step_done = True
            return BrowseInteractiveAction(
                browser_actions="goto('https://ourworldindata.org/co2-emissions')"
            )

        # If no agent has been assigned, start with BrowsingAgent
        if self.current_delegate == '':
            self.current_delegate = 'browsing'
            task, _ = state.get_current_user_intent()
            return AgentDelegateAction(agent='BrowsingAgent', inputs={'task': task})

        # Find last observation
        last_observation = None
        for event in reversed(state.history):
            if isinstance(event, Observation):
                last_observation = event
                break

        if not isinstance(last_observation, AgentDelegateObservation):
            raise Exception('Last observation is not an AgentDelegateObservation')

        goal, _ = state.get_current_user_intent()

        # Switch to VisualBrowsingAgent if images are present
        if self.current_delegate == 'browsing':
            if (
                'image' in last_observation.outputs
                or 'canvas' in last_observation.outputs
            ):
                self.current_delegate = 'visual_browsing'
                return AgentDelegateAction(
                    agent='VisualBrowsingAgent', inputs={'task': goal}
                )
            else:
                return AgentFinishAction()

        elif self.current_delegate == 'visual_browsing':
            return AgentFinishAction()

        else:
            raise Exception('Invalid delegate state')
