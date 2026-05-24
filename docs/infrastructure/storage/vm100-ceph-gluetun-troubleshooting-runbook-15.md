---
title: "VM 100 CPU Change Led Into HA/QMP/Ceph-Related Startup Failure"
track: "infrastructure"
category: "storage"
type: "runbook"
logical_order: 20
date_rule: "Dates are removed from filenames, visible headings, indexes, generated metadata, and runbook body content."
---

# VM 100 CPU Change Led Into HA/QMP/Ceph-Related Startup Failure

## Summary
VM 100 (`debian-docker`) was being adjusted to use 4 vCPUs. During the change, reset and stop/start attempts ran into HA-managed control flow, QMP socket timeouts, stale lock behavior, and a larger underlying Ceph health problem. The VM eventually became unable to start normally until Ceph health was restored.

## Environment
- Proxmox VE cluster
- Host/node involved: `mainframe`
- VM: `100` (`debian-docker`)
- HA-managed VM resource at the start of the incident
- Ceph cluster:
  - 5 monitors configured
  - `mon.mainframe` out of quorum
  - 5 OSDs up/in
  - slow ops on `osd.0`, `osd.1`, `osd.2`
- VM storage backed by Ceph
- Cloud-init attached to VM 100

## Problem
A routine change to VM 100 CPU topology exposed multiple operational issues:
1. HA-controlled VM operations conflicted with manual `qm` commands.
2. QMP became unavailable during reset/stop attempts.
3. Ceph was degraded and blocking I/O.
4. VM startup later hung while generating the cloud-init ISO.

## Symptoms
- CPU change was applied, but VM operations failed afterward.
- Errors seen:
  - `VM 100 qmp command 'system_reset' failed - got timeout`
  - `unable to connect to VM 100 qmp socket - timeout after 51 retries`
  - `Requesting HA stop for VM 100`
  - `can't lock file '/var/lock/qemu-server/lock-100.conf' - got timeout`
- Ceph health warnings:
  - `1/5 mons down`
  - `mon.mainframe ... is down (out of quorum)`
  - `768 slow ops, oldest one blocked for ...`
- Later VM start failure:
  - `generating cloud-init ISO`
  - `timeout waiting on systemd`

## Actions Taken
1. Changed VM 100 CPU topology.
```bash
qm set 100 --sockets 1 --cores 4
```
Purpose: set VM 100 to 4 vCPUs using 1 socket and 4 cores.

2. Additional CPU topology changes were attempted while the VM was already unstable.
```bash
qm set 100 --sockets 1 --cores 8
```
Purpose: temporary adjustment while trying to recover VM startup.

3. Attempted resets and stops from `qm`, which failed due to HA/QMP issues.
```bash
qm reset 100
qm stop 100
qm start 100
```
Purpose: try to restart the VM cleanly.

4. Confirmed HA interactions and that `qm start` was being redirected through HA control.

5. Investigated Ceph health.
```bash
ceph -s
ceph health detail
```
Purpose: determine whether storage health was preventing VM startup.

6. Identified failed monitor and lagging OSD state on Ceph.

7. Attempted monitor service recovery on `mainframe`.
```bash
systemctl status ceph-mon@mainframe --no-pager -l
timedatectl
systemctl restart ceph-mon@mainframe
```
Purpose: restore the failed monitor and rule out time-sync related quorum issues.

8. Found that `ceph-mon@mainframe` was failed and systemd on `mainframe` later became unstable enough to return DBus errors.

9. Protected Ceph during recovery.
```bash
ceph osd set noout
ceph mgr fail mainframe
```
Purpose: avoid rebalancing while the node was being recovered and move active manager duties away from the unhealthy node.

10. Removed stale/broken `mon.mainframe` entry from the Ceph monmap.
```bash
ceph mon dump
ceph mon remove mainframe || ceph mon rm mainframe
ceph mon dump
```
Purpose: remove the dead monitor from cluster state so it could be recreated cleanly.

11. Removed the old local monitor store and recreated the monitor on `mainframe`.
```bash
rm -rf /var/lib/ceph/mon/ceph-mainframe
pveceph mon create
systemctl start ceph-mon@mainframe
systemctl status ceph-mon@mainframe --no-pager -l
```
Purpose: rebuild the local Ceph monitor instance on `mainframe`.

12. Verified cluster state after recovery.
```bash
ceph osd unset noout
ceph -s
```
Purpose: return Ceph to normal operation after the cluster was stable.

