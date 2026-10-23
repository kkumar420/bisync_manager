from manager import (
    folders,
    get_overall_status,
    get_scheduler_status,
    get_scheduler_interval,
    pause,
    resume,
    run_sync,
    run_resync,
    sync_all,
    pause_scheduler,
    resume_scheduler,
    set_scheduler_interval,
    add_folder,
    remove_folder,
    generate_systemd_setup,
    reconnect_google_drive,
    show_service_logs,
)


# =========================================================
# DISPLAY
# =========================================================

def show_status():
    """
    Display the global scheduler status and the status of
    every configured folder.
    """

    print("\nGoogle Drive Bisync Manager")
    print("===========================")

    # -----------------------------------------------------
    # Global scheduler status
    # -----------------------------------------------------

    if get_scheduler_status():
        scheduler_status = "ACTIVE"
    else:
        scheduler_status = "PAUSED"

    print(f"\nAutomatic Sync: {scheduler_status}")
    print(f"Interval: {get_scheduler_interval()} minutes")

    # -----------------------------------------------------
    # Folder status
    # -----------------------------------------------------

    print("\nFolders")
    print("-" * 50)

    statuses = get_overall_status()

    print(
        f"{'Folder':<15} "
        f"{'Auto Sync':<12} "
        f"{'State'}"
    )

    print("-" * 50)

    for folder in folders.values():

        name = folder["name"]
        auto_sync = statuses[name]["auto_sync"]
        state = statuses[name]["state"]

        print(
            f"{name:<15} "
            f"{auto_sync:<12} "
            f"{state}"
        )


def prompt_log_line_count():
    """Ask how many recent journal entries to display (default: 100)."""

    while True:

        value = input(
            "Number of log entries to display [100]: "
        ).strip()

        # An empty input uses the default value.
        if not value:
            return 100

        try:
            lines = int(value)
        except ValueError:
            print("Please enter a valid positive integer.")
            continue

        if lines <= 0:
            print("Please enter a number greater than zero.")
            continue

        return lines


def select_folder(show_service=False):
    """Display configured folders as a numbered list and return the selection."""

    folder_list = list(folders.values())

    if not folder_list:
        print("No folders are configured.")
        return None

    print("\nConfigured folders")

    for index, folder in enumerate(folder_list, start=1):
        label = folder["name"]

        if show_service:
            label += f" ({folder['service']})"

        print(f"{index}. {label}")

    print("0. Cancel")

    choice = input("\nChoose a folder number: ").strip()

    try:
        folder_index = int(choice)
    except ValueError:
        print("Please enter a valid number.")
        return None

    if folder_index == 0:
        print("Cancelled.")
        return None

    if folder_index < 1 or folder_index > len(folder_list):
        print("Invalid folder number.")
        return None

    return folder_list[folder_index - 1]


def inspect_system_logs():
    """Let the user inspect the master or an individual folder service log."""

    while True:

        print("\nSystem Logs")
        print("-----------")
        print("1. Master service (rclone-bisync-all.service)")
        print("2. Individual folder service")
        print("3. Back to main menu")

        choice = input("\nChoose an option: ").strip()

        if choice == "1":

            lines = prompt_log_line_count()
            show_service_logs("rclone-bisync-all.service", lines=lines)

        elif choice == "2":

            folder = select_folder(show_service=True)

            if folder is None:
                continue

            lines = prompt_log_line_count()
            show_service_logs(folder["service"], lines=lines)

        elif choice == "3":

            break

        else:

            print("Invalid option. Please choose a number from the menu.")


# =========================================================
# MAIN CLI
# =========================================================

