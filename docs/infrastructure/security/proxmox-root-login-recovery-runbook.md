---
title: "Proxmox Root Login Failure After Package Upgrade"
track: "infrastructure"
category: "security"
type: "runbook"
logical_order: 10
date_rule: "Dates are removed from filenames, visible headings, indexes, generated metadata, and runbook body content."
---

# Proxmox Root Login Failure After Package Upgrade

## Summary
A Proxmox host became inaccessible through the `root` account after running package maintenance. The troubleshooting focused on root authentication, boot-time recovery methods, and password reset workflows. The session also clarified why a recovery shell launched with `init=/bin/bash` was extremely minimal, why some commands were unavailable there, and what alternative recovery approaches were available.

## Environment
- Platform: Proxmox VE host
- Access paths discussed:
  - Local/physical console
  - GRUB boot parameter editing
  - SSH configuration and authentication path
- Linux components involved:
  - `root` account
  - PAM (Pluggable Authentication Modules)
  - `systemd`
  - GRUB kernel boot parameters
  - Filesystems and mount state
- Security-related message observed:
  - `L1TF: CPU bug present and SMT on, data leak possible`

## Problem
After running package updates, the `root` account could no longer be used to log into the Proxmox host.

## Symptoms
- Root login failure after `apt update` and `apt upgrade`
- In recovery mode, `mount` returned:
  ```bash
  mount: command not found
  ```
- In the same recovery context, `systemd`-based tooling returned:
  ```text
  System has not been booted with systemd as init system (PID 1). Can't operate.
  ```
- A boot-time CPU vulnerability notice appeared:
  ```text
  L1TF: CPU bug present and SMT on, data leak possible
  ```

## Actions Taken
1. Identified likely root-authentication troubleshooting areas:
   - SSH root login policy
   - PAM configuration
   - Root shell assignment
   - Root account lock status
   - Password reset from recovery mode

2. A direct boot recovery method was proposed using the GRUB kernel parameter below to bypass normal startup and drop into a shell early in boot:
   ```bash
   init=/bin/bash
   ```
   Purpose: start a Bash shell as PID 1 instead of the normal init system.

3. In that shell, the intended next step was to remount the root filesystem read-write before changing the password:
   ```bash
   mount -o remount,rw /
   ```
   Purpose: allow writes to system files such as `/etc/shadow`.

4. The host returned `mount: command not found`, which indicated the recovery shell environment was much more minimal than a normal rescue or multi-user boot.

5. Alternative command paths and fallback ideas were discussed:
   ```bash
   /bin/mount -o remount,rw /
   busybox mount -o remount,rw /
   ```
   Purpose: try absolute-path or BusyBox-provided versions of `mount`.

6. It was established that `init=/bin/bash` launches only a bare shell, not a full booted system. That explained:
   - Minimal `PATH`
   - Missing helper tools
   - Read-only root mount by default
   - No `systemd`
   - No normal services

7. Alternative recovery targets were proposed for a fuller rescue environment:
   ```bash
   systemd.unit=rescue.target
   systemd.unit=emergency.target
   ```
   Purpose: boot into recovery using `systemd`, with more standard tools available.

8. A second recovery path using `chroot` from a live environment was documented:
   ```bash
   mount /dev/sdXn /mnt
   mount --bind /dev /mnt/dev
   mount --bind /proc /mnt/proc
   mount --bind /sys /mnt/sys
   chroot /mnt
   passwd
   exit
   reboot
   ```
   Purpose: boot from a rescue/live system, mount the installed Proxmox system, enter it, and reset the password from there.

9. Additional authentication checks were suggested in case the issue was not only the password:
   ```bash
   grep root /etc/passwd
   sudo usermod -s /bin/bash root
   sudo passwd -S root
   sudo passwd -u root
   ```
   Purpose: verify root’s shell and whether the account was locked.

10. SSH- and PAM-related checks were also suggested:
   ```bash
   cat /etc/ssh/sshd_config
   systemctl restart sshd
   cat /etc/pam.d/common-auth
   cat /etc/pam.d/proxmox
   cat /etc/pam.d/login
   ```
   Purpose: verify whether root login policy or PAM changes from the upgrade affected authentication.

11. Post-recovery diagnostic checks were suggested:
   ```bash
   pveversion
   journalctl -xe | grep login
   cat /var/log/auth.log | grep root
   ```
   Purpose: verify package state and review authentication failures.

