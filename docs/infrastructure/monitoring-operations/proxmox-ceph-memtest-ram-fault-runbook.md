---
title: "RAM Fault Investigation on Proxmox/Ceph Node"
track: "infrastructure"
category: "monitoring-operations"
type: "runbook"
logical_order: 10
date_rule: "Dates are removed from filenames, visible headings, indexes, generated metadata, and runbook body content."
---

# RAM Fault Investigation on Proxmox/Ceph Node

## Summary
A suspected memory hardware issue was investigated after repeated MemTest86+ failures on a Proxmox homelab node. The work focused on understanding the operational risk of failing RAM in a virtualization and distributed storage environment, interpreting MemTest86+ output, and defining a safe isolation and test plan to identify whether the issue was caused by one or more DIMMs, a motherboard slot, or a broader platform-level fault.

## Environment
- Proxmox-based homelab environment
- Ceph-backed storage in the homelab
- Virtual machines running on Proxmox
- Likely affected node hardware:
  - CPU: Intel Core i9-9900K
  - RAM observed in test output:
    - DDR4-3200
    - Team Group TEAMGROUP-UD4-3200
    - 8 GB DIMM observed individually in later test
- MemTest variant used:
  - MemTest86+ v6.10
- Relevant workload context:
  - Proxmox virtualization
  - Ceph services or storage roles potentially affected by memory instability

## Problem
A Proxmox node appeared to have failing RAM, confirmed by MemTest86+ showing a large number of repeatable memory errors. The concern was how this would affect VMs, Proxmox itself, and Ceph data integrity.

## Symptoms
- MemTest86+ reported large-scale failures during testing.
- One captured test showed:
  - Test #6: Moving inversions, 64-bit pattern
  - Failure addresses clustered around approximately 5.79 GB
  - Errors: 12,122
  - Status: Failed
- Expected vs found values showed a repeatable incorrect bit pattern rather than random isolated corruption.
- A later single-stick test showed:
  - Status: Pass
  - Errors: 0
  - Same test family running without failure for that individual DIMM/slot combination
- Operational concern was raised that bad RAM could affect:
  - VM stability
  - Filesystem and application data integrity
  - Ceph object writes and cluster behavior

## Actions Taken
1. Reviewed the initial MemTest86+ failure output.
2. Interpreted the failure pattern as consistent with a hard memory fault rather than a software issue.
3. Assessed the impact of bad RAM on:
   - Proxmox host stability
   - VM and container behavior
   - Ceph object integrity and service reliability
4. Considered whether all four installed RAM sticks could realistically be bad.
5. Identified likely alternative explanations for multi-stick instability:
   - Single bad DIMM
   - Bad motherboard slot or channel
   - CPU integrated memory controller issue
   - Instability only when multiple DIMMs are installed together
6. Confirmed that XMP was not being used.
7. Chose a structured isolation plan:
   - Test each existing DIMM individually
   - Use the same slot for controlled comparison
   - Then test two newly purchased DIMMs
8. Ran a later single-stick MemTest86+ session and observed zero errors.
9. Clarified how MemTest works at a high level.
10. Clarified what a memory address means in MemTest output.

## Key Findings
- The initial failure was severe and should be treated as a hardware trust failure on that node.
- The clustered failing addresses around approximately 5.79 GB suggested a repeatable hardware fault in a specific memory region.
- The consistent unexpected bit pattern suggested a stuck bit, bad chip, bad DIMM, bad slot, or bad memory path rather than random one-off noise.
- The later clean single-stick test strongly suggested that not all DIMMs were necessarily bad.
- Since XMP was not enabled, instability was less likely to be caused by an overclocked memory profile.
- The most likely possibilities after the clean single-stick result were:
  - One or more existing DIMMs are bad
  - A specific slot or channel is bad
  - Stability changes depending on DIMM population
- In a Proxmox and Ceph environment, bad RAM must be treated as a high-risk condition because it can cause:
  - VM crashes or guest corruption
  - Host-level service instability
  - Silent Ceph data corruption if corrupted data is checksummed and replicated as valid

## Resolution
Current status: investigation in progress.

No final hardware replacement or permanent repair was completed during this chat. The working plan was:

- Treat the node as untrusted until memory testing is clean
- Test each installed DIMM individually in a controlled manner
- Test the two newly purchased DIMMs individually
- Use results to distinguish between:
  - bad DIMM(s)
  - bad slot/channel
  - broader motherboard or CPU memory controller issue

## Validation
Validation performed during the session:
- One single-stick MemTest86+ run showed:
  - Status: Pass
  - Errors: 0
- This validated that at least one stick and one slot combination could operate without immediate errors.

Validation still required:
- Complete at least one full pass per DIMM when tested individually
- Test known-good DIMMs together as a pair
- Optionally retest with all installed DIMMs only after identifying individually stable hardware
- Only return the node to important Proxmox or Ceph duties after repeated clean memory tests with zero errors

## Follow-Up Tasks
- Test each original DIMM one by one in the same slot.
- Record pass/fail results for every DIMM.
- Test the two newly purchased DIMMs one by one in the same slot.
- If all sticks pass individually, test in pairs.
- If pair testing passes, test full population only if required.
- If failures occur only in one slot, investigate motherboard slot/channel fault.
- If all sticks fail in the same slot, suspect motherboard or CPU memory controller.
- Keep the affected node out of critical Ceph roles until testing is complete.
- Review any important data or services that may have been running on the node during the known-bad RAM period.
- Consider extended monitoring and post-repair validation before restoring production-like workload trust.

## Lessons Learned
- Any MemTest86+ error count above zero is operationally significant in a Proxmox/Ceph environment.
- A large cluster of repeatable errors usually points to a hardware fault, not software.
- Bad RAM is more dangerous than a simple crash because it can cause silent corruption.
- In Ceph, corrupted data can be replicated and protected if corruption occurs before checksumming and write completion.
- Single-stick testing in a fixed slot is the fastest clean way to separate DIMM faults from slot/channel faults.
- A clean solo DIMM result does not prove the whole memory configuration is healthy, but it is a strong isolation signal.
- For homelab infrastructure, stable memory matters more than maximum memory population or speed.

---

# MemTest86+ Interpretation Notes

## Summary
During the troubleshooting session, clarification was provided on what MemTest86+ is doing during a run and what the reported failing address means.

## Environment
- MemTest86+ v6.10
- Intel Core i9-9900K platform
- DDR4 memory on a Proxmox homelab node

## Problem
The meaning of MemTest86+ output fields was unclear during troubleshooting, especially:
- how MemTest works
- what a failing address represents

## Symptoms
- User needed a concise explanation of MemTest behavior.
- User needed clarification on the meaning of the reported failing address.

## Actions Taken
1. Explained that MemTest86+ operates outside the main operating system.
2. Explained that it writes known patterns to RAM and reads them back to detect mismatches.
3. Explained that different tests use different data patterns and access methods to expose marginal or faulty memory behavior.
4. Explained that a memory address in MemTest refers to a physical location in RAM.
5. Explained that the displayed value in GB is a human-friendly approximation of that failing location's offset within physical memory.

## Key Findings
- MemTest86+ is essentially a low-level RAM validation tool that:
  - writes known data
  - reads it back
  - compares expected vs actual values
- A failing address identifies the location in memory where the returned data did not match what was written.
- Repeated failures at nearby addresses often indicate a localized hardware problem.

## Resolution
The output meaning was clarified well enough to support continued troubleshooting and better interpretation of subsequent single-stick test results.

## Validation
Validation was conversational rather than procedural:
- The explanation aligned with the observed MemTest output pattern and helped interpret the earlier clustered failures.

## Follow-Up Tasks
- Continue using failing addresses and expected/found patterns as evidence when isolating DIMMs and slots.
- Keep notes on which DIMMs fail and whether failures occur at similar regions or only in certain hardware combinations.

## Lessons Learned
- Understanding the meaning of MemTest fields improves hardware fault isolation.
- Failing addresses are diagnostic clues, not just abstract numbers.
- Pattern consistency in expected vs found values can help distinguish hard faults from marginal instability.

---

# Command Reference

Double check: this chat did not include normal shell commands for Proxmox, Ceph, Docker, or Linux troubleshooting. The session centered on interpreting MemTest86+ output and defining a hardware isolation workflow. Because of that, the command reference below includes only actions or interfaces explicitly mentioned or strongly implied by the conversation.

