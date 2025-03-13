import json
import os
import shutil


def process_folders(base_path):
    for folder in os.listdir(base_path):
        folder_path = os.path.join(base_path, folder)

        # Check if it's a directory and starts with "openhands_"
        if os.path.isdir(folder_path) and folder.startswith('openhands_'):
            metrics_file = os.path.join(
                folder_path, f"{folder.split('_', 1)[1]}_metrics.json"
            )

            if os.path.exists(metrics_file):
                with open(
                    metrics_file,
                    'r',
                    encoding='utf-8',
                ) as f:
                    data = json.load(f)

                # Get the difficulty value
                difficulty = data.get('difficulty', '').strip()

                if difficulty:
                    new_folder_name = f'{difficulty}_{folder}'
                    new_folder_path = os.path.join(base_path, new_folder_name)

                    # Update the folder_name in the metrics file
                    data['folder_name'] = os.path.join(
                        'logs', base_path, new_folder_name
                    )

                    # Write changes to metrics.json before renaming the folder
                    with open(metrics_file, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=4, ensure_ascii=False)

                    # Rename the folder
                    shutil.move(folder_path, new_folder_path)
                    print(f'Renamed {folder} -> {new_folder_name}')
                else:
                    print(f'Skipping {folder}, difficulty not found in metrics file.')
            else:
                print(f'Skipping {folder}, metrics file not found.')


# Set the base directory where 'step_tasks' is located
base_directory = 'logs/step_tasks'
process_folders(base_directory)
