---
title: "OPNsense LAN Instability, AP/OPT Segmentation Review, and TL-SG108E Storm-Control Stabilization"
track: "infrastructure"
category: "networking"
type: "runbook"
logical_order: 50
date_rule: "Dates are removed from filenames, visible headings, indexes, generated metadata, and runbook body content."
---

# OPNsense LAN Instability, AP/OPT Segmentation Review, and TL-SG108E Storm-Control Stabilization

## Summary
This session focused on troubleshooting intermittent LAN and internet connectivity problems in a homelab network built around OPNsense, multiple TP-Link TL-SG108E smart switches, and TP-Link Archer access points. The original investigation began around a question of whether an OPT interface and a second downstream router were causing client internet failures. During troubleshooting, it was clarified that one downstream TP-Link device was already operating in access point mode rather than router mode, shifting attention back to the main LAN path.

The issue was ultimately narrowed to instability on the flat LAN segment rather than OPT1. The network was simplified conceptually as a flat switched network, and switch storm-control settings were applied uniformly. A flat storm-control threshold of 8000 Kbps on all switches appeared to stabilize the environment.

## Environment
- Router/firewall: OPNsense running on a CWWK 12th-gen Intel mini PC with Intel i3-N305
- Primary LAN switching:
  - 4 × TP-Link TL-SG108E Easy Smart switches
- Wireless infrastructure:
  - TP-Link Archer AX80 in AP mode on LAN
  - TP-Link Archer AX72 Pro in AP mode on OPT1
- Wired clients mentioned:
  - Proxmox nodes
  - Android TV box
- OPNsense interfaces:
  - LAN
  - OPT1
- Logical network design during this session:
  - Flat LAN on the main switched path
  - Separate OPT1 segment feeding the Archer AX72 Pro in AP mode
- Services discussed:
  - OPNsense DHCP
  - OPNsense Unbound DNS
  - Firewall rules and outbound NAT
  - Switch storm control
  - Loop prevention
- VLANs:
  - Discussed conceptually only
  - Not implemented during this session

## Problem
Devices on the main LAN were slow to connect, sometimes failed to get internet access after connecting, and wired devices downstream of the smart switches were also losing connectivity. There was initial uncertainty about whether the issue was related to OPT1 segmentation, downstream TP-Link operating mode, DHCP behavior, or broader layer-2 instability.

## Symptoms
- Devices were slow to connect to the network
- Once connected, devices often had no internet access
- Wired devices connected through the smart-switch chain also lost connectivity
- OPNsense logs showed some default deny and state-violation entries
- There was uncertainty about whether a second downstream TP-Link was acting as a router or only as an AP
- Connectivity problems affected both wireless and wired clients on the main LAN path

## Actions Taken
1. Reviewed the original physical topology:
   - OPNsense LAN → TL-SG108E core switch → additional TL-SG108E switches → Proxmox nodes, Android TV box, and Archer AX80 in AP mode
   - OPNsense OPT1 → Archer AX72 Pro in AP mode

2. Considered whether the downstream TP-Link on the secondary path should operate as:
   - a router behind an OPNsense OPT interface, or
   - a pure AP bridged into the OPNsense segment

3. Clarified that the Archer on the secondary segment was already in AP mode, not router mode.

4. Determined that OPT1 appeared to be functioning correctly and shifted focus to the main LAN path.

5. Reviewed likely causes on LAN:
   - layer-2 loops
   - broadcast or multicast storms
   - rogue DHCP
   - AP uplink misconfiguration
   - switch-chain instability

6. Verified or discussed AP best practices:
   - AP mode enabled
   - DHCP disabled on APs
   - uplink should use LAN port rather than WAN in AP mode
   - management IPs should be static or reserved

7. Discussed assigning static IP addresses to the Archer APs for management.

8. Reviewed TL-SG108E management considerations:
   - password-reset path if login access was lost
   - later confirmed switch login was still using the default credentials

9. Reviewed TL-SG108E VLAN features conceptually:
   - MTU VLAN
   - Port-Based VLAN
   - 802.1Q VLAN
   - PVID behavior
   - Confirmed VLANs were not needed at this time

10. Confirmed that loop prevention was already enabled by default on the switches.

11. Applied storm-control settings uniformly across the switches at a flat threshold of 8000 Kbps to simplify the configuration.

12. Observed that the storm-control change appeared to resolve the immediate LAN instability.

