---
title: "Proxmox HA Design for GPU-Aware Media and Transcoding Workloads"
track: "infrastructure"
category: "architecture"
type: "runbook"
logical_order: 10
date_rule: "Dates are removed from filenames, visible headings, indexes, generated metadata, and runbook body content."
---

# Proxmox HA Design for GPU-Aware Media and Transcoding Workloads

## Summary
This work session focused on how Proxmox High Availability should be designed for media workloads that depend on hardware acceleration, especially Plex and Tdarr. The environment includes one custom PC with an NVIDIA GPU and four Intel NUC nodes with Intel integrated graphics. The goal was to understand how HA behaves when a VM with passed-through hardware fails over, and to design a robust layout for GPU-aware services.

## Environment
- Proxmox VE cluster
- 1 custom PC node with NVIDIA GPU
- 4 identical Intel NUC nodes with Intel iGPU
- Shared-storage-oriented homelab design implied for HA
- Docker workloads running inside VMs
- Plex in Docker
- Tdarr in Docker
- Proxmox HA groups and PCI passthrough under consideration
- Likely reverse-proxy and shared media workflows already present elsewhere in the homelab

## Problem
The main question was how Proxmox HA behaves for VMs that rely on GPU passthrough, and what happens when such a VM moves to another node that may not have the same hardware.

## Symptoms
- Uncertainty about whether HA was truly working for existing VMs
- Concern about Plex losing GPU functionality after failover
- Concern about how Tdarr should be designed in a mixed NVIDIA and Intel cluster
- Need to distinguish between true HA restart behavior and simple autostart behavior

## Actions Taken
1. Reviewed how to verify Proxmox HA health and resource state.
2. Examined how HA behaves when a VM has PCI passthrough attached.
3. Evaluated failover behavior for a VM running Plex in Docker with a passed-through GPU.
4. Mapped the user’s actual hardware topology: one NVIDIA-capable tower and four Intel NUCs.
5. Developed two Plex design patterns:
   - HA with degraded operation on non-GPU-equivalent nodes
   - HA with per-node PCI mappings so the VM can receive either NVIDIA or Intel graphics depending on host
6. Designed a recommended Tdarr architecture separating the server role from worker roles.
7. Clarified the difference between VM autostart on boot and HA-managed state.

## Key Findings
- Proxmox HA can restart a VM on another node only if the VM’s storage is accessible there and the target node satisfies the VM’s hardware requirements.
- PCI passthrough prevents live migration. GPU-backed VMs should be expected to cold-start on failover, not live-migrate.
- A Plex VM with a passed-through NVIDIA GPU cannot simply restart on a node without a compatible passthrough mapping unless the VM is designed to tolerate running without GPU acceleration.
- Proxmox PCI mappings are the cleanest way to abstract different physical GPUs across different nodes under one logical device name.
- In this environment, Plex can be designed either to:
  - run anywhere and fall back to CPU/software transcoding on the NUCs, or
  - use per-node mappings so the tower provides NVIDIA acceleration and NUCs provide Intel Quick Sync.
- Tdarr benefits from being split into:
  - one HA-capable server VM without GPU dependency
  - multiple worker VMs or containers with node-local acceleration
- VM `onboot` is not the same as HA state. HA-managed VMs should be controlled by `ha-manager`, not by relying on `qm set --onboot 1`.

## Resolution
No single live issue was fixed in this portion of the session. Instead, the outcome was a design decision framework:

- For Plex:
  - preferred simple design: allow failover anywhere, with NVIDIA acceleration on the custom PC and software fallback on NUCs
  - advanced design: use Proxmox PCI mappings so the VM receives the node’s available GPU type

- For Tdarr:
  - recommended design: separate Tdarr Server from Tdarr Nodes
  - keep the server small, HA-enabled, and not GPU-dependent
  - run workers with either NVIDIA or Intel hardware acceleration depending on node
  - use shared media storage and local cache/temp space for robustness

- For VM startup:
  - if VM 100 is HA-managed, use HA resource state rather than only node-boot autostart