12. The boot warning below was identified as a separate CPU security notice, not the primary cause of the login issue:
   ```text
   L1TF: CPU bug present and SMT on, data leak possible
   ```

## Key Findings
- Booting with `init=/bin/bash` does **not** provide a normal rescue environment. It replaces the normal init system with Bash as PID 1.
- In that mode, the root filesystem is typically mounted read-only, and command availability may be limited because the environment is intentionally stripped down.
- The error about `systemd` not being PID 1 is expected in an `init=/bin/bash` boot and does not by itself indicate another failure.
- `passwd` can work in a Bash-only recovery environment, but only after the root filesystem is remounted read-write and the binary is reachable.
- `chroot` is a viable fallback when boot-parameter recovery is too limited or inconvenient.
- The L1TF warning is a security advisory related to CPU vulnerability mitigation and SMT/Hyper-Threading, not evidence of a broken password database or authentication stack.

## Resolution
A final successful repair was **not explicitly confirmed** in the conversation. However, the documented recovery path is:

1. Boot into recovery with either:
   - `init=/bin/bash` and manually remount `/` read-write, or
   - `systemd.unit=rescue.target` / `systemd.unit=emergency.target`, or
   - a live ISO plus `chroot`
2. Run `passwd` to reset the root password
3. Reboot normally
4. If login still fails, check:
   - root shell assignment
   - account lock state
   - SSH root login policy
   - PAM configuration
   - authentication logs

## Validation
Success was **not confirmed** in-chat.

Expected validation steps after recovery:
- Log in locally as `root`
- Test web UI access if applicable
- Test SSH only after confirming intended `PermitRootLogin` policy
- Review recent auth failures and confirm they stop appearing
- Confirm Proxmox package state with:
  ```bash
  pveversion
  ```

## Follow-Up Tasks
- Confirm whether the root password reset succeeded
- Review `/etc/ssh/sshd_config` for intentional root login policy
- Review PAM files for unexpected changes after the package upgrade
- Check whether the root account is locked or has a non-login shell
- Review authentication logs after the next successful boot
- Decide whether to address the L1TF/SMT security warning based on homelab threat model
- Record the actual Proxmox version and package changes involved in the failed login event

## Lessons Learned
- `init=/bin/bash` is powerful, but it is not the same thing as a full rescue mode.
- A missing `mount` command in early boot often reflects a minimal environment, not necessarily filesystem corruption.
- If `systemd` is not PID 1, `systemctl` and related tools are expected to fail.
- For repeatable recovery, `rescue.target`, `emergency.target`, or a live ISO with `chroot` are often easier to work with than a raw Bash-only boot.
- Security warnings shown during boot should be separated from the primary incident unless evidence links them directly.

---

# Command Reference

## Command
```bash
apt update
```

**What it does:** Refreshes APT package indexes from configured repositories.  
**Why it was used:** As part of normal package maintenance before upgrade.  
**Expected result:** Updated package lists.  
**Success indicates:** The host can see repositories and package metadata is current.  
**Failure indicates:** Repository, DNS, networking, or package source issues.  
**Risk:** Low.

---

## Command
```bash
apt upgrade
```

**What it does:** Installs available package upgrades for already installed packages.  
**Why it was used:** Routine maintenance on the Proxmox host.  
**Expected result:** Updated packages and possibly updated authentication, SSH, PAM, or boot-related components.  
**Success indicates:** Packages installed cleanly.  
**Failure indicates:** Dependency problems, interrupted package state, or post-install script failures.  
**Risk:** Moderate on infrastructure hosts, because upgrades can affect authentication, services, kernels, or boot behavior.  
**Safer alternative:** Review upgrade plan first, especially on Proxmox hosts.

---

## Command
```bash
cat /etc/ssh/sshd_config
```

**What it does:** Displays the OpenSSH server configuration file.  
**Why it was used:** To check whether root SSH login was intentionally disabled or changed.  
**Expected result:** Review of directives such as `PermitRootLogin`.  
**Success indicates:** SSH policy can be audited directly.  
**Failure indicates:** Missing file or broken SSH package state.  
**Risk:** Low.

---

## Command
```bash
systemctl restart sshd
```

**What it does:** Restarts the SSH daemon under `systemd`.  
**Why it was used:** To apply SSH config changes after editing `sshd_config`.  
**Expected result:** SSH service reloads with new settings.  
**Success indicates:** SSH config is valid and `systemd` is running.  
**Failure indicates:** Invalid SSH config or no `systemd` environment.  
**Risk:** Moderate on remote-only systems, because a bad config can cut off SSH access.

