---
title: "Proxmox Host Kernel Crash Investigation on `mainframe`"
track: "infrastructure"
category: "monitoring-operations"
type: "runbook"
logical_order: 20
date_rule: "Dates are removed from filenames, visible headings, indexes, generated metadata, and runbook body content."
---

# Proxmox Host Kernel Crash Investigation on `mainframe`

## Summary
Investigated a Proxmox host crash on `mainframe` after the host logged a kernel fault and scheduler-related panic behavior. The goal was to determine whether the issue was caused by the Proxmox kernel, an out-of-tree module, or unstable host hardware.

## Environment
- Host: `mainframe`
- Platform: Proxmox VE host
- Motherboard: ASUS ROG Strix Z390-F Gaming
- CPU platform: Intel 8th/9th Gen LGA1151 platform
- Kernel observed in logs: `6.8.12-16-pve`
- Memory:
  - 32 GB installed
  - 4 memory slots populated
  - Non-ECC platform
- Storage context:
  - Ceph in use elsewhere in the homelab
  - ZFS not intentionally used on this host
- Workloads affected:
  - Proxmox scheduling
  - Guest VM availability and stability

## Problem
The Proxmox host experienced a kernel crash, causing host instability and likely affecting guest VMs running on the node.

## Symptoms
- Kernel trace showed a crash in:
  - `unlink_anon_vmas+...`
- Additional fatal messages included:
  - `BUG: scheduling while atomic: pvescheduler/...`
  - `recursive fault but reboot is needed!`
- Kernel was marked tainted.
- Module list in the log included out-of-tree modules such as:
  - `zfs(P0)`
  - `spl(0)`
- Host instability on the Proxmox node would also explain guest-side symptoms such as VM hangs or dropped guest agent connectivity.

## Actions Taken
1. Reviewed the OCR-recovered host kernel crash log from [date removed].
2. Identified that the crash occurred on the Proxmox host rather than inside a guest VM.
3. Noted that the crash path was in Linux memory-management code (`unlink_anon_vmas`).
4. Noted that the scheduler process `pvescheduler` was involved in the panic sequence.
5. Checked whether ZFS was actually part of the intended host design.
6. Distinguished Ceph usage from ZFS usage to avoid conflating unrelated storage layers.
7. Considered kernel taint and loaded third-party modules as potential contributors.

## Key Findings
- The crash was a **host-level kernel problem**, not a guest-only issue.
- `unlink_anon_vmas` is part of the Linux VM/MM subsystem, so the crash pattern was consistent with:
  - memory corruption
  - unstable RAM
  - a buggy out-of-tree kernel module
- The presence of `zfs(P)` and `spl` in the module list meant the host was running with proprietary/out-of-tree kernel modules loaded, even though ZFS was not intentionally part of the design.
- This crash alone did not conclusively prove defective RAM, but it strongly justified hardware and module scrutiny.

## Resolution
No permanent resolution was completed in this part of the session. The working conclusion at this stage was:
- treat the issue as a **host-level kernel instability**
- remove suspicion from Ceph itself
- continue investigating both:
  - unused out-of-tree modules
  - host RAM stability

## Validation
Validation was not yet complete at this stage. The main validation outcome was analytical:
- the issue was correctly reclassified from guest instability to host kernel instability.

## Follow-Up Tasks
- Verify whether `zfs` and `spl` are installed and loaded unnecessarily.
- Remove unused out-of-tree modules if they are not required.
- Continue memory stability testing on the host.
- Keep copies of kernel traces for comparison across incidents.
- Consider pinning to a known-stable Proxmox kernel if crashes continue after hardware remediation.

## Lessons Learned
- A guest appearing frozen can be the result of a host kernel fault.
- Ceph and ZFS are unrelated; loaded ZFS modules should not be assumed to be part of a Ceph design.
- OCR logs can still be useful if the stack frames and panic messages are recognizable.

# Second Host Kernel Crash Linked to `knem`

## Summary
Investigated another Proxmox host crash on `mainframe`. This time, the kernel trace pointed to `knem_cache_alloc`, which suggested a fault involving the `knem` kernel module rather than a generic guest VM issue.

## Environment
- Host: `mainframe`
- Platform: Proxmox VE host
- Kernel family: Proxmox `6.8.x` series
- Workloads impacted:
  - Proxmox-hosted VMs
  - QEMU guest agent visibility
  - General host stability
