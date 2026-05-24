---
title: "Home Assistant OS VM Deployment on Proxmox with Ceph Storage"
track: "infrastructure"
category: "compute"
type: "runbook"
logical_order: 10
date_rule: "Dates are removed from filenames, visible headings, indexes, generated metadata, and runbook body content."
---

# Home Assistant OS VM Deployment on Proxmox with Ceph Storage

## Summary
A Home Assistant OS virtual machine was deployed on a Proxmox cluster and its disk was placed on shared Ceph RBD storage to support cluster portability and future Proxmox HA use. The work session focused on choosing the correct storage location for the Home Assistant image, staging the QCOW2 image on file-based storage, importing it into Ceph RBD, configuring the VM, troubleshooting a boot failure, and clarifying Proxmox console behavior.

## Environment
- Platform: Proxmox VE cluster
- Hypervisor host used during this session: `pve1`
- VM created: `150` (`homeassistant`)
- Guest OS image: `haos_ova-16.3.qcow2`
- Shared VM storage: `cephpool` (Ceph RBD)
- Shared file storage: `snips` (CephFS)
- Staging file locations used:
  - `/var/lib/vz/template/qemu/`
  - `/mnt/pve/snips/iso/`
- VM network bridge: `vmbr0`
- VM CPU model: `x86-64-v3`
- VM memory: `4096 MB`
- VM vCPUs: `2`
- Proxmox console methods discussed:
  - VGA console via GUI `Console` / `noVNC`
  - Serial console via `qm terminal`
- Router/firewall context: OPNsense
- User workstation used for image transfer: Windows PowerShell with `scp`

## Problem
A Home Assistant OS VM needed to be created in a way that supports shared storage and future HA behavior. There was confusion around where the image file should live, whether cloud-init was required, how to upload or move the image, and why the VM would not boot after initial creation.

## Symptoms
- Uncertainty about whether the Home Assistant image itself should be stored on Ceph RBD or CephFS.
- GUI upload/import flow was not working as expected.
- `scp` upload failed because the destination directory did not exist.
- The VM appeared to be running but `qm terminal 150` only showed:
  ```text
  starting serial terminal on interface serial0 (press Ctrl+O to exit)
  ```
- The VGA console showed the VM stuck at:
  ```text
  Booting from hard disk...
  ```
- Uncertainty about whether Home Assistant required a cloud-init drive.
- Uncertainty about how to identify the VM IP address after boot.

## Actions Taken
1. Determined that the Home Assistant VM disk should live on shared Ceph RBD storage (`cephpool`) for HA compatibility, while image files should remain on file-based storage.
2. Clarified that Ceph RBD is block storage and CephFS is file-based storage.
3. Evaluated whether image files should be kept on CephFS and concluded that CephFS is a good shared library location for QCOW2 and ISO files.
4. Decided to keep the existing CephFS storage ID `snips` rather than renaming it, to avoid breaking existing cloud-init snippet references.
5. Created or used a shared image library path under CephFS:
   ```bash
   mkdir -p /mnt/pve/snips/iso
   ```
   Purpose: create a shared location for ISO and QCOW2 files.
6. Moved the Home Assistant QCOW2 file into the CephFS ISO folder:
   ```bash
   mv /var/lib/vz/template/qemu/haos_ova-16.3.qcow2 /mnt/pve/snips/iso/
   ```
   Purpose: place the image in shared file storage.
7. Discussed downloading Debian cloud images into the same shared CephFS library for future VM creation.
8. Confirmed that Home Assistant OS does not use cloud-init and does not need a cloud-init drive.
9. Created a Proxmox VM shell for Home Assistant:
   ```bash
   qm create 150 \
     --name homeassistant \
     --memory 4096 \
     --cores 2 \
     --net0 virtio,bridge=vmbr0 \
     --ostype l26
   ```
   Purpose: create the base VM definition before importing the disk.
10. Imported the Home Assistant image into Ceph RBD:
   ```bash
   qm importdisk 150 /mnt/pve/snips/iso/haos_ova-16.3.qcow2 cephpool --format raw
   ```
   Purpose: create a real Ceph-backed VM disk from the QCOW2 source file.
11. Attached the imported Ceph disk to the VM and set boot order:
   ```bash
   qm set 150 --scsihw virtio-scsi-single --scsi0 cephpool:vm-150-disk-0
   qm set 150 --boot order=scsi0
   ```
   Purpose: attach the Ceph-backed disk as the VM boot disk.
