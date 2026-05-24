---
title: "Recreate `mainframe` OSD on `/dev/sda` and Restore Cluster Capacity"
track: "infrastructure"
category: "storage"
type: "runbook"
logical_order: 20
date_rule: "Dates are removed from filenames, visible headings, indexes, generated metadata, and runbook body content."
---

# Recreate `mainframe` OSD on `/dev/sda` and Restore Cluster Capacity

## Summary
Work focused on removing a broken or misprovisioned Ceph OSD on `mainframe`, cleaning up an accidental OSD deployment on the wrong disk, recreating the OSD on the intended device (`/dev/sda`), and restoring it to cluster service.

## Environment
- Platform: Proxmox VE with Ceph Reef
- Cluster FSID: `5e281287-9217-4e59-b590-400f72adc1e9`
- Ceph version observed later in logs: `18.2.7 (reef)`
- Hosts involved: `mainframe`, `pve1`, `pve2`, `pve3`, `pve4`
- OSD layout at the time: `osd.0` on `mainframe`, `osd.1` on `pve3`, `osd.2` on `pve2`, `osd.3` on `pve1`, `osd.4` on `pve4`
- Intended `mainframe` OSD disk: `/dev/sda`
- Mistakenly used disk during recovery attempt: `/dev/nvme0n1`

## Problem
`osd.0` on `mainframe` was down, missing its OSD data directory, and had been recreated on the wrong device during troubleshooting.

## Symptoms
- Cluster showed `5 osds: 4 up, 4 in`
- `osd.0` repeatedly crashed on `mainframe`
- `ceph-osd@0` was inactive or failed
- `/var/lib/ceph/osd/ceph-0` was missing at one point
- `ceph-volume lvm create --bluestore --data /dev/nvme0n1` was run, then later identified as a mistake
- A stale masked `ceph-osd@0` unit blocked a later recreation attempt on `/dev/sda`

## Actions Taken
1. Checked cluster state and OSD health.
   ```bash
   ceph osd stat
   ceph osd tree
   ceph health detail
   ```
   Purpose: confirm which OSD was down and whether cluster health was degraded.

2. Checked local OSD service state and OSD directory.
   ```bash
   systemctl status ceph-osd@0 --no-pager
   journalctl -u ceph-osd@0 -n 300 --no-pager
   ls -ld /var/lib/ceph/osd/ceph-0
   ceph-volume lvm list | sed -n '1,200p'
   ```
   Purpose: determine whether the OSD existed locally and whether Ceph volume metadata still referenced it.

3. Attempted a quick BlueStore repair.
   ```bash
   systemctl stop ceph-osd@0
   ceph-bluestore-tool quick-fix --path /var/lib/ceph/osd/ceph-0 || true
   systemctl start ceph-osd@0
   ```
   Purpose: try a non-destructive repair before full rebuild.

4. Confirmed the OSD data directory was missing and later noticed the OSD had been recreated on the wrong disk.
   ```bash
   ceph-volume lvm create --bluestore --data /dev/nvme0n1
   ```
   Purpose: this recreated `osd.0` on the wrong device and had to be undone.

5. Marked the OSD out, stopped it, purged it from Ceph, and removed its CRUSH host entry.
   ```bash
   ceph osd out 0
   systemctl stop ceph-osd@0
   ceph crash archive-all
   ceph osd crush rm mainframe
   ceph osd purge 0 --yes-i-really-mean-it
   ```
   Purpose: safely remove the broken OSD from cluster maps before reprovisioning.

6. Zapped the mistaken OSD deployment on `/dev/nvme0n1`.
   ```bash
   ceph-volume lvm zap /dev/nvme0n1 --destroy
   rm -rf /var/lib/ceph/osd/ceph-0 || true
   ```
   Purpose: erase BlueStore/LVM metadata from the wrong device.

7. Found `/dev/sda` was already prepared from a previous attempt, then zapped it too.
   ```bash
   ceph-volume lvm list /dev/sda | sed -n '1,200p'
   ceph-volume lvm zap /dev/sda --destroy
   ```
   Purpose: remove stale OSD metadata so `/dev/sda` could be used cleanly.

8. Cleared stale mounts and the masked unit that prevented OSD recreation.
   ```bash
   umount -l /var/lib/ceph/osd/ceph-0 2>/dev/null || true
   rm -rf /var/lib/ceph/osd/ceph-0 2>/dev/null || true
   systemctl unmask ceph-osd@0
   systemctl daemon-reload
   ```
   Purpose: remove state left behind by earlier failed attempts.

9. Recreated the OSD correctly on `/dev/sda`.
   ```bash
   ceph-volume lvm create --bluestore --data /dev/sda
   ```
   Purpose: provision a fresh BlueStore OSD on the intended disk.

10. Recreated the `mainframe` CRUSH bucket and re-added `osd.0`.
    ```bash
    ceph osd crush add-bucket mainframe host 2>/dev/null || true
    ceph osd crush move mainframe root=default
    ceph osd crush set-device-class ssd osd.0
    ceph osd crush add osd.0 0.45479 host=mainframe 2>/dev/null || \
      ceph osd crush reweight osd.0 1.0
    ceph osd in 0 || true
    ceph osd reweight 0 1.0
    ceph osd unset noout
    ```
    Purpose: put the new OSD back into CRUSH and allow recovery/backfill to begin.

