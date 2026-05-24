---
title: "Cloud-Init Snippet Path and Storage Mapping Troubleshooting"
track: "infrastructure"
category: "automation"
type: "runbook"
logical_order: 40
date_rule: "Dates are removed from filenames, visible headings, indexes, generated metadata, and runbook body content."
---

# Cloud-Init Snippet Path and Storage Mapping Troubleshooting

## Summary
Work focused on getting a Proxmox VM to consume custom cloud-init user-data and network-data YAML files for a Debian Docker VM. The primary goal was to change the VM IP through cloud-init and preserve the existing homelab provisioning logic in YAML.

## Environment
- Proxmox VE host: `mainframe`
- VM ID: `100`
- VM role: Debian Docker VM
- Cloud-init snippets storage ID: `snips`
- `snips` storage config:
  - type: `dir`
  - path: `/var/lib/vz/snips`
  - content: `snippets`
  - shared: `0`
- Cloud-init disk storage: `cephpool`
- Network: `192.168.16.0/24`
- Gateway: `192.168.16.1`
- Intended VM IP: `192.168.16.3`
- Guest NIC names observed later: `eth0`, alternate names `enp0s18`, `ens18`

## Problem
The VM was expected to read custom cloud-init YAML from Proxmox snippet storage, but Proxmox kept generating default cloud-init content instead of embedding the custom user-data.

## Symptoms
- `qm cloudinit dump 100 user` repeatedly showed only default content such as:

```yaml
#cloud-config
hostname: debian-docker
manage_etc_hosts: true
fqdn: debian-docker
chpasswd:
  expire: False
users:
  - default
package_upgrade: true
```

- Initial snippet lookup failed because the file was not found in the assumed directory:

```text
ls: cannot access '/var/lib/vz/snippets/docker-userdata.yml': No such file or directory
```

- Even after correcting the path, Proxmox still embedded default user-data instead of the custom YAML.

## Actions Taken
1. Verified the `cicustom` setting on VM 100.

```bash
qm set 100 --cicustom "user=snips:snippets/docker-userdata.yml,network=snips:snippets/docker-net.yml"
qm cloudinit update 100
```

Purpose: tell Proxmox to use custom user-data and network-data snippets.

2. Confirmed the `snips` storage configuration.

```bash
cat /etc/pve/storage.cfg | grep -A3 snips
```

Purpose: identify the real snippet storage path.

3. Determined that `snips` maps to:

```text
/var/lib/vz/snips/snippets/
```

not:

```text
/var/lib/vz/snippets/
```

4. Created or moved snippet files into the correct directory.

```bash
mkdir -p /var/lib/vz/snips/snippets
```

5. Verified Proxmox could see and resolve the snippet files.

```bash
pvesm list snips
pvesm path snips:snippets/docker-userdata.yml
pvesm path snips:snippets/docker-meta.yml
```

Purpose: confirm Proxmox storage resolution.

6. Tested both `.yml` and `.yaml` naming, cleaned CRLF line endings, checked for BOM-like issues, and verified permissions.

```bash
sed -i 's/\r$//' /var/lib/vz/snips/snippets/docker-*.yml
chmod 0644 /var/lib/vz/snips/snippets/docker-*.yml
```

7. Tested with a minimal cloud-init file to rule out YAML complexity.

```bash
cat > /var/lib/vz/snips/snippets/user-min.yaml <<'EOF'
#cloud-config
write_files:
  - path: /root/OK_MIN_SNIPS
    permissions: '0644'
    content: hi
EOF
```

Purpose: isolate whether any valid `user=` snippet would embed.

## Key Findings
**Facts**
- The correct snippet storage path for `snips:` was `/var/lib/vz/snips/snippets/`.
- Proxmox resolved the files correctly:

```bash
pvesm path snips:snippets/docker-userdata.yml
```

returned:

```text
/var/lib/vz/snips/snippets/docker-userdata.yml
```

- `pvesm list snips` showed the files as valid snippet objects.
- Despite this, `qm cloudinit dump 100 user` still showed only default user-data.
- The same fallback happened even with a minimal test file.

**Interpretation**
- The problem was no longer the file path once `snips` was corrected.
- The issue appeared to be in the Proxmox cloud-init embed step for `cicustom user=...`, because Proxmox could resolve the file but still generated default user-data.

