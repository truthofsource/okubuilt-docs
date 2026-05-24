---
title: "Configure an Additional OPT2 LAN in OPNsense"
track: "infrastructure"
category: "networking"
type: "runbook"
logical_order: 40
date_rule: "Dates are removed from filenames, visible headings, indexes, generated metadata, and runbook body content."
---

# Configure an Additional OPT2 LAN in OPNsense

## Summary
This work session focused on adding a second internal LAN segment on an `OPT2` interface in OPNsense. The goal was to assign a new interface, give it its own IPv4 subnet, optionally enable DHCP, allow traffic with firewall rules, and provide Internet access through outbound NAT when required.

## Environment
- **Firewall/Router:** OPNsense
- **Feature area:** Interface assignment, LAN segmentation, DHCP, firewall policy, outbound NAT
- **Interface involved:** `OPT2` or an available unassigned NIC
- **Example subnet used in planning:** `192.168.2.0/24`
- **Example interface IP used in planning:** `192.168.2.1/24`

## Problem
A new internal network needed to be created on another physical or logical interface in OPNsense so that devices connected to that segment could function as a separate LAN.

## Symptoms
No outage or error condition was recorded in this chat.

This was a configuration request, not a live troubleshooting session. The discussion did note one expected platform behavior:

- New interfaces in OPNsense are typically blocked by default until firewall rules are added.

## Actions Taken
1. Reviewed the process to assign an available interface as `OPT2` in OPNsense.
2. Outlined enabling the new interface and configuring it with a static IPv4 address.
3. Described optional DHCP server configuration for the new subnet.
4. Added a basic allow rule on the `OPT2` interface so clients on that network could pass traffic.
5. Documented outbound NAT setup for Internet access if automatic behavior did not already cover the new subnet.

### Important UI flow
Assign the interface:

```text
Interfaces -> Assignments
```

Purpose: Add and map an available NIC to `OPT2`.

Enable and configure the interface:

```text
Interfaces -> OPT2
```

Purpose: Enable the interface and assign its static IPv4 address.

Optional DHCP configuration:

```text
Services -> DHCPv4 -> OPT2
```

Purpose: Hand out IP addresses automatically to clients on the OPT2 subnet.

Firewall policy for OPT2:

```text
Firewall -> Rules -> OPT2
```

Purpose: Allow traffic from the new LAN, since new interfaces are restricted by default.

Outbound NAT when needed:

```text
Firewall -> NAT -> Outbound
```

Purpose: Ensure the new subnet is translated out the WAN for Internet access.

## Key Findings
- Creating an additional LAN in OPNsense is not just an interface task; it usually requires work in four areas:
  - interface assignment
  - interface addressing
  - firewall rules
  - DHCP and/or NAT, depending on desired behavior
- A newly assigned internal interface will not behave like an existing LAN until access rules are added.
- A separate subnet must be assigned to the new interface. The example given was:
  - interface IP: `192.168.2.1/24`
  - DHCP pool example: `192.168.2.100 - 192.168.2.200`
- Internet access for the new network may require explicit outbound NAT configuration if the firewall is not already handling the new subnet automatically.

## Resolution
A reusable runbook was defined for bringing up an `OPT2` LAN in OPNsense:

1. Assign an unused interface.
2. Enable it as `OPT2`.
3. Give it a static IPv4 address on a new subnet.
4. Enable DHCP if client auto-addressing is desired.
5. Add at least one pass rule on `OPT2`.
6. Add outbound NAT for the subnet if needed.

## Validation
No validation results were recorded in the chat.

Expected validation steps would be:

- A client connected to the `OPT2` network receives an IP address in the expected range.
- The client uses the `OPT2` interface IP as its gateway.
- The client can reach allowed destinations according to firewall policy.
- The client can reach the Internet if outbound NAT is correctly in place.

## Follow-Up Tasks
- Confirm which physical NIC or VLAN-backed interface should be used for `OPT2`.
- Verify whether outbound NAT is already automatic before creating manual rules.
- Decide whether `OPT2` should have unrestricted access or limited access to other internal networks.
- Add DNS policy as needed for the new segment.
- Document the purpose of the new network, such as lab, guest, IoT, or management.

## Lessons Learned
- In OPNsense, interface assignment alone does not make a new LAN usable.
- Firewall policy is a required part of bringing a new segment online.
- DHCP is optional, but practical for client networks.
- NAT requirements depend on the firewall’s outbound NAT mode.
- Clean network design starts with a distinct subnet and a clear policy boundary.

---

# Command Reference

## Command
```text
Interfaces -> Assignments
```

### What it does
Opens the OPNsense interface assignment page, where physical or virtual NICs can be mapped to logical interfaces such as `LAN`, `OPT1`, or `OPT2`.