## Key Findings
- `osd.0` had no valid local OSD directory during part of the incident.
- The first recreation landed on `/dev/nvme0n1`, which was not the intended disk.
- `/dev/sda` also had stale Ceph LVM metadata and had to be zapped.
- A masked `ceph-osd@0` unit caused a rollback when recreating the OSD.
- After unmasking and cleaning up old state, the OSD successfully came up on `/dev/sda`.

## Resolution
`osd.0` was fully reprovisioned on `/dev/sda`, re-added to CRUSH under `mainframe`, marked in, and allowed to backfill.

## Validation
- `ceph -s` showed:
  - `5 osds: 5 up, 5 in`
  - active recovery/backfill progressing
- `ceph osd tree` showed `osd.0` back under host `mainframe`
- `HEALTH_OK` was observed after recovery completed

## Follow-Up Tasks
- Confirm persistent activation of the OSD after reboot
- Review why the wrong device was selected during the first rebuild attempt
- Confirm all OSD systemd activation units are enabled on every OSD node
- Add recovery notes to runbook to avoid reusing stale masked units

## Lessons Learned
- Always verify the target disk with `lsblk` and `ceph-volume lvm list` before recreating an OSD.
- A masked `ceph-osd@<id>` unit can silently block a correct rebuild.
- Stale Ceph LVM metadata on a reused disk must be removed before reprovisioning.
- Unsetting `noout` after recovery is important so Ceph can rebalance normally.

---

# Restore `mainframe` Monitor and Rehome Ceph Manager Services

## Summary
After OSD recovery, work shifted to restoring `mon.mainframe`, correcting Ceph monitor configuration issues, and moving the active Ceph manager role to `pve1` with standby managers on the remaining nodes.

## Environment
- Same Ceph Reef cluster
- Monitor IPs:
  - `mainframe` = `192.168.16.11`
  - `pve1` = `192.168.16.12`
  - `pve2` = `192.168.16.13`
  - `pve3` = `192.168.16.14`
  - `pve4` = `192.168.16.15`
- Shared Ceph config file: `/etc/pve/ceph.conf`

## Problem
`mon.mainframe` was absent from quorum and failed to recreate cleanly. At the same time, Ceph manager placement needed cleanup so `pve1` would become active and the rest would operate as standbys.

## Symptoms
- `pveceph mon create` returned:
  - `monitor address '192.168.16.11' already in use`
- `ceph-mon@mainframe` was failed/inactive
- `/etc/pve/ceph.conf` contained stale monitor-related configuration
- `public_network` and `cluster_network` were set to host IP form (`192.168.16.11/24`) rather than subnet form
- `pveceph mgr create` initially created a manager on `pve1`, but earlier attempts showed missing keyring and no active mgr
- Ceph GUI/manager views later appeared to show duplicated or stale entries

## Actions Taken
1. Verified monitor failure and cluster monitor state.
   ```bash
   systemctl status ceph-mon@mainframe --no-pager
   ceph mon dump
   ceph -s
   timedatectl
   getent hosts mainframe
   ```
   Purpose: confirm monitor identity, address resolution, and quorum state.

2. Attempted monitor creation through Proxmox helper.
   ```bash
   pveceph mon create
   pveceph mon create --mon-address 192.168.16.11
   ```
   Purpose: restore `mon.mainframe` using the supported Proxmox workflow.

3. Inspected and corrected Ceph config.
   ```bash
   grep -nE 'mon host|mon initial members|192\.168\.16\.11|mainframe' /etc/pve/ceph.conf
   sed -ri 's#^( *cluster_network *= *).*#\1192.168.16.0/24#' /etc/pve/ceph.conf
   sed -ri 's#^( *public_network *= *).*#\1192.168.16.0/24#'  /etc/pve/ceph.conf
   ```
   Purpose: fix invalid network definitions and remove conflicting state.

4. Removed stale monitor stanza and stale backup state from shared config.
   ```bash
   awk '
     BEGIN{skip=0}
     /^\[mon\.mainframe\]/{skip=1}
     skip && NF==0{skip=0; next}
     !skip
   ' /etc/pve/ceph.conf > /etc/pve/ceph.conf.new && mv /etc/pve/ceph.conf.new /etc/pve/ceph.conf
   ```
   Purpose: remove stale monitor configuration that interfered with monitor recreation.

5. Rebuilt monitor membership directly by editing monmap state and starting the service.
   ```bash
   ceph mon getmap -o /tmp/monmap
   monmaptool --add mainframe 192.168.16.11 /tmp/monmap
   systemctl enable ceph-mon@mainframe
   systemctl start ceph-mon@mainframe
   ceph mon dump
   ceph -s
   ```
   Purpose: restore `mon.mainframe` as a valid quorum member.

6. Created and stabilized Ceph manager on `pve1`.
   ```bash
   pveceph mgr create
   systemctl enable --now ceph-mgr@pve1
   systemctl status ceph-mgr@pve1 --no-pager
   journalctl -u ceph-mgr@pve1 -e --no-pager
   ceph -s
   ceph mgr dump -f json-pretty | egrep '"active_name"|"active_addr"'
   ceph mgr services
   ```
   Purpose: ensure `pve1` became the active manager.

7. Created standby managers on the remaining nodes.
   ```bash
   pveceph mgr create
   systemctl status ceph-mgr@pve2 --no-pager
   ceph mgr dump | egrep 'active_name|standbys'
   ```
   Similar actions were taken on `pve3`, `pve4`, and `mainframe`.
   Purpose: give the cluster manager failover capacity.

