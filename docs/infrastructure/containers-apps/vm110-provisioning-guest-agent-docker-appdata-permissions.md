---
title: "VM 110 Provisioning Alignment, Guest Agent Check, IP Conflict Discussion, and Docker Appdata Permissions"
track: "infrastructure"
category: "containers-apps"
type: "runbook"
logical_order: 90
date_rule: "Dates are removed from filenames, visible headings, indexes, generated metadata, and runbook body content."
---

# VM 110 Provisioning Alignment, Guest Agent Check, IP Conflict Discussion, and Docker Appdata Permissions

## Summary
This work session focused on reusing the configuration pattern from Proxmox VM 100 for a new VM 110, confirming the correct CPU model, reapplying the cloud-init custom snippet configuration, checking QEMU Guest Agent status, discussing the behavior of duplicate IP addresses on the same network, and standardizing ownership and permissions for Docker appdata under `/opt/docker-apps`. The session ended with a practical permissions plan for appdata used by Docker services such as Traefik and Dockge.

## Environment
- **Hypervisor:** Proxmox VE
- **VMs involved:**  
  - VM 100: existing Debian Docker VM used as reference  
  - VM 110: new VM being aligned to the same pattern
- **Guest OS context:** Debian-based Docker VM
- **Cloud-init snippet storage:** `snips` (CephFS-backed snippet storage)
- **Docker appdata path:** `/opt/docker-apps`
- **Compose path context:** `/opt/compose`
- **Containers / app folders mentioned:** Traefik, Dockge, Radarr, Sonarr, SABnzbd, qBittorrent, Plex, Prowlarr, Lidarr, Syncthing, Vaultwarden, TubeArchivist, Audiobookshelf, and many others under `/opt/docker-apps`
- **Networking context:** Proxmox VM networking on a shared LAN / bridge
- **Remote file management tool:** WinSCP
- **Relevant Proxmox feature:** QEMU Guest Agent
- **Relevant reverse proxy component:** Traefik with `acme.json`

## Problem
A new VM 110 needed to inherit the known-good VM 100 pattern, including CPU model and cloud-init snippet usage. During this process, the guest agent was reported as not running. Separately, there was uncertainty about whether the `debian` user should be able to delete files in Docker appdata from WinSCP, especially for Dockge and app config files such as Traefik JSON data.

## Symptoms
- Uncertainty about the exact CPU model used for VM 100.
- Need to restate the correct `cicustom` line for VM 110.
- Proxmox reported that the **guest agent was not running**.
- Concern about duplicate static IP usage between VMs.
- In WinSCP, the `debian` user could not reliably delete or manage files inside Docker appdata.
- Need to normalize permissions for appdata such as:
  - Traefik files
  - JSON-based app config
  - Dockge data
  - Other service directories under `/opt/docker-apps`

## Actions Taken
1. Recalled the VM 100 resource pattern and applied it conceptually to VM 110.
2. Corrected the CPU model from a generic assumption to the specific Proxmox CPU type:
   ```bash
   qm set 110 --cores 8 --sockets 1 --memory 16384 --balloon 0 --cpu x86-64-v3
   ```
   Purpose: align VM 110 CPU and memory settings with the intended VM 100 profile.

3. Restated the cloud-init custom snippet configuration for VM 110:
   ```bash
   qm set 110 --cicustom "user=snips:snippets/docker-userdata.yml,network=snips:snippets/docker-net.yml"
   ```
   Purpose: attach the existing user-data and network-data snippets from `snips`.

4. Restated the cloud-init drive attachment:
   ```bash
   qm set 110 --ide2 snips:cloudinit
   ```
   Purpose: ensure VM 110 has a cloud-init drive.

5. Addressed the “guest agent isn’t running” issue by identifying the normal enable/install flow:
   ```bash
   qm set 110 --agent enabled=1
   ```
   Purpose: enable QEMU Guest Agent support on the Proxmox side.

   ```bash
   sudo apt update
   sudo apt install -y qemu-guest-agent
   sudo systemctl enable --now qemu-guest-agent
   ```
   Purpose: install and start the guest agent inside the guest OS.

