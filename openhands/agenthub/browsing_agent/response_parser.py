import ast
import re

from openhands.controller.action_parser import ActionParser, ResponseParser
from openhands.core.logger import openhands_logger as logger
from openhands.events.action import (
    Action, 
    BrowseInteractiveAction, 
    InterimMemoryAction
)


def add_noop_for_interim_memory(action_str: str) -> str:
    """
    Detects ```store_interim_memory(' in the action string and appends `'), noop(1000)`
    at the very end of the function call, ensuring natural language text is untouched.

    Args:
        action_str (str): The full response string from LLM, including natural language.

    Returns:
        str: The modified action string with `'), noop(1000)` appended if needed.
    """
    if not action_str:
        return ""

    # Match three backticks followed by `store_interim_memory('`, then capture everything up to the second single quote
    pattern = r"```store_interim_memory\('[^']*'[^']*'"

    # Append `'), noop(1000)` at the end of the matched function call
    modified_action_str = re.sub(pattern, r"\0), noop(1000", action_str, count=1)

    return modified_action_str




class BrowsingResponseParser(ResponseParser):
    def __init__(self) -> None:
        # Need to pay attention to the item order in self.action_parsers
        super().__init__()
        self.action_parsers = [
            BrowsingActionParserInterimMemory(),
            BrowsingActionParserMessage(),
        ]
        self.default_parser = BrowsingActionParserBrowseInteractive()

    def parse(
        self, response: str | dict[str, list[dict[str, dict[str, str | None]]]]
    ) -> Action:
        if isinstance(response, str):
            action_str = response
        else:
            action_str = self.parse_response(response)
        return self.parse_action(action_str)

    def parse_response(
        self, response: dict[str, list[dict[str, dict[str, str | None]]]]
    ) -> str:
        action_str = response['choices'][0]['message']['content']
        if action_str is None:
            return ''
        action_str = action_str.strip()
        # Debugging before modification

        # Add `noop(1000)` to `store_interim_memory(...)` calls
        action_str = add_noop_for_interim_memory(action_str)

        # Ensure action_str ends with ')```'
        if action_str:
            if not action_str.endswith('```'):
                if action_str.endswith(')'):
                    action_str += '```'  # prevent duplicate ending paranthesis, e.g. send_msg_to_user('Done'))
                else:
                    action_str += ')```'  # expected format
        logger.debug(action_str)
        return action_str

    def parse_action(self, action_str: str) -> Action:
        for action_parser in self.action_parsers:
            if action_parser.check_condition(action_str):
                return action_parser.parse(action_str)
        return self.default_parser.parse(action_str)


class BrowsingActionParserInterimMemory(ActionParser):
    """Parser for interim memory actions: Store, Retrieve."""

    def check_condition(self, action_str: str) -> bool:
        """Check if the action string contains an interim memory action, handling backticks and extra formatting."""

        # Split potential thought from actual action
        parts = action_str.split('```')
        interim_action_str = (
            parts[1].strip()
            if len(parts) > 1 and parts[1].strip()
            else parts[0].strip()
        )

        # Remove any remaining backticks and whitespace
        cleaned_action_str = interim_action_str.strip().strip('`')

        # Check if the cleaned action string matches our new unified interim memory format
        is_interim = cleaned_action_str.startswith(
            ("store_interim_memory", "retrieve_interim_memory")
        )
        return is_interim
    def parse(self, action_str: str) -> Action:
        """Parses an interim memory action into an `InterimMemoryAction`."""
        parts = action_str.split('```')
        memory_action_str = (
            parts[1].strip()
            if len(parts) > 1 and parts[1].strip()
            else parts[0].strip()
        )
        thought = parts[0].strip() if parts[1].strip() != '' else ''

        # Ensure full function call format (preserves parentheses)
        action_match = re.match(r'(store_interim_memory|retrieve_interim_memory)(\(.*\))?', memory_action_str)

        if not action_match:
            return BrowseInteractiveAction(
                browser_actions=f'[INTERIM MEMORY] INVALID ACTION: {memory_action_str}'
            )

        action_type = action_match.group(1)  # "store_interim_memory" or "retrieve_interim_memory"
        params = action_match.group(2)       # "('content')" or None

        # Extract content properly
        if params:
            content_match = re.match(r'\((.*?)\)', params)
            content = content_match.group(1) if content_match else ""
        else:
            content = ""

        # Ensure valid content format
        content = content.strip().strip('"').strip("'") if content else ""

        # Handle user message extraction
        msg_content = ''
        for sub_action in memory_action_str.split('\n'):
            if 'send_msg_to_user(' in sub_action:
                try:
                    tree = ast.parse(sub_action)
                    args = tree.body[0].value.args  # type: ignore
                    msg_content = args[0].value
                except SyntaxError:
                    match = re.search(r'send_msg_to_user\((["\'])(.*?)\1\)', sub_action)
                    if match:
                        msg_content = match.group(2)

        # logger.info(f'[PARSING] BROWSER_ACTIONS: {action_type} THOUGHT: {thought} CONTENT: {content} MSG_CONTENT: {msg_content}')

        return InterimMemoryAction(
            browser_actions=action_type,
            content=content,
            thought=thought,
            browsergym_send_msg_to_user=msg_content,
        )


