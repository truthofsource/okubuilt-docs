---
title: "VM 100 Cloud-Init, fstab Recovery, and CephFS Snippets Migration"
track: "infrastructure"
category: "automation"
type: "runbook"
logical_order: 10
date_rule: "Dates are removed from filenames, visible headings, indexes, generated metadata, and runbook body content."
---

# VM 100 Cloud-Init, fstab Recovery, and CephFS Snippets Migration

## Summary
This work session focused on restoring reliable cloud-init behavior for Proxmox VM 100 (`debian-docker`), recovering from a boot failure caused by duplicate `/etc/fstab` entries, and converting the `snips` storage into a proper shared CephFS-backed snippets store so VM migration between cluster nodes would not break cloud-init custom snippet references.

The session started with re-establishing the correct `qm set ... -cicustom` command for VM 100, moved into troubleshooting cloud-init ISO generation and emergency-mode boot failures, and ended with a successful CephFS deployment and validation of VM migration from `mainframe` to `pve1`.

## Environment
- **Platform:** Proxmox VE 8.4.14
- **Kernel:** `6.8.12-16-pve`
- **Ceph version:** 18.2.7 Reef
- **Cluster nodes mentioned:** `mainframe`, `pve1`, `pve2`, `pve3`, `pve4`
- **VM:** `100` (`debian-docker`)
- **Cloud-init snippet files:**
  - `docker-userdata.yml`
  - `docker-net.yml`
- **Original snippet path used locally:**
  - `/var/lib/vz/snippets/`
- **Shared snippet target path after fix:**
  - `/mnt/pve/snips/snippets/`
- **Ceph cluster status during session:**
  - 5 monitors total
  - `mainframe` MON out of quorum
  - quorum maintained by `pve1,pve3,pve2,pve4`
  - 5 OSDs up/in
- **CephFS created:** `cephfs`
- **MDS status after setup:**
  - `pve1` active
  - `pve3` standby
- **Storage involved:**
  - `snips` storage reworked to use CephFS
  - cloud-init drive remained separate from snippet storage
- **Guest OS issue observed in VM 100:**
  - emergency mode due to duplicate `/etc/fstab` entries
  - Docker disk mount failure for `/var/lib/docker`

## Problem
VM 100 needed to use custom cloud-init YAML files consistently across nodes, but several related issues interfered:

1. The correct `cicustom` configuration had to be re-established for VM 100.
2. Cloud-init update behavior was unstable during troubleshooting.
3. VM 100 booted into emergency mode due to duplicate mount entries in `/etc/fstab`.
4. After migration from `mainframe` to `pve1`, Proxmox could not find `snips:snippets/docker-net.yml`.
5. The existing `snips` storage was not functioning as a properly shared CephFS snippets store across the cluster.

## Symptoms
Observed symptoms and errors included:

- Cloud-init command context had to be re-confirmed for VM 100.
- `qm cloudinit update 100` initially followed a `Segmentation fault` message, then `generating cloud-init ISO`.
- VM 100 entered emergency mode during boot.
- systemd reported duplicate mount definitions:
  - duplicate entry in `/etc/fstab`
  - failures for `/opt/docker-apps`
  - failures for `/opt/compose`
- Emergency mode message indicated:
  - root account locked
  - no interactive repair via normal sulogin path
- Additional boot issue showed Docker disk-related failure:
  - `Failed to start systemd-fsck...`
  - dependency failed for `/var/lib/docker`
  - dependency failed for Docker service
- Migration failure after moving VM 100 to `pve1`:
  - `TASK ERROR: volume 'snips:snippets/docker-net.yml' does not exist`
- Name resolution failure when attempting SCP by hostname:
  - `ssh: Could not resolve hostname pve1: Name or service not known`
- Running VM commands on the old node after migration failed:
  - `Configuration file 'nodes/mainframe/qemu-server/100.conf' does not exist`
- CephFS orchestration attempt failed:
  - `Error ENOENT: No orchestrator configured (try ceph orch set backend)`
- Proxmox storage parser warnings appeared after manual config editing:
  - `file /etc/pve/storage.cfg line 1 - ignore config line: ceph mds stat`
  - `unable to parse value of 'shared': unexpected property 'shared'`

