---
title: "Gluetun Startup Failure Caused by Corrupted Server Metadata"
track: "infrastructure"
category: "containers-apps"
type: "runbook"
logical_order: 10
date_rule: "Dates are removed from filenames, visible headings, indexes, generated metadata, and runbook body content."
---

# Gluetun Startup Failure Caused by Corrupted Server Metadata

## Summary
A Dockerized Gluetun VPN container repeatedly failed during startup. The session focused on identifying why the container exited immediately, interpreting the startup logs, and outlining a recovery procedure. The failure was traced to a corrupted Gluetun server metadata file, likely within the container’s persistent configuration storage.

## Environment
- Debian-based Docker host
- Docker Compose-managed container stack
- Gluetun container
- Persistent application data under `/opt/docker-apps/Gluetun`
- Homelab application layout consistent with bind-mounted appdata paths
- Likely local Docker appdata path rather than ephemeral container-only storage
- Timezone shown in logs: `-06:00`
- Gluetun build reported in logs:
  - `latest`
  - built on `[date removed]`
  - commit `712f7c3`

## Problem
The Gluetun container would not remain running and exited during initialization.

## Symptoms
Observed Gluetun log output included:
- Obsolete environment variable warning:
  - `WARN HEALTH_VPN_DURATION_INITIAL is obsolete`
- Normal early startup messages:
  - default route discovery
  - local ethernet discovery
  - firewall enablement
- Fatal error:
```text
ERROR reading servers from file: decoding servers: invalid character '\x00' looking for beginning of object key string
```
- Graceful shutdown immediately after the error:
```text
INFO Shutdown successful
```
- Repeated restart attempts ending with:
```text
gluetun exited with code 1
```

## Actions Taken
1. Reviewed the Gluetun startup logs.
2. Isolated the fatal error involving server metadata parsing.
3. Identified the most likely bad file as a persisted `servers.json` or similar cached server-list file.
4. Recommended stopping the Gluetun container before modifying its persistent files.
5. Recommended checking the Gluetun appdata directory under `/opt/docker-apps/Gluetun`.
6. Recommended confirming corruption by checking for null bytes in the server metadata file.
7. Recommended deleting the corrupted server cache files so Gluetun could recreate them.
8. Recommended removing the obsolete `HEALTH_VPN_DURATION_INITIAL` environment variable from the Compose configuration.
9. Recommended restarting the container and reviewing logs again.

## Key Findings
- Gluetun completed several early initialization steps successfully:
  - routing detection worked
  - interface discovery worked
  - firewall initialization worked
- The crash occurred only when reading persisted server metadata.
- The error text strongly indicated malformed JSON containing null bytes (`\x00`), which is consistent with file corruption rather than a routing or VPN authentication problem.
- The obsolete health environment variable did not appear to be the direct cause of the crash, but it should still be removed for cleanup and future compatibility.
- The service exited cleanly after encountering the file-decoding error, indicating controlled application shutdown rather than host instability.

## Resolution
The recommended recovery was to remove the corrupted Gluetun server metadata cache, specifically the persisted `servers.json` and any related archive such as `servers.json.zip`, then restart the container so it could repopulate valid metadata.

The obsolete `HEALTH_VPN_DURATION_INITIAL` variable was also identified for removal from the Docker Compose environment section.

## Validation
Success would be confirmed by:
- Gluetun starting without exiting
- no recurrence of the JSON decoding error
- container logs progressing past the server metadata load stage
- container remaining up instead of repeatedly restarting
- normal VPN initialization continuing after firewall enablement

## Follow-Up Tasks
- Remove `HEALTH_VPN_DURATION_INITIAL` from the Compose file
- Pin Gluetun to a specific image tag instead of `latest`
- Confirm the persistent Gluetun data path is on stable local storage
- Avoid storing Gluetun state on unreliable or remote-mounted paths
- Review the container volume mappings for the Gluetun config directory
- Monitor for recurrence after restart

## Lessons Learned
- A clean startup sequence can still fail late due to corrupted persistent application state.
- A JSON parse error containing `\x00` strongly suggests file corruption or a partial write.
- Obsolete environment variables may not be fatal, but they create noise and should be cleaned up.
- When a container repeatedly exits during startup, persistent bind-mounted state should be checked early.

