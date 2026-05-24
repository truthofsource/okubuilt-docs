---
title: "Restore `/opt/docker-apps` from Offen Backup"
track: "infrastructure"
category: "containers-apps"
type: "runbook"
logical_order: 30
date_rule: "Dates are removed from filenames, visible headings, indexes, generated metadata, and runbook body content."
---

# Restore `/opt/docker-apps` from Offen Backup

## Summary
Restored the Docker application data tree at `/opt/docker-apps` from an Offen backup archive after JSON, YAML, and other configuration files were accidentally deleted. The restore was done as a full tree overlay, not as a restore of a single app called “Offen.”

## Environment
- Host/VM context:
  - Debian Docker VM: `debian-docker`
  - Proxmox VM ID referenced elsewhere in the session: VM 110
- Backup source:
  - NAS-mounted CIFS path: `/srv/remotemount/NAS/Tools/Backups/Docker/offen/backup-[date removed].tar.gz`
- Restore target:
  - `/opt/docker-apps`
- Relevant tooling:
  - `tar`
  - `rsync`
  - `find`
  - `chown`
  - Docker / Docker Compose
- Related app directories observed under `/opt/docker-apps`:
  - `Traefik`, `Dockge`, `Plex`, `qBittorrent`, `Deluge`, `Overseerr`, `Tautulli`, `Kometa`, `SABnzbd`, `Prowlarr`, `Sonarr`, `Radarr`, and others
- Storage/mount context:
  - NAS mounted over CIFS
  - Local application data stored under `/opt/docker-apps`

## Problem
Important configuration files under `/opt/docker-apps` had been accidentally deleted. The missing files were confirmed to still exist inside an Offen backup archive on the NAS.

## Symptoms
- Missing JSON, YAML, and related app configuration files under `/opt/docker-apps`
- Need to restore the entire `docker-apps` tree, not a folder named `Offen`
- Need to preserve app directory layout and permissions for Docker-managed services such as Dockge and Compose-managed stacks

## Actions Taken
1. Confirmed the restore target was the full `/opt/docker-apps` tree.
2. Reused an already extracted backup payload located under:
   ```bash
   /opt/docker-apps/backup/my-app-backup/
   ```
   and moved its contents into `/opt/docker-apps`.
3. Cleaned up empty wrapper directories left behind after flattening the extracted backup structure.
4. Reset ownership of `/opt/docker-apps` to `debian:debian`.
5. Verified restored top-level app directories under `/opt/docker-apps`.
6. Built a safer repeatable restore workflow using:
   - backup archive variable
   - destination variable
   - staging directory
   - `rsync` merge from `backup/my-app-backup/` into `/opt/docker-apps/`
7. Created a pre-restore snapshot tarball under:
   ```bash
   /opt/docker-apps/.pre-restore/
   ```
8. Extracted the Offen archive to a temporary local staging directory and re-applied the backup onto `/opt/docker-apps`.
9. Re-ran `chown -R debian:debian /opt/docker-apps` after the restore.

Important commands used:

```bash
sudo rsync -a --remove-source-files /opt/docker-apps/backup/my-app-backup/ /opt/docker-apps/
```
Purpose: flatten previously extracted backup contents into the live appdata tree.

```bash
sudo find /opt/docker-apps/backup/my-app-backup -type d -empty -delete
sudo rmdir -p /opt/docker-apps/backup/my-app-backup 2>/dev/null || true
```
Purpose: remove empty wrapper directories left after the file move.

```bash
sudo chown -R debian:debian /opt/docker-apps
```
Purpose: restore writable ownership for Dockge and other app config paths.

```bash
sudo tar -xzpf "$ARCH" -C "$STAGE"
```
Purpose: extract the Offen backup into a staging directory.

```bash
sudo rsync -aHAX --checksum --inplace "$STAGE/backup/my-app-backup/" "$DEST/"
```
Purpose: overlay the backup contents onto the live `/opt/docker-apps` tree.

## Key Findings
- The Offen archive structure was rooted at:
  ```text
  /backup/my-app-backup/...
  ```
  so restore operations had to copy the *contents* of `my-app-backup/` into `/opt/docker-apps/`.
- The restore was not for an app named `Offen`; Offen was only the backup tool and the backup file naming context.
- Trailing slashes on `rsync` source and destination paths were critical to avoid creating an unwanted nested directory.
- The pre-restore tar command produced:
  ```text
  tar: ./.pre-restore/full-pre-restore-[date removed]-17_181715.tgz: file changed as we read it
  ```
  because the snapshot file was being written inside the directory being archived.