## Key Findings
- The problem path was the main LAN, not OPT1.
- The secondary TP-Link device was already in AP mode, so the issue was not caused by an intended router-behind-OPT design.
- Because the AP was bridged, clients behind it should have been using OPNsense-provided DHCP, gateway, and DNS rather than a separate routed path.
- The symptoms matched a likely layer-2 issue more closely than a routing issue:
  - intermittent connectivity
  - slow association
  - wired and wireless impact
  - apparent stabilization after storm-control changes
- Loop prevention was already enabled, but that alone was not sufficient to fully suppress the instability.
- Applying storm control at 8000 Kbps on all switches appeared to mitigate the problem.
- VLAN support on the TL-SG108E and OPNsense was discussed for future use, but VLANs were not part of the implemented fix.

### Facts
- OPT1 appeared stable during this session.
- Archer AX72 Pro was confirmed to be in AP mode.
- Archer AX80 was also being used in AP mode on LAN.
- There were actually 4 TL-SG108E switches in the environment, not 3.
- Loop prevention was enabled by default.
- Storm control set to 8000 Kbps across the switches appeared to solve the issue for the time being.

### Assumptions / Working Theories
- The root cause was likely excessive broadcast, multicast, unknown unicast, or other layer-2 flood behavior on the flat LAN.
- A loop, bursty discovery traffic, or MAC-table churn may have contributed even if loop prevention was enabled.
- Rogue DHCP remained a theoretical possibility earlier in the investigation, but no direct evidence in this conversation confirmed it as the final cause.

## Resolution
The practical workaround and current working fix was to keep the network flat and enable switch storm control uniformly at 8000 Kbps across the TL-SG108E switches. This simplified the configuration and appears to have stabilized LAN behavior.

No VLAN design was deployed during this work session. OPT1 remained separate from LAN, but the main issue was treated as a LAN switching problem rather than a firewall or routed-interface problem.

## Validation
Success was validated informally by observed behavior after the switch change:
- LAN connectivity appeared stable
- Internet access returned for affected devices
- The user reported that storm control seemed to have solved the issue
- A flat 8000 Kbps threshold was retained because it worked and was easy to manage

## Follow-Up Tasks
- Change the default admin password on all TL-SG108E switches
- Assign static management IPs to all TL-SG108E switches
- Assign static management IPs or DHCP reservations to both Archer APs
- Document exact switch port mappings:
  - core switch uplink to OPNsense
  - inter-switch uplinks
  - Proxmox-node ports
  - AP ports
  - Android TV box port
- Back up switch configurations after confirming stability
- Continue monitoring for:
  - renewed packet loss
  - discovery failures
  - intermittent wired drops
  - multicast-heavy application issues
- Consider raising multicast or unknown-unicast storm thresholds on switch uplinks later if application-specific issues appear
- Verify that only OPNsense is providing DHCP on the LAN segment
- Disable EEE/Green Ethernet on uplinks, AP ports, and server ports if not already done
- Keep VLAN planning deferred until the flat network remains stable over time

## Lessons Learned
- Do not assume a downstream TP-Link is routing; confirm whether it is in AP mode or router mode before designing around NAT or firewall behavior.
- If both wired and wireless clients are unstable on the same flat LAN, investigate layer-2 conditions before focusing on routing.
- Loop prevention alone may not be enough to stabilize a noisy switched environment.
- A simple, flat storm-control policy can be a useful first stabilization step in a small homelab.
- Keep management IPs for APs and switches fixed and documented.
- Avoid adding VLAN complexity until the physical topology and baseline switching behavior are stable.

---

# Command Reference

## Command
```bash
ipconfig
```

### What it does
Displays IP configuration on Windows clients.

### Why it was relevant
Used or implied for checking whether a client received the correct IP address, default gateway, and DNS server.

### Expected result
A client on the LAN should receive:
- an IP in the LAN subnet
- default gateway equal to the OPNsense LAN IP
- DNS pointing to OPNsense or the intended DNS path

### What success or failure indicates
- Success: client is likely getting correct DHCP information
- Failure: wrong gateway or DNS may indicate rogue DHCP, AP/router misconfiguration, or subnet mismatch

### Notes
Low risk.

---

## Command
```bash
ifconfig
```

### What it does
Displays interface configuration on Unix-like systems.

### Why it was relevant
Implied as the Linux/macOS equivalent of `ipconfig` for confirming client IP settings.