---

## Command
```bash
cat /etc/pam.d/common-auth
```

**What it does:** Displays shared PAM authentication rules.  
**Why it was used:** To inspect whether authentication flow changed after upgrade.  
**Expected result:** A readable PAM policy stack.  
**Success indicates:** PAM config exists and can be reviewed.  
**Failure indicates:** Possible PAM package/config damage.  
**Risk:** Low for reading.

---

## Command
```bash
cat /etc/pam.d/proxmox
```

**What it does:** Displays Proxmox-specific PAM configuration if present.  
**Why it was used:** To inspect whether Proxmox login/authentication flow was affected.  
**Expected result:** PAM directives relevant to Proxmox auth path.  
**Success indicates:** Proxmox auth configuration is available.  
**Failure indicates:** Missing or damaged auth config.  
**Risk:** Low for reading.

---

## Command
```bash
cat /etc/pam.d/login
```

**What it does:** Displays PAM rules for local console login.  
**Why it was used:** To compare console login policy with other auth paths.  
**Expected result:** Standard login PAM stack.  
**Success indicates:** Console auth path can be reviewed.  
**Failure indicates:** Missing or broken login PAM config.  
**Risk:** Low for reading.

---

## Command
```bash
grep root /etc/passwd
```

**What it does:** Searches the account database for the `root` entry.  
**Why it was used:** To verify the root account record and shell.  
**Expected result:** A line similar to `root:x:0:0:root:/root:/bin/bash`.  
**Success indicates:** Root account exists and its shell can be inspected.  
**Failure indicates:** Corrupt or missing passwd entry.  
**Risk:** Low.

---

## Command
```bash
sudo usermod -s /bin/bash root
```

**What it does:** Changes the login shell for `root` to `/bin/bash`.  
**Why it was used:** To fix a case where root may have been assigned `/usr/sbin/nologin` or another non-interactive shell.  
**Expected result:** Root shell becomes Bash.  
**Success indicates:** Root should be able to start an interactive shell again.  
**Failure indicates:** Account database issue or insufficient privileges.  
**Risk:** Moderate, because modifying the root account incorrectly can worsen access problems.

---

## Command
```bash
sudo passwd -S root
```

**What it does:** Shows root password/account status.  
**Why it was used:** To check whether the root account was locked.  
**Expected result:** Status code such as `P` or `L`.  
**Success indicates:** Account status is readable.  
**Failure indicates:** PAM/account database or privilege issue.  
**Risk:** Low.

---

## Command
```bash
sudo passwd -u root
```

**What it does:** Unlocks the root account.  
**Why it was used:** To reverse an account lock if one existed.  
**Expected result:** Root account becomes unlocked.  
**Success indicates:** Login may resume if the password is valid.  
**Failure indicates:** PAM/account database issues.  
**Risk:** Moderate from a security perspective, because it re-enables root access.

---

## Command
```bash
init=/bin/bash
```

**What it does:** Kernel boot parameter telling Linux to start `/bin/bash` as PID 1 instead of the normal init system.  
**Why it was used:** To get direct low-level recovery access when normal boot/login was unavailable.  
**Expected result:** A bare shell early in boot.  
**Success indicates:** The kernel and root filesystem are bootable enough to start Bash.  
**Failure indicates:** More serious boot or filesystem issues.  
**Risk:** High if misunderstood, because it bypasses normal boot protections and leaves the system in a minimal state.  
**Safer alternative:** `systemd.unit=rescue.target` or a live ISO plus `chroot`.

---

## Command
```bash
mount -o remount,rw /
```

**What it does:** Remounts the currently mounted root filesystem as read-write.  
**Why it was used:** Required before changing files such as `/etc/shadow` with `passwd`.  
**Important flags:**
- `-o remount,rw` = change existing mount options to read-write  
- `/` = the root filesystem  
**Expected result:** Root filesystem becomes writable.  
**Success indicates:** Password and config changes can be saved.  
**Failure indicates:** Missing command, minimal PATH, filesystem issue, or incompatible recovery environment.  
**Risk:** Moderate, because it enables writes on a system booted in recovery mode.

---

## Command
```bash
/bin/mount -o remount,rw /
```

**What it does:** Same as above, but uses the absolute path to `mount`.  
**Why it was used:** In a minimal recovery shell, the `PATH` variable may not include `/bin`, so the command may not be found otherwise.  
**Expected result:** Same as `mount -o remount,rw /`.  
**Success indicates:** The binary exists; the earlier failure was likely just a PATH issue.  
**Failure indicates:** The tool is unavailable in that environment.  
**Risk:** Moderate.