## Resolution
Path confusion was resolved, but the core `cicustom user=` embedding issue remained unresolved in this session.

## Validation
Success was partially validated:
- Proxmox storage resolved the files correctly.
- Snippet files appeared in `pvesm list snips`.
- Full validation failed because `qm cloudinit dump 100 user` never reflected the custom YAML.

## Follow-Up Tasks
- Avoid assuming `/var/lib/vz/snippets/` when a custom snippets storage is configured.
- Prefer verifying snippet storage with `pvesm path` before troubleshooting YAML content.
- Use a manual NoCloud ISO as a fallback when `qm cloudinit dump` keeps showing default content.

## Lessons Learned
- In Proxmox, `storageID:snippets/file.yml` maps to `<storage path>/snippets/file.yml`, not necessarily `/var/lib/vz/snippets/`.
- `pvesm path` is the quickest way to prove the real filesystem mapping.
- If `qm cloudinit dump <vmid> user` keeps showing default content, the problem is likely the embed pipeline rather than YAML syntax alone.

# VM 100 Rebuild Attempt and Accidental Ceph RBD Data Disk Deletion

## Summary
After repeated cloud-init failures, the VM was rebuilt. During that process, the secondary Ceph RBD disk intended for Docker data was detached incorrectly and deleted.

## Environment
- Proxmox host: `mainframe`
- VM ID: `100`
- Storage pool: `cephpool`
- Data disk that was intended to be preserved: `cephpool:vm-100-disk-1`
- Cloud-init disk: `cephpool:vm-100-cloudinit`

## Problem
The goal was to preserve the Docker data disk while recreating VM 100, but the chosen Proxmox disk removal action deleted the Ceph RBD image instead.

## Symptoms
- After deleting `scsi1`, Proxmox began removing an image from Ceph:

```text
Removing image: 100% complete...done.
```

- Reattaching failed:

```text
rbd error: rbd: error opening image vm-100-disk-1: (2) No such file or directory
```

## Actions Taken
1. Attempted to detach the Docker data disk:

```bash
qm set 100 --delete scsi1
```

Purpose: intended to remove the disk from VM config while preserving the underlying RBD volume.

2. Destroyed and recreated the VM configuration.

3. Attempted to reattach the old data disk:

```bash
qm set 100 --scsi1 cephpool:vm-100-disk-1
```

Purpose: restore the preserved Docker data disk.

## Key Findings
**Facts**
- `qm set 100 --delete scsi1` removed the disk entry and triggered Ceph image deletion.
- The RBD image `vm-100-disk-1` no longer existed afterward.
- Later reattach attempts failed because the volume was gone.

**Interpretation**
- On this setup, using `qm set --delete <disk>` on an attached Ceph disk was destructive.
- The operation behaved as “remove and delete,” not “detach and preserve.”

## Resolution
The Docker data disk was lost during the rebuild attempt. The workflow was abandoned in favor of creating a fresh VM and fresh data disk.

## Validation
The loss was confirmed by:

```bash
qm set 100 --scsi1 cephpool:vm-100-disk-1
```

returning:

```text
rbd error: rbd: error opening image vm-100-disk-1: (2) No such file or directory
```

## Follow-Up Tasks
- Use the Proxmox GUI “Detach” behavior or explicitly move disks to `unusedX` if preservation is required.
- Treat `qm set --delete <disk>` as risky on Ceph-backed VM disks.
- Confirm backup or snapshot coverage before destructive disk operations.

## Lessons Learned
- Do not assume “delete from VM config” means “preserve storage volume.”
- On Proxmox with Ceph RBD, disk deletion commands can be immediately destructive.
- Secondary data disks should be backed up or snapshotted before rebuild operations.

# Fresh VM 100 Clone from Debian 12 Cloud Template

## Summary
A fresh VM 100 was created from a Debian 12 cloud template. The Proxmox VM name was changed to `docker`, a new 200 GB data disk was attached, and cloud-init networking from Proxmox was configured successfully.

