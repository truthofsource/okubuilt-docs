---
title: "Recover VM 100 from Emergency Mode with a Helper VM"
track: "infrastructure"
category: "storage"
type: "runbook"
logical_order: 60
date_rule: "Dates are removed from filenames, visible headings, indexes, generated metadata, and runbook body content."
---

# Recover VM 100 from Emergency Mode with a Helper VM

## Summary
VM 100 entered emergency mode again. A helper VM workflow was used to attach VM 100’s disk, inspect the root filesystem offline, and repair configuration issues that were preventing normal boot.

## Environment
- Proxmox VE
- VM 100: Debian-based Docker VM
- Helper VM: VM 101
- Storage:
  - `cephpool:vm-100-disk-0`
  - prior failed assumption of `local-lvm:vm-100-disk-0`
- Guest filesystem:
  - ext4 root partition
  - EFI partition present
- Access methods discussed:
  - Proxmox VNC/console
  - SSH
  - serial console concepts

## Problem
VM 100 failed to boot normally and dropped into emergency mode.

## Symptoms
- VM 100 entered emergency mode again.
- Initial attempt to attach VM 100’s disk to the helper VM failed with:
  - `no such logical volume pve/vm-100-disk-0`
- Hostname confusion occurred later, making the active VM appear to be `helper-vm`.
- Password/login recovery work was also needed after the filesystem work.

## Actions Taken
1. Attempted to attach VM 100’s disk to helper VM 101 using an incorrect storage target.
2. Corrected the disk attachment to Ceph-backed storage.
3. Installed and enabled SSH server on the helper VM so commands could be pasted more easily than through VNC.
4. Used `lsblk` to identify the attached disk and partitions.
5. Determined that the attached VM 100 root filesystem was on `/dev/sda1` in the helper VM context.
6. Mounted the root filesystem and later bind-mounted `/dev`, `/proc`, `/sys`, and `/run` for chroot access.
7. Entered a chroot to repair login-related configuration and user access.

Important commands used:
```bash
qm set 101 -scsi1 cephpool:vm-100-disk-0
```
Attach VM 100’s Ceph-backed disk to helper VM 101.

```bash
lsblk -o NAME,SIZE,FSTYPE,TYPE,MOUNTPOINT
```
Identify the attached disk and its partitions.

```bash
sudo mount /dev/sda1 /mnt/vm100
for d in dev proc sys run; do sudo mount --bind /$d /mnt/vm100/$d; done
sudo chroot /mnt/vm100 /bin/bash
```
Mount the offline root filesystem and enter it for repair.

## Key Findings
- The VM 100 disk was not on `local-lvm`; it was on `cephpool`.
- The helper VM saw:
  - its own disk as `sdb`
  - VM 100’s root disk as `sda`
- The actual root filesystem was on the partition `/dev/sda1`, not the whole disk device.
- Offline repair through chroot was possible once the correct partition was mounted.

## Resolution
The helper VM workflow succeeded once the correct Ceph disk was attached and the correct root partition was mounted.

## Validation
- `lsblk` showed a normal Linux filesystem hierarchy after mounting `/dev/sda1`.
- Chroot launched successfully:
  - `root@helper-vm:/#`

## Follow-Up Tasks
- Detach VM 100’s disk from the helper VM after repairs.
- Document the correct Ceph-backed helper VM procedure.
- Keep a known-good helper VM with SSH enabled for future recovery.

## Lessons Learned
- Always verify the VM disk’s real Proxmox storage backend before attaching it to a helper VM.
- In helper VM recovery work, expect to mount a partition such as `/dev/sdX1`, not the parent disk.
- SSH access to the helper VM is much easier than relying on pasted commands in VNC.

# Restore Console and User Access on VM 100

## Summary
After offline access to VM 100 was obtained, login recovery work focused on restoring usable local credentials and removing confusion caused by broken or partial recovery attempts.

## Environment
- VM 100 Debian guest
- Helper VM chroot into VM 100 root filesystem
- Users involved:
  - `debian`
  - `rescue`
- SSH configuration file:
  - `/etc/ssh/sshd_config`

## Problem
The expected password was no longer working for console login, and earlier password reset attempts did not succeed.

## Symptoms
- Passwords were not working at the console.
- `qm set 100 -ciuser debian -cipassword ...` did not solve the issue.
- Earlier chroot attempts were interrupted or mangled.
- One repair attempt showed:
  - `passwd: user 'debian' does not exist`
  - `chpasswd: (user debian) pam_chauthtok() failed`
- Another attempt showed:
  - `useradd: command not found`
- A pasted command corrupted the SSH config update line.

## Actions Taken
1. Determined that cloud-init password injection was not a reliable fix for the current state.
2. Entered chroot again, this time with the correct bind mounts and a fixed `PATH`.
3. Removed `/etc/nologin` if present.
4. Ensured the `sudo` group existed.
5. Created or reset a `rescue` account.
6. Reset the `debian` password.
7. Corrected SSH password authentication directives in `sshd_config`.

