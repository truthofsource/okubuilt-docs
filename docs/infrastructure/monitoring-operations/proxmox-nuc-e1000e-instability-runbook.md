---
title: "Initial Investigation of Proxmox Host and VM Instability Under Container Load"
track: "infrastructure"
category: "monitoring-operations"
type: "runbook"
logical_order: 30
date_rule: "Dates are removed from filenames, visible headings, indexes, generated metadata, and runbook body content."
---

# Initial Investigation of Proxmox Host and VM Instability Under Container Load

## Summary
Troubleshooting began for a Proxmox node that became unresponsive while running a Debian Docker VM with many containers active. The first goal was to determine whether the issue was caused by kernel faults, guest instability, host overcommit, memory pressure, or storage/network dependencies.

## Environment
- Proxmox VE host: `pve1`
- Kernel observed in logs: `6.8.12-13-pve`
- VM: `debian-docker`
- Guest OS: Debian
- Workload: Docker / Docker Compose containers
- Host network:
  - physical NIC: `eno1`
  - bridge: `vmbr0`
- Ceph present in the environment
- Hardware platform later identified as Intel NUC8i7BEH
- CPU later identified as Intel Core i7-8559U

## Problem
The Proxmox host and the Docker VM became unresponsive after some runtime with most or all containers active.

## Symptoms
- Host and VM both became unresponsive.
- Previous boots ended uncleanly.
- No immediate panic, MCE, or OOM signature was obvious at the start of troubleshooting.
- The issue did not match prior bare-metal behavior, where the same or similar container workload had been stable.

## Actions Taken
1. Listed previous boots and inspected the prior boot’s kernel logs.
2. Filtered logs for warnings, errors, panic signatures, watchdog events, and hardware fault indicators.
3. Checked host memory, swap, CPU, and IO at a healthy moment.
4. Checked live kernel logs inside the Debian Docker VM.
5. Compared the VM-based deployment to the previously stable bare-metal Docker deployment.

Important commands used:
```bash
journalctl --list-boots
```
Purpose: identify which prior boot should be inspected.

```bash
journalctl -k -b -1
```
Purpose: inspect kernel messages from the previous boot.

```bash
journalctl -k -b -1 -p warning..alert
```
Purpose: reduce noise and focus on prior-boot kernel warnings and errors.

```bash
journalctl -k -b -1 | egrep -i 'panic|BUG:|Oops|Call Trace|hardware error|MCE|watchdog|soft lockup|hard lockup|NMI|reset|blocked for more than'
```
Purpose: search for classic crash and hardware-fault signatures.

```bash
free -h
swapon --show
vmstat 1 5
```
Purpose: check host RAM pressure, swap, and basic CPU/IO health.

```bash
sudo journalctl -kf
```
Purpose: watch live kernel messages inside the Docker VM.

## Key Findings
- Prior-boot warnings initially appeared mostly non-fatal:
  - SGX disabled in BIOS
  - CPU vulnerability warnings
  - ACPI thermal firmware warning
  - ZFS taint messages
  - journald corruption / unclean shutdown notice
- No early evidence of:
  - kernel panic
  - MCE / ECC-style hardware fault
  - watchdog soft lockup
  - guest OOM killer
- Live VM logs showed normal Docker bridge and veth lifecycle messages rather than guest kernel crashes.
- At this stage, the issue appeared more likely to be host-side or dependency-related than a Docker guest kernel fault.

## Resolution
No final resolution was reached in this phase. Troubleshooting continued into memory, thermals, and hardware-specific causes.

## Validation
- Prior boot logs were successfully collected and reviewed.
- VM live logs did not show guest kernel panic behavior.
- Early host checks did not reveal a simple OOM or swap-driven failure.

## Follow-Up Tasks
- Capture host telemetry closer to the actual failure window.
- Investigate thermal conditions under sustained load.
- Inspect previous-boot logs near the end of failed runtime.
- Continue checking for hardware- or driver-specific faults.

## Lessons Learned
- Unclean shutdown messages alone do not identify root cause.
- Docker bridge and veth events inside the guest are normal and should not be mistaken for guest kernel failure.
- Early triage should clearly separate:
  - guest failure
  - host failure
  - storage/network dependency failure

# Host Resource Review and Thermal Testing on pve1

## Summary
The next work session focused on determining whether the node was simply overcommitted or memory-starved. Host telemetry showed healthy RAM and swap usage, which shifted attention away from basic overcommit and toward thermals or platform-specific faults.

## Environment
- Proxmox host: `pve1`
- Hardware: Intel NUC8i7BEH
- CPU: Intel Core i7-8559U
- Host RAM: approximately 32 GiB
- Swap: 8 GiB configured
- VM: `debian-docker`
- VM sizing discussed:
  - 12 GiB RAM
  - 4 vCPUs
  - CPU type `x86-64-v3`
  - ballooning disabled

## Problem
The node still became unresponsive after running for a while, even though the container workload was not believed to be especially resource-intensive.