## Environment
- Proxmox host: `mainframe`
- New VM ID: `100`
- Proxmox VM name: `docker`
- Template source: Debian 12 cloud template
- Boot disk: 50 GB clone of template
- Data disk: `cephpool:vm-100-disk-1,size=200G`
- Cloud-init disk: `cephpool:vm-100-cloudinit`
- Static IP from Proxmox: `192.168.16.3/24`
- Gateway: `192.168.16.1`
- Nameservers: `192.168.16.1`, `1.1.1.1`

## Problem
A clean rebuild was needed after the earlier cloud-init and VM state became unreliable.

## Symptoms
- The new VM cloned successfully.
- Proxmox-generated network config worked.
- Proxmox still embedded default cloud-init user-data instead of the custom YAML, even after moving snippets to `local:snippets`.

## Actions Taken
1. Cloned VM 100 from the Debian 12 cloud template.
2. Set the Proxmox VM name to `docker`.
3. Applied VM resources, networking, and console settings.
4. Attached a new 200 GB Ceph data disk:

```bash
qm set 100 --scsi1 cephpool:200
```

5. Applied cloud-init network fields:

```bash
qm set 100 --ipconfig0 ip=192.168.16.3/24,gw=192.168.16.1
qm set 100 --nameserver 192.168.16.1,1.1.1.1
```

6. Attempted to use `local:snippets` instead of `snips:snippets` for user-data and meta-data.

## Key Findings
**Facts**
- The clone succeeded and transferred approximately 50 GB from the template.
- Proxmox created the new data disk successfully.
- `qm cloudinit dump 100 network` showed a valid Proxmox-generated network configuration.
- `qm cloudinit dump 100 user` still showed default user-data:

```yaml
users:
  - default
```

**Interpretation**
- Network configuration via Proxmox fields worked even when custom user-data did not.
- The custom user-data embed issue was not limited to the `snips` storage path.

## Resolution
The fresh VM was created successfully and was recoverable. Networking from Proxmox worked. Custom cloud-init user-data remained unresolved through the standard `cicustom` path.

## Validation
Successful parts were validated by:
- clone completion
- creation of `scsi1` on `cephpool`
- valid network output in:

```bash
qm cloudinit dump 100 network
```

## Follow-Up Tasks
- Keep using Proxmox-generated networking for reliability.
- Use a manual NoCloud ISO for user-data if `cicustom user=` continues to fall back to defaults.
- Reintroduce provisioning steps in a controlled way after guest access is confirmed.

## Lessons Learned
- Separate cloud-init networking from cloud-init user-data when troubleshooting.
- Proxmox `ipconfig0` can work even when `cicustom user=` does not.
- Fresh cloning is often faster than prolonged recovery after cloud-init state corruption.

# Guest Recovery, Console Access, and Network Boot Stall

## Summary
After the fresh VM was created, guest recovery focused on restoring console access, working login credentials, and stable networking. The VM later stalled at `systemd-networkd-wait-online`, which was fixed inside the guest.

## Environment
- Guest OS: Debian 12 cloud image
- Proxmox VM name: `docker`
- Guest hostname observed in some stages: `debian-docker`
- Console access methods:
  - Proxmox noVNC / VGA console
  - serial console
- Network manager in guest: `systemd-networkd`
- Guest NIC observed as:
  - primary runtime name: `eth0`
  - alternative names: `enp0s18`, `ens18`

## Problem
The VM became hard to access after `cloud-init clean`, and later boot stalls occurred at `systemd-networkd-wait-online`.

## Symptoms
- Root login in console was blocked:

```text
root account blocked
```

- Serial console usability was inconsistent.
- The VM stalled at:

```text
systemd-networkd-wait-online
```

- Networking later showed the guest had:
  - IPv4 `192.168.16.3`
  - gateway `192.168.16.1`

## Actions Taken
1. Set built-in cloud-init fields instead of relying on custom user-data:

```bash
qm set 100 --ciuser debian
qm set 100 --cipassword 'Temp-Password-123!'
qm set 100 --ipconfig0 ip=dhcp
```

Purpose: regain access with a known non-root user.

2. Switched console behavior:

```bash
qm set 100 --serial0 socket --vga std
```

Purpose: improve console usability through Proxmox.

3. Logged into the guest and disabled the wait-online service:

```bash
systemctl disable --now systemd-networkd-wait-online.service
systemctl mask systemd-networkd-wait-online.service
```