- The restore logic itself was sound; the warning applied to the snapshot tar operation, not the Offen restore.

## Resolution
The full `/opt/docker-apps` tree was restored by overlaying the backup contents from `backup/my-app-backup/` into `/opt/docker-apps`, followed by resetting ownership to `debian:debian`.

## Validation
Validation was performed by:
- Confirming expected top-level app directories existed under `/opt/docker-apps`
- Listing restored directories such as:
  - `/opt/docker-apps/Traefik/config`
  - `/opt/docker-apps/Dockge/config`
  - `/opt/docker-apps/Plex/config`
- Checking directory size and structure:
  ```bash
  du -sh /opt/docker-apps
  find /opt/docker-apps -maxdepth 2 -type d | sed -n '1,60p'
  ```
- Verifying that a later re-application of the same backup with `rsync` completed successfully

## Follow-Up Tasks
- Consider storing pre-restore safety archives *outside* `/opt/docker-apps` to avoid tar self-inclusion warnings.
- Keep a reusable local staging path for this backup if repeat restores are expected.
- Spot-check critical application config files under:
  - `Traefik/config`
  - `Dockge/config`
  - other restored app paths that had known deleted files
- Start and validate application stacks one by one after restore.

## Lessons Learned
- Offen backup restores should be treated as filesystem tree restores, not app-specific restores.
- Reusing a previously extracted backup payload can save time if its structure is already known and trusted.
- `rsync` with trailing slashes is safer than ad hoc copy/move operations when restoring nested trees.
- Ownership repair is often required after bulk restores so app management tools can write their configs again.
- Saving a snapshot tarball inside the directory being archived is noisy and can be misleading; use an external snapshot location when possible.

---

# Host Instability During NAS-to-NAS CIFS Staging

## Summary
Attempted to optimize future restores by extracting the Offen backup to a reusable staging directory on the NAS itself. This correlated with repeated host/node lockups severe enough that the Proxmox node became unreachable from the cluster and required a power cycle.

## Environment
- Proxmox node: `pve1`
- Same physical machine also hosted the Debian Docker VM performing the restore work
- Relevant VM:
  - VM 110
- NAS path used for staging:
  - `/srv/remotemount/NAS/Tools/Backups/Docker/offen/stage-[date removed]`
- Archive source:
  - `/srv/remotemount/NAS/Tools/Backups/Docker/offen/backup-[date removed].tar.gz`
- Storage/network context:
  - CIFS-mounted NAS
  - Large archive extraction with many small file writes back to CIFS
- Cluster context:
  - Proxmox cluster quorum services on `pve1`
  - Other nodes reported `pve1` as offline during the hang

## Problem
Extracting the backup archive from the NAS back onto a staging directory on the same NAS caused repeated instability. The node became unreachable from the GUI and from the rest of the cluster and had to be power-cycled.

## Symptoms
- During `tar -xzpf` extraction to NAS staging, connection dropped
- Clarified later that this was not just SSH loss:
  - the whole node/host went offline
  - GUI stopped loading
  - node showed offline to the other cluster nodes
- Required physical power cycle to recover
- CIFS-related messages appeared when the staging path was accessed:
  ```text
  CIFS: Attempting to mount \\192.168.16.21\Media
  ```
- When extracting to NAS stage, `tar` also hit:
  ```text
  backup/my-app-backup/DoubleCommander/config/.XDG/doublecmd.pipe: Cannot mkfifo: Operation not permitted
  ```
  which was related to CIFS not supporting FIFO creation for that runtime pipe

## Actions Taken
1. Removed old temporary local staging directory:
   ```bash
   sudo rm -rf /tmp/offen-stage-*
   ```
2. Attempted to create a reusable staging directory directly on the NAS:
   ```bash
   sudo mkdir -p "$NAS_STAGE"
   ```
3. Attempted to extract the Offen archive to the NAS stage:
   ```bash
   sudo tar -xzpf "$ARCH" -C "$NAS_STAGE"
   ```
4. Observed CIFS mount activity and FIFO creation errors.
5. Considered excluding the problematic `.XDG` pipe path from extraction.
6. After repeated node hangs, re-evaluated the strategy and concluded NAS-to-NAS staging was not worth the risk.
7. Reviewed prior-boot logs from `pve1` after recovery to look for evidence of the failure.

Important commands used:

```bash
sudo rm -rf /tmp/offen-stage-*
```
Purpose: remove previous local temporary staging directories.

```bash
sudo mkdir -p "$NAS_STAGE"
```
Purpose: create a persistent staging directory on the NAS.