### Why it was used
This is the starting point for creating a second LAN on a new interface.

### Expected result
An available interface is added and appears as `OPT2` or another assignable optional interface.

### Success or failure meaning
- **Success:** The new interface becomes available for configuration.
- **Failure:** No spare NIC is available, or the wrong NIC is selected.

### Notes
This is a UI action, not a shell command.

---

## Command
```text
Interfaces -> OPT2
```

### What it does
Opens the configuration page for the newly assigned `OPT2` interface.

### Why it was used
To enable the interface and assign it a static IPv4 address.

### Expected result
`OPT2` is enabled and bound to a dedicated subnet such as `192.168.2.1/24`.

### Success or failure meaning
- **Success:** The interface is active and can act as the gateway for its subnet.
- **Failure:** Clients on that segment will not have a functioning gateway or may not be able to communicate at all.

### Notes
Use a subnet that does not overlap with existing LANs, VLANs, VPNs, or upstream networks.

---

## Command
```text
Services -> DHCPv4 -> OPT2
```

### What it does
Opens the DHCP server settings for the `OPT2` interface.

### Why it was used
To optionally provide automatic IP addressing to clients on the new LAN.

### Expected result
Clients connected to `OPT2` receive addresses from a configured pool such as `192.168.2.100 - 192.168.2.200`.

### Success or failure meaning
- **Success:** Clients obtain an IP, gateway, and other DHCP options automatically.
- **Failure:** Clients may self-assign addresses or require manual static configuration.

### Notes
DHCP is not required for the interface to work, but it is usually needed for a normal client LAN.

---

## Command
```text
Firewall -> Rules -> OPT2
```

### What it does
Opens firewall policy management for the `OPT2` interface.

### Why it was used
New interfaces are generally not useful until traffic is explicitly allowed. A pass rule was recommended to allow traffic from `OPT2 net`.

### Expected result
Traffic originating from the new subnet is allowed according to the configured rule set.

### Success or failure meaning
- **Success:** Clients on `OPT2` can reach permitted destinations.
- **Failure:** Traffic appears blocked even though IP addressing is correct.

### Notes
A broad initial rule such as:

- source: `OPT2 net`
- destination: `any`
- protocol: `any`

is convenient for bring-up, but should be tightened later if segmentation matters.

---

## Command
```text
Firewall -> NAT -> Outbound
```

### What it does
Opens outbound NAT configuration.

### Why it was used
To ensure the `OPT2` subnet is translated to the WAN address for Internet access when automatic NAT does not already include it.

### Expected result
Traffic from the `OPT2` subnet is NATed correctly when leaving the WAN interface.

### Success or failure meaning
- **Success:** Clients on `OPT2` can reach external Internet destinations.
- **Failure:** Clients may reach local networks but fail to access the Internet.

### Notes
The documented workflow suggested changing to **Hybrid Outbound NAT** and adding a rule for the `192.168.2.0/24` subnet if needed.

This is policy-impacting and should be changed carefully.

---

## Command
```text
Example interface IPv4 address: 192.168.2.1/24
```

### What it does
Defines the gateway IP and subnet mask for the `OPT2` network.

### Why it was used
A new LAN needs its own unique subnet and interface address.

### Expected result
Hosts on `OPT2` use this address as their default gateway.

### Success or failure meaning
- **Success:** Clients can route through OPNsense.
- **Failure:** Overlapping or incorrect subnetting causes routing and reachability problems.

### Notes
This was an example value from the chat, not a confirmed production address.

---

## Command
```text
Example DHCP range: 192.168.2.100 - 192.168.2.200
```

### What it does
Defines the address pool offered by the DHCP server on `OPT2`.

### Why it was used
To provide a practical example range for a client network.

### Expected result
Clients receive leases within the configured range.

### Success or failure meaning
- **Success:** Clients obtain usable addresses.
- **Failure:** DHCP conflicts, wrong subnetting, or exhausted leases can prevent client connectivity.

### Notes
Reserve space outside the DHCP pool for static hosts if needed.

---

## Command
```text
Hybrid Outbound NAT
```

### What it does
Allows OPNsense to keep automatic outbound NAT behavior while also permitting manual NAT rules.

### Why it was used
It is a practical middle ground when only one new subnet needs explicit outbound NAT treatment.

### Expected result
Existing automatic NAT behavior remains intact while the new subnet can be added manually.

### Success or failure meaning
- **Success:** The new network gains Internet access without fully replacing automatic NAT handling.
- **Failure:** Incorrect NAT mode selection can lead to missing translations or unexpected traffic behavior.

### Notes
This is safer than switching blindly to full manual mode unless there is a strong reason to manage every outbound NAT rule yourself.