def main():

    while True:

        print("\nGoogle Drive Bisync Manager")
        print("===========================")

        print("\nGlobal")
        print("1. Show status")
        print("2. Pause automatic syncing")
        print("3. Resume automatic syncing")
        print("4. Change sync interval")

        print("\nFolders")
        print("5. Sync a folder")
        print("6. Pause a folder")
        print("7. Resume a folder")
        print("8. Add a folder")
        print("9. Remove a folder")

        print("\nSystem")
        print("10. Regenerate systemd setup")
        print("11. Refresh Google Drive token")
        print("12. Inspect system logs")

        print("\nActions")
        print("13. Sync all")
        print("14. Resync a folder")
        print("15. Exit")

        choice = input("\nChoose an option: ").strip()

        # -------------------------------------------------
        # Show complete status
        # -------------------------------------------------

        if choice == "1":

            show_status()

        # -------------------------------------------------
        # Pause automatic syncing
        # -------------------------------------------------

        elif choice == "2":

            pause_scheduler()

        # -------------------------------------------------
        # Resume automatic syncing
        # -------------------------------------------------

        elif choice == "3":

            resume_scheduler()

        # -------------------------------------------------
        # Change scheduler interval
        # -------------------------------------------------

        elif choice == "4":

            try:

                minutes = int(
                    input("Enter interval in minutes: ").strip()
                )

                set_scheduler_interval(minutes)

            except ValueError:

                print("Please enter a valid number.")

        # -------------------------------------------------
        # Sync one folder
        # -------------------------------------------------

        elif choice == "5":

            folder = select_folder()

            if folder is None:
                continue

            name = folder["name"]

            print(f"Syncing {name}...")

            result = run_sync(folder)

            if result.returncode == 0:

                print(f"{name}: Sync successful")

            else:

                print(
                    f"{name}: Sync failed "
                    f"with code {result.returncode}"
                )

        # -------------------------------------------------
        # Pause one folder
        # -------------------------------------------------

        elif choice == "6":

            folder = select_folder()

            if folder is None:
                continue

            pause(folder["name"])

        # -------------------------------------------------
        # Resume one folder
        # -------------------------------------------------

        elif choice == "7":

            folder = select_folder()

            if folder is None:
                continue

            resume(folder["name"])

        # -------------------------------------------------
        # Add a folder
        # -------------------------------------------------

        elif choice == "8":

            name = input("Folder name: ").strip()
            local_path = input("Local path: ").strip()
            remote_path = input("Remote path: ").strip()

            if not name or not local_path or not remote_path:
                print("All fields are required.")
                continue

            print(
                "\nBefore adding this folder, make sure the RCLONE_TEST "
                "marker exists on both sides:"
            )

            print(
                f"  Local:  {local_path}/RCLONE_TEST"
            )

            print(
                f"  Remote: {remote_path}/RCLONE_TEST"
            )

            print(
                "\nThe initial resync will use --resync and --check-access."
            )

            confirmation = input(
                "\nContinue? [y/N]: "
            ).strip().lower()

            if confirmation != "y":
                print("Add cancelled.")
                continue

            add_folder(
                name,
                local_path,
                remote_path
            )

        # -------------------------------------------------
        # Remove a folder
        # -------------------------------------------------

        elif choice == "9":

            folder = select_folder()

            if folder is None:
                continue

            name = folder["name"]

            confirmation = input(
                f"Remove '{name}'? This will delete its generated "
                "systemd service. [y/N]: "
            ).strip().lower()

            if confirmation != "y":
                print("Removal cancelled.")
                continue

            remove_folder(name)

        # -------------------------------------------------
        # Regenerate systemd setup
        # -------------------------------------------------

        elif choice == "10":

            print("Regenerating systemd setup...")

            generate_systemd_setup()

            print("Systemd setup regenerated successfully.")

        # -------------------------------------------------
        # Refresh Google Drive OAuth token
        # -------------------------------------------------

        elif choice == "11":

            reconnect_google_drive()

        # -------------------------------------------------
        # Inspect systemd journal logs
        # -------------------------------------------------

        elif choice == "12":

            inspect_system_logs()

        # -------------------------------------------------
        # Sync all enabled folders
        # -------------------------------------------------

        elif choice == "13":

            sync_all()

        # -------------------------------------------------
        # Resync one folder
        # -------------------------------------------------

        elif choice == "14":

            folder = select_folder()

            if folder is None:
                continue

            name = folder["name"]

            print(f"Resyncing {name}...")
            print(
                "WARNING: This will reinitialize the bisync state."
            )

            result = run_resync(folder)

            if result.returncode == 0:

                print(f"{name}: Resync successful")

            else:

                print(
                    f"{name}: Resync failed "
                    f"with code {result.returncode}"
                )

        # -------------------------------------------------
        # Exit
        # -------------------------------------------------

        elif choice == "15":

            print("Goodbye.")
            break

        # -------------------------------------------------
        # Invalid option
        # -------------------------------------------------

        else:

            print(
                "Invalid option. Please choose a number "
                "from the menu."
            )


# =========================================================
# PROGRAM ENTRY POINT
# =========================================================

if __name__ == "__main__":
    main()
