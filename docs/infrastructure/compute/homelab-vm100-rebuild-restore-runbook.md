---
title: "Rebuild Debian Docker VM 100 from Proxmox Template 9000"
track: "infrastructure"
category: "compute"
type: "runbook"
logical_order: 70
date_rule: "Dates are removed from filenames, visible headings, indexes, generated metadata, and runbook body content."
---

# Rebuild Debian Docker VM 100 from Proxmox Template 9000

## Summary
VM 100 (`debian-docker`) was destroyed and recreated from template 9000 as a full clone on Ceph RBD storage. The goal was to rebuild the main Docker VM cleanly, attach a dedicated Docker data disk, and reapply custom cloud-init from Proxmox snippets.

## Environment
- Proxmox VE host: `mainframe`
- VM: `100` (`debian-docker`)
- Template VM: `9000`
- Storage:
  - VM disks: `cephpool` (Ceph RBD)
  - Cloud-init snippets: `local` at `/var/lib/vz/snippets`
- Cloud-init files:
  - `docker-userdata.yml`
  - `docker-net.yml`
- Guest OS: Debian cloud image / Debian 12 cloud-init guest
- Data disk target: `/var/lib/docker`
- Bind mount targets:
  - `/opt/docker-apps`
  - `/opt/compose`
- Intended static IP: `192.168.16.3`

## Problem
The VM needed a clean rebuild, but the recreation process hit storage syntax issues, cloud-init disk conflicts, and guest boot problems tied to the Docker data disk and cloud-init configuration.

## Symptoms
- Proxmox RBD disk syntax error:
  ```text
  unable to parse rbd volume name '200G'
  ```
- Cloud-init disk creation conflict:
  ```text
  rbd create 'vm-100-cloudinit' error: rbd: create error: (17) File exists
  ```
- The added Ceph disk was initially created with the wrong effective size (`0T`) despite a size argument being intended.
- Guest console behavior suggested emergency-mode style boot problems and inaccessible root shell.
- Cloud-init warnings appeared later during boot.

## Actions Taken
1. Removed or prepared to remove the existing VM 100.
2. Cloned template 9000 into VM 100 as a full clone on `cephpool`.
3. Set the VM SCSI controller to `virtio-scsi-single`.
4. Added a second virtual disk intended for Docker data as `scsi1`.
5. Attached a cloud-init drive on `cephpool`.
6. Applied Proxmox `cicustom` to use:
   - `local:snippets/docker-userdata.yml`
   - `local:snippets/docker-net.yml`
7. Regenerated the cloud-init ISO with `qm cloudinit update 100`.
8. Booted and inspected the VM from the Proxmox serial console.

## Key Findings
- Proxmox Ceph/RBD disk creation syntax was sensitive and early attempts did not create the intended 150–200 GiB secondary disk correctly.
- The cloud-init drive already existed after cloning, so trying to create it again failed.
- The VM could boot far enough for serial console troubleshooting, which made it possible to diagnose storage and cloud-init issues without relying on SSH.
- The root cause of the boot trouble was not basic cloning failure; it was the state of the second disk and the guest provisioning logic.

## Resolution
The rebuild proceeded with:
- VM disks on `cephpool`
- cloud-init snippets stored on `local`
- custom cloud-init attached after creation
- later fixes focused on correcting the second disk and guest-side mount behavior rather than rebuilding again immediately

## Validation
Success at this stage was partial:
- VM 100 existed again on `cephpool`
- custom cloud-init was attached
- the VM booted far enough to provide serial console logs
- further storage and mount fixes were still required

## Follow-Up Tasks
- Correct the second disk size and filesystem handling
- validate cloud-init YAML before future rebuilds
- confirm that the guest network config and Docker storage mount both apply cleanly on first boot
- document a stable VM rebuild sequence for future use

## Lessons Learned
- Ceph-backed Proxmox disk creation syntax should be verified immediately after `qm set`.
- It is safer to create the VM first, then apply `--cicustom`, then regenerate cloud-init.
- Serial console access is essential during first-boot troubleshooting.

---

# Diagnose Boot Failure and Missing Filesystem on /dev/sdb

## Summary
After the rebuild, VM 100 booted but failed to mount the dedicated Docker data disk. Troubleshooting focused on boot logs, cloud-init messages, and the state of `/dev/sdb`.

## Environment
- VM: `100` (`debian-docker`)
- Guest disk layout:
  - `sda`: root disk
  - `sdb`: intended Docker data disk
  - `sr0`: cloud-init NoCloud seed
- Guest console: Proxmox serial console
- Cloud-init datasource: NoCloud from `/dev/sr0`

## Problem
The guest expected `/dev/sdb` to host `/var/lib/docker`, but that disk did not have a usable ext4 filesystem when the guest first booted.

## Symptoms
- Boot log showed:
  ```text
  EXT4-fs (sdb): VFS: Can't find ext4 filesystem
  ```
- Mount activation failure:
  ```text
  Activate mounts: FAIL:mount -a
  ```
- Docker dependency failure tied to `/var/lib/docker`
- CIFS mounts initially reported:
  ```text
  CIFS: VFS: No username specified
  ```
  before `cifs-utils` and config were fully in place
- Cloud-init warning:
  ```text
  Invalid cloud-config provided: Please run 'sudo cloud-init schema --system' to see the schema errors.
  ```

## Actions Taken
1. Opened VM serial console.
2. Reviewed boot output from kernel start through cloud-init final stage.
3. Observed that `/dev/sdb` was detected as a 150 GiB disk.
4. Confirmed the cloud-init datasource was present on `/dev/sr0`.
5. Identified that `/var/lib/docker` was being mounted before `/dev/sdb` had a valid ext4 filesystem.
6. Noted that Docker installation completed later in cloud-init, but Docker service still failed due to the missing filesystem.

## Key Findings
- `/dev/sdb` existed and was visible to the guest, so this was not a Proxmox device presentation issue.
- The failure was specifically that `/dev/sdb` lacked the expected ext4 filesystem.
- Cloud-init ran far enough to install packages, configure networking, and create the `debian` user, so the user-data was not fully ignored.
- The invalid cloud-config warning indicated that at least part of the YAML was malformed, which likely prevented some storage steps from behaving as intended.