8. Removed stale local monitor backup directory after UI duplication concerns.
   ```bash
   ls -1 /var/lib/ceph/mon/
   systemctl list-units 'ceph-mon@*'
   rm -rf /var/lib/ceph/mon/ceph-mainframe.bak.1758198197
   ceph -s
   ceph mon dump
   ```
   Purpose: eliminate local stale state that could confuse UI views.

## Key Findings
- The shared `/etc/pve/ceph.conf` had invalid network lines using a host address instead of subnet notation.
- A stale `mon.mainframe` stanza and/or local backup directory contributed to repeated monitor creation problems.
- `pveceph mon create` did not accept `--mon-id` in this environment.
- `pve1` became active manager successfully after its keyring/service state was corrected.
- Standby managers were eventually visible: `pve4`, `pve2`, `pve3`, and `mainframe`.

## Resolution
`mon.mainframe` was restored to quorum, `pve1` became the active Ceph manager, and standby managers were present on the other nodes.

## Validation
- `ceph -s` showed:
  - `mon: 5 daemons, quorum pve1,pve3,pve2,pve4,mainframe`
  - `mgr: pve1(active, since …), standbys: pve4, pve2, pve3, mainframe`
- `ceph mgr services` showed Prometheus on `pve1`
- `ceph mon dump` listed all five monitor endpoints

## Follow-Up Tasks
- Periodically review `/etc/pve/ceph.conf` for stale monitor sections after manual recovery
- Keep `pve1` as active manager unless there is a reason to rebalance roles
- Avoid mixing Proxmox helper methods and manual monitor surgery unless required

## Lessons Learned
- On Proxmox, monitor state problems often involve both cluster config and local monitor store state.
- `public_network` and `cluster_network` must be subnet definitions, not individual host IPs.
- Standby managers are useful even if they appear idle; they reduce failover time.
- A stale `.bak` monitor directory can be harmless but confusing during troubleshooting.

---

# Recover `mon.mainframe` From Repeated Crashes and Repair an Inconsistent PG

## Summary
After the monitor was restored, `mon.mainframe` later began crashing repeatedly and fell out of quorum. At the same time, Ceph reported one inconsistent placement group and scrub errors. Work focused on rebuilding the local monitor store from the live monmap/keyring, fixing ownership issues, and repairing the damaged PG.

## Environment
- Same Proxmox/Ceph Reef cluster
- `mainframe` monitor address: `192.168.16.11`
- Reported damaged PG: `2.1a`
- Acting set observed during inconsistency: `[1,2,3]`

## Problem
`mon.mainframe` repeatedly crashed and stayed out of quorum. Cluster health also showed scrub errors and an inconsistent PG.

## Symptoms
- `HEALTH_WARN: 1/5 mons down, quorum pve1,pve3,pve2,pve4`
- `mon.mainframe ... is down (out of quorum)`
- `HEALTH_ERR: 2 scrub errors`
- `HEALTH_ERR: Possible data damage: 1 pg inconsistent`
- `pg 2.1a is active+clean+inconsistent`
- Journal logs showed Ceph monitor assertion failures:
  - `MonitorDBStore.h: 615: FAILED ceph_assert(r >= 0)`
  - repeated `DeleteCF(...)` lines
- Later logs also showed:
  - `error opening mon data directory ... Permission denied`

## Actions Taken
1. Verified cluster health and monitor crash history.
   ```bash
   ceph -s
   ceph mon dump | grep mainframe
   journalctl -u ceph-mon@mainframe -b -e
   ceph crash ls-new
   ```
   Purpose: confirm that the monitor was out of quorum and gather crash evidence.

2. Exported the live monmap and monitor key from a healthy quorum member, then copied them to `mainframe`.
   ```bash
   ceph mon getmap -o /tmp/monmap
   ceph auth get mon. -o /tmp/mon.keyring
   scp /tmp/monmap /tmp/mon.keyring mainframe:/tmp/
   ```
   Purpose: use current cluster monitor metadata to rebuild the broken local monitor store.

3. Stopped the broken local monitor and parked the old monitor directory.
   ```bash
   systemctl stop ceph-mon@mainframe
   mv /var/lib/ceph/mon/ceph-mainframe /var/lib/ceph/mon/ceph-mainframe.bad.$(date +%s)
   ```
   Purpose: preserve the broken monitor store while creating a fresh one.

4. Rebuilt the monitor store from the live monmap and keyring.
   ```bash
   ceph-mon -i mainframe --mkfs --monmap /tmp/monmap --keyring /tmp/mon.keyring
   ```
   Purpose: create a new monitor database consistent with the current quorum.

5. Fixed ownership and permissions after `Permission denied` errors.
   ```bash
   install -d -o ceph -g ceph -m 0750 /var/lib/ceph/mon/ceph-mainframe
   chown -R ceph:ceph /var/lib/ceph/mon/ceph-mainframe
   find /var/lib/ceph/mon/ceph-mainframe -type f -name keyring -exec chmod 0600 {} \;
   find /var/lib/ceph/mon/ceph-mainframe -type d -exec chmod 0750 {} \;
   chgrp ceph /var/lib/ceph /var/lib/ceph/mon || true
   chmod 0755 /var/lib/ceph /var/lib/ceph/mon || true
   lsattr -R /var/lib/ceph/mon/ceph-mainframe
   ```
   Purpose: ensure the service account could open the rebuilt monitor store.

