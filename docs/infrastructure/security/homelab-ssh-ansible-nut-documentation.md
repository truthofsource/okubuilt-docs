---
title: "SSH Key Refused but Password Allowed"
track: "infrastructure"
category: "security"
type: "runbook"
logical_order: 20
date_rule: "Dates are removed from filenames, visible headings, indexes, generated metadata, and runbook body content."
---

# SSH Key Refused but Password Allowed

## Summary
Troubleshot an SSH authentication situation where the client reports an SSH key is refused, but the session still allows password login. Clarified how SSH key-based authentication works (public key on server, private key on client) and identified likely causes and next diagnostic steps.

## Environment
- Homelab Linux hosts/VMs accessed via SSH (exact hosts not specified)
- SSH client (likely OpenSSH) from a workstation/phone/terminal
- SSH server (sshd) on the target host(s)

## Problem
SSH reports that a key was “refused” (public key authentication failed), yet password authentication still succeeds.

## Symptoms
- Terminal indicates SSH key authentication was refused/denied.
- User is still prompted for a password and can log in successfully.

## Actions Taken
1. Interpreted the behavior as SSH attempting public key authentication first and then falling back to password authentication if allowed.
2. Confirmed correct key ownership model:
   - Server stores the user’s **public key** in `~/.ssh/authorized_keys`.
   - Client holds the matching **private key** and presents proof during login.

## Key Findings
- “Key refused but password works” is consistent with:
  - The server not accepting the offered key (missing/wrong `authorized_keys`, wrong user, permission issues, or policy/config restrictions), **while still allowing** password auth.
- The keypair relationship is:
  - **Public key**: safe to distribute; placed on server for the target login user.
  - **Private key**: must remain on the client; used to prove identity.
- Separate concept noted:
  - SSH server also has **host keys** used to prove the server’s identity to the client; these are different from user keys.

## Resolution
No change was applied in this chat. Current status is **diagnostic understanding established**; next step is to confirm *why* the server rejected the key.

## Validation
Not performed in this chat. Typical validation would be:
- Run SSH with verbose logging and confirm the server accepts the intended key without prompting for a password.

## Follow-Up Tasks
- Run a verbose SSH connection to identify the exact failure point (wrong key, wrong user, permissions, server policy):
  - `ssh -vvv user@host`
- Verify the public key is in the correct account’s `~/.ssh/authorized_keys`.
- Verify server-side permissions/ownership on `~/.ssh` and `authorized_keys`.
- Confirm SSH daemon policy allows public key auth and that the offered algorithm isn’t restricted.

## Lessons Learned
- SSH auth is a **method chain**: public key can fail silently and password can still succeed if enabled.
- “SSH key refused” is usually a **configuration/permissions/user mismatch**, not proof that keys are “broken.”
- Keep user keypairs distinct from SSH server host keys.

---

# Ansible Concepts and Homelab Use Cases (NUT Example)

## Summary
Explored what Ansible is like at a practical level and how it can be used in a homelab to make consistent, bulk changes across many nodes. Used “install and configure NUT (Network UPS Tools) across all nodes” as a motivating example, including how Ansible manages non-YAML config files.

## Environment
- Homelab fleet of Linux nodes/VMs (Proxmox nodes + Linux VMs implied)
- Management via SSH (Ansible default transport)
- Candidate service: NUT (Network UPS Tools) for UPS monitoring and controlled shutdown

## Problem
Manual configuration and drift across multiple nodes makes “fleet-wide” changes (like installing NUT everywhere and keeping configs consistent) slow, error-prone, and difficult to repeat.

## Symptoms
- Not an outage in this chat; rather a skills/workflow goal:
  - Desire for repeatable bulk changes
  - Desire to manage service configs centrally and apply consistently

## Actions Taken
1. Described Ansible’s core model:
   - Inventory (targets), playbooks (desired state), modules (actions), idempotence (safe re-runs)
2. Gave example patterns:
   - Standardizing Docker settings across multiple Docker VMs (daemon.json + handlers)
   - Performing a bulk change across all nodes (SSH policy + authorized keys)
3. Outlined the typical NUT deployment pattern:
   - 1 NUT “server” attached to UPS via USB
   - NUT “clients” on other nodes to monitor and shut down cleanly
4. Clarified config management approach:
   - Ansible playbooks are YAML, but they can manage config files in *any* format (NUT configs are not YAML).

## Key Findings
- Ansible’s main benefits in a homelab:
  - **Consistency** (reduces drift)
  - **Repeatability** (rebuild/replace nodes easily)
  - **Bulk changes** (apply the same policy across all nodes)
  - **Safer ops** via idempotent tasks and controlled restarts (“handlers”)
- NUT fits Ansible well because it’s:
  - Package installation + service enablement
  - A small set of predictable config files
  - A server/client pattern that maps naturally to inventory groups
- Ansible can manage NUT config files using:
  - **Templates** (preferred for “this file should look exactly like this, with variables”)
  - **Copy** (static identical files)
  - **Line/block edits** (surgical changes while preserving defaults)