## Validation
Validation guidance established during the session included:
- confirm cluster quorum and HA daemon health
- confirm the VM is registered in `ha-manager`
- confirm the VM disks are on shared storage
- test an HA migration or controlled failover
- verify that GPU-dependent services behave correctly on the destination node
- for Tdarr, verify that jobs requeue safely and that transcode temp files are isolated from final media paths

## Follow-Up Tasks
- Create HA groups that reflect GPU capability and intended placement
- Build Proxmox PCI mappings for mixed NVIDIA and Intel GPU nodes
- Decide whether Plex should support software fallback on non-NVIDIA nodes
- Separate Tdarr Server and Tdarr Worker roles if not already done
- Verify all HA-targeted VMs use shared storage
- Test cold-failover behavior for media workloads during maintenance windows

## Lessons Learned
- GPU passthrough and HA work best when hardware differences are abstracted with PCI mappings.
- HA for GPU-backed VMs should be designed as cold-restart HA, not live-migration HA.
- Media services and transcode workers should be architected differently; not every role needs the GPU.
- Proxmox HA and VM boot order/autostart are different control planes and should not be mixed conceptually.

---

# OPNsense Port Forwarding and Traefik Reachability Troubleshooting

## Summary
This work session focused on verifying whether OPNsense was correctly forwarding ports 80 and 443 to Traefik, validating whether Traefik itself was listening properly, and deciding how LAN clients should resolve reverse-proxied services.

## Environment
- OPNsense firewall/router
- Traefik running in Docker on Debian host `debian-docker`
- Public-facing domain `dulynoted.cloud`
- Dashboard hostnames such as `traefik.dulynoted.cloud`
- Docker reverse-proxy network `traefik-proxy`
- Split DNS / local DNS design discussion
- Cloudflare DNS and Cloudflare proxy considerations
- Likely NAT and firewall rules on WAN in OPNsense

## Problem
The objective was to confirm whether ports 80 and 443 were open and correctly forwarded through OPNsense to Traefik, and to determine the best internal DNS approach for LAN access to public service names.

## Symptoms
- Need to verify if OPNsense was forwarding ports 80 and 443 correctly
- Need help setting up port forward rules
- Need to decide between split DNS and local-only `.home`-style naming
- Need to interpret local Traefik test results after moving Docker to a new host that reused the prior IP address

## Actions Taken
1. Checked whether Traefik was listening on ports 80 and 443 on the Docker host.
2. Queried local HTTP and HTTPS responses directly from the host.
3. Reviewed how to create OPNsense WAN port-forward rules for 80 and 443.
4. Reviewed how to create LAN hairpin behavior either with split DNS or NAT reflection.
5. Compared split DNS against a Pi-hole-only local-domain naming design.
6. Considered host move implications after the new Docker host took the old IP address.
7. Discussed how to verify if the reverse-proxy was being reached locally and from WAN.

## Key Findings
- Traefik was confirmed to be listening on:
  - `0.0.0.0:80`
  - `0.0.0.0:443`
  - IPv6 equivalents
- Local HTTP returned `308 Permanent Redirect`, indicating HTTP-to-HTTPS redirection was working.
- Local HTTPS returned `404`, which strongly suggested Traefik itself was reachable, but the request did not match a configured router because it was sent to `127.0.0.1` without the expected Host header.
- The host move reused the old IP, so OPNsense NAT rules pointing at that IP likely remained logically correct, but ARP caches, host-level differences, or Traefik configuration mismatches still needed consideration.
- Split DNS using the real public domain is the better design for Traefik-backed applications because it preserves valid hostnames and TLS expectations.
- A private `.home` naming approach is better reserved for purely internal hostnames that are never intended to use public-domain TLS semantics.

## Resolution
The session established a working troubleshooting flow rather than a single final fix:
- verify Traefik locally first
- confirm OPNsense NAT and WAN rules
- use split DNS for reverse-proxied services behind Traefik
- account for ARP or DNS cache artifacts after moving Docker to a new host that reused the old address

## Validation
Successful local validation already achieved:

```bash
ss -ltnp '( sport = :80 or sport = :443 )'
curl -sI http://127.0.0.1 | head -n1
curl -sIk https://127.0.0.1 -k | head -n1
```

Observed results:
- ports 80 and 443 listening
- HTTP redirect functioning
- HTTPS reaching Traefik but not matching a route without proper hostname

