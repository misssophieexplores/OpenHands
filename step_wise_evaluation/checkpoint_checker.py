import glob
import json
import os
import shutil


def find_latest_log_folder(base_path):
    """
    Find the latest log folder based on timestamped names in the 'logs' directory.
    """
    log_folders = sorted(
        glob.glob(os.path.join(base_path, 'openhands_*')), reverse=True
    )
    return log_folders[0] if log_folders else None


def move_log_folder(log_folder, destination_path):
    """
    Move the log folder to the step_tasks directory and return the new folder path.
    """
    if not os.path.exists(destination_path):
        os.makedirs(destination_path)

    destination = os.path.join(destination_path, os.path.basename(log_folder))
    shutil.move(log_folder, destination)
    print(f'Moved log folder to: {destination}')
    return destination


def find_log_files(base_path):
    """
    Find the latest 'metrics.json'.
    """
    latest_folder = find_latest_log_folder(base_path)
    if not latest_folder:
        return None, None

    metrics_pattern = os.path.join(latest_folder, '*_metrics.json')
    metrics_files = glob.glob(metrics_pattern)

    return metrics_files[0] if metrics_files else None, latest_folder


def get_final_answer(metrics_path):
    """
    Load the metrics file and check the final answer.
    """
    if not metrics_path or not os.path.exists(metrics_path):
        return None, []

    with open(metrics_path, 'r', encoding='utf-8') as file:
        metrics = json.load(file)

    final_answer = metrics.get('final_answer')
    visited_urls = list(metrics.get('visited_urls', {}).keys())
    query = metrics.get('query')
    agent_name = metrics.get('agent_name', 'unknown')
    difficulty = metrics.get('difficulty', 'unknown')
    interim_memory_used, interim_memory_answer_retrieved = get_interim_memory_used(agent_name, metrics.get('visited_urls', {}))


    return final_answer, visited_urls, query, agent_name, difficulty, interim_memory_used, interim_memory_answer_retrieved

def get_interim_memory_used(agent_name, visited_urls):
    """
    Check if any interim memory actions were used.
    """
    if agent_name != 'openhands_memory_visual_browsing_agent':
        return None, None

    interim_memory_used = 0
    interim_memory_answer_retrieved = 0
    print(visited_urls)
    print(type(visited_urls))

    # Loop through the URLs and check their actions
    for data in visited_urls.values():
        actions = data["actions"]

        if "retrieve_interim_memory" in actions:
            return 1, 1  # Highest priority action found, return immediately

        if any(action in actions for action in ["store_interim_memory"]):
            interim_memory_used = 1

    return interim_memory_used, interim_memory_answer_retrieved


def load_checkpoints(checkpoints_path):
    """
    Load the hardcoded checkpoints from a JSON file.
    """
    if not os.path.exists(checkpoints_path):
        return {}

    with open(checkpoints_path, 'r', encoding='utf-8') as file:
        return json.load(file)


def find_step_id_and_checkpoints(query, steps_definition):
    """
    Find the step, id, and checkpoints for a given query.
    """
    for step, details in steps_definition.items():
        for entry in details.get('entries', []):
            if entry.get('query') == query:
                return step, entry.get('id'), entry.get('checkpoints')
    return None, None, None


def check_checkpoints(visited_urls, checkpoints):
    """
    Validate if a single URL contains all required checkpoints and calculate ratios.
    """
    provided = checkpoints.get('provided', [])
    expected = checkpoints.get('expected', [])

    # make sure to lowercase 'visited_urls'
    visited_urls = visited_urls or []  # Ensure it's at least an empty list
    visited_urls = [
        url.lower() for url in visited_urls if isinstance(url, str)
    ]  # Process only strings

    for url in reversed(visited_urls):  # Iterate from the most recent URL
        provided_count = sum(1 for part in provided if part.lower() in url)
        expected_count = sum(1 for part in expected if part.lower() in url)

        if provided_count == len(provided) and expected_count == len(expected):
            return (
                1.0,
                1.0,
                provided_count,
                expected_count,
                provided,
                expected,
                1,
            )  # Full success case

        # Compute ratios for partial fulfillment
        provided_ratio = provided_count / len(provided) if provided else 1.0
        expected_ratio = expected_count / len(expected) if expected else 1.0

        return (
            provided_ratio,
            expected_ratio,
            provided_count,
            expected_count,
            provided,
            expected,
            0,
        )  # Partial success case

    return 0.0, 0.0, 0, 0, provided, expected, 0  # No match found