## Resolution
The issue was narrowed down to guest-side filesystem initialization and mount sequencing. The next step was to manually create the ext4 filesystem on `/dev/sdb` and then refine the cloud-init YAML so first-boot provisioning would handle it correctly in future rebuilds.

## Validation
Validation came from the serial console:
- `sdb` was present
- root filesystem on `sda1` mounted successfully
- cloud-init completed
- the exact mount failure for `sdb` was visible in logs

## Follow-Up Tasks
- create ext4 on `/dev/sdb`
- mount `/var/lib/docker`
- update cloud-init to use valid schema and reliable disk setup
- retest boot after YAML changes

## Lessons Learned
- Presence of a disk in `lsblk` or kernel logs does not mean it is formatted or mountable.
- Cloud-init can complete partially while still leaving critical storage steps broken.
- Boot logs are often enough to separate disk presentation problems from filesystem problems.

---

# Manually Format /dev/sdb, Mount Docker Data, and Start Docker

## Summary
Once the missing filesystem problem was identified, `/dev/sdb` was formatted manually, mounted at `/var/lib/docker`, and Docker was started successfully.

## Environment
- VM: `100`
- Docker root: `/var/lib/docker`
- Data disk: `/dev/sdb`
- Filesystem label used later in YAML: `docker-data`

## Problem
Docker could not start because `/var/lib/docker` was not mounted on the dedicated data disk.

## Symptoms
- `/dev/sdb` had no filesystem in `lsblk -f`
- Mount errors for `/var/lib/docker`
- Docker service could not start correctly until the data disk was mounted

## Actions Taken
1. Listed block devices and filesystems with `lsblk -f`.
2. Created an ext4 filesystem on `/dev/sdb` and labeled it `docker-data`.
3. Mounted `/var/lib/docker`.
4. Started Docker and checked service health.
5. Verified mounted storage with `df -h`.

## Key Findings
- `/dev/sdb` was empty before manual formatting.
- After formatting, `/var/lib/docker` mounted successfully on the dedicated disk.
- Docker started successfully once its data-root path existed on the mounted ext4 filesystem.
- This confirmed the disk, mountpoint, and Docker daemon behavior were otherwise sound.

## Resolution
Manual formatting of `/dev/sdb` restored the intended Docker storage design. `/var/lib/docker` was mounted from the dedicated data disk, and Docker was able to run.

## Validation
Success was confirmed by:
- `lsblk -f` showing ext4 on `/dev/sdb`
- `df -h /var/lib/docker` showing `/dev/sdb` as the backing filesystem
- `systemctl status docker` showing Docker active and running

## Follow-Up Tasks
- bake this storage logic into cloud-init so manual formatting is no longer required
- ensure `/etc/fstab` is clean and uses a stable identifier
- verify Docker daemon configuration still points to `/var/lib/docker`

## Lessons Learned
- Manually fixing the disk is a good recovery method, but provisioning should be fixed so it is not needed on rebuild.
- A dedicated Docker data disk should be validated before restoring application data.

---

# Restore Bind Mount Layout for /opt/docker-apps and /opt/compose

## Summary
After Docker was running again, the guest still lacked the expected bind mount layout that mapped Docker app data and compose files into user-friendly paths under `/opt`.

## Environment
- Source paths:
  - `/var/lib/docker/appdata`
  - `/var/lib/docker/compose`
- Target paths:
  - `/opt/docker-apps`
  - `/opt/compose`
- Mount method: bind mounts via `/etc/fstab`

## Problem
The bind mount targets existed conceptually in the design, but the source directories either did not exist yet or the bind mounts had been added multiple times, causing confusion and layered mounts.

## Symptoms
- Initial mount failures:
  ```text
  mount: /opt/docker-apps: special device /var/lib/docker/appdata does not exist.
  mount: /opt/compose: special device /var/lib/docker/compose does not exist.
  ```
- `findmnt` later showed multiple stacked mount entries for the same targets, including references to both the old root disk and the new Docker data disk

## Actions Taken
1. Created source directories under `/var/lib/docker`.
2. Created target directories under `/opt`.
3. Added `/etc/fstab` bind entries for:
   - `/var/lib/docker/appdata -> /opt/docker-apps`
   - `/var/lib/docker/compose -> /opt/compose`
4. Mounted the bind targets.
5. Verified mount results with `findmnt`.
6. Identified duplicate or layered bind mounts caused by earlier attempts.
7. Cleaned `/etc/fstab` and described a recovery sequence to unmount duplicates and remount once.

## Key Findings
- The bind mounts failed initially because the source directories did not yet exist.
- Repeated `mount` calls plus duplicate `fstab` lines produced confusing layered output.
- The correct design is simple once the source directories exist and `fstab` contains only one clean entry for each target.

## Resolution
The source directories and target directories were created, bind mounts were restored, and the configuration path layout under `/opt` became usable again.

## Validation
Validation came from:
- `findmnt` showing `/opt/docker-apps` and `/opt/compose`
- `/var/lib/docker` mounted from `/dev/sdb`
- Docker running with its data directory on the dedicated disk

## Follow-Up Tasks
- embed clean bind mount handling in cloud-init
- avoid duplicate mount commands during troubleshooting
- keep `/etc/fstab` deduplicated

## Lessons Learned
- Bind mounts depend on source directories existing first.
- Repeated bind-mount attempts can produce misleading stacked output.
- `findmnt` is the best quick check for mount correctness.

---

# Correct Cloud-Init YAML for the Rebuilt Docker VM

## Summary
The cloud-init user-data for VM 100 was iteratively corrected to remove schema errors, properly handle `/dev/sdb`, and align with the new bind-mount layout under `/opt/docker-apps`.

## Environment
- Cloud-init snippet: `/var/lib/vz/snippets/docker-userdata.yml`
- Network snippet: `/var/lib/vz/snippets/docker-net.yml`
- Snippet storage in Proxmox: `local:snippets`
- Intended app layout: `/opt/docker-apps/<app>/config`

