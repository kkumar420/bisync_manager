import json
import os
import subprocess
import tempfile


# =========================================================
# CONFIGURATION
# =========================================================

# config.json is the single source of truth for our setup.
with open("config.json", "r") as file:
    config = json.load(file)


# Paths used by our generated systemd configuration.
#
# os.path.expanduser("~") makes these paths work for the
# current user instead of hard-coding a username.
SYSTEMD_USER_DIR = os.path.expanduser(
    "~/.config/systemd/user"
)

LOCAL_BIN_DIR = os.path.expanduser(
    "~/.local/bin"
)


# Create a dictionary for fast folder lookup.
#
# Instead of searching through config["folders"] every time,
# we can directly do:
#
#     folders["Vaikunth"]
#
# The folder dictionaries stored here are the same objects
# contained inside config["folders"].
folders = {
    folder["name"]: folder
    for folder in config["folders"]
}


# =========================================================
# FILE / CONFIGURATION HELPERS
# =========================================================

def save_config():
    """
    Save the current configuration back to config.json.
    """

    with open("config.json", "w") as file:
        json.dump(config, file, indent=4)


def write_generated_file(path, contents):
    """
    Safely write a generated file.

    The new contents are first written completely to a
    temporary file in the same directory. Once writing has
    succeeded, the temporary file replaces the old file.

    This avoids leaving an important generated file half-
    written if the program crashes during the write.
    """

    directory = os.path.dirname(path)
    
    # Make sure the destination directory exists.
    os.makedirs(directory, exist_ok=True)

    # Create the temporary file in the same directory as the
    # destination so the final replacement can happen on the
    # same filesystem.
    with tempfile.NamedTemporaryFile(
        mode="w",
        dir=directory,
        delete=False
    ) as temp_file:

        temp_file.write(contents)
        temp_path = temp_file.name

    # Replace the old file with the fully written file.
    os.replace(temp_path, path)


# =========================================================
# SYSTEMD HELPERS
# =========================================================

def daemon_reload():
    """
    Tell the systemd user manager to reread its unit files.
    """

    result = subprocess.run([
        "systemctl",
        "--user",
        "daemon-reload",
    ])

    if result.returncode != 0:
        print("Failed to reload systemd.")

    return result


# =========================================================
# RCLONE COMMAND BUILDING
# =========================================================

def build_sync_command(folder):
    """
    Build the normal rclone bisync command for one folder.

    The command is returned as a list of arguments rather
    than a single shell string. This allows subprocess to pass
    paths containing spaces safely as individual arguments.

    This function builds the NORMAL sync command only.
    --resync is handled separately.
    """

    command = [
        "/usr/bin/rclone",
        "bisync",
        folder["local_path"],
        f'{config["remote"]}:{folder["remote_path"]}',
    ]

    defaults = config["defaults"]

    # Add --check-access only when enabled in the configuration.
    if defaults["check_access"]:
        command.append("--check-access")

    # Add the remaining rclone options.
    command.extend([
        "--max-delete", str(defaults["max_delete"]),
        "--tpslimit", str(defaults["tpslimit"]),
        "--tpslimit-burst", str(defaults["tpslimit_burst"]),
        "--transfers", str(defaults["transfers"]),
        "--checkers", str(defaults["checkers"]),
    ])

    return command


def build_resync_command(folder):
    """
    Build the rclone bisync command used for a manual resync.

    This starts with the normal bisync command and adds
    --resync for one-time recovery.

    This command is only used by the manual resync operation.
    Normal scheduled syncing continues to use
    build_sync_command().
    """

    command = build_sync_command(folder)

    command.append("--resync")

    return command


def escape_systemd_argument(argument):
    """
    Convert one command argument into systemd ExecStart syntax.

    Systemd has its own parsing rules for ExecStart= lines,
    so a Python argument list cannot simply be joined together.

    We wrap each argument in double quotes and escape special
    characters that have meaning inside systemd command lines.
    """

    argument = argument.replace("\\", "\\\\")
    argument = argument.replace('"', '\\"')
    argument = argument.replace("%", "%%")
    argument = argument.replace("$", "$$")

    return f'"{argument}"'