Important commands used:
```bash
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
```
Restore admin tools inside the chroot environment.

```bash
rm -f /etc/nologin || true
getent group sudo >/dev/null || groupadd sudo
```
Ensure local logins are not blocked and sudo group exists.

```bash
id -u rescue >/dev/null 2>&1 || /usr/sbin/useradd -m -s /bin/bash -G sudo rescue
echo 'rescue:Docker123' | /usr/sbin/chpasswd

id -u debian >/dev/null 2>&1 || /usr/sbin/useradd -m -s /bin/bash -G sudo debian
echo 'debian:Docker123' | /usr/sbin/chpasswd
```
Create/reset local administrative accounts.

```bash
sed -i -E 's/^\s*#?\s*PasswordAuthentication\s+.*/PasswordAuthentication yes/' /etc/ssh/sshd_config
sed -i -E 's/^\s*#?\s*(KbdInteractiveAuthentication|ChallengeResponseAuthentication)\s+.*/KbdInteractiveAuthentication yes/' /etc/ssh/sshd_config
/usr/sbin/sshd -t
```
Repair SSH password-auth directives and validate the SSH config syntax.

## Key Findings
- The earlier cloud-init password approach was not the right recovery path.
- The chroot environment initially lacked a working admin `PATH`, which caused `useradd` not to be found.
- Pasted multi-line commands could corrupt config-editing lines if entered carelessly.
- Once the chroot environment was prepared correctly, account repair succeeded.

## Resolution
A clean chroot session with a proper `PATH` was used to reset the local login environment and restore administrative access.

## Validation
- `chpasswd` succeeded for both `rescue` and `debian`.
- `sshd -t` passed.
- The chroot exit completed cleanly after the account work.

## Follow-Up Tasks
- Log into VM 100 using the restored account and immediately set a known-good permanent password.
- Remove the temporary rescue account once stable access is confirmed.
- Review whether cloud-init should continue to manage login credentials for this VM.

## Lessons Learned
- For broken Linux guests, offline chroot repair is often more reliable than trying to force cloud-init password changes.
- Always set a valid `PATH` in rescue/chroot sessions.
- Test SSH configuration with `sshd -t` before rebooting or relying on it.

# Diagnose Hostname Confusion and Cloud-Init Behavior on VM 100

## Summary
During recovery, VM 100 appeared to rename itself to `helper-vm`. Investigation showed cloud-init was still active and the system hostname state was inconsistent.

## Environment
- VM 100 Debian guest
- cloud-init enabled
- Files examined:
  - `/etc/hostname`
  - `/etc/hosts`
  - `/etc/cloud/cloud.cfg`
  - `/etc/cloud/cloud.cfg.d/*`

## Problem
VM 100 appeared to be running with the wrong hostname.

## Symptoms
- `hostnamectl` reported:
  - `Static hostname: helper-vm`
- `/etc/hostname` contained `helper-vm`
- `cloud-init` logs showed it was active on boot.
- `preserve_hostname: false` was set.

## Actions Taken
1. Checked hostname status and local hostname files.
2. Queried cloud-init state and logs.
3. Considered using cloud-init clean + reapplying cicustom data later.

Important commands used:
```bash
hostnamectl
cat /etc/hostname
sed -n '1,40p' /etc/hosts
```
Inspect current hostname state.

```bash
sudo journalctl -b | grep -Ei 'set hostname|cloud-ini|dhcp|dhclient|networkd.*hostname'
systemctl is-enabled cloud-init || true
cloud-init status || true
grep -i preserve_hostname /etc/cloud/cloud.cfg || true
ls -1 /etc/cloud/cloud.cfg.d/ || true
```
Check cloud-init activity and hostname-related behavior.

## Key Findings
- cloud-init was still enabled and had run on boot.
- `preserve_hostname: false` meant cloud-init was allowed to rewrite hostname state.
- The VM identity and hostname state had become inconsistent during recovery work.

## Resolution
No final hostname remediation was completed in this session, but the cause was narrowed to cloud-init-managed hostname behavior.

## Validation
- Hostname drift was confirmed through both `hostnamectl` and file inspection.
- cloud-init’s active role was confirmed through logs and status.

## Follow-Up Tasks
- Decide whether to disable cloud-init after the VM is rebuilt or stabilized.
- Reassert the intended hostname through the VM’s cloud-init data or guest config.
- Verify machine identity and cloud-init seed behavior.

## Lessons Learned
- Cloud-init can reapply identity state during recovery if left enabled.
- Hostname anomalies after clone/helper workflows should always prompt a cloud-init review.

# Diagnose Docker Mount and Bind Issues on VM 100

## Summary
After basic guest recovery, attention shifted to Docker storage paths. `/opt/compose` and `/opt/docker-apps` were expected to be backed by `/var/lib/docker/compose` and `/var/lib/docker/appdata`, but the mount state and bind direction were inconsistent.

## Environment
- VM 100 Debian Docker VM
- Docker root on `/var/lib/docker`
- Expected bind layout:
  - `/var/lib/docker/appdata`
  - `/var/lib/docker/compose`
  - `/opt/docker-apps`
  - `/opt/compose`