## Problem
The user-data YAML contained invalid or incomplete configuration for password handling, disk setup, and mount layout.

## Symptoms
- Cloud-init warning:
  ```text
  Invalid cloud-config provided: Please run 'sudo cloud-init schema --system' to see the schema errors.
  ```
- `fs_setup` did not produce the intended filesystem behavior during first boot
- Docker and bind mount steps had to be repaired manually after boot

## Actions Taken
1. Compared the original user-data against the desired target design.
2. Identified the `chpasswd` block as invalid in the way it was written.
3. Removed the invalid `chpasswd` section from the proposed YAML.
4. Switched the Docker data mount logic to rely on:
   - `fs_setup`
   - ext4 label `docker-data`
   - stable mount definitions
5. Reworked bind mount handling to reflect the actual structure:
   - `/opt/docker-apps/<app>/config`
   - `/opt/compose`
6. Discussed moving network-dependent Docker repo setup from `bootcmd` into `runcmd`.
7. Built a cleaner version of the YAML that included:
   - early directory creation
   - `fs_setup` on `/dev/sdb`
   - mount definitions
   - Docker install steps
   - Docker service ordering

## Key Findings
- The invalid `chpasswd` block was a likely cause of schema validation warnings.
- First-boot cloud-init storage behavior is sensitive to syntax and ordering; once it misses its opportunity, later YAML edits do not retroactively fix the guest without a clean reprovision or manual intervention.
- The YAML needed to match the actual restored directory layout, not the old `/DockerAppData` path.

## Resolution
A corrected cloud-init direction was established:
- remove invalid schema elements
- use `fs_setup` to initialize `/dev/sdb`
- mount Docker data from a stable label
- mount or bind `/opt/docker-apps` and `/opt/compose`
- move network-dependent install actions to a later stage

## Validation
Validation was indirect but strong:
- cloud-init completed enough to provision the guest
- later manual fixes confirmed that the intended layout was valid
- the revised YAML addressed the exact issues seen in boot logs and runtime behavior

## Follow-Up Tasks
- validate the final YAML with cloud-init schema tools before the next rebuild
- keep a known-good cloud-init snippet under version control or archived in the homelab docs
- test a full destroy/recreate cycle once the final YAML is settled

## Lessons Learned
- Cloud-init YAML should be treated like code: validate it before production use.
- Disk setup logic and bind mount design should be explicit and reproducible.
- When rebuilding important infrastructure VMs, preserve a working snippet history.

---

# Restore Docker Application Data from Offen Backup to /opt/docker-apps

## Summary
Application data previously backed up with Offen was prepared for restoration to the new host layout under `/opt/docker-apps`. The old archive structure still reflected the legacy backup source path, so the internal paths had to be inspected before extraction.

## Environment
- Backup tool: `offen/docker-volume-backup:v2`
- Backup archive found:
  - `/srv/remotemount/NAS/Tools/Backups/Docker/offen/backup-[date removed].tar.gz`
- NAS mount:
  - `/srv/remotemount/NAS`
- New destination:
  - `/opt/docker-apps`

## Problem
The restored environment no longer uses `/DockerAppData`, but the backup archive was built from the old path. The archive had to be restored into the new layout without preserving the old leading path components.

## Symptoms
- Initial archive lookup failed because the exact filename and extension were wrong.
- Once found, the archive structure showed:
  ```text
  /backup/my-app-backup/<AppName>/config/...
  ```
- This meant a naive extract would recreate the wrapper path, not restore directly into `/opt/docker-apps/<AppName>`.

## Actions Taken
1. Confirmed the NAS CIFS mount was active.
2. Located the correct archive file with `find`.
3. Inspected the archive with `tar -tzf`.
4. Determined that the leading components to remove were:
   - `backup`
   - `my-app-backup`
5. Planned extraction into `/opt/docker-apps` using `--strip-components=2`.
6. Planned to stop compose stacks before extraction.
7. Planned permission normalization after restore.

## Key Findings
- The correct Offen archive was gzipped (`.tar.gz`), not plain `.tar`.
- The archive layout required exactly two components to be stripped to land correctly under `/opt/docker-apps`.
- The backup was usable without reintroducing `/DockerAppData`, provided extraction was handled carefully.

## Resolution
The restore plan was established: stop containers, extract the archive into `/opt/docker-apps` with `--strip-components=2`, reapply ownership and permission policy, then bring the stacks back up.

## Validation
Validation was achieved by:
- confirming the NAS mount
- locating the archive on disk
- reading the top archive entries
- matching those entries to the intended destination layout

## Follow-Up Tasks
- perform the actual extract if not already done
- reapply ownership and secret file permissions after extraction
- restart and validate application stacks
- update backup definitions so future archives are sourced from `/opt/docker-apps`

## Lessons Learned
- Always inspect backup archive structure before restoring into a live environment.
- Backup path migrations should be handled deliberately when host layout changes.
- CIFS mount validation is a necessary first step before restore operations.

---

# Update Backup and Restore Strategy from /DockerAppData to /opt/docker-apps

## Summary
The backup configuration for Offen and Restic still pointed at `/DockerAppData`, but the rebuilt host now uses `/opt/docker-apps`. Backup and restore strategy had to be updated to reflect the new canonical path.

## Environment
- Offen config:
  - archive path: `/srv/remotemount/NAS/Tools/Backups/Docker/offen`
  - old source mapping: `/DockerAppData:/backup/my-app-backup:ro`
- Restic config:
  - repository: `/srv/remotemount/NAS/Tools/Backups/Docker/restic`
  - old source: `/DockerAppData`
- New live source:
  - `/opt/docker-apps`

## Problem
Future backups would be inconsistent or incomplete if the old `/DockerAppData` path remained in the compose definitions after migration.

## Symptoms
- Existing backup configs still referenced `/DockerAppData`
- The rebuilt host used `/opt/docker-apps` instead
- Starting containers before updating these references could accidentally recreate stale path usage