# =========================================================
# FOLDER LOOKUP / EXECUTION
# =========================================================

def get_folder(name):
    """
    Return a folder configuration by name.

    Returns None if the folder does not exist.
    """

    return folders.get(name)


def generate_service_name(name):
    """
    Generate the systemd service filename from a folder name.

    Example:

        "My Library"
            ->
        "rclone-my-library-bisync.service"
    """

    service_name = name.lower().replace(" ", "-")

    return f"rclone-{service_name}-bisync.service"


def run_sync(folder):
    """
    Run a folder's existing systemd service and wait for it
    to finish.

    Python does not invoke rclone directly here. Systemd
    remains responsible for actually executing the folder
    service.
    """

    command = [
        "systemctl",
        "--user",
        "start",
        "--wait",
        folder["service"],
    ]

    return subprocess.run(command)


def run_resync(folder):
    """
    Run a one-time resync through a temporary systemd service.

    The temporary service is always removed after the resync,
    whether the resync succeeds or fails.
    """

    service_name, service_path = generate_resync_service(folder)

    try:
        # Tell systemd about the newly generated service.
        daemon_reload()

        # Run the temporary service and wait for it to finish.
        result = subprocess.run([
            "systemctl",
            "--user",
            "start",
            "--wait",
            service_name,
        ])

        return result

    finally:
        # Remove the temporary service file.
        if os.path.exists(service_path):
            os.remove(service_path)

        # Tell systemd that the temporary unit file is gone.
        daemon_reload()


def sync_all():
    """
    Run all folders that are currently enabled.

    Each folder is executed sequentially because run_sync()
    uses systemctl start --wait.
    """

    for folder in folders.values():

        # Disabled folders are excluded from automatic syncing.
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


# =========================================================
# FOLDER PAUSE / RESUME
# =========================================================

def pause(name):
    """
    Pause automatic syncing for one folder.

    The individual systemd service remains intact. We simply
    mark the folder as disabled and regenerate the dispatcher
    so future automatic cycles skip it.
    """

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
    """
    Resume automatic syncing for one folder.

    The folder is marked enabled and the dispatcher is
    regenerated so future automatic cycles include it again.
    """

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


def add_folder(name, local_path, remote_path):
    """
    Add a new folder and initialize its bisync state.

    The folder is initially disabled so that it cannot enter
    a normal automatic sync before its first --resync succeeds.

    If the resync succeeds, the folder is enabled and added
    to the automatic dispatcher.

    If the resync fails, the folder remains in the configuration
    but stays disabled so it can be fixed and retried later.
    """

    # Prevent duplicate folder names.
    if get_folder(name) is not None:
        print(f"Folder '{name}' already exists.")
        return False

    # Validate the folder name.
    if not name:
        print("Folder name cannot be empty.")
        return False

    # The local directory must already exist.
    if not os.path.isdir(local_path):
        print(f"Local path does not exist: {local_path}")
        return False

    # The remote path cannot be empty.
    if not remote_path:
        print("Remote path cannot be empty.")
        return False

    service_name = generate_service_name(name)

    folder = {
        "name": name,
        "local_path": local_path,
        "remote_path": remote_path,
        "service": service_name,

        # Do NOT enable the folder yet.
        #
        # It must first complete its initial --resync.
        "enabled": False,
    }

    # Add the folder to the configuration.
    config["folders"].append(folder)

    # Add the same folder to the lookup dictionary.
    folders[name] = folder

    # Save the folder immediately so that it exists in
    # config.json even if the initial resync fails.
    save_config()

    # Generate its normal permanent service.
    generate_service(folder)

    # Tell systemd about the new service.
    daemon_reload()

    print(f"\n{name} added.")
    print("Initializing bisync state...")

    # Perform the required initial resync.
    result = run_resync(folder)

    if result.returncode != 0:

        print(
            f"\nInitial resync for {name} failed."
        )
        print(
            "The folder was added but remains disabled."
        )
        print(
            "Fix the problem and run resync manually."
        )

        return False

    # Initial resync succeeded, so the folder is now safe
    # to include in normal automatic syncing.
    folder["enabled"] = True

    save_config()

    # Regenerate the dispatcher so the newly initialized
    # folder is now included.
    generate_dispatcher()

    print(f"\n{name} initialized successfully.")
    print("Automatic syncing enabled.")

    return True


