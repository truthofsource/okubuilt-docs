---
title: "VM 100 Boot Failure, Docker Data Disk Recovery, and Cloud-Init Hardening"
track: "infrastructure"
category: "containers-apps"
type: "runbook"
logical_order: 50
date_rule: "Dates are removed from filenames, visible headings, indexes, generated metadata, and runbook body content."
---

# VM 100 Boot Failure, Docker Data Disk Recovery, and Cloud-Init Hardening

## Summary
This work session focused on recovering Proxmox VM 100 (`debian-docker`) after a boot failure caused by duplicate mount definitions and cloud-init drift, restoring Docker storage to the correct data disk, repairing filesystem corruption on the Docker disk, and hardening the VM’s cloud-init configuration so Docker only starts when the intended Docker data disk is mounted.

The session started as a boot and console recovery problem, expanded into mount troubleshooting, then ended with a stable Docker recovery and a hardened cloud-init design.

## Environment
- **Platform:** Proxmox VE
- **Node:** `mainframe`
- **VM:** `100` (`debian-docker`)
- **Helper VM:** cloned from template `9000`, used as a repair VM
- **Guest OS:** Debian cloud image-based VM
- **Storage:**
  - `scsi0: cephpool:vm-100-disk-0` — OS disk, 50G
  - `scsi1: cephpool:vm-100-disk-1` — Docker/data disk, 150G
  - `ide2: cephpool:vm-100-cloudinit` — cloud-init seed ISO
- **Docker data path:** `/var/lib/docker`
- **App paths:** `/opt/compose`, `/opt/docker-apps`
- **Remote mounts:**
  - `//192.168.16.21/Media` → `/srv/remotemount/NAS`
  - `//192.168.16.22/Public` → `/srv/remotemount/wontonsoup`
- **Container stack:** Docker Engine, Docker Compose, Dockge, Traefik, Gluetun-related containers, multiple app web GUIs
- **Relevant labels / IDs:**
  - Docker data disk label: `docker-data`
  - Docker data disk UUID: `6ce44029-6b4b-4fe4-a78e-bec4402a0444`
- **Cloud-init datasource:** NoCloud from `/dev/sr0`

## Problem
VM 100 became unbootable after old and new cloud-init mount logic overlapped, producing duplicate `/etc/fstab` entries and incorrect boot-time mount behavior. After boot recovery, Docker storage mounts became inconsistent, and `/var/lib/docker` and its bind mounts temporarily attached to the wrong backing filesystem. The Docker data disk then required offline filesystem repair.

## Symptoms
- Boot dropped into **emergency mode**
- systemd errors for duplicate mount units:
  - `Failed to create unit file ... Duplicate entry in /etc/fstab`
- Root account unavailable in emergency shell:
  - `Cannot open access to console, the root account is locked`
- initramfs reported:
  - `root=PARTUUID=... does not exist`
- Cloud-init repeatedly processed NoCloud seed data from `/dev/sr0`
- `/var/lib/docker` mount failed earlier in boot:
  - `Dependency failed for var-lib-docker.mount`
  - `Failed to start systemd-fsck@dev-disk-by-label-docker-data.service`
- Docker later showed as inactive until the data disk mount was corrected
- `fsck` initially refused to run because `/dev/sdb` was still mounted
- `/opt/compose` and `/opt/docker-apps` were observed on **`/dev/sda1`** instead of the Docker data disk
- `cd /opt/compose/dockge` failed with:
  - `No such device`
- `sysctl` was missing in the guest at one point:
  - `sysctl: command not found`

## Actions Taken
1. Reviewed the VM config on Proxmox and identified the VM disk layout.
2. Confirmed that VM 100 used:
   - `scsi0` as OS disk
   - `scsi1` as Docker/data disk
   - `ide2` as cloud-init ISO