12. Changed the CPU model to a cluster-compatible modern baseline instead of host passthrough:
   ```bash
   qm set 150 --cpu x86-64-v3
   ```
   Purpose: standardize CPU features for migration/HA compatibility across nodes.
13. Added serial console support and standard VGA output:
   ```bash
   qm set 150 --serial0 socket --vga std
   ```
   Purpose: keep both serial and VGA console options available.
14. Verified the VM status:
   ```bash
   qm status 150
   ```
   Purpose: confirm that the VM process was actually running.
15. Checked the VM configuration:
   ```bash
   qm config 150
   ```
   Purpose: confirm the attached boot disk, CPU model, console devices, and boot order.
16. Diagnosed the boot problem after the console showed `Booting from hard disk...`.
17. Determined that the Home Assistant image expected UEFI boot, not legacy BIOS.
18. Stopped the VM and converted it to UEFI boot:
   ```bash
   qm stop 150
   qm set 150 --bios ovmf --machine q35
   qm set 150 --efidisk0 cephpool:1,pre-enrolled-keys=1
   qm set 150 --boot order=scsi0
   ```
   Purpose: switch firmware to OVMF/UEFI and add the required EFI vars disk.
19. Restarted the VM:
   ```bash
   qm start 150
   ```
   Purpose: boot the VM using UEFI firmware.
20. Used the Proxmox GUI VGA console rather than relying only on `qm terminal` to watch the actual boot process and confirm the guest came up.
21. Clarified the difference between VGA console, serial console, `qm terminal`, and the Proxmox GUI Console tab.

## Key Findings
- `cephpool` is appropriate for the VM disk because it is shared block storage used for running VMs.
- `snips` is CephFS and is suitable for storing QCOW2, ISO, and snippet files because it is file-based shared storage.
- `qm importdisk` does not move the QCOW2 file onto Ceph as a file; it reads the source file and creates a new VM disk volume in Ceph RBD.
- Home Assistant OS does not require cloud-init.
- The VM was running even when `qm terminal` did not show a useful prompt.
- `qm terminal` connects only to `serial0`; it does not show VGA output.
- The initial boot failure was caused by firmware mismatch:
  - VM firmware was legacy BIOS / SeaBIOS
  - Home Assistant OS image required UEFI / OVMF
- After switching to `bios: ovmf` and adding an EFI disk, the imported Home Assistant disk booted successfully.
- `x86-64-v3` is a better fit than `host` when consistency across cluster nodes matters.

## Resolution
The Home Assistant VM was successfully deployed by:
- storing the image file on CephFS (`/mnt/pve/snips/iso/haos_ova-16.3.qcow2`)
- importing it into Ceph RBD (`cephpool`) as the actual VM disk
- configuring the VM to use `x86-64-v3`
- switching the VM from legacy BIOS boot to UEFI boot with OVMF and an EFI disk

The VM then booted successfully.

## Validation
Success was confirmed by:
- `qm status 150` returning `status: running`
- `qm config 150` showing:
  - `scsi0: cephpool:vm-150-disk-0`
  - `cpu: x86-64-v3`
  - `serial0: socket`
  - `vga: std`
- the Proxmox VGA console showing successful boot after the OVMF change
- Home Assistant becoming accessible through its web interface after boot

## Follow-Up Tasks
- Add VM `150` to a Proxmox HA group only if Ceph cluster health is stable enough for critical services.
- Confirm Home Assistant receives a consistent IP address, preferably through DHCP reservation in OPNsense.
- Consider removing unused or unnecessary devices if the VM configuration should be minimized.
- Decide whether to keep `serial0` enabled long-term or rely only on VGA console access.
- Keep `snips` as the shared image/snippet library and expand its use for ISO/QCOW2 storage.
- Back up the VM through Proxmox and also configure Home Assistant internal backups.
- If USB Zigbee/Z-Wave devices will be used, add USB passthrough to the VM and test device persistence after reboot or failover.

## Lessons Learned
- Shared VM disks belong on Ceph RBD; source images belong on file-based storage such as CephFS.
- `qm importdisk` creates a VM disk from an image file; it does not store the image file itself on RBD.
- Many appliance-style QCOW2 images, including Home Assistant OS, may require UEFI boot.
- A VM can be healthy even if `qm terminal` looks empty; console type matters.
- Keep storage naming stable when it is already referenced in cloud-init or automation.
- For shared homelab image libraries, CephFS is a practical place to keep QCOW2 and ISO files.
- Use VGA console for BIOS/UEFI and early boot troubleshooting; use `qm terminal` only when the guest is known to expose a serial console.