def remove_folder(name):
    """
    Remove a folder from the configuration and generated
    systemd setup.

    The folder's generated systemd service is deleted, while
    the remaining services and dispatcher are left intact.
    """

    folder = get_folder(name)

    if folder is None:
        print(f"Folder '{name}' not found.")
        return False

    # Do not allow a folder to be removed while its sync
    # service is currently running.
    status = get_service_status(folder["service"])

    if status is not None and status["active_state"] == "active":
        print(f"{name} is currently syncing. Stop it before removing.")
        return False

    # Remove the folder from the configuration list.
    config["folders"].remove(folder)

    # Remove the folder from the lookup dictionary.
    del folders[name]

    # Save the updated configuration.
    save_config()

    # Remove the generated systemd service.
    service_path = os.path.join(
        SYSTEMD_USER_DIR,
        folder["service"]
    )

    if os.path.exists(service_path):
        os.remove(service_path)

    # Regenerate the dispatcher so the removed folder is no
    # longer included in automatic sync cycles.
    generate_dispatcher()

    # Tell systemd that the service file has been removed.
    daemon_reload()

    print(f"{name} removed successfully.")

    return True


# =========================================================
# DISPATCHER GENERATION
# =========================================================

def generate_dispatcher():
    """
    Generate the master Bash dispatcher script.

    Only folders whose `enabled` value is True are included.

    The dispatcher starts each folder's systemd service with
    --wait, keeping the execution sequential. || true ensures
    that a failed folder does not prevent subsequent folders
    from running.
    """

    dispatcher_path = os.path.join(
        LOCAL_BIN_DIR,
        "rclone-bisync-all.sh"
    )

    contents = """#!/bin/bash

# THIS FILE IS MANAGED BY BISYNC MANAGER.
# Do not edit manually.

"""

    for folder in folders.values():

        if not folder["enabled"]:
            continue

        contents += (
            f"systemctl --user start --wait "
            f"{folder['service']} || true\n"
        )

    # Safely replace the existing dispatcher.
    write_generated_file(dispatcher_path, contents)

    # The file needs execute permission because systemd will
    # execute it as a script.
    os.chmod(dispatcher_path, 0o755)


# =========================================================
# INDIVIDUAL SERVICE GENERATION
# =========================================================

def generate_service(folder):
    """
    Generate the systemd service unit for one folder.
    """

    service_path = os.path.join(
        SYSTEMD_USER_DIR,
        folder["service"]
    )

    command = build_sync_command(folder)

    # Convert the Python argument list into systemd's
    # ExecStart syntax.
    exec_start = " ".join(
        escape_systemd_argument(argument)
        for argument in command
    )

    service_contents = f"""# THIS FILE IS MANAGED BY BISYNC MANAGER.
# Do not edit manually. Changes will be overwritten.

[Unit]
Description=Bisync {folder["name"]} with Google Drive

[Service]
Type=oneshot
ExecStart={exec_start}
"""

    write_generated_file(service_path, service_contents)


def generate_resync_service(folder):
    """
    Generate a temporary systemd service for a one-time resync.

    The service is separate from the normal folder service so
    the permanent service remains unchanged.
    """

    service_name = (
        folder["service"]
        .replace(".service", "")
        + "-resync.service"
    )

    service_path = os.path.join(
        SYSTEMD_USER_DIR,
        service_name
    )

    command = build_resync_command(folder)

    exec_start = " ".join(
        escape_systemd_argument(argument)
        for argument in command
    )

    service_contents = f"""# TEMPORARY RESYNC SERVICE.
# Generated by Bisync Manager.

[Unit]
Description=Resync {folder["name"]} with Google Drive

[Service]
Type=oneshot
ExecStart={exec_start}
"""

    write_generated_file(service_path, service_contents)

    return service_name, service_path