3. Investigated boot failure messages and identified duplicate `/opt/docker-apps` and `/opt/compose` mount definitions in `/etc/fstab`.
4. Determined that an **older cloud-init YAML had likely been applied on top of a newer configuration**, causing duplicate mount lines and boot instability.
5. Created and used a **helper VM** from template `9000`.
6. Attached VM 100’s OS disk to the helper VM and mounted it for offline repair.
7. Edited VM 100’s `/etc/fstab` from the helper VM:
   - Commented duplicate `/opt/docker-apps` entries
   - Commented duplicate `/opt/compose` entries
   - Corrected malformed lines
   - Replaced stale PARTUUID root references with working UUID-based mount references
8. Detached the repaired OS disk from the helper VM and rebooted VM 100.
9. Re-applied and reviewed cloud-init behavior, including hostname and mount handling.
10. Observed that hostname drifted to `helper-vm`, confirming cloud-init and/or stale template state was being re-applied.
11. Updated the cloud-init design so it would manage mounts consistently and own the hostname configuration.
12. Logged into VM 100 successfully and performed post-recovery verification.
13. Inspected mount state and discovered:
    - `/var/lib/docker` was expected on the Docker disk
    - `/opt/compose` and `/opt/docker-apps` had temporarily latched onto root disk paths when the correct Docker mount was absent
14. Verified Docker mount failures and then corrected the Docker data path.
15. Stopped Docker and containerd to free `/var/lib/docker`.
16. Unmounted all child mountpoints and bind mounts under `/var/lib/docker`.
17. Fully unmounted `/dev/sdb`.
18. Ran an offline filesystem repair on the Docker data disk.
19. `fsck` repaired:
    - orphaned inode list corruption
    - block bitmap mismatches
    - inode bitmap mismatches
    - free block and free inode count inconsistencies
20. Remounted `/var/lib/docker` from the correct Docker disk and remounted bind targets for `/opt/compose` and `/opt/docker-apps`.
21. Restarted containerd and Docker successfully.
22. Verified Docker came back up with the correct root:
    - `/var/lib/docker`
    - `overlay2`
    - `systemd` cgroup driver
23. Observed that 23 containers were active after recovery.
24. Cleaned up the mistaken `dockge` directory that had been created on the wrong backing filesystem during the mount confusion.
25. Hardened the cloud-init YAML to pin Docker storage to the intended disk and to verify the mount before Docker starts.
26. Saved the hardened cloud-init design for future reuse.

## Key Findings
- The original boot failure was caused by **duplicate mount definitions** in `/etc/fstab`, likely from applying an older cloud-init mount configuration over a newer one.
- The PARTUUID boot issue was separate from the Docker mount issue, but it contributed to boot instability.
- Cloud-init was repeatedly processing NoCloud seed data from `/dev/sr0`, which confirmed the VM was still tied to its Proxmox cloud-init ISO.
- The Docker data disk was a single ext4 filesystem directly on **`/dev/sdb`**, not on a partition like `/dev/sdb1`.
- `/var/lib/docker` must be mounted from the dedicated Docker disk **before** bind mounts for `/opt/compose` and `/opt/docker-apps` are triggered.
- Because the bind targets were configured as automounts, they were able to bind against the wrong source path on `/dev/sda1` when `/var/lib/docker` on `/dev/sdb` was not yet mounted.
- Docker itself was healthy once the disk mount was corrected; the real blocker was storage mount state.
- The Docker data disk had real ext4 corruption, not just a mount ordering problem. Offline `fsck` was necessary and successfully repaired it.
- The working data disk identity was:
  - **Label:** `docker-data`
  - **UUID:** `6ce44029-6b4b-4fe4-a78e-bec4402a0444`
- Docker was ultimately confirmed healthy with:
  - `Docker Root Dir: /var/lib/docker`
  - `Driver: overlay2`
  - `Cgroup Driver: systemd`

## Resolution
The recovery was completed in stages:

1. **Boot recovery**
   - Duplicate mount lines in `/etc/fstab` were commented out.
   - The root disk was repaired offline using a helper VM.
   - Boot configuration was normalized enough to get the guest back online.

2. **Docker mount recovery**
   - `/var/lib/docker` was remounted from the correct disk (`/dev/sdb`, label `docker-data`).
   - `/opt/compose` and `/opt/docker-apps` were rebound to the correct directories on that disk.
   - A mistaken Dockge directory created on the wrong backing filesystem was removed.