## Actions Taken
1. Reviewed the old Offen and Restic service configuration.
2. Identified all bind mounts and environment values still referencing `/DockerAppData`.
3. Recommended changing those references to `/opt/docker-apps` before restarting the backup containers.
4. Recommended updating compose files and scripts before bringing any stack back online.

## Key Findings
- Offen backed up the live bind-mounted path mounted into `/backup/my-app-backup`.
- Restic backed up `/DockerAppData` directly.
- Both backup services needed explicit path migration to match the rebuilt host.

## Resolution
The required path migration was identified:
- Offen source volume should change from `/DockerAppData` to `/opt/docker-apps`
- Restic `RESTIC_BACKUP_SOURCES` and bind mount should change from `/DockerAppData` to `/opt/docker-apps`

## Validation
Validation at this stage was design-level:
- old configs were reviewed
- replacement path strategy was established
- risk of stale path recreation was identified before bringing services online

## Follow-Up Tasks
- edit backup stack compose files
- validate backup jobs after restart
- document one known-good backup and restore workflow based on `/opt/docker-apps`

## Lessons Learned
- Rebuilds and path migrations must include backup jobs, not just application stacks.
- Backup containers are easy to overlook during storage layout changes.

---

# Use Resumable Rsync for Application Data Migration and Recovery

## Summary
A resumable rsync-based migration was prepared to copy Docker app data from the old host to the new Docker VM with bandwidth limiting and automatic resume behavior.

## Environment
- Source host: `192.168.16.100`
- Destination host: `192.168.16.3`
- Source path: `/DockerAppData(old)/`
- Destination path: `/opt/docker-apps`

## Problem
A large data copy needed to survive connection drops and resume without restarting from scratch.

## Symptoms
- Concern about connection drops interrupting long file copies
- Earlier shell formatting issues caused an rsync loop to misbehave
- At one point the operator realized the sync had been run on the wrong host

## Actions Taken
1. Built an rsync command with:
   - bandwidth limiting
   - SSH keepalive settings
   - `--partial`
   - `--append-verify`
2. Wrapped it in a retry loop.
3. Added a completion banner after the loop.
4. Discussed how to cancel the loop cleanly.
5. Used a no-change rsync dry run to confirm final completion.

## Key Findings
- The resumable rsync strategy was suitable for unstable or long-running transfers.
- A clean completion was indicated by:
  - zero regular files transferred
  - zero transferred file size
  - return to shell prompt and completion banner
- The approach worked, but host context must be verified before running it.

## Resolution
The rsync process and verification pattern were established as a reusable migration workflow.

## Validation
Validation was provided by the successful dry-run output showing no files needed transfer and a completion timestamp.

## Follow-Up Tasks
- clean any accidental sync artifacts from the wrong host
- keep the resumable rsync snippet in the homelab runbook
- use `hostname` or IP checks before future migrations

## Lessons Learned
- `--partial --append-verify` is a strong default for resumable LAN copies.
- Explicit completion output improves operator confidence.
- Always verify the current host before starting a long-running migration.

---

# Fix Compose File Discovery, Path Assumptions, and Dockge Startup

## Summary
Compose stack management was briefly blocked by incorrect assumptions about file locations. Compose files were stored under per-stack subdirectories within `/opt/compose`, not directly under `/opt/compose`.

## Environment
- Compose root: `/opt/compose`
- Example compose paths:
  - `/opt/compose/dockge/compose.yml`
  - `/opt/compose/traefik/compose.yaml`
  - `/opt/compose/arr_stack/compose.yaml`
  - others under stack subdirectories

## Problem
Service commands failed because they referenced non-existent flat paths like `/opt/compose/dockge.yml`.

## Symptoms
- Docker Compose reported:
  ```text
  open /opt/compose/dockge.yml: no such file or directory
  ```
- `find` with `-maxdepth 1` returned no compose files, which initially obscured the real directory structure.

## Actions Taken
1. Listed compose files recursively under `/opt/compose`.
2. Identified the real Dockge compose file path:
   ```text
   /opt/compose/dockge/compose.yml
   ```
3. Corrected the startup command to use the real path.
4. Confirmed that `docker compose -f <path>` can be run without changing into the directory.

## Key Findings
- Compose files were organized by stack subdirectory, not flat naming.
- Recursive discovery is required for bulk maintenance tasks.
- The issue was path discovery, not a Docker or Dockge runtime failure.

## Resolution
Compose operations were updated to target the actual file paths under `/opt/compose/<stack>/compose.yml|yaml`.

## Validation
Validation came from recursive file discovery and the corrected startup command format.

## Follow-Up Tasks
- standardize compose file naming if desired
- maintain a reusable compose discovery command
- validate all compose paths before mass automation

## Lessons Learned
- Never assume a flat compose directory in a multi-stack homelab.
- File discovery should be recursive before bulk edits or startup automation.

---

# Bulk Remove Deprecated Compose version Lines

## Summary
A reusable regex-based bulk edit was developed to remove obsolete `version: "3.x"` lines from compose files stored under `/opt/compose`.

## Environment
- Compose root: `/opt/compose`
- File types:
  - `compose.yml`
  - `compose.yaml`
  - other YAML compose files

## Problem
Compose files still included deprecated `version:` declarations that were no longer required.

## Symptoms
- Initial bulk edit attempt returned:
  ```text
  sed: no input files
  ```
  because the command assumed flat files at `/opt/compose` depth 1.
- Real compose files were nested in stack subdirectories.

## Actions Taken
1. Searched recursively under `/opt/compose` to locate all compose files.
2. Reworked the bulk edit command to run against the discovered files.
3. Included `.bak` backup creation.
4. Added verification via `grep`.

## Key Findings
- The first failure was due to incorrect depth assumptions, not bad regex logic.
- Recursive compose file discovery solved the input problem.
- A regex removing only `version: "3.x"` style lines was sufficient and safe once the right files were targeted.

## Resolution
A recursive regex-based cleanup approach was established for all compose files under `/opt/compose`.