6. Started the monitor again and checked quorum.
   ```bash
   systemctl start ceph-mon@mainframe
   ps -o user,group,cmd -C ceph-mon
   ceph mon dump | egrep 'quorum|mainframe'
   ceph -s
   ```
   Purpose: verify that the rebuilt monitor joined quorum successfully.

7. Archived old crash records once the monitor was healthy.
   ```bash
   ceph crash archive-all
   ceph crash ls-new
   ```
   Purpose: clear historical crash warnings from cluster health.

8. Investigated and repaired the inconsistent PG.
   ```bash
   ceph health detail
   ceph pg scrub 2.1a
   ceph pg deep-scrub 2.1a
   ceph pg repair 2.1a
   watch -n5 'ceph health detail'
   ```
   Purpose: rescrub and repair the inconsistent placement group.

## Key Findings
- `mon.mainframe` was failing in monitor DB cleanup during startup, then later also failed because of local file permissions.
- Rebuilding the local monitor store from the live quorum monmap/keyring resolved the corrupt local monitor state.
- The inconsistent PG was repairable through normal Ceph scrub/deep-scrub/repair operations.
- `ceph crash archive-all` cleared health warnings tied only to historical crashes.

## Resolution
`mon.mainframe` was rebuilt from the live monitor map and keyring, proper permissions were restored, the monitor rejoined quorum, and PG `2.1a` was scrubbed and repaired until cluster health returned to OK.

## Validation
- `ceph -s` returned to:
  - `mon: 5 daemons, quorum pve1,pve3,pve2,pve4,mainframe`
  - `HEALTH_OK`
- `ceph quorum_status` showed all five monitor names in quorum
- The damaged PG progressed from `active+clean+inconsistent` to healthy after repair
- `ceph crash ls-new` no longer showed new crash entries after archiving and successful service restart

## Follow-Up Tasks
- Monitor `mon.mainframe` for repeated DB corruption after abrupt shutdowns
- Consider checking storage/media health on `mainframe` if monitor crashes recur
- Keep exported monmap/key recovery steps in the Ceph runbook
- Review UPS/power-loss strategy if abrupt outages are contributing to corruption

## Lessons Learned
- A monitor can be present in the monmap but still fail locally due to store corruption or permissions.
- Rebuilding a local monitor store from the live quorum monmap is safer than guessing at stale local metadata.
- `Permission denied` after a manual rebuild is often just ownership/mode mismatch.
- Historical crash warnings can hide the fact that the cluster is currently healthy; archive them after validating recovery.

---

# Recover `osd.0`, Reactivate `osd.4`, and Return Cluster to `HEALTH_OK`

## Summary
Following the monitor and PG repair work, two OSD issues remained: `osd.0` on `mainframe` suffered BlueStore/RocksDB corruption after a disruptive event, and `osd.4` on `pve4` was down and weighted out. Work focused on recovering `osd.0`, reactivating `osd.4`, re-enabling all OSD daemons, and clearing the final `noout` flag.

## Environment
- `osd.0` on `mainframe`, backed by `/dev/sda`
- `osd.4` on `pve4`, backed by `/dev/nvme0n1`
- BlueStore block device examples:
  - `osd.0` LV under `ceph-569333fc-...`
  - `osd.4` LV under `ceph-784f4bee-...`

## Problem
After power-related or abrupt recovery events, `osd.0` stayed down with BlueStore database corruption. `osd.4` was also down and reweight `0`.

## Symptoms
- `ceph osd tree` showed only 3 or 4 OSDs up depending on stage
- `systemctl status ceph-osd@0` repeatedly failed
- Logs for `osd.0` showed:
  - `rocksdb: Corruption: SST file is ahead of WALs in CF O-0`
  - `OSD:init: unable to mount object store`
  - `ERROR: osd init failed: (5) Input/output error`
- `ceph-bluestore-tool fsck` and `repair` both failed on `osd.0`
- `osd.4` on `pve4` existed in Ceph volume metadata but was not active

## Actions Taken
1. Checked which OSDs were up and inspected the damaged PG after repair work.
   ```bash
   ceph osd tree
   ceph osd stat
   ceph osd df
   ceph pg 2.1a query | jq '.state, .stat_sum'
   ```
   Purpose: determine remaining storage degradation.

2. Ensured OSD systemd targets and ceph-volume activators were enabled on each node.
   ```bash
   systemctl enable ceph-osd.target
   systemctl list-unit-files 'ceph-volume@lvm*' --no-legend | awk '{print $1}' | xargs -r -n1 systemctl enable
   systemctl list-units 'ceph-volume@lvm*' --no-legend | awk '{print $1}' | xargs -r -n1 systemctl start
   ceph-volume lvm activate --all
   ```
   Purpose: restore automatic OSD activation after reboot/failure.

3. Investigated and attempted to repair `osd.0`.
   ```bash
   systemctl stop ceph-osd@0
   ceph osd out 0
   ls -l /var/lib/ceph/osd/ceph-0/block
   lsblk -o NAME,SIZE,TYPE,MOUNTPOINT
   ceph-bluestore-tool fsck --path /var/lib/ceph/osd/ceph-0 --log-level 20
   ceph-bluestore-tool repair --path /var/lib/ceph/osd/ceph-0 --log-level 20
   ```
   Purpose: confirm BlueStore block path and test whether the DB could be recovered in place.

4. Verified service state and log output for `osd.0`.
   ```bash
   systemctl status ceph-osd@0 -n50 --no-pager
   journalctl -u ceph-osd@0 -b --no-pager | tail -200
   ```
   Purpose: identify exact startup failure mode.

