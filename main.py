from manager import (
    folders,
    get_folder,
    get_scheduler_status,
    get_scheduler_interval,
    pause,
    resume,
    run_sync,
    sync_all,
    pause_scheduler,
    resume_scheduler,
    set_scheduler_interval,
)


def show_folders():
    """
    Display every configured folder and whether it is
    currently enabled for automatic syncing.
    """

    print("\nConfigured folders:")
    print("-------------------")

    for folder in folders.values():

        if folder["enabled"]:
            status = "ACTIVE"
        else:
            status = "PAUSED"

        print(f"{folder['name']}: {status}")


def show_scheduler():
    """
    Display the current global automatic-sync status
    and the configured interval.
    """
    if get_scheduler_status():
        status = "ACTIVE"
    else:
        status = "PAUSED"

    print("\nAutomatic Sync")
    print("--------------")
    print(f"Status: {status}")
    print(f"Interval: {get_scheduler_interval()} minutes")


def main():

    while True:

        print("\nGoogle Drive Bisync Manager")
        print("===========================")

        print("\nGlobal")
        print("1. Show scheduler status")
        print("2. Pause automatic syncing")
        print("3. Resume automatic syncing")
        print("4. Change sync interval")

        print("\nFolders")
        print("5. Show folders")
        print("6. Sync a folder")
        print("7. Pause a folder")
        print("8. Resume a folder")

        print("\nActions")
        print("9. Sync all")
        print("10. Exit")

        choice = input("\nChoose an option: ").strip()


        # -------------------------------------------------
        # Show scheduler status
        # -------------------------------------------------

        if choice == "1":

            show_scheduler()


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
        # Show folders
        # -------------------------------------------------

        elif choice == "5":

            show_folders()


        # -------------------------------------------------
        # Sync one folder
        # -------------------------------------------------

        elif choice == "6":

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

        elif choice == "7":

            name = input("Folder name: ").strip()

            pause(name)


        # -------------------------------------------------
        # Resume one folder
        # -------------------------------------------------

        elif choice == "8":

            name = input("Folder name: ").strip()

            resume(name)


        # -------------------------------------------------
        # Sync all enabled folders
        # -------------------------------------------------

        elif choice == "9":

            sync_all()


        # -------------------------------------------------
        # Exit
        # -------------------------------------------------

        elif choice == "10":

            print("Goodbye.")
            break


        # -------------------------------------------------
        # Invalid option
        # -------------------------------------------------

        else:

            print("Invalid option. Please choose a number "
                  "from the menu.")


if __name__ == "__main__":
    main()
