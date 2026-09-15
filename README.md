# Google Drive Bisync Manager

A lightweight Linux CLI for managing multiple **rclone bisync** folder pairs with **systemd** — no manual unit files, no hand-rolled scheduler.

Everything (per-folder services, a dispatcher, and a common timer) is generated and controlled from a single `config.json`. Point it at a folder, and it handles safe two-way sync with Google Drive on a schedule you control.

```text
config.json  →  Python manager  →  systemd services/timer  →  rclone  →  Google Drive
```

## Why this exists

`rclone bisync` is powerful but unforgiving to configure by hand across many folders — every folder needs its own service, its own safety flags, and a scheduler that won't let cycles overlap. This project turns that into a single JSON file and a menu-driven CLI, while keeping the actual sync execution and scheduling in systemd, where it belongs.

## Features

- Manage multiple local ↔ Google Drive folder pairs from one config file
- Auto-generate a `systemd` service per folder, plus a dispatcher and timer
- Sync all enabled folders sequentially, or trigger one folder manually
- Pause/resume syncing globally or per folder
- Guided `--resync` workflow for safely initializing new folder pairs
- Add/remove folder pairs entirely from the CLI
- Configurable global sync interval
- Per-folder view of **auto-sync setting** vs. **last execution result**
- Conservative rclone defaults (`--check-access`, `--max-delete`, rate limits)
- One failed folder never blocks the rest of the sync cycle
- Atomic writes for every generated file (safe against interrupted runs)

## Architecture

```text
                         config.json
                              │
                              ▼
                        Python Manager
                              │
             ┌────────────────┼────────────────┐
             │                │                 │
             ▼                ▼                 ▼
       Folder Services    Dispatcher          Timer
             │                │                 │
             │                ▼                 ▼
             │        Master systemd      (schedules the
             │             service         master service)
             │                │
             └────────────────┴──────────────────┐
                                                   ▼
                                                rclone
                                                   │
                                                   ▼
                                            Google Drive
```

**Separation of concerns is deliberate:**

| Layer | Responsibility |
|---|---|
| `config.json` | Single source of truth for folders, defaults, and schedule |
| `manager.py` | Reads/writes config, builds rclone commands, generates systemd units, tracks status |
| `main.py` | Interactive CLI that calls into `manager.py` |
| `systemd` | Actually executes and schedules the sync jobs |
| `rclone` | Performs the bidirectional sync |

The Python code never calls rclone directly — it only ever generates and controls the systemd units that do.

## Requirements