## Validation
Validation consisted of:
- successful recursive compose file discovery
- no remaining `version:` lines after the cleanup
- `.bak` files available for rollback

## Follow-Up Tasks
- clean up `.bak` files when satisfied
- run `docker compose config` on edited stacks as a final sanity check

## Lessons Learned
- Regex maintenance tasks are only as good as the file discovery feeding them.
- Always create backups for bulk in-place YAML edits.

---

# Create Traefik Bridge Network and Restore Traefik ACME Permissions

## Summary
Traefik-specific recovery work included creating the `traefik-proxy` Docker bridge network and troubleshooting write access to the Traefik ACME directory and `acme.json` file.

## Environment
- Docker network: `traefik-proxy`
- Intended network settings:
  - driver: `bridge`
  - subnet: `172.35.0.0/16`
  - gateway: `172.35.0.1`
- Traefik config layout:
  - `/opt/docker-apps/Traefik/config`
  - expected ACME storage under `.../letsencrypt/acme.json`

## Problem
Traefik required both a known bridge network and correct file permissions for its ACME storage, but directory layout assumptions and permissions caused confusion.

## Symptoms
- Network needed to be recreated manually.
- `acme.json` creation attempts initially failed because the path assumption was wrong.
- WinSCP reported permission denied when writing to the Traefik `letsencrypt` directory.
- The `letsencrypt` directory was found to have been given file-like permissions (`0600`), which is invalid for a usable directory.

## Actions Taken
1. Created the `traefik-proxy` Docker bridge network with the intended subnet/gateway.
2. Corrected the Traefik path assumption to use:
   - `/opt/docker-apps/Traefik/config/letsencrypt`
3. Diagnosed permission issues with `namei`, ownership checks, and user/group reasoning.
4. Corrected the guidance:
   - directories need execute bits
   - `letsencrypt` should be a directory
   - `acme.json` should be a file with tight permissions
5. Established two valid permission models:
   - `1000:1000` with `700` directory and `600` file
   - or `debian:docker` with group-shared permissions if operationally needed

## Key Findings
- The directory path was wrong at first because the real per-app layout is `/opt/docker-apps/<app>/config`.
- A directory set to `0600` cannot be traversed or written into normally because it lacks execute permission.
- `acme.json` should be the file restricted to `600`, not the directory.
- Host-side group membership for the Docker socket is a separate concern from Traefik app data ownership.

## Resolution
The correct Traefik ACME storage layout and permission model were re-established:
- use `/opt/docker-apps/Traefik/config/letsencrypt`
- ensure the directory has executable permission
- ensure `acme.json` is tightly permissioned

## Validation
Validation included:
- checking path existence
- checking directory and file ownership/perms
- confirming the intended bridge network definition
- reasoning through SFTP/WinSCP write behavior

## Follow-Up Tasks
- confirm Traefik compose volume mounts align with the corrected ACME path
- recreate or restore `acme.json` if needed
- restart Traefik and confirm certificate storage works

## Lessons Learned
- Secret files and secret directories require different permission models.
- A directory without execute permission behaves like an inaccessible path even if ownership is otherwise correct.
- Reverse proxy recovery work should validate both network and storage assumptions.

---

# Standardize App Permissions Under /opt/docker-apps/<App>/config

## Summary
The restored environment required a consistent permissions policy for application directories stored under `/opt/docker-apps/<App>/config`. Special handling was discussed for Traefik, Authelia, Gluetun, DB-backed apps, TubeArchivist, Plex, and related services.

## Environment
- App root: `/opt/docker-apps`
- Per-app layout: `/opt/docker-apps/<App>/config`
- Runtime UID/GID standard: `1000:1000`

## Problem
Restored files from migration or backup could preserve old ownership or overly open/overly restrictive modes. Some apps require special handling for secrets, DBs, or media/transcode/log access.

## Symptoms
- Permission denied errors in Traefik-related paths
- Need to decide whether `1000:1000` or `debian:docker` was appropriate
- Concern about app-specific special cases

## Actions Taken
1. Established a baseline permissions policy:
   - ownership `1000:1000`
   - directories `2775`
   - files `0664`
2. Identified categories requiring tighter permissions:
   - `.env`
   - `acme.json`
   - keys
   - VPN credentials
   - Authelia config
3. Identified DB file patterns that should be `0660`.
4. Documented app-specific exceptions for Traefik, Authelia, Gluetun, TubeArchivist, Plex, Tautulli, Arr stack, Syncthing, and selected web apps.

## Key Findings
- Most apps can use one sane baseline.
- Secret files should be `0600`.
- DB files should usually be `0660`.
- Traefik `acme.json` is a must-tighten file.
- OpenSearch data for TubeArchivist should not be world-readable.
- Plex transcode benefits from a sticky temp-style directory.

## Resolution
A reusable permissions checklist and shell snippets were developed for the `/opt/docker-apps/<App>/config` layout.

## Validation
Validation was intended through:
- `ls -l`
- `namei -l`
- secret file checks
- app startup behavior after permission normalization

## Follow-Up Tasks
- apply the baseline and special-case permissions to restored apps
- audit secret file permissions after full restore
- verify the host Docker socket access model for Traefik separately

## Lessons Learned
- Baseline-plus-exceptions is more maintainable than one-off manual permissions.
- Numeric UID/GID alignment with container PUID/PGID is usually the cleanest host-side model.
- Secret directories and secret files must be treated differently.

---

# Increase VM 100 Resources and Discuss HA Across Dissimilar Nodes

## Summary
VM 100 started with 2 GiB of RAM and later required an increase. CPU sizing and the implications of running HA across a more powerful tower PC and a weaker Intel NUC were also discussed.

## Environment
- VM: `100`
- Proxmox HA context:
  - stronger tower PC
  - weaker Intel NUC
- Resource targets discussed:
  - RAM increase to 4 GiB
  - possible CPU increase

## Problem
The rebuilt Docker VM needed more memory, and there was a broader design question about how to handle CPU sizing in a cluster with mixed host performance.

