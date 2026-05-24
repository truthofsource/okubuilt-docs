---
title: "OPNsense Web GUI Failure Recovery Documentation and Runbook"
track: "infrastructure"
category: "networking"
type: "runbook"
logical_order: 20
date_rule: "Dates are removed from filenames, visible headings, indexes, generated metadata, and runbook body content."
---

# OPNsense Web GUI Failure Recovery Documentation and Runbook

This document contains two parts:

1. A dated troubleshooting/change record for the OPNsense Web GUI recovery session.
2. A reusable OPNsense Web GUI recovery runbook for future incidents.

---

# Part 1 — Troubleshooting and Change Record

# OPNsense Web GUI Failure and Factory Reset Recovery

## Summary

The OPNsense Web GUI stopped working correctly. Initial troubleshooting focused on recovering the Web GUI service stack through shell commands, service restarts, template regeneration, package repair, and console menu recovery options.

The issue progressed through several states:

- Web GUI not working
- `lighttpd` failing to restart
- Web GUI config file initially missing
- `configctl` returning `action not allowed`
- Web GUI partially loading the OPNsense “Hi there…” splash page
- Login functionality still not working
- Final recovery through console menu **Option 4: Reset to factory defaults**

The final resolution was a factory reset, which restored the Web GUI but also wiped the active OPNsense configuration.

## Environment

- Platform: OPNsense firewall
- Environment: Homelab
- Access methods:
  - OPNsense console menu
  - OPNsense shell
- Relevant services:
  - `lighttpd` — Web GUI frontend web server
  - `php-fpm` — PHP execution backend for Web GUI pages
  - `configd` — OPNsense backend configuration daemon
- Relevant files:
  - `/var/etc/lighty-webConfigurator.conf`
- Relevant firewall component:
  - `pf`, managed with `pfctl`
- Relevant update path:
  - OPNsense console menu Option 12
- Final recovery method:
  - OPNsense console menu Option 4

## Problem

The OPNsense Web GUI was not working. The user needed a way to restore management access from the shell or console menu.

## Symptoms

Observed or discussed symptoms included:

- Web GUI not functioning
- `lighttpd` unable to restart
- Initial reference to `/var/etc/lighty-webConfigurator.conf` returning a “no such directory” / missing file condition
- `configctl` producing an `action not allowed` error
- Web GUI later showing the OPNsense splash text:

```text
Hi there, for over a decade now OPNsense is driving...
```

- Despite the splash page loading, the GUI was still not usable
- This suggested static content could be served, but PHP/backend functionality was still broken

## Actions Taken

### 1. Attempted to restart Web GUI services

The first recovery step was to check and restart the Web GUI service stack.

```bash
service configd restart
service lighttpd restart
```

Purpose:

- Restart the OPNsense backend daemon
- Restart the Web GUI frontend service

### 2. Attempted to verify Web GUI config

The expected Web GUI config file was discussed:

```text
/var/etc/lighty-webConfigurator.conf
```

The file or path was initially reported as missing.

### 3. Attempted to regenerate Web GUI templates

```bash
configctl template reload OPNsense/WebGui
```

Purpose:

- Regenerate the Web GUI configuration, including `lighty-webConfigurator.conf`

Result:

- The user reported an `action not allowed` response.

### 4. Attempted to force HTTP on port 80

```bash
configctl webgui set protocol=http
configctl webgui set port=80
service lighttpd restart
```

Purpose:

- Bypass HTTPS, TLS, or certificate problems
- Attempt to restore GUI access over plain HTTP

### 5. Confirmed configs and `lighttpd` later existed

The user later reported:

```text
Configs and lighttpd are there now
```

At this stage, recovery shifted toward checking whether the service was actually listening and whether the backend was functional.

### 6. Discussed service/port validation

```bash
sockstat -4 -l | grep lighttpd
```

Purpose:

- Confirm whether `lighttpd` was listening on a Web GUI port such as 80 or 443

Also discussed local access testing:

```bash
curl -vk https://127.0.0.1:443
```

or, if HTTP was configured:

```bash
curl -vk http://127.0.0.1
```

Purpose:

- Determine whether the Web GUI responded locally from the firewall itself