## Symptoms
- Host and VM became unresponsive after some runtime.
- Behavior was intermittent rather than a constant “load too high immediately” pattern.
- Prior theory that the node was simply RAM-starved became doubtful.

## Actions Taken
1. Checked host memory and swap usage while the node was healthy.
2. Reviewed `vmstat` output for swap activity and IO wait.
3. Installed `lm-sensors`.
4. Ran `sensors-detect`.
5. Checked baseline temperatures.
6. Monitored temperatures during heavier sustained load.

Important commands used:
```bash
free -h
swapon --show
vmstat 1 5
```
Purpose: verify whether the host was exhausting RAM or swapping.

```bash
apt-get install -y lm-sensors
```
Purpose: install host sensor tooling.

```bash
sensors-detect
```
Purpose: identify supported sensor drivers.

```bash
sensors
```
Purpose: read CPU, chipset, and NVMe temperatures.

```bash
watch -n2 sensors
```
Purpose: monitor temperatures continuously during load.

## Key Findings
- Host memory state was healthy when sampled:
  - about 31 GiB total
  - about 11 GiB used
  - about 19 GiB free
  - swap unused
- `vmstat` showed:
  - no swap-in / swap-out
  - low IO wait
  - plenty of idle CPU at the sampled moment
- This ruled out simple host RAM exhaustion as the immediate cause.
- `lm-sensors` found the `coretemp` driver and provided usable CPU telemetry.
- Initial temperatures were normal.
- Under sustained load, temperatures later spiked dramatically:
  - CPU package reached 99°C
  - at least one core also reached 99°C
- This confirmed that thermal stress was a real issue at least part of the time.

## Resolution
A real thermal problem was identified, but it was not yet proven to be the only root cause.

## Validation
- Host RAM and swap telemetry disproved the simple “memory starvation” theory.
- Sensor telemetry captured thermal throttle territory under load.

## Follow-Up Tasks
- Clean the NUC cooling path.
- Check fan profile and BIOS cooling settings.
- Consider re-pasting if necessary.
- Continue collecting post-crash logs because thermals did not fully explain all failures.

## Lessons Learned
- Verify resource-pressure assumptions with actual telemetry before changing VM sizing.
- Thermal issues can be real without explaining every outage.
- Sample both healthy state and sustained-load state before narrowing the failure domain.

# Thermal Instability Confirmed, Then Ruled Out as the Only Failure Mode

## Summary
Thermal testing confirmed the NUC could reach near-critical CPU temperatures under load. However, a later outage occurred while temperatures were normal, which proved a second failure mechanism existed.

## Environment
- Proxmox host: `pve1`
- Hardware: Intel NUC8i7BEH
- CPU: Intel Core i7-8559U
- Sensor source: `lm-sensors`

## Problem
Even after confirming the node could overheat, the node still later went down when temperatures were only in the mid-60°C range.

## Symptoms
- Under one sustained-load test:
  - package temperature hit 99°C
  - one core hit 99°C
- In a later failure:
  - package temperature was around 66°C
  - cores were around 62–68°C
- The node still went down.

## Actions Taken
1. Observed temperatures continuously during runtime.
2. Compared a high-thermal event to a later outage with normal temperatures.
3. Concluded that thermals were contributing but not the only issue.

Important command used:
```bash
watch -n2 sensors
```
Purpose: compare thermal behavior across different failure windows.

## Key Findings
- The node definitely reached throttle territory in one run.
- Another outage occurred at safe temperatures, so overheating was not the only explanation.
- Troubleshooting needed to pivot back to log-based fault analysis.

## Resolution
Thermals were kept as a real but partial issue. Post-crash log analysis became the next priority.

## Validation
- Two separate sensor observations showed:
  - one clearly thermal event
  - one non-thermal outage
- That split prevented a false conclusion that “temperature alone” was the whole problem.

## Follow-Up Tasks
- Keep thermal monitoring in place.
- Continue reviewing previous-boot logs after each crash.
- Improve cooling anyway, even if a second issue also exists.

## Lessons Learned
- Multiple independent fault domains can coexist on the same node.
- Do not stop at the first confirmed problem if later evidence contradicts a single-cause explanation.

# Previous-Boot Log Analysis Identified Intel e1000e NIC Hardware Hangs

## Summary
Targeted inspection of the previous boot’s final log lines revealed repeated Intel `e1000e` hardware hangs on `eno1`, followed immediately by Ceph socket closures. This established a strong link between node “death” and host network failure.

## Environment
- Proxmox host: `pve1`
- Hardware: Intel NUC8i7BEH
- NIC:
  - interface: `eno1`
  - driver: `e1000e`
- Bridge: `vmbr0`
- Ceph environment present:
  - monitor connectivity affected
  - MDS connectivity affected
- VM: `debian-docker`
- VM and cluster behavior dependent on host network stability

## Problem
The node still failed when temperatures were normal. The goal became distinguishing between:
- power loss
- kernel panic
- reboot/reset
- NIC failure
- Ceph/storage dependency failure