## Actions Taken
1. Re-established the intended cloud-init custom snippet command for VM 100 using the `snips` storage.
2. Confirmed VM ID `100` and noted both `local` and `snips` variants during troubleshooting, then standardized back to `snips`.
3. Stopped VM 100 before re-running cloud-init-related operations.
4. Investigated emergency mode output from the guest and identified duplicate `/etc/fstab` entries affecting:
   - `/opt/docker-apps`
   - `/opt/compose`
5. Identified that boot issues were tied to duplicate mount definitions rather than cloud-init alone.
6. Reviewed the guest-side Docker disk boot failure showing `/var/lib/docker` mount/fsck dependency problems.
7. Reasserted that snippet editing should be performed against the intended storage location and later standardized on `snips`.
8. Migrated VM 100 from `mainframe` to `pve1`.
9. Troubleshot migration failure caused by missing snippet visibility on the destination node.
10. Confirmed hostname resolution for `pve1` was not working from `mainframe`, so IP-based commands were used instead of hostnames.
11. Verified Ceph cluster state:
    ```bash
    ceph -s
    ```
    Purpose: check cluster health, quorum, and readiness for CephFS work.
12. Verified platform versions:
    ```bash
    pveversion
    ceph --version
    ```
    Purpose: confirm Proxmox and Ceph versions during storage troubleshooting.
13. Created a Ceph filesystem:
    ```bash
    ceph fs volume create cephfs
    ```
    Purpose: create a CephFS filesystem for shared file-based storage.
14. Confirmed CephFS existed:
    ```bash
    ceph fs ls
    ceph df
    ```
15. Archived recent Ceph crash records:
    ```bash
    ceph crash archive-all
    ```
16. Attempted to create MDS daemons with `ceph orch`, which failed because no orchestrator backend was configured.
17. Used Proxmox-native Ceph MDS deployment approach instead of cephadm/orchestrator.
18. Verified MDS service state until CephFS reported:
    - `pve1` active MDS
    - `pve3` standby MDS
19. Edited `/etc/pve/storage.cfg` to convert the existing `snips` storage into a CephFS storage definition.
20. Corrected configuration mistakes introduced during manual editing:
    - removed accidental pasted command text
    - removed invalid `shared` property for CephFS storage
21. Verified the CephFS mount became active at:
    - `/mnt/pve/snips`
22. Created the shared snippets directory:
    ```bash
    mkdir -p /mnt/pve/snips/snippets
    ```
23. Copied the two cloud-init YAML files from local snippets storage into the shared CephFS location:
    ```bash
    cp /var/lib/vz/snippets/docker-userdata.yml /mnt/pve/snips/snippets/
    cp /var/lib/vz/snippets/docker-net.yml      /mnt/pve/snips/snippets/
    ```
24. Confirmed Proxmox could see the snippets through the `snips` storage:
    ```bash
    pvesm list snips | grep snippets
    ```
25. Re-applied the `cicustom` config for VM 100 using shared `snips` storage.
26. Rebuilt cloud-init data for VM 100 on the appropriate node.
27. Validated that migration now worked successfully.

## Key Findings
- VM 100’s intended cloud-init custom snippet configuration was:
  ```bash
  qm set 100 -cicustom "user=snips:snippets/docker-userdata.yml,network=snips:snippets/docker-net.yml"
  ```
- Using `snips` instead of `local` was the correct long-term configuration for this environment.
- A shared snippet backend is required for reliable VM migration when `cicustom` references files by storage ID.
- The previous `snips` setup was not functioning as a properly shared snippets store across nodes.
- CephFS was the correct backend for shared snippet storage; Ceph RBD is not appropriate for file-based snippet content.
- CephFS was successfully created even though MDS daemons were not auto-created by the filesystem creation command.
- The cluster was not using cephadm orchestration, so `ceph orch apply mds ...` was not applicable.
- Proxmox accepted the CephFS storage once `storage.cfg` was corrected.
- The parser warnings were caused by accidental text pasted into `/etc/pve/storage.cfg` and by use of an unsupported `shared` property in a CephFS storage block.
- The cloud-init snippet files became cluster-visible only after being copied into:
  - `/mnt/pve/snips/snippets/`