### 7. Discussed temporary firewall bypass

```bash
pfctl -d
```

Purpose:

- Temporarily disable packet filtering to determine whether firewall rules were blocking GUI access

Risk:

- This temporarily disables firewall enforcement and should only be used briefly during troubleshooting.

Re-enable with:

```bash
pfctl -e
```

### 8. Discussed package repair

```bash
pkg install -f opnsense
pkg install -f lighttpd
```

Also later discussed PHP package repair:

```bash
pkg install -f php82 php82-extensions
```

Purpose:

- Repair or reinstall potentially broken OPNsense, web server, or PHP backend components

### 9. Used console update workflow

The user asked how to update through the shell and console menu.

Console menu Option 12 was discussed:

```text
12) Update from console
```

When prompted for a branch/version, the correct general input was discussed as:

```text
latest
```

The user mentioned entering:

```text
25.7
```

This was clarified as likely being interpreted as a version/branch prompt inside the updater, not the original console menu option.

### 10. Web GUI partially loaded

The user reached a page containing the OPNsense splash text:

```text
Hi there, for over a decade now OPNsense is driving...
```

This indicated:

- `lighttpd` was at least partially working
- Static files could be served
- The Web GUI was still not fully functional

Likely issue:

- PHP-FPM or backend services were not executing/rendering the login UI correctly

### 11. Discussed PHP/backend restart

```bash
service php-fpm restart
service configd restart
service lighttpd restart
```

Purpose:

- Restart the full backend/frontend Web GUI chain

### 12. Asked whether recovery could be done through menu options

The following console menu options were identified as useful:

```text
11) Reload all services
12) Update from console
4) Reset to factory defaults
```

Recommended order was:

1. Option 11 — reload all services
2. Option 12 — update from console
3. Option 4 — reset to factory defaults as last resort

### 13. Final recovery action: Option 4 factory reset

The user chose:

```text
4) Reset to factory defaults
```

Purpose:

- Fully reset OPNsense back to factory defaults

Impact:

- Restored default configuration
- Wiped custom firewall, interface, DHCP, NAT, DNS, VLAN, and other settings

## Key Findings

- `lighttpd` failure can be caused by missing or broken generated Web GUI config.
- `/var/etc/lighty-webConfigurator.conf` is generated by OPNsense, not normally hand-maintained.
- `configctl template reload OPNsense/WebGui` is the correct path to regenerate the Web GUI template.
- `configctl` returning `action not allowed` points toward a `configd` backend or permission issue.
- Seeing the OPNsense static “Hi there…” page means the web server is serving at least some static content.
- A static splash page without a usable login flow suggests PHP-FPM or backend execution failure.
- Console menu recovery options can fix many GUI issues without full reset:
  - Option 11 reloads services
  - Option 12 updates from console
- Option 4 factory reset is effective but destructive.

## Resolution

The issue was ultimately resolved by using OPNsense console menu:

```text
4) Reset to factory defaults
```

This reset OPNsense to its default state and restored Web GUI availability.

Default post-reset access:

```text
http://192.168.1.1
```

Default credentials:

```text
root / opnsense
```

## Validation

Validation should include:

- Web GUI loads fully
- Login form appears
- Login succeeds
- OPNsense dashboard opens
- `lighttpd`, `php-fpm`, and `configd` are running
- Firewall packet filtering is enabled
- LAN clients can reach the firewall GUI
- WAN/LAN interfaces are assigned correctly after reset

Useful validation commands:

```bash
service lighttpd status
service php-fpm status
service configd status
sockstat -4 -l | grep lighttpd
```

## Follow-Up Tasks

Because a factory reset was used, the following should be restored or rebuilt:

- WAN interface assignment
- LAN interface assignment
- LAN IP address
- DHCP server settings
- DNS resolver / Unbound settings
- Firewall rules
- NAT outbound rules
- Port forwards
- VLANs, if used
- Gateway configuration
- Static DHCP mappings
- Any aliases
- Any reverse proxy or homelab routing dependencies
- Any rules supporting Traefik or internal services
- Any DNS overrides for homelab services
- OPNsense config backup workflow

Recommended follow-up:

- Export a fresh known-good OPNsense config backup once rebuilt.
- Store the backup somewhere outside the firewall.
- Document custom firewall rules and interface assignments.

## Lessons Learned

- Try safe console options before factory reset:
  - Option 11: Reload all services
  - Option 12: Update from console
- Use factory reset only when backend/config recovery fails or fast restoration is more important than preserving current config.
- Keep OPNsense backups before major changes.
- A partially loading Web GUI is useful diagnostic evidence:
  - Static page = web server probably works
  - Missing login/backend behavior = PHP or configd problem
- During outages, console access is critical.
- Maintaining a short “break glass” runbook reduces guesswork during firewall failure.

---

# Part 2 — Reusable OPNsense Web GUI Recovery Runbook

## Purpose

Provide a repeatable, low-risk procedure to recover a broken OPNsense Web GUI in a homelab environment without immediately resorting to a factory reset.

## Scope

Covers issues where:

- Web GUI is unreachable
- Web GUI partially loads, such as the “Hi there…” page only
- `lighttpd` fails to start
- Backend services such as `configd` or PHP-FPM are broken

## Prerequisites

- Console access, such as physical console, IPMI, or Proxmox VM console
- Root access to the OPNsense shell or console menu
- Awareness that some actions, especially `pfctl -d` and factory reset, carry risk

---

# Recovery Workflow

## Phase 1 — Quick Wins

### 1. Reload All Services

From the OPNsense console menu, choose:

```text
11) Reload all services
```

Purpose:

- Restart core services such as `lighttpd`, `php-fpm`, and `configd`

Expected result:

- The Web GUI returns without further intervention

---

### 2. Reset Web GUI to HTTP

Switch from HTTPS to HTTP to eliminate certificate or TLS-related issues.

```bash
configctl webgui set protocol=http
configctl webgui set port=80
service lighttpd restart
```

Expected result:

```text
http://<LAN_IP>
```

---

### 3. Test Local Web Access

```bash
curl -vk http://127.0.0.1
```

Interpretation:

- HTML response: Web service is working locally.
- Connection refused: Web service is not running or not listening.
- Static page only: Web server may be working, but PHP/backend services may still be broken.

---

## Phase 2 — Service-Level Recovery

### 4. Restart Core Services Manually

```bash
service configd restart
service php-fpm restart
service lighttpd restart
```

Purpose:

- Restart the backend chain that supports the Web GUI:

```text
configd -> php-fpm -> lighttpd
```

Expected result:

- The Web GUI loads correctly and the login form appears.

---

### 5. Verify Web Server Binding

```bash
sockstat -4 -l | grep lighttpd
```

Expected result:

```text
*:80
```

or:

```text
*:443
```

If `lighttpd` is not listening, the problem is likely service or config related.

---

### 6. Temporarily Bypass Firewall Rules

```bash
pfctl -d
```

Purpose:

- Temporarily disables packet filtering to determine whether firewall rules are blocking access to the Web GUI

Warning:

- This temporarily allows traffic that would normally be filtered. Use only for testing.

Re-enable packet filtering afterward:

```bash
pfctl -e
```

---

## Phase 3 — Web GUI Config Repair

### 7. Regenerate Web GUI Config

```bash
configctl template reload OPNsense/WebGui
```

Expected result:

- Recreates the Web GUI config file:

```text
/var/etc/lighty-webConfigurator.conf
```

---

### 8. If You See “Action Not Allowed”

If `configctl` returns:

```text
action not allowed
```

Restart `configd`:

```bash
service configd restart
```

Then retry:

```bash
configctl template reload OPNsense/WebGui
```

Interpretation:

- An “action not allowed” error often points to a broken or stuck `configd` backend.

---

## Phase 4 — Package Repair

### 9. Reinstall Core Packages

```bash
pkg install -f opnsense
pkg install -f lighttpd
pkg install -f php82 php82-extensions
```

Purpose:

- Repair missing or corrupted OPNsense, web server, or PHP backend files

Expected result:

- Required package files are restored and services can start normally.

---

### 10. Update System from Console

From the OPNsense console menu, choose:

```text
12) Update from console
```

When prompted for a version or branch, enter:

```text
latest
```

When prompted to proceed, enter:

```text
y
```