6. Discussed duplicate IP behavior if two VMs boot with the same IP on the same Layer 2 network.
7. Clarified that duplicate IPs on the same subnet would cause ARP instability and intermittent reachability rather than a clean winner/loser scenario.
8. Investigated the appdata permissions question, initially in the context of Dockge.
9. Proposed standardizing Docker appdata ownership to the `debian` user.
10. Requested and reviewed the folder list under `/opt/docker-apps`, which confirmed a broad shared appdata layout including Traefik and Dockge.
11. Recommended standardizing ownership and permissions across all appdata:
   ```bash
   sudo chown -R debian:debian /opt/docker-apps
   sudo chmod -R u=rwX,go-rX /opt/docker-apps
   ```
   Purpose: make `debian` the managing user for appdata and allow WinSCP operations.

12. Identified Traefik `acme.json` as a special-case file requiring tighter permissions:
   ```bash
   sudo chown debian:debian /opt/docker-apps/Traefik/acme.json
   sudo chmod 600 /opt/docker-apps/Traefik/acme.json
   ```
   Purpose: preserve Traefik compatibility with sensitive certificate storage.

## Key Findings
- The intended Proxmox CPU type was **`x86-64-v3`**, not a generic `host` or incorrectly spelled variant.
- VM 110 should reuse the same cloud-init snippet model as VM 100, using:
  - `docker-userdata.yml`
  - `docker-net.yml`
  stored on **`snips`**.
- If the QEMU Guest Agent is reported as not running, the issue can exist on either side:
  - Agent not enabled in Proxmox
  - Agent package not installed / started inside the guest
- Two VMs using the same IP on the same Layer 2 network will usually cause:
  - ARP table instability
  - intermittent connectivity
  - sessions landing on the wrong host
  rather than a predictable failure mode
- In Linux, deleting a file depends primarily on **write and execute permissions on the parent directory**, not only the file ownership itself.
- For this homelab pattern, making `debian` own `/opt/docker-apps` is operationally consistent with Docker workloads that are intended to be managed by that user.
- Traefik `acme.json` is a special permissions case and should remain restricted.

## Resolution
Current working guidance from this session:

- VM 110 should be configured with:
  - `8` cores
  - `1` socket
  - `16384` MB RAM
  - ballooning disabled
  - CPU type `x86-64-v3`

- VM 110 cloud-init should use:
  - user snippet: `snips:snippets/docker-userdata.yml`
  - network snippet: `snips:snippets/docker-net.yml`
  - cloud-init drive on `snips:cloudinit`

- If guest agent status is still needed, the next step is to ensure:
  - Proxmox agent support is enabled
  - `qemu-guest-agent` is installed and running in the guest

- Docker appdata should be standardized to `debian:debian` ownership under `/opt/docker-apps`, with restrictive but usable permissions.

- Traefik `acme.json` should be explicitly set to mode `600`.

## Validation
Validation methods identified in the session:

- Confirm VM CPU setting:
  ```bash
  qm config 110 | grep -i cpu
  ```
- Confirm custom cloud-init snippet attachment:
  ```bash
  qm config 110 | grep -i cicustom
  ```
- Confirm guest agent communication:
  ```bash
  qm guest cmd 110 ping
  ```
- Confirm guest agent service state in the guest:
  ```bash
  systemctl status qemu-guest-agent
  ```
- Confirm appdata ownership and permissions:
  ```bash
  ls -ld /opt/docker-apps /opt/docker-apps/*
  ```
- Confirm Traefik special file permissions:
  ```bash
  ls -l /opt/docker-apps/Traefik
  ```