### Expected result
The client interface should show the correct subnet, address, and routing context.

### What success or failure indicates
- Correct interface details support DHCP and addressing health
- Incorrect subnet or no address points toward DHCP or physical connectivity issues

### Notes
Low risk.

---

## Command
```bash
ping 8.8.8.8
```

### What it does
Tests raw IP connectivity without depending on DNS.

### Why it was relevant
Used conceptually to distinguish routing/internet problems from DNS problems.

### Expected result
Replies from 8.8.8.8 if the client has working connectivity to the internet.

### What success or failure indicates
- Success: routing and outbound connectivity are likely working
- Failure: internet routing, firewall, NAT, or upstream path may be broken

### Notes
Low risk.  
A more policy-neutral test target in some environments may be the ISP gateway or another known reachable IP.

---

## Command
```bash
ping example.com
```

### What it does
Tests both DNS resolution and connectivity.

### Why it was relevant
Used conceptually to determine whether hostname resolution was working after a raw IP ping test.

### Expected result
The hostname should resolve and the destination should reply.

### What success or failure indicates
- If `ping 8.8.8.8` works but this fails, DNS is the likely problem
- If both fail, the issue is probably broader than DNS

### Notes
Low risk.

---

## Command
```bash
nslookup example.com
```

### What it does
Queries DNS directly for a hostname.

### Why it was relevant
Implied for validating whether OPNsense Unbound DNS was reachable and resolving names correctly.

### Expected result
The command should return a valid DNS response from the intended resolver.

### What success or failure indicates
- Success: DNS service path is functioning
- Failure: resolver access, Unbound interface binding, access lists, or upstream resolution may be broken

### Notes
Low risk.

---

## Command
```bash
traceroute 8.8.8.8
```

### What it does
Shows the path packets take toward a destination on Unix-like systems.

### Why it was relevant
Implied for checking whether traffic was traversing the expected local gateway path.

### Expected result
The first hop should be the local router for that segment, followed by upstream path entries.

### What success or failure indicates
- Correct first hop confirms the expected default gateway
- Unexpected first hops can reveal hidden NAT, wrong gateway assignment, or routing asymmetry

### Notes
Low risk.

### Safer / platform note
On Windows, the equivalent is:

```bash
tracert 8.8.8.8
```

---

## Command
```bash
tracert 8.8.8.8
```

### What it does
Windows equivalent of `traceroute`.

### Why it was relevant
Suggested conceptually to verify that clients were using the correct gateway and path.

### Expected result
The first hop should be the local router for the client subnet.

### What success or failure indicates
- Correct path supports proper DHCP and routing
- Incorrect path suggests gateway or topology problems

### Notes
Low risk.

---

## Likely command used
```bash
arp -a
```

### What it does
Displays the ARP cache on many client systems.

### Why it was relevant
A likely troubleshooting step for checking IP-to-MAC relationships and detecting duplicate IP behavior or unexpected gateways.

### Expected result
The gateway IP should map to the expected OPNsense MAC address.

### What success or failure indicates
- Expected mapping supports correct layer-2 forwarding
- Flapping or unexpected MACs can suggest duplicate addressing or rogue infrastructure

### Notes
Low risk.

---

## OPNsense action
```bash
Diagnostics → States → Reset States
```

### What it does
Clears the firewall state table in OPNsense.

### Why it was relevant
Suggested after topology changes or interface-path changes to remove stale states that can produce state-violation logs or inconsistent connectivity.

### Expected result
Existing connections are briefly interrupted, then rebuild using current topology and policy.

### What success or failure indicates
- Improvement afterward suggests stale states contributed to the issue
- No improvement suggests the root cause is elsewhere

### Notes
Moderate operational impact.  
This is disruptive to active sessions and should be used carefully during production traffic.

---

## OPNsense action
```bash
Services → DHCPv4 → Leases
```

### What it does
Displays active DHCP leases on an interface.

### Why it was relevant
Used to verify that clients were receiving addresses from OPNsense rather than from a rogue DHCP server.

### Expected result
Affected clients should appear with addresses in the correct subnet.

### What success or failure indicates
- Expected leases support correct DHCP behavior
- Missing or inconsistent leases may indicate DHCP conflict or wrong segment placement

### Notes
Low risk.  
Read-only diagnostic view.

---

## OPNsense action
```bash
Services → Unbound DNS → General
```

### What it does
Controls Unbound DNS listener interfaces and resolver behavior.