5. Later restarted `osd.0` successfully and confirmed it rejoined the cluster.
   ```bash
   systemctl status 'ceph-osd@*' --no-pager
   ceph osd tree
   ceph osd stat
   ceph -s
   ```
   Purpose: validate that `osd.0` returned to `up` and recovery began.

   **Important note:** the chat log shows the failed diagnostics and then later a successful `osd.0` startup, but it does not include a single explicit final corrective command between those states. The successful recovery is a fact; the exact final repair/rebuild step is not fully captured in the transcript.

6. Reactivated `osd.4` on `pve4`.
   ```bash
   systemctl enable ceph-osd.target
   ceph-volume lvm list
   ceph-volume lvm activate 4 || ceph-volume lvm activate --all
   systemctl status ceph-osd@4 -n50 --no-pager
   ceph osd in 4
   ceph osd reweight 4 1.0
   ```
   Purpose: re-enable the existing OSD and restore it to service.

7. Verified full-cluster storage recovery and unset `noout`.
   ```bash
   ceph -s
   ceph pg stat
   ceph osd unset noout
   ceph osd tree
   ceph osd df
   ```
   Purpose: confirm all OSDs were up/in and that placement groups returned to `active+clean`.

## Key Findings
- `osd.0` failure was BlueStore DB corruption, not simple service-state drift.
- `ceph-bluestore-tool fsck` and `repair` were not sufficient during the failed state that was captured.
- `osd.4` was recoverable by activating the existing ceph-volume metadata and reweighting it.
- Once both OSDs were restored and `noout` was cleared, the cluster returned to normal placement.

## Resolution
`osd.0` was ultimately brought back online on `mainframe`, `osd.4` was reactivated on `pve4`, both OSDs were marked in and weighted correctly, and the cluster returned to `5 osds: 5 up, 5 in`.

## Validation
- `ceph -s` showed:
  - `health: HEALTH_OK`
  - `osd: 5 osds: 5 up, 5 in`
  - `pgs: 33 active+clean`
- `ceph osd tree` showed all five OSDs up under the expected hosts
- `ceph osd df` showed data redistributed across all OSDs
- `ceph osd unset noout` succeeded

## Follow-Up Tasks
- Capture a cleaner future procedure for BlueStore corruption triage vs. rebuild
- Confirm OSD auto-activation persists after reboots on all five nodes
- Review why `osd.0` experienced RocksDB corruption
- Consider using UPS protection or shutdown sequencing improvements if abrupt outage risk remains

## Lessons Learned
- BlueStore/RocksDB corruption can persist even when volume metadata and block symlinks look normal.
- `ceph-volume lvm activate --all` is useful for restoring OSD runtime state after cluster disruption.
- `noout` is helpful during recovery but should be removed once the cluster is stable.
- A healthy monitor quorum and active manager do not guarantee all OSDs are actually serving data.

---

# Post-Recovery Hardening for `mainframe` OSD and General Ceph Stability

## Summary
After the cluster returned to `HEALTH_OK`, work focused on low-risk Ceph hardening for `mainframe` and cluster-wide OSD behavior, including scrub scheduling, memory limits, recovery pacing, monitor compaction, SMART review, and queue/scheduler tuning.

## Environment
- `mainframe` OSD disk identified as Samsung SSD 870 EVO 500GB
- SMART tools already installed: `smartmontools 7.3-pve1`
- OSD scheduler tuning targeted the real block disk behind `/dev/dm-0`, which mapped to `/dev/sda`
- Ceph manager active on `pve1`
- mClock scheduler behavior implicitly present on Reef

## Problem
The goal was to reduce the chance of repeat instability on `mainframe`, keep recovery less disruptive, and document what hardening was useful versus what Ceph Reef/mClock would ignore.

## Symptoms
- Need for gentler backfill/recovery settings after recent failures
- Need to verify SSD health on the `mainframe` OSD disk
- `ceph config get osd osd_recovery_max_active` kept returning `0` even after setting it to `1`
- Attempting `ceph mon compact` directly failed due to incorrect command form
- A udev rule line was mistakenly pasted directly into the shell and failed as a command

## Actions Taken
1. Checked the OSD block path and the backing disk.
   ```bash
   readlink -f /var/lib/ceph/osd/ceph-0/block
   lsblk -no pkname /dev/dm-0
   ```
   Purpose: find the real disk behind the BlueStore LV.

2. Applied temporary I/O queue tuning for the SSD.
   ```bash
   echo none | tee /sys/block/sda/queue/scheduler
   echo 0    | tee /sys/block/sda/queue/add_random
   ```
   Purpose: use SSD-appropriate queue settings and reduce unnecessary entropy accounting.

3. Ran SMART baseline checks on `/dev/sda`.
   ```bash
   apt-get install -y smartmontools
   smartctl -x /dev/sda
   ```
   Purpose: verify that the Samsung SSD backing `osd.0` did not show obvious media failure.

4. Set cluster-wide OSD pacing and memory knobs.
   ```bash
   ceph config set osd osd_max_backfills 1
   ceph config set osd osd_recovery_max_active 1
   ceph config set osd osd_recovery_max_single_start 1
   ceph config set osd osd_memory_target 1073741824
   ceph config set osd bluestore_cache_autotune true
   ceph config set osd bluestore_throttle_bytes 268435456
   ceph config set osd osd_scrub_begin_hour 1
   ceph config set osd osd_scrub_end_hour 7
   ceph config set osd osd_scrub_auto_repair true
   ```
   Purpose: reduce recovery pressure and define an off-hours scrub window.