3. **Filesystem repair**
   - `/dev/sdb` was fully unmounted.
   - Offline `fsck -f -y /dev/sdb` repaired ext4 corruption and metadata inconsistencies.

4. **Cloud-init hardening**
   - Cloud-init was updated so Docker storage mounts by the **exact UUID** of the intended data disk.
   - A Docker mount guard service was added to verify `/var/lib/docker` is mounted from that exact device before Docker starts.
   - Docker service override logic was updated to wait on the required mounts and the verification service.

## Validation
Success was confirmed by all of the following:
- VM 100 booted and became interactive again.
- `/var/lib/docker` mounted from the correct disk:
  - `/dev/sdb`
- Bind mounts resolved correctly:
  - `/opt/compose` → `/dev/sdb[/compose]`
  - `/opt/docker-apps` → `/dev/sdb[/appdata]`
- Docker service became active and running.
- `docker info` showed:
  - `Root: /var/lib/docker`
  - `Driver: overlay2`
  - `Cgroup: systemd`
- `docker system df` showed images, containers, and volumes were present.
- Docker reported **23 active containers** after recovery.
- Cloud-init analysis showed user-data was being read from the NoCloud datasource on the Proxmox cloud-init ISO.
- The hardened YAML was finalized and saved for reuse.

## Follow-Up Tasks
- Reboot VM 100 once more and verify that:
  - `/var/lib/docker` mounts automatically from the correct UUID
  - `/opt/compose` and `/opt/docker-apps` resolve to the Docker data disk after boot
  - Docker starts without manual intervention
- Confirm all app web GUIs are reachable after a clean reboot.
- Verify Dockge’s compose directory and UI state after the mount correction.
- Consider removing `discard` from the Docker data disk mount and relying on `fstrim.timer` if desired for SSD/virt trim strategy consistency.
- Confirm all important containers use `restart: unless-stopped` or equivalent restart policies.
- Keep an eye on ext4 errors or repeated fsck findings in case the Docker data disk or host experienced an unclean shutdown or storage fault.
- Optionally install or configure additional disk health monitoring.
- Review whether bind mounts for `/opt/compose` and `/opt/docker-apps` should remain automounts or become plain binds to reduce mount-order surprises.

## Lessons Learned
- Applying old cloud-init mount logic on top of newer config can silently create duplicate fstab entries and break boot.
- A helper VM is a clean way to repair a broken guest offline when console access is limited.
- systemd automount bind targets can bind against the wrong underlying filesystem if the intended parent mount is missing when the automount first fires.
- For important storage like Docker data, mounting by **UUID** is safer than relying on label or device-name detection alone.
- Docker startup should be explicitly guarded so it cannot come up on the wrong storage path.
- Filesystem repair on active Docker storage must be done offline after fully stopping Docker, containerd, and all subordinate mounts.
- Clean separation between OS disk, Docker disk, and cloud-init ownership makes recovery much easier.

---

# Command Reference

## Command
```bash
cat /etc/pve/qemu-server/100.conf
```

### Purpose
Review the exact Proxmox VM configuration for VM 100.

### What it does
Shows VM hardware, disks, cloud-init, boot settings, CPU, memory, and device mapping.

### Why it was used
To confirm which disk was the OS disk, which was the Docker/data disk, and how cloud-init was attached.

### Expected result
A config showing `scsi0`, `scsi1`, and `ide2` roles.

### What success or failure would indicate
- Success: VM layout is visible and can be reasoned about.
- Failure: wrong VM ID, missing config, or Proxmox metadata issue.

### Homelab relevance
For Proxmox, this is the authoritative per-VM config and is critical for storage recovery and disk attachment work.

---

## Command
```bash
qm clone 9000 101 --name helper-repair
```

### Purpose
Create a helper VM from template `9000`.

### What it does
Clones a template into a new working VM that can be used to mount and repair another VM’s disks offline.