---

# Command Reference

## Command
```bash
mkdir -p /var/lib/vz/template/qemu
```

### What it does
Creates the directory used as a local staging path for QEMU image files.

### Important arguments
- `-p`: creates parent directories as needed and does not fail if the directory already exists.

### Why it was used
The `scp` upload initially failed because the destination path did not exist.

### Expected result
The directory becomes available for file upload.

### Success vs. failure
- Success: the path exists and `scp` can write into it.
- Failure: upload continues to fail because the path is missing or permissions are wrong.

### Risk
Low.

### Safer alternative
None needed.

---

## Command
```powershell
scp "$env:USERPROFILE\Downloads\haos_ova-16.3.qcow2" root@192.168.16.12:/var/lib/vz/template/qemu/
```

### What it does
Copies the Home Assistant QCOW2 image from the Windows workstation to the Proxmox node over SSH.

### Important arguments
- `"$env:USERPROFILE\Downloads\haos_ova-16.3.qcow2"`: source file on Windows.
- `root@192.168.16.12`: destination SSH user and Proxmox node.
- `:/var/lib/vz/template/qemu/`: destination directory on the node.

### Why it was used
The Home Assistant image had to be staged on the Proxmox side before being moved or imported.

### Expected result
The file appears in the target directory on the Proxmox host.

### Success vs. failure
- Success: file is present on the node.
- Failure: authentication, path, or permissions problem.

### Risk
Moderate because it uses the `root` account.

### Safer alternative
Use a non-root SSH account with delegated permissions where possible.

---

## Command
```bash
mkdir -p /mnt/pve/snips/iso
```

### What it does
Creates a shared CephFS directory for ISO and QCOW2 image storage.

### Important arguments
- `-p`: create parents if necessary.

### Why it was used
To establish a shared image library under the existing `snips` storage.

### Expected result
The `iso` directory exists on CephFS.

### Success vs. failure
- Success: shared path exists and is writable.
- Failure: the CephFS mount may be unavailable.

### Risk
Low.

### Safer alternative
None needed.

---

## Command
```bash
mv /var/lib/vz/template/qemu/haos_ova-16.3.qcow2 /mnt/pve/snips/iso/
```

### What it does
Moves the Home Assistant image from local staging into the shared CephFS image library.

### Important arguments
- Source path: local staging copy.
- Destination path: shared CephFS library.

### Why it was used
To centralize images on shared file-based storage rather than leaving them only on one host.

### Expected result
The file disappears from the local staging path and appears on CephFS.

### Success vs. failure
- Success: image is accessible from the CephFS path.
- Failure: source file missing, destination unavailable, or permissions issue.

### Risk
Low to moderate. A move removes the original source from the local path.

### Safer alternative
Use `cp` first, confirm the copy, then delete the original.

---

## Command
```bash
wget https://cdimage.debian.org/cdimage/cloud/bookworm/latest/debian-12-genericcloud-amd64.qcow2
```

### What it does
Downloads the Debian 12 generic cloud QCOW2 image.

### Important arguments
- URL: direct link to the Debian cloud image.

### Why it was used
To populate the shared image library with additional reusable VM source images.

### Expected result
A Debian QCOW2 file is written into the current working directory.

### Success vs. failure
- Success: download completes and the file exists.
- Failure: network, DNS, TLS, or remote file availability issue.

### Risk
Low.

### Safer alternative
Verify checksums after download.

---

## Command
```bash
qm create 150 \
  --name homeassistant \
  --memory 4096 \
  --cores 2 \
  --net0 virtio,bridge=vmbr0 \
  --ostype l26
```

### What it does
Creates the initial Proxmox VM definition.

### Important arguments
- `150`: VMID.
- `--name homeassistant`: VM name.
- `--memory 4096`: RAM in MB.
- `--cores 2`: CPU core count.
- `--net0 virtio,bridge=vmbr0`: attach one virtio NIC to `vmbr0`.
- `--ostype l26`: modern Linux guest type.

### Why it was used
A VM shell must exist before importing and attaching disks.

### Expected result
A new VM config is created in Proxmox.

### Success vs. failure
- Success: `qm config 150` returns a valid VM config.
- Failure: VMID conflict or invalid parameters.

### Risk
Low.

### Safer alternative
Create the VM in the GUI if preferred, then inspect with `qm config`.