5. Compacted all monitors correctly.
   ```bash
   ceph quorum_status -f json-pretty | jq -r '.quorum_names[]'
   ceph tell mon.* compact
   ```
   Purpose: compact monitor RocksDB stores using the correct Reef-compatible syntax.

6. Queried config values and discovered `osd_recovery_max_active` remained `0` at runtime.
   ```bash
   ceph config get osd osd_max_backfills
   ceph config get osd osd_recovery_max_active
   ceph tell osd.* config get osd_recovery_max_active
   ceph tell osd.* config get osd_max_backfills
   ```
   Purpose: determine whether the config database value matched effective daemon behavior.

## Key Findings
- SMART data for the Samsung 870 EVO looked healthy:
  - SMART overall self-assessment passed
  - no reallocated sectors
  - no uncorrectable errors
  - no CRC errors
- `ceph tell mon.* compact` was the correct monitor compaction syntax in this environment.
- `osd_max_backfills=1` applied successfully to all OSDs.
- `osd_recovery_max_active` still showed `0` at runtime on all OSDs, which was later interpreted as normal mClock behavior on Reef rather than a failed configuration push.
- The attempted raw udev rule paste failed because it was shell syntax, not a shell command.

## Resolution
Main hardening changes were applied successfully:
- `osd_max_backfills=1`
- `osd_memory_target=1GiB`
- `bluestore_cache_autotune=true`
- scrub window and auto-repair settings
- monitor compaction completed
- SMART baseline confirmed the `mainframe` OSD SSD did not show obvious failure indicators

`osd_recovery_max_active` was left under the default mClock model rather than forcing legacy behavior.

## Validation
- `ceph tell osd.* config get osd_max_backfills` returned `1` across the cluster
- Monitor compaction completed successfully on all monitors
- SMART output on `/dev/sda` showed no critical failure counters
- Cluster remained healthy after the changes

## Follow-Up Tasks
- Create a persistent udev rule for SSD queue tuning rather than relying only on `/sys` writes
- Decide whether to stay with Reef/mClock defaults or explicitly override them cluster-wide
- Consider running an extended SMART self-test on `/dev/sda`
- Revisit recovery tuning once the cluster has been stable for a longer period

## Lessons Learned
- Not every Ceph config key that can be set will necessarily be honored the way older runbooks expect on newer releases.
- Reef/mClock can make legacy recovery knobs appear unset or ineffective even when recovery pacing is still controlled.
- SSD queue tuning should be made persistent with a udev rule, not by pasting udev syntax into the shell.
- SMART review is useful for ruling out obvious hardware failure before assuming all corruption is software-side.

---

# Command Reference

## Command
```bash
ceph osd stat
```

### What it does
Shows how many OSDs exist and how many are up/in.

### Why it was used
To confirm cluster storage availability during OSD failure and recovery.

### Expected result
A healthy cluster would show all OSDs up and in.

### What success or failure indicates
- Success: expected OSD counts and status
- Failure/degradation: missing or down OSDs, often requiring service or disk investigation

---

## Command
```bash
ceph osd tree
```

### What it does
Displays the CRUSH hierarchy of OSDs by host and root.

### Why it was used
To confirm `osd.0` and later `osd.4` were attached to the correct hosts and were up/down/in/out as expected.

### Expected result
Each OSD should appear under the proper host bucket with expected status.

### What success or failure indicates
- Success: correct OSD placement and CRUSH structure
- Failure: missing host bucket, down OSD, or bad weight/reweight state

---

## Command
```bash
ceph health detail
```

### What it does
Prints detailed health checks and affected objects/PGs.

### Why it was used
To identify monitor crashes, scrub errors, inconsistent PGs, and crash warnings.

### Expected result
`HEALTH_OK` or detailed reasons for non-OK health.

### What success or failure indicates
- Success: cluster is healthy
- Failure: follow the named health checks to the affected service or PG

---

## Command
```bash
systemctl status ceph-osd@0 --no-pager
journalctl -u ceph-osd@0 -n 300 --no-pager
```

### What it does
Checks service state and recent logs for `osd.0`.

### Why it was used
To diagnose why `osd.0` would not start.

### Expected result
Active service and clean startup logs.

### What success or failure indicates
- Success: service is running
- Failure: logs reveal missing directories, BlueStore errors, permission issues, or DB corruption

---

## Command
```bash
ceph-volume lvm list
ceph-volume lvm list /dev/sda
```

### What it does
Shows Ceph OSD metadata stored in LVM on local disks.

### Why it was used
To identify where OSD metadata existed and whether disks were already “prepared.”

### Expected result
OSD IDs, FSIDs, block LVs, and backing devices.

### What success or failure indicates
- Success: confirms existing Ceph volume layout
- Failure or unexpected output: indicates stale metadata or wrong device selection

---

## Command
```bash
ceph-bluestore-tool quick-fix --path /var/lib/ceph/osd/ceph-0
```

### What it does
Attempts a lightweight BlueStore metadata repair.

### Why it was used
As a non-destructive first repair step before full rebuild.

### Expected result
Minor BlueStore issues corrected.

### What success or failure indicates
- Success: OSD may start without rebuild
- Failure: likely needs deeper repair or reprovisioning

### Risk
Moderate. Safer than full rebuild, but still a repair operation on object store metadata.

---