---

## Command
```bash
busybox mount -o remount,rw /
```

**What it does:** Uses the BusyBox implementation of `mount`.  
**Why it was used:** As a fallback in ultra-minimal recovery environments.  
**Expected result:** Root becomes writable even if the full util-linux `mount` command is unavailable.  
**Success indicates:** BusyBox is present and functional.  
**Failure indicates:** BusyBox is not available or the filesystem cannot be remounted.  
**Risk:** Moderate.

---

## Command
```bash
systemd.unit=rescue.target
```

**What it does:** Kernel boot parameter telling `systemd` to boot into rescue mode.  
**Why it was used:** To get a fuller recovery environment than `init=/bin/bash`.  
**Expected result:** Single-user/rescue shell with more standard tools and `systemd` available.  
**Success indicates:** Easier recovery workflow with normal service management support.  
**Failure indicates:** Boot path or systemd issue.  
**Risk:** Lower than `init=/bin/bash`, but still a recovery-mode boot.

---

## Command
```bash
systemd.unit=emergency.target
```

**What it does:** Kernel boot parameter telling `systemd` to boot into emergency mode.  
**Why it was used:** To get a minimal but still `systemd`-managed recovery environment.  
**Expected result:** Very limited environment, but still booted under `systemd`.  
**Success indicates:** Access to a shell without completely bypassing init.  
**Failure indicates:** Deeper boot issue.  
**Risk:** Lower than raw init replacement, but still recovery-only.

---

## Command
```bash
passwd
```

**What it does:** Changes the password for the current or specified account.  
**Why it was used:** To reset the root password during recovery.  
**Expected result:** Prompt for new password, then update to `/etc/shadow`.  
**Success indicates:** New password stored successfully.  
**Failure indicates:** Read-only filesystem, PAM/account issue, or missing binary.  
**Risk:** Moderate, because setting an unknown or mistyped root password can prolong the outage.

---

## Command
```bash
/bin/passwd
```

**What it does:** Same as `passwd`, but with the full binary path.  
**Why it was used:** To work around PATH issues in a minimal shell.  
**Expected result:** Same as `passwd`.  
**Success indicates:** The problem was command lookup, not the tool itself.  
**Failure indicates:** Missing binary or write/auth backend issue.  
**Risk:** Moderate.

---

## Command
```bash
exec /sbin/init
```

**What it does:** Replaces the current shell process with the normal init process.  
**Why it was used:** As a way to continue booting cleanly after making changes in a Bash-only recovery environment.  
**Expected result:** Control passes from the recovery shell to the normal init system.  
**Success indicates:** System can continue startup without immediate reboot.  
**Failure indicates:** Missing init path or broken init stack.  
**Risk:** Moderate, because behavior depends on the exact system state.

---

## Command
```bash
reboot
```

**What it does:** Restarts the system.  
**Why it was used:** To boot back into normal operation after recovery changes.  
**Expected result:** System restarts cleanly.  
**Success indicates:** Recovery changes can be tested on next boot.  
**Failure indicates:** Shutdown/reboot path issues.  
**Risk:** Moderate during recovery, because unsaved changes or bad config may still exist.

---

## Command
```bash
mount /dev/sdXn /mnt
```

**Likely command used**

**What it does:** Mounts the installed system’s root partition under `/mnt`.  
**Why it was used:** First step of a live-ISO `chroot` recovery workflow.  
**Important arguments:**
- `/dev/sdXn` = placeholder for the actual disk partition
- `/mnt` = temporary mount point  
**Expected result:** The installed OS becomes accessible under `/mnt`.  
**Success indicates:** The root filesystem can be mounted externally.  
**Failure indicates:** Wrong partition, filesystem issue, or damaged disk.  
**Risk:** Moderate if mounted read-write on an already damaged filesystem.

---

## Command
```bash
mount --bind /dev /mnt/dev
```

**What it does:** Makes the live environment’s `/dev` visible inside the mounted system.  
**Why it was used:** Required for many commands to work properly inside `chroot`.  
**Expected result:** Device nodes become available inside the chroot.  
**Success indicates:** Better functional recovery environment.  
**Failure indicates:** Incomplete chroot setup.  
**Risk:** Low.

---

## Command
```bash
mount --bind /proc /mnt/proc
```