```bash
sudo tar -xzpf "$ARCH" -C "$NAS_STAGE"
```
Purpose: extract the backup archive onto the NAS staging path.

```bash
sudo tar -xzpf "$ARCH" --exclude='backup/my-app-backup/DoubleCommander/config/.XDG/*' -C "$NAS_STAGE"
```
Purpose: avoid CIFS extraction failure on a runtime FIFO path.

## Key Findings
- CIFS-backed NAS staging was a poor fit for this restore workload.
- The archive contained a FIFO runtime artifact for DoubleCommander:
  ```text
  backup/my-app-backup/DoubleCommander/config/.XDG/doublecmd.pipe
  ```
  which CIFS could not create.
- The repeated failures were not simple SSH disconnects. The entire Proxmox node became unreachable and required a power cycle.
- Review of prior boot logs showed:
  ```text
  VM 110 qmp command 'guest-ping' failed - got timeout
  ```
  indicating VM 110 had become unresponsive before the host was power-cycled.
- The logs did not show a clean shutdown sequence, which was consistent with a hard lock followed by a forced power cycle.
- The cluster log errors:
  ```text
  pmxcfs ... quorum_initialize failed
  ```
  were consistent with the node being isolated from cluster quorum after the failure, but they were not root cause evidence by themselves.
- The observed behavior suggested host-level instability under this specific heavy CIFS I/O pattern, not merely a broadcast/multicast storm.

## Resolution
Abandoned the idea of maintaining a reusable NAS-based staging directory for this backup. The safer workaround was to use local staging only, or skip staging entirely if the live restore had already succeeded.

## Validation
Validation was based on:
- Repeated reproduction of node instability only when performing NAS-to-NAS staging activity
- Confirmation that the live restore itself had already worked before attempting the NAS optimization
- Log review from the previous boot showing VM unresponsiveness and lack of clean shutdown evidence

## Follow-Up Tasks
- Avoid extracting large archive trees from NAS to NAS over CIFS on this host.
- Prefer:
  - direct restore to live data, or
  - local staging on VM disk, followed by local-to-local rsync into `/opt/docker-apps`
- Investigate host stability further if similar hard locks occur under other high-I/O workloads.
- Review host thermals, memory stability, NIC behavior, and storage load if future hangs recur.
- Consider memtest or host-level stability testing when convenient.

## Lessons Learned
- “Lost connection” must be clarified: VM loss, SSH loss, and full host lock are very different failure domains.
- CIFS is a weak choice for staging workloads that create many files and special file types.
- Optimization steps that stress the host are not worth it once the production restore has already succeeded.
- Proxmox cluster symptoms after a hang are often secondary effects, not the original cause.

---

# Re-Run Restore Using Local Staging

## Summary
After abandoning NAS-based staging, re-ran the backup extraction using a local staging path on VM disk. This reduced CIFS write stress and preserved the ability to reapply the Offen backup safely if needed.

## Environment
- Debian Docker VM: `debian-docker`
- Archive source:
  - `/srv/remotemount/NAS/Tools/Backups/Docker/offen/backup-[date removed].tar.gz`
- Local staging target:
  - `/opt/offen-stage-[date removed]`
- Live restore target:
  - `/opt/docker-apps`

## Problem
Needed a safer way to reapply the Offen backup without writing a large extracted tree back to the NAS over CIFS.

## Symptoms
- NAS staging had already correlated with host instability
- Needed to see all extracted folders in local stage, not just the first 40 lines of output
- Ownership needed to be reset after restore

## Actions Taken
1. Switched to a local staging path:
   ```bash
   /opt/offen-stage-[date removed]
   ```
2. Checked available space on `/opt` before extraction.
3. Stopped Docker before restore operations.
4. Created a fresh local staging directory.
5. Extracted the backup archive locally.
6. Used full listing commands to inspect all staged folders.
7. Re-applied ownership to `/opt/docker-apps`.
8. Restarted application stacks after restore.

Important commands used:

```bash
df -h /opt
```
Purpose: verify local disk capacity for staging.

```bash
sudo rm -rf "$LOCAL_STAGE"
sudo mkdir -p "$LOCAL_STAGE"
```
Purpose: recreate a clean local staging directory.

```bash
sudo tar -xzpf "$ARCH" -C "$LOCAL_STAGE"
```
Purpose: extract the Offen archive locally.

```bash
ls -la "$LOCAL_STAGE/backup/my-app-backup" | less
```
Purpose: view the full extracted tree with paging.

```bash
find "$LOCAL_STAGE/backup/my-app-backup" -maxdepth 1 -mindepth 1 -type d | sort
```
Purpose: list all top-level staged directories cleanly.

