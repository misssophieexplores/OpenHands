import json
import os
import time
import urllib.request
from datetime import datetime
from openhands.events.action.highlevel_interim_memory import InterimMemoryActionSet
from browsergym.utils.obs import flatten_axtree_to_str
from openhands.agenthub.browsing_agent.response_parser import BrowsingResponseParser
from openhands.controller.agent import Agent
from openhands.controller.state.state import State
from openhands.core.config import AgentConfig
from openhands.core.logger import get_experiment_folder, get_web_docu_folder
from openhands.core.logger import openhands_logger as logger
from openhands.core.message import ImageContent, Message, TextContent
from openhands.events.action import (
    Action,
    AgentFinishAction,
    BrowseInteractiveAction,
    MessageAction,
    InterimMemoryAction
)
from openhands.events.event import EventSource
from openhands.events.observation import BrowserOutputObservation, InterimMemoryObservation
from openhands.events.observation.observation import Observation
from openhands.llm.metrics_tracker import MetricsTracker
from openhands.llm.llm import LLM
from openhands.runtime.plugins import (
    PluginRequirement,
)
EXPERIMENT_FOLDER = get_experiment_folder()
WEB_DOCU_FOLDER = get_web_docu_folder()
URL_LOG_FILE_JSON = os.path.join(EXPERIMENT_FOLDER, 'url_action_log.json')


def initialize_url_log():
    """Create the URL action log file if it does not exist."""
    if not os.path.exists(URL_LOG_FILE_JSON):
        with open(URL_LOG_FILE_JSON, 'w', encoding='utf-8') as f:
            json.dump([], f, indent=4, ensure_ascii=False)


def log_url_action_json(url, action, agent_type='VisualBrowsingAgent'):
    """Append URL, action, and timestamp to a separate JSON log file."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    log_entry = {
        'timestamp': timestamp,
        'url': url,
        'action': action,
        'agent_type': agent_type,
    }
    initialize_url_log()
    with open(URL_LOG_FILE_JSON, 'r+', encoding='utf-8') as f:
        try:
            logs = json.load(f)
        except json.JSONDecodeError:
            logs = []
        logs.append(log_entry)
        f.seek(0)
        json.dump(logs, f, indent=4, ensure_ascii=False)


def get_error_prefix(obs: BrowserOutputObservation) -> str:
    # temporary fix for OneStopMarket to ignore timeout errors
    if 'timeout' in obs.last_browser_action_error:
        return ''
    return f'## Error from previous action:\n{obs.last_browser_action_error}\n'


def create_goal_prompt(
    goal: str, image_urls: list[str] | None
) -> tuple[str, list[str]]:
    goal_txt: str = f"""\
# Instructions
Review the current state of the page and all other information to find the best possible next action to accomplish your goal. Your answer will be interpreted and executed by a program, make sure to follow the formatting instructions.

## Goal:
{goal}
"""
    goal_image_urls = []
    if image_urls is not None:
        for idx, url in enumerate(image_urls):
            goal_txt = goal_txt + f'Images: Goal input image ({idx+1})\n'
            goal_image_urls.append(url)
    goal_txt += '\n'
    return goal_txt, goal_image_urls


def create_observation_prompt(
    axtree_txt: str,
    tabs: str,
    focused_element: str,
    error_prefix: str,
    som_screenshot: str | None,
) -> tuple[str, str | None]:
    txt_observation = f"""
# Observation of current step:
{tabs}{axtree_txt}{focused_element}{error_prefix}
"""

    # screenshot + som: will be a non-empty string if present in observation
    screenshot_url = None
    if (som_screenshot is not None) and (len(som_screenshot) > 0):
        txt_observation += 'Image: Current page screenshot (Note that only visible portion of webpage is present in the screenshot. You may need to scroll to view the remaining portion of the web-page.\n'
        screenshot_url = som_screenshot
    else:
        logger.info('SOM Screenshot not present in observation!')
    txt_observation += '\n'
    return txt_observation, screenshot_url


def get_tabs(obs: BrowserOutputObservation) -> str:
    prompt_pieces = ['\n## Currently open tabs:']
    for page_index, page_url in enumerate(obs.open_pages_urls):
        active_or_not = ' (active tab)' if page_index == obs.active_page_index else ''
        prompt_piece = f"""\