## Command
```text
MemTest86+ boot and run
```

**What it does**  
Boots into MemTest86+ outside the installed operating system and performs low-level memory testing by writing patterns to RAM and reading them back.

**Why it was used at that moment**  
It was used to confirm whether the node had a real hardware memory fault.

**Expected result**  
- Healthy system: zero errors
- Faulty system: one or more memory errors, often repeatable

**What success or failure would indicate**  
- Success: the tested RAM configuration appears stable for that run
- Failure: the tested memory path is untrustworthy and may include a bad DIMM, bad slot, bad board trace, or CPU memory controller issue

**Risk level**  
Low. Diagnostic only.

**Safer alternative**  
None better for direct offline RAM validation. This is the appropriate tool.

---

## Command
```text
Power off the system and test each DIMM individually in the same slot
```

**Likely command used**  
No shell command was provided in the chat. This was a physical troubleshooting procedure.

**What it does**  
Controls variables by testing one memory stick at a time in a fixed slot so that results can be compared cleanly.

**Why it was used at that moment**  
To distinguish between:
- bad DIMM
- bad motherboard slot/channel
- broader platform-level instability

**Expected result**  
- Good DIMM in good slot: clean MemTest result
- Bad DIMM in same slot: repeated errors
- Multiple DIMMs failing only in one slot: slot/channel or board issue

**What success or failure would indicate**  
- Pass: that stick/slot combination is likely healthy
- Fail: that stick or that slot path is suspect

**Risk level**  
Low to moderate. Physical handling of RAM always carries minor ESD and handling risk.

**Safer alternative**  
Use anti-static precautions and motherboard manual slot guidance.

---

## Command
```text
Test newly purchased DIMMs one by one after old DIMM testing
```

**Likely command used**  
No shell command was provided in the chat. This was a physical troubleshooting step.

**What it does**  
Introduces known-new hardware into the same controlled test process to compare against the original DIMMs.

**Why it was used at that moment**  
To determine whether the original memory kit was faulty or whether the problem persisted even with replacement DIMMs.

**Expected result**  
- New DIMMs pass: original DIMM set becomes more suspect
- New DIMMs also fail in same test conditions: motherboard or CPU memory controller becomes more suspect

**What success or failure would indicate**  
- Success: replacement DIMMs may be viable for production use after further testing
- Failure: the issue may not be limited to the original RAM

**Risk level**  
Low to moderate. Same ESD and handling concerns as any DIMM swap.

**Safer alternative**  
None beyond good handling practice and controlled test methodology.

---

## Command
```text
Interpret failing address and expected/found values in MemTest86+ output
```

**Likely command used**  
Not a shell command. This was diagnostic interpretation of tool output.

**What it does**  
Uses MemTest-reported failing addresses and data mismatches to infer whether errors are localized, repeatable, and likely hardware-related.

**Why it was used at that moment**  
To determine whether the original large error count looked like random noise or a hard repeatable fault.

**Expected result**  
- Clustered addresses and repeatable bit differences suggest real hardware failure
- Isolated, rare, non-repeatable behavior would require more caution before concluding

**What success or failure would indicate**  
- Clear repeatable pattern: strong evidence of hardware fault
- No consistent pattern: requires more testing

**Risk level**  
Low.

**Safer alternative**  
None. This is normal diagnostic interpretation.

---

## Command
```text
Keep the affected Proxmox/Ceph node out of critical service until RAM testing is clean
```

**Likely command used**  
No exact command was provided in the chat.

**What it does**  
Operationally isolates the node so it does not host important VMs or trusted Ceph roles while hardware trust is in doubt.

**Why it was used at that moment**  
Because bad RAM can silently corrupt VM data and Ceph object contents.

**Expected result**  
Reduces the chance of additional corruption while hardware diagnosis is ongoing.

**What success or failure would indicate**  
- Success: unstable hardware is prevented from harming running workloads
- Failure to isolate: continued risk of host crashes or silent corruption

**Risk level**  
Low as an operational decision, but workload availability impact may be moderate depending on cluster capacity.

**Safer alternative**  
If capacity allows, fully power the node off until repair is complete.
