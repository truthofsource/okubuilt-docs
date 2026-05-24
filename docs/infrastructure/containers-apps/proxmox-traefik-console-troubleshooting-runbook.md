---
title: "Approx. date: Boot/console troubleshooting session (date not explicitly stated in chat) - Slow Login Prompt in `qm terminal`"
track: "infrastructure"
category: "containers-apps"
type: "runbook"
logical_order: 70
date_rule: "Dates are removed from filenames, visible headings, indexes, generated metadata, and runbook body content."
---

# Approx. date: Boot/console troubleshooting session (date not explicitly stated in chat) - Slow Login Prompt in `qm terminal`

## Summary
A Proxmox VM was investigated for delayed login prompt visibility when accessed through `qm terminal`. Initial concern included a boot-time stall related to `systemd-tmpfiles-setup.service`, but the issue was later narrowed to console presentation rather than the VM failing to boot. The session focused on distinguishing between a true boot delay and a serial-console or getty presentation issue.

## Environment
- Proxmox VE
- QEMU/KVM VM accessed with `qm terminal`
- Linux guest using `systemd`
- Likely Debian-based guest OS
- Serial console context involving `ttyS0`
- GRUB bootloader and `serial-getty@ttyS0.service`

## Problem
The login prompt took a long time to appear when using `qm terminal`, even after the VM had already finished booting.

## Symptoms
- Boot output included:
  ```text
  Job systemd-tmpfiles-setup.service/start running (2min 32s / no limit)
  ```
- Later clarification indicated the VM had already gotten past that stage and had finished booting.
- `qm terminal` appeared blank or delayed before showing `login:`.

## Actions Taken
1. Considered whether boot was blocked by `systemd-tmpfiles-setup.service`.
2. Reviewed likely causes of slow boot or delayed console availability:
   - slow mounts
   - tmpfiles rules
   - network waits
   - cloud-init work
   - filesystem checks
3. After clarification that boot had completed, the focus shifted to console behavior rather than boot performance.
4. Identified likely causes:
   - serial console not fully configured
   - `qm terminal` attached to `ttyS0` while login was on VGA/`tty1`
   - `serial-getty` already running but not repainting until keypress
5. Proposed enabling a serial login console and adding kernel console parameters.
6. Noted that pressing `Enter` once after attaching may redraw an already-running getty prompt.

## Key Findings
- The observed `systemd-tmpfiles-setup.service` message indicated a boot job was running at one point, but it was not the root cause of the final user-facing issue.
- Once the VM had fully booted, the remaining problem was more consistent with console mismatch than with actual system slowness.
- `qm terminal` behavior depends on:
  - whether Proxmox is attached to a serial device such as `ttyS0`
  - whether the guest kernel logs to that console
  - whether a getty is active on that console
- A blank or delayed screen in `qm terminal` can happen even when the VM is healthy.

## Resolution
Current status: the issue was diagnosed conceptually as a serial console / getty configuration problem rather than a true boot hang.

Recommended fix path:
- enable `serial-getty@ttyS0.service`
- configure GRUB with:
  ```bash
  GRUB_CMDLINE_LINUX_DEFAULT="quiet console=tty0 console=ttyS0"
  ```
- update GRUB and reboot
- test whether `Enter` redraws the prompt when attaching with `qm terminal`

## Validation
Suggested validation steps:
- confirm `serial-getty@ttyS0.service` is active
- reboot the VM
- reconnect with:
  ```bash
  qm terminal 100
  ```
- verify that boot messages and the `login:` prompt appear on the serial console
- if the screen is blank, press `Enter` once and confirm whether the prompt appears immediately

## Follow-Up Tasks
- Verify whether the VM has a configured serial port in Proxmox hardware settings.
- Check whether Proxmox is set to use a serial console for the VM.
- Confirm GRUB kernel command line includes both VGA and serial console targets.
- Confirm the issue is present only in `qm terminal` and not in the Proxmox web console.
- Capture `systemctl status serial-getty@ttyS0.service` and `/etc/default/grub` for documentation.

