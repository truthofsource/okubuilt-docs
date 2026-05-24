---
title: "Recreate Debian Docker VM from Proxmox Template 9000 with Single Root Disk"
track: "infrastructure"
category: "containers-apps"
type: "runbook"
logical_order: 60
date_rule: "Dates are removed from filenames, visible headings, indexes, generated metadata, and runbook body content."
---

# Recreate Debian Docker VM from Proxmox Template 9000 with Single Root Disk

## Summary
A Debian Docker VM was rebuilt from Proxmox template `9000` using `cephpool`, with the root disk expanded to `200G`. During the rebuild, the cloud-init design was simplified: the separate Docker data disk was removed, `/var/lib/docker` was moved back onto the root disk, `/opt/docker-apps` and `/opt/compose` were converted to normal directories instead of bind mounts, and Gluetun-specific restart automation was removed from the cloud-init user-data. The session also covered how cloud-init snippets behave, how `fstab`, bind mounts, and automounts relate, and how to begin restoring application data from the NAS into `/opt/docker-apps`.

## Environment
- **Hypervisor:** Proxmox VE
- **Template source VM:** `9000`
- **Target VM OS:** Debian GNU/Linux 12 (bookworm)
- **Target hostname:** `debian-docker`
- **Kernel:** `6.1.0-40-cloud-amd64`
- **Virtualization:** KVM
- **Storage backend:** `cephpool`
- **Cloud-init snippet storage:** CephFS storage `snips`
- **Snippet directory:** `/mnt/pve/snips/snippets/`
- **User-data snippet:** `snips:snippets/docker-userdata.yml`
- **Network-data snippet:** `snips:snippets/docker-net.yml`
- **Docker data-root:** `/var/lib/docker`
- **Application paths:** `/opt/docker-apps`, `/opt/compose`
- **NAS mounts:**
  - `//192.168.16.21/Media` -> `/srv/remotemount/NAS`
  - `//192.168.16.22/Public` -> `/srv/remotemount/wontonsoup`
- **Mount type for NAS shares:** CIFS with systemd automount
- **Docker service state during validation:** active/running
- **Observed VM disk layout after rebuild:**
  - `sda` = `200G`
  - `sda1` = `/`
  - `sda15` = `/boot/efi`

## Problem
The previous Docker VM design used a second disk mounted at `/var/lib/docker`, bind mounts from `/var/lib/docker/appdata` to `/opt/docker-apps`, and an additional “mount guard” verification service. That design increased complexity and had previously contributed to duplicate `fstab` and mount-ordering issues. The rebuild goal was to simplify the VM design and avoid repeating the older cloud-init and `fstab` problems.

## Symptoms
- Attempting to run `--cicustom` by itself produced:
  ```text
  -bash: --cicustom: command not found
  ```
- Running `apt update -y` as the unprivileged `debian` user produced:
  ```text
  E: Could not open lock file /var/lib/apt/lists/lock - open (13: Permission denied)
  E: Unable to lock directory /var/lib/apt/lists/
  ```
- Initial restore attempt failed because `rsync` was not installed:
  ```text
  sudo: rsync: command not found
  ```
- First restore attempt also failed because the NAS source path was wrong:
  ```text
  rsync: [sender] change_dir "/srv/remotemount/NAS/Backups/docker-apps-backup" failed: No such file or directory (2)
  rsync error: some files/attrs were not transferred ... (code 23)
  ```

## Actions Taken
1. Planned a clone of template `9000` into a new VM on `cephpool` with a `200G` root disk.
2. Confirmed that the correct cloud-init snippet location for CephFS `snips` storage is:
   ```bash
   /mnt/pve/snips/snippets/
   ```
3. Reviewed the existing cloud-init user-data YAML and confirmed it used:
   - a separate disk mounted to `/var/lib/docker`
   - CIFS automounts for NAS shares
   - bind mounts from Docker subdirectories into `/opt`
   - a Docker mount verification script and service
   - Gluetun restart script, service, and timer
4. Confirmed that the existing YAML itself did not inherently cause duplicate `fstab` entries, provided the same mounts were not also manually defined elsewhere.
5. Changed the design goal:
   - remove the second Docker data disk
   - use the root disk for `/var/lib/docker`
   - make `/opt/docker-apps` and `/opt/compose` normal directories
   - remove bind mounts