13. Retried starting VM 100 once Ceph returned to healthy state.
```bash
qm start 100
qm status 100
```

14. Observed cloud-init ISO generation timeout and later worked around cloud-init-related startup issues conceptually by considering removal of the CI drive for recovery.

## Key Findings
- The initial VM issue was not only a CPU configuration problem. It was compounded by:
  - HA-managed resource behavior
  - stuck/stale QMP state
  - Ceph monitor outage
  - Ceph slow ops on multiple OSDs
- `mon.mainframe` had been removed from the monmap and needed to be recreated locally.
- Once the Ceph monitor issue was addressed and `noout` was later unset, the cluster returned to:
  - `HEALTH_OK`
  - 33 PGs `active+clean`
- The VM startup issue then shifted from storage health to cloud-init ISO generation timing.

## Resolution
The core storage-side outage was resolved by repairing Ceph rather than continuing to force VM restarts:
- `mon.mainframe` was removed from the cluster map.
- The local monitor store on `mainframe` was recreated.
- Ceph recovered to `HEALTH_OK`.
- VM 100 could run again, though cloud-init ISO generation remained a separate operational concern.

## Validation
Successful validation included:
- `ceph -s` showing:
  - `HEALTH_OK`
  - all OSDs up/in
  - PGs `active+clean`
- `ceph-mon@mainframe` showing as active locally
- VM 100 reaching `status: running`
- VM 100 responding on the network:
```bash
ping -c1 192.168.16.3
nc -vz 192.168.16.3 22
```
SSH port 22 was reachable, confirming the guest was alive even though QEMU guest agent remained unavailable.

## Follow-Up Tasks
- Revisit VM 100 CPU topology once the environment is stable and perform the change with a clean shutdown.
- Investigate why cloud-init ISO generation timed out.
- Stabilize QEMU guest agent on VM 100.
- Review HA handling workflow for HA-managed VMs before issuing direct `qm` reset/stop commands.
- Consider adding additional safeguards around Ceph monitor recovery and health checks.

## Lessons Learned
- A VM startup failure on Proxmox can be a storage-cluster issue, not just a VM config issue.
- HA-managed VMs should be handled through HA-aware workflows first.
- QMP socket timeouts often indicate a deeper process, lock, or storage-state problem.
- Ceph monitor recovery can be non-destructive when quorum still exists on other nodes.
- `noout` is useful during controlled node recovery, but it must be unset afterward.

---

# Ceph Fully Stabilized and VM 100 Network Reachability Confirmed

## Summary
After the prior day’s Ceph repair work, the cluster was checked again and confirmed healthy. VM 100 was running, reachable by IP, and accepting TCP connections on port 22. The remaining issue shifted from storage failure to guest-side access and tooling reliability.

## Environment
- Proxmox VE host: `mainframe`
- VM 100: `debian-docker`
- Ceph cluster healthy
- Guest IP observed: `192.168.16.3`
- QEMU Guest Agent not functioning inside the guest

## Problem
Even though VM 100 was running, the QEMU guest agent was not available, and SSH usability was still under question.

## Symptoms
- `qm status 100` reported the VM as running.
- `qm agent 100 ping` returned:
  - `QEMU guest agent is not running`
- Network tests from the Proxmox host succeeded:
  - ping worked
  - TCP 22 was open

## Actions Taken
1. Verified VM state and attempted guest agent calls.
```bash
qm status 100
qm agent 100 ping
qm agent 100 network-get-interfaces
```
Purpose: confirm whether the guest was alive and whether QGA was functioning.

2. Identified VM MAC from config.
```bash
qm config 100 | grep -E '^net0:'
```
Purpose: correlate guest networking if needed.

3. Tested network reachability directly.
```bash
ping -c1 192.168.16.3
nc -vz 192.168.16.3 22
```
Purpose: verify whether the guest was reachable independently of QGA.

## Key Findings
- VM 100 was alive and reachable on the network.
- Port 22 was open, so the VM was not dead or storage-blocked at that point.
- The remaining problem was likely guest-side SSH login/authentication and/or guest agent service availability rather than host networking or Proxmox storage.

## Resolution
No final QEMU guest agent fix was completed in this session, but the critical state changed from “VM won’t start” to “VM is running and reachable.” The incident moved into guest-service troubleshooting rather than platform outage recovery.

## Validation
- `qm status 100` showed `running`
- ICMP ping succeeded
- `nc -vz 192.168.16.3 22` reported SSH port open