- Relevant modules mentioned:
  - `knem`
  - `zfs`
  - `spl`
  - virtualization/network-related modules such as `vhost_net`, `tap`

## Problem
A later host crash occurred, and the user wanted to confirm whether the earlier kernel errors were consistent with the current instability.

## Symptoms
- Kernel trace showed:
  - `RIP: 0010:knem_cache_alloc+...`
- Fault markers included:
  - `---[ end trace ... ]---`
  - kernel-space fault address in `CR2`
- Guest-visible effects included:
  - VM instability
  - dropped `qemu-guest-agent`
  - apparent VM freezes after some uptime

## Actions Taken
1. Reviewed the recovered host kernel trace.
2. Confirmed that the trace was from the Proxmox host, not from a guest VM.
3. Interpreted `knem_cache_alloc` as evidence pointing to the `knem` kernel module.
4. Distinguished this fault from the earlier `unlink_anon_vmas` crash while noting that both were host memory-path failures.
5. Considered removal/blacklisting of `knem`.
6. Considered removal of unused ZFS packages to reduce host kernel complexity.

## Key Findings
- The crash was again a **host kernel fault**.
- `knem_cache_alloc` strongly implicated the `knem` module.
- Since host kernel faults can stall scheduling and I/O, guest VM symptoms were consistent with a host-side root cause.
- The presence of multiple distinct MM-adjacent host crashes increased suspicion of:
  - unstable host memory
  - problematic out-of-tree modules
  - or both

## Resolution
No final fix was completed in this portion of the session, but the likely remediation path identified was:
- blacklist or remove `knem`
- remove unused ZFS-related packages if not needed
- continue hardware validation

## Validation
Validation was still pending at this stage. The important completed validation was logical:
- host kernel instability was confirmed as the correct investigative focus.

## Follow-Up Tasks
- Confirm whether `knem` is installed and loaded.
- Blacklist/remove `knem` if not needed.
- Rebuild initramfs after module cleanup.
- Reboot the host and re-check loaded modules.
- Continue host memory testing.

## Lessons Learned
- Repeated guest freezes can originate from a crashing Proxmox host kernel.
- A precise `RIP` location in the stack trace can identify a likely culprit module.
- Unused modules increase attack surface and troubleshooting complexity.

# Host Memory Stability Validation on `mainframe`

## Summary
Performed targeted host memory diagnostics after multiple host kernel crashes. The aim was to determine whether RAM instability was the true underlying cause of the Proxmox host failures.

## Environment
- Host: `mainframe`
- Platform: Proxmox VE host
- Motherboard: ASUS ROG Strix Z390-F Gaming
- Memory installed:
  - TEAMGROUP T-Force Delta RGB DDR4
  - 16 GB kit branding discussed as `4x8GB 3200MHz CL16`
- Effective detected platform state:
  - 4/4 DIMM slots populated
  - Non-ECC memory
- Logs:
  - boot log from `[date removed]`
  - later journal entries from `[date removed]`
- Test tools used:
  - `memtester`
  - `stress-ng`

## Problem
Needed to determine whether host RAM was actually the source of the Proxmox host crashes and VM instability.

## Symptoms
- `memtester` reported extensive failures, including:
  - `FAILURE: possible bad address line`
  - many repeated mismatches across multiple test patterns
  - repeated bit-flip style corruption
- `stress-ng` reported direct memory corruption:
  - `vm: detected 523 bit errors while stressing memory`
  - `vm: detected 1456 bit errors while stressing memory`
- Kernel logs did **not** show Machine Check Exceptions or ECC correction events.
- Journal showed:
  - `EDAC ie31200: No ECC support`
- System reported:
  - `4/4 memory slots populated (from DMI)`

## Actions Taken
1. Confirmed host board model and memory kit details.
2. Discussed whether XMP was in use and clarified that non-XMP/JEDEC recommendations were more appropriate for a stability-first Proxmox host.
3. Queried kernel logs for hardware error indicators:
```bash
sudo dmesg -T | egrep -i 'mce|machine check|hardware error|ecc|memory'
sudo journalctl -k | egrep -i 'mce|hardware error|ecc'
```
Purpose: check for machine check exceptions, ECC activity, or obvious hardware error records.