6. Produced a revised cloud-init user-data YAML reflecting the simplified design.
7. Removed all Gluetun-related automation from that revised YAML.
8. Clarified cloud-init behavior:
   - `write_files`, `runcmd`, and `bootcmd` are effectively one-time per VM instance
   - changing user-data later on the same already-initialized VM does not recreate files automatically
   - network cloud-init can be updated and reapplied on the same VM through Proxmox cloud-init regeneration
9. Clarified cloud-init data types:
   - user-data
   - network-config
   - meta-data
   - vendor-data
10. Saved the simplified current `docker-userdata.yml` design as the remembered baseline for future homelab work.
11. Explained the old “mount guard” concept:
    - it was a custom name, not an official Linux feature
    - it verified that `/var/lib/docker` was mounted from the expected second disk UUID before Docker could start
12. Explained how the previous design worked:
    - Proxmox attached a second disk
    - the disk was mounted via `fstab` at `/var/lib/docker`
    - Docker used `daemon.json` to store data at `/var/lib/docker`
13. Clarified that `fstab` does not tell Docker where to store data; instead:
    - `fstab` determines what filesystem exists at `/var/lib/docker`
    - Docker uses `data-root=/var/lib/docker`
14. Applied cloud-init snippets to the new VM correctly with `qm set ... --cicustom` and `qm cloudinit update`.
15. Booted and validated the rebuilt VM.
16. Checked system identity, disk layout, root disk size, Docker service state, Docker daemon configuration, user group membership, mount entries, and NAS automount behavior.
17. Triggered the NAS automount and verified that the share contents were visible.
18. Attempted to restore application data into `/opt/docker-apps`.
19. Determined the correct NAS source path for appdata:
    ```text
    Backups\docker-VM\appdata
    ```
    which corresponds on Linux to:
    ```bash
    /srv/remotemount/NAS/Backups/docker-VM/appdata
    ```

## Key Findings
- The simplified VM design worked as intended:
  - no separate Docker disk
  - no bind mounts
  - Docker root data remains at `/var/lib/docker` on the root disk
- The rebuilt VM had a single `200G` root disk with `/` mounted on `/dev/sda1`.
- Docker was active and running.
- The Docker configuration file existed and correctly set:
  - `data-root` to `/var/lib/docker`
  - `native.cgroupdriver=systemd`
  - `json-file` logging with rotation
- The `debian` user was correctly in both `sudo` and `docker` groups.
- `/opt/docker-apps` and `/opt/compose` existed as standard directories, but were still owned by `root:root` immediately after provisioning.
- NAS mounts were present in `/etc/fstab` as CIFS systemd automount entries with `comment=cloudconfig`.
- Triggering access to `/srv/remotemount/NAS` caused the CIFS mount attempt to occur as expected.
- The initial restore issue was not a NAS failure; it was a combination of:
  - missing `rsync`
  - wrong source path
- The correct restore source path was identified as `/srv/remotemount/NAS/Backups/docker-VM/appdata`.

## Resolution
The final VM design was simplified successfully:
- cloned from template `9000`
- stored on `cephpool`
- resized to a `200G` single root disk
- configured to use the root disk for Docker storage
- `/opt/docker-apps` and `/opt/compose` kept as normal directories
- removed old Docker second-disk logic
- removed bind mounts
- removed Gluetun restart automation from cloud-init
- retained CIFS automounts for NAS access

The rebuild reached a usable state, and the correct source path for restoring application data was identified. At the end of the session, the system was ready for restore into `/opt/docker-apps`, pending completion of the `rsync` copy and ownership correction.

## Validation
Success was validated through:
- `hostnamectl` showing the expected Debian VM identity
- `lsblk` showing a single `200G` disk
- `df -h /` showing ample space on the root filesystem
- `systemctl status docker` showing Docker active/running
- `cat /etc/docker/daemon.json` showing the intended Docker daemon settings
- `id debian` and `getent group docker` confirming group membership
- `grep ... /etc/fstab` showing the expected CIFS entries generated by cloud-init
- `findmnt /srv/remotemount/NAS` confirming systemd automount behavior
- listing `/srv/remotemount/NAS` successfully showing NAS directories:
  - `Backups`
  - `Downloaders`
  - `Library`
  - `Tools`
  - `_cifs_test`

