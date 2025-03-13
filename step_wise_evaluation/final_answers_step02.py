import json
import os


def get_metrics_files(step_tasks_path):
    """
    Find all 'metrics.json' files in subfolders starting with 'step_02_'.
    """
    metrics_files = []
    for folder in os.listdir(step_tasks_path):
        if folder.startswith('step_02_'):
            for file in os.listdir(os.path.join(step_tasks_path, folder)):
                if file.endswith('_metrics.json'):
                    metrics_path = os.path.join(step_tasks_path, folder, file)
                    metrics_files.append((folder, metrics_path))
    return metrics_files


def validate_final_answers(metrics_files):
    """
    Process metrics.json files to check final answers.
    """
    total_files_checked = len(metrics_files)
    final_answer_in_urls_count = 0
    valid_final_answer_count = 0
    none_final_answer_count = 0
    error_final_answer_count = 0
    other_final_answer_count = 0
    success_count = 0

    valid_folders = []
    none_folders = []
    error_folders = []
    other_folders = []
    success_folders = []

    for folder, metrics_path in metrics_files:
        with open(metrics_path, 'r', encoding='utf-8') as file:
            metrics = json.load(file)

        final_answer = metrics.get('final_answer')
        visited_urls = list(metrics.get('visited_urls', {}).keys())
        checkpoints = metrics.get('checkpoints', {})
        success = metrics.get('success', 0)

        if success == 1:
            success_count += 1
            success_folders.append(folder)

        if final_answer is None:
            none_final_answer_count += 1
            none_folders.append(folder)
            continue

        if 'error' in str(final_answer).lower():
            error_final_answer_count += 1
            error_folders.append(folder)
            continue

        if final_answer in visited_urls:
            final_answer_in_urls_count += 1

            provided_checkpoints = checkpoints.get('provided', [])
            expected_checkpoints = checkpoints.get('expected', [])

            if all(part in final_answer for part in provided_checkpoints) and all(
                part in final_answer for part in expected_checkpoints
            ):
                valid_final_answer_count += 1
                valid_folders.append(folder)
                continue

        other_final_answer_count += 1
        other_folders.append(folder)

    valid_ratio = (
        valid_final_answer_count / total_files_checked if total_files_checked > 0 else 0
    )
    none_ratio = (
        none_final_answer_count / total_files_checked if total_files_checked > 0 else 0
    )
    error_ratio = (
        error_final_answer_count / total_files_checked if total_files_checked > 0 else 0
    )
    other_ratio = (
        other_final_answer_count / total_files_checked if total_files_checked > 0 else 0
    )
    success_ratio = (
        success_count / total_files_checked if total_files_checked > 0 else 0
    )

    print(f'Total files checked: {total_files_checked}')
    print(f'Final answers in visited URLs: {final_answer_in_urls_count}')
    print(
        f'Valid final answers (containing all checkpoints): {valid_final_answer_count}'
    )
    print(f'Ratio of valid final answers: {valid_ratio:.2f}')
    print(f'Ratio of None final answers: {none_ratio:.2f}')
    print(f"Ratio of 'error' in final answers: {error_ratio:.2f}")
    print(f'Ratio of other final answers: {other_ratio:.2f}')
    print(f"Ratio of 'success' being 1: {success_ratio:.2f}")

    print('\nValid folders:', valid_folders)
    print('None final answer folders:', none_folders)
    print('Error final answer folders:', error_folders)
    print('Other final answer folders:', other_folders)
    print('Success folders:', success_folders)


step_tasks_path = 'logs/step_tasks'  # Base path for step tasks
metrics_files = get_metrics_files(step_tasks_path)
validate_final_answers(metrics_files)