### Why it was relevant
Discussed in detail because DNS issues can look like internet failures even when routing works.

### Expected result
Unbound should listen on the intended internal interfaces and permit the intended client subnets.

### What success or failure indicates
- Correct configuration allows reliable name resolution
- Misconfiguration can cause clients to appear “online but without internet”

### Notes
Low risk when reviewing.  
Changing settings may affect DNS for multiple subnets.

---

## OPNsense action
```bash
Firewall → Rules → LAN
```

### What it does
Shows and manages firewall rules for the LAN interface.

### Why it was relevant
A standard check when determining whether the problem is routing/firewall-related or truly layer-2-related.

### Expected result
A permissive LAN rule set should allow normal outbound traffic during basic troubleshooting.

### What success or failure indicates
- If rules are correct and the issue persists, the cause is more likely switching, DHCP, or DNS
- Misordered or missing rules can block traffic in ways that mimic network instability

### Notes
Moderate risk if modified.  
Firewall changes affect reachability immediately.

---

## OPNsense action
```bash
Firewall → NAT → Outbound
```

### What it does
Controls outbound NAT policy.

### Why it was relevant
Discussed when evaluating whether OPT-style routed networks were missing internet due to NAT configuration.

### Expected result
Internal subnets requiring internet access should be translated correctly on WAN.

### What success or failure indicates
- Correct NAT allows outbound internet access
- Missing NAT on a routed subnet breaks internet access even when local connectivity works

### Notes
Moderate risk if changed.  
Incorrect outbound NAT can disrupt all egress traffic.

---

## OPNsense action
```bash
Interfaces → Assignments / Interfaces → OPT1
```

### What it does
Assigns and configures routed interfaces such as OPT1.

### Why it was relevant
Used conceptually when determining whether a second router or AP on OPT1 should be routed or bridged.

### Expected result
OPT1 should have the intended subnet and service scope if used as a separate network.

### What success or failure indicates
- A healthy OPT1 with working clients suggests the main issue is elsewhere
- Misconfiguration would isolate clients on that segment

### Notes
Moderate risk if changed.  
Interface changes can interrupt connected devices.

---

## Switch action
```bash
QoS → Storm Control
```

### What it does
Applies per-port thresholds to suppress excessive broadcast, multicast, or unknown-unicast traffic on the TL-SG108E switches.

### Why it was relevant
This became the key stabilization step in the session.

### Expected result
Flood behavior should be limited enough to prevent LAN instability while still allowing normal traffic.

### What success or failure indicates
- Improvement after enabling or adjusting storm control suggests a layer-2 flood condition was contributing
- Overly aggressive thresholds may suppress legitimate traffic

### Notes
Moderate operational risk.  
Improper thresholds can interfere with legitimate traffic such as discovery or multicast-heavy applications.

---

## Switch action
```bash
Loop Prevention / Loopback Detection
```

### What it does
Attempts to detect and suppress switching loops on the TL-SG108E platform.

### Why it was relevant
Reviewed because a loop or loop-like condition was one of the primary suspected causes of the LAN instability.

### Expected result
The switch should detect and mitigate loop conditions automatically.

### What success or failure indicates
- If enabled but instability persists, additional controls such as storm control may still be required
- A disabled state would increase exposure to accidental loops

### Notes
Low risk to enable.  
Important baseline protection in daisy-chained homelab switch topologies.

---

## Switch action
```bash
Advanced → Network → LAN
```

### What it does
Used on the Archer APs to set or review the management IP address.

### Why it was relevant
Static IP assignment for AP management was part of the cleanup and hardening discussion.

### Expected result
Each AP receives a stable management address in the correct subnet and outside the DHCP pool.

### What success or failure indicates
- Correct IPs make AP administration predictable
- Wrong subnet or overlapping DHCP use can cause management-plane confusion

### Notes
Low to moderate risk.  
Changing the management IP can briefly disconnect the web session until reconnecting to the new address.

---

## Switch / AP action
```bash
Factory reset via recessed reset button
```

### What it does
Restores the switch or AP to factory defaults.

### Why it was relevant
Discussed as a recovery method for TL-SG108E login access before it was discovered that the switches were still using the default credentials.

### Expected result
Default management access and default credentials are restored.

### What success or failure indicates
- Successful reset restores admin access
- It also removes custom configuration, requiring reconfiguration afterward

### Notes
High operational risk.  
Use only when necessary and after recording current settings if possible.