## Lessons Learned
- A blank `qm terminal` session does not always mean the VM is still booting.
- Separate true boot delays from serial-console presentation issues.
- For reliable headless troubleshooting, configure both kernel console output and a getty on `ttyS0`.
- Pressing `Enter` can reveal an already-running login prompt on serial consoles.

---

# Traefik Docker Provider API Version Mismatch

## Summary
Traefik failed to start correctly because its Docker provider was using an outdated Docker client API version. The environment included a `dockersocket` sidecar proxy in front of the Docker socket. Troubleshooting focused on interpreting provider errors, separating root cause from shutdown noise, and identifying the correct remediation path.

## Environment
- Date from logs: [date removed]
- Docker Engine
- Docker Compose
- Traefik container
- `dockersocket` container acting as Docker socket proxy
- Reverse proxy setup using Traefik Docker provider
- HTTP entrypoint on port 80
- HTTPS entrypoint on port 443

## Problem
Traefik could not communicate with the Docker daemon because the Docker API version used by the Traefik binary was too old for the host Docker Engine.

## Symptoms
Observed logs included:

```text
traefik       | [date removed]-18T18:06:48Z ERR Provider error, retrying in 7.845389865s error="Error response from daemon: client version 1.24 is too old. Minimum supported API version is 1.44, please upgrade your client to a newer version" providerName=docker
```

Additional shutdown logs:

```text
dockersocket  | [NOTICE]   (1) : haproxy version is 3.2.4-98813a1
dockersocket  | [WARNING]  (1) : Exiting Master process...
dockersocket  | Proxy dockerfrontend stopped (cumulated conns: FE: 81, BE: 0).
dockersocket  | Proxy dockerbackend stopped (cumulated conns: FE: 0, BE: 81).
dockersocket  | Proxy docker-events stopped (cumulated conns: FE: 0, BE: 0).
traefik       | [date removed]-18T18:06:55Z INF I have to go...
traefik       | [date removed]-18T18:06:55Z INF Stopping server gracefully
traefik       | [date removed]-18T18:06:55Z ERR error="accept tcp [::]:443: use of closed network connection" entryPointName=websecure
traefik       | [date removed]-18T18:06:55Z ERR error="accept tcp [::]:80: use of closed network connection" entryPointName=web
dockersocket  | [WARNING]  (1) : All workers exited. Exiting... (0)
dockersocket exited with code 0
traefik       | [date removed]-18T18:06:56Z INF Server stopped
traefik       | [date removed]-18T18:06:56Z INF Shutting down
traefik       | [date removed]-18T18:06:56Z ERR Cannot retrieve data error="context canceled" providerName=docker
traefik exited with code 0
```

## Actions Taken
1. Reviewed Traefik logs and isolated the first meaningful provider error.
2. Distinguished the root cause from subsequent graceful shutdown messages.
3. Determined that:
   - the error was generated by Traefik as the Docker API client
   - `dockersocket` was only proxying the connection and was not itself the version-mismatched client
4. Identified the likely remediation:
   - upgrade the Traefik image to a modern version
5. Considered a temporary workaround:
   - forcing `DOCKER_API_VERSION=1.44`
6. Explicitly rejected Docker Engine downgrade as a preferred fix.

## Key Findings
- Root cause:
  ```text
  client version 1.24 is too old. Minimum supported API version is 1.44
  ```
- This indicates a Docker API compatibility gap between:
  - the Traefik binary or embedded Docker client library
  - the installed Docker Engine version
- The `dockersocket` container was not the source of the API version problem.
- Messages such as:
  ```text
  use of closed network connection
  ```
  occurred during shutdown and were secondary symptoms, not the initiating fault.
- Both Traefik and `dockersocket` exited with code `0`, indicating controlled shutdown rather than a crash loop caused by signal failure or segmentation fault.

## Resolution
Current status: root cause identified; recommended fix is to upgrade Traefik.