- systemd unit:
  - `docker-verify.mountguard.service`

## Problem
Docker-related bind mounts were not behaving as expected, and `/opt/compose` appeared empty.

## Symptoms
- `findmnt` initially showed no active mounts for the expected paths.
- `/etc/fstab` did not contain the `/var/lib/docker` mount entry at one point.
- `docker-verify.mountguard.service` did not start because:
  - `ConditionPathIsMountPoint=/var/lib/docker was not met`
- `docker.service` still ran even though `/var/lib/docker` was not a mountpoint.
- `/opt/compose` appeared empty.
- Bind test files proved the bind relationship worked only after repair.
- Attempts to inspect mounted paths without root produced `Permission denied`.

## Actions Taken
1. Checked active mount state.
2. Reviewed current `/etc/fstab`.
3. Repaired the guard script typo.
4. Added missing `/var/lib/docker` and bind mount entries.
5. Disabled the guard temporarily when it blocked startup.
6. Wrote a new Docker systemd override.
7. Verified bind behavior with test files.

Important commands used:
```bash
findmnt /var/lib/docker /var/lib/docker/appdata /var/lib/docker/compose || true
grep -Ev '^\s*#|^\s*$' /etc/fstab | sed -n '1,200p'
systemctl status docker-verify.mountguard.service --no-pager || true
systemctl status docker --no-pager || true
```
Check mount state, fstab contents, and Docker/guard unit status.

```bash
sudo mount -a
findmnt /var/lib/docker
```
Apply fstab mounts and verify Docker root state.

```bash
sudo bash -lc 'touch /opt/compose/.bindtest && ls -la /var/lib/docker/compose | grep bindtest || echo "compose bind not active"'
sudo bash -lc 'touch /opt/docker-apps/.bindtest && ls -la /var/lib/docker/appdata | grep bindtest || echo "appdata bind not active"'
```
Prove bind relationships by creating test files on one side and reading them on the other.

## Key Findings
- `/var/lib/docker` was at one point just part of the root filesystem, not a dedicated mount.
- The guard unit correctly refused to run when `/var/lib/docker` was not a mountpoint.
- A malformed or incomplete fstab and guard script contributed to confusion.
- The bind directions had to be carefully reviewed to match the intended layout.
- `/opt/compose` was functionally empty except for `.bindtest` and a small `dockge` directory.

## Resolution
The bind relationships were brought back into a working state for the current session, but the absence of expected compose content suggested that the compose files were either elsewhere or already lost.

## Validation
- `docker info` reported `Root=/var/lib/docker`.
- Bind tests showed `.bindtest` on both sides of the bind.
- `df -h /var/lib/docker` showed the filesystem in use.

## Follow-Up Tasks
- Confirm the intended canonical path direction and keep it consistent.
- Remove temporary `.bindtest` files.
- Revisit whether the guard should be re-enabled after the rebuild.
- Rebuild missing compose directories from backup or prior exports.

## Lessons Learned
- A working Docker daemon does not prove the Docker data disk is mounted correctly.
- `findmnt` and test files are the fastest way to prove whether a bind mount is real.
- systemd guard units are useful, but only when the underlying mount logic is correct.

# Restore NAS CIFS Mount Reliability and Symlink Support

## Summary
A CIFS-mounted NAS share was needed for backups, but backups failed with CIFS timeouts and symlink-related errors. The NAS mount was rebuilt with a clean credentials file and proper mount options, including `mfsymlinks`.

## Environment
- Debian guest VM
- NAS share:
  - `//192.168.16.21/Media`
- Mountpoint:
  - `/srv/remotemount/NAS`
- Credentials file:
  - `/root/.smbcredentials`
- systemd-generated units from `/etc/fstab`:
  - `srv-remotemount-NAS.automount`
  - `srv-remotemount-NAS.mount`

## Problem
Backups to the NAS failed because the share had both connectivity issues and symlink incompatibilities.

## Symptoms
- rsync errors like:
  - `Input/output error (5)` on symlink creation
- kernel logs:
  - `CIFS: VFS: \\192.168.16.21 has not responded in 180 seconds. Reconnecting...`
- Duplicate fstab entries caused:
  - `Duplicate entry in '/etc/fstab'?`
- Systemd initially could not show the generated units until the fstab state was corrected.

## Actions Taken
1. Confirmed the mount lacked the right options.
2. Created a root-only SMB credentials file.
3. Mounted the share manually with `mfsymlinks`.
4. Verified read/write access, ownership mapping, and symlink behavior.
5. Added a single canonical CIFS automount line to `/etc/fstab`.
6. Removed duplicate fstab entries and regenerated systemd units.
7. Verified the generated automount and mount units were active.

Important commands used:
```bash
sudo install -m 600 -o root -g root /dev/null /root/.smbcredentials
sudo bash -lc 'cat > /root/.smbcredentials <<EOF
username=admin
password=Kingsley1
# domain=WORKGROUP
EOF'
```
Create a protected SMB credentials file for CIFS mounts.

