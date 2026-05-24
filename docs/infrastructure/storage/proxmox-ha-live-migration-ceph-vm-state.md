---
title: "Proxmox HA Failover vs Live Migration with Ceph-Backed VM Storage"
track: "infrastructure"
category: "storage"
type: "runbook"
logical_order: 40
date_rule: "Dates are removed from filenames, visible headings, indexes, generated metadata, and runbook body content."
---

# Proxmox HA Failover vs Live Migration with Ceph-Backed VM Storage

## Summary
This work session clarified how Proxmox VM migration behaves when a VM uses Ceph-backed shared storage. The goal was to understand whether migrating a VM from `pve1` to `pve2` should be effectively instantaneous, whether a `16 GiB` transfer indicated disk movement, and how this differs from High Availability (HA) failover when a node goes down.

The discussion also reviewed an actual Proxmox migration log for VM `110`, identified that the transfer shown was VM memory state rather than disk, and distinguished between:
- planned live migration while the source node remains healthy
- HA restart behavior after node failure

---

## Environment
- **Platform:** Proxmox VE cluster
- **Nodes involved:** `pve1`, `pve2`
- **VM involved:** `VM 110`
- **Shared storage context:** Ceph-backed shared storage
  - Ceph RBD is the most likely VM disk backend in this scenario
  - CephFS was also discussed conceptually as shared storage
- **Migration type discussed:**
  - live migration
  - HA failover / restart on another node
- **Cluster networking referenced:** `192.168.16.x`
  - Example remote node address in log: `192.168.16.13`
- **VM memory size observed in migration log:** `16.0 GiB`

---

## Problem
There was uncertainty about what Proxmox transfers during a VM migration when the VM uses shared Ceph storage. Specifically:
- whether Ceph or CephFS makes migration effectively instantaneous
- whether the migration process should avoid transferring `16 GiB`
- whether Proxmox HA would still "move" the VM automatically if the source node fails

---

## Symptoms
Observed migration log from Proxmox for VM `110`:

```text
[date removed] starting migration of VM 110 to node 'pve2' (192.168.16.13)
[date removed] starting VM 110 on remote node 'pve2'
[date removed] start remote tunnel
[date removed] ssh tunnel ver 1
[date removed] starting online/live migration on unix:/run/qemu-server/110.migrate
[date removed] set migration capabilities
[date removed] migration downtime limit: 100 ms
[date removed] migration cachesize: 2.0 GiB
[date removed] set migration parameters
[date removed] start migrate command to unix:/run/qemu-server/110.migrate
[date removed] migration active, transferred 107.8 MiB of 16.0 GiB VM-state, 114.9 MiB/s
...
[date removed] migration active, transferred 3.1 GiB of 16.0 GiB VM-state, 112.7 MiB/s
[date removed] ERROR: online migrate failure - interrupted by signal
[date removed] aborting phase 2 - cleanup resources
[date removed] migrate_cancel
```

Additional clarification from the operator:
- the migration was **manually cancelled**
- concern remained about what HA would do if `pve1` actually went down

---

## Actions Taken
1. Reviewed the expected behavior of Proxmox migration when VM disks are stored on shared Ceph storage.
2. Distinguished between:
   - shared disk access through Ceph
   - RAM transfer required during live migration
3. Examined the migration log line containing:
   ```text
   16.0 GiB VM-state
   ```
4. Interpreted the transfer rate values (`~110–140 MiB/s`) as memory-state transfer consistent with a likely `1 Gbps` migration path.
5. Identified the failure message:
   ```text
   ERROR: online migrate failure - interrupted by signal
   ```
6. Determined that this specific migration failure did not indicate a Ceph or storage problem because it was manually cancelled.
7. Clarified the operator’s actual question: not live migration behavior, but **HA failover behavior when a node goes down**.
8. Explained how Proxmox HA behaves with Ceph-backed shared storage after node failure:
   - the VM is restarted on another eligible node
   - RAM state is not preserved
   - the VM boots from the existing shared Ceph disk

---

## Key Findings
- In Proxmox live migration, the value shown as `VM-state` refers to **RAM contents**, not VM disk size.
- A line such as:
  ```text
  transferred 3.1 GiB of 16.0 GiB VM-state
  ```
  indicates transfer of memory pages from source to destination during live migration.
- With Ceph-backed shared storage, the VM disk does **not** need to be copied from `pve1` to `pve2` during migration.
- Ceph reduces migration overhead by making VM storage available to both nodes, but it does **not** eliminate RAM transfer during live migration.
- Live migration is therefore **fast but not instantaneous**.
- If the source node fails unexpectedly, live migration cannot complete because the running in-memory VM state is lost with the source node.
- In an HA scenario, Proxmox does **not** perform a seamless migration after node failure. Instead, it:
  - detects node loss
  - selects another eligible node
  - starts the VM there using the same Ceph-backed disks
