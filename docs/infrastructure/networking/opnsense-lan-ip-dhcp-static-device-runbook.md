---
title: "OPNsense LAN IP Change & DHCP / Static Device Issues"
track: "infrastructure"
category: "networking"
type: "runbook"
logical_order: 30
date_rule: "Dates are removed from filenames, visible headings, indexes, generated metadata, and runbook body content."
---

# OPNsense LAN IP Change & DHCP / Static Device Issues

## Summary
Changed the LAN subnet on an OPNsense firewall and encountered issues where multiple devices, including Proxmox and OMV hosts, were not appearing on the network. Troubleshooting focused on DHCP configuration, static IP conflicts, and subnet mismatches.

## Environment
- Firewall: OPNsense
- Hypervisor: Proxmox
- Storage: OMV / OpenMediaVault NAS
- Network:
  - Old subnet: `192.168.1.0/24`
  - New subnet: `192.168.16.0/24`
- DHCP: OPNsense DHCPv4 server
- Devices:
  - Proxmox host(s)
  - OMV NAS
  - Other LAN clients using a mix of DHCP and static IPs

## Problem
After changing the LAN IP/subnet in OPNsense, several devices, notably Proxmox and OMV, were no longer visible or reachable on the LAN.

## Symptoms
- Devices did not appear in OPNsense DHCP leases.
- Some devices were missing from LAN visibility checks.
- Proxmox and OMV web interfaces were not reachable.
- Some DHCP clients worked while static-IP devices appeared to disappear.
- Static devices were likely still using the old LAN subnet.

## Actions Taken
1. Changed the OPNsense LAN IP using the console menu:
   - `2) Set interface IP address`
2. Reviewed the IPv6 console prompt:
   - `Configure IPv6 address LAN interface via WAN tracking?`
3. Determined that IPv6 WAN tracking should be skipped/disabled unless the ISP provides IPv6 Prefix Delegation.
4. Configured DHCPv4 for the LAN interface.
5. Discussed DHCP range planning:
   - Example DHCP pool: `192.168.16.21` through `192.168.16.254`
   - Reserved static range: `192.168.16.2` through `192.168.16.20`
6. Identified that several affected devices used static IPs.
7. Determined that static devices configured for the old subnet would not request DHCP leases and would not appear in the DHCP table.
8. Recommended updating static devices to the new subnet or converting them to DHCP reservations.
9. Discussed using a temporary LAN alias for the old subnet as a migration workaround if needed.

## Key Findings
- Static IP devices do not request DHCP leases, so they will not appear in OPNsense DHCP lease tables.
- Devices configured with old-subnet addresses such as `192.168.1.x` cannot directly communicate with a new LAN subnet such as `192.168.16.x/24`.
- A DHCP range of `.21-.254` leaves `.2-.20` available for manually assigned static infrastructure addresses.
- Gateway and DNS settings must also be updated on static devices.
- For a LAN using `192.168.16.1/24`, static devices should generally use:
  - IP address: `192.168.16.2` through `192.168.16.20`, if reserved for static use
  - Gateway: `192.168.16.1`
  - DNS: `192.168.16.1` or another intended DNS resolver

## Resolution
The likely root cause was that Proxmox, OMV, and other manually configured devices still had static IP settings from the old LAN subnet.

The corrective action is to update each static device to the new subnet. Example:

- OPNsense LAN IP: `192.168.16.1/24`
- Proxmox static IP: `192.168.16.2`
- OMV static IP: `192.168.16.3`
- Gateway: `192.168.16.1`
- DNS: `192.168.16.1` or another configured DNS resolver

The DHCP range can safely remain:

```text
192.168.16.21 - 192.168.16.254
```

This leaves:

```text
192.168.16.2 - 192.168.16.20
```

for manually configured infrastructure devices.

## Validation
Validation should include:

1. Confirm OPNsense LAN is reachable at the new IP:
   ```bash
   ping 192.168.16.1
   ```

2. Confirm static devices are reachable at their new addresses:
   ```bash
   ping <device-ip>
   ```

