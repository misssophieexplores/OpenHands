import json
import os
import statistics
import time

from openhands.core.logger import get_experiment_folder
from openhands.core.logger import openhands_logger as logger

log_folder = get_experiment_folder()


class MetricsTracker:
    def __init__(self, model_name='web_voyager'):
        self.start_time = time.time()
        self.step_times = []
        self.input_tokens = 0
        self.output_tokens = 0
        self.model_name = model_name
        self.screenshots = 0
        self.model_calls = 0

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

        # Construct final metrics dict
        metrics = {
            'timestamp': timestamp,
            'folder_name': log_folder,
            'full_runtime': full_runtime,
            'shortest_time_difference': min_latency,
            'longest_time_difference': max_latency,
            'mean_time_difference': mean_latency,
            'median_time_difference': median_latency,
            'input_tokens': self.input_tokens,
            'output_tokens': self.output_tokens,
            'total_tokens': total_tokens,
            'model_name': self.model_name,
            'screenshots': self.screenshots,
            'model_calls': self.model_calls,
        }

        # Save JSON file with naming convention
        filename = f'{timestamp}_metrics.json'
        filepath = os.path.join(log_folder, filename)
        os.makedirs(log_folder, exist_ok=True)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(metrics, f, indent=4)

        logger.info(f'Metrics saved to {filepath}')
        return metrics
