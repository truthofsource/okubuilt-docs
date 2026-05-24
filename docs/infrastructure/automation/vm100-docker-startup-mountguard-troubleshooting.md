---
title: "VM 100 Docker Startup Failure After Mount/Guard Changes"
track: "infrastructure"
category: "automation"
type: "runbook"
logical_order: 80
date_rule: "Dates are removed from filenames, visible headings, indexes, generated metadata, and runbook body content."
---

# VM 100 Docker Startup Failure After Mount/Guard Changes

## Summary
Work was performed on **VM 100 (`debian-docker`)** to restore Docker after recent mount-guard and cloud-init cleanup changes. The main issue was that Docker did not start because its systemd dependency chain referenced a missing guard unit. After Docker was restored, additional validation showed that the `/opt/docker-apps` and `/opt/compose` bind mounts were active, but there were follow-up concerns about whether containers were using the intended appdata paths. Later in the same session, a reboot caused Docker to fail to come back automatically, indicating the boot-time dependency and mount ordering still needed further hardening.

## Environment
- **Virtualization platform:** Proxmox VE
- **VM:** VM 100
- **Hostname:** `debian-docker`
- **Guest OS:** Debian
- **Container runtime:** Docker Engine Community 28.5.2
- **Docker API version:** 1.51
- **Storage layout:**
  - `/var/lib/docker` mounted on a dedicated ext4 disk
  - Expected UUID: `6ce44029-6b4b-4fe4-a78e-bec4402a0444`
  - Filesystem label also present: `docker-data`
- **Bind mount design:**
  - `/var/lib/docker/appdata` → `/opt/docker-apps`
  - `/var/lib/docker/compose` → `/opt/compose`
- **Remote storage:**
  - CIFS mounts under `/srv/remotemount/NAS` and `/srv/remotemount/wontonsoup`
- **Container management:** Docker Compose stacks under `/opt/compose`
- **Related services/containers observed:**
  - `traefik`
  - `dockersocket`
  - `radarr`, `sonarr`, `lidarr`, `readarr`, `bazarr`, `prowlarr`
  - `sabnzbd-vpn`, `qbittorrent-vpn`, `deluge-vpn`, `gluetun`
  - `plexms`, `tautulli`, `overseerr`
  - `flaresolverr`, `whoogle-search`, `uptime-kuma`, `komf`
  - multiple productivity/media stacks

## Problem
Docker commands such as `docker info` stalled and the Docker daemon did not come up reliably after mount/guard-related changes. Even after Docker was manually restored, there were concerns that containers may not have been using the intended appdata bind mounts, and a subsequent reboot caused Docker to fail again.

## Symptoms
- `docker info --format 'DockerRootDir={{.DockerRootDir}}'` stalled and returned nothing.
- `timeout 5 docker version` showed Docker client information, followed by:

```text
daemon not responding
```

- `systemctl status docker` showed:

```text
Active: inactive (dead)
```

- Repeated systemd failures:

```text
Dependency failed for docker.service - Docker Application Container Engine.
docker.service: Job docker.service/start failed with result 'dependency'.
```

- Missing guard unit:

```text
Unit docker-verify.mountguard.service could not be found.
```

- `/etc/fstab` on the live system still referenced:

```text
LABEL=docker-data /var/lib/docker ext4 ...
```

  even though the active cloud-init YAML used a UUID-based mount.

- `mount` reported:

```text
/var/lib/docker: /dev/sda already mounted or mount point busy.
```

- systemd warning after editing `/etc/fstab`:

```text
your fstab has been modified, but systemd still uses the old version; use 'systemctl daemon-reload' to reload.
```

- After Docker was restored, the user observed that containers appeared up but not obviously using the expected appdata paths.
- Later, after rebooting the VM, Docker again failed to come back automatically.
- Separate application-level symptom:

```text
PermissionError: [Errno 13] Permission denied: '/usenet-downloads/complete'
```

  in SABnzbd, with similar behavior in qBittorrent.

## Actions Taken
1. Confirmed that the Docker client was installed and the problem was daemon-side, not CLI-side.
2. Collected systemd status and journal output for:
   - `docker.service`
   - `docker.socket`
   - `docker-verify.mountguard`
3. Checked live storage and mount state with:
   - `lsblk -f`
   - `findmnt /var/lib/docker`
   - `grep` of `/etc/fstab`