- The guest emergency-mode issue was separate from the shared-snippets problem and was caused by duplicate mount definitions in `/etc/fstab`.
- The guest also showed a separate Docker disk mount issue involving `/var/lib/docker`, indicating that boot reliability depended on both clean mount definitions and correct Docker disk identification.

## Resolution
The final working state was achieved by:

1. Creating a CephFS filesystem named `cephfs`.
2. Bringing CephFS online with:
   - `pve1` as active MDS
   - `pve3` as standby MDS
3. Reconfiguring the existing `snips` Proxmox storage as a CephFS storage using:
   - `fs-name cephfs`
   - path `/mnt/pve/snips`
   - content `snippets`
   - username `admin`
4. Removing invalid or accidental lines from `/etc/pve/storage.cfg`.
5. Copying `docker-userdata.yml` and `docker-net.yml` into the shared CephFS snippet directory.
6. Reapplying VM 100’s `cicustom` configuration to use the shared `snips` storage.
7. Rebuilding cloud-init data for VM 100 on the node where the VM actually resided.
8. Confirming that migration now worked successfully.

Guest boot issues related to duplicate `/etc/fstab` entries were identified, but the final status of that guest-side cleanup was not fully documented in this portion of the chat. The migration and shared-snippet problem, however, was resolved.

## Validation
Success was confirmed by:

- `ceph fs ls` showing `cephfs`
- `ceph mds stat` showing:
  - active MDS on `pve1`
  - standby MDS on `pve3`
- `pvesm status | grep snips` showing `snips` active as `cephfs`
- `mount | grep /mnt/pve/snips` showing the CephFS mount active
- `pvesm list snips | grep snippets` showing:
  - `snips:snippets/docker-net.yml`
  - `snips:snippets/docker-userdata.yml`
- Final user confirmation:
  - migration was working

## Follow-Up Tasks
- Clean up VM 100 guest `/etc/fstab` so duplicate bind-mount definitions for `/opt/docker-apps` and `/opt/compose` are removed permanently.
- Verify the `/var/lib/docker` filesystem entry in the guest uses the correct stable identifier, ideally UUID rather than label if label handling is inconsistent.
- Check whether all Proxmox nodes mount `/mnt/pve/snips` cleanly and consistently.
- Consider expanding CephFS `snips` storage content types to include:
  - `iso`
  - `vztmpl`
  - `backup`
  if that matches the intended storage role.
- Repair the out-of-quorum MON on `mainframe` to restore full Ceph monitor redundancy.
- Consider standardizing `/etc/hosts` entries or DNS resolution for cluster node names to avoid SCP/SSH hostname failures.
- Validate cloud-init behavior after future YAML edits by rebuilding:
  ```bash
  qm cloudinit update 100
  ```
- Review whether additional VMs should be moved to shared snippet storage for consistent migration behavior.

## Lessons Learned
- `cicustom` files must live on storage visible to the node performing the operation and to any migration target checks.
- CephFS is appropriate for shared file-based Proxmox storage such as snippets; Ceph RBD is for block devices such as VM disks.
- `ceph fs volume create` creates the filesystem but does not necessarily create MDS daemons automatically in a Proxmox-managed environment.
- In a Proxmox Ceph deployment without cephadm orchestration, use Proxmox-native Ceph management workflows for MDS services.
- Manual editing of `/etc/pve/storage.cfg` is effective but easy to corrupt with pasted shell text; always verify after editing.
- Emergency mode from duplicate `/etc/fstab` entries can be mistaken for a cloud-init issue if changes happen in the same maintenance window.
- When a VM has been migrated, run `qm` commands from the node currently holding the VM config or target the correct node over SSH.
- Shared snippet storage removes a common migration failure point for cloud-init-enabled VMs.

# Command Reference

## Command
```bash
qm set 100 -cicustom "user=snips:snippets/docker-userdata.yml,network=snips:snippets/docker-net.yml"
```

**What it does:** Sets custom cloud-init user-data and network-data files for VM 100.  
**Why it was used:** To make VM 100 consume the intended YAML config files.  
**Expected result:** VM 100 config gains a `cicustom` entry pointing at the two files.  
**Success indicates:** Proxmox can resolve the storage ID and file paths.  
**Failure indicates:** Storage definition, file path, or shared-storage visibility is broken.  
**Risk:** Low. Mispointing files can cause wrong guest initialization behavior.

