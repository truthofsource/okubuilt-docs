---
title: "Ceph Monitor Crash Loop on `mainframe`"
track: "infrastructure"
category: "storage"
type: "runbook"
logical_order: 30
date_rule: "Dates are removed from filenames, visible headings, indexes, generated metadata, and runbook body content."
---

# Ceph Monitor Crash Loop on `mainframe`

## Summary
Troubleshooting a Ceph monitor (`ceph-mon`) crash loop on the `mainframe` node in a Proxmox + Ceph homelab cluster. The monitor repeatedly aborted during cluster probe/sync operations, preventing it from starting and participating in quorum.

## Environment
- **Platform:** Proxmox VE cluster
- **Storage:** Ceph
- **Node affected:** `mainframe`
- **Service:** `ceph-mon@mainframe` (Ceph monitor daemon)
- **Network:** 192.168.16.x cluster network
- **Cluster type:** Multi-node Ceph cluster assumed based on prior homelab context

## Problem
The Ceph monitor on node `mainframe` failed to start and entered a crash loop, preventing it from participating in cluster quorum.

## Symptoms
The system logs showed repeated monitor crashes and systemd restart failures:

```text
ceph-mon@mainframe.service: Main process exited, code=killed, status=6/ABRT
ceph-mon@mainframe.service: Failed with result 'signal'
ceph-mon@mainframe.service: Start request repeated too quickly
Failed to start ceph-mon@mainframe.service - Ceph cluster monitor daemon.
```

The crash stack trace included monitor probe and sync functions:

```text
Monitor::sync_start(...)
Monitor::handle_probe_reply(...)
Monitor::handle_probe(...)
Monitor::dispatch_op(...)
Monitor::_ms_dispatch(...)
```

Systemd also reported:

```text
Scheduled restart job, restart counter is at 6.
```

## Actions Taken
1. Reviewed the Ceph monitor crash output from `mainframe`.
2. Identified that the crash occurred during Ceph monitor probe/sync handling.
3. Interpreted `status=6/ABRT` as a deliberate abort by the Ceph process rather than a normal exit.
4. Considered likely causes:
   - Corrupted monitor database / monstore
   - Inconsistent monitor state
   - Monmap or FSID mismatch
   - Monitor network communication problems
   - Resource pressure from nearby workload activity
5. Discussed whether installing a VM could have caused the issue.

## Key Findings
- The monitor crashed during the `handle_probe` / `sync_start` path, which is involved in communication and synchronization between Ceph monitors.
- `status=6/ABRT` indicates a `SIGABRT`, meaning the process intentionally aborted, commonly because an internal assertion failed.
- This type of crash is often associated with an inconsistent monitor state, corrupted monitor store, or cluster metadata mismatch.
- Installing a VM normally should not directly crash a Ceph monitor.
- A VM installation could be related only indirectly if it affected:
  - Physical disks used by Ceph
  - Network bridge or cluster communication
  - Node resources such as RAM or CPU
  - Ceph packages, configuration, FSID, or monmap state

## Resolution
No final repair was completed in this chat. The issue remained in the investigation stage.

The most likely root cause was identified as one of the following:

1. Corrupted or inconsistent Ceph monitor database at:

   ```text
   /var/lib/ceph/mon/ceph-mainframe
   ```

2. Mismatch between the monitor’s local state and the rest of the cluster, such as a monmap, monitor address, or FSID inconsistency.

3. Less likely, but possible: an indirect side effect from recent VM work if that work changed disk layout, network configuration, or consumed enough system resources to destabilize Ceph services.

## Validation
Validation was not completed in this session.

Recommended validation after repair:

```bash
ceph -s
```

Purpose: Confirm the cluster health state and verify that monitors are in quorum.

Expected healthy result:
- Ceph reports quorum established
- `mainframe` appears as an active monitor if it was re-added successfully
- No repeating crash loop in systemd logs

Additional service validation:

```bash
systemctl status ceph-mon@mainframe
```

Purpose: Confirm the monitor service is active and no longer crash looping.