Further validation steps discussed:
- test from a LAN host using the actual hostname
- test from outside the network
- confirm OPNsense live firewall logs for TCP/80 and TCP/443
- confirm DNS resolution for LAN clients points to the Traefik LAN IP under split DNS

## Follow-Up Tasks
- Verify the exact OPNsense NAT rules for WAN TCP/80 and WAN TCP/443
- Confirm WAN firewall pass rules were auto-created or manually added
- Add or validate split DNS records for proxied services
- Flush stale ARP/DNS caches on clients if host-IP reuse causes ambiguity
- Confirm external path from WAN or cellular once local hostname tests pass

## Lessons Learned
- A `404` from Traefik on localhost HTTPS often means routing mismatch, not transport failure.
- Reusing an old IP on a new Docker host keeps NAT logic simple but can still leave stale cache problems.
- Split DNS is cleaner than NAT reflection for most homelab reverse-proxy use cases.
- Public service names should generally resolve to the reverse-proxy’s LAN IP for internal clients.

---

# Traefik Migration, Reverse Proxy Recovery, and Configuration Modernization

## Summary
This work session focused on recovering and modernizing a Traefik deployment after Docker was moved to a new host that inherited the old IP address. The work included analyzing a dashboard `500 Internal Server Error`, reviewing the existing Docker Compose file, updating Traefik to a current v3-based layout, modernizing dynamic and static configuration, and clarifying required file locations and permissions.

## Environment
- Debian Docker VM/host: `debian-docker`
- Docker Compose
- Traefik originally on image `traefik:2.6`
- Docker socket proxy: `tecnativa/docker-socket-proxy`
- Cloudflare DNS-01 ACME challenge
- Domain: `dulynoted.cloud`
- Dashboard hostname: `traefik.dulynoted.cloud`
- Config root on host: `/opt/docker-apps/Traefik/config`
- Dynamic config path under discussion: `/opt/docker-apps/Traefik/config/dynamic`
- ACME storage: `/opt/docker-apps/Traefik/config/letsencrypt/acme.json`
- Access log path: `/opt/docker-apps/Traefik/config/logs/access.log`

## Problem
After moving Docker to a new host and reusing the prior IP, the Traefik dashboard returned `500 Internal Server Error`. The existing configuration needed to be inspected, corrected, and modernized.

## Symptoms
- Browser error:
  - `https://traefik.dulynoted.cloud/`
  - `500 Internal Server Error`
- Existing compose showed several likely issues:
  - Traefik 2.6 in use
  - missing explicit Docker provider flags for the socket proxy
  - use of entrypoint names inconsistent with later config expectations
  - file-based middleware reference `organizr-auth@file` without a confirmed file-provider layout
  - legacy middleware names
  - security-sensitive Cloudflare token exposed in compose
- Existing static config enabled `api.insecure: true`
- Existing dynamic config used `ipWhiteList`, old entrypoint names, and Pi-hole redirect logic that needed review

## Actions Taken
1. Reviewed the existing Traefik Docker Compose file.
2. Identified specific configuration problems:
   - missing provider wiring to the socket proxy
   - dashboard service label conflict
   - middleware dependency on file provider
   - missing or inconsistent entrypoint definitions
3. Recommended rotating the exposed Cloudflare DNS API token.
4. Rewrote the Docker Compose file for Traefik v3.
5. Standardized the configuration layout under `/opt/docker-apps/Traefik/config`.
6. Updated the dynamic configuration:
   - entrypoints changed from `https` to `websecure`
   - `ipWhiteList` updated to `ipAllowList`
   - Pi-hole redirect logic corrected
7. Updated the static `traefik.yml`:
   - standardized `web` and `websecure`
   - moved file provider to a directory model
   - disabled `api.insecure`
   - aligned with docker-socket-proxy
8. Clarified `.env` format for `CF_DNS_API_TOKEN`.
9. Clarified what DNS resolvers in ACME DNS-01 config do and why explicit resolvers may help.

