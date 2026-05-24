---
title: "WireGuard Hub-and-Spoke Remote Access (EC2 Hub + Proxmox LXC Spoke)"
track: "infrastructure"
category: "networking"
type: "runbook"
logical_order: 60
date_rule: "Dates are removed from filenames, visible headings, indexes, generated metadata, and runbook body content."
---

# WireGuard Hub-and-Spoke Remote Access (EC2 Hub + Proxmox LXC Spoke)

## Summary
Designed a remote-access approach for a homelab that avoids ISP limitations (notably CGNAT and changing home public IPs) by using a publicly reachable AWS EC2 instance as a WireGuard “hub” and a Proxmox LXC container as a persistent “spoke” that also routes traffic into the home LAN. A mobile device is added as a second spoke for anywhere-access.

## Environment
**Cloud**
- AWS EC2 instance (“wireguard-hub”)
- OS: Amazon Linux 2 (per guide)
- Inbound access controlled by AWS Security Group
- WireGuard UDP port: **61517/UDP** (per guide)

**Homelab**
- Proxmox VE (host)
- Proxmox LXC container (Debian/Ubuntu template suggested)
- WireGuard client inside LXC (wg-quick)
- LXC requires host TUN device access (`/dev/net/tun`)
- Local home LAN subnet example referenced: **192.168.2.0/24** (from the guide’s examples)

**Client**
- Mobile device using official WireGuard app (Android/iOS)
- Client config imported via QR code

**Assumptions (explicitly labeled)**
- **Assumption:** The WireGuard tunnel interface is `wg0` and the LAN interface inside the LXC is `eth0` (guide states `eth0`; actual interface names may vary).
- **Assumption:** The WireGuard VPN subnet is a private range (commonly `10.x.x.x/24`), but the exact range is not provided in the pasted text.

## Problem
Enable secure remote access to internal homelab services (e.g., Docker apps on LAN IPs) from anywhere **without** relying on inbound connectivity to the home network, which may be blocked or complicated by:
- CGNAT (no true public IP / no inbound port-forwarding possible)
- Changing home public IP addresses (dynamic WAN IP)

## Symptoms
No direct “break/fix” symptoms were presented; this was primarily a design + implementation discussion. The key constraints being addressed:
- Inability/unreliability of inbound access to home due to CGNAT
- Home public IP changes over time

## Actions Taken
### 1) Created an AWS EC2 “Hub” for WireGuard
- Launched EC2 instance (Amazon Linux 2) sized as micro instance.
- Configured Security Group inbound rules:
  - SSH from “My IP” (restricted management access)
  - Custom UDP port **61517** from anywhere (WireGuard transport)

### 2) Installed and configured WireGuard on EC2 via installer script
- Connected via SSH using a key pair.
- Downloaded and ran a setup script which:
  - installs/configures WireGuard server on EC2
  - creates initial client config for the homelab (`homelab01.conf`)
  - supports adding additional clients later

### 3) Provisioned a Proxmox LXC “Spoke” to maintain a tunnel to EC2
- Created a new LXC (Debian/Ubuntu suggested).
- Enabled LXC capabilities needed for WireGuard:
  - Exposed host TUN device to the container: `dev0: /dev/net/tun`
  - Enabled LXC features `nesting=1,keyctl=1` (as suggested)

### 4) Installed WireGuard tooling inside the LXC and brought up wg0
- Installed packages: `wireguard-tools`, `resolvconf`, `iptables`
- Created `/etc/wireguard/wg0.conf` using the client config from EC2 (`homelab01.conf`)
- Enabled and started `wg-quick@wg0`
- Verified tunnel state using `wg show` (expected handshake info)

### 5) Added a mobile client (“Spoke 2”) and imported config via QR code
- Re-ran setup script on EC2 to “Add a new client”
- Generated QR code using `qrencode`
- Imported into the mobile WireGuard app
- Adjusted `AllowedIPs` to include homelab subnet (e.g., `192.168.2.0/24`) or optionally `0.0.0.0/0` for full-tunnel

### 6) Enabled full access to homelab LAN through the LXC (routing + NAT)
To allow the phone to access **LAN hosts** (not only the LXC), configured the LXC to behave like a router between:
- the WireGuard tunnel network (wg0)
- the home LAN (eth0)