### Why it was used
To create a rescue/helper VM for offline disk work.

### Expected result
A new VM ID 101 named `helper-repair`.

### What success or failure would indicate
- Success: helper VM is available for offline disk work.
- Failure: clone problem, storage issue, or template not available.

### Homelab relevance
A helper VM is a common Proxmox recovery technique for repairing broken guest filesystems and configs.

---

## Command
```bash
qm set 101 --scsi2 cephpool:vm-100-disk-0
```

### Purpose
Attach VM 100’s OS disk to the helper VM.

### What it does
Adds the existing Ceph-backed disk as an extra SCSI disk to the helper VM.

### Why it was used
To mount and edit VM 100’s OS disk offline.

### Expected result
The helper VM sees VM 100’s disk as a new block device.

### What success or failure would indicate
- Success: disk becomes accessible for repair work.
- Failure: disk path mismatch, storage issue, or VM config issue.

### Risk
Attaching a disk to a helper VM while the original VM is still running is risky and can corrupt data.

### Safer alternative
Always shut down the original VM before re-attaching its disk elsewhere.

### Homelab relevance
In Proxmox with Ceph-backed volumes, this is a standard disk rescue workflow.

---

## Command
```bash
lsblk -fp
```

### Purpose
Inspect disks, filesystems, labels, UUIDs, and mountpoints.

### What it does
Lists block devices in full path form with filesystem metadata.

### Why it was used
To identify which guest disks were mounted where and whether Docker data was on the correct disk.

### Expected result
Block devices like `/dev/sda`, `/dev/sdb`, filesystem labels, and mountpoints.

### What success or failure would indicate
- Success: storage state is visible.
- Failure: device enumeration issue or missing tools.

### Homelab relevance
Useful across Linux, Proxmox guests, Docker hosts, and recovery sessions.

---

## Command
```bash
sudo mount /dev/sdb1 /mnt/repair
```

### Purpose
Mount VM 100’s root filesystem from the helper VM.

### What it does
Mounts the attached disk’s filesystem to a temporary location for offline editing.

### Why it was used
To edit `/etc/fstab` and other files on VM 100 while it was powered off.

### Expected result
Mounted guest filesystem visible under `/mnt/repair`.

### What success or failure would indicate
- Success: disk is accessible and repair can proceed.
- Failure: wrong partition, wrong filesystem type, or corruption.

### Risk
Mounting read-write changes the target guest filesystem. That was necessary here.

---

## Command
```bash
sudo sed -i '/[[:space:]]\/opt\/docker-apps[[:space:]]/ s/^/# /' /mnt/repair/etc/fstab
```

### Purpose
Comment duplicate `/opt/docker-apps` mount lines in `fstab`.

### What it does
Finds matching lines and comments them out.

### Why it was used
To stop systemd from generating duplicate mount units and booting into emergency mode.

### Expected result
Duplicate lines become commented and no longer apply.

### What success or failure would indicate
- Success: one source of truth remains for the mount.
- Failure: wrong pattern, wrong file, or no matching line.

### Risk
Editing `fstab` incorrectly can make the system unbootable.

---

## Command
```bash
sudo sed -i '/[[:space:]]\/opt\/compose[[:space:]]/ s/^/# /' /mnt/repair/etc/fstab
```

### Purpose
Comment duplicate `/opt/compose` mount lines in `fstab`.

### What it does
Disables all matching active lines for that mountpoint.

### Why it was used
To remove duplicate mount definitions that caused boot failure.

### Expected result
Only the intended mount mechanism remains active.

### What success or failure would indicate
- Success: duplicate systemd mount generation stops.
- Failure: duplicate lines remain or wrong lines are changed.

---

## Command
```bash
sudo mount -L docker-data /var/lib/docker
```

### Purpose
Mount the Docker data disk by filesystem label.

### What it does
Mounts whichever ext4 filesystem has label `docker-data` at `/var/lib/docker`.

### Why it was used
To reattach Docker storage to the intended dedicated disk after mount drift.

### Expected result
`/var/lib/docker` becomes backed by `/dev/sdb`.