## Follow-Up Tasks
- Install `rsync` if it is still not present:
  ```bash
  sudo apt update
  sudo apt install -y rsync
  ```
- Restore appdata from:
  ```bash
  /srv/remotemount/NAS/Backups/docker-VM/appdata/
  ```
  into:
  ```bash
  /opt/docker-apps/
  ```
- Change ownership of `/opt/docker-apps` and `/opt/compose` to `debian:debian`.
- Restore Docker Compose stack files into `/opt/compose` if they are not already present.
- Bring stacks up one by one and validate volumes, permissions, and application access.
- Confirm container paths now match the new plain-directory layout under `/opt`.
- Optionally snapshot the working VM after appdata restore and initial service bring-up.

## Lessons Learned
- `--cicustom` is a `qm set` argument, not a standalone shell command.
- Cloud-init user-data is effectively one-time per VM instance; changing it later on the same VM does not automatically recreate files.
- Cloud-init network configuration is more easily reapplied than user-data.
- Duplicate `fstab` issues come from duplicate mount definitions, not from `mounts:` alone.
- `fstab` controls what filesystem appears at a path; application config controls whether the application uses that path.
- Bind mounts are useful abstraction tools, but they also add another layer to reason about during boot and troubleshooting.
- For this VM’s purpose, using a single root disk and plain `/opt` directories is operationally simpler and easier to validate.
- Always verify the exact NAS restore path before running copy operations.

---

# Command Reference

## Command
```bash
qm clone 9000 110 --name debian-docker-200g --full --storage cephpool
```

**What it does:** Clones Proxmox template `9000` into a new full VM stored on `cephpool`.  
**Why it was used:** To create the replacement Debian Docker VM from the template.  
**Important arguments:**
- `9000` = source template VMID
- `110` = destination VMID
- `--name` = assigns a VM name
- `--full` = performs a full clone instead of linked clone
- `--storage cephpool` = places disks on Ceph-backed VM storage

**Expected result:** A new VM is created from the template on `cephpool`.  
**Failure would indicate:** Wrong source template, missing storage, or clone/storage permissions issues.

## Command
```bash
qm resize 110 scsi0 200G
```

**What it does:** Resizes the VM’s main disk to `200G`.  
**Why it was used:** To give the rebuilt Docker VM a larger single root disk instead of relying on a second Docker data disk.  
**Important arguments:**
- `110` = VMID
- `scsi0` = primary disk
- `200G` = target disk size

**Expected result:** The Proxmox disk image grows to `200G`.  
**Failure would indicate:** Wrong disk identifier or storage resize limitations.  
**Risk:** Low to moderate; resizing is generally safe when expanding, but shrinking would be risky.

## Command
```bash
qm set 110 --cicustom "user=snips:snippets/docker-userdata.yml,network=snips:snippets/docker-net.yml"
```

**What it does:** Tells Proxmox to use custom cloud-init snippets for user-data and network config.  
**Why it was used:** To apply the user’s stored cloud-init YAML files from CephFS `snips` storage.  
**Important arguments:**
- `--cicustom` = custom cloud-init mapping
- `user=...` = path to user-data snippet
- `network=...` = path to network config snippet

**Expected result:** VM configuration is updated to point to the specified snippets.  
**Failure would indicate:** Wrong VMID, bad snippet path, or inaccessible snippet storage.  
**Key lesson:** `--cicustom` cannot be run by itself; it must be part of `qm set`.

## Command
```bash
qm cloudinit update 110
```

**What it does:** Regenerates the cloud-init ISO data for VM `110`.  
**Why it was used:** To make Proxmox rebuild the cloud-init drive after changing snippet assignments or content.  
**Expected result:** The VM will boot with updated cloud-init metadata.  
**Failure would indicate:** Cloud-init drive or VM configuration issues.

## Command
```bash
qm start 110
```

**What it does:** Starts the VM.  
**Why it was used:** To boot the newly cloned and configured Debian Docker VM.  
**Expected result:** VM enters running state.  
**Failure would indicate:** VM hardware config, storage attach, or guest boot problems.