Purpose: stop boot delays when the interface did not satisfy wait-online conditions.

4. Disabled cloud-init guest-side network rendering:

```bash
printf 'network: {config: disabled}\n' > /etc/cloud/cloud.cfg.d/99-disable-network-config.cfg
```

Purpose: prevent future conflicts between cloud-init and manual/systemd-networkd config.

5. Created a static `systemd-networkd` file for the guest.

```bash
cat >/etc/systemd/network/10-ens18.network <<'EOF'
[Match]
Name=ens18

[Network]
Address=192.168.16.3/24
Gateway=192.168.16.1
DNS=192.168.16.1
DNS=1.1.1.1
EOF
```

Purpose: define the desired static IP in-guest.

6. Restarted network services and validated:

```bash
systemctl restart systemd-networkd
networkctl status ens18
```

7. Noted the real runtime device naming:
   - `eth0` was the active name
   - `ens18` and `enp0s18` were alternate names

8. Planned a more robust match file using both names and MAC address.

## Key Findings
**Facts**
- Root login was blocked because the cloud image kept root locked.
- Console access worked with the `debian` user rather than root.
- The network came up successfully with static IPv4 `192.168.16.3`.
- `networkctl status ens18` showed the link as routable and online.
- The interface naming was broader than expected; matching only `ens18` was less robust than matching `eth0` plus alternate names and/or MAC.

**Interpretation**
- The boot stall was caused by wait-online behavior rather than total network failure.
- Managing guest networking directly with `systemd-networkd` was more reliable than waiting on cloud-init user-data for this rebuild.

## Resolution
Console access was restored with a normal user, and the boot stall at `systemd-networkd-wait-online` was resolved by masking the wait service and managing the guest network directly with `systemd-networkd`.

## Validation
Validation succeeded with:

```bash
networkctl status ens18
ip -4 addr show dev ens18
ip route
ping -c2 192.168.16.1
ping -c2 1.1.1.1
getent hosts debian.org
```

Observed state:
- static IP assigned
- default gateway present
- DNS configured
- network online

## Follow-Up Tasks
- Replace the initial interface match file with a more robust file matching `eth0`, `ens18`, `enp0s18`, and MAC address.
- Set Proxmox cloud-init networking to manual if in-guest `systemd-networkd` becomes the long-term source of truth.
- Confirm boot remains fast after reboot.

## Lessons Learned
- Cloud images often lock root by default; use a non-root user for recovery.
- `systemd-networkd-wait-online` can block boot even when the interface is nearly functional.
- In-guest network ownership should be explicit; do not let cloud-init and manual networking both try to manage the same interface.

# Manual NoCloud ISO Workaround for Cloud-Init User-Data

## Summary
Because Proxmox kept embedding default user-data instead of the custom YAML, a manual NoCloud `cidata` ISO was built from the user-data file and attached directly to the VM as a CDROM.

## Environment
- Proxmox host: `mainframe`
- VM ID: `100`
- Manual ISO path: `/var/lib/vz/template/iso/ci-100-userdata.iso`
- Source user-data file: `/var/lib/vz/snippets/docker-userdata.yml`
- Temporary staging path: `/tmp/ci-100/`
- ISO label: `cidata`

## Problem
Standard `qm cloudinit update` never embedded the custom user-data file, even from `local:snippets`.

## Symptoms
- `qm cloudinit dump 100 user` kept returning the default fallback.
- Both `snips:` and `local:` snippet sources exhibited the same behavior.
- A manual ISO was needed to bypass the embed path.

## Actions Taken
1. Staged user-data and meta-data:

```bash
mkdir -p /tmp/ci-100
cp /var/lib/vz/snippets/docker-userdata.yml /tmp/ci-100/user-data
printf 'instance-id: iid-%s\nlocal-hostname: docker\n' "$VMID-$(date +%s)" > /tmp/ci-100/meta-data
```

2. Built a NoCloud ISO using `genisoimage` or equivalent.
3. Mounted the ISO on the host and confirmed contents:

```text
meta-data
user-data
```

4. Replaced the Proxmox cloud-init CDROM with the manual ISO:

```bash
qm set 100 --delete ide2
qm set 100 --ide2 local:iso/ci-100-userdata.iso,media=cdrom
```