## Key Findings
- The original compose depended on a docker-socket-proxy but did not configure Traefik’s Docker provider endpoint explicitly.
- The compose referenced `organizr-auth@file`, which required a valid dynamic file provider and readable config files.
- The dashboard should be exposed via `api@internal`, not through an invented load-balancer service definition on port 8080.
- `api.insecure: true` was not appropriate when the dashboard was already being published through a secure router.
- Traefik v3 remains broadly compatible with the prior v2-style routing model, but static configuration needed cleanup and some deprecated constructs needed updating.
- Dynamic configuration should be stored under a directory such as `/etc/traefik/dynamic`, not tied to a single filename if the deployment is intended to grow.
- `acme.json` permissions are critical; Traefik expects the file to exist and be restricted.
- Access log paths and dynamic file paths must exist on disk and be readable or writable as appropriate.

## Resolution
A new Traefik v3 configuration baseline was established:

### Static config location
- Host: `/opt/docker-apps/Traefik/config/traefik.yml`
- Container: `/etc/traefik/traefik.yml`

### Dynamic config location
- Host: `/opt/docker-apps/Traefik/config/dynamic/*.yml`
- Container: `/etc/traefik/dynamic/*.yml`

### Key design changes
- Traefik upgraded from `2.6` to a current v3-series image
- Docker provider explicitly enabled and pointed at `tcp://dockersocket:2375`
- Dashboard served through `api@internal`
- Entry points standardized to `web` and `websecure`
- File provider changed to a directory-based layout
- `api.insecure` disabled
- Cloudflare token moved to `.env`
- Dynamic middleware modernized for Traefik v3

## Validation
Validation steps discussed or completed:
- local Traefik transport checks succeeded
- revised file locations and permissions were specified
- post-change validation recommended:

```bash
docker compose restart traefik
curl -Ik --resolve traefik.dulynoted.cloud:443:<LAN_IP> https://traefik.dulynoted.cloud
```

Expected result:
- a valid dashboard response at the origin instead of a `500`

## Follow-Up Tasks
- Rotate the exposed Cloudflare API token immediately
- Replace old compose and static/dynamic config with the updated v3-compatible versions
- Ensure all dynamic files under `/opt/docker-apps/Traefik/config/dynamic` are readable
- Verify `acme.json` exists and has strict permissions
- Re-test dashboard origin path before testing through Cloudflare
- Re-enable Organizr or other forwardAuth only after base dashboard routing works
- Review all other router labels for consistent `websecure` entrypoint naming

## Lessons Learned
- A `500` at the dashboard can be caused by middleware/provider wiring issues, not just transport errors.
- File-provider and permission mistakes are common failure points in Traefik migrations.
- Static and dynamic config should be separated cleanly before adding more services.
- Tokens should never be hardcoded in compose files.
- Modernizing Traefik is easier when the dashboard router is simplified first and auth is added back later.

---

# Traefik DNS-01 and Resolver Behavior Clarification

## Summary
This short work segment clarified what the `resolvers` setting means in Traefik’s ACME DNS-01 configuration and why explicit public DNS resolvers may improve reliability.

## Environment
- Traefik
- ACME DNS-01 challenge
- Cloudflare DNS
- Public domain `dulynoted.cloud`

## Problem
There was a need to understand the comment indicating that Cloudflare’s recursive resolvers could be preferred during DNS-01 validation.

## Symptoms
- Configuration included resolver lines but their role was unclear
- Need to understand whether the setting changed authoritative propagation or only validation behavior

## Actions Taken
1. Explained the DNS-01 flow:
   - create TXT record
   - poll until visible
   - Let’s Encrypt validates
2. Clarified that the `resolvers` field controls which recursive resolvers Traefik uses to look up the TXT record.
3. Explained why public resolvers such as `1.1.1.1` and `1.0.0.1` can be more reliable than local cached resolvers.

## Key Findings
- The setting does not force propagation.
- It can reduce failures caused by stale local caches, split DNS, or slow recursive resolvers.
- It is especially useful when the homelab uses Pi-hole, local DNS overrides, or other caching layers.

## Resolution
The meaning of the resolver block was clarified, and the current use of Cloudflare’s recursive resolvers remained acceptable.

## Validation
Suggested validation:

```bash
dig +short TXT _acme-challenge.dulynoted.cloud
dig @1.1.1.1 +short TXT _acme-challenge.dulynoted.cloud
```

