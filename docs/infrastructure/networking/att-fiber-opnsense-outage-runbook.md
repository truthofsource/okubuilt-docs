---
title: "AT&T Fiber Outage (ONT / OPNsense WAN Loss)"
track: "infrastructure"
category: "networking"
type: "runbook"
logical_order: 10
date_rule: "Dates are removed from filenames, visible headings, indexes, generated metadata, and runbook body content."
---

# AT&T Fiber Outage (ONT / OPNsense WAN Loss)

## Summary
Troubleshooting a sudden internet outage in a homelab environment using OPNsense with AT&T fiber. The issue was isolated to the upstream fiber connection (ONT) and resolved via power cycling.

---

## Environment
- Router/Firewall: OPNsense
- ISP: AT&T Fiber
- Gateway: BGW320
- ONT (Optical Network Terminal): External fiber termination device
- LAN: Homelab network (Proxmox cluster, Docker workloads, etc.)
- Topology:
  - Fiber → ONT → AT&T Gateway (BGW320 or passthrough) → OPNsense → LAN

---

## Problem
Complete loss of internet connectivity across the homelab network.

---

## Symptoms
- No internet access from LAN devices
- Likely failed external connectivity (e.g., ping to public IPs)
- ONT displayed a red light prior to recovery
- AT&T gateway not in normal solid white state during issue

---

## Actions Taken
1. Observed physical device status (ONT and AT&T gateway LEDs)
2. Performed a power cycle of the ONT
3. Allowed ONT to fully reinitialize and re-establish fiber link
4. Verified gateway returned to normal (solid white) state

---

## Key Findings
- Red light on ONT indicated Loss of Signal (LOS) or upstream fiber issue
- Issue was not caused by:
  - OPNsense configuration
  - Internal networking (LAN, VLANs, firewall rules)
- Likely causes:
  - Temporary ISP-side disruption
  - Optical signal drop or PON re-sync requirement
- AT&T fiber can exhibit MAC/session stickiness, requiring ONT reset to renegotiate connection

---

## Resolution
- Power cycling the ONT restored fiber signal and connectivity
- Network returned to normal operation without additional configuration changes

---

## Validation
- AT&T gateway returned to solid white (healthy state)
- Internet connectivity restored across LAN devices
- Implicit validation: upstream routing, DNS, and WAN connectivity functional

---

## Follow-Up Tasks
- Place ONT and gateway on a UPS to prevent transient outages
- Document WAN interface name on OPNsense for faster troubleshooting
- Capture logs during future outages:
  - `/var/log/system.log`
- Consider monitoring:
  - WAN gateway status (dpinger)
  - Interface flaps
- (Optional) Review AT&T passthrough / bypass configuration for stability

---

## Lessons Learned
- Physical layer issues can mimic higher-layer failures (DNS, routing, firewall)
- Always check ONT status lights first in fiber setups
- Power cycling ONT is often required due to:
  - PON re-authentication
  - ISP MAC/session binding behavior
- LED meanings differ:
  - BGW320: white = healthy
  - ONT: green = healthy, red = signal failure
- Avoid unnecessary troubleshooting of OPNsense until WAN link is confirmed up

---

# Command Reference

## Command
```bash
ping 1.1.1.1
```

### What it does
Tests basic IP connectivity to an external host (Cloudflare DNS).

### Why it was used
To determine whether the issue was:
- Layer 3 connectivity (WAN down), or
- DNS-related

### Expected Result
- Success → WAN is up, issue likely DNS
- Failure → WAN or upstream connectivity issue

---

## Command
```bash
ifconfig -a
```

### What it does
Displays all network interfaces and their status.

### Why it was relevant
Used to identify the WAN interface and check:
- Link state
- Assigned IP address

### Expected Result
- WAN interface should show:
  - `status: active`
  - Valid public IP

---

## Command
```bash
netstat -rn4 | grep ^default
```

### What it does
Displays the IPv4 routing table default gateway.

### Why it was relevant
Confirms whether a valid default route exists for outbound traffic.

### Expected Result
- Valid default gateway via WAN interface

---

## Command
```bash
/sbin/dhclient -r <wanif>
/sbin/dhclient <wanif>
```

### What it does
Releases and renews DHCP lease on the WAN interface.

### Why it was suggested
To recover WAN connectivity without rebooting hardware.

### Important Notes
- `<wanif>` = actual WAN interface (e.g., `igb0`, `ix0`)
- Safe to run

### Expected Result
- New IP lease assigned
- WAN connectivity restored

---

## Command
```bash
clog /var/log/system.log | tail -50
```

### What it does
Displays recent system logs on OPNsense.

### Why it was relevant
To check:
- DHCP failures
- Gateway status
- Interface errors

### Expected Result
- Successful DHCP lease messages
- No persistent WAN errors

---

## Command
```bash
configctl interface reconfigure wan
```

### What it does
Reinitializes the WAN interface in OPNsense.

### Why it was suggested
To recover from gateway or dpinger issues without rebooting.

### Expected Result
- WAN interface resets
- Gateway status restored

---

## Command
```bash
configctl unbound restart
```

### What it does
Restarts the Unbound DNS resolver.

### Why it was suggested
Used when:
- IP connectivity works
- DNS resolution fails

### Expected Result
- DNS resolution restored

---

## Command
```bash
drill cloudflare.com @1.1.1.1
```

### What it does
Performs a DNS lookup using a specific DNS server.

### Why it was suggested
To isolate DNS issues:
- Tests external DNS directly

### Expected Result
- Valid DNS response → DNS working
- Failure → DNS or upstream issue