def get_model_data(agent_name):
    """
    Determine model types based on agent_name.
    """
    model_data = {'text_model': 1, 'vision_model': 0, 'multi_agent': 0}

    if agent_name == 'openhands_visual_browsing_agent' or agent_name == 'openhands_memory_visual_browsing_agent':
        model_data['vision_model'] = 1
    elif agent_name == 'openhands_delegator_agent':
        model_data['vision_model'] = 1
        model_data['multi_agent'] = 1

    return model_data



# Define Paths
logs_base_path = 'logs'  # Base logs folder (general logs)
step_tasks_path = 'logs/step_tasks'  # Destination folder for processed logs
checkpoints_path = 'step_wise_evaluation/steps_definition.json'  # Update with actual checkpoint file path
checkpoints_data = load_checkpoints(checkpoints_path)

# Load metrics
metrics_path, latest_log_folder = find_log_files(logs_base_path)
print(f'Metrics File Path: {metrics_path}')

if metrics_path:
    final_answer, visited_urls, query, agent_name, difficulty, interim_memory_used, interim_memory_answer_retrieved = get_final_answer(
        metrics_path
    )

    # Find step, task_id, and checkpoints based on query
    step, query_id, checkpoints = find_step_id_and_checkpoints(query, checkpoints_data)

    if step and query_id is None:
        print('No match found.')
        # TODO: Error handling

    if step and query_id is not None:
        # initialize success to None
        success = None
        # Check if all required URLs were visited
        required_urls = checkpoints.get('urls', [])
        missing_urls = [url for url in required_urls if url not in visited_urls]
        if missing_urls:
            success = 0  # If any required URL is missing, set success to 0 immediately
        if (
            success != 0
            and (difficulty == 'step_02' or difficulty == 'step_03')
            and final_answer not in visited_urls
        ):
            (
                checkpoint_provided_ratio,
                checkpoint_expected_ratio,
                checkpoint_provided_count,
                checkpoint_expected_count,
                checkpoints_provided_list,
                checkpoints_expected_list,
                success,
            ) = check_checkpoints(visited_urls, checkpoints)
        else:
            if success != 0:  # Proceed only if all required URLs were visited
                (
                    checkpoint_provided_ratio,
                    checkpoint_expected_ratio,
                    checkpoint_provided_count,
                    checkpoint_expected_count,
                    checkpoints_provided_list,
                    checkpoints_expected_list,
                    success,
                ) = check_checkpoints([final_answer], checkpoints)
            (
                checkpoint_provided_ratio,
                checkpoint_expected_ratio,
                checkpoint_provided_count,
                checkpoint_expected_count,
                checkpoints_provided_list,
                checkpoints_expected_list,
                success,
            ) = check_checkpoints([final_answer], checkpoints)


        # Move log folder to step_tasks if step and query_id were found
        new_log_folder = move_log_folder(latest_log_folder, step_tasks_path)

        # Update metrics_path to new location
        new_metrics_path = os.path.join(new_log_folder, os.path.basename(metrics_path))

        # Get model data
        model_data = get_model_data(agent_name)


        # Write results to metrics.json
        with open(new_metrics_path, 'r', encoding='utf-8') as file:
            metrics_data = json.load(file)

        metrics_data.update(
            {
                'folder_name': new_log_folder,
                'difficulty': step,
                'task_id': query_id,
                'checkpoints': checkpoints,
                'checkpoint_provided_ratio': checkpoint_provided_ratio,
                'checkpoint_expected_ratio': checkpoint_expected_ratio,
                'success': success,
                'interim_memory_used': interim_memory_used,
                'interim_memory_answer_retrieved': interim_memory_answer_retrieved,
                **model_data,  # Add model data dynamically,
            }
        )

        with open(new_metrics_path, 'w', encoding='utf-8') as file:
            json.dump(metrics_data, file, indent=4, ensure_ascii=False)

        print('Updated metrics.json with full checkpoint and model data.')
    else:
        print('No match found. Metrics file was not updated.')
else:
    print('No metrics file found.')