def generate_all_services():
    """
    Generate the systemd service file for every configured
    folder.
    """

    for folder in folders.values():
        generate_service(folder)


# =========================================================
# MASTER SYSTEMD SERVICE
# =========================================================

def generate_master_service():
    """
    Generate the systemd service that executes the dispatcher.
    """

    service_path = os.path.join(
        SYSTEMD_USER_DIR,
        "rclone-bisync-all.service"
    )

    service_contents = """# THIS FILE IS MANAGED BY BISYNC MANAGER.
# Do not edit manually. Changes will be overwritten.

[Unit]
Description=Run all rclone bisync jobs

[Service]
Type=oneshot
ExecStart=%h/.local/bin/rclone-bisync-all.sh
"""

    write_generated_file(service_path, service_contents)


# =========================================================
# TIMER GENERATION
# =========================================================

def generate_timer():
    """
    Generate the systemd timer responsible for scheduling
    automatic sync cycles.

    The interval is measured from the completion of the
    master service, so sync cycles do not overlap.
    """

    timer_path = os.path.join(
        SYSTEMD_USER_DIR,
        "rclone-bisync-all.timer"
    )

    interval = config["scheduler"]["interval_minutes"]

    timer_contents = f"""# THIS FILE IS MANAGED BY BISYNC MANAGER.
# Do not edit manually. Changes will be overwritten.

[Unit]
Description=Run all rclone bisync jobs

[Timer]
OnUnitInactiveSec={interval}min
Persistent=true

[Install]
WantedBy=timers.target
"""

    write_generated_file(timer_path, timer_contents)


# =========================================================
# SCHEDULER CONTROL
# =========================================================

def sync_scheduler_state():
    """
    Make the actual systemd timer state match config.json.

    This function starts/stops the timer only. It does not
    manually trigger a sync.
    """

    timer = "rclone-bisync-all.timer"

    if config["scheduler"]["enabled"]:

        subprocess.run([
            "systemctl",
            "--user",
            "enable",
            "--now",
            timer,
        ])

    else:

        subprocess.run([
            "systemctl",
            "--user",
            "disable",
            "--now",
            timer,
        ])


def pause_scheduler():
    """
    Pause global automatic syncing.

    Only the timer is stopped. A cycle that is already running
    is not deliberately interrupted.
    """

    scheduler = config["scheduler"]

    if not scheduler["enabled"]:
        print("Automatic syncing is already paused.")
        return

    result = subprocess.run([
        "systemctl",
        "--user",
        "stop",
        "rclone-bisync-all.timer",
    ])

    if result.returncode != 0:
        print("Failed to pause automatic syncing.")
        return

    scheduler["enabled"] = False

    save_config()

    print("Automatic syncing paused.")


def resume_scheduler():
    """
    Resume global automatic syncing.

    The timer is started first, then the master service is
    triggered immediately for the first sync cycle.
    """

    scheduler = config["scheduler"]

    if scheduler["enabled"]:
        print("Automatic syncing is already active.")
        return

    result = subprocess.run([
        "systemctl",
        "--user",
        "start",
        "rclone-bisync-all.timer",
    ])

    if result.returncode != 0:
        print("Failed to resume automatic syncing.")
        return

    scheduler["enabled"] = True
    save_config()

    # Run the first sync immediately.
    subprocess.run([
        "systemctl",
        "--user",
        "start",
        "--no-block",
        "rclone-bisync-all.service",
    ])

    print("Automatic syncing resumed.")


