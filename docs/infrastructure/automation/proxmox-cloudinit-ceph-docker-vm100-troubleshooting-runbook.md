---
title: "Proxmox Cloud-Init Snippets, Ceph Disk Integration, and Docker VM Setup"
track: "infrastructure"
category: "automation"
type: "runbook"
logical_order: 30
date_rule: "Dates are removed from filenames, visible headings, indexes, generated metadata, and runbook body content."
---

# Proxmox Cloud-Init Snippets, Ceph Disk Integration, and Docker VM Setup

## Summary
Configured and troubleshot a Debian-based Docker VM (`VM 100`) on Proxmox using custom cloud-init snippets, Ceph RBD storage, NAS CIFS mounts, Docker Compose, and systemd automation.

The main issue was that the custom cloud-init `user-data` snippet (`docker-userdata.yml`) was not being applied, even though the network snippet worked and Proxmox could see the files in snippet storage.

## Environment
- **Platform:** Proxmox VE cluster
- **Primary node used:** `mainframe`
- **VM:** `100`, named `docker-testing` / intended hostname `debian-docker`
- **Guest OS:** Debian cloud image
- **Storage:**
  - `cephpool` - Ceph RBD storage for VM disks and cloud-init disk
  - `snips` - Proxmox directory storage for cloud-init snippets
- **Cloud-init files:**
  - `docker-userdata.yml`
  - `docker-net.yml`
- **Networking:**
  - VM NIC: `ens18`
  - Static target observed: `192.168.16.82/24`
  - Gateway/DNS: `192.168.16.1`
- **Docker-related services:**
  - Docker
  - Docker Compose plugin
  - Gluetun
  - qBittorrent VPN container
  - SABnzbd VPN container
  - Deluge VPN container
- **NAS mounts:**
  - `//192.168.16.21/Media` → `/srv/remotemount/NAS`
  - `//192.168.16.22/Public` → `/srv/remotemount/wontonsoup`

## Problem
Proxmox was not injecting the custom `docker-userdata.yml` cloud-init configuration into VM 100. The user-data file contained user creation, SSH key injection, package installation, CIFS mount configuration, Ceph disk formatting/mounting, Docker systemd overrides, and Gluetun restart timer logic.

The network snippet worked, but the user-data snippet repeatedly fell back to Proxmox defaults.

## Symptoms
- `qm cloudinit dump 100 user` repeatedly showed Proxmox-generated defaults instead of the custom YAML:

```yaml
#cloud-config
hostname: docker-testing
manage_etc_hosts: true
fqdn: docker-testing
chpasswd:
  expire: False
users:
  - default
package_upgrade: true
```

- `qm cloudinit dump 100 network` showed valid network output, meaning the network snippet was being processed.
- Inside the VM, cloud-init eventually reached `status: done`, but the expected user-data-driven disk setup was not applied.
- `/dev/sdb` existed as a 100 GB disk, but it had no filesystem and no mountpoint.
- `df -h | grep docker` produced no output.
- YAML syntax validation succeeded, so the issue was not basic YAML syntax.

## Actions Taken

### 1. Checked VM ID and corrected target VM
The troubleshooting initially referenced VM `102`, but the active target was corrected to **VM 100**.

### 2. Created and inspected `docker-userdata.yml`
The cloud-init user-data file was built to include:
- Debian user creation
- SSH key injection
- Hashed password
- Docker packages
- CIFS credentials
- NAS mounts
- Docker systemd dependency override
- Gluetun restart script, service, and timer
- Ceph RBD disk setup for Docker data

### 3. Generated a hashed password
A SHA-512 hash was generated for the `debian` user password and placed into the YAML under `passwd:`.

### 4. Confirmed snippet file contents and permissions
```bash
cat /var/lib/vz/snips/snippets/docker-userdata.yml
ls -l /var/lib/vz/snips/snippets/docker-userdata.yml
```

Purpose: verify that the expected YAML existed and was readable by Proxmox.

### 5. Validated YAML syntax
```bash
python3 -c 'import yaml,sys; yaml.safe_load(sys.stdin)' < /var/lib/vz/snips/snippets/docker-userdata.yml && echo "YAML OK"
```

Result: `YAML OK`.

### 6. Reworked Proxmox snippet storage layout
There was confusion caused by nested paths such as:

```text
/var/lib/vz/snippets/snippets/
/var/lib/vz/snips/snippets/
/var/lib/vz/snips/snippets/snippets/
```

The intended final storage definition became:

```ini
dir: snips
        path /var/lib/vz/snips
        content snippets
        shared 0
```

This means valid snippet files live at:

```text
/var/lib/vz/snips/snippets/docker-userdata.yml
/var/lib/vz/snips/snippets/docker-net.yml
```

### 7. Verified Proxmox could see the snippets
```bash
pvesm list snips
```

Confirmed output:

```text
Volid                              Format  Type      Size VMID
snips:snippets/docker-net.yml      snippet snippets   158
snips:snippets/docker-userdata.yml snippet snippets  3598
```

### 8. Reapplied `cicustom`
```bash
qm set 100 --cicustom "user=snips:snippets/docker-userdata.yml,network=snips:snippets/docker-net.yml"
qm cloudinit update 100
```

Purpose: attach both custom user-data and network-data snippets to VM 100 and regenerate the cloud-init ISO.

### 9. Checked VM config for `cicustom`
```bash
cat /etc/pve/nodes/mainframe/qemu-server/100.conf | grep cicustom
```

Confirmed:

```text
cicustom: user=snips:snippets/docker-userdata.yml,network=snips:snippets/docker-net.yml
```

### 10. Confirmed network-data was applied
```bash
qm cloudinit dump 100 network
```

Observed DHCP-style generated network output with DNS server `192.168.16.1`. Earlier VM-side checks also showed `192.168.16.82/24` assigned to `ens18`.

### 11. Confirmed user-data was still not applied
```bash
qm cloudinit dump 100 user
```

Still showed default Proxmox user-data rather than the custom YAML.

### 12. Added a dedicated Ceph RBD for Docker data
A separate 100 GB disk was planned for Docker state and compose stacks, intended as a VM-bound Ceph RBD named similar to:

```text
vm-100-docker-disk
```

This disk appeared in the VM as `/dev/sdb`:

```bash
lsblk
```

Observed:

```text
sdb  100G disk
```

### 13. Verified `/dev/sdb` had not been formatted or mounted
```bash
df -h | grep docker
lsblk -f | grep sdb
```

Findings:
- No `/var/lib/docker` mount appeared.
- `sdb` showed no filesystem metadata.

## Key Findings
- Proxmox could see both snippets via `pvesm list snips`.
- The VM config correctly referenced both snippets using `cicustom`.
- The network snippet worked.
- The user-data snippet did not work, even after YAML reordering and syntax validation.
- The problem was not simply file location, permissions, or YAML syntax.
- The custom user-data contained complex sections:
  - `write_files`
  - `fs_setup`
  - `mounts`
  - `runcmd`
  - systemd unit creation
- The likely operational conclusion was that the complex `user=` snippet was not being consumed as expected by Proxmox/cloud-init in this workflow.

## Resolution
The immediate issue was not fully resolved in the chat. The current status is:

- Snippet storage path is fixed.
- Proxmox can list the snippets.
- `cicustom` points to the correct files.
- Network snippet works.
- User-data snippet still falls back to defaults.

The recommended next design is to split the configuration:

1. **Minimal user-data snippet** for identity only:
   - user creation
   - SSH authorized key
   - password hash
   - sudo settings

2. **Separate setup/provisioning snippet or post-boot script** for complex host setup:
   - disk formatting
   - `/var/lib/docker` mount
   - `/opt/compose` bind mount
   - CIFS mounts
   - Docker systemd override
   - Gluetun timer/service

Possible next `cicustom` direction:

```bash
qm set 100 --cicustom "user=snips:snippets/docker-user.yml,network=snips:snippets/docker-net.yml"
```

Then apply advanced setup using either:
- `vendor=` cloud-init data if validated in Proxmox
- a first-boot script
- manual provisioning
- Ansible or another configuration management tool

## Validation
Validated items:

- VM cloud-init status completed:

```bash
sudo cloud-init status --long
```

Observed:

```text
status: done
DataSourceNoCloud [seed=/dev/sr0][dsmode=net]
```

- VM network applied:

```bash
ip a
```

Observed:

```text
ens18: inet 192.168.16.82/24
```

- Proxmox snippet storage recognized files:

```bash
pvesm list snips
```

- VM config contained expected `cicustom` mapping:

```bash
cat /etc/pve/nodes/mainframe/qemu-server/100.conf | grep cicustom
```

Failed validation:

- `qm cloudinit dump 100 user` still showed defaults.
- `/dev/sdb` was not formatted or mounted.
- `/var/lib/docker` was not backed by the Ceph RBD yet.