Tab {page_index}{active_or_not}:
URL: {page_url}
"""
        prompt_pieces.append(prompt_piece)
    return '\n'.join(prompt_pieces) + '\n'


def get_axtree(axtree_txt: str) -> str:
    bid_info = """\
Note: [bid] is the unique alpha-numeric identifier at the beginning of lines for each element in the AXTree. Always use bid to refer to elements in your actions.

"""
    visible_tag_info = """\
Note: You can only interact with visible elements. If the "visible" tag is not present, the element is not visible on the page.

"""
    return f'\n## AXTree:\n{bid_info}{visible_tag_info}{axtree_txt}\n'


def get_action_prompt(action_set: InterimMemoryActionSet) -> str:
    action_set_generic_info = """\
Note: This action set includes standard browsing actions as well as interim memory actions. Most of the browsing actions are python function executing playwright code. The primary way of referring to elements in the page is through bid which are specified in your observations.
Interim memory actions allow you to store, update, and retrieve information for later use.
"""
    action_description = action_set.describe(
        with_long_description=False,
        with_examples=False,
    )
    action_prompt = f'# Action space:\n{action_set_generic_info}{action_description}\n'
    return action_prompt


def get_history_prompt(prev_actions: list[BrowseInteractiveAction]) -> str:
    history_prompt = ['# History of all previous interactions with the task:\n']
    for i in range(len(prev_actions)):
        history_prompt.append(f'## step {i+1}')
        history_prompt.append(
            f'\nOuput thought and action: {prev_actions[i].thought} ```{prev_actions[i].browser_actions}```\n'
        )
    return '\n'.join(history_prompt) + '\n'


class VisualBrowsingAgent(Agent):
    VERSION = '1.0'
    """
    VisualBrowsing Agent that can uses webpage screenshots during browsing.
    """

    sandbox_plugins: list[PluginRequirement] = []
    response_parser = BrowsingResponseParser()

    def __init__(
        self,
        llm: LLM,
        config: AgentConfig,
    ) -> None:
        """Initializes a new instance of the VisualBrowsingAgent class.

        Parameters:
        - llm (LLM): The llm to be used by this agent
        """
        super().__init__(llm, config)
        self.page_counter = 1
        self.metrics_tracker = MetricsTracker(
            model_name=llm.config.model, agent_name='openhands_memory_visual_browsing_agent'
        )
        # define a configurable action space, with chat functionality, web navigation, and webpage grounding using accessibility tree and HTML.
        # see https://github.com/ServiceNow/BrowserGym/blob/main/core/src/browsergym/core/action/highlevel.py for more details
        action_subsets = [
            'chat',
            'bid',
            'nav',
            'tab',
            'infeas',
        ]
        self.action_space = InterimMemoryActionSet(
            subsets=action_subsets,
            strict=False,  # less strict on the parsing of the actions
            multiaction=False,
        )
        self.action_prompt = get_action_prompt(self.action_space)
        self.abstract_example = f"""
# Abstract Example

Here is an abstract version of the answer with description of the content of each tag. Make sure you follow this structure, but replace the content with your answer:

You must mandatorily think step by step. If you need to make calculations such as coordinates, write them here. Describe the effect that your previous action had on the current content of the page.

If relevant, store or update information in interim memory to keep track of findings across multiple steps.

In summary the next action I will perform is ```{self.action_space.example_action(abstract=True)}```
"""
        self.concrete_example = """
# Concrete Example

Here is a concrete example of how to format your answer. Make sure to generate the action in the correct format, ensuring that the action is present inside ``````:

## Example 1: Handling UI interactions
Let's think step-by-step. From the previous action, I tried to set the value of year to "2022" using select_option, but it doesn't appear to be in the form. It may be a dynamic dropdown, so I will try using click with the bid "324" and look at the response from the page.

In summary, the next action I will perform is ```click('324')```

---

## Example 2: Storing partial answers in Interim Memory
The user asked me to find the price, availability, and product ID for multiple products. I have found the price and product ID for Product A, but not its availability yet. Since this is part of the final answer, I will store the details I have so far before continuing searching for the availabilty information. In summary, the next action I will perform is ```store_interim_memory('Product A - Price: $49.99, Product ID: 12345'), scroll(0, 1000)```
"""

        self.hints = """
Note:
* Make sure to use bid to identify elements when using commands.
* Interacting with comboboxes, dropdowns, and auto-complete fields can be tricky; sometimes you need to use select_option, while other times you need to use fill or click and wait for the reaction of the page.
* Use interim memory to store relevant information. Retrieve stored information before finalizing the answer.
"""
        self.reset()

    def reset(self) -> None:
        """Resets the VisualBrowsingAgent."""
        super().reset()
        self.cost_accumulator = 0
        self.error_accumulator = 0

    def step(self, state: State) -> Action:
        """Performs one step using the VisualBrowsingAgent.

        This includes gathering information on previous steps and prompting the model to make a browsing command to execute.

        Parameters:
        - state (State): used to get updated info

        Returns:
        - BrowseInteractiveAction(browsergym_command) - BrowserGym commands to run
        - MessageAction(content) - Message action to run (e.g. ask for clarification)
        - AgentFinishAction() - end the interaction
        """
        step_start_time = time.time()  # Start timing
        input_tokens, output_tokens = 0, 0  # Default token values

        messages: list[Message] = []
        prev_actions = []
        cur_axtree_txt = ''
        error_prefix = ''
        focused_element = ''
        tabs = ''
        last_obs = None
        last_action = None
        observation_txt = "No observation available."
        som_screenshot = None

        if len(state.history) == 1:
            # for visualwebarena, webarena and miniwob++ eval, we need to retrieve the initial observation already in browser env
            # initialize and retrieve the first observation by issuing an noop OP
            # For non-benchmark browsing, the browser env starts with a blank page, and the agent is expected to first navigate to desired websites
            return BrowseInteractiveAction(browser_actions='noop(1000)')
        
        # Step 1: Identify last action & observation
        for event in state.history:
            if isinstance(event, (BrowseInteractiveAction, InterimMemoryAction)): 
                prev_actions.append(event)
                last_action = event 
            elif isinstance(event, MessageAction) and event.source == EventSource.AGENT:
                # agent has responded, task finished.
                final_answer = event.content
                self.metrics_tracker.set_final_answer(final_answer) 
                logger.info('Final Metrics Summary:')
                logger.info(self.llm.metrics.log())
                self.metrics_tracker.save_metrics() 
                return AgentFinishAction(outputs={'content': event.content})  
            elif isinstance(event, InterimMemoryObservation):
                # Ensure last_action is correctly updated when storing interim memory
                last_action_str = (
                    last_action.browser_actions if isinstance(last_action, InterimMemoryAction)
                    else last_obs.last_browser_action if isinstance(last_obs, InterimMemoryObservation)
                    else "retrieve_interim_memory()"
                )

                last_obs = event
                last_action = event 

    
            elif isinstance(event, Observation):
                last_obs = event

        if len(prev_actions) >= 1:  # ignore noop()
            prev_actions = prev_actions[1:]  # remove the first noop action

        # Step 2: Handle agent response if needed
        # if the final BrowserInteractiveAction exec BrowserGym's send_msg_to_user,
        # we should also send a message back to the user in OpenHands and call it a day
        if (
            isinstance(last_action, (BrowseInteractiveAction, InterimMemoryAction))
            and last_action.browsergym_send_msg_to_user
        ):
            return MessageAction(last_action.browsergym_send_msg_to_user)
        
        # Step 3: Separate Handling for Browser vs Interim Memory Observations
        history_prompt = get_history_prompt(prev_actions)
        if isinstance(last_obs, (BrowserOutputObservation, InterimMemoryObservation)): 
            if last_obs.error:
                # add error recovery prompt prefix
                error_prefix = get_error_prefix(last_obs)
                if len(error_prefix) > 0:
                    self.error_accumulator += 1
                    if self.error_accumulator > 10:
                        return MessageAction(
                            'Too many errors encountered. Task failed.'
                        )
            if isinstance(last_obs, BrowserOutputObservation):
                # check if the last observation is an error for BrowswerOutputObservation
                focused_element = '## Focused element:\nNone\n'
                if last_obs.focused_element_bid is not None:
                    focused_element = (
                        f"## Focused element:\nbid='{last_obs.focused_element_bid}'\n"
                    )
                tabs = get_tabs(last_obs)
            cur_url_str = last_obs.url if hasattr(last_obs, 'url') else ''


            last_action_str = last_obs.last_browser_action if isinstance(last_obs, BrowserOutputObservation) else last_action.last_browser_action


            print(f"\n###########\nDEBUGGING\nlast_action_str: {last_action_str}\nlast_obs.last_browser_action: {last_obs.last_browser_action}\nlast_action: {last_action}\n###########\n")

            # Log to the separate file
            log_url_action_json(url=cur_url_str, action=last_action_str)
            self.metrics_tracker.track_visited_url(cur_url_str, last_action_str)
            if cur_url_str:  # Normal browser actions
                self.metrics_tracker.track_visited_url(cur_url_str, last_action_str)
            else:  # Handle interim memory actions
                if isinstance(last_action, InterimMemoryAction):
                    self.metrics_tracker.track_visited_url('', last_action_str)


            if isinstance(last_obs, BrowserOutputObservation): # only for BrowserOutputObservations
                try:
                    # IMPORTANT: keep AX Tree of full webpage, add visible and clickable tags
                    cur_axtree_txt = flatten_axtree_to_str(
                        last_obs.axtree_object,
                        extra_properties=last_obs.extra_element_properties,
                        with_visible=True,
                        with_clickable=True,
                        with_center_coords=False,
                        with_bounding_box_coords=False,
                        filter_visible_only=False,
                        filter_with_bid_only=False,
                        filter_som_only=False,
                    )
                    cur_axtree_txt = get_axtree(axtree_txt=cur_axtree_txt)
                except Exception as e:
                    logger.error(
                        'Error when trying to process the accessibility tree: %s', e
                    )
                    return MessageAction('Error encountered when browsing.')
                set_of_marks = last_obs.set_of_marks if hasattr(last_obs, "set_of_marks") else None

        elif isinstance(last_obs, InterimMemoryObservation):
            # Handle Interim Memory Observations
            cur_url_str = ""  # No URL for interim memory
            last_action_str = last_action.browser_actions if isinstance(last_action, InterimMemoryAction) else ""

            log_url_action_json(url=cur_url_str, action=last_action_str)
            self.metrics_tracker.track_visited_url(cur_url_str, last_action_str)

            observation_txt = f"Retrieved Interim Memory:\n{last_obs.content}"
            som_screenshot = None  # No screenshot for interim memory
            set_of_marks = None  # No marks needed for interim memory

        else:
            # Fallback case (should not happen)
            logger.warning("Unhandled observation type: %s", type(last_obs))
            observation_txt = "Unhandled observation."
            som_screenshot = None
            set_of_marks = None
    
        goal, image_urls = state.get_current_user_intent()

        if goal is None:
            goal = state.inputs['task']
        # Store the query in metrics (only on first step)
        if self.metrics_tracker.query is None:
            self.metrics_tracker.set_query(goal)
        goal_txt, goal_images = create_goal_prompt(goal, image_urls)
        if isinstance(last_obs, BrowserOutputObservation):
            observation_txt, som_screenshot = create_observation_prompt(
                cur_axtree_txt, tabs, focused_element, error_prefix, set_of_marks
            )


        # Step 4: Create the prompt for the LLM
        if isinstance(last_obs, BrowserOutputObservation):
            # Save screenshot if available
            if som_screenshot is not None and len(som_screenshot) > 0:
                timestamp_som = datetime.now().strftime('%Y-%m-%d_%H-%M')
                screenshot_filename = os.path.join(
                    WEB_DOCU_FOLDER,
                    f'{timestamp_som}_screenshot_{self.page_counter}.png',
                )  # save screenshot with timestamp
                self.metrics_tracker.increment_screenshot_count()  # increment screenshot count

                try:
                    urllib.request.urlretrieve(som_screenshot, screenshot_filename)
                    logger.info(f'Saved screenshot to {screenshot_filename}')
                except Exception as e:
                    logger.error(f'Failed to save screenshot: {e}')

        # Save the webpage structure (AXTree) and interaction history
        timestamp_web = datetime.now().strftime('%Y-%m-%d_%H-%M')
        content_filename = os.path.join(
            WEB_DOCU_FOLDER, f'{timestamp_web}_webpage_{self.page_counter}.txt'
        )
        with open(content_filename, 'w', encoding='utf-8') as f:
            f.write('==== PAGE URL ====\n')
            if last_obs is not None and hasattr(last_obs, 'url'):
                f.write(f'{last_obs.url}\n\n')
            else:
                f.write('No URL available\n\n')
            f.write('==== ACCESSIBILITY TREE ====\n')
            f.write(cur_axtree_txt + '\n\n')
            # f.write("==== PREVIOUS ACTIONS ====\n")
            # f.write(history_prompt + "\n")
        self.page_counter += 1

        human_prompt: list[TextContent | ImageContent] = [
            TextContent(type='text', text=goal_txt)
        ]
        if len(goal_images) > 0:
            human_prompt.append(ImageContent(image_urls=goal_images))
        human_prompt.append(TextContent(type='text', text=observation_txt))
        if som_screenshot is not None:
            human_prompt.append(ImageContent(image_urls=[som_screenshot]))
        remaining_content = f"""
{history_prompt}\
{self.action_prompt}\
{self.hints}\
{self.abstract_example}\
{self.concrete_example}\
"""
        human_prompt.append(TextContent(type='text', text=remaining_content))

        system_msg = """\