## Key Findings
**Facts**
- The manual ISO was created successfully.
- Mounting the ISO on the Proxmox host showed the expected files.
- The ISO attachment to VM 100 succeeded.

**Interpretation**
- This approach bypassed Proxmox’s failing `cicustom user=` embed mechanism.
- The manual ISO became the most deterministic path to get the original cloud-init YAML into the guest.

## Resolution
The manual NoCloud ISO workaround was prepared and attached. At the point this documentation request was made, the workaround had been staged but not yet fully validated as the final long-term provisioning method.

## Validation
Successful host-side validation:
- ISO built without error
- ISO contents visible when loop-mounted
- ISO attached to VM as `ide2`

Guest-side validation of full YAML execution was still pending at the end of the session.

## Follow-Up Tasks
- Boot the guest with the manual ISO attached.
- Run:

```bash
cloud-init clean
reboot
```

inside the VM if needed to force a fresh run.
- Verify package installation, files, timers, and mount configuration from the YAML.
- Decide whether to keep the manual ISO workflow or continue troubleshooting Proxmox embed behavior.

## Lessons Learned
- A manual NoCloud ISO is a strong fallback when Proxmox `cicustom` user-data embedding fails silently.
- Always verify the ISO contents before attaching it to a VM.
- Separating host-side ISO build validation from guest-side cloud-init execution validation keeps troubleshooting clearer.

# Command Reference

## Command
```bash
qm set 100 --cicustom "user=snips:snippets/docker-userdata.yml,network=snips:snippets/docker-net.yml"
```

**What it does:** Tells Proxmox VM 100 to use custom cloud-init user-data and network-data snippet files.  
**Why it was used:** To make the VM consume the saved YAML instead of autogenerated defaults.  
**Expected result:** `qm cloudinit update 100` should build an ISO containing the specified files.  
**Success indicates:** `qm cloudinit dump 100 user` and `qm cloudinit dump 100 network` show the custom content.  
**Failure indicates:** Proxmox fell back to defaults or could not embed the snippets.  
**Risk:** Low.

## Command
```bash
qm cloudinit update 100
```

**What it does:** Rebuilds the cloud-init ISO for VM 100.  
**Why it was used:** Required after changing any cloud-init setting, such as `cicustom`, `ipconfig0`, or metadata.  
**Expected result:** Proxmox prints `generating cloud-init ISO`.  
**Success indicates:** New cloud-init data is available to the VM at next boot.  
**Failure indicates:** The ISO was not rebuilt or underlying storage had an issue.  
**Risk:** Low.

## Command
```bash
qm cloudinit dump 100 user
```

**What it does:** Shows the effective user-data content currently embedded in the VM’s cloud-init ISO.  
**Why it was used:** To prove whether custom user-data was actually embedded.  
**Expected result:** Full YAML from the snippet file.  
**Success indicates:** The VM should see the custom user-data on boot.  
**Failure indicates:** If it shows default content, Proxmox embedded fallback data instead.  
**Risk:** Low.

## Command
```bash
qm cloudinit dump 100 network
```

**What it does:** Shows the effective network config embedded in the cloud-init ISO.  
**Why it was used:** To verify whether Proxmox networking or custom network YAML was being applied.  
**Expected result:** Either custom network YAML or Proxmox-generated v1 config.  
**Success indicates:** Network configuration is present for the guest.  
**Failure indicates:** Missing or incorrect network config in the ISO.  
**Risk:** Low.

## Command
```bash
cat /etc/pve/storage.cfg | grep -A3 snips
```

**What it does:** Displays the `snips` storage definition and its next three lines.  
**Why it was used:** To find the real path and content type of the snippets storage.  
**Expected result:** The `path` and `content snippets` lines.  
**Success indicates:** You know where Proxmox expects snippet files.  
**Failure indicates:** Storage config may be missing or misnamed.  
**Risk:** Low.

## Command
```bash
mkdir -p /var/lib/vz/snips/snippets
```

**What it does:** Creates the actual snippet directory path for the `snips` storage.  
**Why it was used:** The original assumption about `/var/lib/vz/snippets` was wrong.  
**Expected result:** Directory exists without error.  
**Success indicates:** Snippet files can be placed where `snips:` expects them.  
**Failure indicates:** Filesystem permission or path issue.  
**Risk:** Low.