class BrowsingActionParserMessage(ActionParser):
    """Parser action:
    - BrowseInteractiveAction(browser_actions) - unexpected response format, message back to user
    """

    def __init__(self) -> None:
        pass

    def check_condition(self, action_str: str) -> bool:
        return '```' not in action_str

    def parse(self, action_str: str) -> Action:
        msg = f'send_msg_to_user("""{action_str}""")'
        return BrowseInteractiveAction(
            browser_actions=msg,
            thought=action_str,
            browsergym_send_msg_to_user=action_str,
        )


class BrowsingActionParserBrowseInteractive(ActionParser):
    """Parser action:
    - BrowseInteractiveAction(browser_actions) - handle send message to user function call in BrowserGym
    """

    def __init__(self) -> None:
        pass

    def check_condition(self, action_str: str) -> bool:
        return True

    def parse(self, action_str: str) -> Action:
        # parse the action string into browser_actions and thought
        # the LLM can return only one string, or both

        # when both are returned, it looks like this:
        ### Based on the current state of the page and the goal of finding out the president of the USA, the next action should involve searching for information related to the president.
        ### To achieve this, we can navigate to a reliable source such as a search engine or a specific website that provides information about the current president of the USA.
        ### Here is an example of a valid action to achieve this:
        ### ```
        ### goto('https://www.whitehouse.gov/about-the-white-house/presidents/'
        # in practice, BrowsingResponseParser.parse_response also added )``` to the end of the string

        # when the LLM returns only one string, it looks like this:
        ### goto('https://www.whitehouse.gov/about-the-white-house/presidents/')
        # and parse_response added )``` to the end of the string
        parts = action_str.split('```')
        browser_actions = (
            parts[1].strip() if parts[1].strip() != '' else parts[0].strip()
        )
        thought = parts[0].strip() if parts[1].strip() != '' else ''

        # if the LLM wants to talk to the user, we extract the message
        msg_content = ''
        for sub_action in browser_actions.split('\n'):
            if 'send_msg_to_user(' in sub_action:
                try:
                    tree = ast.parse(sub_action)
                    args = tree.body[0].value.args  # type: ignore
                    msg_content = args[0].value
                except SyntaxError:
                    logger.error(f'Error parsing action: {sub_action}')
                    # the syntax was not correct, but we can still try to get the message
                    # e.g. send_msg_to_user("Hello, world!") or send_msg_to_user('Hello, world!'
                    match = re.search(r'send_msg_to_user\((["\'])(.*?)\1\)', sub_action)
                    if match:
                        msg_content = match.group(2)
                    else:
                        msg_content = ''

        return BrowseInteractiveAction(
            browser_actions=browser_actions,
            thought=thought,
            browsergym_send_msg_to_user=msg_content,
        )