## Symptoms
- VM memory was only 2 GiB
- Desire to increase to 4 GiB and possibly raise CPU allocation
- Concern that a VM sized for a tower might not fit or perform similarly on a weaker HA target

## Actions Taken
1. Proposed changing VM memory to 4 GiB.
2. Discussed increasing CPU with Proxmox `qm set`.
3. Explained that one VM has one config, even in HA.
4. Discussed using a portable CPU model instead of `host` if live migration or HA portability across dissimilar nodes matters.
5. Discussed using maximum topology plus boot-time online vCPU adjustment via hookscript as a more advanced option.

## Key Findings
- RAM increase is straightforward.
- CPU sizing is more nuanced in mixed-node HA:
  - one VM config applies across nodes
  - `cpu: host` is best performance but worse portability
  - portable CPU models help with migration across different hardware
- The final resource decision depends on whether migration portability or performance is more important.

## Resolution
The intended direction was to increase VM memory to 4 GiB and consider a moderate CPU increase, with awareness that HA across dissimilar nodes requires deliberate CPU model choices.

## Validation
No final resource reconfiguration was confirmed in-guest in this session, but the correct Proxmox resource-setting approach was established.

## Follow-Up Tasks
- set final RAM and CPU values on VM 100
- decide whether to prioritize `cpu: host` performance or a portable CPU model
- document HA behavior expectations across tower and NUC nodes

## Lessons Learned
- Resource changes are easy; mixed-node portability is the hard part.
- HA design should account for the weakest node that may need to start the VM.

---

# Command Reference

## Command
```bash
qm clone 9000 100 --name debian-docker --storage cephpool --full 1
```

**What it does**  
Creates VM 100 from template 9000 as a full clone on the Ceph RBD-backed storage pool `cephpool`.

**Important flags**
- `9000`: source template VM ID
- `100`: destination VM ID
- `--name debian-docker`: sets the VM name
- `--storage cephpool`: places clone storage on the Ceph pool
- `--full 1`: creates an independent full clone instead of a linked clone

**Why it was used**  
To rebuild the main Docker VM cleanly.

**Expected result**  
A new VM 100 exists on `cephpool` and can be configured with cloud-init and an extra data disk.

**What failure indicates**  
Template, storage, or Proxmox clone errors.

**Risk**  
Low to moderate. It creates a new VM but does not by itself destroy the old one.

---

## Command
```bash
qm set 100 --scsihw virtio-scsi-single
```

**What it does**  
Sets the guest’s SCSI controller to `virtio-scsi-single`.

**Why it was used**  
To provide a modern, stable controller for multiple attached disks.

**Expected result**  
The VM configuration shows the selected SCSI controller.

**What failure indicates**  
VM config or Proxmox-side issue.

**Proxmox relevance**  
Controller choice affects how additional disks are presented to the guest.

---

## Command
```bash
qm set 100 --scsi1 cephpool:0,size=150G,ssd=1,discard=on,cache=writeback
```

**What it does**  
Attempts to create a new Ceph-backed disk and attach it as `scsi1`.

**Important flags**
- `cephpool:0`: create a new disk on `cephpool`
- `size=150G`: intended disk size
- `ssd=1`: mark as SSD-like
- `discard=on`: allow discard/TRIM semantics
- `cache=writeback`: use writeback caching

**Why it was used**  
To create the dedicated Docker data disk that would later mount at `/var/lib/docker`.

**Expected result**  
A new Ceph RBD image appears and the VM config shows `scsi1`.

**What failure indicates**  
Incorrect Proxmox/Ceph disk syntax or storage-layer handling issues.

**Risk**  
Moderate. Mis-specified storage arguments can create an unusable disk.

**Safer alternative**  
Verify the resulting disk immediately with `qm config 100` and storage inspection before proceeding.

---

## Command
```bash
qm set 100 --ide2 cephpool:cloudinit
```

**What it does**  
Attaches a cloud-init disk to VM 100 on `cephpool`.

**Why it was used**  
To provide NoCloud seed data built from Proxmox cloud-init settings.

**Expected result**  
The VM has an `ide2` cloud-init drive attached.

**What failure indicates**  
If it reports `File exists`, the cloud-init volume is already present and should not be recreated.

**Risk**  
Low.

---

## Command
```bash
qm set 100 --cicustom "user=local:snippets/docker-userdata.yml,network=local:snippets/docker-net.yml"
```

**What it does**  
Tells Proxmox to use custom cloud-init snippet files for user-data and network-config.

**Important arguments**
- `user=local:snippets/docker-userdata.yml`
- `network=local:snippets/docker-net.yml`

**Why it was used**  
The default cloud-init template behavior was not sufficient for the Docker VM’s custom provisioning.

**Expected result**  
`qm config 100` reflects the custom cloud-init snippet references.

**What failure indicates**  
Snippet path or storage content-type issues.

**Proxmox relevance**  
This is how Proxmox consumes user-managed cloud-init YAML from snippet-capable storage.

---

## Command
```bash
qm cloudinit update 100
```

**What it does**  
Regenerates the cloud-init ISO for VM 100 after snippet or config changes.

**Why it was used**  
To ensure updated user-data and network-config were baked into the next boot.

**Expected result**  
A fresh cloud-init seed image is generated.

**What failure indicates**  
Cloud-init disk problems or malformed VM config.

---

## Command
```bash
qm terminal 100
```

**What it does**  
Opens the serial console for VM 100 from the Proxmox host.

**Why it was used**  
To inspect boot logs, cloud-init output, and early mount failures when SSH was not yet reliable.

**Expected result**  
Live serial console output from the guest.

**What failure indicates**  
Console misconfiguration or a VM state issue.

**Proxmox relevance**  
Serial console access is often the fastest path to diagnose cloud-image first-boot issues.

---

## Command
```bash
lsblk -f
```

**What it does**  
Lists block devices, filesystems, labels, and mountpoints.

**Why it was used**  
To confirm whether `/dev/sdb` existed and whether it had a filesystem.

**Expected result**  
`sdb` appears with filesystem and label once formatted.

**What failure indicates**  
If `sdb` lacks a filesystem, the Docker data disk has not been initialized.