## Resolution
No NUT deployment was executed in this chat. Outcome is a clear design for how Ansible would manage it:
- One role (e.g., `nut`) with conditional tasks for server vs clients
- Inventory groups to control which nodes get server/client configs
- Templates for NUT config files, with Ansible handlers to restart services only when needed

## Validation
Not performed in this chat. Typical validation would include:
- Confirm packages installed on all targets
- Confirm services enabled and active
- Confirm NUT clients can query the server (`upsc`) and shutdown behavior is correct (in a safe test scenario)

## Follow-Up Tasks
- Decide which node is physically connected to the UPS (designate as NUT server).
- Define inventory groups: `nut_server` and `nut_clients`.
- Store credentials safely (Ansible Vault or equivalent).
- Add observability/alerts (optional): NUT status checks and notification path.

## Lessons Learned
- Even when config files aren’t YAML, Ansible can still manage them cleanly via templates and idempotent file tasks.
- Using groups + variables is the “real” unlock: you can apply patterns (server/client) without duplicating playbooks.

---

# Command Reference

## Command
```bash
ssh -vvv user@host
```

**Purpose (main flow):** Produce verbose SSH client logs to see exactly why public key auth was rejected and what method succeeded next.

**What it does:**  
Starts an SSH connection with maximum verbosity (client-side). It prints the auth methods attempted (publickey, password), which keys were offered, and what the server accepted or rejected.

**Important flags/arguments:**
- `-vvv`: triple verbose output (most detail)
- `user@host`: target user and host/IP for the SSH login

**Why it was used at that moment:**  
To move from “key refused” (symptom) to the specific root cause (wrong key, wrong user, missing key on server, permissions, server policy).

**Expected result:**  
Log lines showing:
- which identity files are tried
- “Offering public key …”
- whether the server accepts it
- if rejected, which auth methods remain

**Success indicates:**  
Seeing “Server accepts key” (or equivalent) and logging in without a password prompt.

**Failure indicates:**  
Repeated key offers rejected and fallback to password, or total auth failure with “Permission denied”.

**Risky?**  
Low risk. It only increases logging on the client. Do not paste logs publicly if they include sensitive hostnames, usernames, or internal IPs.

---

## Command
```bash
ssh -i ~/.ssh/id_ed25519 user@host
```

**Purpose (main flow):** Force the SSH client to use a specific private key.

**What it does:**  
Connects to the host using the given identity file as the private key.

**Important flags/arguments:**
- `-i <path>`: path to the private key to use

**Why it was used at that moment:**  
When multiple keys exist locally and the client offers the “wrong” one first, or does not try the intended key.

**Expected result:**  
The server accepts that key and you log in without password, if public key auth is configured correctly.

**Success indicates:**  
No password prompt; auth succeeds via public key.

**Failure indicates:**  
Key mismatch, server-side key not installed for that user, permissions problems, or server policy disallowing that key type.

**Risky?**  
Low risk. Main risk is user confusion from using the wrong key or exposing key paths in shared logs.

---

## Command (implied server-side permissions fix)
```bash
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys
chown -R "$USER:$USER" ~/.ssh
```

**Purpose (main flow):** Fix common SSH key authentication failures caused by permissive permissions or wrong ownership.

**What it does:**  
Locks down the `.ssh` directory and `authorized_keys` file so `sshd` will trust and use them.

**Important flags/arguments:**
- `chmod 700`: only the user can access the `.ssh` directory
- `chmod 600`: only the user can read/write `authorized_keys`
- `chown -R`: recursively sets ownership; be cautious with `-R`

**Why it was used at that moment:**  
`sshd` often ignores keys if permissions are too open or ownership is wrong.

**Expected result:**  
After fixing permissions, public key auth should work, assuming the correct key is present for the correct user.

**Success indicates:**  
Key auth succeeds and password is no longer needed.

**Failure indicates:**  
Key is missing/wrong, wrong user, or server configuration disables/restricts public key auth.

**Risky?**  
Moderate if you run `chown -R` on the wrong path. Safer alternative:

```bash
chown -R "$USER:$USER" /home/<user>/.ssh
```

---

## Command (Ansible/NUT config management example pattern)
```yaml
- name: Render upsmon.conf from template
  template:
    src: upsmon.conf.j2
    dest: /etc/nut/upsmon.conf
    owner: root
    group: nut
    mode: "0640"
  notify: restart nut-monitor
```

**Purpose (main flow):** Manage NUT config files, which are non-YAML, consistently across nodes using Ansible.

**What it does:**  
Renders a Jinja2 template into a destination file with controlled permissions, and triggers a handler restart only if the file changed.

**Important fields:**
- `template:` module: renders `*.j2` with variables
- `dest`: where the config lands on the target
- `mode/owner/group`: ensures correct access controls
- `notify`: triggers restart only when changes occur

**Why it was used at that moment:**  
To answer whether Ansible can edit/manage NUT configs and to show the most common, maintainable approach.

**Expected result:**  
Config files become predictable and identical, with per-host or per-group variables, and service restarts are controlled.

**Risky?**  
Low-to-moderate. Overwriting configs can break a service if the template is wrong. Safer pattern: test on one node/group first, or use `blockinfile` for incremental injection.
