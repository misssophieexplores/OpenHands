import atexit
import json
import os
import re
import statistics
import time
from collections import defaultdict
from typing import DefaultDict, Dict
from urllib.parse import urlparse

from openhands.core.logger import get_experiment_folder
from openhands.core.logger import openhands_logger as logger

log_folder = get_experiment_folder()


class MetricsTracker:
    def __init__(self, model_name='gpt-4o', agent_name='openhands'):
        self.start_time = time.time()
        self.step_times = []
        self.input_tokens = 0
        self.output_tokens = 0
        self.model_name = model_name
        self.agent_name: str = agent_name
        self.screenshots = 0
        self.model_calls = 0
        self.visited_urls = {}
        self.domain_counts = {}
        self.query: str | None = None
        self.final_answer: str | None = None
        self.errors = 0
        atexit.register(self.save_metrics)  # Automatically save at program exit

    def set_query(self, query: str):
        """Sets the initial query (only once)."""
        if self.query is None:  # Ensure we don't overwrite it
            self.query = query

    def set_final_answer(self, answer: str):
        """Sets the final answer."""
        self.final_answer = answer

    def increment_error_count(self):
        """Increments the error count."""
        self.errors += 1

    def record_step(self, step_start_time, input_tokens, output_tokens):
        step_duration = time.time() - step_start_time
        self.step_times.append(step_duration)
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens

    def increment_screenshot_count(self):
        """Increments the screenshot count."""
        self.screenshots += 1

    def increment_model_calls(self):
        """Increments the model call count."""
        self.model_calls += 1

    def extract_actions(self, action_type: str | None) -> list[str]:
        """Extracts all action names from a multi-action string.

        Returns:
            list[str]: A list of extracted action names (e.g., ["click", "select_option"]).
        """
        if not action_type:  # Ensure it's not None or empty
            return []
        return re.findall(r'(\w+)\(', action_type)

    def track_visited_url(self, url: str, action_type: str):
        """Track visited URLs and count occurrences, ignoring None values."""
        # if url == 'about:blank':  # Skip tracking if the URL is missing
        #     return

        if url not in self.visited_urls:
            self.visited_urls[url] = {
                'visits': 0,
                'actions': {},  # Ensure this is a normal dictionary
            }

        # Increment visit count
        self.visited_urls[url]['visits'] += 1

        # Increment action count
        actions_only = self.extract_actions(action_type) or []
        for action in actions_only:
            if action:
                self.visited_urls[url]['actions'].setdefault(action, 0)
                self.visited_urls[url]['actions'][action] += 1

    def count_unique_websites(self) -> Dict[str, int]:
        """Count unique domains from visited URLs."""
        domain_counts: DefaultDict[str, int] = defaultdict(int)
        for url, data in self.visited_urls.items():
            visits = data.get('visits', 0)
            base_domain = self.extract_base_domain(url)
            if base_domain:
                domain_counts[base_domain] += (
                    visits  # Safe because defaultdict(int) ensures values start at 0
                )
        return dict(
            domain_counts
        )  # Convert back to regular dict to avoid unexpected behavior

    def extract_base_domain(self, url):
        """Extract base domain from URL (e.g., google.com from https://www.google.com/)."""
        parsed_url = urlparse(url)
        return parsed_url.netloc.split(':')[0]  # Removes any port if present

    def save_metrics(self):
        end_time = time.time()
        full_runtime = end_time - self.start_time
        total_tokens = self.input_tokens + self.output_tokens

        # Calculate stepwise metrics
        min_latency = min(self.step_times, default=0)
        max_latency = max(self.step_times, default=0)
        mean_latency = statistics.mean(self.step_times) if self.step_times else 0
        median_latency = statistics.median(self.step_times) if self.step_times else 0

        # Extract timestamp from log folder name
        folder_name = os.path.basename(log_folder)
        timestamp = folder_name.replace('openhands_', '')  # Correctly extract timestamp

        # Count unique domains from visited URLs
        domain_counts = self.count_unique_websites()

        # Construct final metrics dict
        metrics = {
            'timestamp': timestamp,
            'agent_name': self.agent_name,
            'query': self.query,
            'folder_name': log_folder,
            'full_runtime': full_runtime,
            'start_url': None,
            'final_answer': self.final_answer,
            'shortest_time_difference': min_latency,
            'longest_time_difference': max_latency,
            'mean_time_difference': mean_latency,
            'median_time_difference': median_latency,
            'number_of_timestamps': len(self.step_times),
            'errors': self.errors,
            'input_tokens': self.input_tokens,
            'output_tokens': self.output_tokens,
            'total_tokens': total_tokens,
            'model_name': self.model_name,
            'screenshots': self.screenshots,
            'model_calls': self.model_calls,
            'num_webpage_visits': len(self.visited_urls),
            'visited_urls': self.visited_urls,
            'domain_counts': domain_counts,
        }

        # Save JSON file with naming convention
        filename = f'{timestamp}_metrics.json'
        filepath = os.path.join(log_folder, filename)
        os.makedirs(log_folder, exist_ok=True)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(metrics, f, indent=4, ensure_ascii=False)

        logger.info(f'Metrics saved to {filepath}')
        return metrics