## Follow-Up Tasks
- Compare `qm config 100` and `qm config 110` directly to ensure no important VM options were missed.
- Confirm whether VM 110 should receive a unique static IP or DHCP reservation before boot if cloned from VM 100 patterns.
- Verify that VM 110 has the cloud-init drive attached before first boot.
- Confirm whether guest agent status matters operationally for this VM or can be deferred.
- Review whether some containers should explicitly run as `1000:1000` to prevent future root-owned file creation.
- Audit sensitive files under `/opt/docker-apps` beyond Traefik `acme.json`, such as:
  - `.env` files
  - API key files
  - backup credentials
  - secret JSON / YAML files

## Lessons Learned
- Reusing a known-good VM pattern is efficient, but exact CPU type names matter in Proxmox.
- Cloud-init snippet location must match the actual snippet storage backend in use.
- QEMU Guest Agent problems often come from forgetting one half of the configuration: host-side enablement or guest-side service install.
- Duplicate IPs on the same LAN create confusing intermittent failures, not always obvious hard-down conditions.
- For Docker bind-mounted appdata, operational ownership should match the user expected to manage files over SSH / WinSCP.
- Sensitive files such as Traefik `acme.json` should be handled as exceptions even when standardizing broader directory permissions.

---

# Command Reference

## Command
```bash
qm set 110 --cores 8 --sockets 1 --memory 16384 --balloon 0 --cpu x86-64-v3
```

**What it does**  
Updates Proxmox VM 110 to use 8 CPU cores, 1 socket, 16 GiB RAM, ballooning disabled, and the `x86-64-v3` CPU model.

**Important flags / arguments**
- `110`: target VM ID
- `--cores 8`: assigns 8 virtual CPU cores
- `--sockets 1`: keeps those cores under 1 virtual socket
- `--memory 16384`: allocates 16384 MB RAM
- `--balloon 0`: disables ballooning
- `--cpu x86-64-v3`: sets the emulated CPU model

**Why it was used at that moment**  
To make VM 110 match the known resource pattern intended from VM 100.

**Expected result**  
VM 110 configuration reflects the specified CPU and RAM settings.

**What success or failure would indicate**
- Success: `qm config 110` shows the updated values.
- Failure: typo in CPU model, invalid VM ID, or Proxmox rejecting the setting.

**Risk level**  
Low to moderate. CPU model changes can affect guest compatibility if changed on an already-running or already-tuned guest.

**Safer alternative**  
Inspect VM 100 directly first with `qm config 100` and mirror only the confirmed values.

## Command
```bash
qm config 110 | grep -i cpu
```

**What it does**  
Shows the CPU-related configuration lines for VM 110.

**Important flags / arguments**
- `qm config 110`: prints the VM configuration
- `grep -i cpu`: filters output case-insensitively for CPU-related lines

**Why it was used at that moment**  
To validate that the CPU model and CPU-related settings were applied correctly.

**Expected result**  
A line showing the configured CPU type and possibly related CPU settings.

**What success or failure would indicate**
- Success: expected CPU config appears.
- Failure: missing expected line means the prior change did not apply or was not stored.

**Risk level**  
Low.

## Command
```bash
qm set 110 --cicustom "user=snips:snippets/docker-userdata.yml,network=snips:snippets/docker-net.yml"
```

**What it does**  
Tells Proxmox to use custom cloud-init user-data and network-data files for VM 110 from the `snips` storage.

**Important flags / arguments**
- `--cicustom`: overrides the default generated cloud-init config
- `user=...`: points to the cloud-init user-data snippet
- `network=...`: points to the cloud-init network-data snippet
- `snips:snippets/...`: Proxmox storage and file path syntax for snippet storage

**Why it was used at that moment**  
To reuse the established Debian Docker VM cloud-init pattern for VM 110.

**Expected result**  
VM 110 references the custom user and network cloud-init snippet files.

**What success or failure would indicate**
- Success: `qm config 110` shows the `cicustom` entry.
- Failure: snippet path, storage name, or file location is wrong.

**Risk level**  
Moderate. A wrong snippet can misconfigure login, networking, package install, or storage mounts.