Recommended primary remediation:
- update the Traefik image in Docker Compose to a current release, such as:
  ```yaml
  image: traefik:v3.1
  ```

Temporary workaround if an immediate upgrade is not possible:
- set:
  ```yaml
  DOCKER_API_VERSION=1.44
  ```
- treat this only as an interim measure

Not recommended:
- downgrading Docker Engine to preserve support for very old client API versions

## Validation
Suggested validation steps after remediation:
1. Pull and deploy the updated Traefik image.
2. Start Traefik and `dockersocket`.
3. Review logs for absence of:
   ```text
   client version 1.24 is too old
   ```
4. Confirm Traefik successfully loads the Docker provider and discovers routers/services.
5. Confirm ports 80 and 443 remain bound and available after startup.

## Follow-Up Tasks
- Review the current Traefik image tag and document the exact version in use before and after remediation.
- Verify whether other Compose stacks use similarly outdated pinned image tags.
- Confirm compatibility of Traefik static flags and dynamic configuration with the target upgraded version.
- Consider documenting a version policy for critical infrastructure containers such as Traefik.
- Add a post-upgrade validation checklist for routes, TLS, and Docker provider discovery.

## Lessons Learned
- The first provider error is usually the most important line in the log stream.
- Graceful-shutdown errors around entrypoints often follow the real issue and should not be mistaken for root cause.
- A Docker socket proxy can be healthy while the client behind it is too old.
- Infrastructure containers such as reverse proxies should be kept within a supported version range relative to the Docker Engine.

---

# Command Reference

## Command
```bash
journalctl -u systemd-tmpfiles-setup.service -b
```

### Purpose
View logs for `systemd-tmpfiles-setup.service` from the current boot.

### What it does
Queries the systemd journal for only this unit during the current boot session.

### Important parts
- `-u systemd-tmpfiles-setup.service` limits output to that service
- `-b` limits output to the current boot

### Why it was used
To determine whether boot delay was caused by tmpfiles processing.

### Expected result
Logs showing whether the service completed normally, stalled on a path, or emitted errors.

### What success or failure indicates
- Normal completion suggests tmpfiles is not the current blocker.
- Long pauses, filesystem errors, or path access failures indicate a real boot bottleneck.

### Risk
Low risk. Read-only.

---

## Command
```bash
systemd-analyze blame
```

### Purpose
Show which services or units consumed the most time during boot.

### What it does
Lists boot units sorted by initialization time.

### Why it was used
To identify whether boot slowness was real and, if so, which unit was responsible.

### Expected result
A ranked list of services and mounts by startup duration.

### What success or failure indicates
- Long times on mount units, network waits, or tmpfiles help pinpoint the delay.
- If nothing significant appears, the issue may be console-related rather than a real boot hold-up.

### Risk
Low risk. Read-only.

---

## Command
```bash
systemd-analyze critical-chain
```

### Purpose
Show the dependency path that controlled how long the system took to reach the boot target.

### What it does
Displays the chain of units that gated boot progress.

### Why it was used
To tell whether the login delay was caused by service dependencies instead of console behavior.

### Expected result
A timing tree showing the key boot path.

### What success or failure indicates
- A long dependency chain confirms actual boot delay.
- A normal chain suggests the system is up and the issue is likely with console access or getty behavior.

### Risk
Low risk. Read-only.

---

## Command
```bash
systemctl --failed
```

### Purpose
List failed systemd units.

### What it does
Shows services, mounts, or targets that failed during boot or runtime.

### Why it was used
To identify failed boot components that could explain missing login or partial system initialization.

### Expected result
Either no failed units or a short list of failed components.

### What success or failure indicates
- No failed units suggests the boot completed cleanly.
- Failed getty, mount, or networking units may explain delayed or missing console login.

### Risk
Low risk. Read-only.

---

## Command
```bash
journalctl -b -u systemd-tmpfiles-setup.service | sed -n '1,80p'
```

### Purpose
Show the first portion of tmpfiles logs from the current boot.