---

## Command
```bash
qm importdisk 150 /mnt/pve/snips/iso/haos_ova-16.3.qcow2 cephpool --format raw
```

### What it does
Reads the QCOW2 file and creates a new VM disk volume in Ceph RBD for VM 150.

### Important arguments
- `150`: target VMID.
- `/mnt/pve/snips/iso/haos_ova-16.3.qcow2`: source image file.
- `cephpool`: target Ceph RBD storage.
- `--format raw`: preferred format for RBD-backed VM disks.

### Why it was used
This is the actual step that turns a source appliance image into a real Proxmox VM disk on shared storage.

### Expected result
A disk such as `cephpool:vm-150-disk-0` is created and may appear as an unused disk until attached.

### Success vs. failure
- Success: import completes and Proxmox reports a created RBD volume.
- Failure: source file path wrong, storage unavailable, or insufficient space.

### Risk
Moderate because it allocates shared storage space.

### Safer alternative
Verify source path and available storage before import.

---

## Command
```bash
qm set 150 --scsihw virtio-scsi-single --scsi0 cephpool:vm-150-disk-0
```

### What it does
Attaches the imported Ceph-backed disk to the VM as `scsi0` and sets the SCSI controller type.

### Important arguments
- `--scsihw virtio-scsi-single`: efficient paravirtualized SCSI controller.
- `--scsi0 cephpool:vm-150-disk-0`: attach the imported Ceph disk as the primary disk.

### Why it was used
The imported disk must be attached before the VM can boot from it.

### Expected result
`qm config 150` shows a `scsi0` disk entry.

### Success vs. failure
- Success: disk appears in VM config.
- Failure: disk identifier wrong or storage unavailable.

### Risk
Low.

### Safer alternative
Attach through the GUI if preferred.

---

## Command
```bash
qm set 150 --boot order=scsi0
```

### What it does
Sets the VM boot order so the primary SCSI disk is attempted first.

### Important arguments
- `--boot order=scsi0`: boot from the attached Home Assistant disk.

### Why it was used
Without correct boot order, Proxmox may try to boot from the wrong device.

### Expected result
The VM firmware attempts to boot from the imported OS disk.

### Success vs. failure
- Success: `qm config 150` shows `boot: order=scsi0`.
- Failure: the VM may still boot from the wrong device.

### Risk
Low.

### Safer alternative
Change boot order in the GUI `Options` tab.

---

## Command
```bash
qm set 150 --cpu x86-64-v3
```

### What it does
Sets the VM CPU model to the `x86-64-v3` baseline.

### Important arguments
- `x86-64-v3`: a modern CPU feature level intended to be portable across compatible nodes.

### Why it was used
The goal was to avoid `host` passthrough and use a consistent cluster-friendly CPU model.

### Expected result
The VM sees a modern but controlled CPU feature set.

### Success vs. failure
- Success: `qm config 150` shows `cpu: x86-64-v3`.
- Failure: invalid CPU model or unsupported host capabilities.

### Risk
Low to moderate. Migration will fail if target hosts do not support the selected CPU level.

### Safer alternative
Use `host` only when migration consistency is not required.

---

## Command
```bash
qm set 150 --serial0 socket --vga std
```

### What it does
Adds a serial console device and keeps a standard VGA display device.

### Important arguments
- `--serial0 socket`: creates a host-side serial socket for the VM.
- `--vga std`: creates a standard VGA device for graphical console output.

### Why it was used
To make both console paths available:
- VGA for boot troubleshooting
- serial for optional CLI access through `qm terminal`

### Expected result
The VM exposes both a VGA console and a serial port.

### Success vs. failure
- Success: both entries appear in `qm config`.
- Failure: console access remains limited.

### Risk
Low.

### Safer alternative
None needed.

---

## Command
```bash
qm status 150
```

### What it does
Shows the runtime state of the VM.

### Important arguments
- `150`: VMID.

### Why it was used
To confirm whether the VM process was actually running when console output was unclear.

### Expected result
A status line such as `status: running`.

### Success vs. failure
- Success: the VM is running or stopped as reported.
- Failure: invalid VMID or Proxmox issue.

### Risk
Low.

### Safer alternative
Check the VM state in the GUI.

---

## Command
```bash
qm terminal 150
```

### What it does
Connects to the VM’s `serial0` console.

### Important arguments
- `150`: VMID.

### Why it was used
To try to access the Home Assistant CLI from the Proxmox shell.

