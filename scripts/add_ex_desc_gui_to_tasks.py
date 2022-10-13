"""
Adds a call to the experiment description GUI to select tasks
"""
import os
from pathlib import Path
from sys import platform
import json

# Add any custom tasks to this list
TASK_LIST = ['_iblrig_tasks_biasedChoiceWorld',
             '_iblrig_tasks_trainingChoiceWorld',
             '_iblrig_tasks_passiveChoiceWorld',
             '_iblrig_tasks_ephysChoiceWorld',
             '_iblrig_tasks_passiveChoiceWorldIndependent',
             '_iblrig_tasks_habituationChoiceWorld']

TASKS_PATH = ""  # Set path for platform
if platform == "win32":
    TASKS_PATH = Path("C:\\iblrig_params\\IBL\\tasks")
else:
    TASKS_PATH = Path.home() / "Documents" / "iblrig_params" / "IBL" / "tasks"

# Command to prepend to each task in the TASK_LIST
PYTHON_CMD = "python C:\\iblscripts\\deploy\\project_procedure_gui\\experiment_form.py"


if __name__ == "__main__":
    dirs = [Path(f) for f in os.scandir(TASKS_PATH) if f.is_dir()] if Path(TASKS_PATH).exists() else None
    for dir in dirs:
        if dir.parts[-1] in TASK_LIST:
            # set path to json file
            json_file_path = dir / (dir.name + ".json")

            # open file and create dict from json
            f = open(json_file_path)
            data = json.load(f)
            f.close()

            # check if there are no commands in the json file; add PYTHON_CMD
            json_write_needed = False
            if not data["commands"]:
                data["commands"] = [{
                    "cmd": PYTHON_CMD,
                    "type": "create_execcmd",
                    "when": 0
                }]
                json_write_needed = True
            else:
                # check command list PYTHON_CMD, insert if missing
                insert_needed = True
                for cmds in data["commands"]:
                    if PYTHON_CMD in cmds["cmd"]:
                        insert_needed = False
                        break
                if insert_needed:
                    data["commands"].insert(0, {
                        "cmd": PYTHON_CMD,
                        "type": "create_execcmd",
                        "when": 0})
                    json_write_needed = True

            # write formatted data back to json file
            if json_write_needed:
                formatted_data = json.dumps(data, indent=4)
                with open(json_file_path, "w") as f:
                    f.write(formatted_data)