### What success or failure would indicate
- Success: Docker root points to the correct disk.
- Failure: wrong label, missing disk, or filesystem issue.

### Risk
If the wrong filesystem has that label, Docker could start on the wrong disk.

### Safer alternative
Mount by UUID instead of label.

---

## Command
```bash
findmnt /var/lib/docker
```

### Purpose
Confirm the current backing source for `/var/lib/docker`.

### What it does
Shows the exact device or filesystem mounted at that path.

### Why it was used
To verify whether Docker storage was on `/dev/sdb` or mistakenly on the root disk.

### Expected result
`SOURCE=/dev/sdb` once corrected.

### What success or failure would indicate
- Success: mount source is clearly identified.
- Failure: mount missing, path not mounted, or wrong source.

---

## Command
```bash
findmnt /opt/compose
```

### Purpose
Confirm the source backing `/opt/compose`.

### What it does
Shows the bind or automount backing that path.

### Why it was used
To detect when `/opt/compose` had latched onto the wrong source path on `/dev/sda1`.

### Expected result
Correct source should ultimately be `/dev/sdb[/compose]`.

### What success or failure would indicate
- Success: bind target is correctly attached to Docker data disk.
- Failure: source drift or missing mount.

---

## Command
```bash
findmnt /opt/docker-apps
```

### Purpose
Confirm the source backing `/opt/docker-apps`.

### What it does
Shows the active mount source for that bind target.

### Why it was used
To ensure Docker app data was being pulled from the intended storage.

### Expected result
Correct source should be `/dev/sdb[/appdata]`.

### What success or failure would indicate
- Success: appdata bind is correct.
- Failure: appdata bind is using the wrong filesystem.

---

## Command
```bash
sudo systemctl stop docker docker.socket containerd
```

### Purpose
Stop Docker and container runtime services before storage work.

### What it does
Stops Docker, the Docker socket activation unit, and containerd.

### Why it was used
To release mounts and overlay usage so `/var/lib/docker` could be unmounted and repaired safely.

### Expected result
Runtime stack stops cleanly.

### What success or failure would indicate
- Success: data disk can be unmounted.
- Failure: active containers or systemd restart behavior may still hold the mount.

### Risk
Stopping these services interrupts all running containers.

### Homelab relevance
On a Docker host, this is the correct first step before filesystem maintenance on Docker storage.

---

## Command
```bash
sudo pkill -9 -f 'containerd-shim'
```

### Purpose
Force-stop lingering containerd shim processes.

### What it does
Kills processes matching the containerd shim process name.

### Why it was used
To free mount references that prevented unmounting `/var/lib/docker`.

### Expected result
Shim processes exit immediately.

### What success or failure would indicate
- Success: mountpoints can be released.
- Failure: other processes still hold the filesystem.

### Risk
Force-killing runtime processes is disruptive and can leave temporary inconsistencies. It was justified here because the disk required offline repair.

---

## Command
```bash
mount | awk '$3 ~ /^\/var\/lib\/docker(\/|$)/ {print $3}' | sort -r | xargs -r -n1 sudo umount
```

### Purpose
Unmount child mountpoints under `/var/lib/docker` from deepest to shallowest.

### What it does
Finds all mounts rooted under `/var/lib/docker`, sorts them in reverse path order, and unmounts them.

### Why it was used
Unmounting parent mounts first fails if child mounts still exist.

### Expected result
All subordinate Docker mountpoints disappear.

### What success or failure would indicate
- Success: the main Docker mount can be unmounted.
- Failure: some process still holds a mountpoint open.

### Risk
Unmounting live Docker storage while containers are active would be dangerous. Runtime processes were stopped first.

---

## Command
```bash
mount | awk '$1=="/dev/sdb"{print $3}' | sort -r | xargs -r -n1 sudo umount
```

### Purpose
Unmount every mountpoint backed by `/dev/sdb`.

### What it does
Finds all current mount targets using `/dev/sdb` and unmounts them.

### Why it was used
To fully detach the Docker data disk before running `fsck`.