## Follow-Up Tasks
- Repair `qemu-guest-agent` inside VM 100
- Validate actual SSH login path, not just port reachability
- Review guest service startup order after reboot
- Review cloud-init impact on networking and SSH provisioning

## Lessons Learned
- QEMU guest agent absence does not mean the guest is down.
- Network reachability tests are a better immediate truth source than agent state during recovery.
- Separate platform health from guest-service health when troubleshooting.

---

# Gluetun VPN Stack Repaired for Deluge, qBittorrent, and SABnzbd

## Summary
A Docker VPN stack using Gluetun with Mullvad WireGuard was failing due to multiple configuration and state issues: a broken healthcheck assumption, invalid or missing WireGuard key handling, and a corrupted `servers.json` in the Gluetun config volume. The stack was repaired and brought back online. Remaining warnings pointed to CIFS/NAS write-permission or filename-handling issues on SABnzbd download paths.

## Environment
- VM 100: Debian Docker VM
- Docker Compose stack under `/opt/compose/gluetun_stack/compose.yaml`
- Containers:
  - `gluetun`
  - `deluge-vpn`
  - `qbittorrent-vpn`
  - `sabnzbd-vpn`
- VPN provider: Mullvad
- VPN type: WireGuard
- Shared Docker network: `traefik-proxy`
- Reverse proxy: Traefik
- App config directories under `/opt/docker-apps`
- Download paths on NAS/CIFS mounts under `/srv/remotemount/...`

## Problem
The VPN-dependent Docker stack was unstable and unhealthy. Gluetun failed health checks and later crash-looped because of invalid VPN key handling and a corrupted server metadata file. Dependent containers were also being terminated when Gluetun restarted.

## Symptoms
- Gluetun marked unhealthy.
- Earlier healthcheck was targeting `127.0.0.1:8000` without confirmed control server alignment.
- Gluetun log errors included:
  - `Wireguard settings: private key is not set`
  - `private key is not valid: ... illegal base64 data at input byte 0`
  - `ERROR reading servers from file: decoding servers: invalid character 'l' after object key:value pair`
- Dependent containers received shutdown signals:
  - `Catching signal: SIGTERM`
  - clean exits for Deluge and SABnzbd
  - qBittorrent exited with code `137`
- Later logs showed Gluetun healthy once repaired:
  - control server listening on `:8000`
  - healthcheck healthy
  - public IP resolved through Mullvad

## Actions Taken
1. Reviewed the compose configuration for Gluetun and dependent containers.

2. Identified that the healthcheck/control-server relationship needed to be aligned and that the stack needed a known-good Gluetun configuration.

3. Updated the Gluetun service configuration to include:
- WireGuard with Mullvad
- inline private key in YAML
- control server on port 8000
- startup stability settings
- explicit healthcheck against `/v1/health`
- broad server selection by country rather than pinning a single hostname during recovery

4. Brought the stack down and removed corrupted server metadata.
```bash
docker compose -f /opt/compose/gluetun_stack/compose.yaml down
rm -f /opt/docker-apps/Gluetun/config/servers.json /opt/docker-apps/Gluetun/config/servers.json.tmp 2>/dev/null || true
```
Purpose: fully stop the stack and delete the bad Gluetun server cache.

5. Attempted ownership and permission repair on Gluetun config paths.
```bash
chown -R 1000:1000 /opt/docker-apps/Gluetun
chmod -R 775 /opt/docker-apps/Gluetun
```
Purpose: normalize host-side file ownership for the Gluetun config volume.

6. Those ownership changes failed because they were run as non-root:
- `Operation not permitted`

7. Started Gluetun alone for isolated validation.
```bash
docker compose -f /opt/compose/gluetun_stack/compose.yaml up -d gluetun
docker logs -f --tail=200 gluetun
```
Purpose: verify VPN connectivity and Gluetun health before starting dependent applications.

8. Confirmed successful Gluetun startup:
- firewall enabled
- control server on port 8000
- healthcheck healthy
- Mullvad WireGuard connected
- public IP reported in Canada

9. Started Deluge, qBittorrent, and SABnzbd after Gluetun stabilized.
```bash
docker compose -f /opt/compose/gluetun_stack/compose.yaml up -d deluge qbittorrent sabnzbd
```
Purpose: restore the full VPN stack after the shared network namespace anchor was healthy.