### What it does
Reads service logs, then limits output to the first 80 printed lines.

### Important parts
- `sed -n '1,80p'` prints only lines 1 through 80

### Why it was used
To quickly inspect early tmpfiles activity without dumping an excessively long log.

### Expected result
Compact service output suitable for troubleshooting.

### What success or failure indicates
Useful for spotting where processing slowed or failed.

### Risk
Low risk. Read-only.

---

## Command
```bash
qm terminal 100
```

### Purpose
Attach to the Proxmox VM serial console for VM ID 100.

### What it does
Opens a terminal session to the VM console managed by Proxmox.

### Important parts
- `100` is the VM ID

### Why it was used
To observe boot behavior and check whether a login prompt appeared.

### Expected result
Kernel messages, boot logs, or a login prompt if the guest is configured for serial console access.

### What success or failure indicates
- A visible prompt suggests serial console and getty are working.
- A blank screen may indicate no serial output, missing getty on `ttyS0`, or only VGA console output.

### Risk
Low risk. Interactive access only.

### Platform note
In Proxmox, `qm terminal` is most useful when the guest is configured with a serial port and login on `ttyS0`.

---

## Command
```bash
sudo systemctl enable --now serial-getty@ttyS0.service
```

### Purpose
Enable and start a login prompt on the serial console.

### What it does
Configures systemd to launch a getty on `ttyS0` immediately and on future boots.

### Important parts
- `enable` persists across reboots
- `--now` starts the service immediately
- `serial-getty@ttyS0.service` targets the serial device commonly used by Proxmox serial console

### Why it was used
To ensure `qm terminal` has a login prompt to display after boot.

### Expected result
The service becomes active and starts listening on `ttyS0`.

### What success or failure indicates
- Success means the guest is now prepared to present login over serial.
- Failure may indicate missing serial device support or guest console mismatch.

### Risk
Low risk.

---

## Command
```bash
sudo update-grub
```

### Purpose
Regenerate GRUB configuration after editing kernel command-line settings.

### What it does
Rebuilds the GRUB boot configuration based on `/etc/default/grub` and related scripts.

### Why it was used
After adding `console=tty0 console=ttyS0`, GRUB must be updated so the next boot uses the new console parameters.

### Expected result
New GRUB configuration written without errors.

### What success or failure indicates
- Success means the next reboot should use the updated kernel console settings.
- Failure means serial console configuration changes will not take effect.

### Risk
Moderate. Safe when done correctly, but mistakes in bootloader configuration can affect boot behavior.

### Safer alternative
Back up `/etc/default/grub` before editing.

---

## Command
```bash
cat /etc/default/grub | sed -n '1,20p'
```

### Purpose
Review the beginning of the GRUB defaults file.

### What it does
Prints the first 20 lines of the file for quick inspection.

### Why it was used
To verify whether `GRUB_CMDLINE_LINUX_DEFAULT` includes the required console parameters.

### Expected result
A readable snippet showing current GRUB defaults.

### What success or failure indicates
Useful for validating whether serial console settings are correctly defined.

### Risk
Low risk. Read-only.

---

## Command
```bash
systemctl status serial-getty@ttyS0.service
```

### Purpose
Check the state of the serial getty service.

### What it does
Shows whether the service is active, enabled, failed, or inactive, along with recent log lines.

### Why it was used
To confirm whether login should appear on the serial console.

### Expected result
`active (running)` when properly configured.

### What success or failure indicates
- Active service supports `qm terminal` login visibility.
- Inactive or failed status points to the root of the missing prompt.

### Risk
Low risk. Read-only.

---

## Command
```bash
cd /opt/compose/traefik_stack
```

### Purpose
Change into the Traefik Compose project directory.

### What it does
Sets the working directory so `docker compose` commands apply to the intended stack.

### Why it was used
To manage the Traefik and `dockersocket` containers from the correct Compose context.

### Expected result
Shell working directory changes successfully.