4. Reviewed the kernel/journal output.
5. Ran `memtester` and observed widespread failures across many test categories.
6. Ran `stress-ng` using large VM-backed memory allocations:
```bash
sudo stress-ng --vm 2 --vm-bytes 80% --timeout 30m --metrics-brief
```
Purpose: stress memory allocation and detect corruption under load.

7. Interpreted the absence of ECC support together with repeated user-space memory corruption.

## Key Findings
- The host platform has **no ECC support**, so memory corruption cannot be corrected or cleanly attributed by ECC reporting.
- `memtester` output showed severe and repeated memory corruption, including:
  - stuck address failures
  - random value mismatches
  - arithmetic and pattern test corruption
- `stress-ng` independently reproduced memory errors with large numbers of bit flips.
- The combination of:
  - repeated host kernel crashes
  - repeated memory test failures
  - lack of ECC
  is strong evidence that the memory path is unstable.
- At this stage, host RAM instability became the leading root-cause candidate over Proxmox software alone.

## Resolution
Current status:
- No hardware replacement had yet been completed in the chat.
- The operational conclusion was that **RAM instability is real and must be treated as an active hardware issue**.
- Recommended immediate remediation path:
  - run memory at JEDEC-safe settings
  - isolate DIMMs one at a time
  - identify bad stick or slot
  - replace unstable memory kit as needed

## Validation
Validation was strong and multi-layered:
- `memtester` reproduced corruption repeatedly.
- `stress-ng` detected hundreds to thousands of bit errors.
- Log review confirmed the system is non-ECC and therefore unable to mask or correct these failures.
- The results were consistent with the earlier host kernel crashes.

## Follow-Up Tasks
- Enter BIOS and set memory to conservative JEDEC settings.
- Disable XMP if enabled now or in future tests.
- Test one DIMM at a time in the same slot.
- Test a known-good DIMM across slots to rule out a motherboard slot issue.
- Run bootable MemTest86 or Memtest86+ for deeper validation.
- Replace failing DIMM(s) or memory kit.
- After hardware correction, re-validate host stability under Proxmox load.
- Review storage and service integrity after running with unstable RAM.

## Lessons Learned
- Widespread bit flips in both `memtester` and `stress-ng` are strong evidence of hardware-level memory instability.
- Absence of MCE logs does not clear RAM on a non-ECC platform.
- Host memory faults can masquerade as VM instability, guest agent drops, and kernel crashes.
- For a virtualization host, conservative JEDEC settings are often preferable to performance-oriented memory profiles.

# Memory Tuning and Power-State Diagnostic Discussion

## Summary
Discussed whether disabling S-/P-/C-states would be meaningful in this case and whether the memory test results could identify a particular DIMM.

## Environment
- Host: `mainframe`
- Board: ASUS ROG Strix Z390-F Gaming
- Memory subsystem:
  - 4 DIMMs installed
  - non-ECC DDR4
- Operating role:
  - always-on Proxmox host

## Problem
Needed to interpret advice seen elsewhere about disabling S-/P-/C-states and determine whether existing tests could identify a specific RAM stick.

## Symptoms
- Host crashes and proven memory bit errors already existed.
- No explicit DIMM-level failure mapping was available from the performed tests.

## Actions Taken
1. Evaluated whether disabling sleep/power states would meaningfully address the confirmed memory corruption.
2. Clarified that:
   - S-states are generally irrelevant for an always-on Proxmox host
   - P-/C-state changes can be used as a diagnostic aid, but not as a true fix for memory corruption
3. Evaluated whether `stress-ng --vm` could identify the specific failing stick.
4. Clarified that the performed tests only proved memory corruption, not DIMM identity.
5. Recommended one-DIMM-at-a-time testing and slot isolation.

## Key Findings
- Disabling power states may reduce transient conditions, but it does not explain away large-scale repeatable memory corruption.
- The current evidence still points to unstable RAM, slot, or IMC path rather than a pure CPU power-management issue.
- Existing Linux memory stress tools used in-session did **not** identify the failing stick.

## Resolution
Current status:
- No permanent BIOS power-state changes were adopted as the fix.
- The recommended path remained:
  - JEDEC-safe memory settings
  - isolate sticks individually
  - replace bad hardware if identified

## Validation
No new validation was completed in this section. This was a decision/interpretation step that refined the troubleshooting path.

