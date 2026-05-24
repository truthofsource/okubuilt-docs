---
title: "Proxmox Cloud-Init Snippet Storage and `cicustom` HA Behavior"
track: "infrastructure"
category: "automation"
type: "runbook"
logical_order: 50
date_rule: "Dates are removed from filenames, visible headings, indexes, generated metadata, and runbook body content."
---

# Proxmox Cloud-Init Snippet Storage and `cicustom` HA Behavior

## Summary
This work session focused on reusing and correcting a Proxmox `cicustom` configuration for a Docker VM that uses cloud-init custom user-data and network-data files. The main goals were to:
- restate the correct `qm set --cicustom` command
- adapt it from shared `snips` storage to `local` snippet storage
- clarify how Proxmox behaves during HA migration when more than one snippet-capable storage exists
- correct the network snippet filename from `docker0-net.yml` to `docker-net.yml`

The session resulted in a clean understanding that Proxmox does not automatically choose between snippet storages during HA movement. The storage ID explicitly referenced in `cicustom` determines where Proxmox looks when cloud-init data is regenerated.

## Environment
- Platform: Proxmox VE
- VM role: Debian Docker VM
- VM ID discussed: `100`
- Cloud-init custom snippet files:
  - `docker-userdata.yml`
  - `docker-net.yml`
- Storage backends discussed:
  - `snips` — shared snippet-capable storage
  - `local` — node-local directory storage
- Relevant Proxmox feature areas:
  - cloud-init
  - `cicustom`
  - HA migration behavior
  - snippet storage resolution

## Problem
The immediate need was to restate the correct `cicustom` command for the user’s Docker VM, then adjust it for node-local snippet storage instead of shared storage.

A second issue emerged around HA behavior: if both `snips` and `local` are enabled for snippets, it was unclear how Proxmox decides which storage to use after an HA migration.

A final correction was required because the network cloud-init file was initially referenced as `docker0-net.yml`, but the correct filename was `docker-net.yml`.

## Symptoms
Observed issues in the conversation included:
- need to reissue the correct `cicustom` command
- storage target changed from shared `snips` to `local`
- uncertainty about snippet source selection during HA migration
- incorrect network snippet filename initially used:
  - `docker0-net.yml`
- corrected filename later provided:
  - `docker-net.yml`

No runtime outage or explicit Proxmox error output was shown in this chat. The issues were configuration correctness and operational clarity.

## Actions Taken
1. Reissued the `cicustom` command for VM `100` using shared `snips` storage and the files:
   - `docker-userdata.yml`
   - `docker0-net.yml`

2. Adjusted the guidance to use `local` storage instead of `snips`.

3. Clarified that for `local` storage, snippet files must exist under:

   ```bash
   /var/lib/vz/snippets/
   ```

4. Provided a `local`-based `cicustom` example and recommended verifying the rendered cloud-init configuration.

5. Answered the HA migration question by explaining that Proxmox does not dynamically choose between available snippet storages. The storage ID written in the VM’s `cicustom` setting is authoritative.

6. Explained the operational implication:
   - `local:snippets/...` requires matching files on every node where the VM may run and where cloud-init may be regenerated.
   - `snips:snippets/...` is preferable for HA when it is cluster-accessible.

7. Recommended shared snippet storage for HA-aware operation.

8. Provided a helper loop to mirror snippet files to all nodes when using `local`.

9. Corrected the network snippet filename from `docker0-net.yml` to `docker-net.yml`.

10. Reissued both valid final forms of the command:
    - one using `local`
    - one using `snips`

## Key Findings
- Proxmox does not automatically prefer one snippet storage over another during HA migration.
- The VM’s `cicustom` entry explicitly pins the cloud-init snippet source storage.
- The storage prefix in `cicustom` matters more than whether multiple storages support snippets.
- HA migration alone does not imply automatic storage failover for cloud-init source files.
- If the VM uses `local:snippets/...`, the same snippet files must exist on each target node if cloud-init regeneration is expected there.
- Shared snippet storage is operationally cleaner for HA-capable VMs.
- The correct network file in this session was `docker-net.yml`, not `docker0-net.yml`.

## Resolution
The configuration guidance was corrected and finalized as follows:

For node-local snippet storage:
- use `local:snippets/docker-userdata.yml`
- use `local:snippets/docker-net.yml`

For shared snippet storage:
- use `snips:snippets/docker-userdata.yml`
- use `snips:snippets/docker-net.yml`

Operationally, the current best-practice resolution is:
- use shared snippet storage for HA-aware VMs where possible
- use `local` only if snippet files are manually mirrored to every relevant node

## Validation
Validation steps discussed in the chat included:
- check the VM configuration for the `cicustom` entry
- dump rendered cloud-init user data
- dump rendered cloud-init network data
- confirm snippet files exist at the expected storage path

These checks confirm:
- the VM is pointing to the intended storage and filenames
- Proxmox can render the correct cloud-init configuration
- the corrected filename is actually in use

