---
title: "Homelab Runbook: Proxmox Cloud-Init Snippets, Ceph RBD Docker Disk, and Docker/NAS Integration"
track: "infrastructure"
category: "automation"
type: "runbook"
logical_order: 20
date_rule: "Dates are removed from filenames, visible headings, indexes, generated metadata, and runbook body content."
---

# Homelab Runbook: Proxmox Cloud-Init Snippets, Ceph RBD Docker Disk, and Docker/NAS Integration

## Scope

This document summarizes a troubleshooting and configuration session for VM 100, a Debian Docker VM in a Proxmox/Ceph homelab. The work focused on Proxmox Cloud-Init custom snippets, Ceph-backed Cloud-Init media, a dedicated Ceph RBD disk for Docker data, SMB NAS mounts, Docker service ordering, and Gluetun container restart automation.

Dates are based on timestamps visible in command output where possible. Where the exact work-session date was not directly available, the date is marked as approximate and tied to observed file or Cloud-Init timestamps.

---

# VM 100 Cloud-Init Snippet Path and User-Data Validation

## Summary

Troubleshot Proxmox Cloud-Init user-data for VM 100 after custom YAML was not being applied as expected. The main focus was getting `docker-userdata.yml` and `docker-net.yml` into the correct Proxmox snippets storage path, attaching them with `cicustom`, regenerating the Cloud-Init ISO, and proving that the custom user-data was actually present in the Cloud-Init disk.

## Environment

- Proxmox node: `mainframe`
- VM: `100`
- VM name observed: `docker-testing`
- Guest hostname target: `debian-docker`
- Guest OS: Debian cloud image
- Proxmox Cloud-Init datasource: NoCloud via `/dev/sr0`
- Snippet storage:
  - Storage ID: `snips`
  - Earlier path observed: `/var/lib/vz/snippets`
  - Later corrected path: `/var/lib/vz/snips`
- Ceph RBD pool: `cephpool`
- Cloud-Init disk: `vm-100-cloudinit`
- Network:
  - VM MAC: `bc:24:11:9f:fa:e9`
  - Intended/static IP seen later: `192.168.16.82/24`

## Problem

VM 100 was not consistently receiving custom Cloud-Init user-data from `docker-userdata.yml`. Proxmox output often showed default generated user-data instead of the custom YAML.

## Symptoms

Proxmox repeatedly showed default Cloud-Init user-data:

```bash
qm cloudinit dump 100 user
```

Observed output:

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

Earlier, `qm set` against the wrong VM ID also failed:

```bash
qm set 102 --delete cicustom
qm cloudinit update 102
```

Observed error:

```text
Configuration file 'nodes/mainframe/qemu-server/102.conf' does not exist
```

This clarified that the target VM was VM 100, not VM 102.

## Actions Taken

Verified available Proxmox storages:

```bash
pvesm status
```

Checked the `snips` storage definition:

```bash
cat /etc/pve/storage.cfg | grep -A5 snips
```

Created and edited `docker-userdata.yml`, including:

- `debian` user
- SSH public key
- hashed password
- `qemu-guest-agent`
- `docker.io`

Applied the custom user-data snippet:

```bash
qm set 100 --cicustom "user=snips:snippets/docker-userdata.yml"
qm cloudinit update 100
```

Verified file permissions:

```bash
ls -l /var/lib/vz/snippets/docker-userdata.yml
```

Cleared leftover Proxmox-generated Cloud-Init fields:

```bash
qm set 100 --delete ciuser --delete cipassword --delete sshkeys
```

Moved Cloud-Init disk between storages during testing:

```bash
qm set 100 --delete ide2
qm set 100 --ide2 snips:cloudinit
```

This produced a storage capability issue later because `snips` did not support image content.

Moved Cloud-Init disk back to Ceph for HA-safe storage:

```bash
qm set 100 --delete ide2
qm set 100 --ide2 cephpool:cloudinit
qm cloudinit update 100
```

Mapped and mounted the Ceph RBD Cloud-Init disk to inspect its actual contents:

```bash
rbd ls cephpool | grep vm-100-cloudinit
rbd map cephpool/vm-100-cloudinit
rbd device list
mkdir -p /mnt/ci-test
mount /dev/rbd0 /mnt/ci-test
ls -l /mnt/ci-test
cat /mnt/ci-test/user-data
```

After validation, the expected cleanup was:

```bash
umount /mnt/ci-test
rbd unmap /dev/rbd0
```

Inside the VM, Cloud-Init was validated with:

```bash
getent passwd debian
cat /home/debian/.ssh/authorized_keys
sudo cloud-init status --long
```

## Key Findings

- VM 102 did not exist on `mainframe`; the correct VM was VM 100.
- Proxmox stores VM configs under:

  ```text
  /etc/pve/nodes/<node>/qemu-server/<vmid>.conf
  ```