## Command
```bash
ceph-volume lvm create --bluestore --data /dev/sda
```

### What it does
Creates a new BlueStore OSD on the specified device.

### Why it was used
To reprovision `osd.0` on the intended disk.

### Expected result
A new OSD directory, block LV, and activated OSD service.

### What success or failure indicates
- Success: OSD can be brought into cluster
- Failure: stale metadata, masked service, or wrong disk state may block creation

### Risk
High. This destroys prior data on the target device.

---

## Command
```bash
ceph osd purge 0 --yes-i-really-mean-it
```

### What it does
Removes the OSD from cluster maps and deletes related auth entries.

### Why it was used
To cleanly remove broken `osd.0` before reprovisioning.

### Expected result
OSD is gone from cluster metadata.

### What success or failure indicates
- Success: safe to rebuild/readd
- Failure: stale CRUSH/auth references may remain

### Risk
High. This is destructive cluster metadata removal.

---

## Command
```bash
ceph-volume lvm zap /dev/nvme0n1 --destroy
ceph-volume lvm zap /dev/sda --destroy
```

### What it does
Erases Ceph/LVM metadata from the target device.

### Why it was used
To remove mistaken or stale OSD state before rebuilding.

### Expected result
Disk no longer appears as a prepared Ceph OSD device.

### What success or failure indicates
- Success: device is reusable
- Failure: active mounts/LVs may still exist

### Risk
High. This destroys Ceph metadata and LVM structures on the target disk.

---

## Command
```bash
systemctl unmask ceph-osd@0
systemctl daemon-reload
```

### What it does
Removes a systemd mask and reloads unit definitions.

### Why it was used
A masked `ceph-osd@0` prevented successful OSD recreation.

### Expected result
The service can be enabled/started again.

### What success or failure indicates
- Success: later creation/activation can proceed
- Failure: stale systemd state remains

---

## Command
```bash
ceph osd crush add-bucket mainframe host
ceph osd crush move mainframe root=default
ceph osd crush add osd.0 0.45479 host=mainframe
ceph osd crush set-device-class ssd osd.0
```

### What it does
Creates/positions a host bucket in CRUSH, adds the OSD, and assigns device class.

### Why it was used
To restore `mainframe` and `osd.0` to the CRUSH hierarchy after rebuild.

### Expected result
OSD appears under the correct host and root.

### What success or failure indicates
- Success: OSD participates in placement correctly
- Failure: data placement and balancing may be wrong

### Risk
Moderate. Incorrect CRUSH edits can misplace data.

---

## Command
```bash
ceph osd in 0
ceph osd reweight 0 1.0
ceph osd unset noout
```

### What it does
Marks the OSD back in, restores full reweight, and clears the noout flag.

### Why it was used
To let the cluster rebalance onto the restored OSD.

### Expected result
Backfill/remap starts and then clears.

### What success or failure indicates
- Success: OSD resumes normal cluster duty
- Failure: OSD may still be down or blocked

---

## Command
```bash
pveceph mon create
pveceph mon destroy mainframe
```

### What it does
Proxmox helper commands to create or remove Ceph monitor services on a node.

### Why it was used
To restore `mon.mainframe` using the Proxmox-supported workflow.

### Expected result
A local monitor directory and active monitor service.

### What success or failure indicates
- Success: monitor joins monmap/quorum
- Failure: stale config, conflicting IP, or local store problems remain

---

## Command
```bash
ceph mon dump
ceph mon getmap -o /tmp/monmap
ceph auth get mon. -o /tmp/mon.keyring
```

### What it does
Inspects monitor membership, exports the monitor map, and exports monitor auth material.

### Why it was used
To rebuild a broken local monitor store from healthy cluster state.

### Expected result
A current monmap and valid monitor keyring.

### What success or failure indicates
- Success: suitable inputs for monitor rebuild
- Failure: quorum or auth access problems

---

## Command
```bash
ceph-mon -i mainframe --mkfs --monmap /tmp/monmap --keyring /tmp/mon.keyring
```

### What it does
Initializes a local monitor store from a supplied monmap and keyring.

### Why it was used
To replace the broken `mainframe` monitor database with a clean one.

### Expected result
A valid local monitor store under `/var/lib/ceph/mon/ceph-mainframe`.

### What success or failure indicates
- Success: monitor can start and join quorum
- Failure: permissions, bad monmap, or stale local state remain

### Risk
High. This replaces the local monitor store.

---

## Command
```bash
systemctl enable --now ceph-mgr@pve1
ceph mgr dump
ceph mgr services
```

### What it does
Starts a Ceph manager and shows active/standby manager details and exported services.

### Why it was used
To move active manager duties to `pve1` and validate standby managers.

### Expected result
`pve1` becomes active, others become standbys, and services like Prometheus appear.

### What success or failure indicates
- Success: healthy manager control plane
- Failure: missing keyrings, service startup failure, or no active mgr

---

## Command
```bash
ceph crash ls-new
ceph crash archive-all
```

### What it does
Lists new crash records and archives them.

### Why it was used
To review repeated monitor/OSD crashes and clear historical crash warnings after recovery.

### Expected result
`ls-new` shows only unarchived crashes; after archiving it should be empty or reduced.

### What success or failure indicates
- Success: warnings can be reduced after actual repair
- Failure: continuing crashes will recreate entries

---

## Command
```bash
ceph pg scrub 2.1a
ceph pg deep-scrub 2.1a
ceph pg repair 2.1a
```