---

## Command
```bash
qm cloudinit update 100
```

**What it does:** Regenerates the cloud-init ISO/config drive content for VM 100.  
**Why it was used:** Required after changing cloud-init snippet references or contents.  
**Expected result:** Proxmox rebuilds the VM’s cloud-init data successfully.  
**Success indicates:** The referenced snippet files are readable and cloud-init metadata generation is working.  
**Failure indicates:** Missing files, storage visibility problems, or cloud-init generation issues.  
**Risk:** Low. Safe routine operation.

---

## Command
```bash
qm set 100 -ide2 local:cloudinit
```

**What it does:** Adds or reassigns a cloud-init drive to VM 100 on `local` storage.  
**Why it was used:** To ensure the VM had a cloud-init drive attached.  
**Expected result:** VM config includes an `ide2` cloud-init device.  
**Success indicates:** The VM can attach a cloud-init drive on that storage.  
**Failure indicates:** Storage or VM configuration issue.  
**Risk:** Low.

---

## Command
```bash
qm config 100 | grep -E 'cicustom|ide2'
```

**What it does:** Displays the relevant cloud-init-related settings from the VM config.  
**Why it was used:** Quick validation that `cicustom` and cloud-init drive settings were in place.  
**Expected result:** Output shows the `cicustom` entry and `ide2` cloud-init drive.  
**Success indicates:** Config changes were applied.  
**Failure indicates:** The VM was not updated or is on another node.

---

## Command
```bash
qm cloudinit dump 100 user
```

**What it does:** Dumps the resolved user-data for VM 100.  
**Why it was used:** To confirm Proxmox could read and render the custom user-data YAML.  
**Expected result:** The cloud-init user-data content is printed.  
**Success indicates:** Snippet file is accessible and valid enough to be processed.  
**Failure indicates:** Missing snippet, bad storage reference, or rendering problem.

---

## Command
```bash
qm cloudinit dump 100 network
```

**What it does:** Dumps the resolved network cloud-init config for VM 100.  
**Why it was used:** To confirm Proxmox could read and render the custom network YAML.  
**Expected result:** The network config content is printed.  
**Success indicates:** Network snippet is accessible.  
**Failure indicates:** Missing or invalid network-data reference.

---

## Command
```bash
ls -l /var/lib/vz/snippets/docker-userdata.yml /var/lib/vz/snippets/docker-net.yml
```

**What it does:** Verifies the local snippet files exist and are readable.  
**Why it was used:** To confirm the source files existed before moving or reusing them.  
**Expected result:** File metadata appears for both YAML files.  
**Failure indicates:** Missing files or wrong path.

---

## Command
```bash
pvesm path local:snippets/docker-userdata.yml
```

**Likely command used**

**What it does:** Resolves the real filesystem path for a Proxmox storage object.  
**Why it was useful:** Helps confirm where a storage-backed snippet physically lives.  
**Expected result:** A path under the relevant storage mount.  
**Failure indicates:** Storage ID or content path is wrong.

---

## Command
```bash
pvesm path local:snippets/docker-net.yml
```

**Likely command used**

**What it does:** Resolves the real filesystem path for the network snippet.  
**Why it was useful:** Confirms where Proxmox expects the file.  
**Expected result:** Valid path output.

---

## Command
```bash
cp /var/lib/vz/snippets/docker-userdata.yml /var/lib/vz/snippets/docker-userdata.yml.bak
cp /var/lib/vz/snippets/docker-net.yml /var/lib/vz/snippets/docker-net.yml.bak
```

**What it does:** Makes quick local backups of the snippet files before editing.  
**Why it was used:** Protects against accidental YAML corruption.  
**Expected result:** `.bak` files created beside originals.  
**Risk:** Low. Good safety step.

---

## Command
```bash
nano /var/lib/vz/snippets/docker-userdata.yml
```

**What it does:** Opens the user-data YAML in the Nano editor.  
**Why it was used:** To modify the cloud-init user-data file.  
**Expected result:** File opens for editing.  
**Risk:** Low, but editing syntax-sensitive YAML requires care.

---

## Command
```bash
nano /var/lib/vz/snippets/docker-net.yml
```