---

## Command
```bash
sudo mkfs.ext4 -F -L docker-data /dev/sdb
```

**What it does**  
Creates an ext4 filesystem on `/dev/sdb` with label `docker-data`.

**Important flags**
- `-F`: force filesystem creation
- `-L docker-data`: assign a filesystem label

**Why it was used**  
To recover from the first-boot failure where `/dev/sdb` existed but had no ext4 filesystem.

**Expected result**  
`lsblk -f` and `blkid` show ext4 and label `docker-data`.

**What failure indicates**  
Disk problems, permissions problems, or use of the wrong device.

**Risk**  
High. This destroys existing contents on `/dev/sdb`.

**Safer alternative**  
Double-check the target device with `lsblk -f` before running it.

---

## Command
```bash
sudo mount -a
```

**What it does**  
Attempts to mount all entries from `/etc/fstab`.

**Why it was used**  
To activate newly added filesystem and bind mount definitions.

**Expected result**  
All valid `fstab` entries mount without error.

**What failure indicates**  
Bad paths, missing source directories, missing filesystems, or invalid `fstab` syntax.

**Risk**  
Moderate. A bad `fstab` can break later boots if not corrected.

---

## Command
```bash
sudo systemctl start docker
```

**What it does**  
Starts the Docker daemon.

**Why it was used**  
Docker could only start after `/var/lib/docker` was successfully mounted from `/dev/sdb`.

**Expected result**  
Docker service becomes active.

**What failure indicates**  
Dependency or storage-root problems.

**Docker relevance**  
Docker will fail or behave incorrectly if its data-root is unavailable or mounted on the wrong filesystem.

---

## Command
```bash
sudo systemctl status docker --no-pager
```

**What it does**  
Shows Docker service status without invoking a pager.

**Why it was used**  
To verify whether Docker was running after storage fixes.

**Expected result**  
`active (running)`.

**What failure indicates**  
Mount dependency failure, daemon config issue, or container runtime issue.

---

## Command
```bash
findmnt /var/lib/docker /opt/docker-apps /opt/compose
```

**What it does**  
Shows live mount sources and types for the requested targets.

**Why it was used**  
To verify the Docker data mount and bind mounts, and to detect layered or duplicate mounts.

**Expected result**  
`/var/lib/docker` points to `/dev/sdb` or the ext4 label; `/opt/docker-apps` and `/opt/compose` point to bind sources under `/var/lib/docker`.

**What failure indicates**  
Incorrect bind mounts, stale mounts, or mount source problems.

---

## Command
```bash
cloud-init status --long
```

**What it does**  
Reports detailed cloud-init state in the guest.

**Why it was used**  
To determine whether provisioning had completed or failed.

**Expected result**  
Cloud-init modules complete without fatal errors.

**What failure indicates**  
Provisioning or datasource issues.

**Cloud-init relevance**  
Useful for separating provisioning failure from ordinary system boot behavior.

---

## Command
```bash
Likely command used:
cloud-init devel schema --config-file /var/lib/vz/snippets/docker-userdata.yml
```

**What it does**  
Validates the cloud-init YAML file against the expected schema.

**Why it was used**  
To diagnose the invalid cloud-config warning and catch malformed YAML before reuse.

**Expected result**  
Validation passes without schema errors.

**What failure indicates**  
The YAML contains unsupported or malformed keys.

**Safer alternative**  
Validate before attaching the snippet to a production VM.

---

## Command
```bash
find /srv/remotemount/NAS -maxdepth 5 -iname 'backup-[date removed].tar*' -printf '%p\n'
```

**What it does**  
Searches the NAS-mounted backup tree for the expected Offen backup archive.

**Why it was used**  
The original archive path assumption was wrong and needed to be corrected.

**Expected result**  
Prints the full path to the matching archive.

**What failure indicates**  
Wrong path assumption, missing NAS mount, or missing backup file.

---

## Command
```bash
tar -tzf "/srv/remotemount/NAS/Tools/Backups/Docker/offen/backup-[date removed].tar.gz" | head -n 20
```

**What it does**  
Lists the first 20 entries in the gzipped tar archive without extracting it.

**Why it was used**  
To determine the internal path structure and the correct strip count for restoration.

**Expected result**  
Archive entries showing the leading directories, such as `/backup/my-app-backup/...`.

**What failure indicates**  
Bad path, archive corruption, or wrong compression assumption.

---

## Command
```bash
sudo tar --numeric-owner --same-owner --acls --xattrs -xpf "$ARCH" -C /opt/docker-apps --strip-components=2 -z
```

**What it does**  
Extracts the Offen archive into `/opt/docker-apps`, removing the first two path components.

**Important flags**
- `--numeric-owner`: preserve numeric UID/GID
- `--same-owner`: restore ownership if possible
- `--acls --xattrs`: preserve ACLs and extended attributes
- `-xpf`: extract from file and preserve permissions
- `-C /opt/docker-apps`: destination directory
- `--strip-components=2`: remove `backup/my-app-backup`
- `-z`: treat input as gzip-compressed

**Why it was used**  
The archive layout was `/backup/my-app-backup/<AppName>/...`, while the live destination should be `/opt/docker-apps/<AppName>/...`.

**Expected result**  
App directories appear directly under `/opt/docker-apps`.

**What failure indicates**  
Wrong strip count, path problems, or archive issues.

**Risk**  
Moderate to high. This can overwrite existing restored data.

**Safer alternative**  
Extract into a staging directory first, then `rsync` into place.

---

## Command
```bash
sudo rsync -aHAX --numeric-ids --partial --append-verify --info=progress2 --stats --bwlimit=12M -e "ssh -o ServerAliveInterval=30 -o ServerAliveCountMax=6" root@192.168.16.100:"/DockerAppData(old)/" /opt/docker-apps
```

**What it does**  
Pulls app data from the old host into `/opt/docker-apps` with metadata preservation, throttling, and resumable transfer behavior.