# Host-Side Permission Problem on Gluetun Config Directory

## Summary
After identifying the corrupted Gluetun server metadata issue, a second operational problem appeared: the host user `debian` no longer had permission to modify the Gluetun configuration directory. The session shifted to restoring maintainable ownership and write access on the host while preserving container functionality.

## Environment
- Debian host user: `debian`
- Docker and Docker Compose
- Gluetun application directory:
  - `/opt/docker-apps/Gluetun`
  - specifically `/opt/docker-apps/Gluetun/config/`
- Host-side file ownership reported as `root:root`
- Container likely writing files as root inside the bind-mounted host path

## Problem
The `debian` user could no longer make changes inside the Gluetun config directory because the directory ownership and permissions were incompatible with normal host-side administration.

## Symptoms
- Host-side Gluetun config path was owned by:
```text
root:root
```
- The `debian` user could not modify files in:
```text
/opt/docker-apps/Gluetun/config/
```
- Permission issues appeared after the Gluetun troubleshooting work, likely due to container-created files or directories being written as root.

## Actions Taken
1. Identified that the host-side config directory ownership was `root:root`.
2. Explained that Gluetun likely wrote files as root inside the container, causing root-owned files on the host bind mount.
3. Recommended stopping the Gluetun container before changing ownership or permissions.
4. Recommended ensuring the `debian` user was a member of the `docker` group.
5. Recommended recursively changing ownership of the Gluetun directory to `debian:docker`.
6. Recommended applying directory permissions with the setgid bit so new files inherit the `docker` group.
7. Recommended applying cooperative file permissions so both the owner and group can modify content.
8. Recommended installing and using ACLs so future files created under the directory remain editable by the host user and group.
9. Recommended deleting the corrupted Gluetun server metadata files once access was restored.
10. Recommended restarting the container and watching logs.

## Key Findings
- The permission problem was distinct from the original startup corruption issue.
- The underlying cause was likely host bind-mounted content being created by a root-running container process.
- Without corrective ownership, future maintenance of Gluetun config files from the host would remain difficult.
- Setting normal UNIX ownership alone may not be enough if the container continues creating new files as root.
- Default ACLs and setgid directory permissions were recommended to make future writes operationally manageable.

## Resolution
The recommended fix was:
- stop the container
- add `debian` to the `docker` group
- recursively change ownership of `/opt/docker-apps/Gluetun` to `debian:docker`
- apply group-friendly permissions with setgid on directories
- apply default ACLs so newly created content remains writable by the intended host administrator
- remove the corrupted metadata files
- restart Gluetun

This established a more maintainable host-side permission model for a container that may still write files as root.

## Validation
Success would be confirmed by:
- the `debian` user being able to create, edit, and remove files under `/opt/docker-apps/Gluetun/config/`
- new files inheriting the correct group ownership
- Gluetun starting successfully after metadata cleanup
- no immediate recurrence of root-only access problems for routine config edits

## Follow-Up Tasks
- Verify the effective group membership of `debian` after re-login or shell refresh
- Confirm ACL support is installed and active on the filesystem
- Review whether Gluetun can be run with a non-root UID/GID in this deployment model
- Validate that the Gluetun bind mount is on local storage and not a remote share
- Check whether other application directories under `/opt/docker-apps` have similar ownership drift
- Standardize a host-side ownership model for Docker appdata directories

## Lessons Learned
- Container root writes to bind mounts commonly produce `root:root` ownership on the host.
- Permission fixes should be durable, not just one-time `chown` corrections.
- setgid directories plus default ACLs are useful when a containerized app must remain editable from the host.
- Permission problems can mask or delay direct remediation of the original application issue.

# Command Reference

## Command
```bash
docker compose stop gluetun
```

### Purpose
Stop the Gluetun service managed by Docker Compose before modifying its files or permissions.

### What it does
Stops the Gluetun container defined in the current Compose project.

### Why it was used
To prevent Gluetun from writing to its state directory while troubleshooting corruption or changing ownership.