## Follow-Up Tasks
- Create a minimal `docker-user.yml` and test only user creation.
- Move complex setup into a separate file or script.
- Decide whether to use `vendor=` for advanced setup.
- Manually format and mount `/dev/sdb` if immediate Docker use is needed.
- Use UUID-based fstab entries instead of `/dev/sdb` for long-term reliability.
- Add logging to Gluetun restart script.
- Validate Docker service dependencies after mounts are working.
- Consider replacing Debian `docker.io` with Docker CE from Docker’s official repository.
- Consider Ansible for repeatable VM provisioning instead of increasingly large cloud-init YAML.

## Lessons Learned
- Proxmox snippet storage paths are easy to confuse. A storage path like `/var/lib/vz/snips` with `content snippets` expects files in `/var/lib/vz/snips/snippets/`.
- `pvesm list <storage>` is the best way to verify Proxmox can actually see snippets.
- `qm cloudinit dump` is useful, but behavior with complex custom user-data should be validated carefully.
- Keep cloud-init user-data minimal when troubleshooting.
- Separate identity, disk setup, mounts, and application bootstrap logic.
- Avoid relying on `/dev/sdb` long-term; use UUIDs after formatting.
- Docker data on a separate Ceph RBD is cleaner than storing it on the root disk.
- Bind mounting `/opt/compose` from the Docker data disk is valid, but should be documented clearly.

---

# Command Reference

## Command
```bash
qm set 100 --cicustom "user=snips:snippets/docker-userdata.yml,network=snips:snippets/docker-net.yml"
```

**What it does:** Sets custom cloud-init snippets for VM 100.

**Important arguments:**
- `user=...` points to the user-data YAML.
- `network=...` points to the network config YAML.
- `snips:` is the Proxmox storage ID.
- `snippets/...` is the content path inside the storage.

**Why it was used:** To make VM 100 consume custom cloud-init files instead of Proxmox defaults.

**Expected result:** VM config should show the `cicustom` line, and `qm cloudinit update 100` should include those snippets in the cloud-init ISO.

**Failure meaning:** If `qm cloudinit dump 100 user` still shows defaults, Proxmox is not applying the user-data snippet correctly.

---

## Command
```bash
qm cloudinit update 100
```

**What it does:** Regenerates the cloud-init disk/ISO for VM 100.

**Why it was used:** Required after changing `cicustom` or modifying snippet files.

**Expected result:** The VM’s cloud-init ISO reflects the latest snippets.

**Failure meaning:** Errors such as missing volume indicate the snippet path or storage config is wrong.

---

## Command
```bash
qm cloudinit dump 100 user
```

**What it does:** Dumps the effective user-data Proxmox generated for VM 100.

**Why it was used:** To verify whether custom `docker-userdata.yml` was being injected.

**Expected result:** The custom `#cloud-config` content should appear.

**Observed issue:** It kept showing default Proxmox content:

```yaml
users:
  - default
```

---

## Command
```bash
qm cloudinit dump 100 network
```

**What it does:** Dumps the generated cloud-init network configuration.

**Why it was used:** To verify `docker-net.yml` behavior separately from user-data.

**Result:** Network config appeared, confirming that at least the network snippet path was working.

---

## Command
```bash
cat /etc/pve/storage.cfg | grep -A5 snips
```

**What it does:** Shows the Proxmox storage definition for `snips`.

**Why it was used:** To confirm the storage root path and content type.

**Expected result:**

```ini
dir: snips
    path /var/lib/vz/snips
    content snippets
```

**Operational note:** If the path is `/var/lib/vz/snips`, snippet files must live under `/var/lib/vz/snips/snippets/`.

---

## Command
```bash
pvesm list snips
```

**What it does:** Lists volumes/files Proxmox recognizes on the `snips` storage.

**Why it was used:** To verify Proxmox could see `docker-userdata.yml` and `docker-net.yml`.

**Expected result:**

```text
snips:snippets/docker-net.yml
snips:snippets/docker-userdata.yml
```

**Failure meaning:** Empty output means files are in the wrong path or storage config is wrong.

---

## Command
```bash
cat /etc/pve/nodes/mainframe/qemu-server/100.conf | grep cicustom
```

**What it does:** Reads the VM config directly and filters for the `cicustom` line.

**Why it was used:** To confirm VM 100 was actually pointing at the intended snippet files.

**Expected result:**

```text
cicustom: user=snips:snippets/docker-userdata.yml,network=snips:snippets/docker-net.yml
```

---

## Command
```bash
python3 -c 'import yaml,sys; yaml.safe_load(sys.stdin)' < /var/lib/vz/snips/snippets/docker-userdata.yml && echo "YAML OK"
```

**What it does:** Uses Python’s YAML parser to validate basic YAML syntax.

**Why it was used:** To check whether syntax errors caused cloud-init rejection.