- Cloud-Init snippets must be located under the `snippets/` subfolder of the Proxmox storage root.
- If storage `snips` has:

  ```text
  path /var/lib/vz/snips
  content snippets
  ```

  then snippet files must live in:

  ```text
  /var/lib/vz/snips/snippets/
  ```

  and be referenced as:

  ```text
  snips:snippets/<file>.yml
  ```

- The Cloud-Init drive `ide2` is not a normal uploaded ISO. It is a small Proxmox-generated disk/image presented to the guest as a CD-ROM.
- A storage used for `ide2` must support VM disk images. A storage configured only for `snippets` cannot hold the Cloud-Init disk.
- For HA/live migration, the Cloud-Init disk should stay on shared storage such as Ceph RBD.
- `qm cloudinit dump` may show Proxmox-generated defaults and may not always be sufficient proof of what is inside the generated Cloud-Init disk when custom snippets are involved.
- Inspecting the mounted Cloud-Init RBD directly showed the custom `user-data` file was present.

## Resolution

The custom Cloud-Init user-data was confirmed by directly mounting the Ceph RBD-backed Cloud-Init disk and reading:

```bash
cat /mnt/ci-test/user-data
```

The VM also confirmed that Cloud-Init applied core user-data by showing:

```text
debian:x:1000:1000:Debian:/home/debian:/bin/bash
```

and the expected SSH key in:

```text
/home/debian/.ssh/authorized_keys
```

## Validation

Inside the VM:

```bash
sudo cloud-init status --long
```

showed:

```text
status: done
DataSourceNoCloud [seed=/dev/sr0][dsmode=net]
```

The `debian` user existed and the SSH public key was present.

## Follow-Up Tasks

- Keep Cloud-Init user-data, network config, and heavier setup logic modular to reduce YAML complexity.
- Prefer validating the actual Cloud-Init disk contents if `qm cloudinit dump` appears misleading.
- Keep Cloud-Init `ide2` on shared Ceph storage for HA-safe migration.
- Avoid placing the Cloud-Init disk on a snippets-only storage unless that storage also supports `images`.

## Lessons Learned

- Always confirm the target VM ID before applying `qm` commands.
- `pvesm list <storage>` is the best first check to confirm Proxmox recognizes snippets.
- Snippet storage path design matters; avoid confusing nested paths such as `snippets/snippets` unless intentionally configured.
- For Proxmox HA, all VM disks, including Cloud-Init media, should live on shared storage.

---

# Snips Storage Reorganization and Snippet Visibility Fix

## Summary

Reorganized the dedicated Cloud-Init snippets storage to use a clearer path under `/var/lib/vz/snips`, moved YAML files into the correct `snippets/` subfolder, and verified Proxmox could list both Cloud-Init YAML files.

## Environment

- Proxmox node: `mainframe`
- Storage ID: `snips`
- Final storage path:

  ```text
  /var/lib/vz/snips
  ```

- Final YAML location:

  ```text
  /var/lib/vz/snips/snippets/
  ```

- Snippet files:
  - `docker-userdata.yml`
  - `docker-net.yml`

## Problem

Proxmox could not find snippet volumes after the storage path was changed. Running Cloud-Init update produced errors such as:

```text
volume 'snips:snippets/docker-net.yml' does not exist
```

Another attempted reference produced:

```text
unable to parse directory volume name 'docker-net.yml'
```

## Symptoms

`pvesm list snips` initially showed no snippet files:

```bash
pvesm list snips
```

Observed output:

```text
Volid Format  Type      Size VMID
```

The YAML files existed on disk, but Proxmox did not recognize them as snippet content.

## Actions Taken

Checked current storage config:

```bash
cat /etc/pve/storage.cfg | grep -A5 snips
```

Final correct config observed:

```text
dir: snips
        path /var/lib/vz/snips
        content snippets
        shared 0
```

Checked YAML location:

```bash
ls -l /var/lib/vz/snips/snippets/
```

Observed files:

```text
docker-net.yml
docker-userdata.yml
```

Verified Proxmox now recognizes the snippets:

```bash
pvesm list snips
```

Observed output:

```text
Volid                              Format  Type      Size VMID
snips:snippets/docker-net.yml      snippet snippets   158
snips:snippets/docker-userdata.yml snippet snippets  3598
```

Reattached snippets to VM 100:

```bash
qm set 100 --cicustom "user=snips:snippets/docker-userdata.yml,network=snips:snippets/docker-net.yml"
qm cloudinit update 100
```

## Key Findings

- With `path /var/lib/vz/snips`, Proxmox expects snippet files under:

  ```text
  /var/lib/vz/snips/snippets/
  ```

- The correct `cicustom` references are:

  ```text
  user=snips:snippets/docker-userdata.yml
  network=snips:snippets/docker-net.yml
  ```

- Referencing `snips:docker-net.yml` is invalid because Proxmox expects the content-type subpath `snippets/`.
- `pvesm list snips` returning the two YAML files confirmed the storage and file layout were correct.