def set_scheduler_interval(minutes):
    """
    Change the interval between completed sync cycles.

    The timer is regenerated from the new configuration.
    If the scheduler is active, its timer is restarted so the
    new timer definition takes effect.

    Restarting the TIMER does not restart the currently running
    master service or rclone process.
    """

    if minutes <= 0:
        print("Interval must be greater than 0 minutes.")
        return

    config["scheduler"]["interval_minutes"] = minutes

    save_config()

    generate_timer()
    daemon_reload()

    # Only restart the timer if automatic syncing is currently
    # enabled. We never restart the master service here.
    if config["scheduler"]["enabled"]:

        subprocess.run([
            "systemctl",
            "--user",
            "restart",
            "rclone-bisync-all.timer",
        ])

    print(f"Scheduler interval set to {minutes} minutes.")


def get_scheduler_status():
    """
    Return whether global automatic syncing is enabled.
    """

    return config["scheduler"]["enabled"]


def get_scheduler_interval():
    """
    Return the configured scheduler interval in minutes.
    """

    return config["scheduler"]["interval_minutes"]


# =========================================================
# COMPLETE SYSTEMD SETUP GENERATION
# =========================================================

def generate_systemd_setup():
    """
    Regenerate the complete systemd configuration from
    config.json.

    This includes:
        - individual folder services
        - dispatcher
        - master service
        - timer

    After all files have been generated, systemd is reloaded
    once so it sees the new definitions.

    Finally, the timer is made consistent with config.json.
    """

    generate_all_services()
    generate_dispatcher()
    generate_master_service()
    generate_timer()

    # All unit files have now been generated, so reload systemd once.
    daemon_reload()

    # Make the timer's enabled/running state match config.json.
    # This does NOT trigger an immediate sync.
    sync_scheduler_state()


# =========================================================
# STATUS
# =========================================================

def get_service_status(service):
    """
    Return information about a systemd service.

    ActiveState tells us what the service is doing right now.

    Result tells us how the most recent execution ended.
    """

    result = subprocess.run(
        [
            "systemctl",
            "--user",
            "show",
            service,
            "--property=ActiveState",
            "--property=Result",
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return None

    status = {}

    for line in result.stdout.splitlines():
        key, value = line.split("=", 1)
        status[key] = value

    return {
        "active_state": status.get("ActiveState"),
        "result": status.get("Result"),
    }


def get_folder_state(folder):
    """
    Return the execution state of a folder's service.

    SYNCING -> rclone is running right now.
    SUCCESS -> the most recent run completed successfully.
    FAILED  -> the service's most recent run failed.
    UNKNOWN -> the state could not be determined.
    """

    status = get_service_status(folder["service"])

    if status is None:
        return "UNKNOWN"

    if status["active_state"] == "active":
        return "SYNCING"

    if (
        status["active_state"] == "inactive"
        and status["result"] == "success"
    ):
        return "SUCCESS"

    if status["active_state"] == "failed":
        return "FAILED"

    return "UNKNOWN"


def get_folder_auto_sync_status(folder):
    """
    Return whether automatic syncing is enabled for this folder.

    This answers:

        "Will the automatic dispatcher include this folder?"
    """

    if folder["enabled"]:
        return "ENABLED"

    return "PAUSED"


def get_folder_status(folder):
    """
    Return both kinds of status for a folder.

    The result is a dictionary so that the caller can clearly
    distinguish configuration state from execution state.

    Example:

        {
            "auto_sync": "ENABLED",
            "state": "SUCCESS"
        }
    """

    return {
        "auto_sync": get_folder_auto_sync_status(folder),
        "state": get_folder_state(folder),
    }


def get_overall_status():
    """
    Return the status of every configured folder.

    The folder name is used as the key.

    Example:

        {
            "Vaikunth": {
                "auto_sync": "ENABLED",
                "state": "SUCCESS"
            },

            "My_Library": {
                "auto_sync": "PAUSED",
                "state": "SUCCESS"
            }
        }
    """

    return {
        folder["name"]: get_folder_status(folder)
        for folder in folders.values()
    }