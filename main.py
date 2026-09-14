import json
import subprocess

with open("config.json", "r") as file:
    config = json.load(file)

def build_sync_command(folder):
    command = [
        "rclone",
        "bisync",
        folder["local_path"],
        f'{config["remote"]}:{folder["remote_path"]}',
    ]

    defaults = config["defaults"]

    if defaults["check_access"]:
        command.append("--check-access")
    
    command.extend([
        "--max-delete", str(defaults["max_delete"]),
        "--tpslimit", str(defaults["tpslimit"]),
        "--tpslimit-burst", str(defaults["tpslimit_burst"]),
        "--transfers", str(defaults["transfers"]),
        "--checkers", str(defaults["checkers"]),
    ])

    return command

def run_sync(folder):
    command = build_sync_command(folder)
    result = subprocess.run(command)
    return result.returncode

# print(f"Remote: {config['remote']}")
# print(f"Interval:{config['scheduler']['interval_minutes']} minutes")
# print()

# for folder in config["folders"]:
#     # status = "ON" if folder["enabled"] else "OFF"
#     # print(f"{folder['name']:<15} [{status}]")
#     command = build_sync_command(folder)

#     print(folder["name"])
#     print(command)
#     print()

folder = config["folders"][1]

return_code = run_sync(folder)

print(f"rclone exited with the code: {return_code}")