## Symptoms
Previous-boot logs ended with repeated messages such as:
- `e1000e 0000:00:1f.6 eno1: Detected Hardware Unit Hang`
- `libceph: mon3 ... socket closed`
- `libceph: mds0 ... socket closed`

The node appeared offline externally and required reboot.

## Actions Taken
1. Pulled the final lines from the previous boot’s kernel log.
2. Pulled previous-boot error and alert messages.
3. Searched the previous boot for panic, watchdog, MCE, reset, and reboot indicators.
4. Checked `last -x` to confirm reboot timing and uptime windows.
5. Interpreted the end-of-boot sequence.

Important commands used:
```bash
journalctl -k -b -1 | tail -n 120
```
Purpose: inspect final kernel messages before reboot.

```bash
journalctl -b -1 -p err..alert | tail -n 120
```
Purpose: inspect severe prior-boot errors.

```bash
journalctl -b -1 | egrep -i 'panic|BUG:|Call Trace|watchdog|soft lockup|hard lockup|mce|hardware error|fatal|reset|reboot' | tail -n 80
```
Purpose: check for classic crash signatures.

```bash
last -x | head
```
Purpose: confirm reboot sequence and uptime windows.

## Key Findings
- The previous boot ended with repeated `e1000e` NIC hangs on `eno1`.
- Ceph monitor and MDS socket closures followed immediately.
- No matching panic, MCE, or watchdog signature was found in the same time window.
- This strongly indicated:
  - host networking failed first
  - Ceph connectivity failed as a downstream effect
  - the node appeared “dead” because network access and Ceph-backed or Ceph-dependent services collapsed

## Resolution
The primary failure mode captured in logs was identified as Intel `e1000e` NIC hangs on the onboard NUC NIC.

## Validation
- Previous-boot logs clearly captured repeated `Detected Hardware Unit Hang` messages.
- Ceph socket closures immediately followed.
- The absence of panic/MCE signatures made the NIC/driver path the strongest explanation.

## Follow-Up Tasks
- Apply an offload workaround on the affected node.
- Standardize the workaround on similar NUC8i7BEH nodes.
- Continue checking for recurrence of `e1000e` hang messages.
- Consider BIOS updates and alternate NIC options if needed.

## Lessons Learned
- On clustered Proxmox/Ceph nodes, a NIC failure can look like total host death.
- Ceph errors can be downstream effects of NIC instability rather than the root cause.
- Previous-boot tail inspection is often more useful than broad log sweeps once the likely failure window is known.

# Applied e1000e Offload Workaround on pve1

## Summary
A mitigation was applied to disable problematic offload features on the Intel NUC onboard NIC and on the Linux bridge. The change was tested live and then persisted in the network interfaces configuration.

## Environment
- Proxmox host: `pve1`
- Hardware: Intel NUC8i7BEH
- Physical NIC: `eno1`
- Linux bridge: `vmbr0`
- Driver: `e1000e`
- Network config file: `/etc/network/interfaces`

## Problem
The Intel onboard NIC on `pve1` was hanging under load and causing host network loss and downstream Ceph disconnects.

## Symptoms
- Repeated:
  - `e1000e ... Detected Hardware Unit Hang`
- Followed by:
  - `libceph ... socket closed`
- Host and VM appeared down or frozen from the network.

## Actions Taken
1. Installed `ethtool`.
2. Disabled TSO/GSO/GRO offloads live on `eno1`.
3. Disabled TSO/GSO/GRO offloads live on `vmbr0`.
4. Verified offload state using `ethtool -k`.
5. Edited `/etc/network/interfaces` to add persistent `post-up` commands.
6. Reloaded networking with `ifreload -a`.
7. Re-verified offload settings after reload.

Important commands used:
```bash
apt-get install -y ethtool
```
Purpose: install NIC feature tuning tool.

```bash
ethtool -K eno1 tso off gso off gro off
```
Purpose: disable problematic offloads on the physical NIC.

```bash
ethtool -K vmbr0 tso off gso off gro off
```
Purpose: apply the same mitigation at the bridge layer where supported.

```bash
ethtool -k eno1 | egrep 'tso|gso|gro'
```
Purpose: verify the physical NIC’s offload state.

```bash
ethtool -k vmbr0 | egrep 'tso|gso|gro'
```
Purpose: inspect bridge feature state after the change.

```bash
nano /etc/network/interfaces
```
Purpose: persist the workaround across reboot.

```bash
ifreload -a
```
Purpose: apply the network config without a full reboot.

Persisted configuration:
```text
auto lo
iface lo inet loopback

auto eno1
iface eno1 inet manual
    post-up /sbin/ethtool -K eno1 tso off gso off gro off

auto vmbr0
iface vmbr0 inet static
        address 192.168.16.12/24
        gateway 192.168.16.1
        bridge-ports eno1
        bridge-stp off
        bridge-fd 0
        post-up /sbin/ethtool -K vmbr0 tso off gso off gro off

iface wlp0s20f3 inet manual

source /etc/network/interfaces.d/*
```