After the update finishes, reboot.

Purpose:

- Pull fresh package and system updates that may repair broken GUI components.

---

## Phase 5 — Diagnose Partial Page Load

### Symptom

The Web GUI displays the OPNsense “Hi there…” page, but the login form is missing or not working.

### Likely Root Cause

`lighttpd` is serving static files, but PHP is not executing correctly.

### Fix

```bash
service php-fpm restart
service configd restart
service lighttpd restart
```

Expected result:

- The full login page appears and authentication works.

---

## Phase 6 — Last Resort

### 11. Factory Reset

From the OPNsense console menu, choose:

```text
4) Reset to factory defaults
```

Warning:

- This wipes the OPNsense configuration.

After reset, the Web GUI should be available at:

```text
http://192.168.1.1
```

Default login:

```text
root / opnsense
```

---

# Validation Checklist

After recovery, confirm:

- [ ] Web GUI loads fully, not just a static splash page.
- [ ] Login form appears.
- [ ] Authentication works.
- [ ] `lighttpd` is running.
- [ ] `php-fpm` is running.
- [ ] `configd` is running.
- [ ] Web GUI port is listening.
- [ ] Firewall packet filtering is re-enabled if it was disabled.

Check service status:

```bash
service lighttpd status
service php-fpm status
service configd status
```

Check listening ports:

```bash
sockstat -4 -l | grep lighttpd
```

Confirm firewall is enabled if you disabled it earlier:

```bash
pfctl -e
```

---

# Post-Recovery Tasks

If factory reset was used, reconfigure or restore:

- WAN and LAN interfaces
- Firewall rules
- NAT and port forwards
- DHCP settings
- VLANs
- DNS / Unbound settings
- Gateway configuration
- Static mappings
- Any Traefik or reverse proxy dependencies
- Internal service access rules

Also consider:

- Restoring from a known-good OPNsense config backup
- Re-enabling HTTPS for the Web GUI
- Verifying LAN-to-firewall access rules
- Exporting a fresh config backup after recovery

---

# Decision Tree

```text
GUI broken?
│
├── Try Option 11: Reload all services
│
├── Still broken?
│   ├── Reset Web GUI to HTTP:80
│   └── Restart lighttpd
│
├── Still broken?
│   ├── Restart configd, php-fpm, and lighttpd
│   └── Verify lighttpd is listening
│
├── Still broken?
│   ├── Temporarily disable packet filter with pfctl -d
│   └── Re-enable with pfctl -e after testing
│
├── Still broken?
│   ├── Regenerate Web GUI template
│   └── Restart configd if action is not allowed
│
├── Still broken?
│   ├── Reinstall opnsense, lighttpd, and PHP packages
│   └── Run console Option 12 update
│
├── Static page only?
│   └── Restart php-fpm, configd, and lighttpd
│
└── Completely broken?
    └── Console Option 4: Factory reset
```

---

# Command Reference

## Command

```bash
service configd restart
```

Restarts the OPNsense backend configuration daemon.

- Used when `configctl` fails or backend actions are not working.
- Expected success: `configd` restarts and accepts commands.
- Failure may indicate deeper service or package corruption.

---

## Command

```bash
service php-fpm restart
```

Restarts PHP-FPM, which executes the PHP code behind the OPNsense Web GUI.

- Used when the static page loads but the login form is missing.
- Expected success: PHP-backed GUI pages render correctly.

---

## Command

```bash
service lighttpd restart
```

Restarts the Web GUI frontend web server.

- Used when the GUI does not load or after regenerating GUI config.
- Expected success: `lighttpd` starts and listens on the configured port.

---

## Command

```bash
configctl template reload OPNsense/WebGui
```

Regenerates the OPNsense Web GUI template files.

- Used when `/var/etc/lighty-webConfigurator.conf` is missing or broken.
- Expected success: Web GUI config file is recreated.
- Failure such as “action not allowed” points toward `configd` issues.

---

## Command

```bash
configctl webgui set protocol=http
```

Sets the Web GUI protocol to HTTP.

- Used to bypass HTTPS, certificate, or TLS problems.
- Expected success: GUI can be reached over plain HTTP.

---

## Command

```bash
configctl webgui set port=80
```