## Key Findings
- The corrupted `/gluetun/servers.json` was a hard blocker and caused repeated early exits.
- WireGuard key handling was briefly incorrect during configuration changes.
- Keeping the private key inline in YAML was workable as long as the value was quoted and valid.
- Once Gluetun stabilized, Deluge, qBittorrent, and SABnzbd all launched successfully through the shared namespace.
- qBittorrent WebUI came up on port 8880.
- Deluge daemon and Web UI started successfully.
- SABnzbd started successfully but warned that:
  - `/usenet-downloads/incomplete` was not writable with special character filenames
  - `/usenet-downloads/complete` was not writable with special character filenames

## Resolution
The Gluetun stack was successfully restored by:
- deleting the corrupted `servers.json`
- correcting WireGuard key handling
- using a stable Gluetun configuration
- bringing up Gluetun by itself first
- starting dependent containers only after Gluetun became healthy

The stack was operational at the end of the session.

## Validation
Validation came from:
- Gluetun logs showing:
  - firewall enabled
  - healthcheck healthy
  - DNS ready
  - public VPN IP in Canada
- qBittorrent logs showing WebUI startup on `localhost:8880`
- Deluge logs showing daemon and UI availability
- SABnzbd logs showing full service startup on port `8088`

## Follow-Up Tasks
- Fix SABnzbd download path writeability and special-character handling on NAS/CIFS mounts.
- Revisit whether DNS-over-TLS should remain enabled or temporarily disabled for stability.
- Run host-side permission changes with `sudo` if ownership normalization is still desired.
- Consider whether to repin to a specific Mullvad hostname only after long-term stability is confirmed.
- Rotate WireGuard private keys if any prior testing exposed or mishandled them.

## Lessons Learned
- Start Gluetun by itself first when debugging a VPN-dependent shared-namespace stack.
- A corrupted persistent metadata file can look like a networking problem when it is actually a storage/config-volume problem.
- When Gluetun is the network namespace owner, every dependent container inherits its lifecycle.
- Non-root host users cannot repair ownership on protected bind-mounted config paths.
- CIFS/NAS mount behavior can surface as application warnings even after the VPN stack itself is healthy.

---

# Command Reference

## Command
```bash
qm set 100 --sockets 1 --cores 4
```
**What it does:** Sets VM 100 CPU topology to 1 socket and 4 cores.  
**Important arguments:**  
- `100`: VM ID  
- `--sockets 1`: one CPU socket exposed to the guest  
- `--cores 4`: four cores per socket  
**Why it was used:** To change VM 100 to 4 vCPUs.  
**Expected result:** VM config reflects 4 total vCPUs.  
**Success indicates:** The config change was accepted.  
**Failure indicates:** Proxmox config write or locking issue.

## Command
```bash
qm set 100 --sockets 1 --cores 8
```
**What it does:** Changes VM CPU topology to 8 cores temporarily.  
**Why it was used:** Recovery/testing while the VM was already unstable.  
**Risk:** Changing CPU topology during instability can complicate troubleshooting.

## Command
```bash
qm reset 100
```
**What it does:** Issues a hard reset to the VM through QMP.  
**Why it was used:** To force a reboot when the guest was not responding normally.  
**Expected result:** Immediate guest reset.  
**Failure indicates:** QMP unavailable, stuck VM process, or host-side control path problem.  
**Risk:** Equivalent to pulling power inside the guest.

## Command
```bash
qm stop 100
```
**What it does:** Stops the VM from the Proxmox host.  
**Why it was used:** To halt the guest during recovery.  
**Expected result:** VM transitions to stopped.  
**Failure indicates:** lock issue, HA interaction, or QMP/control-path problem.

## Command
```bash
qm start 100
```
**What it does:** Starts VM 100.  
**Why it was used:** To test whether the platform and storage were healthy enough to boot the guest.  
**Expected result:** VM enters running state.  
**Failure indicates:** storage, config, HA, lock, or runtime startup problem.

## Command
```bash
ha-manager status
```
**What it does:** Shows Proxmox HA resource status.  
**Why it was used:** To determine whether VM 100 was HA-managed and whether HA was interfering with direct VM control.  
**Expected result:** Resource state and node placement information.

## Command
```bash
ceph -s
```
**What it does:** Displays a concise Ceph cluster status summary.  
**Why it was used:** To determine whether storage cluster health was blocking VM operations.  
**Expected result:** cluster health, mon/mgr/osd state, PG state, and usage summary.  
**Success indicates:** cluster responds and provides current health.  
**Failure indicates:** cluster connectivity or CLI environment issue.