## Key Findings
- `eno1` successfully showed the relevant offload features disabled.
- `vmbr0` showed mixed bridge-specific behavior, which is normal; the key mitigation is on the physical NIC.
- The mitigation fits a known Intel NUC / `e1000e` problem pattern under Linux and bursty network load.

## Resolution
The `e1000e` offload workaround was applied successfully on `pve1` and made persistent.

## Validation
- Live `ethtool` changes succeeded.
- Verification output showed the relevant offload features disabled on `eno1`.
- After about a day, the node appeared stable with most containers running.

## Follow-Up Tasks
- Apply the same workaround to other Intel NUC8i7BEH nodes using the same NIC/driver path.
- Keep checking for:
  - `e1000e` hardware hangs
  - Ceph socket closures
- Continue monitoring temperatures because thermal spikes were also confirmed earlier.
- Consider BIOS updates and cooling cleanup on all NUC nodes.

## Lessons Learned
- Intel NUC onboard `e1000e` NIC instability can destabilize an entire Proxmox/Ceph node.
- Disabling TSO/GSO/GRO is a practical and low-risk mitigation.
- Persisting the fix in `/etc/network/interfaces` is better than relying on manual reapplication after reboot.

# Follow-Up Operational Notes After Stability Improved

## Summary
After roughly a day of runtime, the node appeared stable with most containers running. The conversation then shifted into follow-up operational guidance for other NUC nodes, VM disk option tuning, backup option clarification, and Proxmox update workflow.

## Environment
- Proxmox host: `pve1`
- Other nodes: Intel NUC8i7BEH
- VM: `debian-docker`
- Proxmox storage and VM disk options discussed:
  - IOThreads
  - discard
  - cloud-init disk
  - per-disk backup checkbox

## Problem
With immediate instability reduced, the next goal was to standardize the workaround and document safe operational behavior.

## Symptoms
- Node appeared stable after the NIC workaround.
- A Proxmox warning occurred when enabling IOThread:
  - `WARN: iothread is only valid with virtio disk or virtio-scsi-single controller, ignoring`
- Clarification was needed on:
  - whether to apply the NIC fix to other NUCs
  - whether IOThreads/discard were appropriate
  - where backup storage is actually consumed
  - how to update Proxmox cleanly

## Actions Taken
1. Determined that the NIC workaround should likely be repeated on other NUC8i7BEH nodes using the same onboard NIC and driver.
2. Reviewed whether `iothread` and `discard` were appropriate for the VM disk.
3. Explained that the per-disk Proxmox “Backup” checkbox only controls inclusion in backups and does not allocate separate disk storage on its own.
4. Interpreted the IOThread warning as a controller/disk compatibility issue.
5. Documented concise Proxmox update commands and Proxmox wrapper behavior.

Important commands used or discussed:
```bash
pveversion
```
Purpose: check current Proxmox version before updating.

```bash
apt update
apt full-upgrade -y
reboot
```
Purpose: standard Proxmox update flow.

```bash
pveupdate
pveupgrade
reboot
```
Purpose: wrapper-based Proxmox update flow.

## Key Findings
- The Intel NUC8i7BEH platform likely shares the same `e1000e` risk on other nodes, so the workaround should be standardized there as well.
- `iothread` is only valid for:
  - virtio disks
  - disks on a `virtio-scsi-single` controller
- Enabling `iothread` on unsupported disks such as cloud-init or unsupported controller types produces a warning and is ignored.
- `discard=on` is generally reasonable for thin-provisioned or Ceph-backed virtual disks when trim/unmap is supported.
- The Proxmox disk “Backup” option only controls whether a disk is included in a VM backup job.
- `pveupdate` and `pveupgrade` are Proxmox convenience wrappers around the normal `apt` flow.

## Resolution
Current status:
- `pve1` appeared stable after the NIC offload workaround.
- Guidance was captured for:
  - repeating the NIC fix on similar NUC nodes
  - using IOThread only on supported disk/controller combinations
  - enabling discard where appropriate
  - understanding disk-backup inclusion behavior
  - updating Proxmox using either standard `apt` or Proxmox wrappers

## Validation
- Roughly one day of improved stability was observed with most containers running.
- No new failure evidence was presented during this follow-up checkpoint.

## Follow-Up Tasks
- Apply the NIC workaround across other NUC8i7BEH nodes.
- Review BIOS versions and cooling health on all NUC nodes.
- Verify VM controller types before enabling IOThreads.
- Continue observing `pve1` before fully closing the incident.

## Lessons Learned
- Once a platform-specific fault pattern is confirmed, standardizing the workaround across identical nodes is usually worthwhile.
- Not all Proxmox disk options apply to all controller types.
- Concise operational notes are useful once an incident moves from active troubleshooting to maintenance.

---

# Command Reference

## Command
```bash
journalctl --list-boots
```

### What it does
Lists known boot sessions from the systemd journal, each with a relative boot index such as `0`, `-1`, or `-2`.

### Important flags or arguments
- none in this invocation