## Follow-Up Tasks
- Test each DIMM independently in slot A2.
- Test a known-good DIMM in other slots.
- Only revisit power-state tuning if instability remains after memory hardware is proven good.

## Lessons Learned
- Power-state changes can be useful for narrowing edge-case instability, but they are not a substitute for fixing bad RAM.
- Tools like `stress-ng` can prove corruption without localizing the bad DIMM.
- DIMM isolation remains the most reliable low-cost method on a non-ECC desktop platform.

# Replacement RAM Selection for a Stability-First Proxmox Host

## Summary
Reviewed replacement RAM selection for the ASUS ROG Strix Z390-F and corrected earlier advice that assumed XMP usage. The goal shifted to selecting memory appropriate for a stable no-XMP Proxmox host.

## Environment
- Host: `mainframe`
- Motherboard: ASUS ROG Strix Z390-F Gaming
- CPU family: Intel 8th/9th Gen
- Requirement:
  - no-XMP / JEDEC-oriented stability
  - homelab/Proxmox host usage
- Current RAM:
  - TEAMGROUP T-Force Delta RGB DDR4
  - unstable under testing

## Problem
Needed replacement RAM recommendations that prioritize reliability over XMP-driven speed.

## Symptoms
- Existing RAM showed clear corruption in memory stress tests.
- Earlier generic suggestions mentioning XMP were not aligned with the stated stability-first requirement.

## Actions Taken
1. Reviewed the board model and platform class.
2. Corrected the recommendation path to no-XMP / JEDEC memory.
3. Identified that the safe operating target for a stability-focused Z390 host is generally JEDEC DDR4 speeds.
4. Recommended conservative, non-XMP-oriented kit choices such as:
   - Crucial DDR4-2666 JEDEC
   - Kingston ValueRAM DDR4-2666 JEDEC
5. Discussed 2x16 GB and 4x16 GB stable capacity options rather than performance-tuned RGB kits.

## Key Findings
- For this host role, JEDEC memory is more appropriate than relying on XMP profiles.
- Full population of 4 DIMM slots puts more stress on the memory controller than a 2-DIMM layout.
- Replacing RGB/performance-oriented memory with plain JEDEC-oriented DIMMs is operationally sensible for a Proxmox host.

## Resolution
Current status:
- No new kit was purchased in the chat.
- The direction of travel was to replace the current unstable RAM with conservative JEDEC DDR4 suitable for the Z390 platform.

## Validation
Not yet applicable. Validation will come after:
- installation
- MemTest/Memtest86+
- Linux-side stress testing
- stable Proxmox uptime

## Follow-Up Tasks
- Decide target capacity: 32 GB or 64 GB.
- Prefer matched kits rather than mixed modules.
- Validate replacement RAM with both bootable and Linux-based tests.
- Re-check host kernel stability after replacement.

## Lessons Learned
- Homelab hosts benefit more from conservative memory configuration than peak memory frequency.
- Advice appropriate for gaming builds is not always appropriate for always-on virtualization hosts.
- Correcting assumptions about XMP matters when making hardware recommendations.

# Command Reference

## Command
```bash
sudo dmesg -T | egrep -i 'mce|machine check|hardware error|ecc|memory'
```

### What it does
Searches the kernel ring buffer for machine check, ECC, hardware error, or memory-related messages.

### Important flags and arguments
- `dmesg -T` shows kernel messages with human-readable timestamps.
- `egrep -i` performs a case-insensitive extended regex search.

### Why it was used
To look for kernel-reported evidence of hardware memory failure, machine check exceptions, or ECC activity on the Proxmox host.

### Expected result
- Matches such as `MCE`, `hardware error`, or ECC correction/failure would support hardware suspicion.
- No such messages would not fully clear RAM, especially on a non-ECC system.

### Success or failure meaning
- **Success:** command runs and returns matching kernel lines if present.
- **No output:** no matching strings were found in the current ring buffer.

### Risk
Low risk. Read-only diagnostic command.

### Safer alternative
`journalctl -k` can provide a broader boot history if the ring buffer has rotated.

## Command
```bash
sudo journalctl -k | egrep -i 'mce|hardware error|ecc'
```

### What it does
Searches the systemd journal for kernel log entries related to machine checks, hardware errors, and ECC.

### Important flags and arguments
- `journalctl -k` restricts output to kernel messages.
- `egrep -i` performs case-insensitive matching.