### Expected result
The Gluetun container stops cleanly.

### Success or failure meaning
- Success: safe to inspect or modify persistent files
- Failure: container may still be running, which risks race conditions

### Risk
Low.

### Safer alternative
None needed for this task.

## Command
```bash
docker stop gluetun
```

### Purpose
Stop the Gluetun container directly when not using Compose context.

### What it does
Stops the running container named `gluetun`.

### Why it was used
As an alternative to the Compose-based stop command.

### Expected result
Container stops and releases active file access.

### Success or failure meaning
- Success: safe to work on host-side bind-mounted files
- Failure: wrong container name or Docker daemon issue

### Risk
Low.

## Command
```bash
GLUETUN_DIR=/opt/docker-apps/gluetun
[ -d "$GLUETUN_DIR" ] || GLUETUN_DIR=/var/lib/docker/appdata/Gluetun
echo "$GLUETUN_DIR"
ls -lah "$GLUETUN_DIR"
```

### Purpose
Identify the actual persistent Gluetun appdata directory on the host.

### What it does
- assigns a likely path
- falls back to another likely path if the first does not exist
- prints the selected path
- lists the contents for inspection

### Why it was used
To locate the persisted server metadata files and confirm the appdata layout.

### Expected result
A valid Gluetun appdata directory is displayed and listed.

### Success or failure meaning
- Success: persistent state location is identified
- Failure: volume mapping may differ from expectations

### Risk
Low.

### Notes
This is a reconstructed helper sequence, not a platform command.

## Command
```bash
grep -nU $'\x00' "$GLUETUN_DIR/servers.json" || true
```

### Purpose
Check whether the Gluetun server metadata file contains null bytes.

### What it does
Searches `servers.json` for null characters and prints matching line information if found.

### Important flags or arguments
- `-n`: show line numbers
- `-U`: treat file as binary when needed
- `|| true`: prevent the shell from stopping on non-match

### Why it was used
The log error referenced `\x00`, which commonly indicates corruption.

### Expected result
Matches indicate null-byte corruption.

### Success or failure meaning
- Success with matches: strong evidence of file corruption
- No matches: corruption may still exist in another malformed form

### Risk
Low.

## Command
```bash
head -c 200 "$GLUETUN_DIR/servers.json" | cat -A
```

### Purpose
Inspect the beginning of the JSON file for non-printable or malformed content.

### What it does
Prints the first 200 bytes of the file and reveals control characters in a visible format.

### Important flags or arguments
- `head -c 200`: read only the first 200 bytes
- `cat -A`: show hidden/control characters

### Why it was used
To visually confirm whether the file contains corruption such as null bytes.

### Expected result
A clean JSON file should begin with valid JSON syntax.

### Success or failure meaning
- Success with readable JSON: file may be intact at the beginning
- Visible control characters or garbage: likely corrupted file

### Risk
Low.

## Command
```bash
rm -f "$GLUETUN_DIR/servers.json" "$GLUETUN_DIR/servers.json.zip" 2>/dev/null || true
```

### Purpose
Remove corrupted Gluetun server metadata cache files.

### What it does
Deletes the JSON metadata file and related archive if present.

### Important flags or arguments
- `-f`: force removal without prompting
- `2>/dev/null`: hide harmless file-not-found errors
- `|| true`: ignore command failure in strict shells

### Why it was used
To allow Gluetun to rebuild or re-download valid server metadata.

### Expected result
Corrupted cache files are removed.

### Success or failure meaning
- Success: next startup should attempt to recreate clean metadata
- Failure: permissions or incorrect path may block cleanup

### Risk
Moderate.
This deletes files. Confirm the path carefully before running.

### Safer alternative
Rename the files first for backup:
```bash
mv "$GLUETUN_DIR/servers.json" "$GLUETUN_DIR/servers.json.bak"
```

## Command
```bash
chmod u+rwX "$GLUETUN_DIR"
```

### Purpose
Ensure the owner has read, write, and directory traversal access to the Gluetun directory.

### What it does
Adds owner read/write access and execute only where appropriate.

### Why it was used
To improve host-side writability of the application directory.