## Follow-Up Tasks
- Check the full monitor logs before the stack trace for the first real error.
- Confirm whether other monitors still have quorum.
- Verify monitor data directory exists and appears intact.
- Compare Ceph versions across all nodes.
- Verify monitor IP addresses and cluster network reachability.
- Confirm monitor ports are reachable between nodes:
  - TCP 3300
  - TCP 6789
- If corruption is confirmed, consider repairing the monstore.
- If the cluster has healthy quorum from other monitors, consider removing and re-adding the `mainframe` monitor.
- Review any recent VM installation steps to ensure no Ceph disks, bridges, or cluster network settings were modified.

## Lessons Learned
- A Ceph monitor crash during `handle_probe` or `sync_start` usually points toward monitor synchronization, quorum, or local monitor database problems.
- `SIGABRT` means Ceph intentionally stopped itself after detecting an unsafe condition.
- Installing a VM does not normally affect Ceph monitor health.
- VM work can indirectly affect Ceph if it changes storage, network, or resource availability.
- In a Proxmox + Ceph homelab, keep clear separation between:
  - VM installation disks
  - Ceph OSD disks
  - Ceph monitor state
  - Proxmox host storage
- Maintaining at least three healthy monitors improves cluster resilience and makes monitor recovery safer.

---

# Command Reference

## Command

```bash
journalctl -u ceph-mon@mainframe -n 100 -f
```

### What it does
Shows the last 100 log entries for the `ceph-mon@mainframe` systemd service and follows new log output live.

### Important flags and arguments
- `journalctl`: Reads systemd journal logs.
- `-u ceph-mon@mainframe`: Filters logs to the specific Ceph monitor service on `mainframe`.
- `-n 100`: Shows the last 100 lines.
- `-f`: Follows new logs in real time.

### Why it was used
This command is useful when a Ceph monitor is crash looping and you need to see the exact errors immediately before and during the crash.

### Expected result
A useful log stream showing:
- Monitor startup
- Probe/sync activity
- Database errors
- Assertion failures
- Systemd restart events

### Success or failure meaning
- **Success:** Logs show the cause or at least the crash pattern.
- **Failure:** If no logs appear, the service may not be starting, the unit name may be wrong, or logs may have rotated.

### Risk
Low. This is read-only.

---

## Command

```bash
ceph -s
```

### What it does
Shows the overall Ceph cluster status.

### Important output areas
- Cluster health
- Monitor quorum
- Manager status
- OSD count and state
- Pool and placement group health

### Why it was used
This command would determine whether the rest of the cluster is healthy and whether the `mainframe` monitor is participating in quorum.

### Expected result
A healthy cluster should show something like:
- `HEALTH_OK` or a clearly explained warning
- Multiple monitors in quorum
- OSDs up and in

### Success or failure meaning
- **Success with quorum:** The cluster can still make decisions and recover the failed monitor more safely.
- **Failure or no quorum:** Monitor failure may be more serious and recovery must be handled carefully.

### Risk
Low. This is read-only.

---

## Command

```bash
systemctl status ceph-mon@mainframe
```

### What it does
Displays the current systemd status of the Ceph monitor service on `mainframe`.

### Important flags and arguments
- `systemctl status`: Shows service state, recent logs, process ID, and failure reason.
- `ceph-mon@mainframe`: The instance-specific Ceph monitor unit for the `mainframe` node.

### Why it was used
This command is useful to confirm whether the monitor is active, failed, restarting, or blocked by systemd restart limits.

### Expected result
For a healthy monitor:
```text
Active: active (running)
```

For this failure scenario:
```text
Active: failed
Result: signal
status=6/ABRT
```

### Success or failure meaning
- **Active/running:** Monitor started successfully.
- **Failed with signal:** Monitor crashed or aborted.
- **Start request repeated too quickly:** Systemd stopped trying because the service failed too many times in a short period.

### Risk
Low. This is read-only.

---

## Likely Command Used

```bash
ls -lh /var/lib/ceph/mon/ceph-mainframe
```

### What it does
Lists the Ceph monitor data directory for the `mainframe` monitor.

