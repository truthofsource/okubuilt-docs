---
title: "Planning TrueNAS VM ZFS Storage on Proxmox with 4×16TB HDDs"
track: "infrastructure"
category: "storage"
type: "runbook"
logical_order: 10
date_rule: "Dates are removed from filenames, visible headings, indexes, generated metadata, and runbook body content."
---

# Planning TrueNAS VM ZFS Storage on Proxmox with 4×16TB HDDs

## Summary
This work session focused on planning a TrueNAS virtual machine on Proxmox to manage a ZFS pool built from four 16TB HDDs. The main goals were to determine the correct ZFS layout, decide whether motherboard SATA controller passthrough was viable, verify whether a Ceph SATA SSD would be unintentionally included in passthrough, and identify the correct hardware approach for clean disk presentation to TrueNAS.

The session ended with the conclusion that the onboard SATA controller could not be safely passed through because all SATA devices on the host were attached to the same Intel AHCI controller, including the Ceph SSD. The recommended path forward was to purchase a dedicated HBA and use it in IT mode for passthrough to the TrueNAS VM.

## Environment
- **Hypervisor:** Proxmox VE
- **Host:** `mainframe`
- **Boot device:** Separate NVMe drive for Proxmox host OS
- **Target storage VM:** Planned TrueNAS VM
- **Intended ZFS disks:** 4×16TB HDD
- **Other SATA device present:** 1 SATA SSD already part of a cephpool
- **Onboard SATA controller:** Intel Cannon Lake PCH SATA AHCI Controller at `00:17.0`
- **Relevant storage context:** Ceph pool already in use on the Proxmox host; one SATA SSD must remain under host control and must not be exposed to TrueNAS by mistake

## Problem
The user wanted to build ZFS storage in a TrueNAS VM on Proxmox using four 16TB HDDs and preferred to passthrough the entire SATA controller for clean disk access. However, there was concern that another SATA SSD used by Ceph might be attached to the same controller and would be included unintentionally.

A related question was whether one physical SATA port on the motherboard corresponded to one separate SATA controller.

## Symptoms
No outage or failure occurred during this session. This was a design and verification task. The main risks identified were:
- accidental passthrough of the Ceph SATA SSD to the TrueNAS VM
- loss of Proxmox host access to all motherboard SATA devices if the whole controller were passed through
- potential cephpool breakage if the Ceph SSD were removed from host access
- incorrect assumption that one SATA port equals one controller

## Actions Taken
1. Reviewed the intended storage layout for the TrueNAS VM.
2. Adjusted the original plan from 5 HDDs to **4×16TB HDDs**.
3. Discussed suitable ZFS layouts for four large-capacity disks.
4. Evaluated whole-controller passthrough as the preferred method for exposing disks to TrueNAS.
5. Clarified the distinction between:
   - a **SATA port**
   - a **SATA controller**
6. Ran a PCI device listing on the Proxmox host to enumerate SATA controllers:

```bash
lspci -nn | egrep -i 'sata|ahci|asmedia|marvell'
```

Purpose: identify whether the system had one or multiple SATA controllers.

7. Ran a disk path listing to map attached SATA disks to their PCI controller:

```bash
ls -l /dev/disk/by-path/ | egrep 'ata-|sata'
```

Purpose: verify which controller each SATA disk used.

8. Interpreted the command output to determine whether the four 16TB HDDs and the Ceph SSD were isolated on different controllers or shared the same one.
9. Ruled out onboard controller passthrough because all SATA disks were attached to the same controller.
10. Evaluated alternative approaches:
    - use a dedicated PCIe HBA for the 4 HDDs
    - passthrough individual disks by `/dev/disk/by-id/`
11. Recommended purchase of an LSI HBA and explained why **IT mode** is required for ZFS/TrueNAS.

## Key Findings
- The Proxmox host has **only one onboard SATA controller**:
  - `00:17.0 SATA controller [0106]: Intel Corporation Cannon Lake PCH SATA AHCI Controller [8086:a352]`
- All enumerated SATA devices were attached to that same controller via paths like:
  - `pci-0000:00:17.0-ata-*`