3. Confirm DHCP clients receive addresses in the expected range:
   ```text
   192.168.16.21 - 192.168.16.254
   ```

4. Confirm Proxmox and OMV web interfaces are reachable from a LAN client.

5. Check OPNsense ARP visibility:
   ```bash
   arp -a
   ```

6. For DHCP devices, confirm they appear under:
   ```text
   OPNsense GUI -> Services -> DHCPv4 -> Leases
   ```

## Follow-Up Tasks
- [ ] Update Proxmox static IP configuration to match the new LAN subnet.
- [ ] Update OMV static IP configuration to match the new LAN subnet.
- [ ] Verify all static devices use the correct gateway and DNS.
- [ ] Reserve `.2-.20` for infrastructure devices.
- [ ] Keep `.21-.254` for DHCP clients, or narrow the range if fewer DHCP addresses are needed.
- [ ] Consider converting static devices to DHCP reservations in OPNsense.
- [ ] Document the final IP allocation plan.
- [ ] Check for other DHCP servers on the network to avoid conflicts.
- [ ] Remove any temporary old-subnet aliases after migration is complete.

## Lessons Learned
- Changing the LAN subnet requires updating every static IP device.
- DHCP lease tables only show DHCP clients, not manually configured static devices.
- Static infrastructure devices should be kept outside the DHCP pool.
- DHCP reservations are often easier to manage than configuring static IPs directly on every device.
- When changing OPNsense LAN addressing, expect the management session to drop and reconnect using the new LAN IP.
- IPv6 WAN tracking should only be enabled if the ISP provides IPv6 Prefix Delegation and IPv6 is intentionally being used.

# Command Reference

## Command
```bash
ip addr show
```

### What it does
Displays network interfaces, assigned IP addresses, link state, and address scopes on Linux systems.

### Important arguments
No extra arguments were used.

### Why it was used
Used to verify the current IP address on OMV or another Linux-based device after the LAN subnet change.

### Expected result
The device should show an address in the new subnet, such as:

```text
192.168.16.x/24
```

### Failure indication
If the device still shows an address like:

```text
192.168.1.x/24
```

then it is still configured for the old subnet and will likely be unreachable from the new LAN.

---

## Command
```bash
ip a
```

### What it does
Short form of `ip addr show`. Displays interface and IP address information.

### Important arguments
No extra arguments were used.

### Why it was used
Useful on Proxmox because the management IP is usually assigned to a Linux bridge such as `vmbr0`.

### Expected result
The Proxmox bridge should show an address in the new subnet, such as:

```text
192.168.16.x/24
```

### Failure indication
If `vmbr0` still has the old subnet, Proxmox management will not be reachable from the new LAN.

---

## Command
```bash
arp -a
```

### What it does
Displays the ARP table, showing IP-to-MAC mappings for devices visible at Layer 2.

### Important arguments
No extra arguments were used.

### Why it was used
Used to check whether OPNsense or another host can see devices on the LAN even if those devices are not listed in DHCP leases.

### Expected result
Reachable LAN devices should appear with their IP and MAC address.

### Failure indication
If Proxmox or OMV do not appear, they may be disconnected, on the wrong subnet, using the wrong VLAN, powered off, or otherwise unreachable at Layer 2/Layer 3.

---

## Command
```cmd
ipconfig /release
ipconfig /renew
```

### What it does
Releases and renews a DHCP lease on Windows.

### Important arguments
- `/release`: drops the current DHCP lease.
- `/renew`: requests a new DHCP lease.

### Why it was used
Useful after changing the OPNsense LAN IP or DHCP range so Windows clients request an address from the new subnet.

### Expected result
The Windows client receives an address in the new DHCP range, such as:

```text
192.168.16.21 - 192.168.16.254
```

### Failure indication
If the client gets an APIPA address like `169.254.x.x`, it did not receive a DHCP response.

---

## Command
```bash
sudo dhclient -r && sudo dhclient
```

### What it does
Releases and renews a DHCP lease on many Linux systems using `dhclient`.

### Important arguments
- `-r`: releases the current lease.
- `&&`: runs the second command only if the first succeeds.
- `dhclient`: requests a new DHCP lease.