Steps:
- Enabled IPv4 forwarding:
  - `net.ipv4.ip_forward=1` in `/etc/sysctl.conf`, applied via `sysctl -p`
- Added WireGuard `PostUp`/`PostDown` iptables rules in `/etc/wireguard/wg0.conf` under `[Interface]` to:
  - allow forwarding between wg0 and eth0
  - NAT (MASQUERADE) traffic going out via eth0 so LAN devices reply correctly
- Restarted WireGuard (`systemctl restart wg-quick@wg0`)

## Key Findings
### Hub vs Spoke clarification
- **EC2 is the only internet-facing “server endpoint.”**
  - Mobile devices and the homelab connect to EC2’s public IP/port.
- The **Proxmox LXC is a WireGuard client (“spoke”), not the public server.**
  - It maintains an outbound tunnel to EC2.
  - It additionally acts as a **LAN gateway** (router/NAT) so the phone can reach other LAN hosts.

### How this bypasses CGNAT
- CGNAT breaks inbound connectivity to the home network (no workable port-forwarding).
- This design does not require inbound to home:
  - Home LXC **initiates outbound** VPN traffic to EC2 (allowed through NAT/CGNAT)
  - Phone **initiates outbound** VPN traffic to EC2
  - EC2 routes traffic between connected peers inside the VPN overlay

### Dynamic home IP is irrelevant in this design
- The phone’s endpoint is EC2 (stable public endpoint), not the home WAN IP.
- Even if the home WAN IP changes, the LXC re-initiates outbound traffic to EC2 and the tunnel is re-established.

### AllowedIPs determines split vs full tunnel behavior
- If phone’s `AllowedIPs` includes only `192.168.2.0/24`, then only homelab traffic goes through VPN (split tunnel).
- If phone’s `AllowedIPs` is `0.0.0.0/0`, then all traffic goes through EC2 (full tunnel).
- **Note:** The guide implies public IP checks “should show EC2”; that is only true with full tunnel (`0.0.0.0/0`), not with split tunnel.

## Resolution
Implemented an architecture and configuration approach (per the guide) that provides:
- stable remote access through an EC2 hub
- persistent homelab connectivity via a WireGuard LXC spoke
- optional routing/NAT on the LXC to reach the entire home LAN from the VPN

**Current status:** Documented setup and rationale; no post-change issues or rollbacks were described in this conversation.

## Validation
Validation steps described in the guide:
1. On mobile (off Wi-Fi), enable WireGuard and access an internal LAN service by private IP (example: `http://192.168.2.100:2283`).
2. Check public IP from phone using a “what is my IP” site:
   - Should show EC2 public IP **only if** full tunnel is configured (`AllowedIPs = 0.0.0.0/0`).

## Follow-Up Tasks
- **AWS cost control:** Create an AWS Budget or CloudWatch billing alarm to avoid surprise charges.
- **Harden SSH access:** Keep SSH restricted to a known IP or use an alternative secure method (e.g., Session Manager) if IP changes frequently.
- **Confirm interface names:** Validate actual LXC LAN interface name (may not be `eth0`).
- **Persistence and resilience:** Consider adding WireGuard keepalives on the LXC peer config if NAT mappings time out (not explicitly included in pasted guide text).
- **Logging/monitoring:** Add basic tunnel health checks (handshake age) and alerting.

## Lessons Learned
- Using a public “hub” (EC2) avoids needing inbound access to home and cleanly sidesteps CGNAT.
- Running WireGuard in an LXC is viable but requires access to `/dev/net/tun` and sometimes `nesting/keyctl`.
- To access the entire LAN through the VPN, the LXC must do **IP forwarding + NAT** unless you implement return routing on your LAN devices/router.
- `AllowedIPs` is the key knob that controls split tunnel vs full tunnel behavior.

---

# Command Reference