## Resolution

The `snips` storage path was confirmed as:

```text
/var/lib/vz/snips
```

and the YAML files were placed under:

```text
/var/lib/vz/snips/snippets/
```

Proxmox successfully listed them via `pvesm list snips`.

## Validation

Successful `pvesm list snips` output showed both expected snippet volumes:

```text
snips:snippets/docker-net.yml
snips:snippets/docker-userdata.yml
```

## Follow-Up Tasks

- Remove leftover old snippet folders only after confirming they are not referenced.
- Keep future snippet paths standardized under `/var/lib/vz/snips/snippets/`.
- Use `pvesm list snips` before troubleshooting Cloud-Init content.

## Lessons Learned

- The Proxmox storage path is the storage root; snippet files must still be inside a `snippets/` subdirectory beneath that root.
- Do not guess `cicustom` paths. Verify with `pvesm list`.
- Storage path cleanup is safer when done in small steps: create, move, verify, then delete old folders.

---

# Dedicated 100 GB Ceph RBD Disk for Docker Data

## Summary

Designed a separate Ceph RBD disk for Docker data and Docker Compose files so the VM root disk remains clean and Docker state is stored on HA-capable Ceph-backed storage.

## Environment

- VM: 100
- Root disk: `scsi0` on `cephpool`
- Intended Docker data disk: 100 GB Ceph RBD
- Intended disk name: `vm-100-docker-disk`
- Guest disk device observed: `/dev/sdb`
- Intended mount points:
  - `/var/lib/docker`
  - `/opt/compose`

## Problem

The VM had a new 100 GB disk visible as `/dev/sdb`, but Docker was not using it because the disk was raw, unformatted, and unmounted.

## Symptoms

Inside the VM:

```bash
df -h | grep docker
lsblk -f | grep sdb
```

Output only showed:

```text
sdb
```

`lsblk` showed:

```text
sdb       8:16   0  100G  0 disk
```

No filesystem or mountpoint was present.

## Actions Taken

Discussed using a separate RBD instead of placing Docker data on the existing root RBD.

Attempted generic RBD naming:

```bash
qm set 100 --scsi1 cephpool:docker-disk
```

This failed with:

```text
unable to parse rbd volume name 'docker-disk'
```

Identified that Proxmox VM disks should follow a Proxmox-friendly naming convention, such as:

```text
vm-100-docker-disk
```

cloud-Init sections for disk setup:

```yaml
fs_setup:
  - label: docker-disk
    filesystem: ext4
    device: /dev/sdb
    overwrite: true
```

and mounts:

```yaml
mounts:
  - [ "/dev/sdb", "/var/lib/docker", "ext4", "defaults,nofail", "0", "2" ]
  - [ "/var/lib/docker/compose", "/opt/compose", "none", "bind,nofail", "0", "0" ]
```

## Key Findings

- A separate Ceph RBD for Docker data is better than using the root disk because:
  - Docker images, logs, and volumes cannot fill the OS disk.
  - Docker data can be snapshotted or restored separately.
  - The OS VM can be rebuilt while retaining Docker data.
  - The VM remains HA-safe because the disk is on Ceph.
- The disk appears inside the VM as `/dev/sdb`, but it must be formatted and mounted before Docker uses it.
- The current VM showed `/dev/sdb` but no filesystem, meaning the Cloud-Init disk setup had not applied yet.
- Mounting `/var/lib/docker/compose` to `/opt/compose` with a bind mount gives a convenient human-friendly path while storing data on the Ceph Docker disk.

## Resolution

The target architecture was defined, but the disk still needed to be formatted and mounted inside the VM or via successful Cloud-Init reapplication.

## Validation

Inside the VM, `/dev/sdb` was visible:

```text
sdb       8:16   0  100G  0 disk
```

But validation also showed the disk was not yet active for Docker:

```bash
df -h | grep docker
```

returned no result.

## Follow-Up Tasks

- Create or attach the correctly named RBD:

  ```bash
  rbd create cephpool/vm-100-docker-disk --size 100G
  qm set 100 --scsi1 cephpool:vm-100-docker-disk
  ```

- Format and mount `/dev/sdb` manually if Cloud-Init does not apply:

  ```bash
  sudo mkfs.ext4 -L docker-disk /dev/sdb
  sudo mkdir -p /var/lib/docker
  sudo mount /dev/sdb /var/lib/docker
  ```

- Add persistent `/etc/fstab` entries or fix Cloud-Init so `fs_setup` and `mounts` apply.
- Stop Docker before moving existing Docker data.
- Consider using UUID-based mounts instead of `/dev/sdb` for long-term safety.

## Lessons Learned

- Ceph RBD only provides the block device; the guest OS still needs a filesystem and mount configuration.
- Device names such as `/dev/sdb` can be convenient but are less robust than UUIDs.
- A dedicated Docker disk is cleaner and safer than storing Docker state on the root filesystem.