Compare what the default resolver sees versus what `1.1.1.1` sees.

## Follow-Up Tasks
- Keep the explicit resolvers if DNS-01 propagation timing has ever been inconsistent
- Remove them only if there is a deliberate reason to rely on internal resolvers

## Lessons Learned
- DNS challenge failures are often resolver-visibility problems, not provider-API problems.
- Public recursive resolvers can make ACME automation more deterministic in homelab environments.

---

# Command Reference

## Command
```bash
pvecm status
```
Checks Proxmox cluster quorum and membership state.

Why it was used:
To confirm that the Proxmox cluster is healthy enough for HA decisions.

Expected result:
A quorate cluster with the expected nodes present.

Success indicates:
Cluster control plane is operational.

Failure indicates:
HA behavior may be unreliable or blocked by quorum issues.

Risk:
Low.

---

## Command
```bash
systemctl is-active pve-ha-crm pve-ha-lrm corosync
```
Checks whether Proxmox HA manager daemons and Corosync are active.

Why it was used:
To verify the HA stack is actually running on the nodes.

Expected result:
`active` for the relevant services.

Success indicates:
HA service processes are available.

Failure indicates:
HA cannot properly manage resources.

Risk:
Low.

---

## Command
```bash
ha-manager status
```
Displays current Proxmox HA resource state.

Why it was used:
To confirm whether a VM is actually HA-managed and what state it is in.

Expected result:
The VM appears as an HA resource with expected state.

Success indicates:
The VM is under HA control.

Failure indicates:
The VM may only be using normal Proxmox startup behavior rather than HA.

Risk:
Low.

---

## Command
```bash
ha-manager add vm:100 --group gpu-nodes --state started
```
Adds VM 100 to Proxmox HA and places it in an HA group.

Why it was used:
To manage startup/failover for a GPU-aware VM using HA.

Important arguments:
- `vm:100`: HA resource identifier
- `--group gpu-nodes`: restricts eligible nodes
- `--state started`: desired HA state

Expected result:
VM becomes an HA-managed resource.

Success indicates:
HA will attempt to keep the VM running on eligible nodes.

Failure indicates:
Resource or group config needs correction.

Risk:
Moderate. Changes HA behavior for a production VM.

Safer alternative:
Review `ha-manager status` and HA group definitions first.

---

## Command
```bash
qm set 100 --onboot 1
```
Enables node-boot autostart for VM 100.

Why it was used:
To make VM 100 start when a Proxmox node boots.

Important arguments:
- `100`: VM ID
- `--onboot 1`: enable boot-time autostart

Expected result:
VM config reflects `onboot: 1`.

Success indicates:
The node will try to start the VM at boot if HA is not controlling it.

Failure indicates:
VM config change did not apply.

Risk:
Low.

Important note:
If the VM is HA-managed, HA state is the preferred control mechanism.

---

## Command
```bash
qm config 100 | grep -E 'onboot|startup'
```
Shows whether autostart and startup ordering are configured on VM 100.

Why it was used:
To verify boot-time VM settings.

Expected result:
Relevant config lines appear if configured.

Success indicates:
Autostart or startup order was saved.

Failure indicates:
Settings may not have been applied.

Risk:
Low.

---

## Command
```bash
ss -ltnp '( sport = :80 or sport = :443 )'
```
Shows listening TCP sockets on ports 80 and 443.

Why it was used:
To confirm Traefik was actually listening on HTTP and HTTPS ports.

Important arguments:
- `-l`: listening sockets only
- `-t`: TCP
- `-n`: numeric output
- `-p`: process info when available

Expected result:
Listeners on port 80 and 443 on the expected interfaces.

Success indicates:
The reverse proxy is bound to the right ports.

Failure indicates:
Traefik or container port publishing is broken.

Risk:
Low.

---

## Command
```bash
curl -sI http://127.0.0.1 | head -n1
```
Fetches only HTTP headers from local HTTP service and shows the first response line.

Why it was used:
To verify whether local HTTP on port 80 responds.

Important arguments:
- `-s`: silent
- `-I`: HEAD request / headers only

Expected result:
A response such as `308 Permanent Redirect`.

Success indicates:
Local HTTP service is working.