**What it does:** Opens the network-data YAML in the Nano editor.  
**Why it was used:** To modify the network cloud-init YAML.  
**Expected result:** File opens for editing.  
**Risk:** Low, but YAML formatting mistakes can break boot-time networking.

---

## Command
```bash
ceph -s
```

**What it does:** Displays overall Ceph cluster health and service state.  
**Why it was used:** To confirm cluster readiness before adding CephFS-based storage.  
**Expected result:** Health summary, MON/MGR/OSD status, usage, and PG state.  
**Success indicates:** Cluster has quorum and stable OSD state.  
**Failure indicates:** Health warnings or errors that may affect storage reliability.  
**Homelab relevance:** Critical for judging whether shared storage changes are safe.

---

## Command
```bash
pveversion
ceph --version
```

**What it does:** Shows Proxmox and Ceph versions.  
**Why it was used:** To verify the environment during troubleshooting and confirm feature expectations.  
**Expected result:** Version strings for both components.

---

## Command
```bash
ceph fs volume create cephfs
```

**What it does:** Creates a CephFS filesystem named `cephfs`, including metadata and data pools.  
**Why it was used:** To create a shared file-based backend for snippets.  
**Expected result:** CephFS and its pools are created.  
**Success indicates:** File-backed shared storage can now be layered onto the cluster.  
**Failure indicates:** Ceph health or permission problems.  
**Risk:** Moderate. Creates new Ceph pools and filesystem structures.

---

## Command
```bash
ceph fs ls
```

**What it does:** Lists Ceph filesystems.  
**Why it was used:** To confirm that `cephfs` was created successfully.  
**Expected result:** `cephfs` appears in the output.

---

## Command
```bash
ceph df
```

**What it does:** Shows pool-level usage in Ceph.  
**Why it was used:** To confirm the new CephFS metadata and data pools existed.  
**Expected result:** Pools such as `cephfs.cephfs.meta` and `cephfs.cephfs.data` appear.

---

## Command
```bash
ceph crash archive-all
```

**What it does:** Archives recorded Ceph daemon crash reports.  
**Why it was used:** To clear stale health warnings before continuing.  
**Expected result:** Recent crash records are archived.  
**Success indicates:** Fewer health warnings if those crashes were already handled.  
**Risk:** Low, but it hides unresolved crash history if used carelessly.

---

## Command
```bash
ceph orch apply mds cephfs --placement="pve1 pve3"
```

**What it does:** Attempts to deploy CephFS MDS daemons using cephadm orchestrator.  
**Why it was used:** Initial attempt to create active and standby MDS services.  
**Expected result:** MDS daemons deployed on `pve1` and `pve3`.  
**Actual result in this session:** Failed because no orchestrator backend was configured.  
**Lesson:** Not appropriate in a Proxmox-managed Ceph cluster without cephadm.

---

## Command
```bash
ceph mds stat
```

**What it does:** Shows metadata server state for CephFS.  
**Why it was used:** To verify whether CephFS had active and standby MDS daemons.  
**Expected result:** One active MDS and ideally one standby.  
**Success indicates:** CephFS is operational for client mounts.

---

## Command
```bash
ceph fs status cephfs
```

**What it does:** Shows detailed status of the `cephfs` filesystem.  
**Why it was used:** To verify pool usage and active MDS state.  
**Expected result:** Filesystem details, MDS rank state, pool info, client count.

---

## Command
```bash
pveceph mds create
```

**Likely command used**

**What it does:** Creates a Ceph MDS daemon using Proxmox’s Ceph integration.  
**Why it was used:** Needed because `ceph orch` was unavailable.  
**Expected result:** An MDS service starts on the node.  
**Success indicates:** Proxmox-managed CephFS metadata service is available.  
**Risk:** Low to moderate. Creates and enables a Ceph service on the node.

---

## Command
```bash
nano /etc/pve/storage.cfg
```

**What it does:** Opens the cluster-wide Proxmox storage configuration file.  
**Why it was used:** To redefine `snips` as a CephFS-backed storage.  
**Expected result:** Manual storage configuration changes can be made.  
**Risk:** Moderate. Bad edits can break storage parsing cluster-wide.

---

## Command
```bash
pvesm status | grep snips
```