### What success or failure indicates
- Success means subsequent Compose commands target the right project.
- Failure suggests the expected stack path may differ.

### Risk
Low risk.

---

## Command
```bash
docker compose pull traefik
```

### Purpose
Download the updated Traefik image.

### What it does
Pulls the latest version of the specified image tag defined for the `traefik` service.

### Why it was used
To upgrade Traefik and resolve Docker API client compatibility issues.

### Expected result
A successful image download for the configured Traefik tag.

### What success or failure indicates
- Success means the updated image is ready for deployment.
- Failure may indicate network, registry, authentication, or tag issues.

### Risk
Low risk, but it changes what image version will be used on the next deployment.

### Platform note
For Docker Compose environments, image updates should be paired with controlled restart and post-change validation.

---

## Command
```bash
docker compose up -d traefik dockersocket
```

### Purpose
Start or recreate the Traefik and `dockersocket` services in detached mode.

### What it does
Applies the current Compose configuration to the named services and runs them in the background.

### Important parts
- `-d` runs containers detached
- service names restrict scope to Traefik-related components

### Why it was used
To deploy the upgraded Traefik image and restore reverse proxy service.

### Expected result
Containers start successfully and remain running.

### What success or failure indicates
- Stable running containers indicate the deployment likely succeeded.
- Immediate exit or restart loops indicate remaining config or compatibility problems.

### Risk
Moderate. This changes live reverse proxy components and can temporarily interrupt ingress traffic.

### Safer alternative
Review the Compose diff and image tag changes before restarting production-facing proxy services.

---

## Command
```bash
docker logs -f traefik
```

### Purpose
Follow Traefik container logs in real time.

### What it does
Streams stdout/stderr from the Traefik container continuously.

### Important parts
- `-f` follows the log stream

### Why it was used
To verify whether the Docker provider initializes correctly after upgrade.

### Expected result
Startup logs showing provider loading, router discovery, and absence of API version errors.

### What success or failure indicates
- No provider error indicates the compatibility issue is resolved.
- Reappearance of the API version error means the old image, wrong tag, or another incompatible component is still in play.

### Risk
Low risk. Read-only.

---

## Command
```yaml
image: traefik:v3.1
```

### Purpose
Pin Traefik to a current major release in Compose configuration.

### What it does
Tells Docker Compose which Traefik image version to deploy.

### Why it was used
To replace an outdated Traefik version that embedded an old Docker client API.

### Expected result
A newer Traefik binary with current Docker provider compatibility.

### What success or failure indicates
- Successful deployment suggests API compatibility should improve.
- If startup still fails, review other static flags, provider settings, or whether the image actually changed.

### Risk
Moderate. Major version upgrades can introduce config differences.

### Safer alternative
Use a tested minor version pin and review Traefik release notes before upgrading.

---

## Command
```yaml
DOCKER_API_VERSION=1.44
```

### Purpose
Force the Docker client library inside the container to negotiate with API version 1.44.

### What it does
Overrides automatic API version selection through an environment variable.

### Why it was used
As a temporary workaround when an immediate Traefik upgrade is not possible.

### Expected result
The Docker provider may successfully talk to the Docker daemon if the client library can operate at that version.

### What success or failure indicates
- Success suggests temporary compatibility can be restored.
- Failure means the binary itself is too old or otherwise incompatible.

### Risk
Moderate. This is a workaround, not a long-term fix.

### Safer alternative
Upgrade Traefik rather than relying on API version forcing.

---

## Command
```text
Likely command used: docker compose logs traefik dockersocket
```

### Purpose
Review recent logs from the Traefik and `dockersocket` services together.

### What it does
Shows log output for both containers in one view.

### Why it was likely used
The troubleshooting relied on correlated logs from both services, which are commonly viewed this way in Compose environments.

### Expected result
Interleaved container logs showing the provider error and controlled shutdown sequence.

### What success or failure indicates
Useful for identifying which service emitted the first fault and which only reacted afterward.

### Risk
Low risk. Read-only.