## Command
```bash
ceph health detail
```
**What it does:** Shows detailed Ceph health warnings and errors.  
**Why it was used:** To identify specific monitor and OSD problems.  
**Expected result:** exact warning classes such as `MON_DOWN` or `SLOW_OPS`.

## Command
```bash
systemctl status ceph-mon@mainframe --no-pager -l
```
**What it does:** Shows detailed service status for the Ceph monitor on `mainframe`.  
**Important arguments:**  
- `--no-pager`: prints directly to the terminal  
- `-l`: full lines without truncation  
**Why it was used:** To diagnose why `mon.mainframe` was out of quorum.  
**Expected result:** active/running or failed state with log excerpts.

## Command
```bash
timedatectl
```
**What it does:** Displays local time, time sync, and NTP status.  
**Why it was used:** Time skew can break Ceph monitor quorum and elections.  
**Expected result:** synchronized system clock.

## Command
```bash
ceph osd set noout
```
**What it does:** Sets the Ceph `noout` flag to prevent OSDs being marked out automatically.  
**Why it was used:** To avoid cluster rebalance while recovering a node.  
**Expected result:** cluster health mentions `noout`.  
**Risk:** Should be unset after maintenance; leaving it enabled can hide real failures.

## Command
```bash
ceph mgr fail mainframe
```
**What it does:** Forces the active Ceph manager on `mainframe` to fail over to a standby manager.  
**Why it was used:** To reduce dependency on the unhealthy node during recovery.  
**Expected result:** another mgr becomes active.

## Command
```bash
ceph mon dump
```
**What it does:** Dumps the current monitor map.  
**Why it was used:** To verify whether `mon.mainframe` was still registered in the cluster.  
**Expected result:** monitor addresses and monmap epoch.

## Command
```bash
ceph mon remove mainframe || ceph mon rm mainframe
```
**What it does:** Removes `mon.mainframe` from the Ceph monitor map.  
**Why it was used:** To cleanly remove the stale/broken monitor definition before recreating it.  
**Expected result:** `mainframe` no longer appears in `ceph mon dump`.  
**Risk:** Safe only because the remaining monitors already had quorum.

## Command
```bash
rm -rf /var/lib/ceph/mon/ceph-mainframe
```
**What it does:** Deletes the local monitor data directory for `mainframe`.  
**Why it was used:** To remove the broken local monitor store before recreating it.  
**Expected result:** directory removed so a clean monitor can be created.  
**Risk:** Destructive to the local monitor instance; appropriate only when recreating the monitor and cluster quorum already exists elsewhere.

## Command
```bash
pveceph mon create
```
**What it does:** Creates a Ceph monitor on the local Proxmox node.  
**Why it was used:** To recreate `mon.mainframe` after removing the stale entry and local data.  
**Expected result:** local monitor service and data store are rebuilt.

## Command
```bash
ceph osd unset noout
```
**What it does:** Removes the Ceph `noout` maintenance flag.  
**Why it was used:** To return the cluster to normal behavior after recovery.  
**Expected result:** cluster health no longer reports `noout`.

## Command
```bash
qm status 100
```
**What it does:** Shows whether VM 100 is running or stopped.  
**Why it was used:** To validate guest state during recovery.

## Command
```bash
qm agent 100 ping
```
**What it does:** Tests connectivity to the QEMU Guest Agent inside VM 100.  
**Why it was used:** To check whether the guest agent was functioning.  
**Expected result:** a successful ping response.  
**Failure indicates:** guest agent not running, missing device, or guest-side service issue.

## Command
```bash
qm agent 100 network-get-interfaces
```
**What it does:** Queries guest network interfaces through QEMU Guest Agent.  
**Why it was used:** To discover the guest IP from Proxmox without logging into the VM.  
**Failure indicates:** guest agent not available.

## Command
```bash
qm config 100 | grep -E '^net0:'
```
**What it does:** Extracts the VM’s primary network interface definition from config.  
**Why it was used:** To identify the MAC address for ARP/neighbor lookup.

## Command
```bash
ping -c1 192.168.16.3
```
**What it does:** Sends one ICMP echo request to the guest IP.  
**Why it was used:** To confirm guest network reachability.  
**Success indicates:** the guest responds on the network.  
**Failure indicates:** guest networking, firewall, or host routing issue.