4. Identified a mismatch between the **intended cloud-init configuration** and the **live system state**:
   - cloud-init YAML mounted `/var/lib/docker` by **UUID**
   - live `/etc/fstab` mounted `/var/lib/docker` by **LABEL**
5. Reviewed the current cloud-init YAML, which included:
   - UUID-based Docker data mount
   - a verification script at `/usr/local/sbin/verify-docker-data.sh`
   - `docker-verify.mountguard.service`
   - a Docker systemd override requiring the guard and mount paths
6. Determined that Docker was blocked because systemd expected `docker-verify.mountguard.service`, but the unit was missing on the running system.
7. Recreated the Docker verification script using the expected UUID.
8. Attempted to align `/etc/fstab` from `LABEL=docker-data` to the UUID-based mount entry.
9. Recreated or restored the guard unit and Docker override.
10. Reloaded systemd and restarted relevant services.
11. Verified that Docker eventually came back and that `/var/lib/docker` was mounted:

```text
/var/lib/docker /dev/sda ext4 rw,relatime,discard
DockerRootDir=/var/lib/docker
```

12. Confirmed many containers were running again with `docker ps -a`.
13. Investigated whether containers were using the intended appdata by checking bind mounts and automount units.
14. Triggered `/opt/docker-apps` and `/opt/compose` automounts by accessing those paths.
15. Performed a bind test by creating `.bindtest` files under `/opt/docker-apps` and `/opt/compose` and confirming they appeared under:
    - `/var/lib/docker/appdata`
    - `/var/lib/docker/compose`
16. Concluded that the bind mounts were active.
17. Considered ownership correction on appdata paths, but the user chose not to apply it because the system appeared to be working.
18. Documented the follow-up issue that Docker still failed to return automatically after a reboot, indicating the boot ordering problem was not fully resolved.
19. Noted a separate permission issue affecting SABnzbd and qBittorrent download paths, but that issue was not fully resolved in this session.

## Key Findings
- The Docker CLI was healthy; the daemon was not starting.
- The root cause of the first outage was **systemd dependency failure**, not Docker engine corruption.
- Docker was blocked because:
  - `docker.service` depended on `docker-verify.mountguard.service`
  - that unit was **missing**
- The current cloud-init YAML was **UUID-based**, but the live `/etc/fstab` initially still used `LABEL=docker-data`.
- `/var/lib/docker` itself was successfully mounted on the dedicated ext4 disk once the system was corrected.
- The `/opt/docker-apps` and `/opt/compose` paths were managed with `x-systemd.automount`, which meant they were not mounted until first access.
- The bind mount test confirmed:
  - `/opt/docker-apps` correctly mapped to `/var/lib/docker/appdata`
  - `/opt/compose` correctly mapped to `/var/lib/docker/compose`
- Containers being "up" did not automatically prove they were using the intended host paths; mount validation was necessary.
- The environment still had unresolved boot-order reliability problems after reboot.
- Application-level permission failures on download directories likely involved CIFS mount permissions, NAS ACLs, or container UID/GID expectations, but that investigation remained incomplete.

## Resolution
### Restored during the session
- Docker was manually restored by:
  - recreating the Docker data verification script
  - restoring the missing `docker-verify.mountguard.service`
  - reloading systemd
  - aligning the intended mount strategy toward the UUID-based configuration
  - restarting Docker and related units
- Docker resumed normal operation and containers started again.
- Bind mounts for appdata and compose storage were validated as active.

### Current status at end of session
- **Docker was running**
- **Containers were running**
- **Bind mounts were confirmed active**
- **Automatic startup after reboot was still not fully fixed**
- **SABnzbd/qBittorrent permission issues were still open**

## Validation
Success during the live recovery was confirmed by:
- Docker root directory returning successfully:

```bash
docker info --format 'DockerRootDir={{.DockerRootDir}}'
```

- Docker showing active containers:

```bash
docker ps -a --format 'table {{.Names}}\t{{.Status}}'
```

- `/var/lib/docker` shown as mounted on the dedicated ext4 disk:

```bash
findmnt /var/lib/docker
```

- Automount units shown active:

```bash
systemctl status opt-docker\x2dapps.automount opt-compose.automount
```

- Bind test files created under `/opt/...` appearing under `/var/lib/docker/...`, confirming the bind relationship.

## Follow-Up Tasks
- Fix Docker boot reliability after VM reboot.
- Verify that `docker-verify.mountguard.service` persists correctly across reboots.
- Confirm the final `/etc/fstab` entry for `/var/lib/docker` matches the chosen strategy:
  - either UUID-based everywhere
  - or label-based everywhere