**What it does:** Binds the running kernel’s `/proc` filesystem into the mounted target.  
**Why it was used:** Needed for many system tools inside the chroot.  
**Expected result:** Process/kernel info becomes visible in the chroot.  
**Success indicates:** More complete recovery environment.  
**Failure indicates:** Chroot will be limited.  
**Risk:** Low.

---

## Command
```bash
mount --bind /sys /mnt/sys
```

**What it does:** Binds the running kernel’s `/sys` into the mounted target.  
**Why it was used:** Needed for hardware and kernel interface visibility inside the chroot.  
**Expected result:** `/sys` is available in the chroot.  
**Success indicates:** Better system tooling support inside recovery.  
**Failure indicates:** Incomplete chroot.  
**Risk:** Low.

---

## Command
```bash
chroot /mnt
```

**What it does:** Changes the apparent root directory to `/mnt` for the current process.  
**Why it was used:** To operate on the installed Proxmox system as if it were the currently booted OS.  
**Expected result:** Commands like `passwd` affect the mounted system, not the live ISO.  
**Success indicates:** Recovery commands are now targeting the installed OS.  
**Failure indicates:** Missing binaries, incomplete bind mounts, or bad root mount.  
**Risk:** Moderate, because actions now modify the installed system directly.

---

## Command
```bash
exit
```

**What it does:** Leaves the current shell.  
**Why it was used:** To leave the `chroot` shell after repairs.  
**Expected result:** Return to the live environment shell.  
**Success indicates:** Chroot session closed cleanly.  
**Failure indicates:** Usually just wrong shell context.  
**Risk:** Low.

---

## Command
```bash
pveversion
```

**What it does:** Displays Proxmox version and package state information.  
**Why it was used:** To verify whether Proxmox package state was healthy after upgrade/recovery.  
**Expected result:** Installed Proxmox version details.  
**Success indicates:** Proxmox tooling is present and readable.  
**Failure indicates:** Package or PATH issue.  
**Risk:** Low.

---

## Command
```bash
journalctl -xe | grep login
```

**What it does:** Searches recent `systemd` journal output for login-related entries.  
**Why it was used:** To inspect auth failures after recovery.  
**Expected result:** Recent login/authentication messages.  
**Success indicates:** Useful auth evidence in the journal.  
**Failure indicates:** No `systemd` journal, no matching logs, or boot context without `systemd`.  
**Risk:** Low.

---

## Command
```bash
cat /var/log/auth.log | grep root
```

**What it does:** Searches the traditional authentication log for entries related to root.  
**Why it was used:** To inspect whether PAM, SSH, or local login rejected root and why.  
**Expected result:** Matching auth log entries.  
**Success indicates:** You can trace root login failures historically.  
**Failure indicates:** Different logging backend or missing file.  
**Risk:** Low.

---

## Command
```bash
dmesg | grep -i l1tf
```

**What it does:** Searches kernel boot messages for L1TF mitigation status.  
**Why it was used:** To investigate the CPU vulnerability warning.  
**Expected result:** Kernel messages describing mitigation state.  
**Success indicates:** You can confirm how the kernel is handling L1TF.  
**Failure indicates:** No matching messages or limited log access.  
**Risk:** Low.

---

## Command
```bash
lscpu | grep Thread
```

**What it does:** Displays CPU topology and filters for thread count per core.  
**Why it was used:** To confirm whether SMT/Hyper-Threading is enabled.  
**Expected result:** A line showing thread count.  
**Success indicates:** You can verify whether SMT remains on.  
**Failure indicates:** Missing utility or no match.  
**Risk:** Low.

---

## Command
```bash
update-grub
```

**What it does:** Regenerates GRUB boot configuration.  
**Why it was used:** To apply persistent kernel boot parameters such as CPU mitigation settings.  
**Expected result:** Updated GRUB config files.  
**Success indicates:** New boot parameters will be used on next reboot.  
**Failure indicates:** GRUB/package/config issue.  
**Risk:** Moderate, because bad bootloader config can affect startup.

---

## Command
```bash
mitigations=auto,nosmt
```

**What it does:** Kernel boot parameter enabling automatic mitigations and disabling SMT for security.  
**Why it was used:** To reduce L1TF-related exposure.  
**Expected result:** Security mitigations applied; SMT disabled after reboot.  
**Success indicates:** Lower side-channel risk.  
**Failure indicates:** Boot parameter not applied or unsupported setting.  
**Risk:** Operational rather than destructive; it can reduce performance.