## Command
```bash
pvesm list snips
```

**What it does:** Lists objects visible through the `snips` Proxmox storage.  
**Why it was used:** To confirm Proxmox could see the snippet files.  
**Expected result:** Entries like `snips:snippets/docker-userdata.yml`.  
**Success indicates:** Storage registration and file presence are correct.  
**Failure indicates:** Files are in the wrong place or storage is inactive.  
**Risk:** Low.

## Command
```bash
pvesm path snips:snippets/docker-userdata.yml
```

**What it does:** Resolves a Proxmox storage object into its real filesystem path.  
**Why it was used:** To prove which directory Proxmox was actually using.  
**Expected result:** `/var/lib/vz/snips/snippets/docker-userdata.yml`.  
**Success indicates:** The snippet storage mapping is understood correctly.  
**Failure indicates:** Proxmox cannot resolve the object.  
**Risk:** Low.

## Command
```bash
sed -i 's/\r$//' /var/lib/vz/snips/snippets/docker-*.yml
```

**What it does:** Removes Windows CRLF carriage returns from the YAML files.  
**Why it was used:** CRLF line endings can break YAML parsing or cloud-init behavior.  
**Expected result:** Files remain present with Unix line endings.  
**Success indicates:** Line-ending corruption is ruled out.  
**Failure indicates:** File path or shell glob issue.  
**Risk:** Low.

## Command
```bash
chmod 0644 /var/lib/vz/snips/snippets/docker-*.yml
```

**What it does:** Sets standard readable permissions on the snippet files.  
**Why it was used:** To ensure Proxmox could read the files.  
**Expected result:** Files become owner-writable and world-readable.  
**Success indicates:** Permissions are unlikely to block embed.  
**Failure indicates:** File ownership or path issue.  
**Risk:** Low.

## Command
```bash
qm config 100 | egrep -i 'cicustom|ide2|cloudinit|ipconfig|ciuser|sshkeys'
```

**What it does:** Displays the cloud-init-relevant parts of the VM config.  
**Why it was used:** To verify that cloud-init disk, custom snippets, and CI fields were actually set.  
**Expected result:** `ide2`, `cicustom`, and other relevant lines.  
**Success indicates:** Proxmox VM config contains the intended cloud-init settings.  
**Failure indicates:** Required config values were not applied.  
**Risk:** Low.

## Command
```bash
qm set 100 --delete scsi1
```

**What it does:** Removes the `scsi1` disk definition from VM 100.  
**Why it was used:** Intended as a detach step before rebuilding the VM.  
**Expected result:** Disk no longer attached to VM.  
**Actual result in this session:** The underlying Ceph RBD volume was deleted.  
**Success/failure meaning:** On this setup, “success” was destructive.  
**Risk:** **High / destructive.**  
**Safer alternative:** Use the Proxmox GUI detach workflow or move the disk to `unusedX` before rebuild.

## Command
```bash
qm destroy 100 --destroy-unreferenced-disks 0
```

**Likely command used**  
**What it does:** Destroys VM 100 while attempting to preserve unreferenced disks.  
**Why it was used:** To rebuild the VM without intentionally deleting preserved data disks.  
**Expected result:** VM config removed, detached disks retained.  
**Failure indicates:** Detached disk handling was not actually safe beforehand.  
**Risk:** Medium to high if disk state is misunderstood.

## Command
```bash
qm clone <TEMPLATE_VMID> 100 --name docker --full 1 --storage cephpool
```

**Likely command used**  
**What it does:** Creates a full clone of the Debian 12 cloud template as VM 100 with the Proxmox name `docker`.  
**Why it was used:** To start fresh after the failed recovery/rebuild path.  
**Expected result:** New VM 100 with a 50 GB boot disk copied from the template.  
**Success indicates:** Clean starting point for provisioning.  
**Failure indicates:** Template, storage, or cluster issue.  
**Risk:** Medium due to storage consumption.

## Command
```bash
qm set 100 --name docker
```

**What it does:** Sets the Proxmox display name of VM 100 to `docker`.  
**Why it was used:** The user wanted the Proxmox VM name changed, not the in-guest hostname.  
**Expected result:** VM appears as `docker` in Proxmox inventory.  
**Success indicates:** Proxmox metadata updated.  
**Failure indicates:** VMID conflict or CLI issue.  
**Risk:** Low.