- HA failover with Ceph is effectively a **reboot on another node**, not a continuation of the exact prior in-memory execution state.
- The observed migration error in this session was not an infrastructure failure; it was caused by a manual cancellation.

---

## Resolution
The issue was resolved conceptually rather than through a configuration change.

Final understanding:
- the `16 GiB` shown in the migration log referred to **VM RAM**
- Ceph-backed shared storage avoids a full disk transfer during migration
- HA after node failure will **restart** the VM on another node instead of preserving the running state
- planned live migration and HA failover are separate behaviors and should not be interpreted the same way

Current status:
- no storage migration issue was identified
- no Ceph fault was indicated by the provided log
- the operator now has a correct model for how Proxmox migration and HA behave with Ceph-backed VM disks

---

## Validation
Success was confirmed by matching the migration log behavior to Proxmox live migration mechanics:

- `16.0 GiB VM-state` matched the VM’s memory allocation, not disk
- transfer rates aligned with expected network-based RAM copy behavior
- the failure reason matched a manual abort rather than storage or cluster failure
- the HA explanation was reconciled against the operator’s intended question:
  - no live handoff after node death
  - restart from shared Ceph storage on another eligible node

A useful validation command noted during the discussion was:

```bash
qm config 110 | grep memory
```

Purpose: confirm the VM’s configured memory size and compare it to the `VM-state` shown in migration logs.

---

## Follow-Up Tasks
- Confirm that VM `110` is on Ceph RBD shared storage rather than local-only storage.
- Review HA group membership and failover target eligibility for critical VMs.
- Test planned HA behavior with a controlled maintenance scenario rather than waiting for an actual node failure.
- Verify corosync quorum health and node fencing behavior so HA restart timing is understood ahead of an outage.
- Document which VMs are expected to tolerate reboot-style failover versus those requiring application-level clustering.
- If faster live migration is desired, evaluate migration network bandwidth between Proxmox nodes.

---

## Lessons Learned
- In Proxmox migration logs, `VM-state` means **memory state**, not disk.
- Ceph shared storage removes the need to copy VM disks during migration, but not RAM during live migration.
- HA failover after node loss is a **restart**, not a transparent continuation of execution.
- A migration log must be interpreted carefully before assuming a storage bottleneck.
- Manual cancellation can resemble migration failure in logs; operator actions should be ruled out before deeper troubleshooting.

---

# Command Reference

## Command
```bash
qm config 110 | grep memory
```

**What it does:**  
Displays the Proxmox VM configuration for VM `110` and filters for the memory entry.

**Important arguments:**  
- `qm config 110` — shows the configuration of VM `110`
- `grep memory` — limits output to lines containing `memory`

**Why it was used at that moment:**  
To verify whether the `16.0 GiB VM-state` shown in the migration log matched the VM’s configured RAM.

**Expected result:**  
A line similar to:

```text
memory: 16384
```

**What success or failure would indicate:**  
- If it shows `16384`, that confirms the migration log’s `16.0 GiB VM-state` refers to RAM.
- If it shows a different value, either the VM memory changed later or the log refers to a different runtime state.

**Platform relevance:**  
For Proxmox, this is a direct way to correlate migration behavior with VM resource configuration.

---

## Command
```bash
journalctl -r | head -n 40
```

**What it does:**  
Shows the most recent journal entries in reverse chronological order, limited to the newest 40 lines.

**Important arguments:**  
- `-r` — reverse order, newest first
- `head -n 40` — show the first 40 lines of that output

**Why it was suggested:**  
To quickly inspect recent system events around a migration failure or interruption.

**Expected result:**  
Recent logs from Proxmox services, SSH, kernel messages, or system daemons that may explain an aborted migration.

**What success or failure would indicate:**  
- Useful recent log entries can help identify whether a migration failure was due to service restart, SSH interruption, or other host-side events.
- If nothing relevant appears, more targeted journal queries are needed.

**Risk level:**  
Low risk. Read-only.

**Safer alternative:**  
A time-bounded `journalctl` query is usually cleaner for incident review.

---

## Command
```bash
journalctl -S "[date removed]" -U "[date removed]"
```

**What it does:**  
Queries system logs only for the specified time window.

**Important arguments:**  
- `-S` — start time
- `-U` — end time

**Why it was suggested:**  
To inspect logs specifically around the migration interruption time.

**Expected result:**  
A filtered set of entries from the exact incident window.

**What success or failure would indicate:**  
- Relevant service or network logs during the event window can identify the cause of interruption.
- If nothing appears, the event may not have been logged by the system journal or may require service-specific filtering.

**Platform relevance:**  
Useful during Proxmox troubleshooting to isolate cluster, SSH, or daemon activity around a specific failure.

**Risk level:**  
Low risk. Read-only.

---

## Command
```bash
journalctl -u pvedaemon -u pveproxy -u ssh -S "[date removed]" -U "[date removed]"
```

**What it does:**  
Shows logs for specific services in a defined time window.