```bash
sudo rsync -aHAX --checksum --inplace "$LOCAL_STAGE/backup/my-app-backup/" "$DEST/"
```
Purpose: overlay the local stage onto the live appdata tree.

```bash
sudo chown -R debian:debian /opt/docker-apps
```
Purpose: restore writable ownership for container config paths.

## Key Findings
- Local staging avoided the special-file limitations and instability seen with CIFS NAS staging.
- The earlier `sed -n '1,40p'` output limitation was only a display truncation choice, not an extraction problem.
- Full listings confirmed the local stage contained the expected backup tree.
- Ownership repair was still required after restore operations.

## Resolution
Local staging on `/opt/offen-stage-[date removed]` replaced NAS staging as the preferred reusable restore workflow.

## Validation
Validation was performed by:
- Confirming the local staging directory contained the expected backup tree
- Reapplying the backup to `/opt/docker-apps`
- Resetting ownership successfully
- Proceeding to restart and test application stacks afterwards

## Follow-Up Tasks
- Keep local staging as the standard repeat-restore method for this backup set.
- Optionally delete the local stage later if disk space is needed.
- Continue validating critical app configurations after restore.

## Lessons Learned
- Read-from-NAS and write-to-local is much safer than read-from-NAS and write-back-to-NAS over CIFS.
- Truncated output commands can make a healthy restore look incomplete.
- A reusable local stage is a practical middle ground between speed and safety.

---

# Container Stack Recovery: Plex Hardware Device Error and Gluetun Healthcheck Fix

## Summary
After restoring appdata, container stacks were brought back up. Two notable issues were encountered: Plex failed due to a missing `/dev/dri` device in the VM, and the `gluetun_stack` remained blocked because a custom Docker healthcheck did not match Gluetun’s actual control/health behavior.

## Environment
- Compose-managed stacks:
  - `plex_stack`
  - `gluetun_stack`
- Relevant containers:
  - `plexms`
  - `plexautoskip`
  - `overseerr`
  - `tautulli`
  - `intro-editor-for-plex`
  - `kometa`
  - `gluetun`
  - `deluge-vpn`
  - `qbittorrent-vpn`
  - `sabnzbd-vpn`
  - `metube-stash-vpn`
  - `jdownloader2-stash-vpn`
  - `gallery-dl-stash-vpn`
- Reverse proxy/network:
  - external Docker network `traefik-proxy`
  - Traefik labels for HTTPS hostnames under `*.dulynoted.cloud`
- VPN:
  - Gluetun with Mullvad WireGuard
  - Country selection set to Canada

## Problem
- Plex stack failed because the VM did not have `/dev/dri`.
- Gluetun stack containers were stuck waiting because `gluetun` was marked unhealthy even though the VPN connection itself was working.

## Symptoms
### Plex
- Docker returned:
  ```text
  error gathering device information while adding custom device "/dev/dri": no such file or directory
  ```
- Plex compose included:
  ```yaml
  devices:
    - /dev/dri:/dev/dri
  ```

### Gluetun
- `gluetun_stack` services stayed in waiting/unhealthy state.
- Gluetun logs showed successful VPN startup, for example:
  ```text
  Public IP address is 146.70.198.216 (Canada, Quebec, Montréal - source: ipinfo)
  ```
- Logs also showed:
  ```text
  WARN HEALTH_VPN_DURATION_INITIAL is obsolete
  ```
- Gluetun settings summary indicated:
  - Control server on port `8000`
  - Health server on `127.0.0.1:9999`
- Custom compose healthcheck attempted:
  ```yaml
  curl -fsS http://127.0.0.1:8000/v1/health || exit 1
  ```
- Dependent containers used:
  ```yaml
  depends_on:
    gluetun:
      condition: service_healthy
  ```

## Actions Taken
### Plex
1. Identified that the error was caused by the host/VM lacking `/dev/dri`.
2. Determined that the quick workaround was to comment out the `devices` section in the Plex service to allow software transcoding.
3. Deferred hardware transcoding rework for later.

### Gluetun
1. Checked logs for the Gluetun container:
   ```bash
   docker logs gluetun | tail -n 80
   ```
2. Confirmed Gluetun had:
   - enabled firewall
   - started DNS
   - brought up WireGuard
   - obtained a VPN public IP
3. Determined that the custom Docker healthcheck was incorrect.
4. Removed the custom `healthcheck:` block from the `gluetun` service.
5. Removed obsolete environment variable:
   ```yaml
   HEALTH_VPN_DURATION_INITIAL=60s
   ```