**What it does:** Shows storage status for the `snips` storage entry.  
**Why it was used:** To verify the new CephFS storage was active.  
**Expected result:** `snips` shows as active and of type `cephfs`.  
**Success indicates:** Proxmox can mount and use the storage.

---

## Command
```bash
mount | grep /mnt/pve/snips
```

**What it does:** Confirms the CephFS mount is active on the node.  
**Why it was used:** To verify the storage was actually mounted, not just defined.  
**Expected result:** A Ceph mount line for `/mnt/pve/snips`.

---

## Command
```bash
mkdir -p /mnt/pve/snips
```

**What it does:** Ensures the CephFS mount point directory exists.  
**Why it was used:** Needed before mounting or validating the storage path.  
**Expected result:** Directory exists.  
**Risk:** Low.

---

## Command
```bash
mkdir -p /mnt/pve/snips/snippets
```

**What it does:** Creates the shared snippets directory on CephFS.  
**Why it was used:** Proxmox snippet content was intended to live there.  
**Expected result:** Directory is created if it does not already exist.

---

## Command
```bash
cp /var/lib/vz/snippets/docker-userdata.yml /mnt/pve/snips/snippets/
cp /var/lib/vz/snippets/docker-net.yml      /mnt/pve/snips/snippets/
```

**What it does:** Copies the local snippet YAML files into the shared CephFS snippets directory.  
**Why it was used:** So all nodes could access the same snippet files through `snips`.  
**Expected result:** Files exist on shared storage.  
**Success indicates:** Future migrations can resolve snippet references cluster-wide.

---

## Command
```bash
pvesm list snips | grep snippets
```

**What it does:** Lists files known to the `snips` storage and filters for snippet entries.  
**Why it was used:** To confirm the YAML files were visible through Proxmox storage abstractions.  
**Expected result:** Both YAML files appear with `snippet` content type.

---

## Command
```bash
scp /var/lib/vz/snippets/docker-userdata.yml root@192.168.16.12:/mnt/pve/snips/snippets/
scp /var/lib/vz/snippets/docker-net.yml      root@192.168.16.12:/mnt/pve/snips/snippets/
```

**What it does:** Copies snippet files to another node using SCP.  
**Why it was used:** Attempted as a workaround before shared storage was fully fixed.  
**Expected result:** Files arrive on the target node.  
**Failure indicates:** Hostname resolution, connectivity, or permissions issue.  
**Risk:** Low. Manual file distribution can drift over time if not replaced by shared storage.

---

## Command
```bash
ssh root@192.168.16.12 'mkdir -p /mnt/pve/snips/snippets'
```

**What it does:** Creates the snippets directory remotely on the target node.  
**Why it was used:** Part of the workaround path while troubleshooting storage visibility.

---

## Command
```bash
getent hosts pve1
```

**What it does:** Checks whether the hostname `pve1` resolves on the current node.  
**Why it was used:** To troubleshoot SSH/SCP failures caused by missing name resolution.  
**Expected result:** The IP mapping for `pve1`.  
**Failure indicates:** `/etc/hosts` or DNS needs correction.

---

## Command
```bash
pvecm nodes
```

**What it does:** Shows nodes in the Proxmox cluster.  
**Why it was used:** Helpful for identifying cluster membership and likely management IP relationships.  
**Homelab relevance:** Useful during node-to-node troubleshooting.

---

## Command
```bash
grep -E 'node|ring0_addr' /etc/pve/corosync.conf
```

**What it does:** Extracts node names and cluster addresses from Corosync config.  
**Why it was used:** Helps identify node addressing when hostname resolution is broken.

---

## Command
```bash
nl -ba /etc/pve/storage.cfg | sed -n '1,80p'
```

**What it does:** Shows the storage config with line numbers.  
**Why it was used:** To identify the invalid first line and other parsing issues.  
**Expected result:** Human-readable numbered output for troubleshooting.

---

## Command
```bash
sed -i '1{/^ceph mds stat$/d}' /etc/pve/storage.cfg
```

**What it does:** Deletes line 1 if it exactly matches the accidental pasted command text.  
**Why it was used:** To remove the parser warning cause.  
**Expected result:** `storage.cfg` no longer starts with invalid command text.  
**Risk:** Moderate. Direct in-place edit to cluster config file.

---

## Command
```bash
sed -i '/^[[:space:]]*shared[[:space:]]\+/d' /etc/pve/storage.cfg
```