### Why it was used at that moment
To identify which earlier boot corresponded to a failure window before inspecting previous-boot logs.

### Expected result
A list of boots with IDs and time ranges.

### What success or failure would indicate
- Success: prior boots are available for review.
- Failure: journald may not be persistent or older logs may be unavailable.

### Risk
Low.

### Safer alternative
None needed.

---

## Command
```bash
journalctl -k -b -1
```

### What it does
Shows kernel messages from the previous boot.

### Important flags or arguments
- `-k`: kernel messages only
- `-b -1`: previous boot

### Why it was used at that moment
To inspect host-side kernel and driver behavior leading up to the last crash or reboot.

### Expected result
The previous boot’s kernel log.

### What success or failure would indicate
- Success: prior-boot kernel history is available.
- Failure: logs from the prior boot are missing.

### Risk
Low.

### Safer alternative
None needed.

---

## Command
```bash
journalctl -k -b -1 -p warning..alert
```

### What it does
Filters the previous boot’s kernel log to warnings and more severe messages.

### Important flags or arguments
- `-p warning..alert`: severity range from warning through alert

### Why it was used at that moment
To reduce noise and focus only on significant prior-boot kernel warnings and errors.

### Expected result
A smaller, higher-signal set of kernel messages.

### What success or failure would indicate
- Success: serious kernel messages are easier to inspect.
- No output: there may have been no warning-level kernel events captured.

### Risk
Low.

### Safer alternative
None needed.

---

## Command
```bash
journalctl -k -b -1 | egrep -i 'panic|BUG:|Oops|Call Trace|hardware error|MCE|watchdog|soft lockup|hard lockup|NMI|reset|blocked for more than'
```

### What it does
Searches the previous boot’s kernel log for common panic, fault, and hardware-error signatures.

### Important flags or arguments
- `egrep -i`: extended regex, case-insensitive
- Search terms include common kernel crash indicators

### Why it was used at that moment
To quickly identify whether the failure resembled a classic panic, watchdog event, or MCE-style hardware fault.

### Expected result
Any matching fault signatures.

### What success or failure would indicate
- Matches found: there may be direct crash or hardware clues.
- No matches: the failure may be outside classic kernel panic patterns.

### Risk
Low.

### Safer alternative
None needed.

---

## Command
```bash
free -h
```

### What it does
Displays memory usage in human-readable units.

### Important flags or arguments
- `-h`: human-readable output

### Why it was used at that moment
To check whether host RAM exhaustion was contributing to instability.

### Expected result
A summary showing total, used, free, shared, cache, and available memory.

### What success or failure would indicate
- High available memory: RAM starvation is less likely.
- Very low available memory plus swap activity: memory pressure is more likely.

### Risk
Low.

### Safer alternative
None needed.

---

## Command
```bash
swapon --show
```

### What it does
Lists configured swap devices and current swap usage.

### Important flags or arguments
- `--show`: tabular display of active swap devices

### Why it was used at that moment
To verify whether the host had started swapping.

### Expected result
A list of swap devices and used size.

### What success or failure would indicate
- `0B` used: no current swap pressure.
- Nonzero usage: swap pressure exists or existed.

### Risk
Low.

### Safer alternative
None needed.

---

## Command
```bash
vmstat 1 5
```

### What it does
Prints virtual memory, process, IO, swap, and CPU statistics every second for five samples.

### Important flags or arguments
- `1`: sample interval in seconds
- `5`: number of samples

### Why it was used at that moment
To check whether the host was swapping, blocked on IO, or under visible CPU pressure.

### Expected result
Five rows of live system telemetry.

### What success or failure would indicate
- `si`/`so` above zero: active swap activity.
- High `wa`: IO wait / storage bottleneck.
- High run queue or low idle: CPU pressure.

### Risk
Low.

### Safer alternative
None needed.

---

## Command
```bash
sudo journalctl -kf
```

### What it does
Follows live kernel messages continuously.

### Important flags or arguments
- `-k`: kernel messages only
- `-f`: follow new entries as they arrive

### Why it was used at that moment
To observe live guest or host kernel behavior during runtime and while reproducing the issue.

### Expected result
New kernel messages appear as they are logged.

### What success or failure would indicate
- New fault messages during a problem window can reveal the root cause.
- Quiet output may simply mean the kernel is not logging anything unusual.

### Risk
Low.

### Safer alternative
None needed.

---

## Command
```bash
apt-get install -y lm-sensors
```

### What it does
Installs Linux hardware sensor utilities and dependencies.

### Important flags or arguments
- `-y`: automatically answer yes to prompts

### Why it was used at that moment
To gather thermal telemetry from the NUC host.

### Expected result
The `lm-sensors` package and dependencies install successfully.

### What success or failure would indicate
- Success: thermal readings can be collected.
- Failure: package or repository issue must be resolved first.

### Risk
Low.

### Safer alternative
None needed.

---

## Command
```bash
sensors-detect
```

### What it does
Probes the system for supported hardware monitoring chips and recommended drivers.