- Re-check `systemctl cat docker` to confirm the final override is correct.
- Decide whether `RequiresMountsFor=/opt/docker-apps /opt/compose` should remain, or whether automount-only behavior is preferable.
- Validate that key Compose stacks are using bind mounts instead of anonymous Docker volumes.
- Resolve CIFS/NAS permissions for:
  - `/usenet-downloads/complete`
  - qBittorrent download paths
- Confirm container UID/GID expectations against CIFS mount options and NAS permissions.
- Test a clean reboot after final boot-order changes.

## Lessons Learned
- If `docker info` hangs but the client responds, check `docker.service` and its systemd dependency chain first.
- A missing systemd dependency can completely block Docker startup while leaving `docker.socket` active.
- Cloud-init intent and live `/etc/fstab` state can drift; both must be checked.
- Using a UUID in one place and a label in another increases confusion during recovery.
- `x-systemd.automount` can make bind mounts appear absent until they are first accessed.
- A successful container start does not prove that intended host paths are in use.
- For Docker-on-VM storage layouts, validating mounts is as important as validating the Docker daemon itself.
- Reboot behavior must be tested after storage and systemd dependency changes; a live recovery is not enough.

---

# Command Reference

## Command
```bash
timeout 5 docker version || echo "daemon not responding"
```

**What it does:**  
Runs `docker version` but limits it to 5 seconds.

**Flags and arguments:**  
- `timeout 5` stops the command after 5 seconds.
- `|| echo ...` prints a message if the command times out or fails.

**Why it was used:**  
To determine whether the Docker client worked while the daemon was unresponsive.

**Expected result:**  
Client information prints quickly. If the daemon is unavailable, the command times out.

**What success or failure indicates:**  
- Client output plus timeout message means the Docker CLI works, but the daemon is not responding.
- Full output means the daemon is reachable.

**Risk:** Low.

---

## Command
```bash
systemctl status docker -n 50 --no-pager
```

**What it does:**  
Shows recent status and logs for `docker.service`.

**Flags and arguments:**  
- `-n 50` shows the last 50 log lines.
- `--no-pager` prints directly to the terminal.

**Why it was used:**  
To see whether Docker was running and why it failed.

**Expected result:**  
Either an active service or clear dependency/startup errors.

**What success or failure indicates:**  
- `active (running)` means daemon is up.
- `inactive (dead)` or dependency errors mean startup path is still broken.

**Risk:** Low.

---

## Command
```bash
systemctl status docker.socket --no-pager
```

**What it does:**  
Shows whether Docker socket activation is enabled and listening.

**Why it was used:**  
To separate socket availability from actual daemon availability.

**Expected result:**  
Socket may be active even when `docker.service` is down.

**What success or failure indicates:**  
- Active socket plus dead service means the socket exists, but the daemon is blocked.
- Both down indicates a broader Docker startup failure.

**Risk:** Low.

---

## Command
```bash
systemctl status docker-verify.mountguard --no-pager
```

**Likely command used:**  
The actual unit name may have been `docker-verify.mountguard.service`.

**What it does:**  
Checks the status of the mount verification unit.

**Why it was used:**  
Docker depended on this unit.

**Expected result:**  
The unit should exist and succeed before Docker starts.

**What success or failure indicates:**  
- Success means the guard passed.
- Missing unit means Docker dependency failure.
- Failed unit means mount or UUID/label mismatch.

**Risk:** Low.

---

## Command
```bash
journalctl -u docker -b --no-pager | tail -n 200
```

**What it does:**  
Shows Docker logs from the current boot.

**Flags and arguments:**  
- `-u docker` filters to Docker service logs.
- `-b` restricts to the current boot.
- `tail -n 200` shows the last 200 lines.

**Why it was used:**  
To identify repeated startup errors and dependency failures.

**Expected result:**  
Systemd and Docker daemon log lines related to startup.

**What success or failure indicates:**  
Repeated `Dependency failed` messages pointed to a unit/dependency issue, not a container issue.

**Risk:** Low.

---

## Command
```bash
journalctl -u docker-verify.mountguard -b --no-pager | tail -n 200
```

**What it does:**  
Shows logs for the guard unit from the current boot.

**Why it was used:**  
To confirm whether the guard existed and whether it passed or failed.

**Expected result:**  
Guard validation output or a missing-unit condition.

**What success or failure indicates:**  
- Success means Docker data mount validation passed.
- Failure means wrong mount, wrong device, or non-mountpoint.
- No entries or missing unit means dependency target absent.