## Command
```bash
qm set 100 --scsi1 cephpool:200
```

**What it does:** Creates and attaches a new 200 GB Ceph RBD disk at `scsi1`.  
**Why it was used:** To replace the lost Docker data disk with a fresh one.  
**Expected result:** New disk object such as `cephpool:vm-100-disk-1,size=200G`.  
**Success indicates:** Fresh data disk available, usually as `/dev/sdb`.  
**Failure indicates:** Storage syntax, pool, or Ceph issue.  
**Risk:** Medium.

## Command
```bash
qm set 100 --ipconfig0 ip=192.168.16.3/24,gw=192.168.16.1
```

**What it does:** Tells Proxmox to generate static cloud-init network config for the first NIC.  
**Why it was used:** To reliably set networking even while custom user-data embedding was broken.  
**Expected result:** `qm cloudinit dump 100 network` shows static IP and gateway.  
**Success indicates:** Cloud-init networking from Proxmox should work on boot.  
**Failure indicates:** Guest may not receive the expected IP.  
**Risk:** Low.

## Command
```bash
qm set 100 --nameserver 192.168.16.1,1.1.1.1
```

**What it does:** Sets DNS servers in Proxmox’s cloud-init network generation.  
**Why it was used:** To match the intended static network configuration.  
**Expected result:** Nameserver list appears in the generated network config.  
**Success indicates:** Guest should receive those resolvers on boot.  
**Failure indicates:** DNS may be missing or malformed in the generated config.  
**Risk:** Low.

## Command
```bash
qm set 100 --ciuser debian
qm set 100 --cipassword 'Temp-Password-123!'
```

**What they do:** Set the default cloud-init username and password for the VM.  
**Why they were used:** To recover guest access when custom user-data was not applying.  
**Expected result:** A usable `debian` login account appears after cloud-init runs.  
**Success indicates:** Console access can be restored without relying on root.  
**Failure indicates:** Cloud-init did not rerun or did not apply the fields.  
**Risk:** Medium because a temporary password is being stored in config.

## Command
```bash
qm set 100 --serial0 socket --vga std
```

**What it does:** Enables a serial socket and uses a standard VGA console.  
**Why it was used:** To improve console usability during guest recovery.  
**Expected result:** Easier noVNC input and usable serial terminal fallback.  
**Success indicates:** Console login becomes possible.  
**Failure indicates:** The problem is in the guest boot/login path, not just console mode.  
**Risk:** Low.

## Command
```bash
cloud-init clean
```

**What it does:** Clears cloud-init instance state inside the guest so the next boot runs initialization again.  
**Why it was used:** To force cloud-init to reapply configuration after changing metadata or the attached CD.  
**Expected result:** Next boot reprocesses cloud-init inputs.  
**Success indicates:** New cloud-init inputs should be consumed.  
**Failure indicates:** Guest may reapply bad/default inputs and become inaccessible.  
**Risk:** Medium. Use carefully when the cloud-init source is not yet confirmed.

## Command
```bash
systemctl disable --now systemd-networkd-wait-online.service
systemctl mask systemd-networkd-wait-online.service
```

**What they do:** Stop, disable, and hard-mask the wait-online service.  
**Why they were used:** The VM stalled during boot at `systemd-networkd-wait-online`.  
**Expected result:** Faster boot without blocking on network-online state.  
**Success indicates:** Boot proceeds even if the network is slow or partially misdetected.  
**Failure indicates:** Another boot dependency is still blocking startup.  
**Risk:** Low. The tradeoff is that some services may start before networking is fully ready.

## Command
```bash
printf 'network: {config: disabled}\n' > /etc/cloud/cloud.cfg.d/99-disable-network-config.cfg
```

**What it does:** Disables cloud-init network rendering inside the guest.  
**Why it was used:** To prevent cloud-init and `systemd-networkd` from both trying to manage the NIC.  
**Expected result:** Guest networking is controlled only by local `.network` files.  
**Success indicates:** Future reboots avoid config fights.  
**Failure indicates:** Cloud-init may still overwrite network config.  
**Risk:** Low.