### Important flags or arguments
- interactive prompts during hardware probing

### Why it was used at that moment
To identify which driver modules were needed for temperature reporting.

### Expected result
A detection summary showing supported sensors and recommended modules.

### What success or failure would indicate
- Success: usable drivers are identified.
- Failure: the platform may expose only limited monitoring.

### Risk
Low to moderate. Some bus probing is more intrusive than simply reading existing sensors.

### Safer alternative
Run only `sensors` first if sensor modules are already loaded, but `sensors-detect` is standard when telemetry is missing.

---

## Command
```bash
sensors
```

### What it does
Displays current temperature and sensor readings.

### Important flags or arguments
- none in this invocation

### Why it was used at that moment
To inspect CPU, chipset, and NVMe temperatures while evaluating thermal behavior.

### Expected result
Temperature readings per detected device.

### What success or failure would indicate
- High temperatures near critical thresholds indicate thermal stress.
- Normal temperatures during failure windows suggest another fault domain exists.

### Risk
Low.

### Safer alternative
None needed.

---

## Command
```bash
watch -n2 sensors
```

### What it does
Repeats the `sensors` command every two seconds.

### Important flags or arguments
- `-n2`: update every two seconds

### Why it was used at that moment
To catch peak temperatures under sustained load rather than relying on a single snapshot.

### Expected result
A continuously refreshed thermal display.

### What success or failure would indicate
- CPU temperatures near 99–100°C indicate thermal throttle territory on this NUC.
- Later normal readings during a crash showed thermal issues were not the only problem.

### Risk
Low.

### Safer alternative
None needed.

---

## Command
```bash
journalctl -k -b -1 | tail -n 120
```

### What it does
Shows the last 120 lines of the previous boot’s kernel log.

### Important flags or arguments
- `tail -n 120`: limit to the end of the log where the failure likely occurred

### Why it was used at that moment
To inspect the final kernel events before the reboot.

### Expected result
The previous boot’s last kernel messages.

### What success or failure would indicate
- This command exposed the repeated `e1000e` NIC hang messages.
- If the log ends abruptly with no clue, hard power loss or deeper lockup remains possible.

### Risk
Low.

### Safer alternative
None needed.

---

## Command
```bash
journalctl -b -1 -p err..alert | tail -n 120
```

### What it does
Shows the last 120 error-level and higher messages from the previous boot.

### Important flags or arguments
- `-b -1`: previous boot
- `-p err..alert`: error through alert severity
- `tail -n 120`: limit output to the end of the failure window

### Why it was used at that moment
To isolate high-severity service and kernel errors from the failing boot.

### Expected result
A compact list of severe prior-boot messages.

### What success or failure would indicate
- This helped confirm the NIC hang as the main severe event before reboot.

### Risk
Low.

### Safer alternative
None needed.

---

## Command
```bash
journalctl -b -1 | egrep -i 'panic|BUG:|Call Trace|watchdog|soft lockup|hard lockup|mce|hardware error|fatal|reset|reboot' | tail -n 80
```

### What it does
Searches the previous boot’s full journal for panic, watchdog, and hardware-fault signatures.

### Important flags or arguments
- `egrep -i`: case-insensitive regex search
- `tail -n 80`: focus on the end of the result set

### Why it was used at that moment
To distinguish a NIC or network failure from a classic kernel panic or hardware fault.

### Expected result
Any matching critical fault lines.

### What success or failure would indicate
- Few or no relevant matches support a non-panic failure path.
- Strong matches would shift attention back to kernel or hardware-fault analysis.

### Risk
Low.

### Safer alternative
None needed.

---

## Command
```bash
last -x | head
```

### What it does
Shows recent login, reboot, shutdown, and runlevel events.

### Important flags or arguments
- `-x`: include system events such as reboot and runlevel changes
- `head`: limit to the most recent entries

### Why it was used at that moment
To confirm reboot timing and how long the failed boot lasted.

### Expected result
Recent reboot and runlevel history.

### What success or failure would indicate
- Frequent reboot entries confirm repeated outages.
- Helps align journal timestamps with observed downtime.

### Risk
Low.

### Safer alternative
None needed.

---

## Command
```bash
apt-get install -y ethtool
```

### What it does
Installs the NIC inspection and tuning utility.

### Important flags or arguments
- `-y`: automatically answer yes

### Why it was used at that moment
To disable problematic offload features on the Intel onboard NIC.

### Expected result
`ethtool` installs successfully.

### What success or failure would indicate
- Success: NIC features can be queried and changed.
- Failure: NIC mitigation steps cannot be applied yet.

### Risk
Low.

### Safer alternative
None needed.

---

## Command
```bash
ethtool -K eno1 tso off gso off gro off
```

### What it does
Disables transmit segmentation offload, generic segmentation offload, and generic receive offload on the physical NIC.

### Important flags or arguments
- `-K`: change offload settings
- `tso off`: disable TCP segmentation offload
- `gso off`: disable generic segmentation offload
- `gro off`: disable generic receive offload