6. Simplified dependent container startup conditions from:
   ```yaml
   condition: service_healthy
   ```
   to:
   ```yaml
   depends_on:
     - gluetun
   ```
7. Replaced the inline `WIREGUARD_PRIVATE_KEY` with an environment variable reference:
   ```yaml
   WIREGUARD_PRIVATE_KEY=${MULLVAD_WG_KEY}
   ```
8. Re-deployed the stack successfully.

Important commands used:

```bash
docker logs gluetun | tail -n 80
```
Purpose: review recent Gluetun startup and VPN status logs.

```bash
docker logs -f gluetun
```
Purpose: follow Gluetun logs live.

```bash
cd /opt/compose/gluetun_stack
docker compose down
docker compose up -d
```
Purpose: redeploy the corrected VPN stack.

```bash
docker ps --format 'table {{.Names}}\t{{.Status}}'
```
Purpose: confirm containers are running and not stuck waiting.

## Key Findings
### Plex
- The Plex failure was not related to the restore itself.
- The Docker VM currently lacked `/dev/dri`, so the compose file’s device passthrough was invalid.
- Commenting out the `/dev/dri` mapping is an acceptable short-term workaround when hardware transcoding is unavailable.

### Gluetun
- Gluetun itself was healthy at the VPN level.
- The problem was Docker health logic, not VPN connectivity.
- The deciding evidence in the logs was:
  - DNS ready
  - firewall enabled
  - WireGuard setup complete
  - public VPN IP obtained
- The custom healthcheck was calling a path that did not match Gluetun’s real behavior.
- Dependent services were blocked only because `condition: service_healthy` chained their startup to a failing custom probe.
- `HEALTH_VPN_DURATION_INITIAL` is obsolete and should be removed from current Gluetun configs.

## Resolution
- Plex: use the stack without `/dev/dri` until GPU passthrough or device exposure is fixed.
- Gluetun: removed the bad custom healthcheck, removed the obsolete health environment variable, simplified `depends_on`, and re-deployed successfully.
- The updated stack came up and worked.

## Validation
Validation was confirmed by:
- Successful `docker compose up -d` after the Gluetun stack changes
- `docker ps` showing the stack containers running
- User confirmation that the updated Gluetun stack worked
- Gluetun logs showing a valid VPN public IP in Canada

## Follow-Up Tasks
- Rotate the Mullvad WireGuard private key that was exposed during troubleshooting.
- Store the new key in a `.env` file rather than inline in the compose file.
- Revisit `/dev/dri` passthrough for Plex if hardware transcoding is desired again.
- Optionally add a correct future Gluetun healthcheck only after confirming the intended endpoint and behavior against the current image version.
- Validate application UIs through Traefik after full stack recovery:
  - qBittorrent
  - Deluge
  - SABnzbd
  - Plex
  - Overseerr
  - Tautulli

## Lessons Learned
- A service can be operational while Docker still marks it unhealthy if the custom probe is wrong.
- Startup gating with `condition: service_healthy` can freeze an entire stack when the primary healthcheck is incorrect.
- Logs that show successful firewall, DNS, VPN, and public IP acquisition are strong evidence that the core service is working.
- Secrets should not be pasted into compose files during troubleshooting.

---

# Command Reference

## Command
```bash
sudo rsync -a --remove-source-files /opt/docker-apps/backup/my-app-backup/ /opt/docker-apps/
```

**What it does**  
Moves the contents of a previously extracted backup payload into the live `/opt/docker-apps` tree while preserving permissions, timestamps, symlinks, and basic metadata.

**Important flags / arguments**
- `-a` — archive mode; preserves structure and metadata
- `--remove-source-files` — removes source files after successful transfer
- trailing `/` on source — copies contents of `my-app-backup/`, not the directory itself

**Why it was used**  
To flatten a previously extracted Offen backup tree into the live appdata location.

**Expected result**  
App folders such as `Traefik`, `Dockge`, `Plex`, and others appear directly under `/opt/docker-apps`.

**Success indicates**  
The extracted backup payload has been merged into the live app tree.

**Failure indicates**  
Incorrect source path, permission issues, or interrupted file move.

**Risk**
- Moderate. `--remove-source-files` is destructive to the source tree after successful transfer.
- Safer alternative: omit `--remove-source-files` if you want to preserve the source payload.

---

## Command
```bash
sudo find /opt/docker-apps/backup/my-app-backup -type d -empty -delete
sudo rmdir -p /opt/docker-apps/backup/my-app-backup 2>/dev/null || true
```