- This means the motherboard SATA ports are not independent controllers; they are multiple ports provided by a single AHCI controller.
- As a result, passing through controller `00:17.0` to the TrueNAS VM would remove **all SATA-attached disks** from the Proxmox host.
- That would include the SATA SSD already used by Ceph, which must remain under Proxmox control.
- Therefore, **whole-controller passthrough of the onboard SATA controller is not safe in the current hardware layout**.
- For four 16TB HDDs, the most conservative recommended ZFS layout is **RAIDZ2**, because large-disk rebuilds are lengthy and double parity provides better fault tolerance.
- A dedicated HBA in **IT mode** is the cleanest solution for TrueNAS virtualization:
  - the 4 HDDs would connect to the HBA
  - the Ceph SSD would remain on motherboard SATA
  - the HBA would be passed through as a PCI device to the TrueNAS VM

## Resolution
### Current status
No live storage migration or passthrough change was performed during this session.

### Final decision
The current onboard SATA controller should **not** be passed through to the TrueNAS VM because it also carries the Ceph SATA SSD.

### Recommended implementation path
1. Purchase a supported PCIe HBA such as:
   - LSI 9207-8i
   - LSI 9211-8i
   - LSI 9300-8i
2. Ensure the HBA is running **IT mode** firmware.
3. Attach the 4×16TB HDDs to the HBA.
4. Leave the Ceph SSD on the motherboard SATA controller.
5. Pass through the HBA PCI device to the TrueNAS VM.
6. Build the TrueNAS pool as **RAIDZ2** unless capacity priorities justify another layout.

### Alternative workaround
If no HBA is added, individual-disk passthrough using stable `/dev/disk/by-id/` names is possible, but this is less ideal than HBA passthrough for a TrueNAS VM design.

## Validation
The conclusion was validated by direct host inspection.

### SATA controller enumeration
```bash
lspci -nn | egrep -i 'sata|ahci|asmedia|marvell'
```

This showed only one SATA controller: `00:17.0`.

### Disk-to-controller mapping
```bash
ls -l /dev/disk/by-path/ | egrep 'ata-|sata'
```

This showed all SATA disks mapped to `pci-0000:00:17.0-ata-*`, confirming that the HDDs and Ceph SSD share the same controller.

This was sufficient to validate that onboard controller passthrough would include every motherboard SATA disk.

## Follow-Up Tasks
- Buy a supported PCIe HBA suitable for TrueNAS passthrough.
- Confirm the HBA is flashed to **IT mode** before use.
- Buy the correct forward breakout cables for the chosen HBA.
- Physically move the four 16TB HDDs from motherboard SATA to the HBA.
- Leave the Ceph SSD on the motherboard SATA controller.
- Enable and validate IOMMU support in BIOS and Proxmox before PCI passthrough.
- Create or configure the TrueNAS VM with PCI passthrough of the HBA.
- Build the ZFS pool in TrueNAS, likely as RAIDZ2.
- Validate SMART visibility, disk serial visibility, and pool health inside TrueNAS after deployment.

## Lessons Learned
- A motherboard SATA **port** is not the same thing as a SATA **controller**.
- Consumer motherboards often expose several SATA ports through a single Intel AHCI controller.
- Whole-controller passthrough is only safe when every disk on that controller is intended for the guest VM.
- If one host-critical disk such as a Ceph OSD SSD is on the same controller, controller passthrough is not viable.
- For virtualized TrueNAS, a dedicated HBA in IT mode is the cleanest and most maintainable approach.
- For large-capacity HDD pools, RAIDZ2 is often the safer default than RAIDZ1 because rebuild windows are longer and risk exposure is higher.

---

# Command Reference

## Command
```bash
lspci -nn | egrep -i 'sata|ahci|asmedia|marvell'
```

### What it does
Lists PCI devices on the Proxmox host and filters the output for SATA-related controller names and common vendor/controller keywords.

### Important flags and arguments
- `lspci`  
  Lists PCI devices in the system.
- `-nn`  
  Shows both human-readable names and numeric vendor/device IDs, useful for exact hardware identification.
- `egrep -i`  
  Filters output case-insensitively for matching keywords.
- `'sata|ahci|asmedia|marvell'`  
  Searches for common onboard SATA or add-in controller identifiers.

### Why it was used at that moment
It was used to determine whether the Proxmox host had:
- only one onboard SATA controller, or
- multiple SATA controllers that might allow safe isolation of disks for passthrough.

### Expected result
One or more controller lines with PCI addresses such as `00:17.0`.

### What success or failure would indicate
- **Success:** hardware inventory is visible and can be used for passthrough planning.
- **If only one SATA controller appears:** all motherboard SATA ports may belong to the same controller.
- **If multiple controllers appear:** it may be possible to isolate the HDDs and Ceph SSD onto different controllers.