**What it does:** Removes invalid `shared` lines from the storage config.  
**Why it was used:** CephFS storage config rejected that property in this context.  
**Expected result:** No more `unexpected property 'shared'` parse errors.

---

## Command
```bash
head -n 3 /etc/pve/storage.cfg | cat -A
```

**What it does:** Displays the first few lines with hidden characters visible.  
**Why it was used:** To detect stray control characters or hidden text.  
**Expected result:** Makes line endings or invisible characters obvious.

---

## Command
```bash
sed -i '1s/^\xEF\xBB\xBF//' /etc/pve/storage.cfg
```

**What it does:** Removes a UTF-8 BOM if present at the start of the file.  
**Why it was suggested:** Hidden characters can cause parser oddities.  
**Expected result:** Cleaner file start if BOM existed.

---

## Command
```bash
sed -i 's/\r$//' /etc/pve/storage.cfg
```

**What it does:** Converts Windows CRLF endings to Unix LF endings.  
**Why it was suggested:** Prevents parsing problems caused by carriage returns.

---

## Command
```bash
grep -n '/var/lib/docker' /etc/fstab
```

**What it does:** Finds Docker-related mount entries in the guest filesystem table.  
**Why it was used:** To troubleshoot boot failures and Docker disk mount issues.  
**Expected result:** Relevant `/var/lib/docker` line(s).  
**Failure indicates:** Missing mount entry or wrong file state.

---

## Command
```bash
lsblk -f
```

**What it does:** Lists block devices, filesystems, labels, and UUIDs.  
**Why it was used:** To identify the Docker disk and verify labels/UUIDs.  
**Expected result:** Filesystem and identifier details for attached disks.  
**Homelab relevance:** Essential for diagnosing guest disk mount issues.

---

## Command
```bash
ls -l /dev/disk/by-label
```

**What it does:** Lists symlinks for disks by filesystem label.  
**Why it was used:** To verify whether the expected Docker disk label actually existed.

---

## Command
```bash
blkid
```

**What it does:** Prints block device UUIDs, labels, and filesystem types.  
**Why it was used:** To compare real device identifiers against `/etc/fstab`.

---

## Command
```bash
umount /var/lib/docker
```

**Likely command used**

**What it does:** Unmounts the Docker data mountpoint.  
**Why it was suggested:** Needed before running filesystem repair.  
**Risk:** Moderate. Unsafe if Docker is actively using the mount.

---

## Command
```bash
e2fsck -f -y /dev/disk/by-label/docker
```

**What it does:** Forces an ext filesystem check and auto-answers yes to repairs.  
**Why it was suggested:** To repair a Docker data disk if fsck was blocking boot.  
**Expected result:** Filesystem inconsistencies repaired.  
**Success indicates:** Disk may mount cleanly afterwards.  
**Failure indicates:** More serious corruption or wrong device selection.  
**Risk:** Moderate to high. Filesystem repair changes disk metadata; must target the correct device.

---

## Command
```bash
mount /var/lib/docker
```

**What it does:** Attempts to mount the Docker data filesystem manually.  
**Why it was used:** To validate whether the disk would now mount after repair or config changes.

---

## Command
```bash
systemctl restart docker
```

**What it does:** Restarts the Docker daemon.  
**Why it was used:** To bring Docker back after mount recovery.  
**Expected result:** Docker service starts successfully.  
**Failure indicates:** Mount, daemon, or config issues remain.

---

## Command
```bash
systemctl daemon-reload
```

**What it does:** Reloads systemd unit definitions after config changes.  
**Why it was used:** Needed after changing mount-related config or unit files.  
**Expected result:** systemd recognizes the updated configuration.

---

## Command
```bash
mount -a
```

**What it does:** Attempts to mount all filesystems defined in `/etc/fstab`.  
**Why it was suggested:** Quick validation of corrected fstab entries.  
**Expected result:** All valid mounts come up without error.  
**Failure indicates:** Remaining fstab issues.

---

## Command
```bash
systemd-analyze verify /etc/fstab
```

**What it does:** Validates systemd interpretation of fstab.  
**Why it was suggested:** Helps catch duplicate or invalid mount definitions before reboot.

---