---

# SMB NAS Mounts and Docker Service Ordering

## Summary

Designed Cloud-Init configuration to mount two SMB shares and make Docker wait for NAS-backed media paths before starting. This prevents containers from writing into empty local directories when NAS mounts are unavailable.

## Environment

- NAS Media server: `192.168.16.21`
- NAS Media share: `Media`
- Wontonsoup server: `192.168.16.22`
- Wontonsoup share: `Public`
- Credentials file: `/etc/smb-cred`
- Mount points:
  - `/srv/remotemount/NAS`
  - `/srv/remotemount/wontonsoup`
- Docker service override:
  - `/etc/systemd/system/docker.service.d/override.conf`

## Problem

Docker containers using bind mounts under `/srv/remotemount/...` could start before SMB shares were mounted. This could cause apps to see empty folders and potentially write data locally instead of to the NAS.

## Symptoms

The issue was preventive/design-focused rather than caused by a current failure. The risk was identified from Docker Compose paths such as:

```text
/srv/remotemount/NAS/Library/TV
/srv/remotemount/NAS/Downloaders/qBittorrent/downloads
/srv/remotemount/wontonsoup/Downloaders/deluge/downloads
```

## Actions Taken

Added Cloud-Init `write_files` entry for SMB credentials:

```yaml
write_files:
  - path: /etc/smb-cred
    permissions: '0600'
    owner: root:root
    content: |
      username=admin
      password=<redacted>
```

Added mountpoint creation:

```yaml
bootcmd:
  - mkdir -p /srv/remotemount/NAS
  - mkdir -p /srv/remotemount/wontonsoup
```

Added CIFS mounts:

```yaml
mounts:
  - [ "//192.168.16.21/Media", "/srv/remotemount/NAS", "cifs", "credentials=/etc/smb-cred,rw,iocharset=utf8,vers=3.0,nofail,uid=500,gid=1000,x-systemd.automount", "0", "0" ]
  - [ "//192.168.16.22/Public", "/srv/remotemount/wontonsoup", "cifs", "credentials=/etc/smb-cred,rw,iocharset=utf8,vers=3.0,nofail,uid=500,gid=1000,x-systemd.automount", "0", "0" ]
```

Designed Docker systemd override:

```ini
[Unit]
Requires=srv-remotemount-NAS.mount srv-remotemount-wontonsoup.mount var-lib-docker.mount
After=srv-remotemount-NAS.mount srv-remotemount-wontonsoup.mount var-lib-docker.mount
BindsTo=srv-remotemount-NAS.mount srv-remotemount-wontonsoup.mount var-lib-docker.mount
```

## Key Findings

- Systemd converts mount paths into unit names:
  - `/srv/remotemount/NAS` → `srv-remotemount-NAS.mount`
  - `/srv/remotemount/wontonsoup` → `srv-remotemount-wontonsoup.mount`
  - `/var/lib/docker` → `var-lib-docker.mount`
- `Requires` and `After` make Docker wait for mounts before starting.
- `BindsTo` ties Docker’s lifecycle to the mounts; if a mount disappears, Docker is stopped.
- Binding Docker daemon to NAS mounts is simple but heavy-handed because all containers are affected.
- A more granular future approach would be to bind individual Compose stacks to only the mounts they require.

## Resolution

A Cloud-Init-managed Docker override was drafted so Docker starts only after required storage is available.

## Validation

Expected validation commands inside the VM:

```bash
systemctl cat docker.service
mount | grep remotemount
df -h | grep remotemount
```

## Follow-Up Tasks

- Verify the generated Docker override exists after Cloud-Init runs.
- Consider stack-level systemd units for Compose services to avoid stopping all Docker containers when one NAS share drops.
- Consider adding `x-systemd.idle-timeout` or `_netdev` for more explicit network filesystem behavior.

## Lessons Learned

- Docker Compose `depends_on` does not wait for host mounts.
- Host mount readiness belongs to systemd/fstab, not Docker Compose.
- `BindsTo` is powerful but should be used carefully because it can stop Docker when a mount drops.

---

# Docker Compose Storage and Gluetun Restart Automation

## Summary

Discussed how to store Docker Compose stacks and how to automate Gluetun-related container restarts. The final design favored storing Compose stacks on the dedicated Ceph-backed Docker disk and using a systemd timer to periodically run a Gluetun restart script.

## Environment

- Docker VM: VM 100
- Docker Compose path: `/opt/compose`
- Docker data path: `/var/lib/docker`
- Gluetun container: `gluetun`
- Gluetun-dependent containers:
  - `qbittorrent-vpn`
  - `sabnzbd-vpn`
  - `deluge-vpn`
- Script path:
  - `/usr/local/bin/restart_gluetun_docker_containers.sh`
- Systemd service:
  - `restart-gluetun-docker.service`
- Systemd timer:
  - `restart-gluetun-docker.timer`