**Safer alternative**  
Run `qm cloudinit dump 110 user` and `qm cloudinit dump 110 network` before boot to inspect the effective rendered config if needed.

## Command
```bash
qm config 110 | grep -i cicustom
```

**What it does**  
Checks whether a custom cloud-init configuration is attached to VM 110.

**Important flags / arguments**
- `qm config 110`: prints the config
- `grep -i cicustom`: finds the `cicustom` line

**Why it was used at that moment**  
To confirm the snippet attachment was saved correctly.

**Expected result**  
A line containing the `user=` and `network=` snippet references.

**What success or failure would indicate**
- Success: cloud-init override is present.
- Failure: missing line means the setting was not applied.

**Risk level**  
Low.

## Command
```bash
qm set 110 --ide2 snips:cloudinit
```

**What it does**  
Attaches a cloud-init drive to VM 110 on the `ide2` bus using the `snips` storage.

**Important flags / arguments**
- `--ide2`: sets the second IDE device slot
- `snips:cloudinit`: creates or attaches a Proxmox-managed cloud-init disk on the `snips` storage

**Why it was used at that moment**  
Cloud-init needs a cloud-init drive attached to inject metadata into the VM.

**Expected result**  
VM 110 has a cloud-init drive available.

**What success or failure would indicate**
- Success: `qm config 110` shows an `ide2` cloud-init disk.
- Failure: storage or content type may not support the requested object.

**Risk level**  
Low.

## Command
```bash
qm set 110 --agent enabled=1
```

**What it does**  
Enables QEMU Guest Agent support for VM 110 in Proxmox.

**Important flags / arguments**
- `--agent enabled=1`: turns on guest agent integration for the VM

**Why it was used at that moment**  
The guest agent was reported as not running, so host-side support needed to be confirmed.

**Expected result**  
Proxmox is ready to communicate with the guest agent once the guest-side service is running.

**What success or failure would indicate**
- Success: VM options show guest agent enabled.
- Failure: invalid VM ID or config application issue.

**Risk level**  
Low.

## Command
```bash
sudo apt update
```

**What it does**  
Refreshes the Debian package index.

**Important flags / arguments**
- `sudo`: runs with administrative privileges
- `apt update`: fetches current package metadata

**Why it was used at that moment**  
Installing `qemu-guest-agent` requires a current package index.

**Expected result**  
Package lists refresh successfully from configured repositories.

**What success or failure would indicate**
- Success: package index updated and package install can proceed.
- Failure: DNS, network, repository, or mirror issues.

**Risk level**  
Low.

## Command
```bash
sudo apt install -y qemu-guest-agent
```

**What it does**  
Installs the QEMU Guest Agent package inside the Debian VM.

**Important flags / arguments**
- `install`: installs packages
- `-y`: automatically answers yes to prompts
- `qemu-guest-agent`: guest agent package name

**Why it was used at that moment**  
To provide the actual guest-side service required for Proxmox guest-agent integration.

**Expected result**  
Package is installed successfully.

**What success or failure would indicate**
- Success: systemd service becomes available.
- Failure: package repository, connectivity, or dpkg issues.

**Risk level**  
Low.

## Command
```bash
sudo systemctl enable --now qemu-guest-agent
```

**What it does**  
Enables the guest agent to start at boot and starts it immediately.

**Important flags / arguments**
- `enable`: persistently enables the service
- `--now`: starts it immediately
- `qemu-guest-agent`: service unit name

**Why it was used at that moment**  
To make the guest agent active right away and persistent across reboots.

**Expected result**  
The service enters the running state.

**What success or failure would indicate**
- Success: `systemctl status` shows active.
- Failure: service misconfiguration, missing package, or virtualization-side communication issue.

**Risk level**  
Low.

## Command
```bash
systemctl status qemu-guest-agent
```

**What it does**  
Shows the status of the guest agent service.

**Important flags / arguments**
- `status`: displays runtime state, logs, and service metadata