### Expected result
`findmnt /dev/sdb` returns nothing afterward.

### What success or failure would indicate
- Success: the disk is offline and safe to check.
- Failure: one or more mountpoints still hold the device.

---

## Command
```bash
sudo fsck -f -y /dev/sdb
```

### Purpose
Run an offline ext filesystem repair on the Docker data disk.

### What it does
Forces a full filesystem check and automatically answers yes to repair prompts.

### Why it was used
The disk showed corruption symptoms and had failed boot-time fsck.

### Expected result
Filesystem metadata is repaired and the tool reports any fixes performed.

### What success or failure would indicate
- Success: corruption repaired and filesystem ready for remount.
- Failure: serious storage damage or inability to complete repairs.

### Risk
`fsck -y` makes automatic modifications. It should only be run on an unmounted filesystem or in a properly offline recovery scenario.

### Homelab relevance
Critical for ext4-backed Docker data disks after unclean shutdowns or mount inconsistencies.

---

## Command
```bash
sudo mount -a
```

### Purpose
Mount all filesystems from `/etc/fstab`.

### What it does
Processes the current `fstab` and mounts anything not yet mounted.

### Why it was used
To restore all standard mounts after repair and config changes.

### Expected result
Required local and automount-backed filesystems come online without errors.

### What success or failure would indicate
- Success: `fstab` is valid and mount dependencies resolve.
- Failure: syntax errors, missing devices, or incorrect mount options.

---

## Command
```bash
sudo systemctl start containerd docker
```

### Purpose
Restart the container runtime stack after storage recovery.

### What it does
Starts containerd and Docker services.

### Why it was used
To bring application containers back online after the Docker disk was repaired and remounted.

### Expected result
Docker daemon becomes active and loads containers from the correct storage root.

### What success or failure would indicate
- Success: Docker storage path is healthy and accessible.
- Failure: mount path still wrong, daemon config issue, or container runtime problem.

---

## Command
```bash
docker info --format 'Root: {{.DockerRootDir}}  Driver: {{.Driver}}  Cgroup: {{.CgroupDriver}}'
```

### Purpose
Validate Docker’s core runtime state.

### What it does
Prints Docker’s root directory, storage driver, and cgroup driver.

### Why it was used
To confirm Docker was using the correct storage root after recovery.

### Expected result
`Root: /var/lib/docker  Driver: overlay2  Cgroup: systemd`

### What success or failure would indicate
- Success: Docker is healthy and aligned with the intended configuration.
- Failure: wrong root path, wrong driver, or broken daemon state.

### Homelab relevance
Useful for verifying Docker host correctness after storage or daemon changes.

---

## Command
```bash
docker system df
```

### Purpose
Inspect Docker object usage.

### What it does
Shows how much space images, containers, volumes, and build cache consume.

### Why it was used
To confirm Docker had recovered its expected state and still saw its stored objects.

### Expected result
Nonzero image/container counts and sizes.

### What success or failure would indicate
- Success: Docker metadata and storage survived recovery.
- Failure: missing images, missing containers, or wrong Docker root.

---

## Command
```bash
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
```

### Purpose
List currently running containers and published ports.

### What it does
Shows names, states, and exposed ports of active containers.

### Why it was used
To confirm that application containers came back after Docker recovery.

### Expected result
A list of running containers with statuses such as `Up`.

### What success or failure would indicate
- Success: app stack is active again.
- Failure: Docker is running but containers did not restart.

---

## Command
```bash
sudo mkdir -p /mnt/rootdisk
sudo mount /dev/sda1 /mnt/rootdisk
sudo rm -rf /mnt/rootdisk/var/lib/docker/compose/dockge
sudo umount /mnt/rootdisk
```

### Purpose
Remove the accidental Dockge directory created on the wrong backing filesystem.

### What it does
Temporarily mounts the root disk, deletes the mistaken directory path, and unmounts it.

### Why it was used
A Dockge folder had been created while `/opt/compose` was bound to the wrong source on the root disk.

### Expected result
The stray directory is removed from the wrong filesystem.