## Problem

VPN-dependent Docker containers may start too early or become unhealthy after boot. A recurring restart mechanism was desired to refresh Gluetun and dependent containers.

## Symptoms

This was a preventive reliability improvement rather than a confirmed failure during the session.

## Actions Taken

Reviewed an existing script pattern:

```bash
#!/bin/bash

CONTAINER_NAMES="gluetun qbittorrent-vpn sabnzb-vpn deluge-vpn"

sleep 600

for container in $CONTAINER_NAMES; do
    docker restart "$container"
done
```

Corrected container naming in later designs to:

```text
sabnzbd-vpn
```

Designed a systemd service:

```ini
[Unit]
Description=Restart Gluetun Docker Containers
After=docker.service
Requires=docker.service

[Service]
Type=simple
ExecStart=/usr/local/bin/restart_gluetun_docker_containers.sh

[Install]
WantedBy=multi-user.target
```

Designed a systemd timer:

```ini
[Unit]
Description=Restart Gluetun Docker Containers Timer

[Timer]
OnBootSec=10min
OnUnitActiveSec=10min

[Install]
WantedBy=timers.target
```

Discussed healthchecks and Autoheal but deferred Docker-level healthcheck/Autoheal work for later.

## Key Findings

- A systemd timer is cleaner than embedding `sleep 600` directly in an always-running service.
- `OnBootSec=10min` delays first execution until 10 minutes after boot.
- `OnUnitActiveSec=10min` repeats execution 10 minutes after the service last ran.
- A healthcheck-based restart script would be less disruptive than restarting containers every 10 minutes, but the timer-only approach was kept for now.
- `/usr/local/bin` is a typical Linux location for administrator-created scripts.

## Resolution

A Cloud-Init-managed systemd script/service/timer design was created to restart Gluetun-related containers after boot and then repeatedly every 10 minutes.

## Validation

Expected checks:

```bash
systemctl status restart-gluetun-docker.timer
systemctl list-timers | grep gluetun
journalctl -u restart-gluetun-docker.service
```

## Follow-Up Tasks

- Replace fixed periodic restarts with healthcheck-triggered restarts later.
- Add Docker Compose healthchecks for Gluetun and dependent apps.
- Consider adding an Autoheal container later.
- Ensure all container names in the script exactly match Compose `container_name` values.

## Lessons Learned

- Systemd timers are better than long-running sleep scripts for scheduled tasks.
- Restarting VPN containers every 10 minutes can cause brief service interruptions.
- Healthcheck-driven remediation is cleaner than blind periodic restarts.

---

# Docker Compose Stack Review: Plex and Gluetun Stacks

## Summary

Reviewed existing Docker Compose stacks for Plex-related services and VPN-protected downloader services. The focus was on Traefik exposure, host port usage, mount dependencies, and Gluetun network design.

## Environment

- Reverse proxy: Traefik
- Traefik domain examples:
  - `plex.dulynoted.cloud`
  - `overseerr.dulynoted.cloud`
  - `tautulli.dulynoted.cloud`
  - `qbit.dulynoted.cloud`
  - `deluge.dulynoted.cloud`
  - `sabnzbd.dulynoted.cloud`
- Docker network reference: `traefik-proxy`
- Media stack:
  - Plex
  - PlexAutoSkip
  - Overseerr
  - Tautulli
  - Intro Editor for Plex
  - Plex Meta Manager
- Downloader/VPN stack:
  - Gluetun
  - qBittorrent
  - Deluge
  - SABnzbd

## Problem

Stacks were being migrated to the new Docker VM/storage design. The user wanted advice on whether current Compose patterns were appropriate.

## Symptoms

No failure was being debugged directly in this section. The review identified potential reliability and exposure risks.

## Actions Taken

Reviewed Plex Compose stack and identified:

- Plex direct ports published to host.
- Other web apps also published with `ports:` while also routed through Traefik.
- Media paths depended on `/srv/remotemount/...`.
- Plex used `/tmp` for transcode.
- Plex used `/dev/dri` for hardware acceleration.

Reviewed Gluetun stack and identified:

- Downloader containers used:

  ```yaml
  network_mode: service:gluetun
  ```

- Traefik labels were attached to Gluetun, which is correct when apps share Gluetun’s network namespace.
- Many ports were published on Gluetun for qBittorrent, Deluge, and SABnzbd.
- Generic healthchecks used outbound connectivity checks.

## Key Findings

- Plex can reasonably keep some direct host ports for LAN clients and Plex discovery.
- Web apps such as Overseerr and Tautulli do not usually need direct host ports if Traefik handles HTTPS routing.
- When containers use `network_mode: service:gluetun`, Traefik labels often need to be attached to Gluetun because the child containers share Gluetun’s network stack.
- `depends_on` controls container startup order, not host mount readiness.
- Host storage readiness should be handled by systemd/fstab, not Compose alone.
- Refactoring means reorganizing config for maintainability without changing behavior, such as moving Traefik labels closer to the logical service where possible.