### Expected result
Owner permissions become less restrictive.

### Success or failure meaning
- Success: owner can better manage the directory
- Failure: wrong ownership or missing privileges still block access

### Risk
Low.

## Command
```yaml
image: qmcgaw/gluetun:vX.Y.Z
```

### Purpose
Pin the Gluetun image to a known release instead of using `latest`.

### What it does
Configures Docker Compose to pull and run a specific Gluetun version.

### Why it was used
To reduce upgrade-related surprises and configuration drift.

### Expected result
Future deployments use a fixed version.

### Success or failure meaning
- Success: consistent repeatable container behavior
- Failure: tag may not exist or may be outdated

### Risk
Low.

## Command
```bash
docker compose up -d gluetun
```

### Purpose
Start Gluetun in detached mode after cleanup or permission changes.

### What it does
Creates or starts the Gluetun service in the background.

### Important flags or arguments
- `-d`: detached mode

### Why it was used
To test whether the corrupted metadata fix resolved the startup problem.

### Expected result
The container starts and remains running.

### Success or failure meaning
- Success: startup proceeds normally
- Failure: logs should be checked for remaining errors

### Risk
Low.

## Command
```bash
docker logs -f gluetun
```

### Purpose
Follow Gluetun logs in real time after restart.

### What it does
Streams live log output from the Gluetun container.

### Important flags or arguments
- `-f`: follow mode

### Why it was used
To confirm whether the server metadata error was gone and whether initialization continued successfully.

### Expected result
Logs progress past the previous failure point.

### Success or failure meaning
- Success: container remains up and logs continue normally
- Failure: repeated fatal messages indicate unresolved issues

### Risk
Low.

## Command
```bash
curl -fsSL -o "$GLUETUN_DIR/servers.json" \
  https://raw.githubusercontent.com/qdm12/gluetun/refs/heads/master/internal/storage/servers.json
```

### Purpose
Manually seed a fresh Gluetun server metadata file.

### What it does
Downloads a server metadata JSON file directly into the Gluetun persistent directory.

### Important flags or arguments
- `-f`: fail on server errors
- `-s`: silent mode
- `-S`: show errors when silent
- `-L`: follow redirects
- `-o`: write output to the specified file

### Why it was used
As an optional manual recovery path if automatic regeneration was not desired or did not work.

### Expected result
A new `servers.json` is written to the Gluetun directory.

### Success or failure meaning
- Success: startup can use a fresh metadata file
- Failure: network, path, or permission issue

### Risk
Moderate.
This overwrites the destination file.

### Safer alternative
Write to a temporary file first, inspect it, then move it into place.

## Command
```bash
sudo usermod -aG docker debian
```

### Purpose
Add the `debian` user to the `docker` group.

### What it does
Appends the user to the supplementary `docker` group without removing existing group memberships.

### Important flags or arguments
- `-a`: append
- `-G`: supplementary groups

### Why it was used
To ensure the `debian` user has the intended group membership for Docker-related file access and administration.

### Expected result
The user is added to the `docker` group.

### Success or failure meaning
- Success: group membership change applies on next login or shell refresh
- Failure: insufficient privileges or invalid group/user

### Risk
Low.

### Notes
Requires a new login session, `newgrp`, or equivalent for the current shell to reflect the change.

## Command
```bash
newgrp docker
```

### Purpose
Refresh the current shell with the `docker` group as the active group.

### What it does
Starts a new shell session using the specified group.

### Why it was used
To avoid logging out and back in immediately after changing group membership.

### Expected result
Current shell sees updated effective group context.

### Success or failure meaning
- Success: group-based access can be tested immediately
- Failure: the user may still need to log out and back in

### Risk
Low.

## Command
```bash
sudo chown -R debian:docker /opt/docker-apps/Gluetun
```

### Purpose
Recursively transfer ownership of the Gluetun appdata directory to the intended host user and group.

### What it does
Changes owner to `debian` and group to `docker` for all files and directories under the path.

### Important flags or arguments
- `-R`: recursive

### Why it was used
To restore host-side administrative control over Gluetun files after root-owned content appeared.

### Expected result
Files become owned by `debian:docker`.