### What success or failure would indicate
- Success: cleanup completed without touching the real Docker disk.
- Failure: wrong path, wrong disk, or mount issue.

### Risk
Deleting the wrong path here could remove wanted data. Path verification is important.

---

## Command
```bash
qm set 101 --delete scsi2
```

### Purpose
Detach VM 100’s disk from the helper VM.

### What it does
Removes the extra attached disk from helper VM 101’s config.

### Why it was used
To return the disk to normal ownership after offline repair.

### Expected result
The helper VM no longer sees VM 100’s disk.

### What success or failure would indicate
- Success: disk safely detached.
- Failure: wrong bus slot or config mismatch.

### Important note
This detaches the disk from the helper VM config; it does **not** delete the disk from storage.

### Homelab relevance
Important distinction in Proxmox: config detach is not storage deletion.

---

## Command
```bash
cloud-init analyze show
```

### Purpose
Review cloud-init stage execution history and timing.

### What it does
Shows what cloud-init stages ran, how long they took, and whether modules previously ran or ran successfully.

### Why it was used
To confirm that NoCloud user-data was being read from `/dev/sr0` and that cloud-init had applied configuration.

### Expected result
Boot records showing datasource detection and module execution.

### What success or failure would indicate
- Success: cloud-init is active and consuming the expected data source.
- Failure: cloud-init disabled, broken datasource, or missing tools.

### Homelab relevance
Very useful when Proxmox cloud-init snippets are not behaving as expected.

---

## Command
```bash
qm cloudinit update 100
```

### Purpose
Regenerate the Proxmox cloud-init seed ISO for VM 100.

### What it does
Updates the cloud-init ISO contents attached to the VM based on current Proxmox config and custom snippets.

### Why it was used or implied
Necessary when cloud-init YAML changes and the updated config must be fed into the VM.

### Expected result
The VM sees refreshed NoCloud metadata and user-data on next boot.

### What success or failure would indicate
- Success: cloud-init changes will apply on next guest initialization.
- Failure: snippet path, storage, or config issue.

### Homelab relevance
Core to Proxmox cloud-init workflows.

---

## Command
```bash
qm cloudinit dump 100 user
```

### Purpose
Inspect the effective user-data Proxmox is providing to the VM.

### What it does
Prints the rendered cloud-init user-data for the VM.

### Why it was used or implied
To verify that the intended hardened YAML was actually what Proxmox would deliver.

### Expected result
Rendered YAML reflecting the current cloud-init design.

### What success or failure would indicate
- Success: user-data path and rendering are correct.
- Failure: old snippet still referenced or config not updated.

---

## Command
```bash
sudo cloud-init clean --logs --seed
```

### Purpose
Force cloud-init to treat the next boot as fresh initialization.

### What it does
Removes cached state, logs, and seed tracking so cloud-init reruns setup.

### Why it was used or implied
Needed when reapplying updated cloud-init config to an already-provisioned VM.

### Expected result
Cloud-init reruns relevant stages on next boot.

### What success or failure would indicate
- Success: hostname, mounts, and config changes can re-apply.
- Failure: cloud-init version limitation or package issue.

### Risk
Re-running cloud-init can reapply config in disruptive ways if the YAML is not carefully controlled.

---

## Command
```bash
sudo systemctl enable docker
```

### Purpose
Ensure Docker starts on boot.

### What it does
Enables the Docker service unit in systemd.

### Why it was used
To make Docker and its containers recover automatically after reboot.

### Expected result
Docker is enabled for future boots.

### What success or failure would indicate
- Success: service links are created.
- Failure: unit not found or systemd issue.

---

## Command
```bash
sudo systemctl restart docker
```

### Purpose
Restart Docker after mount or config changes.

### What it does
Stops and starts the Docker service.

### Why it was used
Needed after storage recovery, daemon config changes, or service override updates.

### Expected result
Docker restarts cleanly and reconnects to the correct storage.

### What success or failure would indicate
- Success: Docker state stabilizes on the corrected mount.
- Failure: mount issue persists or daemon config is invalid.