## Command
```bash
nc -vz 192.168.16.3 22
```
**What it does:** Tests TCP connectivity to port 22 on the guest.  
**Important arguments:**  
- `-v`: verbose  
- `-z`: scan mode without sending payload  
**Why it was used:** To check whether SSH was listening.  
**Success indicates:** TCP port 22 open.  
**Failure indicates:** SSH not listening, filtering, or routing issue.

## Command
```bash
docker compose -f /opt/compose/gluetun_stack/compose.yaml down
```
**What it does:** Stops and removes the services in the Gluetun stack.  
**Why it was used:** To fully reset the VPN stack during repair.  
**Expected result:** containers removed cleanly.

## Command
```bash
rm -f /opt/docker-apps/Gluetun/config/servers.json /opt/docker-apps/Gluetun/config/servers.json.tmp 2>/dev/null || true
```
**What it does:** Removes Gluetun’s cached server metadata files.  
**Why it was used:** The file was corrupted and causing Gluetun startup failure.  
**Expected result:** Gluetun regenerates a valid `servers.json` on next startup.

## Command
```bash
chown -R 1000:1000 /opt/docker-apps/Gluetun
```
**What it does:** Recursively changes ownership of the Gluetun config directory.  
**Why it was used:** To align host file ownership with the container’s runtime UID/GID.  
**Expected result:** Gluetun can read/write config files as user 1000.  
**Failure indicates:** insufficient privileges or filesystem restrictions.  
**Risk:** Recursive ownership changes should be used carefully on shared paths.

## Command
```bash
chmod -R 775 /opt/docker-apps/Gluetun
```
**What it does:** Recursively sets directory/file permissions to group-writable/readable/executable as appropriate.  
**Why it was used:** To ensure Gluetun could write its config cache and state.  
**Failure indicates:** insufficient privileges or filesystem restrictions.

## Command
```bash
docker compose -f /opt/compose/gluetun_stack/compose.yaml up -d gluetun
```
**What it does:** Starts only the Gluetun service in detached mode.  
**Why it was used:** To validate the VPN container independently before starting dependent apps.  
**Expected result:** Gluetun reaches healthy state and remains running.

## Command
```bash
docker logs -f --tail=200 gluetun
```
**What it does:** Follows the most recent 200 lines of Gluetun logs.  
**Why it was used:** To monitor startup, VPN initialization, DNS, healthcheck, and exit reasons in real time.

## Command
```bash
docker compose -f /opt/compose/gluetun_stack/compose.yaml up -d deluge qbittorrent sabnzbd
```
**What it does:** Starts the VPN-dependent application containers after Gluetun is healthy.  
**Why it was used:** To restore the rest of the stack once the shared network namespace owner was stable.

## Command
```bash
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
```
**What it does:** Shows running containers with names, status, and published ports in table form.  
**Why it was used:** To quickly verify container state after recovery.

## Command
```bash
curl -fsS http://127.0.0.1:8000/v1/health
```
**What it does:** Queries the Gluetun control/health endpoint.  
**Important arguments:**  
- `-f`: fail on HTTP errors  
- `-sS`: quiet normal output but show errors  
**Why it was used:** To confirm Gluetun health from inside the host/container namespace.  
**Expected result:** successful HTTP response.

## Command
```bash
docker exec -it gluetun sh -c 'wg show; wget -qO- https://ipinfo.io/ip || curl -s https://ipinfo.io/ip'
```
**What it does:** Runs WireGuard status and public IP checks inside the Gluetun container.  
**Why it was used:** To verify VPN tunnel state and the public egress IP.

## Command
```bash
sudo chown -R 1000:1000 /opt/docker-apps/{Deluge,qBittorrent,SABnzbd}
```
**Likely command used.**  
**What it does:** Corrects ownership of LinuxServer.io app config directories.  
**Why it was recommended:** Those containers run as UID/GID 1000.  
**Expected result:** apps can read/write their config and state correctly.

## Command
```bash
sudo chmod -R 775 /opt/docker-apps/{Deluge,qBittorrent,SABnzbd}
```
**Likely command used.**  
**What it does:** Applies writable permissions to the app config directories.  
**Why it was recommended:** To reduce config-write failures for LinuxServer.io containers.

## Command
```bash
sudo mount -a
```
**Likely command used.**  
**What it does:** Mounts all filesystems listed in `/etc/fstab` that are not already mounted.  
**Why it was recommended:** To apply corrected CIFS mount options for NAS-backed download directories.  
**Expected result:** updated mount options become active without full reboot.  
**Risk:** A bad `/etc/fstab` entry can cause mount failures or boot problems later if not validated carefully.