### Why it was used
Useful for Linux clients that need to request a new IP from OPNsense after the LAN subnet change.

### Expected result
The client receives an IP in the new DHCP range.

### Failure indication
If no lease is assigned, DHCP may be disabled, misconfigured, blocked, or the client may not be connected to the correct LAN.

---

## Likely Command Used
```bash
ping 192.168.16.1
```

### What it does
Tests ICMP reachability to the OPNsense LAN gateway.

### Important arguments
- `192.168.16.1`: example OPNsense LAN IP after the subnet change.

### Why it was used
Used to confirm that a client can reach the firewall on the new LAN address.

### Expected result
Successful replies indicate the gateway is reachable.

### Failure indication
Failure may indicate:
- Client is on the wrong subnet.
- Client has incorrect gateway settings.
- OPNsense LAN IP is configured differently.
- Cabling, switch, VLAN, or interface assignment is wrong.
- ICMP is blocked, though default LAN behavior usually allows this.

---

## Likely Command Used
```bash
ping <client-ip>
```

### What it does
Tests reachability to another LAN device.

### Important arguments
- `<client-ip>`: replace with the IP address of the device being tested.

### Why it was used
Used to verify that Proxmox, OMV, or another LAN device is reachable after updating static IP settings.

### Expected result
Successful replies confirm basic network connectivity.

### Failure indication
Failure may indicate:
- Device has the wrong static IP.
- Device has the wrong subnet mask.
- Device has the wrong gateway.
- Device is offline.
- Device is on the wrong switch port or VLAN.
- Host firewall blocks ICMP.

---

## OPNsense Console Action
```text
2) Set interface IP address
```

### What it does
Runs the OPNsense console wizard for assigning or changing an interface IP address.

### Important prompts
Typical prompts include:
- Select interface, such as LAN.
- Enter IPv4 address.
- Enter subnet bit count, such as `24`.
- Configure upstream gateway, usually skipped for LAN.
- Configure IPv6 via WAN tracking.
- Configure DHCP range.

### Why it was used
Used to change the LAN IP address when configuring the OPNsense LAN subnet.

### Expected result
OPNsense applies the new LAN IP and optionally enables DHCP on that interface.

### Failure or risk
Changing the LAN IP can immediately disconnect the current management session. The administrator must reconnect using the new LAN address.

---

## OPNsense DHCP Range Example
```text
192.168.16.21 - 192.168.16.254
```

### What it does
Defines the pool of IPv4 addresses OPNsense can hand out to DHCP clients.

### Why it was used
This range allows DHCP clients to receive addresses while keeping `.2-.20` available for manually assigned infrastructure devices.

### Expected result
DHCP clients receive addresses from `.21` through `.254`.

### Failure or risk
If the range overlaps manually configured static IPs, duplicate IP conflicts can occur.

---

## Reserved Static IP Range Example
```text
192.168.16.2 - 192.168.16.20
```

### What it does
Defines an address block outside the DHCP pool for manually configured infrastructure devices.

### Why it was used
Useful for systems such as:
- Proxmox hosts
- OMV NAS
- Access points
- Printers
- Switch management IPs
- Other always-on infrastructure

### Expected result
Static infrastructure devices do not conflict with DHCP clients.

### Failure or risk
If a static device is accidentally configured inside the DHCP pool, OPNsense may hand the same IP to another device.

---

## Optional OPNsense Migration Approach: Temporary LAN Alias

### Likely GUI Path
```text
Interfaces -> Virtual IPs -> Settings
```

or depending on OPNsense version and configuration:

```text
Interfaces -> LAN
```

### What it does
Adds an additional IP/subnet to the LAN interface so OPNsense can temporarily communicate with devices still on the old subnet.

### Why it may be used
Useful when static devices are still configured for the old subnet and cannot be reached after the main LAN subnet changes.

### Expected result
Devices on both old and new subnets may be reachable long enough to migrate their static IP settings.

### Risk
Do not leave temporary old-subnet aliases in place permanently unless intentionally designed. It can complicate routing, firewall policy, DNS assumptions, and troubleshooting.