## Command
```bash
ssh -i /path/to/your-key.pem ec2-user@YOUR_EC2_PUBLIC_IP
```
**What it does:** SSH into the EC2 instance using an SSH private key file.  
**Important parts:**
- `-i ...pem` selects the key used for authentication.
- `ec2-user@...` is the default login user for Amazon Linux 2.  
**Why used:** Required to administer the EC2 hub and install WireGuard.  
**Expected result:** Successful shell prompt on EC2.  
**Failure indicates:** Wrong key permissions, wrong IP, security group blocking SSH, wrong username, or IP restriction mismatch.  
**Risk:** Low, but exposing SSH broadly is risky; the guide restricts SSH to “My IP.”

---

## Command
```bash
curl -O https://github.com/codeunbound/homelab/blob/main/automation/wireguard/wireguard-setup.sh
```
**What it does:** Downloads a file from a URL and saves it locally using the remote filename.  
**Important parts:**
- `-O` writes output to a local file named like the remote file.  
**Why used:** Retrieve the installer script to set up WireGuard on EC2.  
**Expected result:** A local file `wireguard-setup.sh` exists in the current directory.  
**Failure indicates:** Wrong URL, network/DNS issues, permissions, or GitHub HTML download vs raw file issue.  
**Risk:** Medium. Running scripts from the internet is inherently risky.  
**Safer alternative:** Download from a trusted “raw” URL and inspect first (`less wireguard-setup.sh`) before executing.

---

## Command
```bash
chmod +x wireguard-setup.sh
```
**What it does:** Marks the script as executable.  
**Why used:** Allows running `./wireguard-setup.sh`.  
**Expected result:** File becomes executable.  
**Failure indicates:** Permission issue or missing file.  
**Risk:** Low.

---

## Command
```bash
sudo ./wireguard-setup.sh
```
**What it does:** Executes the setup script as root.  
**Why used:** Installing packages and configuring networking/services requires root.  
**Expected result:** WireGuard installed/configured; client config(s) generated.  
**Failure indicates:** Missing dependencies, OS mismatch, script errors, or permission issues.  
**Risk:** High (root execution).  
**Safer alternative:** Inspect script contents first; consider pinning versions or using a known-good installer method.

---

## Command
```bash
sudo cat /etc/wireguard/wg0-clients/homelab01.conf
```
**What it does:** Displays the generated client configuration for the homelab.  
**Why used:** Copy config contents into the LXC’s `/etc/wireguard/wg0.conf`.  
**Expected result:** Full WireGuard client config printed.  
**Failure indicates:** File path differs, script didn’t generate configs, or permissions issue.  
**Risk:** Low, but avoid leaking private keys.

---

## Command
```bash
pct enter <VMID>
```
**What it does:** Opens a shell inside a Proxmox LXC container.  
**Why used:** To install WireGuard and configure the tunnel inside the container.  
**Expected result:** Shell inside container.  
**Failure indicates:** Wrong VMID, container not running, insufficient permissions.  
**Risk:** Low.

---

## Command
```bash
apt update && apt upgrade -y
```
**What it does:** Updates package lists and upgrades installed packages on Debian/Ubuntu-based LXC.  
**Important parts:**
- `-y` auto-confirms prompts.  
**Why used:** Ensure system is current before installing new packages.  
**Expected result:** Packages updated/upgraded successfully.  
**Failure indicates:** DNS/network issues, repo errors, or broken package state.  
**Risk:** Medium, because upgrades can change behavior.  
**Safer alternative:** Review upgrades first by omitting `-y` on sensitive systems.

---

## Command
```bash
apt install wireguard-tools resolvconf iptables -y
```
**What it does:** Installs WireGuard tooling, DNS management helper, and firewall tools.  
**Why used:** Needed to bring up wg0 and implement forwarding/NAT rules.  
**Expected result:** Packages installed successfully.  
**Failure indicates:** Repo problems or incompatible distro base.  
**Risk:** Low to medium.

---

## Command
```bash
mkdir -p /etc/wireguard
```
**What it does:** Creates the WireGuard config directory if it does not exist.  
**Why used:** Standard location for WireGuard configs.  
**Expected result:** Directory exists.  
**Risk:** Low.

---

## Command
```bash
nano /etc/wireguard/wg0.conf
```
**What it does:** Opens the wg0 configuration file for editing.  
**Why used:** Paste the client config from EC2 into the LXC.  
**Expected result:** File saved with correct WireGuard config.  
**Failure indicates:** Syntax errors, wrong permissions, or wrong file path.  
**Risk:** Medium, because misconfiguration can break the tunnel.