**What it does**  
Deletes empty directories left behind after moving files out of the extracted backup wrapper.

**Important flags / arguments**
- `-type d` — directory only
- `-empty` — match empty directories only
- `-delete` — remove matches
- `rmdir -p` — remove parent directories if they are empty

**Why it was used**  
To clean up the old backup wrapper structure after flattening.

**Expected result**  
`backup/my-app-backup` and its empty parents are removed if no files remain.

**Success indicates**  
The flattening operation completed and left only empty wrappers behind.

**Failure indicates**  
Some files or subdirectories still remain, or permissions prevent deletion.

**Risk**
- Low, provided the path is correct.

---

## Command
```bash
sudo chown -R debian:debian /opt/docker-apps
```

**What it does**  
Recursively changes ownership of the appdata tree to user `debian` and group `debian`.

**Important flags / arguments**
- `-R` — recurse through all files and directories

**Why it was used**  
To ensure Dockge, Compose-managed services, and file-based app configs were writable by the intended user.

**Expected result**  
Config files and directories become owned by `debian:debian`.

**Success indicates**  
The app management user can edit and maintain the files again.

**Failure indicates**  
Permission or path issues.

**Risk**
- Moderate. This can override intentional ownership on some special files if used indiscriminately.
- Safer alternative: limit the path or reapply ownership only to the affected app directories.

---

## Command
```bash
sudo tar -czpf "$DEST/.pre-restore/full-pre-restore-$STAMP.tgz" --exclude="$DEST/.pre-restore" -C "$DEST" .
```

**What it does**  
Creates a compressed tar snapshot of the current `/opt/docker-apps` tree before restoring.

**Important flags / arguments**
- `-c` — create archive
- `-z` — gzip compression
- `-p` — preserve permissions
- `-f` — output file
- `-C "$DEST"` — change into target directory before archiving
- `.` — archive the current directory contents

**Why it was used**  
As a safety snapshot before overlaying the Offen backup onto the live appdata.

**Expected result**  
A tarball appears under `.pre-restore`.

**Success indicates**  
There is a rollback snapshot available.

**Failure indicates**  
Path problems, insufficient space, or self-inclusion issues.

**Risk**
- Low to moderate. Storing the snapshot inside the directory being archived can generate self-read warnings.
- Safer alternative: save the snapshot outside `/opt/docker-apps`.

---

## Command
```bash
sudo tar -xzpf "$ARCH" -C "$STAGE"
```

**What it does**  
Extracts the Offen backup archive to a staging directory.

**Important flags / arguments**
- `-x` — extract
- `-z` — gzip input
- `-p` — preserve permissions
- `-f` — archive file
- `-C "$STAGE"` — extract into the chosen staging directory

**Why it was used**  
To inspect and stage the backup before merging it into the live appdata tree.

**Expected result**  
A tree such as `backup/my-app-backup/...` appears under the staging path.

**Success indicates**  
The archive is readable and extractable.

**Failure indicates**  
Path issues, storage problems, or filesystem incompatibilities such as unsupported special files on CIFS.

**Risk**
- Low on local filesystems.
- Higher on CIFS if the archive contains special files like FIFOs.

---

## Command
```bash
sudo tar -xzpf "$ARCH" --exclude='backup/my-app-backup/DoubleCommander/config/.XDG/*' -C "$NAS_STAGE"
```

**What it does**  
Extracts the archive while excluding a problematic runtime `.XDG` path containing a FIFO.

**Important flags / arguments**
- `--exclude=...` — skip matching paths during extraction

**Why it was used**  
CIFS could not create the `doublecmd.pipe` FIFO contained in that path.

**Expected result**  
The archive extracts without trying to create unsupported special files.

**Success indicates**  
The rest of the backup is staged even though a nonessential runtime artifact is omitted.

**Failure indicates**  
Other unsupported files, CIFS mount problems, or path issues remain.

**Risk**
- Low.
- Tradeoff: excluded files are not restored. In this case the excluded FIFO was a runtime artifact, not core config.

---

## Command
```bash
sudo rsync -aHAX --checksum --inplace "$STAGE/backup/my-app-backup/" "$DEST/"
```

**What it does**  
Overlays the staged backup contents onto the live `/opt/docker-apps` tree.

**Important flags / arguments**
- `-a` — archive mode
- `-H` — preserve hard links
- `-A` — preserve ACLs
- `-X` — preserve extended attributes
- `--checksum` — compare by checksum, not just size/time
- `--inplace` — update destination files in place
- trailing `/` — merge contents, not parent folder

**Why it was used**  
To restore missing files and refresh the live appdata tree from the staged backup.