**Why it was used at that moment**  
To confirm whether the service was actually running inside the guest.

**Expected result**  
`active (running)` or a useful failure message.

**What success or failure would indicate**
- Success: service is active.
- Failure: service crash, missing package, or other startup issue.

**Risk level**  
Low.

## Command
```bash
journalctl -u qemu-guest-agent -n 40
```

**What it does**  
Shows the last 40 log lines for the QEMU Guest Agent service.

**Important flags / arguments**
- `-u qemu-guest-agent`: restricts logs to that unit
- `-n 40`: prints the last 40 lines

**Why it was used at that moment**  
To diagnose why the service might not be running.

**Expected result**  
Service startup logs or error messages.

**What success or failure would indicate**
- Success: logs explain current behavior.
- Failure: absence of logs may indicate the unit never started or logging is unavailable.

**Risk level**  
Low.

## Command
```bash
qm guest cmd 110 ping
```

**What it does**  
Sends a simple guest-agent command to VM 110 from the Proxmox host.

**Important flags / arguments**
- `guest cmd`: runs a QEMU Guest Agent command
- `110`: target VM
- `ping`: basic connectivity test against the agent

**Why it was used at that moment**  
To verify that the Proxmox host can talk to the guest agent.

**Expected result**  
A valid JSON response or a successful acknowledgment.

**What success or failure would indicate**
- Success: guest agent is installed, running, and reachable.
- Failure: agent is disabled, not installed, not running, or not connected.

**Risk level**  
Low.

## Command
```bash
id debian
```

**What it does**  
Displays the numeric and named user/group identity for the `debian` account.

**Important flags / arguments**
- `debian`: the user being queried

**Why it was used at that moment**  
To confirm the expected UID and GID, likely `1000:1000`, before setting ownership.

**Expected result**  
Output showing `uid=1000(debian) gid=1000(debian)` or similar.

**What success or failure would indicate**
- Success: confirms what ownership target to use.
- Failure: if the user does not exist or has different IDs than assumed.

**Risk level**  
Low.

## Command
```bash
sudo chown -R debian:debian /opt/docker-apps
```

**What it does**  
Recursively changes ownership of everything under `/opt/docker-apps` to user `debian` and group `debian`.

**Important flags / arguments**
- `chown`: change ownership
- `-R`: recurse into all files and directories
- `debian:debian`: new owner and group
- `/opt/docker-apps`: target directory tree

**Why it was used at that moment**  
To make Docker appdata manageable from WinSCP and consistent with the intended host-side managing user.

**Expected result**  
All appdata under `/opt/docker-apps` becomes owned by `debian`.

**What success or failure would indicate**
- Success: `ls -l` shows `debian debian` ownership.
- Failure: permissions, mount behavior, or immutable filesystem characteristics may block changes.

**Risk level**  
Moderate. Recursive ownership changes can affect container expectations if a service requires root-owned files.

**Safer alternative**  
Change only selected app folders first, such as `/opt/docker-apps/Dockge` or `/opt/docker-apps/Traefik`, and validate behavior.

## Command
```bash
sudo chmod -R u=rwX,go-rX /opt/docker-apps
```

**What it does**  
Recursively sets permissions so the owner has read/write and execute where appropriate, while group and others lose read and execute access.

**Important flags / arguments**
- `chmod`: change mode
- `-R`: recurse
- `u=rwX`: owner gets read/write and execute only where needed
- `go-rX`: remove read and execute from group and others

**Why it was used at that moment**  
To standardize appdata permissions for security and usability.

**Expected result**  
Directories remain traversable by the owner, files become writable by the owner, and exposure to other users is minimized.

**What success or failure would indicate**
- Success: WinSCP as `debian` can edit/delete files, and permissions look tighter.
- Failure: some applications may expect broader access or a different owner.

**Risk level**  
Moderate. Recursive chmod can break apps if they need shared group access or executable bits on specific files.