## Command
```bash
mount | grep -E '/var/lib/docker|/opt/docker-apps|/opt/compose'
```

**What it does:** Verifies whether the Docker data mount and bind mounts are active.  
**Why it was used:** To confirm guest storage layout after mount troubleshooting.

---

## Command
```bash
systemctl list-unit-files | grep -E 'opt-.*\.mount'
```

**What it does:** Lists mount units related to the problematic bind paths.  
**Why it was used:** To check whether `.mount` units duplicated the fstab entries.

---

## Command
```bash
ls -l /etc/systemd/system/*opt*mount
```

**What it does:** Shows mount unit files related to `/opt` paths.  
**Why it was used:** To identify duplicate systemd mount definitions.

---

## Command
```bash
rm -f /etc/systemd/system/opt-docker*x2dapps.mount /etc/systemd/system/opt-compose.mount
```

**What it does:** Removes manually defined systemd mount units that could duplicate fstab entries.  
**Why it was used:** To eliminate duplicate mount sources.  
**Risk:** Moderate. Deletes unit files; confirm they are truly duplicates before removal.

---

## Command
```bash
mount -o remount,rw /
```

**What it does:** Remounts the root filesystem read-write.  
**Why it was used:** Required when booting into a minimal recovery shell before editing files.  
**Expected result:** System files become writable.  
**Risk:** Low in recovery context.

---

## Command
```bash
exec /sbin/reboot -f
```

**What it does:** Forces an immediate reboot from a limited recovery environment.  
**Why it was used:** Useful after repairs when normal reboot tooling may be unavailable.  
**Risk:** Moderate. Forceful reboot can skip some normal shutdown behavior.

---

## Command
```bash
journalctl -xb
```

**What it does:** Shows logs for the current boot.  
**Why it was referenced:** systemd emergency mode explicitly suggested it for diagnosis.  
**Expected result:** Boot-time failure details.  
**Homelab relevance:** Critical for diagnosing guest boot failures.

---

## Command
```bash
ssh root@192.168.16.12 'qm set 100 -cicustom "user=snips:snippets/docker-userdata.yml,network=snips:snippets/docker-net.yml" && qm cloudinit update 100'
```

**Likely command used**

**What it does:** Runs the cloud-init reconfiguration directly on the node holding VM 100.  
**Why it was useful:** After migration, VM config operations needed to happen on the correct node.  
**Expected result:** VM 100’s cloud-init settings are updated on the owning node.

---

## Command
```bash
qm start 100
```

**What it does:** Starts VM 100.  
**Why it was used:** To boot the VM after cloud-init and storage changes.  
**Expected result:** VM boots normally.

---

## Command
```bash
grep -R --line-number 'snips:' /etc/pve/nodes/*/qemu-server /etc/pve/nodes/*/lxc
```

**What it does:** Searches all VM and container configs for references to `snips`.  
**Why it was suggested:** To find dependent configs before removing or redefining storage.  
**Expected result:** All configs using `snips` are listed.

---

## Command
```bash
pvesm list snips
```

**What it does:** Lists objects available in the `snips` storage.  
**Why it was used:** To confirm snippet visibility and storage correctness.

---

## Command
```bash
file /etc/pve/storage.cfg
```

**Likely command used or implied by output context**

**What it does:** Normally identifies file type, but in this session parser output referencing the file appeared alongside status checks.  
**Why it matters:** The important operational point was that Proxmox was parsing `storage.cfg` and warning about invalid content.

---

## Command
```bash
xxd -g 1 -l 32 /etc/pve/storage.cfg
```

**What it does:** Shows the first bytes of the file in hex.  
**Why it was suggested:** To detect hidden bytes or malformed file beginnings if warnings persisted.

---

## Command
```bash
grep -H . /etc/pve/nodes/*/qemu-server/100.conf
```

**Likely command used**

**What it does:** Searches for the VM 100 config file across cluster node directories.  
**Why it was suggested:** To determine which node currently owned the VM config after migration.  
**Expected result:** Path to the active config location.

---

## Command
```bash
awk '/^lock|^node/ {print}' /etc/pve/qemu-server/100.conf
```

**Likely command used**

**What it does:** Extracts lock or node-related lines from a VM config.  
**Why it was suggested:** Helps identify VM location or migration state quickly.