**Expected result:** `YAML OK`.

**Limit:** This only validates YAML syntax, not whether cloud-init supports every key or whether Proxmox will process it as expected.

---

## Command
```bash
ls -l /var/lib/vz/snips/snippets/
```

**What it does:** Lists snippet files in the final intended snippet directory.

**Why it was used:** To confirm files were present after moving/cleaning directories.

**Expected result:**

```text
docker-net.yml
docker-userdata.yml
```

---

## Command
```bash
rm -rf /var/lib/vz/snips/snippets/snippets
```

**What it does:** Deletes the duplicate nested `snippets` folder.

**Why it was used:** To clean up confusing duplicate directory structure.

**Risk:** High. `rm -rf` permanently deletes files and directories.

**Safer approach:** Always inspect first:

```bash
ls -l /var/lib/vz/snips/snippets/snippets/
```

---

## Command
```bash
sudo cloud-init status --long
```

**What it does:** Shows cloud-init status inside the VM.

**Why it was used:** To confirm whether cloud-init completed or failed.

**Expected result:**

```text
status: done
```

**Failure meaning:** `status: error` indicates a failed cloud-init module, often package install, network, mount, or script failure.

---

## Command
```bash
ip a
```

**What it does:** Shows network interfaces and assigned IP addresses inside the VM.

**Why it was used:** To verify cloud-init network configuration.

**Expected result:** `ens18` should have the expected IP address, such as `192.168.16.82/24`.

---

## Command
```bash
lsblk
```

**What it does:** Shows block devices inside the VM.

**Why it was used:** To confirm the Ceph RBD disk appeared as `/dev/sdb`.

**Expected result:** A 100 GB `sdb` disk should appear.

---

## Command
```bash
lsblk -f | grep sdb
```

**What it does:** Shows filesystem metadata for `/dev/sdb`.

**Why it was used:** To see whether the Docker disk was formatted.

**Expected result:** `ext4` filesystem shown if formatting succeeded.

**Observed result:** Only `sdb` appeared, meaning no filesystem was present.

---

## Command
```bash
df -h | grep docker
```

**What it does:** Checks whether any mounted filesystem includes `docker` in its path.

**Why it was used:** To confirm `/var/lib/docker` was mounted from the Ceph disk.

**Expected result:** A line showing `/var/lib/docker` mounted.

**Observed result:** No output, meaning Docker data disk was not mounted.

---

## Command
```bash
qm set 100 --scsi1 cephpool:100
```

**What it does:** Adds a new 100 GB disk from `cephpool` to VM 100 as `scsi1`.

**Why it was used:** To create a dedicated Ceph-backed Docker data disk.

**Expected result:** VM sees a new disk, usually `/dev/sdb`.

**Note:** Proxmox-managed disks typically use VM-associated naming such as `vm-100-disk-1`.

---

## Command
```bash
qm set 100 --scsi1 cephpool:vm-100-docker-disk
```

**What it does:** Attempts to attach a named Ceph RBD image to VM 100.

**Why it was discussed:** The user wanted a recognizable Docker data disk name.

**Important note:** Proxmox RBD naming and volume parsing can be strict. Generic names such as `docker-disk` may fail with parsing errors unless created and referenced in a Proxmox-compatible way.

---

## Command
```bash
rbd create cephpool/docker-disk --size 100G
```

**Likely command discussed.**

**What it does:** Creates a raw Ceph RBD image named `docker-disk` in pool `cephpool`.

**Why it was discussed:** To create a dedicated 100 GB Ceph block device for Docker.

**Caution:** A manually named RBD may not be managed by Proxmox the same way as VM-owned disks.

---

## Command
```bash
rbd create cephpool/vm-100-docker-disk --size 100G
```

**Likely command discussed.**

**What it does:** Creates a Ceph RBD image with VM-associated naming.

**Why it was preferred:** Better aligns with Proxmox VM ownership and lifecycle expectations.

---

## Command
```bash
mkfs.ext4 -L docker-disk /dev/sdb
```

**Likely manual fallback command discussed.**

**What it does:** Formats `/dev/sdb` as ext4 with label `docker-disk`.

**Why it would be used:** If cloud-init failed to format the Docker data disk.

**Risk:** Destructive. This erases all data on `/dev/sdb`.

---

## Command
```bash
sudo mount /dev/sdb /var/lib/docker
```

**Likely manual fallback command discussed.**

**What it does:** Mounts the Docker data disk onto `/var/lib/docker`.

**Why it would be used:** To make Docker use the Ceph-backed disk immediately.

**Caution:** Docker should be stopped before moving or replacing `/var/lib/docker`.
