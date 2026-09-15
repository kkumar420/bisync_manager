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
    command = [
        "systemctl",
        "--user",
        "start",
        "--wait",
        folder["service"],
    ]

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
            print(
                f"{folder['name']}: Sync failed "
                f"with code {result.returncode}"
            )

def pause_scheduler():
    # Get the current scheduler state from our configuration.
    scheduler = config["scheduler"]

    # If it is already disabled, there is nothing to do.
    if not scheduler["enabled"]:
        print("Automatic syncing is already paused.")
        return

    # Stop the timer.
    #
    # This stops FUTURE automatic cycles.
    # It does not deliberately kill a bisync operation that is
    # already running.
    result = subprocess.run([
        "systemctl",
        "--user",
        "stop",
        "rclone-bisync-all.timer",
    ])

    # Only change our configuration if systemd successfully
    # stopped the timer.
    if result.returncode != 0:
        print("Failed to pause automatic syncing.")
        return

    scheduler["enabled"] = False

    save_config()

    print("Automatic syncing paused.")


def resume_scheduler():
    scheduler = config["scheduler"]

    # If it is already enabled, don't start it again unnecessarily.
    if scheduler["enabled"]:
        print("Automatic syncing is already active.")
        return

    # Start the timer.
    result = subprocess.run([
        "systemctl",
        "--user",
        "start",
        "rclone-bisync-all.timer",
    ])

    # Only update our config if systemd successfully started it.
    if result.returncode != 0:
        print("Failed to resume automatic syncing.")
        return

    scheduler["enabled"] = True

    save_config()

    print("Automatic syncing resumed.")


def set_scheduler_interval(minutes):
    # Basic validation so we don't accidentally create a
    # nonsensical timer such as 0 or -5 minutes.
    if minutes <= 0:
        print("Interval must be greater than 0 minutes.")
        return

    scheduler = config["scheduler"]

    # Update our source of truth first.
    scheduler["interval_minutes"] = minutes

    save_config()

    # For now, while we have not yet built our proper systemd
    # unit generator, we update the existing timer file directly.
    timer_path = "/home/kkumar420/.config/systemd/user/rclone-bisync-all.timer"

    with open(timer_path, "w") as file:
        file.write("""[Unit]
Description=Run all rclone bisync jobs

[Timer]
OnBootSec=2min
""")

        file.write(
            f"OnUnitInactiveSec={minutes}min\n"
        )

        file.write("""Persistent=true

[Install]
WantedBy=timers.target
""")

    # Tell systemd that the timer unit file has changed.
    subprocess.run([
        "systemctl",
        "--user",
        "daemon-reload",
    ])

    # If automatic syncing is currently active, restart the timer
    # so the new interval takes effect immediately.
    if scheduler["enabled"]:

        subprocess.run([
            "systemctl",
            "--user",
            "restart",
            "rclone-bisync-all.timer",
        ])

    print(f"Scheduler interval set to {minutes} minutes.")

def get_scheduler_status():
    return config["scheduler"]["enabled"]


def get_scheduler_interval():
    return config["scheduler"]["interval_minutes"]