### What it does
Forces a scrub, deep scrub, and repair of the named placement group.

### Why it was used
To fix `pg 2.1a` after Ceph reported it as inconsistent.

### Expected result
PG transitions through scrub/repair and returns to clean.

### What success or failure indicates
- Success: inconsistency resolved
- Failure: deeper data corruption may remain

### Risk
Moderate. Repair changes cluster metadata/object state and should be used when inconsistency is confirmed.

---

## Command
```bash
ceph-volume lvm activate --all
```

### What it does
Activates all locally known Ceph OSDs from ceph-volume metadata.

### Why it was used
To restore OSD runtime activation after failures or reboot-like conditions.

### Expected result
Relevant `ceph-osd@<id>` services are enabled/started.

### What success or failure indicates
- Success: OSD runtime state restored
- Failure: underlying block path, metadata, or service state still broken

---

## Command
```bash
ceph-bluestore-tool fsck --path /var/lib/ceph/osd/ceph-0 --log-level 20
ceph-bluestore-tool repair --path /var/lib/ceph/osd/ceph-0 --log-level 20
```

### What it does
Runs BlueStore integrity checks and attempted repair.

### Why it was used
To investigate `osd.0` RocksDB corruption.

### Expected result
Repairable corruption would be corrected.

### What success or failure indicates
- Success: OSD may mount again
- Failure: DB corruption may require rebuild or stronger recovery action

### Risk
Moderate to high. Repair operations touch BlueStore metadata and should be run carefully.

---

## Command
```bash
ceph-volume lvm activate 4 || ceph-volume lvm activate --all
ceph osd in 4
ceph osd reweight 4 1.0
```

### What it does
Activates `osd.4`, marks it in, and restores full cluster weight.

### Why it was used
To bring `pve4` storage back into service.

### Expected result
`osd.4` becomes `up` and `in`.

### What success or failure indicates
- Success: cluster capacity and redundancy are restored
- Failure: local OSD metadata or service startup issues remain

---

## Command
```bash
smartctl -x /dev/sda
```

### What it does
Prints extended SMART health and device statistics.

### Why it was used
To verify SSD health on the disk backing `osd.0`.

### Expected result
Healthy SMART status, no media or CRC errors.

### What success or failure indicates
- Success: no obvious hardware fault
- Failure: disk/media issues may explain corruption or instability

---

## Command
```bash
ceph tell mon.* compact
```

### What it does
Requests RocksDB compaction on all monitors.

### Why it was used
To perform light monitor database maintenance after monitor recovery.

### Expected result
Each monitor reports compaction completion.

### What success or failure indicates
- Success: monitor DB compaction finished
- Failure: monitor command syntax or monitor availability issue

---

## Command
```bash
ceph config set osd osd_max_backfills 1
ceph config set osd osd_memory_target 1073741824
ceph config set osd bluestore_cache_autotune true
ceph config set osd bluestore_throttle_bytes 268435456
ceph config set osd osd_scrub_begin_hour 1
ceph config set osd osd_scrub_end_hour 7
ceph config set osd osd_scrub_auto_repair true
```

### What it does
Writes cluster-wide Ceph configuration overrides for OSD runtime behavior.

### Why it was used
To reduce recovery disruption, cap OSD memory, and move scrub activity into overnight hours.

### Expected result
All OSDs honor the new settings unless overridden by newer scheduler behavior.

### What success or failure indicates
- Success: values appear in config queries and affect daemon behavior where supported
- Failure: runtime output may still show defaults if a different subsystem controls behavior

---

## Command
```bash
ceph tell osd.* config get osd_max_backfills
ceph tell osd.* config get osd_recovery_max_active
```

### What it does
Queries effective runtime config values from every OSD daemon.

### Why it was used
To confirm whether cluster-wide recovery knobs were actually active.

### Expected result
Consistent values across all OSDs.

### What success or failure indicates
- Success: settings applied as intended
- Failure or unexpected values: scheduler behavior or unsupported legacy settings may be in play

---

## Command
```bash
echo none | tee /sys/block/sda/queue/scheduler
echo 0    | tee /sys/block/sda/queue/add_random
```

### What it does
Applies runtime block queue tuning to the SSD device.

### Why it was used
To use SSD-friendly scheduler behavior and reduce unnecessary entropy accounting.

### Expected result
Queue settings change immediately until reboot.

### What success or failure indicates
- Success: kernel accepts the values
- Failure: wrong device name or unsupported scheduler

### Risk
Low to moderate. Runtime tuning only, but wrong device targeting can affect unrelated storage behavior.

---

## Command
```bash
systemctl enable ceph-osd.target
systemctl enable ceph-osd@4
systemctl enable ceph-volume@lvm-4-6612f47f-76be-4dc5-8b24-3332023e28db
```

### What it does
Ensures OSD targets and local ceph-volume activation units are enabled across reboots.

### Why it was used
To make OSD activation persist after node restart or service disruption.

### Expected result
Required units are enabled in systemd.

### What success or failure indicates
- Success: OSDs are more likely to auto-start after reboot
- Failure: cluster may come back partially degraded after restart

---

## Command
```bash
watch -n3 'ceph -s; echo; ceph pg stat'
```

### What it does
Continuously monitors cluster health and PG state.

### Why it was used
To watch recovery, remapping, and final convergence to `active+clean`.

### Expected result
Recovery counters decrease until all PGs are clean.

### What success or failure indicates
- Success: backfill and remap complete
- Failure: recovery stalls or health errors persist