## Resolution

No Compose stack was rewritten during this session. The design recommendations were:

- Keep Docker daemon storage on Ceph.
- Keep media mounts under `/srv/remotemount/...`.
- Let systemd handle host mount readiness.
- Later consider stack-level systemd units instead of binding the entire Docker daemon to mounts.
- Later improve Traefik/Gluetun label organization and healthchecks.

## Validation

Not yet performed. Future validation should include:

```bash
docker compose config
docker compose up -d
docker ps
docker network inspect traefik-proxy
```

## Follow-Up Tasks

- Refactor Traefik labels later.
- Decide which services need direct host ports.
- Add service-specific healthchecks.
- Add `curl` to images/scripts that require healthchecks.
- Confirm hardware acceleration works after migration.

## Lessons Learned

- Traefik-only exposure reduces attack surface for web apps.
- Plex is a special case because LAN clients and discovery may need direct ports.
- Gluetun network namespace sharing changes where Traefik labels should live.
- Compose handles container dependencies; systemd handles host dependencies.

---

# Command Reference

## `qm set 102 --delete cicustom`
```bash
qm set 102 --delete cicustom
```

Removes the `cicustom` setting from VM 102. It failed because VM 102 did not exist on `mainframe`.

- `qm set`: modifies a VM config.
- `102`: target VM ID.
- `--delete cicustom`: removes the custom Cloud-Init snippet mapping.
- Expected result: VM config updates if VM exists.
- Failure indicates the VM ID is wrong or the VM config is not on that node.

Risk: Low, but removing `cicustom` can cause a VM to fall back to Proxmox-generated Cloud-Init defaults.

---

## `qm cloudinit update 102`
```bash
qm cloudinit update 102
```

Regenerates the Cloud-Init disk for VM 102. It failed because VM 102 did not exist.

- Used to rebuild the Cloud-Init ISO/disk after changing config.
- Failure indicates wrong VM ID or missing config.

---

## `qm set 100 --cicustom ...`
```bash
qm set 100 --cicustom "user=snips:snippets/docker-userdata.yml,network=snips:snippets/docker-net.yml"
```

Attaches custom Cloud-Init user-data and network snippets to VM 100.

- `user=` points to Cloud-Init user-data.
- `network=` points to Cloud-Init network config.
- `snips:` is the Proxmox storage ID.
- `snippets/<file>.yml` is the volume path under the storage root.

Expected result: VM config contains the `cicustom` line and Cloud-Init uses these snippets during ISO generation.

---

## `qm cloudinit update 100`
```bash
qm cloudinit update 100
```

Regenerates VM 100’s Cloud-Init disk.

- Used after changing `cicustom`, `ciuser`, `ipconfig0`, hostname, or Cloud-Init snippets.
- Expected result: `generating cloud-init ISO`.
- If a snippet volume does not exist, the command fails with a volume error.

---

## `qm cloudinit dump 100 user`
```bash
qm cloudinit dump 100 user
```

Displays generated Cloud-Init user-data for VM 100.

- Useful for checking Proxmox-generated Cloud-Init content.
- It may not always be sufficient proof of the actual custom snippet contents when `cicustom` behavior is confusing.
- If it shows `users: - default`, Proxmox is either falling back to defaults or the dump is not showing the custom snippet as expected.

---

## `qm cloudinit dump 100 network`
```bash
qm cloudinit dump 100 network
```

Displays generated Cloud-Init network config for VM 100.

- Useful for validating DHCP/static IP settings.
- In this session, network config was easier to validate than user-data.

---

## `pvesm status`
```bash
pvesm status
```

Lists Proxmox storage backends and their status.

- Used to confirm `cephpool`, `local`, `local-lvm`, and `snips`.
- Helps identify the storage IDs used in `qm set`.

---

## `cat /etc/pve/storage.cfg | grep -A5 snips`
```bash
cat /etc/pve/storage.cfg | grep -A5 snips
```

Shows the `snips` storage configuration.

- `path` determines the storage root.
- `content snippets` allows Cloud-Init snippets.
- `shared 0` means Proxmox considers this storage local, not shared.

Expected final config:

```text
dir: snips
        path /var/lib/vz/snips
        content snippets
        shared 0
```

---

## `pvesm list snips`
```bash
pvesm list snips
```

Lists volumes recognized by the `snips` storage.

Expected successful output includes:

```text
snips:snippets/docker-net.yml
snips:snippets/docker-userdata.yml
```

If empty, Proxmox does not see the files as snippet volumes.

---

## `mkdir -p /var/lib/vz/snips/snippets`
```bash
mkdir -p /var/lib/vz/snips/snippets
```

Creates the proper snippet directory tree for storage root `/var/lib/vz/snips`.

- `-p` creates parents as needed and does not error if the directory already exists.
- Required because Proxmox expects snippet content under a `snippets/` subdirectory.