## Command
```bash
hostnamectl
```

**What it does:** Shows system hostname and OS details.  
**Why it was used:** To verify the rebuilt VM identity and operating system state.  
**Expected result:** Hostname `debian-docker` and Debian 12 details are shown.

## Command
```bash
id
```

**What it does:** Shows current user and group membership.  
**Why it was used:** To confirm the active login context.

## Command
```bash
lsblk
```

**What it does:** Lists block devices and mountpoints.  
**Why it was used:** To validate that the rebuilt VM had a single `200G` disk and no second Docker data disk.  
**Expected result:** `sda` with `200G`, root on `sda1`, EFI on `sda15`.

## Command
```bash
df -h /
```

**What it does:** Shows filesystem usage for the root mount.  
**Why it was used:** To validate available space on the single root disk after resize and guest expansion.  
**Expected result:** Root filesystem shows roughly `197G` usable capacity.

## Command
```bash
findmnt /srv/remotemount/NAS /srv/remotemount/wontonsoup
```

**What it does:** Displays mount information for the NAS and secondary CIFS mountpoints.  
**Why it was used:** To confirm mount state and automount behavior.  
**Expected result:** Either automount state or active mount details are shown.

## Command
```bash
grep -E 'docker|NAS|wontonsoup' /etc/fstab || echo "no docker/NAS entries in fstab"
```

**What it does:** Searches `fstab` for relevant mount entries.  
**Why it was used:** To verify what cloud-init placed into `fstab`, especially for CIFS and any Docker-related mounts.  
**Expected result:** CIFS entries appear; no unwanted duplicate Docker mounts should exist.  
**Failure would indicate:** Missing expected mount definitions or an incorrect query pattern.

## Command
```bash
sudo systemctl status docker --no-pager
```

**What it does:** Shows Docker service state without invoking the pager.  
**Why it was used:** To verify that Docker started successfully after provisioning.  
**Expected result:** `docker.service` is loaded, enabled, and active/running.

## Command
```bash
cat /etc/docker/daemon.json
```

**What it does:** Displays Docker daemon configuration.  
**Why it was used:** To confirm `data-root` and logging settings created by cloud-init.  
**Expected result:** JSON includes `data-root: /var/lib/docker` and `native.cgroupdriver=systemd`.

## Command
```bash
getent group docker
```

**What it does:** Queries the system group database for the `docker` group.  
**Why it was used:** To confirm that the group exists and includes the `debian` user.

## Command
```bash
id debian
```

**What it does:** Shows user and group membership for the `debian` account.  
**Why it was used:** To confirm it was added to `sudo` and `docker`.

## Command
```bash
ls -ld /opt/docker-apps /opt/compose
```

**What it does:** Lists the directories and their ownership/permissions.  
**Why it was used:** To confirm the directories existed as plain directories and were not bind mounts.  
**Expected result:** Both paths exist.  
**Key finding:** They were owned by `root:root` immediately after provisioning.

## Command
```bash
ls /opt/docker-apps || echo "no appdata yet"
```

**What it does:** Lists the restored appdata directory contents if present.  
**Why it was used:** To check whether application data had already been restored.

## Command
```bash
stat /srv/remotemount/NAS >/dev/null
```

**What it does:** Touches the automount path without producing visible output.  
**Why it was used:** To trigger the systemd automount for the NAS share.  
**Expected result:** Access causes the CIFS mount to be attempted.

## Command
```bash
findmnt /srv/remotemount/NAS
```

**What it does:** Shows the current mount handling for the NAS path.  
**Why it was used:** To distinguish between autofs state and active CIFS mount state.

## Command
```bash
ls /srv/remotemount/NAS
```

**What it does:** Lists NAS share contents.  
**Why it was used:** To validate that the CIFS share mounted successfully and the expected top-level directories were visible.

## Command
```bash
apt update -y
```

**What it does:** Updates apt package indexes.  
**Why it was used:** The user attempted package maintenance after provisioning.  
**Expected result:** Package lists are refreshed.  
**Observed result:** Permission denied because it was run as the non-root `debian` user.  
**Safer/correct usage:** Use `sudo apt update`.

## Command
```bash
sudo apt update
```