**Important flags**
- `-aHAX`: archive, hardlinks, ACLs, xattrs
- `--numeric-ids`: preserve UID/GID numerically
- `--partial`: keep partial files
- `--append-verify`: resume and verify appended files
- `--info=progress2 --stats`: detailed progress and summary
- `--bwlimit=12M`: rate limit
- SSH keepalive options: prevent idle disconnects

**Why it was used**  
To move a large Docker application tree safely over the LAN even if connections dropped.

**Expected result**  
Data copies into `/opt/docker-apps` and can be resumed if interrupted.

**What failure indicates**  
SSH, path, permission, or network interruption issues.

**Risk**  
Moderate. Running on the wrong host or wrong destination can sync into the wrong place.

**Safer alternative**  
Echo `hostname` and IP before starting long transfers.

---

## Command
```bash
sudo rsync -aHAXn --delete --info=stats2,flist0,del0 -e "ssh -o ServerAliveInterval=30 -o ServerAliveCountMax=6" root@192.168.16.100:"/DockerAppData(old)/" /opt/docker-apps
```

**What it does**  
Runs a dry-run rsync comparison without changing files.

**Why it was used**  
To confirm that the migration had completed and source and destination matched.

**Expected result**  
Zero files transferred when the trees are fully in sync.

**What failure indicates**  
Remaining drift between source and destination.

---

## Command
```bash
find /opt/compose -type f \( -iname 'docker-compose.yml' -o -iname 'compose.yml' -o -iname '*.yml' -o -iname '*.yaml' \)
```

**What it does**  
Recursively finds compose files under `/opt/compose`.

**Why it was used**  
Compose files were not stored flat under `/opt/compose`; they lived in stack subdirectories.

**Expected result**  
A list of actual compose file paths.

**What failure indicates**  
Wrong root path or missing compose files.

---

## Command
```bash
docker compose -f /opt/compose/dockge/compose.yml up -d
```

**What it does**  
Starts the Dockge stack using the correct nested compose file path.

**Why it was used**  
The earlier command assumed a nonexistent path `/opt/compose/dockge.yml`.

**Expected result**  
Dockge containers start in detached mode.

**What failure indicates**  
Wrong path, compose syntax problem, or runtime issue.

**Docker relevance**  
`docker compose -f` allows stack management without changing into the compose directory.

---

## Command
```bash
find /opt/compose -type f \( -name '*.yml' -o -name '*.yaml' \) -exec sed -ri.bak -e 's/\r$//' -e "/^[[:space:]]*version:[[:space:]]*['\"]?3(\.[0-9]+)?['\"]?[[:space:]]*(#.*)?$/d" {} +
```

**What it does**  
Recursively edits compose files in place, removes Windows CRLF if present, and deletes deprecated `version: "3.x"` lines.

**Why it was used**  
To clean up legacy Compose syntax across many stack files.

**Expected result**  
No remaining top-level `version:` declarations matching 3.x, with `.bak` rollback files preserved.

**What failure indicates**  
Wrong file targeting or shell quoting issues.

**Risk**  
Moderate. Bulk in-place edits affect many files.

**Safer alternative**  
Run a dry-run `grep` first and keep backups until validation is complete.

---

## Command
```bash
docker network create --driver bridge --subnet 172.35.0.0/16 --gateway 172.35.0.1 traefik-proxy
```

**What it does**  
Creates the `traefik-proxy` Docker bridge network with the specified subnet and gateway.

**Why it was used**  
Traefik and proxied services needed a known shared bridge network.

**Expected result**  
`traefik-proxy` exists with the requested IPAM settings.

**What failure indicates**  
Name conflict or subnet overlap.

**Docker relevance**  
A shared bridge network is the standard pattern for Traefik-to-service communication on a single Docker host.

---

## Command
```bash
namei -l /opt/docker-apps/Traefik/config/letsencrypt/acme.json
```

**What it does**  
Displays permissions and ownership for every path component from `/` to the target file.

**Why it was used**  
To diagnose WinSCP and shell permission errors in the Traefik `letsencrypt` path.

**Expected result**  
Each directory in the chain is traversable and the file exists with the intended ownership and mode.

**What failure indicates**  
Missing directories or insufficient execute/read/write permission somewhere in the path.

---

## Command
```bash
sudo install -m 600 -o 1000 -g 1000 /dev/null /opt/docker-apps/Traefik/config/letsencrypt/acme.json
```

**What it does**  
Creates `acme.json` if missing, with strict permissions and explicit ownership.

**Important flags**
- `-m 600`: set file mode to 600
- `-o 1000 -g 1000`: set owner/group
- `/dev/null`: source for creating an empty file

**Why it was used**  
Traefik requires `acme.json` to exist with strict permissions.

**Expected result**  
An empty but correctly permissioned `acme.json` at the target path.

**What failure indicates**  
Missing parent directory or permission problem.

**Risk**  
Moderate. If the file already exists, this can replace it depending on usage context.

**Safer alternative**  
Use `touch` and then `chmod`/`chown` if preserving existing contents is critical.

---

## Command
```bash
qm set 100 --memory 4096
```

**What it does**  
Sets VM 100 memory allocation to 4096 MiB (4 GiB).

**Why it was used**  
The rebuilt Docker VM initially had only 2 GiB and needed more RAM.

**Expected result**  
VM config reflects 4 GiB of memory.

**What failure indicates**  
VM config or Proxmox-side issue.

**Proxmox relevance**  
RAM sizing directly affects guest workload stability and HA fit on target nodes.

---

## Command
```bash
Likely command used:
qm set 100 --cpu host --sockets 1 --cores 2
```

**What it does**  
Sets CPU model and topology for the VM.

**Why it was discussed**  
The VM may need more CPU, but HA portability across mismatched nodes complicates the choice.

**Expected result**  
VM config reflects the new CPU topology.

**What failure indicates**  
Proxmox config issue or an architectural mismatch with migration requirements.

**Risk**  
Low for the config change itself; higher operationally if `cpu: host` is used across mismatched HA nodes.

**Safer alternative**  
Use a portable baseline CPU model when cross-node migration compatibility matters more than peak performance.
