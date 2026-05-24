---
title: "Runbook – Build Debian Docker VM (Proxmox + Ceph + Cloud-Init)"
track: "infrastructure"
category: "compute"
type: "runbook"
logical_order: 20
date_rule: "Dates are removed from filenames, visible headings, indexes, generated metadata, and runbook body content."
---

# Runbook – Build Debian Docker VM (Proxmox + Ceph + Cloud-Init)

## Summary
This runbook provisions a **Debian 12 Docker VM** on Proxmox with:

- Ceph-backed storage
- Dedicated Docker disk (`/dev/sdb` → `/var/lib/docker`)
- Bind mounts:
  - `/opt/docker-apps` → container appdata
  - `/opt/compose` → compose stacks
- CIFS NAS mounts aligned to host UID/GID
- Docker installed from the official Docker repository
- Proper permissions for Traefik and application stacks
- Optional static IP via cloud-init

Designed to be **idempotent and reproducible** for a homelab Docker host rebuild or migration.

---

## Environment

- **Hypervisor:** Proxmox VE
- **Storage backend:** Ceph RBD
- **Ceph pool:** `cephpool`
- **VM ID:** `100` example
- **VM name:** `debian-docker`
- **OS:** Debian 12 cloud image
- **Network:** `192.168.16.0/24`
- **Gateway / router:** OPNsense at `192.168.16.1`
- **Snippet storage:** `snips`, backed by CephFS
- **NAS CIFS mounts:**
  - `//192.168.16.21/Media` → `/srv/remotemount/NAS`
  - `//192.168.16.22/Public` → `/srv/remotemount/wontonsoup`
- **Primary Docker paths:**
  - `/var/lib/docker`
  - `/opt/docker-apps`
  - `/opt/compose`
- **Key containers / services:** Docker, Docker Compose, Traefik, Plex, Radarr, Sonarr, qBittorrent, SABnzbd, TubeArchivist, Gluetun

---

## Prerequisites

- Proxmox node has access to Ceph storage pool `cephpool`.
- Debian 12 generic cloud image is available.
- Proxmox snippet storage `snips` is configured and available cluster-wide.
- VM networking uses bridge `vmbr0`.
- NAS SMB shares are reachable from the Docker VM network.
- Old Docker appdata, if migrating, exists under `/DockerAppData` on the previous host.

---

## Procedure

### 1. Create the Base VM

Create the VM shell:

```bash
qm create 100 --name debian-docker --memory 8192 --cores 4 --net0 virtio,bridge=vmbr0
```

Import the Debian cloud image to Ceph:

```bash
qm importdisk 100 debian-12-genericcloud-amd64.qcow2 cephpool
```

Attach the boot disk and cloud-init drive:

```bash
qm set 100 --scsi0 cephpool:vm-100-disk-0
qm set 100 --boot order=scsi0
qm set 100 --scsihw virtio-scsi-pci
qm set 100 --ide2 cephpool:cloudinit
qm set 100 --serial0 socket --vga serial0
```

---

### 2. Add the Dedicated Docker Disk

Attach a 100 GB Ceph-backed disk for Docker data:

```bash
qm set 100 --scsi1 cephpool:100G
```

Expected VM disk layout:

```text
scsi0: 50G OS/root disk
scsi1: 100G Docker data disk
```

---

### 3. Create Cloud-Init Network Config

Use this for the static Docker VM IP. Replace the MAC address before applying.

Find the VM NIC MAC address:

```bash
qm config 100 | grep net0
```

Create `docker-net.yml`:

```bash
cat > /var/lib/vz/snips/snippets/docker-net.yml <<'NETEOF'
version: 2
renderer: networkd
ethernets:
  ens18:
    match:
      macaddress: aa:bb:cc:dd:ee:ff
    set-name: ens18
    dhcp4: no
    dhcp6: no
    addresses:
      - 192.168.16.3/24
    routes:
      - to: default
        via: 192.168.16.1
    nameservers:
      addresses:
        - 192.168.16.1
        - 1.1.1.1
NETEOF
```

---

### 4. Create Cloud-Init User Data

Create the main cloud-init config:

```bash
cat > /var/lib/vz/snips/snippets/docker-userdata.yml <<'USEREOF'
#cloud-config
hostname: debian-docker
manage_etc_hosts: true
ssh_pwauth: true

users:
  - name: debian
    groups: sudo
    shell: /bin/bash
    sudo: ALL=(ALL) NOPASSWD:ALL

package_update: false
packages:
  - qemu-guest-agent
  - cifs-utils
  - curl
  - gnupg
  - ca-certificates
  - lsb-release

bootcmd:
  - mkdir -p /var/lib/docker /srv/remotemount/NAS /srv/remotemount/wontonsoup /opt/compose /opt/docker-apps

fs_setup:
  - label: docker-disk
    filesystem: ext4
    device: /dev/sdb
    overwrite: true

mounts:
  - [ "/dev/sdb", "/var/lib/docker", "ext4", "defaults,nofail", "0", "2" ]
  - [ "//192.168.16.21/Media", "/srv/remotemount/NAS", "cifs", "credentials=/etc/smb-cred,rw,uid=1000,gid=1000,forceuid,forcegid,x-systemd.automount", "0", "0" ]
  - [ "//192.168.16.22/Public", "/srv/remotemount/wontonsoup", "cifs", "credentials=/etc/smb-cred,rw,uid=1000,gid=1000,forceuid,forcegid,x-systemd.automount", "0", "0" ]

write_files:
  - path: /etc/smb-cred
    permissions: '0600'
    content: |
      username=admin
      password=REPLACE_ME

runcmd:
  - mount /var/lib/docker
  - mkdir -p /var/lib/docker/appdata /var/lib/docker/compose
  - echo "/var/lib/docker/appdata /opt/docker-apps none bind 0 0" >> /etc/fstab
  - echo "/var/lib/docker/compose /opt/compose none bind 0 0" >> /etc/fstab
  - mount -a

  # Ownership
  - groupadd -f docker
  - chown -R debian:debian /var/lib/docker/appdata
  - chown -R debian:docker /var/lib/docker/compose

  # Permissions
  - chmod -R 2770 /var/lib/docker/appdata
  - chmod -R 2750 /var/lib/docker/compose

  # Docker official repository
  - install -m 0755 -d /etc/apt/keyrings
  - curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  - chmod a+r /etc/apt/keyrings/docker.gpg
  - echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian bookworm stable" > /etc/apt/sources.list.d/docker.list
  - apt-get update
  - apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

  # Docker group access
  - usermod -aG docker debian

  - systemctl enable docker
  - systemctl start docker
USEREOF
```

> **Security note:** Replace `REPLACE_ME` with the actual SMB password before deployment. Do not commit this snippet to a public repository with real credentials.

---

### 5. Attach Cloud-Init Config

Attach both the user-data and network snippets:

```bash
qm set 100 --cicustom "user=snips:snippets/docker-userdata.yml,network=snips:snippets/docker-net.yml"
qm cloudinit update 100
```

---

### 6. Start the VM

```bash
qm start 100
```

---

## Post-Deployment Validation

### Verify Cloud-Init

```bash
cloud-init status --long
```

Expected result:

```text
status: done
```

---

### Verify Disk and Mounts

```bash
lsblk -f
mount | egrep "docker|/opt|/srv"
```

Expected results:

- `/dev/sdb` formatted as ext4
- `/dev/sdb` mounted at `/var/lib/docker`
- `/opt/docker-apps` bind-mounted from `/var/lib/docker/appdata`
- `/opt/compose` bind-mounted from `/var/lib/docker/compose`
- NAS mounts available under `/srv/remotemount/*`

---

### Verify Docker

```bash
docker --version
systemctl status docker --no-pager
```

Expected results:

- Docker version prints successfully
- `docker.service` is active or starts successfully

---

### Verify Docker Group Access

```bash
id debian
ls -l /var/run/docker.sock
```

Expected results:

- `debian` is a member of the `docker` group
- Docker socket is owned by `root:docker`

If group membership was just added, log out and back in or run:

```bash
newgrp docker
```

---

## Data Migration Procedure

### Pull Appdata from Old Docker Host

Run this from the new VM:

```bash
sudo rsync -avz --partial --append-verify \
  -e "ssh -o ServerAliveInterval=60 -o ServerAliveCountMax=3 -o MACs=hmac-sha2-256" \
  root@192.168.16.3:/DockerAppData/ /opt/docker-apps/
```

---

### Validate File Count

```bash
ssh root@192.168.16.3 "find /DockerAppData -type f | wc -l"
sudo find /opt/docker-apps -type f | wc -l
```

Expected result: counts match.

---

### Validate With Checksum Dry Run

```bash
sudo rsync -avcn --delete \
  -e "ssh -o ServerAliveInterval=60 -o ServerAliveCountMax=3 -o MACs=hmac-sha2-256" \
  root@192.168.16.3:/DockerAppData/ /opt/docker-apps/
```

Expected result: no output listing changed files.

---

## Compose File Cleanup

### Update PUID/PGID to 1000

Run this from the new VM:

```bash
sudo bash -c 'find /opt/compose -type f \( -iname "*.yml" -o -iname "*.yaml" -o -name ".env" -o -iname "*.env" \) -print0 \
| xargs -0 sed -ri.bak \
  -e "s/PUID=[0-9]+/PUID=1000/g" \
  -e "s/PGID=[0-9]+/PGID=1000/g" \
  -e "s/PUID:\s*[\"\047]?[0-9]+[\"\047]?/PUID: 1000/g" \
  -e "s/PGID:\s*[\"\047]?[0-9]+[\"\047]?/PGID: 1000/g"'
```

---

### Verify PUID/PGID Updates

```bash
grep -RniE 'P(G|U)ID[:=]' /opt/compose | head -50
```

---

### Remove Backup Files After Verification

```bash
sudo find /opt/compose -type f -name "*.bak" -delete
```

---

## Traefik Permissions

### Fix `acme.json`

```bash
sudo chmod 600 /opt/docker-apps/Traefik/config/acme.json
```