### Risk
Low risk. Read-only inspection command.

### Safer alternative
None needed. This is already a safe discovery command.

---

## Command
```bash
ls -l /dev/disk/by-path/ | egrep 'ata-|sata'
```

### What it does
Lists persistent disk path symlinks and filters for SATA-attached devices. These path names often include the PCI controller address and ATA port mapping, which helps determine which controller a disk is attached to.

### Important flags and arguments
- `ls -l`  
  Shows symlink targets rather than only file names.
- `/dev/disk/by-path/`  
  Contains stable device symlinks based on bus/path topology.
- `egrep 'ata-|sata'`  
  Filters to show ATA/SATA-related entries.

### Why it was used at that moment
It was used to map each SATA disk to its controller and to confirm whether the 4 HDDs and the Ceph SSD shared the same PCI SATA controller.

### Expected result
Entries such as:

```bash
pci-0000:00:17.0-ata-1 -> ../../sda
```

These expose the PCI controller address and the Linux block device currently associated with that path.

### What success or failure would indicate
- **Success:** each disk can be mapped to a specific controller.
- **If all disks show the same PCI address:** whole-controller passthrough would include them all.
- **If disks show different PCI addresses:** controller separation may be possible.

### Risk
Low risk. Read-only inspection command.

### Safer alternative
None needed. This is an appropriate topology-inspection command.

---

## Likely command used
```bash
qm set <VMID> -hostpci0 0000:00:17.0,pcie=1
```

### What it does
Adds a PCI passthrough device to a Proxmox VM configuration. In this case it would pass a SATA controller through to the guest.

### Important flags and arguments
- `qm set`  
  Modifies a Proxmox VM configuration.
- `<VMID>`  
  Target VM ID, which would be the TrueNAS VM.
- `-hostpci0`  
  Adds the first passthrough PCI device entry.
- `0000:00:17.0`  
  Full PCI address of the controller.
- `pcie=1`  
  Presents the device as a PCIe device when appropriate.

### Why it was discussed
This is the standard Proxmox method for passing an entire controller to a VM. It was relevant because the user initially wanted whole-controller passthrough for TrueNAS.

### Expected result
The VM configuration would include the SATA controller as a passthrough device, and on boot the guest OS would take ownership of that controller.

### What success or failure would indicate
- **Success:** the VM sees the controller and the host no longer manages disks behind it.
- **Failure or incorrect usage:** the VM may fail to start, or the host may lose access to disks it still needs.

### Risk
High risk in this environment. Passing through `00:17.0` would also remove the Ceph SATA SSD and all other motherboard SATA disks from Proxmox host control.

### Safer alternative
Use a dedicated HBA for passthrough, or passthrough only specific disks by `/dev/disk/by-id/`.

---

## Likely command used
```bash
lsblk -o NAME,SIZE,MODEL,SERIAL,TYPE
```

### What it does
Displays block devices with selected columns including size, model, serial, and type.

### Important flags and arguments
- `lsblk`  
  Lists block devices.
- `-o`  
  Selects custom output columns.
- `NAME,SIZE,MODEL,SERIAL,TYPE`  
  Useful for distinguishing large HDDs from SSDs and identifying exact disks by model and serial.

### Why it was suggested
It would be used to identify which Linux block devices correspond to the 16TB HDDs and which disk is the Ceph SSD.

### Expected result
A readable disk inventory showing device names and hardware identity data.

### What success or failure would indicate
- **Success:** disks can be clearly identified before passthrough planning.
- **Failure or missing serials:** further identification may require SMART tools or additional queries.

### Risk
Low risk. Read-only inspection command.

### Safer alternative
None needed.

---

## Likely command used
```bash
ls -l /dev/disk/by-id/ | egrep 'ata-|wwn-' | egrep -v 'part'
```

### What it does
Lists stable disk identifiers that should be used instead of `/dev/sdX` names when passing individual disks to a VM.

### Important flags and arguments
- `/dev/disk/by-id/`  
  Persistent device names based on serial/model/WWN.
- `egrep 'ata-|wwn-'`  
  Filters for ATA or WWN-based identifiers.
- `egrep -v 'part'`  
  Excludes partition symlinks and shows whole disks only.

### Why it was suggested
This is the preferred identification method if passing through specific disks rather than a whole controller.

### Expected result
Stable device paths suitable for raw-disk passthrough in Proxmox.