```bash
sudo mount -t cifs //192.168.16.21/Media /srv/remotemount/NAS \
  -o rw,vers=3.1.1,credentials=/root/.smbcredentials,uid=1000,gid=1000,iocharset=utf8,mfsymlinks,noperm,noserverino,dir_mode=0775,file_mode=0664,actimeo=1,cache=none
```
Mount the NAS manually with symlink emulation and explicit ownership mapping.

```bash
ln -s target.txt /srv/remotemount/NAS/_cifs_test/link-to-target
readlink /srv/remotemount/NAS/_cifs_test/link-to-target
cat /srv/remotemount/NAS/_cifs_test/link-to-target
```
Validate that symlink behavior works over CIFS.

```bash
systemctl list-units 'srv-remotemount-NAS.*' --all
systemctl status srv-remotemount-NAS.automount srv-remotemount-NAS.mount
```
Validate the fstab-generated automount units.

## Key Findings
- `mfsymlinks` was necessary for Linux symlink behavior over SMB.
- The share could be mounted with expected ownership as UID/GID 1000.
- Duplicate fstab lines caused systemd generator conflicts.
- Once cleaned up, the automount worked normally.

## Resolution
The NAS mount was rebuilt using a dedicated credentials file and a single correct `/etc/fstab` entry with systemd automount support and `mfsymlinks`.

## Validation
- Files could be created on the share as `debian:debian`.
- Symlink creation and dereferencing worked.
- `srv-remotemount-NAS.automount` and `srv-remotemount-NAS.mount` both appeared as loaded/generated and active.

## Follow-Up Tasks
- Consider increasing the idle timeout from 60 seconds if reconnects remain annoying.
- Monitor for further CIFS reconnect events.
- Reuse the same mount pattern for other shares if needed.

## Lessons Learned
- CIFS path issues and symlink issues should be solved before running bulk rsync jobs.
- Keep only one canonical fstab entry per mountpoint.
- systemd automounts are reliable once the generator input is clean.

# Backup Docker Appdata and Compose to NAS

## Summary
The goal shifted from fixing VM 100 in place to preserving Docker state for a future rebuild. Backups of `/opt/docker-apps` and `/opt/compose` were attempted to the NAS.

## Environment
- VM 100 (`debian-docker`)
- Docker appdata:
  - `/opt/docker-apps`
- Compose directory:
  - `/opt/compose`
- NAS target:
  - `/srv/remotemount/NAS/Backups/docker-VM`

## Problem
A full backup of Docker appdata and compose needed to be created before rebuilding the VM.

## Symptoms
- Initial backup attempts using more complex approaches led to confusion.
- `/opt/compose` appeared nearly empty:
  - `.bindtest`
  - `dockge`
- Initial snapshot verification showed:
  - appdata source about 811 MB
  - backup snapshot about 779 MB
  - compose source 8 KB
  - compose snapshot effectively empty
- CIFS read-ahead messages appeared during copy:
  - `CIFS: __readahead_batch() returned 257/1024`

## Actions Taken
1. Determined the canonical live source directories were:
   - `/opt/docker-apps`
   - `/opt/compose`
2. Created backup roots on the NAS.
3. Created an rsync exclude file for logs, caches, and temp data.
4. Created timestamped snapshots using rsync.
5. Performed size and file-count comparisons.
6. Spot-checked large files to confirm they existed in the backup.

Important commands used:
```bash
APPDATA_SRC="/opt/docker-apps"
COMPOSE_SRC="/opt/compose"
```
Set the actual source paths for backup.

```bash
TS="$(date +%F_%H%M%S)"
DEST_APP="$BASE/appdata/snap-$TS"
DEST_CMP="$BASE/compose/snap-$TS"
mkdir -p "$DEST_APP" "$DEST_CMP"

rsync -aHAX --delete --numeric-ids $EXC "$APPDATA_SRC"/ "$DEST_APP"/
rsync -aHAX --delete --numeric-ids $EXC "$COMPOSE_SRC"/ "$DEST_CMP"/
```
Create snapshot-style backups of appdata and compose.

## Key Findings
- The live compose directory on the VM was effectively empty except for minimal content.
- Appdata backup largely succeeded; missing items were later traced to exclusions and SMB restore complexity.
- The small compose snapshot was real, not just a display artifact.

## Resolution
A usable appdata backup path was established on the NAS. Compose recovery remained unresolved because the source compose directory was mostly empty.

## Validation
- Appdata snapshots existed on the NAS with many expected app directories.
- Spot checks confirmed large appdata files existed in the snapshot.
- Size and file-count comparisons were close enough to show the backup was mostly successful.

## Follow-Up Tasks
- Rebuild missing compose files from prior exports, backups, or previous chats.
- Consider archive-based backups instead of raw rsync to CIFS.
- Add verification steps to future backup jobs.