---

## `mv ...`
```bash
mv /var/lib/vz/snippets/docker-userdata.yml /var/lib/vz/snips/snippets/
mv /var/lib/vz/snippets/docker-net.yml /var/lib/vz/snips/snippets/
```

Moves YAML snippets into the final Proxmox snippets directory.

- Used to align files with the `snips` storage path.
- If files already exist at the destination, be careful not to overwrite newer versions accidentally.

Risk: Moderate. Moving the wrong file or overwriting a newer YAML can break Cloud-Init provisioning.

---

## `rm -rf ...`
```bash
rm -rf /var/lib/vz/snips/snippets/snippets
```

Deletes an unwanted nested snippets folder.

- `rm -rf` recursively removes files and directories without prompting.
- Used only after confirming YAML files were safely stored in the correct location.

Risk: High. Verify with `ls -l` before running.

Safer check first:

```bash
ls -l /var/lib/vz/snips/snippets/snippets/
```

---

## `ls -l ...`
```bash
ls -l /var/lib/vz/snips/snippets/
```

Lists files and permissions in the final snippet directory.

- Used to verify `docker-userdata.yml` and `docker-net.yml` exist.
- Also confirms size and ownership.

Expected files:

```text
docker-net.yml
docker-userdata.yml
```

---

## `python3 YAML validation`
```bash
python3 -c 'import yaml,sys; yaml.safe_load(sys.stdin)' < /var/lib/vz/snips/snippets/docker-userdata.yml && echo "YAML OK"
```

Validates YAML syntax.

- Uses Python’s YAML library.
- Confirms the file is syntactically valid YAML.
- Does not guarantee Cloud-Init semantically accepts every module.

Success output:

```text
YAML OK
```

---

## `qm set 100 --delete ciuser --delete cipassword --delete sshkeys`
```bash
qm set 100 --delete ciuser --delete cipassword --delete sshkeys
```

Removes Proxmox-generated Cloud-Init user, password, and SSH key fields.

- Used to prevent Proxmox defaults from conflicting with custom user-data.
- Expected result: VM config no longer has those fields.

Risk: Low to moderate. If custom user-data does not apply, the VM may lose intended login settings.

---

## `qm set 100 --delete ide2`
```bash
qm set 100 --delete ide2
```

Removes the Cloud-Init drive from VM 100.

- Used before recreating `ide2` on the desired storage.
- Removes the existing Cloud-Init disk image.

Risk: Moderate. The VM will lose its Cloud-Init media until recreated.

---

## `qm set 100 --ide2 cephpool:cloudinit`
```bash
qm set 100 --ide2 cephpool:cloudinit
```

Creates/attaches a Cloud-Init disk on Ceph RBD storage.

- `ide2` is the conventional Cloud-Init CD-ROM slot in Proxmox.
- `cephpool:cloudinit` tells Proxmox to create a Cloud-Init disk in the Ceph pool.

Expected result:

```text
ide2: successfully created disk 'cephpool:vm-100-cloudinit,media=cdrom'
```

This is HA-friendly because Ceph storage is shared across nodes.

---

## `qm set 100 --ide2 snips:cloudinit`
```bash
qm set 100 --ide2 snips:cloudinit
```

Attempted to create a Cloud-Init disk on the `snips` storage.

This failed or became unsuitable because `snips` only supported `content snippets`, not `images`.

Failure observed:

```text
TASK ERROR: storage 'snips' does not support content-type 'images'
```

Lesson: snippets storage and Cloud-Init disk storage are related but not the same function.

---

## `rbd ls cephpool | grep vm-100-cloudinit`
```bash
rbd ls cephpool | grep vm-100-cloudinit
```

Lists Ceph RBD images and filters for the Cloud-Init disk.

- Confirms the RBD object exists.
- Used before mapping it for inspection.

---

## `rbd map cephpool/vm-100-cloudinit`
```bash
rbd map cephpool/vm-100-cloudinit
```

Maps the Ceph RBD image to a local block device on the Proxmox host.

Expected result:

```text
/dev/rbd0
```

Risk: Moderate. Do not write to the mapped Cloud-Init disk unless intentionally modifying it.

---

## `rbd device list`
```bash
rbd device list
```

Shows mapped RBD devices.

Used to identify the local device path, such as:

```text
/dev/rbd0
```

---

## `mount /dev/rbd0 /mnt/ci-test`
```bash
mount /dev/rbd0 /mnt/ci-test
```

Mounts the mapped Cloud-Init disk for inspection.

Expected warning:

```text
source write-protected, mounted read-only
```

This is normal for Cloud-Init media presented as a CD-ROM.

---

## `cat /mnt/ci-test/user-data`
```bash
cat /mnt/ci-test/user-data
```

Reads the actual user-data file inside the generated Cloud-Init disk.

This was the most direct validation that the custom YAML was embedded.