Failure indicates:
Nothing is listening or the proxy is failing.

Risk:
Low.

---

## Command
```bash
curl -sIk https://127.0.0.1 -k | head -n1
```
Fetches HTTPS headers from localhost while ignoring certificate validation.

Why it was used:
To confirm HTTPS service reachability on the host.

Important arguments:
- `-I`: headers only
- `-k`: ignore TLS certificate validation

Expected result:
An HTTPS response such as `404`, `200`, or redirect status.

Success indicates:
Traefik is reachable over HTTPS.

Failure indicates:
TLS listener or container publishing is broken.

Risk:
Low.

---

## Command
```bash
curl -Ik --resolve traefik.dulynoted.cloud:443:<LAN_IP> https://traefik.dulynoted.cloud
```
Forces a specific hostname to resolve to a chosen IP for a local origin test.

Why it was used:
To test Traefik routing using the real Host header without relying on public DNS.

Important arguments:
- `--resolve host:port:ip`: overrides DNS for this curl request

Expected result:
A proper dashboard response from the Traefik origin.

Success indicates:
Origin routing works and the issue may lie elsewhere.

Failure indicates:
Router, middleware, or certificate issues at the origin.

Risk:
Low.

---

## Command
```bash
docker network create traefik-proxy
```
Creates the external Docker bridge network used by Traefik and proxied services.

Why it was used:
To ensure the reverse-proxy network exists before starting services that rely on it.

Expected result:
Network exists after command completion.

Success indicates:
Containers can join the expected shared network.

Failure indicates:
Existing network conflict or Docker issue.

Risk:
Low.

---

## Command
```bash
docker compose pull
```
Pulls the latest images defined in the compose file.

Why it was used:
To update Traefik and related services.

Expected result:
Images download successfully.

Success indicates:
New versions are ready to deploy.

Failure indicates:
Registry, auth, or connectivity problems.

Risk:
Low to moderate. Pulling newer images may introduce behavior changes.

---

## Command
```bash
docker compose down
```
Stops and removes the current compose stack.

Why it was used:
To replace or restart the Traefik stack with updated configuration.

Expected result:
Containers are stopped and removed.

Success indicates:
The environment is ready for clean recreation.

Failure indicates:
Compose state or Docker daemon problems.

Risk:
Moderate. Causes service interruption.

Safer alternative:
For some changes, `docker compose restart` may be sufficient.

---

## Command
```bash
docker compose up -d
```
Starts the compose stack in detached mode.

Why it was used:
To bring the updated Traefik stack online.

Important arguments:
- `-d`: detached mode

Expected result:
Containers start successfully in the background.

Success indicates:
The stack is running.

Failure indicates:
Config, permissions, image, or dependency problems.

Risk:
Low to moderate.

---

## Command
```bash
docker compose restart traefik
```
Restarts only the Traefik service in the compose stack.

Why it was used:
To apply static or dynamic configuration changes.

Expected result:
Traefik restarts cleanly.

Success indicates:
New config is loaded.

Failure indicates:
Syntax, permission, or dependency problems.

Risk:
Low to moderate. Causes brief reverse-proxy outage.

---

## Command
```bash
docker logs --tail=200 traefik
```
Shows the most recent log lines for the Traefik container.

Why it was used:
To troubleshoot dashboard `500` errors and config parsing issues.

Important arguments:
- `--tail=200`: show recent lines only

Expected result:
Useful log output indicating router, provider, middleware, or TLS problems.

Success indicates:
Logs are available for diagnosis.

Failure indicates:
Container may not be running.

Risk:
Low.

---

## Command
```bash
arp -an | grep <OLD_IP>
```
Shows ARP cache entries for the reused old IP address.

Why it was used:
To verify whether clients were still associating the reused IP with the previous host MAC address.

Expected result:
ARP entry maps to the current host MAC.

Success indicates:
Layer-2 resolution is current.

Failure indicates:
Stale ARP caching may be misdirecting traffic.

Risk:
Low.

---

## Command
```bash
ping -c2 <OLD_IP>
```
Tests basic IP connectivity to the reused old IP address.

Why it was used:
To confirm the new host is reachable on that address.

Expected result:
Successful replies.