Expected result: Traefik can safely read and write ACME certificate data.

---

## Cutover Checklist

Before switching the new VM to `192.168.16.3`:

- [ ] Stop Docker containers on the old host.
- [ ] Run final rsync from old host to new host.
- [ ] Shut down old host or remove its `.3` address.
- [ ] Boot or reconfigure new VM with `192.168.16.3`.
- [ ] Send gratuitous ARP from new VM:

```bash
sudo arping -A -c 3 -I ens18 192.168.16.3
```

- [ ] Validate Traefik routes.
- [ ] Validate app UIs.
- [ ] Validate NAS-backed paths.

---

## Follow-Up Tasks

- Convert compose files to shared `.env` variables.
- Remove obsolete `version:` keys from compose files.
- Review permissions per special-case app, especially databases and Elasticsearch/Redis-backed apps.
- Add healthchecks and restart policies.
- Create backup job for `/opt/docker-apps` and `/opt/compose`.
- Monitor disk usage on `/var/lib/docker`.
- Validate Traefik TLS renewal after cutover.

---

# Command Reference

## Command
```bash
qm create 100 --name debian-docker --memory 8192 --cores 4 --net0 virtio,bridge=vmbr0
```
Creates a new Proxmox VM shell. The VM is assigned ID `100`, given the name `debian-docker`, 8 GB RAM, 4 vCPUs, and a VirtIO NIC attached to `vmbr0`.

---

## Command
```bash
qm importdisk 100 debian-12-genericcloud-amd64.qcow2 cephpool
```
Imports the Debian cloud image into Proxmox storage. In this runbook, the target storage is the Ceph RBD pool `cephpool`.

---

## Command
```bash
qm set 100 --scsi1 cephpool:100G
```
Adds a second 100 GB Ceph-backed disk to VM `100`. This disk is expected to appear inside Debian as `/dev/sdb` and is used for Docker data.

---

## Command
```bash
qm set 100 --cicustom "user=snips:snippets/docker-userdata.yml,network=snips:snippets/docker-net.yml"
```
Attaches custom cloud-init user-data and network-data snippets. The `snips` storage must be available on the Proxmox node where the VM boots.

---

## Command
```bash
qm cloudinit update 100
```
Regenerates the cloud-init ISO for VM `100` after snippet changes.

---

## Command
```bash
cloud-init status --long
```
Shows whether cloud-init completed successfully. `status: done` indicates successful completion; `status: error` means logs should be reviewed.

---

## Command
```bash
lsblk -f
```
Lists disks, filesystems, labels, UUIDs, and mountpoints. Used to verify that `/dev/sdb` is formatted and mounted correctly.

---

## Command
```bash
mount | egrep "docker|/opt|/srv"
```
Filters mounted filesystems to Docker, bind mounts, and NAS mounts.

---

## Command
```bash
sudo rsync -avz --partial --append-verify -e "ssh -o ServerAliveInterval=60 -o ServerAliveCountMax=3 -o MACs=hmac-sha2-256" root@192.168.16.3:/DockerAppData/ /opt/docker-apps/
```
Copies appdata from the old Docker host to the new host.

- `-a`: archive mode, preserves timestamps, permissions, symlinks, and ownership where possible
- `-v`: verbose output
- `-z`: compression
- `--partial`: keeps partially transferred files
- `--append-verify`: resumes partially transferred files and verifies them
- `-e ssh`: uses SSH transport
- SSH keepalive and MAC options help reduce transfer failures in unstable connections

---

## Command
```bash
sudo rsync -avcn --delete root@192.168.16.3:/DockerAppData/ /opt/docker-apps/
```
Performs a checksum-based dry-run comparison.

- `-c`: compare file contents by checksum
- `-n`: dry-run, do not write changes
- `--delete`: detects files present on destination but missing from source

No output means the source and destination are effectively synchronized.

---

## Command
```bash
sudo bash -c 'find /opt/compose -type f \( -iname "*.yml" -o -iname "*.yaml" -o -name ".env" -o -iname "*.env" \) -print0 | xargs -0 sed -ri.bak -e "s/PUID=[0-9]+/PUID=1000/g" -e "s/PGID=[0-9]+/PGID=1000/g" -e "s/PUID:\s*[\"\047]?[0-9]+[\"\047]?/PUID: 1000/g" -e "s/PGID:\s*[\"\047]?[0-9]+[\"\047]?/PGID: 1000/g"'
```
Updates PUID and PGID values across compose and environment files.

- Uses `find` to discover YAML and env files
- Uses `sed` with extended regex
- Creates `.bak` backups
- Handles both `PUID=500` style and `PUID: "500"` style

---

## Command
```bash
sudo chmod 600 /opt/docker-apps/Traefik/config/acme.json
```
Sets strict permissions for Traefik's ACME certificate file. This is required because `acme.json` contains TLS private key material.

---

## Command
```bash
sudo arping -A -c 3 -I ens18 192.168.16.3
```
Sends gratuitous ARP after IP cutover so switches, hosts, and the router update their ARP caches for the new VM.
