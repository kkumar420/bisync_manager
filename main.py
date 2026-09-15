import json
import subprocess

with open("config.json", "r") as file:
    config = json.load(file)

folders = {
    folder["name"]: folder
    for folder in config["folders"]
}

def save_config():
    with open("config.json", "w") as file:
        json.dump(config, file, indent=4)

def generate_dispatcher():
    dispatcher_path = "/home/kkumar420/.local/bin/rclone-bisync-all.sh"

    with open(dispatcher_path, "w") as file:
        file.write("#!/bin/bash\n\n")

        for folder in folders.values():

            if not folder["enabled"]:
                continue

            file.write(
                f"systemctl --user start --wait "
                f"{folder['service']} || true\n"
            )

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
    return subprocess.run(command)

def get_folder(name):
    return folders.get(name)

def pause(name):
    folder = get_folder(name)

    if folder is None:
        print(f"Folder '{name}' not found")
        return

    if not folder["enabled"]:
        print(f"{name} is already paused")
        return

    folder["enabled"] = False
    save_config()
    generate_dispatcher()
    print(f"{name} paused.")

def resume(name):
    folder = get_folder(name)

    if folder is None:
        print(f"Folder '{name}' not found")
        return

    if folder["enabled"]:
        print(f"{name} is already active")
        return

    folder["enabled"] = True
    save_config()
    generate_dispatcher()
    print(f"{name} resumed")

def sync_all():
    for folder in folders.values():
        if not folder["enabled"]:
            continue

        print(f"Syncing {folder['name']}...")

        result = run_sync(folder)

        if result.returncode == 0:
            print(f"{folder['name']}: Sync successful")
        else:
            print(f"{folder['name']}: Sync failed with code {result.returncode}")


pause("My_Library")
pause("BITS_Goa")