### Success or failure meaning
- Success: host-side edits become possible
- Failure: path, privileges, or filesystem restrictions need review

### Risk
Moderate.
Recursive ownership changes can have broad effects if the path is wrong.

### Safer alternative
Run first on the specific `config` subdirectory if a narrower change is preferred.

## Command
```bash
sudo find /opt/docker-apps/Gluetun -type d -exec chmod 2775 {} \;
```

### Purpose
Make directories group-writable and enforce group inheritance on newly created entries.

### What it does
Finds all directories and sets permissions to `2775`.

### Important flags or arguments
- `-type d`: directories only
- `chmod 2775`:
  - `2`: setgid bit
  - `775`: rwx for owner and group, rx for others

### Why it was used
To make future directory content inherit the `docker` group and remain manageable from the host.

### Expected result
Directories become group-cooperative and inherit group ownership.

### Success or failure meaning
- Success: new files under these directories tend to stay in the intended group
- Failure: permissions remain inconsistent

### Risk
Moderate.
Applying permissions recursively should be limited to the correct path.

## Command
```bash
sudo find /opt/docker-apps/Gluetun -type f -exec chmod 664 {} \;
```

### Purpose
Make files readable and writable by owner and group.

### What it does
Finds all regular files and sets them to `664`.

### Important flags or arguments
- `-type f`: files only
- `664`: rw for owner/group, r for others

### Why it was used
To complement the directory permission model and permit host-side editing by the intended user/group.

### Expected result
Files are writable by both owner and group.

### Success or failure meaning
- Success: routine edits no longer require root
- Failure: ownership or ACLs may still block effective access

### Risk
Moderate.

## Command
```bash
sudo apt-get update -y && sudo apt-get install -y acl
```

### Purpose
Install ACL tooling on the Debian host.

### What it does
Refreshes package metadata and installs the `acl` package.

### Important flags or arguments
- `-y`: automatically answer yes to prompts

### Why it was used
Default ACLs were needed so future files created in the directory would remain manageable.

### Expected result
The `setfacl` command becomes available.

### Success or failure meaning
- Success: ACLs can be configured
- Failure: package management or network issue

### Risk
Low.

## Command
```bash
sudo setfacl -R -m u:debian:rwx,g:docker:rwx /opt/docker-apps/Gluetun
```

### Purpose
Apply ACL entries granting explicit access to the `debian` user and `docker` group.

### What it does
Recursively adds ACL rules giving read/write/execute permissions where applicable.

### Important flags or arguments
- `-R`: recursive
- `-m`: modify ACL entries

### Why it was used
To ensure that standard ownership alone would not block future administration.

### Expected result
The `debian` user and `docker` group gain effective access to the directory tree.

### Success or failure meaning
- Success: host-side manageability improves
- Failure: ACL support or filesystem compatibility issue

### Risk
Moderate.

## Command
```bash
sudo setfacl -R -m d:u:debian:rwx,d:g:docker:rwx /opt/docker-apps/Gluetun
```

### Purpose
Set default ACLs for newly created files and directories.

### What it does
Recursively applies default ACL entries so future content inherits the desired access model.

### Important flags or arguments
- `d:` prefix: default ACL entry
- `-R`: recursive
- `-m`: modify ACL entries

### Why it was used
To prevent recurring permission drift when the container creates new content.

### Expected result
New files and directories under the tree inherit useful access for the host admin user and group.

### Success or failure meaning
- Success: permission model becomes durable
- Failure: filesystem or ACL support issue

### Risk
Moderate.

## Command
```bash
rm -f /opt/docker-apps/Gluetun/servers.json /opt/docker-apps/Gluetun/servers.json.zip
```

### Purpose
Delete corrupted Gluetun metadata after restoring host-side write access.

### What it does
Removes the known-bad cache files from the appdata directory.

### Why it was used
To complete the original corruption remediation once permission issues were solved.

### Expected result
Corrupted files are gone and Gluetun can rebuild them.

### Success or failure meaning
- Success: cleanup is complete
- Failure: remaining permission or path issue

### Risk
Moderate.
Verify the path before deletion.