**Risk:** Low.

---

## Command
```bash
lsblk -f | grep -E 'sdb|6ce44029-6b4b-4fe4-a78e-bec4402a0444'
```

**What it does:**  
Lists block devices and filters for the relevant device or UUID.

**Why it was used:**  
To identify which disk held the Docker ext4 filesystem.

**Expected result:**  
A line showing the device, filesystem type, label, and UUID.

**What success or failure indicates:**  
- Matching UUID present means the expected Docker data disk exists.
- No match means disk/UUID mismatch or wrong assumption.

**Risk:** Low.

---

## Command
```bash
findmnt /var/lib/docker
```

**What it does:**  
Shows the live mount backing `/var/lib/docker`.

**Why it was used:**  
To confirm whether Docker’s data root was actually mounted.

**Expected result:**  
The source device, mountpoint, filesystem type, and options.

**What success or failure indicates:**  
- Mounted means Docker storage path exists.
- Not mounted means guard and Docker should fail.

**Risk:** Low.

---

## Command
```bash
grep -nE 'UUID=6ce44029-6b4b-4fe4-a78e-bec4402a0444|/var/lib/docker|/opt/(docker-apps|compose)' /etc/fstab
```

**What it does:**  
Searches `/etc/fstab` for Docker storage and bind mount entries.

**Why it was used:**  
To compare intended mount configuration with live system state.

**Expected result:**  
Entries for `/var/lib/docker`, `/opt/docker-apps`, and `/opt/compose`.

**What success or failure indicates:**  
- UUID entry means mount configured by UUID.
- LABEL entry means mount configured by label.
- Duplicate or conflicting lines indicate possible boot problems.

**Risk:** Low.

---

## Command
```bash
docker info --format 'DockerRootDir={{.DockerRootDir}}'
```

**What it does:**  
Queries Docker for its configured root directory.

**Why it was used:**  
To confirm that Docker was using `/var/lib/docker`.

**Expected result:**  
`DockerRootDir=/var/lib/docker`

**What success or failure indicates:**  
- Correct output means daemon is up and using expected root.
- Hanging or blank output means daemon is not responding or not fully started.

**Risk:** Low.

---

## Command
```bash
sudo sed -i 's|^LABEL=docker-data[[:space:]]\+/var/lib/docker[[:space:]]\+ext4|UUID=6ce44029-6b4b-4fe4-a78e-bec4402a0444 /var/lib/docker ext4|' /etc/fstab
```

**What it does:**  
Edits `/etc/fstab` in place to replace a label-based Docker data mount with a UUID-based one.

**Flags and arguments:**  
- `sed -i` edits the file directly.

**Why it was used:**  
To align the live system with the cloud-init YAML and guard logic.

**Expected result:**  
The `/var/lib/docker` line in `/etc/fstab` changes from `LABEL=` to `UUID=`.

**What success or failure indicates:**  
- Correct replacement means live config aligned with intended config.
- No change means pattern mismatch or already corrected.

**Risk:** Medium.  
Editing `/etc/fstab` incorrectly can break boot or mount behavior.

**Safer alternative:**  
Back up `/etc/fstab` before editing.

---

## Command
```bash
sudo tee /usr/local/sbin/verify-docker-data.sh >/dev/null <<'EOF'
#!/bin/bash
set -euo pipefail
EXPECTED_UUID="6ce44029-6b4b-4fe4-a78e-bec4402a0444"
MP="/var/lib/docker"
if ! mountpoint -q "$MP"; then
  echo "ERROR: $MP is not a mountpoint." >&2; exit 1
fi
DEV="$(findmnt -no SOURCE "$MP" || true)"
UUID="$(blkid -s UUID -o value "$DEV" || true)"
if [ "$UUID" != "$EXPECTED_UUID" ]; then
  echo "ERROR: $MP is on $DEV (UUID=$UUID), expected UUID=$EXPECTED_UUID." >&2
  exit 2
fi
EOF
```

**What it does:**  
Creates a shell script that validates that `/var/lib/docker` is a mountpoint backed by the expected UUID.

**Why it was used:**  
To prevent Docker from starting on the wrong storage path.

**Expected result:**  
A guard script is created successfully.

**What success or failure indicates:**  
- Exit 0 means mount is correct.
- Exit 1 means `/var/lib/docker` is not mounted.
- Exit 2 means wrong device/UUID.