### Why it was used
To search a longer-lived kernel log history than `dmesg` alone and check whether past boot sessions recorded hardware-level faults.

### Expected result
- MCE/ECC/hardware error logs would strengthen the case for host hardware instability.
- In this case, the relevant finding was:
  - `EDAC ie31200: No ECC support`

### Success or failure meaning
- **Success:** journal access and matching lines returned.
- **No output:** no matching kernel entries were found.

### Risk
Low risk. Read-only diagnostic command.

### Safer alternative
None needed; this is already a safe log query.

## Command
```bash
sudo stress-ng --vm 2 --vm-bytes 80% --timeout 30m --metrics-brief
```

### What it does
Runs two memory (`vm`) stress workers, each allocating and exercising a large amount of memory, while reporting basic metrics.

### Important flags and arguments
- `--vm 2` launches 2 VM memory stress workers.
- `--vm-bytes 80%` tells each worker to use a large portion of available memory.
- `--timeout 30m` runs the stress for 30 minutes.
- `--metrics-brief` prints summary performance numbers.

### Why it was used
To reproduce memory corruption under sustained load on the Proxmox host.

### Expected result
- On a healthy system: no bit-error reports and a clean completion.
- On an unstable memory subsystem: stress-ng may report detected bit errors or terminate unsuccessfully.

### Success or failure meaning
- **Success:** run completes with no bit-error failures.
- **Failure:** reported bit errors strongly indicate unstable memory hardware or memory settings.

### Risk
Moderate.
- Heavy memory pressure can affect host responsiveness.
- Should not be run casually on a production virtualization host carrying critical workloads.

### Safer alternative
Run a bootable offline memory test such as MemTest86/Memtest86+ during a maintenance window.

## Command
```bash
memtester 24576M 2
```

### What it does
Exercises a large block of memory with multiple test patterns for two loops.

### Important flags and arguments
- `24576M` requests testing of roughly 24 GiB.
- `2` runs two test loops.

### Why it was used
To test most of the host’s available RAM from Linux and look for corruption patterns.

### Expected result
- Healthy memory should complete pattern tests with no failures.
- Repeated mismatches, stuck address failures, or bit-flip patterns indicate unstable RAM, slot, or memory controller path.

### Success or failure meaning
- **Success:** zero reported failures.
- **Failure:** strong evidence of memory corruption.

### Risk
Moderate.
- High memory allocation on a live host can pressure other services.
- Best used during maintenance windows.

### Safer alternative
Bootable MemTest86/Memtest86+ performs testing outside the running OS and avoids interference from live workloads.

## Command
```bash
lsmod | egrep -i 'knem|zfs|spl'
```

### What it does
Lists currently loaded kernel modules and filters for modules relevant to the investigation.

### Important flags and arguments
- `lsmod` shows active modules.
- `egrep -i` filters case-insensitively.

### Why it was used
To confirm whether suspect out-of-tree modules such as `knem`, `zfs`, or `spl` were loaded on the host.

### Expected result
- Presence of these modules would support module cleanup and simplification.
- Absence would reduce suspicion for those specific components.

### Success or failure meaning
- **Success:** matching modules, if any, are shown.
- **No output:** none of the searched modules are currently loaded.

### Risk
Low risk. Read-only diagnostic command.

### Safer alternative
None needed.

## Command
```bash
modprobe -r knem
```

### What it does
Attempts to unload the `knem` kernel module from the running kernel.

### Important flags and arguments
- `-r` removes the specified module if it is not in active use.

### Why it was discussed
Because a host kernel trace pointed at `knem_cache_alloc`, suggesting `knem` may have contributed to the crash.

### Expected result
- Successful unload if the module is present and not busy.
- Failure if the module is in use or not loaded.

### Success or failure meaning
- **Success:** the module is removed from the running kernel.
- **Failure:** either it is not loaded or something still depends on it.

### Risk
Moderate to high.
- Removing a kernel module on a live Proxmox host can destabilize dependent workloads if the module is actually in use.

### Safer alternative
Blacklist the module and remove it during a maintenance reboot window.

## Command
```bash
echo 'blacklist knem' > /etc/modprobe.d/blacklist-knem.conf
```

### What it does
Creates a modprobe blacklist entry to prevent the `knem` module from auto-loading.