## Lessons Learned
- Appdata and compose should be backed up separately and verified separately.
- A nearly empty compose tree should be treated as a real recovery problem, not just a mount bug.
- Raw rsync to CIFS works, but archive-first workflows are safer for large restores.

# Restore Appdata from Offen Backup Archive

## Summary
A large Offen backup archive was restored back into `/opt/docker-apps` after missing files were discovered in the earlier NAS snapshot. The recovery focused on restoring all appdata content from a `tar.gz` archive.

## Environment
- VM 100 (`debian-docker`)
- Backup source:
  - `/srv/remotemount/NAS/Tools/Backups/Docker/offen/backup-[date removed].tar.gz`
- Restore target:
  - `/opt/docker-apps`
- Temporary extraction paths:
  - `/tmp/offen-restore-*`
  - `/var/tmp/offen-restore`
- Backup tool used originally:
  - Offen Docker Volume Backup

## Problem
Files were still missing after earlier backup and restore work. A complete restore from the older Offen archive was needed, and the archive layout was initially misunderstood.

## Symptoms
- Early restore attempts failed because:
  - the wrong `.tar` versus `.tar.gz` extension was assumed
  - archive extraction commands relied on lost shell variables after logout
  - restore attempts incorrectly targeted `/opt/docker-apps/Offen`
- One tar attempt failed with:
  - `tar (child): /archive.tar.gz: Cannot open: No such file or directory`
- Another tar path attempt failed with:
  - `tar: backup/my-app-backup: Not found in archive`
- The archive repeatedly showed:
  - `tar: Removing leading '/' from member names`
- CIFS messages appeared during copy:
  - `CIFS: __readahead_batch() returned 257/1024`

## Actions Taken
1. Confirmed the archive was really a `.tar.gz`.
2. Verified the archive with `gzip -t`.
3. Listed archive contents with `tar -tzf`.
4. Confirmed the archive root structure was:
   - `/backup/my-app-backup/...`
5. Copied the archive locally before extraction to avoid CIFS issues.
6. Extracted the payload into `/opt/docker-apps` using strip logic.
7. Observed that some content first landed under:
   - `/opt/docker-apps/backup/my-app-backup`
8. Moved payload contents up into `/opt/docker-apps`.
9. Used a staging workflow and later re-extracted the entire payload directly into `/opt/docker-apps`.
10. Considered overwrite semantics to restore deleted JSON, YAML, and DB files.

Important commands used:
```bash
gzip -t "$TMP/archive.tar.gz" && echo "gzip OK"
tar -tzf "$TMP/archive.tar.gz" | head -20
```
Validate archive integrity and inspect internal path layout.

```bash
sudo tar -xzpf "$TMP/archive.tar.gz" \
  -C "$DEST" \
  --strip-components=2 \
  /backup/my-app-backup
```
Extract the backup payload into the appdata root while dropping the wrapper path.

```bash
sudo rsync -a --remove-source-files /opt/docker-apps/backup/my-app-backup/ /opt/docker-apps/
```
Move restored payload contents up one level after an earlier wrapper-path extraction.

## Key Findings
- The backup archive was valid.
- The archive layout used an absolute top-level path:
  - `/backup/my-app-backup/...`
- The restore destination was the full `/opt/docker-apps` tree, not an `Offen` subdirectory.
- Missing files could still occur if they were not in the specific backup date being restored, or if later confusion about destination structure hid them.

## Resolution
A full appdata restore from the Offen archive into `/opt/docker-apps` was completed. The restored tree showed many expected application directories, including:
- `Radarr-ES`
- `Monica`
- `Overseerr`
- `Plex`
- `Traefik`
- `Notifiarr`
- and many others

## Validation
- `gzip -t` returned `gzip OK`.
- `tar -tzf` showed expected app directories under `/backup/my-app-backup`.
- `du -sh /opt/docker-apps` returned 45 GB after restore.
- `find /opt/docker-apps -maxdepth 2 -type d` showed many recovered application directories.

## Follow-Up Tasks
- Confirm whether all expected per-app files are present by checking specific known-missing JSON, YAML, and DB files.
- Restore `/opt/compose` separately, because this Offen archive was appdata-only.
- Decide whether to rebuild compose files manually or from other backups.
- Consider a safer future backup format:
  - archive-first locally
  - then transfer the archive to NAS

## Lessons Learned
- Always confirm the exact archive type and internal path structure before restoring.
- Shell variables are lost after logout; long restore workflows should be rerun from a fresh, self-contained set of commands.
- For large SMB-backed restores, copying the archive locally first is more reliable than extracting directly from the mounted share.
- Offen appdata backups do not automatically solve missing compose files.

# Command Reference

## Command
```bash
qm set 101 -scsi1 cephpool:vm-100-disk-0
```

### What it does
Attaches VM 100’s Ceph-backed disk to helper VM 101 as an extra SCSI disk.

### Important flags or arguments
- `qm set`: Modify a Proxmox VM config.
- `101`: Helper VM ID.
- `-scsi1`: Attach the disk as the second SCSI device.
- `cephpool:vm-100-disk-0`: The existing VM disk on Ceph storage.