- Linux with `systemd --user` services
- Python 3
- [rclone](https://rclone.org/), with a configured Google Drive remote

## Setup

**1. Install and configure rclone**

```bash
sudo apt update
sudo apt install rclone
rclone config          # set up a remote, e.g. "my-gdrive"
rclone lsd my-gdrive:   # verify it works
```

**2. Get the project**

```bash
git clone https://github.com/kkumar420/bisync_manager.git
cd bisync_manager
mkdir -p ~/.config/systemd/user ~/.local/bin
```

**3. Configure `config.json`**

```json
{
    "remote": "my-gdrive",

    "scheduler": {
        "enabled": true,
        "interval_minutes": 5
    },

    "defaults": {
        "check_access": true,
        "max_delete": 10,
        "tpslimit": 5,
        "tpslimit_burst": 5,
        "transfers": 4,
        "checkers": 8
    },

    "folders": [
        {
            "name": "Vaikunth",
            "local_path": "/path/to/Vaikunth",
            "remote_path": "Vaikunth",
            "service": "rclone-vaikunth-bisync.service",
            "enabled": true
        }
    ]
}
```

| Field | Meaning |
|---|---|
| `name` | Human-readable folder name (shown in the CLI) |
| `local_path` | Local directory to sync |
| `remote_path` | Path inside the configured rclone remote |
| `service` | Generated systemd service name |
| `enabled` | Whether this folder is included in automatic sync cycles |

`name` and `service` are kept separate so user-facing names don't have to follow systemd naming rules.

**4. Generate the systemd setup**

```bash
python3 main.py
```

Choose **`10. Regenerate systemd setup`** to generate all services, the dispatcher, the master service, and the timer from your config.

## Usage

```bash
python3 main.py
```

```text
Global
1. Show status
2. Pause automatic syncing
3. Resume automatic syncing
4. Change sync interval

Folders
5. Sync a folder
6. Pause a folder
7. Resume a folder
8. Add a folder
9. Remove a folder

System
10. Regenerate systemd setup

Actions
11. Sync all
12. Resync a folder
13. Exit
```

### Status view

Status separates **configuration** from **execution**:

- **Auto Sync** — should this folder run in future automatic cycles?
- **State** — what happened the last time it ran?

```text
Folder          Auto Sync    State
--------------------------------------------------
Vaikunth        ENABLED      SUCCESS
My_Library      PAUSED       SUCCESS
BITS_Goa        ENABLED      FAILED
DSA_Sheet       ENABLED      SYNCING
```

A paused folder still shows its last known result — pausing doesn't erase history.

### Adding a folder

New folders can't jump straight into automatic syncing — bisync needs an initial `--resync` to establish a baseline first:

```text
Add folder
    ↓
Folder stored, disabled
    ↓
Normal systemd service generated
    ↓
Initial --resync runs
    ↓
   Succeeded?
    ├── No  → stays disabled, fix and retry
    └── Yes → enabled, joins the automatic dispatcher
```

The initial resync runs through a **temporary** systemd service, so the permanent service definition is never touched by it. Normal scheduled syncs never use `--resync`.

Before adding a folder, make sure an `RCLONE_TEST` marker file exists in **both** the local folder and the corresponding Google Drive folder — the manager checks for it via `--check-access` but doesn't create it for you.

### Removing a folder

Removing a folder deletes its config entry, its generated service file, and regenerates the dispatcher. A folder that's actively syncing can't be removed until it finishes.

## Safety

Normal syncs run with conservative defaults:

```text
--check-access
--max-delete 10
--tpslimit 5
--tpslimit-burst 5
--transfers 4
--checkers 8
```

- **`--check-access`** relies on the `RCLONE_TEST` marker as a sanity check before syncing.
- **`--max-delete`** caps how many files can be deleted in one run, guarding against a runaway sync wiping out a folder.
- **Sequential execution** — folders sync one at a time (`Folder A → Folder B → Folder C → …`), so API usage and system load stay bounded, and cycles never overlap.
- **Isolated failures** — the dispatcher runs each folder with `|| true`, so one failing folder doesn't stop the rest.
- **Atomic writes** — every generated file (services, dispatcher, timer) is written to a temp file first, then swapped in with `os.replace()`, so a crash mid-write can't leave a half-written unit file behind.

## Scheduling

A single timer drives all automatic syncing:

```ini
[Timer]
OnUnitInactiveSec=5min
Persistent=true
```

Because the timer is keyed off the master service going *inactive* (rather than a fixed clock interval), the next cycle only starts once the previous one has fully finished:

```text
Start cycle → sync enabled folders → master service finishes
    → wait configured interval → start next cycle
```

Resuming automatic syncing starts the timer **and** triggers an immediate first cycle, rather than waiting for the interval to elapse.

## Generated files

```text
~/.config/systemd/user/
├── rclone-<folder>-bisync.service   (one per folder)
├── rclone-bisync-all.service        (master/dispatcher service)
└── rclone-bisync-all.timer

~/.local/bin/
└── rclone-bisync-all.sh             (dispatcher script)
```

All generated files are headed with a warning that they're managed by Bisync Manager — edit `config.json` instead of these directly, since they're overwritten on every regeneration.

## Troubleshooting

```bash
# Check one folder's service
systemctl --user status rclone-vaikunth-bisync.service

# View its logs
journalctl --user -u rclone-vaikunth-bisync.service -n 50 --no-pager

# Check the master service / dispatcher run
journalctl --user -u rclone-bisync-all.service -n 50 --no-pager

# Check or list timers
systemctl --user status rclone-bisync-all.timer
systemctl --user list-timers

# Inspect a generated unit or the dispatcher script
systemctl --user cat rclone-vaikunth-bisync.service
cat ~/.local/bin/rclone-bisync-all.sh
```

**If rclone reports that `--resync` is required:** don't keep re-running the normal sync. Use **`12. Resync a folder`** from the CLI after you've figured out what caused the mismatch.

## Project structure

```text
bisync_manager/
├── config.json     # Single source of truth
├── manager.py      # Config, rclone commands, systemd generation, status
├── main.py         # Interactive CLI
└── README.md
```

## Design goals

- `config.json` is the only source of truth
- Python handles configuration and orchestration — nothing else
- systemd handles execution and scheduling
- rclone handles the actual sync
- One service per folder → isolation and independent logs
- One dispatcher + timer → centralized, non-overlapping scheduling
- Generated files mean no unit files are ever hand-edited
- A failure in one folder never blocks the others

This is a personal Linux automation and learning project, not a production-grade sync platform.

## License

Intended primarily for personal use and learning.