---

## Command
```bash
systemctl enable wg-quick@wg0
systemctl start wg-quick@wg0
```
**What it does:** Enables WireGuard tunnel `wg0` to start at boot and starts it now.  
**Why used:** Make the tunnel persistent and active.  
**Expected result:** Service active; tunnel interface created.  
**Failure indicates:** Bad config, missing kernel module, no TUN access, or service errors.  
**Risk:** Low.

---

## Command
```bash
wg show
```
**What it does:** Displays WireGuard interface and peer status, including handshakes.  
**Why used:** Verify that the tunnel is up and exchanging keepalive/handshake traffic.  
**Expected result:** Shows interface `wg0` and peer handshake timestamps.  
**Failure indicates:** Routing/firewall issues, wrong keys, endpoint unreachable.  
**Risk:** Low.

---

## Command
```bash
sudo yum install qrencode -y
```
**What it does:** Installs QR code generation tool on Amazon Linux (yum-based).  
**Why used:** To convert a client config file into a scannable QR code for the phone.  
**Expected result:** `qrencode` available.  
**Failure indicates:** Repo issues or package name differences.  
**Risk:** Low.

---

## Command
```bash
sudo qrencode -t ansiutf8 -r /home/ec2-user/wg0-client-codeunbound01.conf
```
**What it does:** Prints a QR code in the terminal encoding the client config file.  
**Important parts:**
- `-t ansiutf8` outputs a terminal-friendly QR code.
- `-r <file>` reads content from file.  
**Why used:** Fast import into mobile WireGuard app.  
**Expected result:** QR code displayed.  
**Failure indicates:** Wrong path, missing file, permissions.  
**Risk:** Low, but the config includes private keys, so do not screen-share it.

---

## Command
```bash
nano /etc/sysctl.conf
```
**What it does:** Edits kernel parameter configuration.  
**Why used:** Enable IPv4 forwarding for routing from wg0 to LAN.  
**Expected result:** `net.ipv4.ip_forward=1` set.  
**Risk:** Medium, because it affects networking system-wide in the container.  
**Safer alternative:** Use a drop-in file under `/etc/sysctl.d/` for more controlled configuration.

---

## Command
```bash
sysctl -p
```
**What it does:** Applies sysctl settings from `/etc/sysctl.conf` immediately.  
**Why used:** Turn on forwarding without reboot.  
**Expected result:** Forwarding enabled.  
**Failure indicates:** Syntax errors or permissions.  
**Risk:** Low.

---

## Command
```bash
systemctl restart wg-quick@wg0
```
**What it does:** Restarts the wg0 tunnel service to apply config changes (`PostUp`/`PostDown` rules).  
**Why used:** Ensures new iptables/NAT rules are applied.  
**Expected result:** Tunnel returns to active; LAN access works.  
**Failure indicates:** Config syntax errors, iptables failures, missing kernel features.  
**Risk:** Medium, because it creates a brief disconnect and could fail to come back up if config is wrong.

---

## iptables rules from wg0.conf PostUp/PostDown
```bash
iptables -A FORWARD -i %i -o eth0 -j ACCEPT
iptables -A FORWARD -i eth0 -o %i -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
```

Corresponding `PostDown` rules remove the same rules using `-D`.

**What they do:**
- Allow forwarding from WireGuard interface (`%i`, which expands to `wg0`) to LAN interface (`eth0`).
- Allow return traffic back into the tunnel for established connections.
- NAT outbound traffic to the LAN so LAN hosts reply to the LXC without needing routes to the VPN subnet.

**Why used:** Enables phone → VPN → LXC → LAN host connectivity reliably.  
**Expected result:** Remote clients can reach `192.168.2.0/24` hosts while connected to VPN.  
**Failure indicates:** Wrong interface name, iptables not installed, forwarding disabled, or routing/AllowedIPs mismatch.  
**Risk:** Medium to high because firewall/routing changes can affect connectivity.  
**Safer alternative:** Prefer explicit routing on the LAN gateway/router instead of NAT if you control it and want end-to-end visibility, but NAT is simpler and often “just works.”