### Why it was used
To mount and repair VM 100 offline from a helper VM.

### Expected result
VM 101 gains visibility of VM 100’s disk.

### Success or failure meaning
- Success: the disk appears in helper VM block devices.
- Failure: wrong storage backend or wrong disk identifier was used.

### Risk
Moderate. Attaching the wrong disk can risk modifying the wrong VM’s data.

### Safer alternative
Double-check with Proxmox VM config and storage listing before attaching.

## Command
```bash
lsblk -o NAME,SIZE,FSTYPE,TYPE,MOUNTPOINT
```

### What it does
Lists block devices, partitions, filesystems, and mountpoints.

### Important flags or arguments
- `-o`: Select output columns.

### Why it was used
To identify which device and partition belonged to the offline VM root disk.

### Expected result
A readable map of disks and partitions.

### Success or failure meaning
- Success: the correct root partition can be identified.
- Failure: attached disk missing or helper VM does not see the disk.

### Risk
Low.

### Safer alternative
None needed; this is a standard inspection command.

## Command
```bash
sudo mount /dev/sda1 /mnt/vm100
for d in dev proc sys run; do sudo mount --bind /$d /mnt/vm100/$d; done
sudo chroot /mnt/vm100 /bin/bash
```

### What it does
Mounts the offline guest root filesystem, bind-mounts critical pseudo-filesystems, and enters a chroot.

### Important flags or arguments
- `mount --bind`: Makes host pseudo-filesystems available inside the chroot.
- `chroot`: Changes the apparent root directory of the current shell.

### Why it was used
To repair VM 100 as if logged into its own root filesystem.

### Expected result
A root shell inside the mounted guest filesystem.

### Success or failure meaning
- Success: admin tools and configuration files can be edited in place.
- Failure: wrong partition mounted or missing bind mounts.

### Risk
High. This directly edits another system’s root filesystem.

### Safer alternative
Mount read-only first for inspection, then remount read-write only when ready.

## Command
```bash
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
```

### What it does
Sets a full administrative command path inside the current shell.

### Important flags or arguments
No flags.

### Why it was used
The rescue shell or chroot session did not have admin tools in the path.

### Expected result
Commands such as `useradd`, `groupadd`, and `chpasswd` become available.

### Success or failure meaning
- Success: admin commands can be executed.
- Failure: binaries may be missing from the chrooted system.

### Risk
Low.

## Command
```bash
rm -f /etc/nologin || true
getent group sudo >/dev/null || groupadd sudo
```

### What it does
Removes a file that blocks logins and ensures the `sudo` group exists.

### Important flags or arguments
- `-f`: Ignore missing file.
- `|| true`: Avoid aborting on benign failure.

### Why it was used
To restore login access in the recovered VM.

### Expected result
No login-block file and a valid `sudo` group.

### Success or failure meaning
- Success: local login barriers are removed.
- Failure: filesystem or chroot issues remain.

### Risk
Low.

## Command
```bash
id -u rescue >/dev/null 2>&1 || /usr/sbin/useradd -m -s /bin/bash -G sudo rescue
echo 'rescue:Docker123' | /usr/sbin/chpasswd

id -u debian >/dev/null 2>&1 || /usr/sbin/useradd -m -s /bin/bash -G sudo debian
echo 'debian:Docker123' | /usr/sbin/chpasswd
```

### What it does
Creates or resets local users and passwords.

### Important flags or arguments
- `useradd -m`: Create a home directory.
- `-s /bin/bash`: Set shell.
- `-G sudo`: Add user to the sudo group.
- `chpasswd`: Set password from stdin.

### Why it was used
To restore console and admin access.

### Expected result
Working local credentials for recovery.

### Success or failure meaning
- Success: passwords reset and user accounts exist.
- Failure: broken passwd/shadow state, bad chroot, or missing tools.

### Risk
Moderate. Password resets directly affect guest authentication.

## Command
```bash
sed -i -E 's/^\s*#?\s*PasswordAuthentication\s+.*/PasswordAuthentication yes/' /etc/ssh/sshd_config
sed -i -E 's/^\s*#?\s*(KbdInteractiveAuthentication|ChallengeResponseAuthentication)\s+.*/KbdInteractiveAuthentication yes/' /etc/ssh/sshd_config
/usr/sbin/sshd -t
```

### What it does
Enables SSH password-based authentication settings and validates the SSH daemon config.

### Important flags or arguments
- `sed -i`: Edit file in place.
- `-E`: Extended regex.
- `sshd -t`: Syntax check only.

### Why it was used
To repair password-auth SSH access after login problems.

### Expected result
A valid SSH config allowing password auth.

### Success or failure meaning
- Success: `sshd -t` exits cleanly.
- Failure: config file corruption or bad syntax remains.

### Risk
Moderate. A bad SSH config can lock out remote access.

### Safer alternative
Back up `sshd_config` before editing.

## Command
```bash
hostnamectl
cat /etc/hostname
sed -n '1,40p' /etc/hosts
```