### Expected result
A serial terminal attaches and may show a guest login prompt if the guest outputs to serial.

### Success vs. failure
- Success: useful guest serial output appears.
- Failure: blank session or no prompt does not necessarily mean the VM is down.

### Risk
Low.

### Safer alternative
Use the GUI VGA console for early boot troubleshooting.

---

## Command
```bash
qm config 150
```

### What it does
Prints the VM configuration.

### Important arguments
- `150`: VMID.

### Why it was used
To verify the boot disk, CPU model, console devices, and boot order.

### Expected result
The current VM config is displayed.

### Success vs. failure
- Success: config output reflects intended settings.
- Failure: wrong VMID or Proxmox issue.

### Risk
Low.

### Safer alternative
Inspect the VM `Hardware` and `Options` tabs in the GUI.

---

## Command
```bash
qm stop 150
```

### What it does
Stops the VM.

### Important arguments
- `150`: VMID.

### Why it was used
The VM had to be powered off before changing firmware settings.

### Expected result
The VM transitions to a stopped state.

### Success vs. failure
- Success: `qm status 150` shows stopped.
- Failure: the guest may hang or require a forced stop.

### Risk
Moderate because it interrupts the guest immediately if not shut down gracefully.

### Safer alternative
Use a graceful guest shutdown first if the guest is responsive.

---

## Command
```bash
qm set 150 --bios ovmf --machine q35
```

### What it does
Changes the VM firmware to UEFI and uses the `q35` machine type.

### Important arguments
- `--bios ovmf`: use UEFI firmware.
- `--machine q35`: modern PCIe-based machine type often paired with OVMF.

### Why it was used
The Home Assistant image would not boot with legacy BIOS and required UEFI.

### Expected result
The VM firmware can detect and boot the EFI bootloader inside the Home Assistant disk.

### Success vs. failure
- Success: the guest proceeds past the firmware stage and boots.
- Failure: boot remains stuck or the EFI disk is still missing.

### Risk
Moderate. Firmware changes can make an existing VM unbootable if the guest expects the old firmware mode.

### Safer alternative
Verify appliance image firmware requirements before building the VM.

---

## Command
```bash
qm set 150 --efidisk0 cephpool:1,pre-enrolled-keys=1
```

### What it does
Creates and attaches an EFI variables disk on Ceph RBD.

### Important arguments
- `--efidisk0`: attach EFI variables storage.
- `cephpool:1`: allocate the EFI disk on shared Ceph storage.
- `pre-enrolled-keys=1`: create it with pre-enrolled keys.

### Why it was used
OVMF requires an EFI vars disk for normal UEFI boot behavior in Proxmox.

### Expected result
A small additional VM disk is created and attached for EFI data.

### Success vs. failure
- Success: the VM can boot under OVMF.
- Failure: OVMF may not boot the guest properly without this disk.

### Risk
Low.

### Safer alternative
Add the EFI disk from the GUI `Hardware` tab if preferred.

---

## Command
```bash
qm start 150
```

### What it does
Starts the VM.

### Important arguments
- `150`: VMID.

### Why it was used
To boot the VM after import and again after firmware correction.

### Expected result
The VM enters the running state and begins guest boot.

### Success vs. failure
- Success: VM boots and becomes reachable.
- Failure: boot loops, hangs, or remains inaccessible.

### Risk
Low.

### Safer alternative
Start from the GUI if preferred.

---

## Likely command used
```bash
ls -lh /var/lib/vz/template/qemu/haos_ova-16.3.qcow2
```

### What it does
Checks whether the source image file exists and shows its size.

### Important arguments
- `-l`: long format.
- `-h`: human-readable sizes.

### Why it was used
To confirm the upload or file placement succeeded before import.

### Expected result
The file path, ownership, and size are shown.

### Success vs. failure
- Success: image file is visible and nonzero.
- Failure: file missing or unexpectedly small.

### Risk
Low.

### Safer alternative
None needed.

---

## Likely command used
```bash
ls -lh /mnt/pve/snips/iso/haos_ova-16.3.qcow2
```

### What it does
Confirms that the image file exists in shared CephFS storage.

### Important arguments
- `-l`: long format.
- `-h`: human-readable sizes.

### Why it was used
To verify the image had been moved into the shared image library before import.

### Expected result
The file is listed with its size.

### Success vs. failure
- Success: shared source image is available for import.
- Failure: move failed or CephFS is unavailable.

### Risk
Low.

### Safer alternative
None needed.