## Follow-Up Tasks
- Decide whether VM `100` should remain on `local` snippets or move back to shared `snips`.
- If staying on `local`, copy snippet files to every HA-capable Proxmox node.
- Confirm `Snippets` content type is enabled on the intended storage.
- Standardize cloud-init snippet naming to avoid future `docker0-net.yml` vs `docker-net.yml` confusion.
- Re-run cloud-init regeneration after any snippet filename or storage change.
- Document the canonical location of all snippet files used by HA-managed VMs.

## Lessons Learned
- In Proxmox, `cicustom` is explicit, not automatic.
- Multiple snippet-capable storages do not create automatic fallback behavior.
- Shared snippet storage is simpler for clustered or HA-managed VMs.
- Local snippet storage adds operational overhead because every node must be kept in sync.
- File naming consistency matters; a small filename mismatch can break cloud-init customization.

---

# Command Reference

## Command
```bash
qm set 100 --cicustom "user=snips:snippets/docker-userdata.yml,network=snips:snippets/docker0-net.yml"
```

**Purpose:** Set custom cloud-init user-data and network-data sources for VM `100` using the shared `snips` storage.

**What it does:** Updates the VM configuration so Proxmox uses the specified snippet files instead of only the default cloud-init generated values.

**Important arguments:**
- `qm set`: modifies a Proxmox VM configuration.
- `100`: the VM ID being modified.
- `--cicustom`: tells Proxmox to use custom cloud-init files.
- `user=snips:snippets/docker-userdata.yml`: uses `docker-userdata.yml` as the user-data source from storage ID `snips`.
- `network=snips:snippets/docker0-net.yml`: uses `docker0-net.yml` as the network-data source from storage ID `snips`.

**Why it was used at that moment:** To restate the prior cloud-init customization command for the Docker VM.

**Expected result:** The VM config should reference the custom snippet files on `snips`.

**What success would indicate:** `qm config 100` should show the `cicustom` entry with the same storage and filenames.

**What failure would indicate:**
- storage ID may not exist
- `Snippets` content type may not be enabled
- referenced file may not exist
- filename may be wrong

**Risk level:** Low to moderate. It changes how cloud-init is rendered for the VM.

**Safer alternative:** Verify the snippet files exist and dump the rendered cloud-init config after setting it.

---

## Command
```bash
qm cloudinit update 100
```

**Purpose:** Regenerate the cloud-init drive for VM `100` after changing cloud-init settings.

**What it does:** Refreshes the cloud-init ISO/drive content attached to the VM based on current configuration, including any `cicustom` settings.

**Important arguments:**
- `qm cloudinit update`: rebuilds the VM’s cloud-init data source.
- `100`: the VM ID being updated.

**Why it was used at that moment:** After changing the `cicustom` path, Proxmox needed to regenerate the cloud-init data so the VM would use the new files.

**Expected result:** The cloud-init drive content should reflect the updated user-data and network-data sources.

**What success would indicate:** Subsequent `qm cloudinit dump` output should show the intended content.

**What failure would indicate:**
- bad snippet path
- invalid YAML
- inaccessible snippet storage
- unsupported or missing cloud-init disk configuration

**Risk level:** Low. It does not directly destroy VM data, but it can change future guest initialization behavior.

**Safer alternative:** Run the dump commands afterward before rebooting or redeploying the VM.

---

## Command
```bash
qm set 100 --cicustom "user=local:snippets/docker-userdata.yml,network=local:snippets/docker0-net.yml"
```

**Purpose:** Configure VM `100` to use node-local snippet files stored on `local` storage.

**What it does:** Pins cloud-init custom files to Proxmox directory storage `local`, which maps to the local filesystem on the node.

**Important arguments:**
- `local:snippets/...`: refers to snippet files stored on the node-local Proxmox storage named `local`.

**Why it was used at that moment:** The user stated they were using `local` storage instead of `snips`.

**Expected result:** The VM config should now look for the snippet files on `local`.

**What success would indicate:** The VM config reflects `local:snippets/...`, and the files exist under:

```bash
/var/lib/vz/snippets/
```

**What failure would indicate:**
- `local` storage is missing `Snippets` content support
- files are not present locally
- wrong filename used

**Risk level:** Moderate in HA contexts. Local storage is not automatically shared across nodes.

**Safer alternative:** Use a shared snippet storage for any VM that may move between nodes.

---

## Command
```bash
qm config 100 | grep cicustom
```

**Purpose:** Check whether VM `100` has a `cicustom` entry and see exactly what it points to.

**What it does:** Prints the VM configuration and filters it for lines containing `cicustom`.

**Important arguments:**
- `qm config 100`: displays the full configuration of VM `100`.
- `| grep cicustom`: filters output to only the cloud-init custom line.

**Why it was used at that moment:** To confirm the effective storage ID and filenames after editing the config.

**Expected result:** A line showing the configured `cicustom` paths.

**What success would indicate:** The VM is pinned to the intended snippet storage and filenames.

**What failure would indicate:** No `cicustom` line means the custom snippet reference was not applied.

**Risk level:** Low. Read-only validation.