### Why it was used at that moment
To avoid the offload paths associated with the observed `e1000e` hardware hangs on the Intel NUC NIC.

### Expected result
The command succeeds and the requested offloads are disabled.

### What success or failure would indicate
- Success: the NIC is less likely to hit the buggy offload path.
- Failure: the feature is unsupported or the change was rejected.

### Risk
Low. Performance may decrease slightly because packet processing shifts more into software.

### Safer alternative
Disabling only one feature at a time is sometimes used for narrower testing, but disabling all three was the chosen mitigation here.

---

## Command
```bash
ethtool -K vmbr0 tso off gso off gro off
```

### What it does
Requests the same offload-related changes on the Linux bridge device.

### Important flags or arguments
- same offload flags as above

### Why it was used at that moment
To align bridge-layer behavior with the NIC workaround where supported.

### Expected result
Some bridge features may change; others may remain fixed or partially supported.

### What success or failure would indicate
- Mixed bridge output is normal.
- The critical mitigation remains the change on the physical NIC.

### Risk
Low.

### Safer alternative
The physical NIC change alone is the essential step.

---

## Command
```bash
ethtool -k eno1 | egrep 'tso|gso|gro'
```

### What it does
Displays the relevant offload settings for the physical NIC.

### Important flags or arguments
- `-k`: show NIC feature state
- `egrep 'tso|gso|gro'`: filter only relevant offload entries

### Why it was used at that moment
To verify that the workaround was actually in effect on `eno1`.

### Expected result
Relevant offloads show `off` or `off [fixed]`.

### What success or failure would indicate
- Correct output confirms the physical NIC mitigation is active.

### Risk
Low.

### Safer alternative
None needed.

---

## Command
```bash
ethtool -k vmbr0 | egrep 'tso|gso|gro'
```

### What it does
Displays the relevant offload-related settings for the bridge.

### Important flags or arguments
- `-k`: show feature state
- `egrep 'tso|gso|gro'`: filter relevant entries

### Why it was used at that moment
To inspect bridge-level behavior after applying the workaround.

### Expected result
A mix of bridge-specific feature states.

### What success or failure would indicate
- Use this as supplemental verification only; `eno1` is the important interface.

### Risk
Low.

### Safer alternative
None needed.

---

## Command
```bash
nano /etc/network/interfaces
```

### What it does
Opens the Proxmox host network configuration file for editing.

### Important flags or arguments
- none

### Why it was used at that moment
To persist the `ethtool` workaround with `post-up` lines.

### Expected result
The network configuration file opens in the editor.

### What success or failure would indicate
- Success: the workaround can survive reboot.
- Failure: another editor or permission check is needed.

### Risk
Moderate. Incorrect edits can break management networking on the host.

### Safer alternative
The Proxmox GUI is safer for common network changes, but direct file edits are often necessary for custom `post-up` directives.

---

## Command
```bash
ifreload -a
```

### What it does
Reloads all interface definitions using ifupdown2.

### Important flags or arguments
- `-a`: reload all interfaces

### Why it was used at that moment
To apply the persistent NIC workaround without rebooting the node.

### Expected result
Interfaces reload successfully and `post-up` hooks run.

### What success or failure would indicate
- Success: the persistent change is live immediately.
- Failure: there may be a syntax issue in `/etc/network/interfaces`.

### Risk
Moderate. Reloading networking on a remote Proxmox host can interrupt management access if the config is wrong.

### Safer alternative
Reboot during a maintenance window instead of live reloading.

---

## Command
```bash
pveversion
```

### What it does
Shows installed Proxmox VE version information.

### Important flags or arguments
- none

### Why it was used at that moment
To check the current update baseline before upgrading the node.

### Expected result
Proxmox version output.

### What success or failure would indicate
- Success: confirms current installed version state.

### Risk
Low.

### Safer alternative
None needed.

---

## Command
```bash
apt update
```

### What it does
Refreshes package metadata from configured Debian and Proxmox repositories.

### Important flags or arguments
- none

### Why it was used at that moment
As part of the standard Proxmox node update workflow.

### Expected result
Updated package lists.

### What success or failure would indicate
- Success: host is ready for package upgrade.
- Failure: repository, network, or configuration problem exists.

### Risk
Low.

### Safer alternative
`pveupdate` is the Proxmox wrapper for a similar step.

---

## Command
```bash
apt full-upgrade -y
```

### What it does
Performs a full package upgrade, allowing dependency changes and replacements.

### Important flags or arguments
- `full-upgrade`: upgrade with dependency changes
- `-y`: automatically confirm prompts

### Why it was used at that moment
To fully update the Proxmox node, including kernel and core packages.

### Expected result
The node upgrades all eligible packages.

### What success or failure would indicate
- Success: node is updated and ready for reboot.
- Failure: package dependency or repository issues must be addressed.

### Risk
Moderate. This can update critical Proxmox, kernel, and storage components.

### Safer alternative
Run on one node at a time during a maintenance window.

---

## Command
```bash
reboot
```

### What it does
Restarts the node.