### Important flags and arguments
- `ls`: Lists files.
- `-l`: Long listing format.
- `-h`: Human-readable file sizes.
- `/var/lib/ceph/mon/ceph-mainframe`: The expected monitor data directory.

### Why it would be used
To confirm that the monitor data directory exists and contains monitor database files.

### Expected result
The directory should exist and contain monitor store data.

### Success or failure meaning
- **Directory exists with data:** Monitor store is present, but may still be corrupt.
- **Directory missing:** The monitor may not have been initialized or the data was removed.
- **Permission errors:** Ownership or permissions may be wrong.

### Risk
Low. This is read-only.

---

## Potential Future Repair Command

```bash
ceph-monstore-tool /var/lib/ceph/mon/ceph-mainframe store repair
```

### What it does
Attempts to repair the Ceph monitor’s local database.

### Important flags and arguments
- `ceph-monstore-tool`: Ceph utility for inspecting or repairing monitor stores.
- `/var/lib/ceph/mon/ceph-mainframe`: Target monitor store path.
- `store repair`: Attempts repair of the monitor store.

### Why it would be used
If logs indicate RocksDB/LevelDB corruption or monitor store inconsistency.

### Expected result
The tool attempts to repair the monitor store so the monitor can start again.

### Success or failure meaning
- **Success:** The monitor may be able to start again.
- **Failure:** The store may be too damaged or the issue may be unrelated to local DB corruption.

### Risk
Medium. This modifies monitor data. Back up the monitor directory first if possible.

### Safer alternative
If the rest of the cluster has healthy quorum, it may be safer to remove and re-add the affected monitor instead of repairing the local store.

---

## Potential Future Command

```bash
ceph mon remove mainframe
```

### What it does
Removes the `mainframe` monitor from the Ceph monitor map.

### Why it would be used
If the cluster has healthy quorum without `mainframe`, removing and re-adding the monitor can be safer than repairing a corrupted local store.

### Expected result
The monitor is removed from the monitor map.

### Success or failure meaning
- **Success:** Cluster no longer expects `mainframe` to participate as a monitor.
- **Failure:** The cluster may not have quorum, the monitor name may be incorrect, or permissions may be insufficient.

### Risk
High if quorum is already fragile. Do not remove monitors casually in a degraded cluster.

### Safer practice
Run `ceph -s` first and confirm the remaining monitors have quorum.

---

## Potential Future Command

```bash
ceph mon add mainframe 192.168.16.11
```

### What it does
Adds `mainframe` back to the Ceph monitor map with the specified IP address.

### Important arguments
- `mainframe`: Monitor name.
- `192.168.16.11`: Monitor IP address, based on prior homelab addressing context.

### Why it would be used
To reintroduce the `mainframe` monitor after removing or rebuilding it.

### Expected result
The cluster records `mainframe` as a monitor at the specified address.

### Success or failure meaning
- **Success:** The monitor map is updated.
- **Failure:** IP mismatch, quorum issues, or existing stale monitor state may need cleanup.

### Risk
Medium. Incorrect monitor IPs can cause quorum or connectivity issues.

---

## Potential Future Command

```bash
ceph --version
```

### What it does
Displays the installed Ceph version.

### Why it would be used
To verify whether all nodes are running compatible Ceph versions.

### Expected result
All Proxmox/Ceph nodes should report the same major Ceph release.

### Success or failure meaning
- **Same versions:** Version mismatch is less likely.
- **Different versions:** Monitor compatibility or feature mismatch may be involved.

### Risk
Low. This is read-only.

---

## Potential Future Command

```bash
dpkg -l | grep ceph
```

### What it does
Lists installed Debian packages containing `ceph` in the package name.

### Important parts
- `dpkg -l`: Lists installed packages.
- `grep ceph`: Filters output for Ceph packages.

### Why it would be used
To compare Ceph package versions across Proxmox nodes.

### Expected result
Ceph packages should generally match across cluster nodes.

### Success or failure meaning
- **Consistent versions:** Package mismatch is less likely.
- **Inconsistent versions:** Upgrade mismatch may need correction.

### Risk
Low. This is read-only.