**Expected result**  
Missing and changed files under `/opt/docker-apps` are restored from the backup.

**Success indicates**  
The live tree now matches the backup contents for the paths involved.

**Failure indicates**  
Path, permission, or I/O problems.

**Risk**
- Moderate. This overwrites destination files.
- Safer alternative: snapshot the destination first.

---

## Command
```bash
du -sh /opt/docker-apps
```

**What it does**  
Shows the total size of the appdata directory in human-readable form.

**Important flags / arguments**
- `-s` — summary only
- `-h` — human-readable units

**Why it was used**  
To sanity-check the presence and approximate size of restored data.

**Expected result**  
A size value such as `23G /opt/docker-apps`.

**Success indicates**  
The directory exists and contains substantial data.

**Failure indicates**  
Path issues or access problems.

---

## Command
```bash
find /opt/docker-apps -maxdepth 2 -type d | sed -n '1,60p'
```

**What it does**  
Lists top-level and near-top-level directories under `/opt/docker-apps`.

**Important flags / arguments**
- `-maxdepth 2` — limit recursion
- `-type d` — directories only
- `sed -n '1,60p'` — print the first 60 lines only

**Why it was used**  
To quickly confirm the restored app directory structure.

**Expected result**  
Common app folders appear in the output.

**Success indicates**  
The restore produced the expected directory layout.

**Failure indicates**  
Missing paths or unexpectedly sparse output.

---

## Command
```bash
df -h /opt
```

**What it does**  
Shows free and used space on the filesystem containing `/opt`.

**Important flags / arguments**
- `-h` — human-readable output

**Why it was used**  
To check if local staging had enough disk space.

**Expected result**  
Displays total, used, and available space.

**Success indicates**  
Sufficient free space exists for staging.

**Failure indicates**  
The filesystem may be full or inaccessible.

---

## Command
```bash
sudo rm -rf /tmp/offen-stage-*
```

**What it does**  
Removes old temporary staging directories.

**Important flags / arguments**
- `-r` — recursive
- `-f` — force removal without prompting

**Why it was used**  
To clean up obsolete temporary restore staging directories.

**Expected result**  
Matching temporary staging directories are deleted.

**Success indicates**  
The temp workspace is cleaned up.

**Failure indicates**  
Path issues or filesystem problems.

**Risk**
- High if the glob is wrong.
- Safer alternative: list matches first with `ls -d /tmp/offen-stage-*`.

---

## Command
```bash
sudo rm -rf "$LOCAL_STAGE"
sudo mkdir -p "$LOCAL_STAGE"
```

**What it does**  
Recreates a clean local staging directory.

**Important flags / arguments**
- `rm -rf` — forcibly remove prior staging content
- `mkdir -p` — create directory and parents if needed

**Why it was used**  
To ensure the new local stage did not contain stale files from an earlier extract.

**Expected result**  
An empty, clean staging directory exists.

**Success indicates**  
The local stage is ready for extraction.

**Failure indicates**  
Permission or filesystem issues.

**Risk**
- Moderate to high if `$LOCAL_STAGE` is wrong.
- Safer alternative: echo the variable first and verify it before deletion.

---

## Command
```bash
ls -la "$LOCAL_STAGE/backup/my-app-backup" | less
```

**What it does**  
Displays the full staged backup tree listing with paging.

**Important flags / arguments**
- `-l` — long listing
- `-a` — include hidden entries
- `less` — pager for long output

**Why it was used**  
To inspect the complete extracted backup rather than only the first 40 lines.

**Expected result**  
A scrollable directory listing of all top-level entries.

**Success indicates**  
The local stage contains the expected backup tree.

**Failure indicates**  
Extraction was incomplete or the path is wrong.

---

## Command
```bash
find "$LOCAL_STAGE/backup/my-app-backup" -maxdepth 1 -mindepth 1 -type d | sort
```

**What it does**  
Lists all top-level directories in the extracted backup.

**Important flags / arguments**
- `-maxdepth 1` — only top level
- `-mindepth 1` — exclude the root directory itself
- `-type d` — directories only
- `sort` — alphabetize output

**Why it was used**  
To get a clean inventory of all staged app folders.

**Expected result**  
A sorted list of app directory paths.

**Success indicates**  
The expected app set is present in the staged backup.

**Failure indicates**  
Extraction problems or wrong path selection.

---

## Command
```bash
docker compose down
docker compose up -d
```

**What it does**  
Stops and removes the current stack, then recreates and starts it in detached mode.