**Risk:** Medium.  
This can intentionally block Docker startup if storage is not exactly as expected.

---

## Command
```bash
sudo systemctl daemon-reload
```

**What it does:**  
Reloads systemd unit definitions and regenerated mount interpretations from `/etc/fstab`.

**Why it was used:**  
Because `/etc/fstab` and systemd unit files were modified.

**Expected result:**  
No output or a clean return.

**What success or failure indicates:**  
Without this step, systemd may still use stale mount and service definitions.

**Risk:** Low.

---

## Command
```bash
sudo systemctl enable --now docker-verify.mountguard.service
```

**What it does:**  
Enables the guard service to start at boot and starts it immediately.

**Why it was used:**  
To restore the missing dependency and test it live.

**Expected result:**  
The service enables and runs successfully.

**What success or failure indicates:**  
- Success means guard exists and passed.
- Failure means missing mount, wrong device, or broken service file.

**Risk:** Low to medium.  
If the guard fails, Docker remains blocked.

---

## Command
```bash
sudo systemctl restart docker.socket
sudo systemctl start docker
```

**What it does:**  
Restarts the Docker socket unit and starts the Docker daemon.

**Why it was used:**  
To bring Docker back after dependency and mount corrections.

**Expected result:**  
`docker.service` becomes active.

**What success or failure indicates:**  
- Success means Docker restored.
- Failure means remaining dependency or mount issue.

**Risk:** Low.

---

## Command
```bash
docker ps -a --format 'table {{.Names}}\t{{.Status}}'
```

**What it does:**  
Lists all containers with their names and statuses.

**Why it was used:**  
To verify that containers returned after Docker recovery.

**Expected result:**  
A table showing containers as `Up`, `Exited`, or `Restarting`.

**What success or failure indicates:**  
- Many `Up` containers means Docker recovery succeeded.
- `Restarting` or `Exited` means container-level follow-up is needed.

**Risk:** Low.

---

## Command
```bash
systemctl status opt-docker\x2dapps.automount opt-compose.automount --no-pager
```

**What it does:**  
Checks the automount units for `/opt/docker-apps` and `/opt/compose`.

**Why it was used:**  
Those paths were bind-mounted using automount semantics.

**Expected result:**  
Active automount units.

**What success or failure indicates:**  
- Active automounts mean first access should trigger the mounts.
- Missing or inactive means bind paths may not activate automatically.

**Risk:** Low.

---

## Command
```bash
sudo bash -lc 'stat /opt/docker-apps >/dev/null; stat /opt/compose >/dev/null'
```

**What it does:**  
Accesses the `/opt` paths to trigger their automounts.

**Why it was used:**  
Because `x-systemd.automount` only mounts them on first access.

**Expected result:**  
No output; automounts should become active.

**What success or failure indicates:**  
- Successful access means the automount trigger executed.
- Failure means path or mount issue.

**Risk:** Low.

---

## Command
```bash
findmnt /opt/docker-apps /opt/compose /var/lib/docker/appdata /var/lib/docker/compose
```

**What it does:**  
Shows the live mount relationships for the appdata and compose bind paths.

**Why it was used:**  
To verify whether the intended bind mounts were actually active.

**Expected result:**  
Mount information for both `/opt` paths and their backing paths.

**What success or failure indicates:**  
- Mounted means bind path active.
- Missing means containers may not be using intended host storage.

**Risk:** Low.

---

## Command
```bash
sudo bash -lc 'touch /opt/docker-apps/.bindtest && ls -la /var/lib/docker/appdata | grep bindtest'
```

**What it does:**  
Creates a test file under `/opt/docker-apps` and verifies it appears in `/var/lib/docker/appdata`.

**Why it was used:**  
To prove the bind mount relationship rather than only trusting unit state.

**Expected result:**  
The `.bindtest` file is visible in the backing directory.

**What success or failure indicates:**  
- File visible means bind mount is active.
- File absent means bind mount is not active or mapped elsewhere.

**Risk:** Low.

---

## Command
```bash
sudo bash -lc 'touch /opt/compose/.bindtest && ls -la /var/lib/docker/compose | grep bindtest'
```

**What it does:**  
Creates a test file under `/opt/compose` and verifies it appears in `/var/lib/docker/compose`.

**Why it was used:**  
To validate the Compose directory bind mount.

**Expected result:**  
The `.bindtest` file appears in the backing directory.

**What success or failure indicates:**  
- Present means the bind is active.
- Missing means the bind issue remains.

**Risk:** Low.