### What success or failure would indicate
- **Success:** individual HDDs can be safely targeted by stable ID.
- **Failure or ambiguity:** disk identification is incomplete and should be verified before passthrough.

### Risk
Low risk. Read-only inspection command.

### Safer alternative
None needed.

---

## Likely command used
```bash
qm set <VMID> -scsi1 /dev/disk/by-id/ata-<disk-id>
```

### What it does
Assigns a host disk directly to a Proxmox VM as a raw SCSI device using a stable `/dev/disk/by-id/` path.

### Important flags and arguments
- `qm set`  
  Edits Proxmox VM configuration.
- `-scsi1`  
  Attaches a disk to the first available SCSI slot.
- `/dev/disk/by-id/ata-<disk-id>`  
  Stable host path to the physical disk.

### Why it was discussed
This is the fallback method when whole-controller passthrough is not possible and the user still wants TrueNAS to see real disks.

### Expected result
The specified physical disk becomes available inside the guest VM.

### What success or failure would indicate
- **Success:** the guest sees the individual disk.
- **Failure:** incorrect device mapping or a VM boot/config issue.
- **Incorrect disk choice:** a host-managed disk could be exposed accidentally.

### Risk
Moderate. Safe when done carefully with correct disk IDs, but dangerous if the wrong disk is selected.

### Safer alternative
Dedicated HBA passthrough remains safer and cleaner.

---

## Likely command used
```bash
update-grub
```

### What it does
Rebuilds the GRUB bootloader configuration after changes to kernel boot parameters.

### Important flags and arguments
No special flags here.

### Why it was discussed
Needed when enabling IOMMU-related kernel parameters for PCI passthrough on Proxmox.

### Expected result
GRUB config regenerates successfully.

### What success or failure would indicate
- **Success:** bootloader will use updated kernel arguments at next reboot.
- **Failure:** passthrough-related boot parameter changes may not take effect.

### Risk
Moderate. Generally safe, but boot configuration changes should be made carefully on production hosts.

### Safer alternative
Back up `/etc/default/grub` before modifying it.

---

## Likely command used
```bash
update-initramfs -u -k all
```

### What it does
Rebuilds initramfs images for installed kernels, ensuring boot-time modules and parameters are updated.

### Important flags and arguments
- `-u`  
  Updates existing initramfs images.
- `-k all`  
  Applies the update to all installed kernels.

### Why it was discussed
Often paired with IOMMU or vfio-related configuration changes before rebooting a Proxmox host for PCI passthrough readiness.

### Expected result
Initramfs images rebuild successfully.

### What success or failure would indicate
- **Success:** boot environment is updated for passthrough-related changes.
- **Failure:** the host may boot without necessary module/initramfs updates.

### Risk
Moderate. Common system administration command, but it affects boot preparation.

### Safer alternative
Ensure recent host backups and console access exist before major boot-chain changes.

---

## Likely command used
```bash
find /sys/kernel/iommu_groups/ -type l | grep -E '00:17.0|03:00.0'
```

### What it does
Inspects IOMMU group membership for specific PCI devices to determine whether passthrough isolation is clean.

### Important flags and arguments
- `find /sys/kernel/iommu_groups/ -type l`  
  Lists PCI devices grouped by IOMMU isolation boundaries.
- `grep -E '00:17.0|03:00.0'`  
  Filters for target controller/device addresses.

### Why it was discussed
A device must be in a passthrough-safe IOMMU grouping, especially for full PCI controller passthrough.

### Expected result
Output showing the group containing the target controller.

### What success or failure would indicate
- **Success with clean isolation:** passthrough is more likely to be practical.
- **Shared group with critical devices:** passthrough may be unsafe or require workarounds.

### Risk
Low risk. Read-only inspection command.

### Safer alternative
None needed.

---

## Concept note: IT mode
No shell command was run for this, but it was an important technical point in the session.

### What it means
**IT mode** means the HBA firmware exposes each attached drive directly to the operating system without hardware RAID abstraction.

### Why it matters here
TrueNAS and ZFS should manage disks directly. An HBA in RAID/IR mode can hide or virtualize disks, which is not desirable for ZFS.

### Expected outcome
With an HBA in IT mode:
- each disk appears individually in TrueNAS
- SMART and serial information are visible
- ZFS manages redundancy and recovery directly

### Risk
Using a RAID-mode card instead of IT mode can complicate ZFS visibility, health checks, and recovery.

### Safer alternative
Buy an HBA confirmed to be flashed to IT mode before installation.