**Important flags / arguments**
- `down` — stop and remove containers, networks defined by the compose project
- `up -d` — start containers in background mode

**Why it was used**  
To restart corrected stacks such as `gluetun_stack` after compose changes.

**Expected result**  
Containers stop cleanly and restart with updated configuration.

**Success indicates**  
The compose changes were accepted and services start.

**Failure indicates**  
Bad compose syntax, missing mounts/devices, or service-level startup errors.

**Risk**
- Moderate. Stops services during redeploy.
- Safer alternative: use `docker compose up -d` after targeted edits if you do not need a full down/up cycle.

---

## Command
```bash
docker logs gluetun | tail -n 80
```

**What it does**  
Shows the last 80 lines of logs from the `gluetun` container.

**Important flags / arguments**
- `tail -n 80` — show recent log lines only

**Why it was used**  
To determine whether Gluetun itself was failing or only its Docker health logic was failing.

**Expected result**  
Recent Gluetun startup logs including firewall, DNS, VPN, and public IP information.

**Success indicates**  
Useful evidence is available for troubleshooting startup and health status.

**Failure indicates**  
The container may not exist, may not be running, or logging may be unavailable.

---

## Command
```bash
docker logs -f gluetun
```

**What it does**  
Follows Gluetun logs live.

**Important flags / arguments**
- `-f` — follow log output continuously

**Why it was used**  
To watch Gluetun startup and status changes in real time.

**Expected result**  
Live streaming log output until interrupted with `Ctrl+C`.

**Success indicates**  
The container is running and producing log events.

**Failure indicates**  
Container naming or runtime issues.

---

## Command
```bash
docker ps --format 'table {{.Names}}\t{{.Status}}'
```

**What it does**  
Shows container names and status in a compact table.

**Important flags / arguments**
- `--format` — custom output format for quick status review

**Why it was used**  
To confirm whether `gluetun` and dependent containers were up, waiting, or unhealthy.

**Expected result**  
A table showing names and container status.

**Success indicates**  
Services are running as expected.

**Failure indicates**  
Containers may be exited, restarting, or absent.

---

## Command
```bash
cd /opt/compose/gluetun_stack
```

**What it does**  
Changes into the compose project directory for the Gluetun-based stack.

**Why it was used**  
Docker Compose commands should be run from the correct project directory to target the intended stack files.

**Expected result**  
Subsequent `docker compose` commands apply to the Gluetun stack.

**Success indicates**  
The correct compose directory exists.

**Failure indicates**  
Wrong path or missing stack files.

---

## Command
```bash
ls -l /dev/net/tun
```

**Likely command used**

**What it does**  
Checks whether the TUN device required by VPN containers exists inside the VM.

**Why it would be used**  
Gluetun requires `/dev/net/tun`; absence would prevent WireGuard/OpenVPN tunnel setup.

**Expected result**  
A character device entry for `/dev/net/tun`.

**Success indicates**  
The VM exposes the TUN device correctly.

**Failure indicates**  
VPN containers may fail to initialize their tunnel interface.

---

## Command
```bash
ls -l /dev/dri
```

**Likely command used**

**What it does**  
Checks whether GPU render device nodes are available.

**Why it would be used**  
Plex attempted to map `/dev/dri:/dev/dri` for hardware transcoding.

**Expected result**  
Device nodes such as `card0` and `renderD128`.

**Success indicates**  
The VM or host exposes graphics device nodes for container passthrough.

**Failure indicates**  
Plex hardware transcoding device mapping will fail.

---

## Command
```bash
journalctl -b -1 | tail -n 100
```

**Likely command used**

**What it does**  
Shows the last 100 lines from the previous boot’s logs.

**Important flags / arguments**
- `-b -1` — previous boot
- `tail -n 100` — only recent lines

**Why it was used**  
To inspect what happened before the Proxmox node was power-cycled after the hang.

**Expected result**  
Recent logs from the failed boot, including service errors or VM timeouts.

**Success indicates**  
There is enough retained journal data to inspect the failure window.

**Failure indicates**  
The journal may be incomplete or old logs unavailable.

---

## Command
```bash
journalctl -b -1 -p 0..3 | less
```

**Likely command used**

**What it does**  
Shows high-priority errors from the previous boot with paging.

**Important flags / arguments**
- `-p 0..3` — emergency through error priority
- `less` — page long output

**Why it was used**  
To focus on serious errors that could explain the host/node failure.

**Expected result**  
Critical log messages such as kernel, service, or cluster errors.

**Success indicates**  
Actionable high-severity logs are available.

**Failure indicates**  
No high-severity logs were written before the hard lock or power cycle.