**Safer alternative**  
Use separate `find` commands for directories and files to control permissions more precisely.

## Command
```bash
sudo find /opt/docker-apps -type d -exec chmod 750 {} \;
```

**What it does**  
Sets all directories under `/opt/docker-apps` to mode `750`.

**Important flags / arguments**
- `find`: traverses the tree
- `-type d`: matches directories only
- `-exec chmod 750 {} \;`: applies mode `750` to each directory

**Why it was used at that moment**  
To provide a more precise alternative to recursive chmod.

**Expected result**  
Directories are readable, writable, and traversable by owner; readable and traversable by group; inaccessible to others.

**What success or failure would indicate**
- Success: directory traversal works as intended.
- Failure: applications depending on wider access may fail.

**Risk level**  
Moderate.

## Command
```bash
sudo find /opt/docker-apps -type f -exec chmod 640 {} \;
```

**What it does**  
Sets all regular files under `/opt/docker-apps` to mode `640`.

**Important flags / arguments**
- `-type f`: matches files only
- `chmod 640`: owner read/write, group read, others no access

**Why it was used at that moment**  
To provide tighter, file-specific permission control.

**Expected result**  
Files are owner-editable and group-readable.

**What success or failure would indicate**
- Success: data files become consistently protected.
- Failure: executable scripts may lose execute permission.

**Risk level**  
Moderate. Do not blindly use this if appdata includes scripts that need to remain executable.

## Command
```bash
sudo chown debian:debian /opt/docker-apps/Traefik/acme.json
```

**What it does**  
Sets ownership of Traefik’s certificate storage file to `debian`.

**Important flags / arguments**
- target file: `/opt/docker-apps/Traefik/acme.json`

**Why it was used at that moment**  
Traefik certificate storage needed to align with the standardized owner while remaining securely restricted.

**Expected result**  
The file is owned by `debian`.

**What success or failure would indicate**
- Success: ownership changes cleanly.
- Failure: missing file path or permission problem.

**Risk level**  
Low to moderate. Ownership changes are usually safe here, but confirm the container can still access the file.

## Command
```bash
sudo chmod 600 /opt/docker-apps/Traefik/acme.json
```

**What it does**  
Restricts `acme.json` so only the owner can read and write it.

**Important flags / arguments**
- `600`: owner read/write only

**Why it was used at that moment**  
Traefik commonly expects sensitive certificate storage to be tightly permissioned.

**Expected result**  
Traefik accepts the file permissions and continues operating normally.

**What success or failure would indicate**
- Success: Traefik reads and writes certificate data without permission warnings.
- Failure: wrong owner or wrong container runtime user may prevent access.

**Risk level**  
Low. This is usually the recommended mode for `acme.json`.

## Command
```bash
ls -ld /opt/docker-apps /opt/docker-apps/*
```

**What it does**  
Lists detailed permissions and ownership for the appdata root and all immediate child directories.

**Important flags / arguments**
- `-l`: long listing format
- `-d`: list directory entries themselves, not their contents
- `/opt/docker-apps/*`: expands to each app folder

**Why it was used at that moment**  
To audit ownership and mode problems across the appdata tree.

**Expected result**  
A list showing each folder’s owner, group, and permission mode.

**What success or failure would indicate**
- Success: provides a quick view for spotting root-owned or mispermissioned directories.
- Failure: shell glob or path issue if the directory does not exist.

**Risk level**  
Low.

## Command
```bash
ls -l /opt/docker-apps/Traefik
```

**What it does**  
Lists detailed contents of the Traefik appdata directory.

**Important flags / arguments**
- `-l`: long format listing

**Why it was used at that moment**  
To specifically verify the state of `acme.json` and other Traefik files.

**Expected result**  
Shows ownership, mode, and filenames inside the Traefik directory.

**What success or failure would indicate**
- Success: can visually confirm `acme.json` ownership and mode.
- Failure: path incorrect or directory absent.

**Risk level**  
Low.