---

## Command
```bash
findmnt -no SOURCE /var/lib/docker
blkid -s UUID -o value "$(findmnt -no SOURCE /var/lib/docker)"
```

**What it does:**  
Finds the device behind `/var/lib/docker` and reads its UUID.

**Why it was used:**  
To compare the live backing device with the expected UUID.

**Expected result:**  
A source device path and the expected UUID value.

**What success or failure indicates:**  
- Matching UUID means Docker data is on the intended disk.
- Different UUID means guard mismatch or wrong storage path.

**Risk:** Low.

---

## Command
```bash
systemctl cat docker | grep -E 'RequiresMountsFor|docker-verify.mountguard|ConditionPathIsMountPoint'
```

**Likely command used:**  
This was discussed as a validation step for the final override.

**What it does:**  
Shows the effective Docker systemd unit and filters for mount-related directives.

**Why it was used:**  
To confirm that Docker’s startup behavior matched the intended design.

**Expected result:**  
Lines showing mount and guard dependencies.

**What success or failure indicates:**  
- Expected directives present means the override loaded correctly.
- Missing directives mean Docker may not be protected on boot.

**Risk:** Low.

---

## Command
```bash
docker inspect -f '{{range .Mounts}}{{printf "%-12s %-60s -> %s\n" .Type .Source .Destination}}{{end}}' sabnzbd-vpn
```

**Likely command used:**  
A similar mount inspection command was proposed for SABnzbd and qBittorrent.

**What it does:**  
Shows container mount types, sources, and destinations.

**Why it was used:**  
To verify whether download paths were bind-mounted correctly.

**Expected result:**  
Bind mounts to the intended CIFS-backed paths.

**What success or failure indicates:**  
- `bind` mount to expected path means Docker side is correct.
- `volume` or unexpected path means container is not using intended storage.

**Risk:** Low.

---

## Command
```bash
findmnt /srv/remotemount/NAS
```

**Likely command used:**  
This was proposed for the SABnzbd/qBittorrent permissions issue.

**What it does:**  
Checks whether the NAS CIFS share is mounted.

**Why it was used:**  
Download path permission errors may be caused by the NAS share not being mounted or mounted incorrectly.

**Expected result:**  
A live mount entry for the NAS path.

**What success or failure indicates:**  
- Mounted means proceed to permissions/ACL checks.
- Not mounted means Docker containers may be writing to the wrong local path or failing outright.

**Risk:** Low.

---

## Command
```bash
sudo -u '#1000' bash -lc 'touch /srv/remotemount/NAS/Downloaders/SABnzbd/downloads/complete/.permtest'
```

**Likely command used:**  
A similar UID-based write test was proposed.

**What it does:**  
Tests whether UID 1000 can write to the CIFS-mounted download directory.

**Why it was used:**  
LinuxServer-style containers commonly run as `PUID=1000`, so host-side testing with that UID is a direct way to validate write permissions.

**Expected result:**  
A test file is created successfully.

**What success or failure indicates:**  
- Success means host-side permissions are likely correct.
- Permission denied means NAS ACL, CIFS options, or ownership issue.

**Risk:** Low.

---

## Command
```bash
docker exec -u 1000 sabnzbd-vpn sh -lc 'touch /usenet-downloads/complete/.writetest && echo OK && rm -f /usenet-downloads/complete/.writetest'
```

**Likely command used:**  
A similar in-container permission test was proposed.

**What it does:**  
Tests whether the application container can write to its mapped download directory as UID 1000.

**Why it was used:**  
To confirm that the permission problem existed from the container’s perspective, not just the host’s.

**Expected result:**  
The file is created and then removed, printing `OK`.

**What success or failure indicates:**  
- Success means container can write.
- Failure means volume mapping or permissions are still wrong.

**Risk:** Low.

---

## Command
```bash
sudo chown -R 1000:1000 /var/lib/docker/appdata /var/lib/docker/compose
```

**What it does:**  
Changes ownership of the appdata and compose directories to UID/GID 1000.

**Why it was discussed:**  
As a possible fix for permission mismatches on bind-mounted paths.

**Expected result:**  
Directories become owned by the Docker app user/group.

**What success or failure indicates:**  
May resolve container write failures if UID/GID mismatch was the cause.

**Risk:** Medium.  
Recursive ownership changes can be disruptive if some data is intentionally owned by other users or services.

**Safer alternative:**  
Inspect ownership first with `stat` or `ls -la`, and change only affected subdirectories.