**Safer alternative:** None needed; this is already safe.

---

## Command
```bash
qm cloudinit dump 100 user
```

**Purpose:** Display the rendered cloud-init user-data for VM `100`.

**What it does:** Shows the effective user-data that Proxmox will present to the guest.

**Important arguments:**
- `dump`: outputs the generated cloud-init data instead of applying anything.
- `user`: requests the user-data portion.

**Why it was used at that moment:** To verify that the user-data snippet was being rendered correctly.

**Expected result:** A YAML output containing the effective user-data.

**What success would indicate:** The intended custom data is visible and readable.

**What failure would indicate:**
- missing file
- malformed YAML
- inaccessible storage
- misconfigured `cicustom`

**Risk level:** Low. Read-only validation.

---

## Command
```bash
qm cloudinit dump 100 network
```

**Purpose:** Display the rendered cloud-init network-data for VM `100`.

**What it does:** Shows the network configuration Proxmox will pass to the guest through cloud-init.

**Important arguments:**
- `network`: requests the network-data portion.

**Why it was used at that moment:** To verify the network snippet path and confirm the corrected filename was in use.

**Expected result:** Rendered network YAML for the VM.

**What success would indicate:** The expected network config appears.

**What failure would indicate:**
- bad filename
- invalid network YAML
- inaccessible snippet path
- stale `cicustom` config

**Risk level:** Low. Read-only validation.

---

## Command
```bash
ls -l /var/lib/vz/snippets/docker-userdata.yml
ls -l /var/lib/vz/snippets/docker0-net.yml
```

**Purpose:** Verify that the local snippet files exist on disk.

**What it does:** Lists the files and their permissions in the Proxmox local snippets directory.

**Important arguments:**
- `ls -l`: long listing format showing permissions, owner, size, and timestamp.

**Why it was used at that moment:** To validate local snippet placement when using `local:snippets/...`.

**Expected result:** The specified files should appear in the output.

**What success would indicate:** The snippet files are present on that node.

**What failure would indicate:** Missing file, typo, or wrong node-local placement.

**Risk level:** Low. Read-only validation.

---

## Command
```bash
for n in pve1 pve2 pve3 pve4; do
  ssh root@$n "mkdir -p /var/lib/vz/snippets"
  scp /var/lib/vz/snippets/docker-userdata.yml root@$n:/var/lib/vz/snippets/
  scp /var/lib/vz/snippets/docker0-net.yml   root@$n:/var/lib/vz/snippets/
done
```

**Purpose:** Mirror local snippet files to multiple Proxmox nodes for HA compatibility.

**What it does:** Creates the snippet directory on each target node if needed, then copies the snippet files to that same path on every node listed.

**Important arguments:**
- `for n in ...; do ... done`: shell loop over the listed node names.
- `ssh root@$n "mkdir -p /var/lib/vz/snippets"`: ensures the snippet directory exists remotely.
- `scp ... root@$n:/var/lib/vz/snippets/`: copies files to the target node.

**Why it was used at that moment:** Because `local` storage is node-local, every node needs identical snippet files if the VM may run or be regenerated there.

**Expected result:** All listed nodes should receive the snippet files in the correct local path.

**What success would indicate:** The files exist on every node and can support local snippet-based cloud-init regeneration.

**What failure would indicate:**
- SSH connectivity issue
- authentication problem
- incorrect hostnames
- missing source file
- permissions issue

**Risk level:** Moderate. It writes files to multiple cluster nodes.

**Safer alternative:** Use shared snippet storage instead of manually synchronizing local files.

---

## Command
```bash
qm set 100 --cicustom "user=snips:snippets/docker-userdata.yml,network=snips:snippets/docker-net.yml"
```

**Purpose:** Set the corrected shared-storage `cicustom` configuration using the final confirmed network filename.

**What it does:** Pins VM `100` to the `snips` storage and uses:
- `docker-userdata.yml`
- `docker-net.yml`

**Why it was used at that moment:** To correct the earlier network filename from `docker0-net.yml` to `docker-net.yml`.

**Expected result:** The VM config references the corrected shared snippet files.

**What success would indicate:** `qm config 100 | grep cicustom` shows `docker-net.yml`.

**What failure would indicate:** The corrected file may not exist on the shared storage.

**Risk level:** Low to moderate. Changes guest init source configuration.

---

## Command
```bash
qm set 100 --cicustom "user=local:snippets/docker-userdata.yml,network=local:snippets/docker-net.yml"
```

**Purpose:** Set the corrected local-storage `cicustom` configuration using the final confirmed network filename.

**What it does:** Pins VM `100` to local snippet files using the corrected network-data filename.

**Why it was used at that moment:** To provide the final corrected command for the user’s current storage choice.

**Expected result:** The VM uses the local snippet files with the correct names on that node.

**What success would indicate:** Both config and cloud-init dump commands reflect `docker-net.yml`.

**What failure would indicate:** The corrected local file may be absent from `/var/lib/vz/snippets/`.

**Risk level:** Moderate in HA contexts because `local` must be synchronized manually across nodes.