### What it does
Inspects hostname state and static host mappings.

### Important flags or arguments
- `sed -n '1,40p'`: Print the first 40 lines.

### Why it was used
To understand why VM 100 appeared as `helper-vm`.

### Expected result
The current static hostname and local host configuration are displayed.

### Success or failure meaning
- Success: hostname drift is visible.
- Failure: deeper system corruption or missing tools.

### Risk
Low.

## Command
```bash
sudo journalctl -b | grep -Ei 'set hostname|cloud-ini|dhcp|dhclient|networkd.*hostname'
systemctl is-enabled cloud-init || true
cloud-init status || true
grep -i preserve_hostname /etc/cloud/cloud.cfg || true
ls -1 /etc/cloud/cloud.cfg.d/ || true
```

### What it does
Checks whether cloud-init or networking changed the hostname during boot.

### Important flags or arguments
- `journalctl -b`: Current boot logs.
- `grep -Ei`: Case-insensitive extended matching.

### Why it was used
To confirm whether cloud-init was still controlling hostname behavior.

### Expected result
Evidence of cloud-init activity and relevant settings.

### Success or failure meaning
- Success: root cause of hostname drift becomes visible.
- Failure: incomplete logs or missing cloud-init.

### Risk
Low.

## Command
```bash
findmnt /var/lib/docker /var/lib/docker/appdata /var/lib/docker/compose || true
grep -Ev '^\s*#|^\s*$' /etc/fstab | sed -n '1,200p'
systemctl status docker-verify.mountguard.service --no-pager || true
systemctl status docker --no-pager || true
```

### What it does
Checks actual mount state, active fstab entries, and Docker-related systemd unit status.

### Important flags or arguments
- `findmnt`: Shows real mount relationships.
- `grep -Ev`: Filters out comments and blank lines.
- `--no-pager`: Print full unit status directly.

### Why it was used
To diagnose why Docker root and bind mounts were inconsistent.

### Expected result
A clear picture of whether `/var/lib/docker` is really mounted and whether Docker guard logic is behaving.

### Success or failure meaning
- Success: mount state becomes clear.
- Failure: path confusion persists or units are broken.

### Risk
Low.

## Command
```bash
sudo mount -a
findmnt /var/lib/docker
```

### What it does
Applies all fstab mounts and then confirms whether Docker root is mounted.

### Important flags or arguments
- `mount -a`: Mount all eligible entries from fstab.

### Why it was used
To apply repaired mount definitions.

### Expected result
`/var/lib/docker` appears as a real mountpoint if fstab is correct.

### Success or failure meaning
- Success: dedicated Docker data mount is active.
- Failure: fstab entry wrong, device missing, or mount failed.

### Risk
Moderate. Bad fstab entries can cause boot or mount issues.

## Command
```bash
sudo bash -lc 'touch /opt/compose/.bindtest && ls -la /var/lib/docker/compose | grep bindtest || echo "compose bind not active"'
sudo bash -lc 'touch /opt/docker-apps/.bindtest && ls -la /var/lib/docker/appdata | grep bindtest || echo "appdata bind not active"'
```

### What it does
Creates a test file on one side of the bind and checks whether it appears on the other side.

### Important flags or arguments
- `bash -lc`: Run a login-like shell command string.
- `touch`: Create a file if missing.

### Why it was used
To prove whether the bind mounts were actually working.

### Expected result
The test file appears on the opposite path.

### Success or failure meaning
- Success: real bind relationship exists.
- Failure: bind not active or path direction wrong.

### Risk
Low.

## Command
```bash
sudo install -m 600 -o root -g root /dev/null /root/.smbcredentials
sudo bash -lc 'cat > /root/.smbcredentials <<EOF
username=admin
password=Kingsley1
# domain=WORKGROUP
EOF'
```

### What it does
Creates a protected SMB credentials file.

### Important flags or arguments
- `install -m 600`: Create file with strict permissions.
- `-o root -g root`: Root ownership.

### Why it was used
CIFS mounts needed credentials without exposing them in command history or fstab.

### Expected result
A root-readable-only credentials file.

### Success or failure meaning
- Success: CIFS mounts can authenticate.
- Failure: mount auth errors continue.

### Risk
High. Contains plaintext credentials.

### Safer alternative
Use a separate secret-management method if available.

## Command
```bash
sudo mount -t cifs //192.168.16.21/Media /srv/remotemount/NAS \
  -o rw,vers=3.1.1,credentials=/root/.smbcredentials,uid=1000,gid=1000,iocharset=utf8,mfsymlinks,noperm,noserverino,dir_mode=0775,file_mode=0664,actimeo=1,cache=none
```

### What it does
Mounts the NAS share manually over SMB/CIFS.

### Important flags or arguments
- `vers=3.1.1`: SMB protocol version.
- `credentials=...`: Use stored SMB credentials.
- `uid/gid=1000`: Present files as owned by the Debian user.
- `mfsymlinks`: Emulate Linux symlinks on SMB.
- `cache=none`: Minimize caching for correctness.
- `actimeo=1`: Keep attribute cache lifetime short.