Success indicates:
Host is reachable at layer 3.

Failure indicates:
Network path or host-address issue.

Risk:
Low.

---

## Command
```bash
ssh <OLD_IP>
```
Attempts SSH connectivity to the host at the reused IP.

Why it was used:
To verify that the host answering on the reused IP is the expected system.

Expected result:
SSH connection to the new host.

Success indicates:
The new host is reachable and likely owns the IP.

Failure indicates:
Wrong system answering, firewall issue, or host down.

Risk:
Low.

---

## Command
```bash
ip neigh flush all
```
Flushes the Linux ARP/neighbor cache.

Why it was used:
To clear stale client-side address resolution after a host-IP migration.

Expected result:
Neighbor cache is cleared and rebuilt on next traffic.

Success indicates:
Subsequent traffic should learn the current MAC.

Failure indicates:
Permissions or OS differences.

Risk:
Moderate. Temporarily disrupts cached neighbor entries.

Safer alternative:
Clear only the specific affected neighbor entry if possible.

---

## Command
```bash
chmod 600 /opt/docker-apps/Traefik/config/letsencrypt/acme.json
```
Restricts the ACME storage file so only the owner can read/write it.

Why it was used:
Traefik expects strict permissions on `acme.json`.

Expected result:
Mode becomes `600`.

Success indicates:
Traefik can use the file without permission complaints.

Failure indicates:
Permission or path issue.

Risk:
Low.

---

## Command
```bash
chown root:root /opt/docker-apps/Traefik/config/letsencrypt/acme.json
```
Sets file ownership of `acme.json` to root.

Why it was used:
To align ownership with Traefik container expectations when mounted.

Expected result:
File becomes owned by root.

Success indicates:
File ownership is standardized.

Failure indicates:
Filesystem or privilege issue.

Risk:
Low.

---

## Command
```bash
mkdir -p /opt/docker-apps/Traefik/config/{dynamic,logs,letsencrypt}
```
Creates required Traefik config directories.

Why it was used:
To establish the file layout expected by the compose and static config.

Expected result:
Directories exist.

Success indicates:
Traefik mount paths can contain required files.

Failure indicates:
Permission or filesystem issues.

Risk:
Low.

---

## Command
```bash
touch /opt/docker-apps/Traefik/config/logs/access.log
```
Creates the Traefik access log file if it does not already exist.

Why it was used:
The configured access log path must exist and be writable.

Expected result:
File exists.

Success indicates:
Traefik can write access logs.

Failure indicates:
Permission or path issue.

Risk:
Low.

---

## Command
```bash
touch /opt/docker-apps/Traefik/config/letsencrypt/acme.json
```
Creates the ACME storage file if it does not already exist.

Why it was used:
Traefik expects the file to exist at startup.

Expected result:
File exists and can then be permissioned correctly.

Success indicates:
ACME storage path is ready.

Failure indicates:
Permission or path issue.

Risk:
Low.

---

## Command
```bash
chmod 644 /opt/docker-apps/Traefik/config/dynamic/*.yml
```
Makes dynamic config files readable to the container.

Why it was used:
Traefik must be able to read file-provider configuration.

Expected result:
Files become world-readable.

Success indicates:
File provider can read them.

Failure indicates:
Path or shell expansion issue.

Risk:
Low.

---

## Command
```bash
dig +short TXT _acme-challenge.dulynoted.cloud
```
Queries the TXT record for the ACME challenge using the system default resolver.

Why it was used:
To see whether the challenge record is visible through the current DNS path.

Expected result:
Current challenge TXT record appears when present.

Success indicates:
Resolver sees the challenge record.

Failure indicates:
Propagation or resolver-visibility issue.

Risk:
Low.

---

## Command
```bash
dig @1.1.1.1 +short TXT _acme-challenge.dulynoted.cloud
```
Queries the TXT record for the ACME challenge specifically against Cloudflare’s recursive resolver.

Why it was used:
To compare public-recursive visibility versus local resolver visibility.

Expected result:
TXT record appears if public propagation is visible there.

Success indicates:
Public resolver sees the challenge correctly.

Failure indicates:
Propagation delay or authoritative publication issue.

Risk:
Low.