---

## `umount /mnt/ci-test`
```bash
umount /mnt/ci-test
```

Unmounts the Cloud-Init disk after inspection.

Always unmount before unmapping the RBD.

---

## `rbd unmap /dev/rbd0`
```bash
rbd unmap /dev/rbd0
```

Unmaps the RBD device from the Proxmox host.

Used after validation to clean up the temporary device mapping.

---

## `sudo cloud-init status --long`
```bash
sudo cloud-init status --long
```

Checks Cloud-Init status inside the VM.

Useful outputs:

```text
status: done
```

or:

```text
status: error
```

In this session, an earlier failure showed an `apt-get` package install error. Later validation showed Cloud-Init completed successfully.

---

## `ip a`
```bash
ip a
```

Shows network interfaces and IP addresses inside the VM.

Used to confirm the VM had:

```text
192.168.16.82/24
```

on `ens18`.

---

## `lsblk`
```bash
lsblk
```

Lists block devices inside the VM.

Observed:

```text
sda  50G
sdb 100G
sr0   4M
```

- `sda`: root disk
- `sdb`: intended Docker Ceph RBD disk
- `sr0`: Cloud-Init CD-ROM

---

## `df -h | grep docker`
```bash
df -h | grep docker
```

Checks whether any filesystem is mounted on a path containing `docker`.

No output means `/var/lib/docker` is not backed by a separate mounted filesystem.

---

## `lsblk -f | grep sdb`
```bash
lsblk -f | grep sdb
```

Checks if `/dev/sdb` has a filesystem and mountpoint.

Output only showing `sdb` means the disk exists but is unformatted or not mounted.

---

## `mkfs.ext4`
```bash
sudo mkfs.ext4 -L docker-disk /dev/sdb
```

Formats `/dev/sdb` as ext4 and labels it `docker-disk`.

Risk: High. This erases all data on `/dev/sdb`.

Only run when certain `/dev/sdb` is the intended new Docker data disk.

---

## `mount /dev/sdb /var/lib/docker`
```bash
sudo mount /dev/sdb /var/lib/docker
```

Mounts the Docker data disk at Docker’s default data directory.

- Docker stores images, containers, volumes, layers, and metadata under `/var/lib/docker`.
- Docker should usually be stopped before moving or replacing this path.

---

## `systemctl daemon-reload`
```bash
systemctl daemon-reload
```

Reloads systemd unit files after writing new service, timer, or override files.

Used after Cloud-Init writes:

- Docker override
- Gluetun restart service
- Gluetun restart timer

---

## `systemctl enable docker`
```bash
systemctl enable docker
```

Enables Docker to start at boot.

Used after installing Docker through Cloud-Init.

---

## `systemctl restart docker`
```bash
systemctl restart docker
```

Restarts Docker so new systemd overrides take effect.

Risk: Moderate. Restarting Docker can stop or restart running containers.

---

## `systemctl enable restart-gluetun-docker.timer`
```bash
systemctl enable restart-gluetun-docker.timer
```

Enables the Gluetun restart timer at boot.

The timer is intended to run after boot and then periodically.

---

## `systemctl start restart-gluetun-docker.timer`
```bash
systemctl start restart-gluetun-docker.timer
```

Starts the Gluetun timer immediately without waiting for reboot.

---

## `systemctl status restart-gluetun-docker.timer`
```bash
systemctl status restart-gluetun-docker.timer
```

Checks whether the Gluetun timer is loaded, enabled, and active.

---

## `systemctl list-timers | grep gluetun`
```bash
systemctl list-timers | grep gluetun
```

Shows when the Gluetun timer will next run.

Useful for validating timer scheduling.

---

## `journalctl -u restart-gluetun-docker.service`
```bash
journalctl -u restart-gluetun-docker.service
```

Shows logs from the Gluetun restart service.

Used to confirm whether the restart script executed and whether `docker restart` commands succeeded.

---

## `docker restart`
```bash
docker restart gluetun qbittorrent-vpn sabnzbd-vpn deluge-vpn
```

Restarts the VPN and downloader containers.

- Used by the Gluetun restart script.
- Can briefly interrupt downloads and VPN-dependent traffic.

Risk: Moderate. Frequent restarts can disrupt active downloads.

---

## `docker compose config`
```bash
docker compose config
```

Validates and renders a Docker Compose file.

Useful before starting migrated stacks.

---

## `docker compose up -d`
```bash
docker compose up -d
```

Starts a Compose stack in detached mode.

- `-d`: detached/background mode.
- Should be run from the directory containing `docker-compose.yml` or with `-f`.

---

## `docker ps`
```bash
docker ps
```

Lists running containers.

Used to verify services started after Compose deployment.

---

## `docker network inspect traefik-proxy`
```bash
docker network inspect traefik-proxy
```

Inspects the Docker network used by Traefik and app containers.

Useful for debugging service discovery and reverse proxy routing.