### Important flags or arguments
- none

### Why it was used at that moment
To load updated kernels or apply changes that require reboot.

### Expected result
The node restarts and returns to service.

### What success or failure would indicate
- Success: host comes back online with the updated runtime.
- Failure: console investigation may be required.

### Risk
High in a clustered environment if workloads are not planned around the reboot.

### Safer alternative
Migrate or stop critical workloads first.

---

## Command
```bash
pveupdate
```

### What it does
Runs the Proxmox convenience wrapper for refreshing package lists.

### Important flags or arguments
- none

### Why it was used at that moment
To describe the concise Proxmox-native update flow.

### Expected result
Repository metadata refreshes.

### What success or failure would indicate
- Success: package lists are current.
- Failure: same classes of issues as `apt update`.

### Risk
Low.

### Safer alternative
`apt update` is the standard Debian equivalent.

---

## Command
```bash
pveupgrade
```

### What it does
Runs the Proxmox convenience wrapper for a full node upgrade.

### Important flags or arguments
- none in this invocation

### Why it was used at that moment
To describe the concise Proxmox-native update flow.

### Expected result
Available Proxmox and Debian package upgrades are applied.

### What success or failure would indicate
- Success: host is updated.
- Failure: dependency or repository issues need review.

### Risk
Moderate. This can affect critical virtualization and storage components.

### Safer alternative
`apt full-upgrade` is the standard Debian equivalent.

---

## Command
```bash
Likely command used: top
```

### What it does
Displays live process, CPU, memory, and load information.

### Important flags or arguments
- interactive usage
- in a VM, pressing `1` shows per-vCPU detail

### Why it was used at that moment
To inspect runtime CPU pressure, IO wait, and possible VM steal time.

### Expected result
An interactive process and CPU summary.

### What success or failure would indicate
- High `wa`: storage bottleneck.
- High `st` inside a VM: host scheduling contention.
- High load with poor responsiveness: potential lockup or backend dependency issue.

### Risk
Low.

### Safer alternative
`htop` if installed, but `top` is standard and usually available.

---

## Command
```bash
Likely command used: iostat -x 1
```

### What it does
Displays extended disk IO statistics every second.

### Important flags or arguments
- `-x`: extended device statistics
- `1`: one-second interval

### Why it was used at that moment
To determine whether storage latency or device saturation was contributing to freezes.

### Expected result
Rolling per-device IO stats including utilization and wait times.

### What success or failure would indicate
- High `%util` and `await` indicate a storage bottleneck.
- Low utilization suggests storage is not the main limiter.

### Risk
Low.

### Safer alternative
None needed.

---

## Command
```bash
Likely command used: stress-ng --cpu 8 --vm 2 --vm-bytes 75% --io 4 --timeout 30m
```

### What it does
Generates synthetic CPU, memory, and IO load on the host.

### Important flags or arguments
- `--cpu 8`: stress 8 CPU workers
- `--vm 2`: memory stress workers
- `--vm-bytes 75%`: target 75% memory usage
- `--io 4`: IO stress workers
- `--timeout 30m`: run for 30 minutes

### Why it was discussed at that moment
To separate generic hardware instability from workload-specific failures.

### Expected result
Thirty minutes of sustained synthetic load.

### What success or failure would indicate
- Stable run: hardware may be okay and workload pattern may matter more.
- Crash/hang: deeper hardware, firmware, or kernel issues become more likely.

### Risk
Moderate to high. Can push the node into failure and should be run only in a maintenance window.

### Safer alternative
Run a shorter-duration test first.

---

## Command
```bash
Likely command used: memtest86+ / MemTest86 boot run
```

### What it does
Tests system RAM outside the normal operating system.

### Important flags or arguments
- boot-time utility rather than a shell command in this session

### Why it was discussed at that moment
To rule out faulty RAM after repeated host instability.

### Expected result
Multiple clean passes with zero errors.

### What success or failure would indicate
- Zero errors: RAM is less likely to be the issue.
- Any errors: memory or memory path faults are strongly suspected.

### Risk
Low runtime risk, but requires host downtime.

### Safer alternative
None equivalent from inside the running OS.

---

## Command
```bash
Likely command used: qm / Proxmox GUI disk option changes for iothread and discard
```

### What it does
Applies VM disk options such as IOThreads and discard/TRIM handling.

### Important flags or arguments
- `iothread`: valid on supported virtio/virtio-scsi-single disk paths
- `discard`: enables trim/unmap propagation when supported

### Why it was discussed at that moment
To improve VM disk behavior and explain why Proxmox ignored IOThread on an unsupported disk/controller combination.

### Expected result
Supported disks accept the setting; unsupported ones emit a warning and ignore it.

### What success or failure would indicate
- Warning about unsupported controller or disk type means IOThread is ignored safely.
- Correct use requires a virtio disk or `virtio-scsi-single` controller.

### Risk
Low to moderate depending on whether controller changes require downtime.

### Safer alternative
Verify disk bus and SCSI controller type before enabling IOThread.