**Important arguments:**  
- `-u pvedaemon` — Proxmox management daemon
- `-u pveproxy` — Proxmox web/API proxy
- `-u ssh` — SSH service
- `-S` / `-U` — time window bounds

**Why it was suggested:**  
To check whether the migration interruption came from Proxmox service behavior or an SSH tunnel problem.

**Expected result:**  
Service logs that may correlate with migration initiation, interruption, cancellation, or transport problems.

**What success or failure would indicate:**  
- Relevant service messages may confirm cancellation, daemon interruption, or transport loss.
- Lack of errors may suggest a manual abort or an event outside those services.

**Platform relevance:**  
In Proxmox, live migration depends heavily on management daemons and transport setup, so these logs are high-value for incident review.

**Risk level:**  
Low risk. Read-only.

---

## Command
```bash
pvecm status
```

**What it does:**  
Displays Proxmox cluster status, including quorum state and cluster membership.

**Why it was suggested:**  
To verify that the cluster was healthy if there were concerns about why migration or HA behavior might fail.

**Expected result:**  
Healthy quorum, visible nodes, and no obvious cluster membership issues.

**What success or failure would indicate:**  
- Healthy quorum supports normal HA and migration decisions.
- Loss of quorum or cluster instability can prevent HA actions or interfere with node coordination.

**Platform relevance:**  
This is one of the core cluster health commands in Proxmox.

**Risk level:**  
Low risk. Read-only.

---

## Command
```bash
ping -c 5 pve2
```

**What it does:**  
Sends five ICMP echo requests to `pve2` to confirm basic network reachability.

**Important arguments:**  
- `-c 5` — send 5 packets, then stop

**Why it was suggested:**  
To verify whether the destination node was reachable during migration troubleshooting.

**Expected result:**  
Five successful replies with stable latency.

**What success or failure would indicate:**  
- Successful replies indicate basic Layer 3 connectivity.
- Packet loss or failure indicates a possible network or host availability problem.

**Platform relevance:**  
Migration and HA both depend on reliable node-to-node communication, even when storage is shared through Ceph.

**Risk level:**  
Low risk. Read-only.

---

## Command
```bash
Likely command used: qm migrate 110 pve2 --online
```

**What it does:**  
Initiates a live migration of VM `110` from its current node to `pve2`.

**Important arguments:**  
- `qm migrate` — Proxmox VM migration command
- `110` — VM ID
- `pve2` — destination node
- `--online` — perform live migration while the VM remains running

**Why it was likely used:**  
The log clearly shows an online/live migration of VM `110` to `pve2`. Even if initiated from the GUI, this is the logical CLI equivalent.

**Expected result:**  
Proxmox starts the VM on the destination node, transfers the VM memory state, then briefly pauses and completes cutover.

**What success or failure would indicate:**  
- Success indicates healthy cluster communications, compatible VM configuration, and accessible shared storage.
- Failure can indicate transport interruption, node issues, manual cancellation, incompatible CPU/state conditions, or other migration blockers.

**Risk level:**  
Moderate. This affects a running VM.

**Safer alternative:**  
Use the Proxmox GUI for clearer visibility, or perform an offline migration during maintenance if seamless runtime continuity is not required.

**Platform relevance:**  
For Ceph-backed Proxmox VMs, this command usually transfers RAM state rather than copying disk storage.

---

## Command
```bash
Likely action used: Proxmox GUI migration cancel / abort
```

**What it does:**  
Cancels an in-progress migration task from the Proxmox interface.

**Why it was likely used:**  
The operator later confirmed the migration was manually cancelled.

**Expected result:**  
The migration task stops, cleanup occurs, and the task log may show messages such as:

```text
ERROR: online migrate failure - interrupted by signal
migrate_cancel
```

**What success or failure would indicate:**  
- If cancellation succeeds cleanly, the VM should remain in a stable state on the source node or be cleaned up appropriately depending on migration phase.
- If cancellation occurs at an unsafe point or coincides with other issues, follow-up validation of VM placement and status is required.

**Risk level:**  
Moderate. Cancelling migration interrupts a running administrative task and should be done deliberately.

**Safer alternative:**  
Prefer allowing a healthy migration to finish unless there is a clear reason to stop it.

---

## Command
```bash
Likely command used: ha-manager status
```

**What it does:**  
Displays the state of Proxmox HA resources and HA-managed services.

**Why it is relevant here:**  
Although not explicitly run in the chat, it is directly relevant to validating HA behavior after clarifying that the real question was about failover rather than live migration.

**Expected result:**  
A list of HA-managed resources, their states, and current node placement.

**What success or failure would indicate:**  
- If the VM appears as HA-managed and healthy, it is eligible for automated failover according to policy.
- If it is absent from HA management, the VM will not be automatically restarted elsewhere after node failure.

**Platform relevance:**  
This is a key Proxmox HA operational check.

**Risk level:**  
Low risk. Read-only.