## Command
```bash
cat >/etc/systemd/network/10-ens18.network <<'EOF'
[Match]
Name=ens18

[Network]
Address=192.168.16.3/24
Gateway=192.168.16.1
DNS=192.168.16.1
DNS=1.1.1.1
EOF
```

**What it does:** Creates a static `systemd-networkd` configuration file for the VM NIC.  
**Why it was used:** To make networking work in-guest when cloud-init networking was unreliable.  
**Expected result:** The guest comes up at `192.168.16.3/24` with the specified gateway and DNS.  
**Success indicates:** `networkctl`, `ip route`, and ping tests succeed.  
**Failure indicates:** Wrong interface match or another network manager conflict.  
**Risk:** Low.

## Command
```bash
systemctl restart systemd-networkd
networkctl status ens18
```

**What they do:** Restart `systemd-networkd` and inspect the link state of the configured NIC.  
**Why they were used:** To apply and validate the static network file.  
**Expected result:** Interface shows `configured`, `routable`, and `online`.  
**Success indicates:** Networking is healthy.  
**Failure indicates:** The match file or route settings are wrong.  
**Risk:** Low.

## Command
```bash
cat >/home/debian/.ssh/authorized_keys <<'EOF'
...
EOF
```

**Likely command used**  
**What it does:** Installs the user’s SSH public key for the `debian` account.  
**Why it was used:** To restore key-based access after guest login was recovered.  
**Expected result:** SSH key authentication works to the VM.  
**Success indicates:** Passwordless login is possible.  
**Failure indicates:** File permissions, home ownership, or key format issue.  
**Risk:** Low.

## Command
```bash
mkdir -p /tmp/ci-100
cp /var/lib/vz/snippets/docker-userdata.yml /tmp/ci-100/user-data
printf 'instance-id: iid-%s\nlocal-hostname: docker\n' "$VMID-$(date +%s)" > /tmp/ci-100/meta-data
```

**What it does:** Stages NoCloud `user-data` and `meta-data` files for manual ISO creation.  
**Why it was used:** To bypass Proxmox’s failing cloud-init embed path.  
**Expected result:** Two plain-text files ready for inclusion in a `cidata` ISO.  
**Success indicates:** Manual NoCloud ISO creation can proceed.  
**Failure indicates:** Path or file-generation issue.  
**Risk:** Low.

## Command
```bash
genisoimage -quiet -output /var/lib/vz/template/iso/ci-100-userdata.iso -volid cidata -joliet -rock /tmp/ci-100/user-data /tmp/ci-100/meta-data
```

**Likely command used**  
**What it does:** Builds a NoCloud ISO labeled `cidata` from the staged user-data and meta-data files.  
**Why it was used:** To provide cloud-init inputs without relying on Proxmox `cicustom` embedding.  
**Expected result:** A bootable cloud-init ISO file containing `user-data` and `meta-data`.  
**Success indicates:** The guest can consume the YAML directly from the ISO.  
**Failure indicates:** Missing ISO tool or file path issue.  
**Risk:** Low.

## Command
```bash
mount -o loop /var/lib/vz/template/iso/ci-100-userdata.iso /mnt/ci
ls -lah /mnt/ci
umount /mnt/ci
```

**What they do:** Loop-mount the generated ISO, list its contents, and unmount it.  
**Why they were used:** To verify that `meta-data` and `user-data` actually made it into the ISO.  
**Expected result:** Both files are visible in the mounted ISO.  
**Success indicates:** Host-side ISO creation succeeded.  
**Failure indicates:** The ISO is empty or malformed.  
**Risk:** Low.

## Command
```bash
qm set 100 --delete ide2
qm set 100 --ide2 local:iso/ci-100-userdata.iso,media=cdrom
```

**What they do:** Remove the existing cloud-init CD and attach the manually built NoCloud ISO as the VM’s CDROM.  
**Why they were used:** To bypass Proxmox’s embedded cloud-init disk and present a known-good `cidata` ISO instead.  
**Expected result:** VM boots with the manual ISO attached on `ide2`.  
**Success indicates:** Cloud-init can read the attached NoCloud ISO directly.  
**Failure indicates:** ISO path or VM CD configuration issue.  
**Risk:** Medium if the wrong CD is detached or replaced.
