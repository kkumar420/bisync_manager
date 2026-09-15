from manager import (
    folders,
    get_folder,
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

    print(f"{'Folder':<15} {'Auto Sync':<12} {'State'}")
    print("-" * 50)

    for folder in folders.values():

        name = folder["name"]
        auto_sync = statuses[name]["auto_sync"]
        state = statuses[name]["state"]

        print(f"{name:<15} {auto_sync:<12} {state}")


# =========================================================
# MAIN CLI
# =========================================================

def main():

    while True:

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

        print("\nActions")
        print("11. Sync all")
        print("12. Resync a folder")
        print("13. Exit")

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

            name = input("Folder name: ").strip()

            folder = get_folder(name)

            if folder is None:
                print(f"Folder '{name}' not found.")
                continue

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

            name = input("Folder name: ").strip()

            pause(name)


        # -------------------------------------------------
        # Resume one folder
        # -------------------------------------------------

        elif choice == "7":

            name = input("Folder name: ").strip()

            resume(name)


        elif choice == "8":

            name = input("Folder name: ").strip()
            local_path = input("Local path: ").strip()
            remote_path = input("Remote path: ").strip()

            if not name or not local_path or not remote_path:
                print("All fields are required.")
                continue

            add_folder(name, local_path, remote_path)


        elif choice == "9":

            name = input("Folder name: ").strip()

            folder = get_folder(name)

            if folder is None:
                print(f"Folder '{name}' not found.")
                continue

            confirmation = input(
                f"Remove '{name}'? This will delete its generated "
                "systemd service. [y/N]: "
            ).strip().lower()

            if confirmation != "y":
                print("Removal cancelled.")
                continue

            remove_folder(name)


        elif choice == "10":

            print("Regenerating systemd setup...")

            generate_systemd_setup()

            print("Systemd setup regenerated successfully.")

        # -------------------------------------------------
        # Sync all enabled folders
        # -------------------------------------------------

        elif choice == "11":

            sync_all()


        # -------------------------------------------------
        # Exit
        # -------------------------------------------------

        elif choice == "12":

            name = input("Folder name: ").strip()

            folder = get_folder(name)

            if folder is None:
                print(f"Folder '{name}' not found.")
                continue

            print(f"Resyncing {name}...")
            print("WARNING: This will reinitialize the bisync state.")

            result = run_resync(folder)

            if result.returncode == 0:
                print(f"{name}: Resync successful")
            else:
                print(
                    f"{name}: Resync failed "
                    f"with code {result.returncode}"
        )


        elif choice == "13":

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