**What it does:** Updates package indexes with root privileges.  
**Why it was recommended:** The `debian` user had sudo access and apt requires root.

## Command
```bash
sudo apt upgrade
```

**What it does:** Upgrades installed packages.  
**Why it was recommended:** To continue package maintenance after a successful update.  
**Risk:** Moderate; package upgrades can change service behavior.

## Command
```bash
sudo -i
```

**What it does:** Opens a root login shell.  
**Why it was recommended:** As an alternative to prefixing each admin command with `sudo`.  
**Risk:** Moderate; remaining in a root shell increases the chance of accidental destructive commands.

## Command
```bash
sudo apt install -y rsync
```

**What it does:** Installs `rsync`.  
**Why it was recommended:** The restore workflow depended on `rsync`, but the package was missing.  
**Expected result:** `rsync` becomes available for backup restoration.

## Command
```bash
sudo rsync -avh /srv/remotemount/NAS/Backups/docker-apps-backup/ /opt/docker-apps/
```

**What it does:** Copies a backup tree into `/opt/docker-apps/` while preserving metadata and showing progress-like verbose output.  
**Why it was attempted:** To restore application data from the NAS.  
**Observed result:** Failed because the path did not exist.  
**Important flags:**
- `-a` = archive mode, preserve metadata
- `-v` = verbose
- `-h` = human-readable numbers

**Failure indicated:** Incorrect NAS source path, not a problem with the destination directory itself.

## Command
```bash
ls /srv/remotemount/NAS
ls /srv/remotemount/NAS/Backups
ls /srv/remotemount/NAS/Backups/*
```

**What it does:** Enumerates candidate backup locations under the NAS path.  
**Why it was recommended:** To discover the correct restore source path after the first `rsync` failed.  
**Expected result:** Reveal the actual backup folder structure.

## Command
```bash
sudo rsync -avh /srv/remotemount/NAS/Backups/docker-VM/appdata/ /opt/docker-apps/
```

**What it does:** Restores the contents of the identified `appdata` backup directory into `/opt/docker-apps/`.  
**Why it was recommended:** This was the corrected NAS source path based on the user’s confirmation.  
**Expected result:** Folders such as application config directories are copied directly into `/opt/docker-apps/`.  
**Important note:** The trailing slash on `appdata/` means “copy the contents of this directory,” not the directory itself.

## Command
```bash
sudo chown -R debian:debian /opt/docker-apps /opt/compose
```

**What it does:** Recursively assigns ownership of the appdata and compose directories to the `debian` user and group.  
**Why it was recommended:** To align ownership with the user account and common container `PUID=1000` / `PGID=1000` patterns.  
**Risk:** Moderate; recursive ownership changes should be targeted carefully.

## Command
```bash
sudo cp -a /srv/remotemount/NAS/Backups/docker-apps-backup/. /opt/docker-apps/
```

**What it does:** Alternative copy method using `cp -a` to preserve metadata.  
**Why it was suggested:** As a fallback if the user did not want to install `rsync`.  
**Important note:** The `.` after the source path copies the contents of the directory.  
**Risk:** Slightly less informative than `rsync`; no built-in resume behavior.

## Command
```bash
cd /opt/compose/<your_stack>
docker compose up -d
```

**What it does:** Enters a compose stack directory and starts the stack in detached mode.  
**Why it was recommended:** To validate restored configuration and bring services back online after appdata restoration.  
**Expected result:** Containers start in the background.  
**Failure would indicate:** Missing compose files, bad paths, permission problems, or application-specific misconfiguration.

## Command
```bash
Likely command used: pvesm list snips | grep snippets
```

**What it does:** Lists files available in the `snips` Proxmox storage and filters for snippet entries.  
**Why it was relevant:** To verify that cloud-init YAML files placed in CephFS `snips` storage are visible to Proxmox.  
**Expected result:** The snippet filenames appear in the output.

## Command
```bash
Likely command used: cp /var/lib/vz/snippets/docker-userdata.yml /mnt/pve/snips/snippets/
```

**What it does:** Copies a local snippet into CephFS-backed `snips` storage.  
**Why it was relevant:** The user asked where the snippet directory is for CephFS `snips`.  
**Expected result:** The YAML becomes available from `snips:snippets/...` for cloud-init usage.