### Important flags and arguments
- Writes a blacklist directive into a persistent configuration file.

### Why it was discussed
To keep `knem` from loading again after reboot if it was not required.

### Expected result
- Future boots should not automatically load `knem`.

### Success or failure meaning
- **Success:** file is created and used by modprobe/initramfs logic after rebuild/reboot.
- **Failure:** module may still load if initramfs or another config path still includes it.

### Risk
Moderate.
- Blacklisting a needed module can break dependent software.

### Safer alternative
Confirm the module is unused before blacklisting; test during maintenance.

## Command
```bash
apt-get purge -y zfs-dkms zfsutils-linux spl-dkms
```

### What it does
Removes ZFS-related DKMS packages and utilities from the host.

### Important flags and arguments
- `purge` removes packages and their configuration files.
- `-y` auto-confirms prompts.

### Why it was discussed
Because ZFS was not part of the intended host design, yet ZFS/SPL modules appeared in crash logs.

### Expected result
- Removes unused ZFS package set and reduces out-of-tree kernel surface area.

### Success or failure meaning
- **Success:** packages are removed.
- **Failure:** package names may differ, or dependencies may block removal.

### Risk
High if ZFS is actually in use.
- Removing ZFS packages from a host using ZFS storage can break storage access and boot behavior.

### Safer alternative
Confirm with storage and module checks before removal.

## Command
```bash
update-initramfs -u -k all
```

### What it does
Rebuilds initramfs images for all installed kernels.

### Important flags and arguments
- `-u` updates existing initramfs images.
- `-k all` applies the update to all installed kernels.

### Why it was discussed
Needed after module blacklisting or package removal so boot images reflect the new module state.

### Expected result
- Rebuilt initramfs images without the unwanted modules or with updated module configuration.

### Success or failure meaning
- **Success:** initramfs images are regenerated cleanly.
- **Failure:** packaging or initramfs hooks may need further correction.

### Risk
Moderate.
- A bad initramfs rebuild can affect bootability if the system depends on modules that are removed or misconfigured.

### Safer alternative
Keep console/KVM access ready before rebooting after initramfs changes.

## Command
```bash
sudo dmidecode -t memory
```

### What it does
Reads SMBIOS/DMI memory inventory data from firmware.

### Important flags and arguments
- `-t memory` restricts output to memory device structures.

### Why it was implied
To identify slot population, module size, and part details for DIMM isolation and replacement planning.

### Expected result
- Shows slot locators, sizes, configured speed, and often part numbers.

### Success or failure meaning
- **Success:** hardware inventory is displayed.
- **Failure:** uncommon unless firmware tables are inaccessible.

### Risk
Low risk. Read-only hardware inventory command.

### Safer alternative
None needed.

## Command
```bash
Likely command used: MemTest86 or Memtest86+ from bootable media
```

### What it does
Runs memory diagnostics outside the installed operating system.

### Important flags and arguments
- Tool-specific; not a shell command from the running OS.

### Why it was recommended
Because offline memory testing avoids interference from the running kernel and is one of the best ways to validate DIMM stability.

### Expected result
- Zero errors on healthy memory.
- Any error strongly indicates RAM/slot/IMC instability.

### Success or failure meaning
- **Success:** multiple clean passes.
- **Failure:** errors indicate hardware instability.

### Risk
Low operational risk, but requires downtime.

### Safer alternative
Linux-based tests like `memtester` are easier to run live, but are less isolated than bootable tests.

## Command
```bash
Likely command used: one-DIMM-at-a-time retest in slot A2, followed by known-good DIMM testing across slots
```

### What it does
This is a test procedure rather than a single command:
- install one DIMM only
- boot
- run memory test
- repeat per DIMM and per slot

### Important flags and arguments
Not applicable.

### Why it was recommended
To isolate whether the instability follows:
- a specific DIMM
- a specific motherboard slot
- or only a fully populated configuration

### Expected result
- Errors following one DIMM point to a bad stick.
- Errors following one slot point to board/slot/channel issues.
- Errors only with full population suggest margin issues with the IMC or timings.

### Success or failure meaning
- **Success:** stable one-stick and slot mapping identifies the failing component.
- **Failure:** inconsistent results may require deeper platform-level investigation.

### Risk
Low, aside from maintenance downtime and handling hardware.

### Safer alternative
None better for a non-ECC desktop platform.