### Why it was used
To validate a working mount before committing the config to fstab.

### Expected result
A working NAS mount with file ownership and symlink behavior matching Linux expectations.

### Success or failure meaning
- Success: NAS is accessible and Linux workflows work.
- Failure: credentials, share path, or SMB options are wrong.

### Risk
Moderate. A bad mount command can mask path issues or hang on network problems.

## Command
```bash
ln -s target.txt /srv/remotemount/NAS/_cifs_test/link-to-target
readlink /srv/remotemount/NAS/_cifs_test/link-to-target
cat /srv/remotemount/NAS/_cifs_test/link-to-target
```

### What it does
Creates and tests a symlink on the mounted NAS share.

### Important flags or arguments
- `ln -s`: Create symbolic link.
- `readlink`: Show link target.

### Why it was used
To prove `mfsymlinks` solved the SMB symlink problem.

### Expected result
The symlink resolves and file contents are readable through it.

### Success or failure meaning
- Success: SMB symlink emulation works.
- Failure: mount options are insufficient.

### Risk
Low.

## Command
```bash
systemctl list-units 'srv-remotemount-NAS.*' --all
systemctl status srv-remotemount-NAS.automount srv-remotemount-NAS.mount
```

### What it does
Checks the fstab-generated systemd automount and mount units.

### Important flags or arguments
- `--all`: Include inactive units.
- `status`: Show current unit state and logs.

### Why it was used
To validate the automount behavior after fixing `/etc/fstab`.

### Expected result
The automount unit is active and the mount unit activates on access.

### Success or failure meaning
- Success: the NAS mount is persistent and on-demand.
- Failure: fstab or systemd generator input is still wrong.

### Risk
Low.

## Command
```bash
rsync -aHAX --delete --numeric-ids "$APPDATA_SRC"/ "$DEST_APP"/
rsync -aHAX --delete --numeric-ids "$COMPOSE_SRC"/ "$DEST_CMP"/
```

### What it does
Copies appdata and compose trees to backup destinations while preserving metadata.

### Important flags or arguments
- `-a`: Archive mode.
- `-H`: Preserve hard links.
- `-A`: Preserve ACLs.
- `-X`: Preserve extended attributes.
- `--delete`: Remove files from destination not present in source.
- `--numeric-ids`: Preserve numeric ownership.

### Why it was used
To create restorable NAS snapshots of Docker state.

### Expected result
Backup snapshot directories matching the source tree.

### Success or failure meaning
- Success: backup snapshots are usable for restore.
- Failure: SMB or permission issues interrupt the copy.

### Risk
Moderate. `--delete` can erase destination content if paths are reversed.

## Command
```bash
gzip -t "$TMP/archive.tar.gz" && echo "gzip OK"
tar -tzf "$TMP/archive.tar.gz" | head -20
```

### What it does
Tests archive integrity and lists the first few archive entries.

### Important flags or arguments
- `gzip -t`: Validate gzip compression layer.
- `tar -tzf`: List contents of a gzip-compressed tar archive.

### Why it was used
To confirm the Offen backup archive was valid and to inspect its internal path layout.

### Expected result
`gzip OK` and visible archive entries.

### Success or failure meaning
- Success: archive is readable and path structure is known.
- Failure: corrupted archive or wrong file format.

### Risk
Low.

## Command
```bash
sudo tar -xzpf "$TMP/archive.tar.gz" \
  -C "$DEST" \
  --strip-components=2 \
  /backup/my-app-backup
```

### What it does
Extracts the backup payload directly into the appdata destination while discarding wrapper path components.

### Important flags or arguments
- `-x`: Extract.
- `-z`: Gzip-compressed archive.
- `-p`: Preserve permissions.
- `-f`: Archive file.
- `-C "$DEST"`: Extract into destination directory.
- `--strip-components=2`: Remove the first two path components.

### Why it was used
The archive root was `/backup/my-app-backup/...`, but the desired restore target was `/opt/docker-apps/...`.

### Expected result
App directories are restored directly into `/opt/docker-apps`.

### Success or failure meaning
- Success: payload lands at the desired depth.
- Failure: wrong archive path or wrong strip depth.

### Risk
High. A bad strip value can place files into the wrong location.

## Command
```bash
sudo rsync -a --remove-source-files /opt/docker-apps/backup/my-app-backup/ /opt/docker-apps/
```

### What it does
Moves restored contents out of an accidentally nested wrapper directory into the real appdata root.

### Important flags or arguments
- `--remove-source-files`: Delete source files after successful copy.

### Why it was used
An earlier restore left the payload nested under `/opt/docker-apps/backup/my-app-backup`.

### Expected result
Files move up into the correct root while the nested wrapper becomes empty.

### Success or failure meaning
- Success: restored tree ends up in the expected location.
- Failure: source and destination remain inconsistent.

### Risk
Moderate. Using remove-source semantics is risky if source and destination are wrong.