You are an agent trying to solve a web task based on the content of the page and user instructions. You can interact with the page and explore, and send messages to the user when you finish the task. Each time you submit an action it will be sent to the browser and you will receive a new page.
""".strip()

        messages.append(Message(role='system', content=[TextContent(text=system_msg)]))
        messages.append(Message(role='user', content=human_prompt))

        flat_messages = self.llm.format_messages_for_llm(messages)

        response = self.llm.completion(
            messages=flat_messages,
            temperature=0.0,
            stop=[')```', ')\n```'],
        )
        print(f"\nDEBUGGING RESPONSE: {response}\n")
        # Extract token usage from the response object
        if hasattr(response, 'usage'):
            input_tokens = response.usage.get('prompt_tokens', 0)
            output_tokens = response.usage.get('completion_tokens', 0)

        # Record metrics before returning
        self.metrics_tracker.record_step(step_start_time, input_tokens, output_tokens)
        # # TODO: DEBUGGIN ONLY
        # action_str = self.response_parser.parse(response)
        # if isinstance(action_str, InterimMemoryAction):
        #     result_observation = state.handle_interim_memory_action(action_str)

        #     if isinstance(result_observation, InterimMemoryObservation):
        #         return result_observation  # Ensures the agent reads and integrates the memory


        return self.response_parser.parse(response) 