Sets the Web GUI port to 80.

- Used to force access through a known default HTTP port.
- Watch for conflicts if another service is using port 80.

---

## Command

```bash
sockstat -4 -l | grep lighttpd
```

Checks whether `lighttpd` is listening on IPv4.

- Used to verify whether the Web GUI is actually bound to a port.
- Success shows `lighttpd` listening on port 80 or 443.

---

## Command

```bash
curl -vk http://127.0.0.1
```

Tests Web GUI access locally from the OPNsense firewall itself.

- Used to separate service problems from network/firewall problems.
- HTML output means the web service is responding locally.
- Connection refused means the service is not listening.

---

## Command

```bash
curl -vk https://127.0.0.1:443
```

Tests local HTTPS access to the Web GUI.

- Used when the GUI is expected to be available over HTTPS.
- The `-k` flag allows curl to ignore certificate validation errors.
- The `-v` flag prints verbose connection information.

---

## Command

```bash
pfctl -d
```

Disables the packet filter.

- Used to test whether firewall rules are blocking GUI access.
- Risk: temporarily bypasses firewall filtering.
- Use only during troubleshooting.

---

## Command

```bash
pfctl -e
```

Re-enables the packet filter.

- Used immediately after testing with `pfctl -d`.
- Expected result: firewall filtering resumes.

---

## Command

```bash
pkg install -f opnsense
```

Force reinstalls the OPNsense package.

- Used to repair missing or corrupted core files.
- Usually safer than a factory reset, but still significant.

---

## Command

```bash
pkg install -f lighttpd
```

Force reinstalls the `lighttpd` web server package.

- Used when Web GUI frontend files or binaries may be damaged.

---

## Command

```bash
pkg install -f php82 php82-extensions
```

Force reinstalls PHP and PHP extensions.

- Used when the Web GUI static page loads but PHP-backed pages fail.
- Relevant when the login form does not render.

---

## Command

```bash
opnsense-update -f
```

Forces an OPNsense firmware update refresh.

- Used to repair or refresh system update state.
- Often paired with the console update workflow.

---

## Command

```bash
opnsense-update -kr latest
```

Updates kernel and base system to the latest available release.

- Used for deeper repair when packages or base system components are inconsistent.
- Reboot afterward.

---

## Command

```bash
reboot
```

Reboots OPNsense.

- Used after package repair, updates, or major config repair.
- Expected result: clean service startup after boot.

---

## Console Option

```text
4) Reset to factory defaults
```

Factory resets OPNsense.

- Used only as a last resort.
- Risk: wipes firewall configuration.
- Expected result: Web GUI restored at `http://192.168.1.1`.

---

## Console Option

```text
11) Reload all services
```

Reloads all services from the OPNsense console menu.

- Used as the safest first recovery step.
- Expected result: Web GUI may return without deeper changes.

---

## Console Option

```text
12) Update from console
```

Runs OPNsense update from the console menu.

- Used to repair packages and system components.
- When prompted for version or branch, `latest` is usually appropriate for the current stable branch.

---

# Break Glass Checklist

Use this when the Web GUI is down and you need the fastest practical recovery path.

1. Console menu:
   ```text
   11) Reload all services
   ```

2. If still broken, shell:
   ```bash
   service configd restart
   service php-fpm restart
   service lighttpd restart
   ```

3. If still broken, force HTTP:
   ```bash
   configctl webgui set protocol=http
   configctl webgui set port=80
   service lighttpd restart
   ```

4. Test locally:
   ```bash
   curl -vk http://127.0.0.1
   ```

5. Check listening port:
   ```bash
   sockstat -4 -l | grep lighttpd
   ```

6. If access may be blocked:
   ```bash
   pfctl -d
   ```

   Re-enable immediately after testing:

   ```bash
   pfctl -e
   ```

7. If templates are broken:
   ```bash
   configctl template reload OPNsense/WebGui
   ```

8. If packages are broken:
   ```bash
   pkg install -f opnsense
   pkg install -f lighttpd
   pkg install -f php82 php82-extensions
   reboot
   ```

9. If nothing works and backup/rebuild is acceptable:
   ```text
   Console Option 4: Reset to factory defaults
   ```
