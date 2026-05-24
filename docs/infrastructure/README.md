# Infrastructure Documentation

Real homelab systems, operational notes, incidents, and runbooks.

## Ordering Rule

Documents are ordered by logical event flow inside each category.

## Date Rule

Dates are removed from filenames, visible headings, indexes, generated metadata, and runbook body content.

## Categories

- [Architecture](architecture/)
- [Compute](compute/)
- [Networking](networking/)
- [Storage](storage/)
- [Containers & Apps](containers-apps/)
- [Automation](automation/)
- [Security](security/)
- [Monitoring & Operations](monitoring-operations/)
- [Troubleshooting & Incidents](troubleshooting-incidents/)
- [Runbooks](runbooks/)

## Source Index

### Architecture

- [proxmox-traefik-opnsense-ha-runbook.md](architecture/proxmox-traefik-opnsense-ha-runbook.md)

### Compute

- [home-assistant-os-proxmox-ceph-vm-deployment.md](compute/home-assistant-os-proxmox-ceph-vm-deployment.md)
- [debian-docker-vm-runbook.md](compute/debian-docker-vm-runbook.md)
- [homelab-vm100-rebuild-restore-runbook.md](compute/homelab-vm100-rebuild-restore-runbook.md)

### Networking

- [att-fiber-opnsense-outage-runbook.md](networking/att-fiber-opnsense-outage-runbook.md)
- [opnsense-web-gui-documentation-and-runbook.md](networking/opnsense-web-gui-documentation-and-runbook.md)
- [opnsense-lan-ip-dhcp-static-device-runbook.md](networking/opnsense-lan-ip-dhcp-static-device-runbook.md)
- [opnsense-opt2-lan-runbook.md](networking/opnsense-opt2-lan-runbook.md)
- [opnsense-lan-instability-storm-control-runbook.md](networking/opnsense-lan-instability-storm-control-runbook.md)
- [wireguard-ec2-proxmox-lxc-homelab-remote-access.md](networking/wireguard-ec2-proxmox-lxc-homelab-remote-access.md)

### Storage

- [truenas-vm-zfs-hba-planning.md](storage/truenas-vm-zfs-hba-planning.md)
- [ceph-mainframe-osd-mon-mgr-recovery-runbook.md](storage/ceph-mainframe-osd-mon-mgr-recovery-runbook.md)
- [vm100-ceph-gluetun-troubleshooting-runbook-15.md](storage/vm100-ceph-gluetun-troubleshooting-runbook-15.md)
- [ceph-monitor-crash-loop-mainframe.md](storage/ceph-monitor-crash-loop-mainframe.md)
- [proxmox-ha-live-migration-ceph-vm-state.md](storage/proxmox-ha-live-migration-ceph-vm-state.md)
- [vm100-docker-nas-offen-recovery-runbook.md](storage/vm100-docker-nas-offen-recovery-runbook.md)

### Containers & Apps

- [gluetun-corrupted-servers-permissions-runbook.md](containers-apps/gluetun-corrupted-servers-permissions-runbook.md)
- [docker-apps-offen-restore-gluetun-recovery-runbook.md](containers-apps/docker-apps-offen-restore-gluetun-recovery-runbook.md)
- [docker-compose-memos-image-tag-troubleshooting.md](containers-apps/docker-compose-memos-image-tag-troubleshooting.md)
- [traefik-proxy-docker-network-runbook.md](containers-apps/traefik-proxy-docker-network-runbook.md)
- [vm100-docker-data-disk-recovery-cloud-init-hardening.md](containers-apps/vm100-docker-data-disk-recovery-cloud-init-hardening.md)
- [debian-docker-vm-rebuild-cloudinit-runbook.md](containers-apps/debian-docker-vm-rebuild-cloudinit-runbook.md)
- [traefik-docker29-upgrade-troubleshooting-runbook.md](containers-apps/traefik-docker29-upgrade-troubleshooting-runbook.md)
- [proxmox-traefik-console-troubleshooting-runbook.md](containers-apps/proxmox-traefik-console-troubleshooting-runbook.md)
- [vm110-provisioning-guest-agent-docker-appdata-permissions.md](containers-apps/vm110-provisioning-guest-agent-docker-appdata-permissions.md)

### Automation

- [proxmox-cephfs-snips-cloudinit-vm100-runbook.md](automation/proxmox-cephfs-snips-cloudinit-vm100-runbook.md)
- [proxmox-cloudinit-ceph-docker-runbook.md](automation/proxmox-cloudinit-ceph-docker-runbook.md)
- [proxmox-cloudinit-ceph-docker-vm100-troubleshooting-runbook.md](automation/proxmox-cloudinit-ceph-docker-vm100-troubleshooting-runbook.md)
- [proxmox-cloud-init-docker-vm-troubleshooting.md](automation/proxmox-cloud-init-docker-vm-troubleshooting.md)
- [proxmox-cloudinit-cicustom-snippet-storage-ha.md](automation/proxmox-cloudinit-cicustom-snippet-storage-ha.md)
- [vm100-docker-startup-mountguard-troubleshooting.md](automation/vm100-docker-startup-mountguard-troubleshooting.md)

### Security

- [proxmox-root-login-recovery-runbook.md](security/proxmox-root-login-recovery-runbook.md)
- [homelab-ssh-ansible-nut-documentation.md](security/homelab-ssh-ansible-nut-documentation.md)

### Monitoring & Operations

- [proxmox-ceph-memtest-ram-fault-runbook.md](monitoring-operations/proxmox-ceph-memtest-ram-fault-runbook.md)
- [proxmox-host-kernel-ram-instability-runbook.md](monitoring-operations/proxmox-host-kernel-ram-instability-runbook.md)
- [proxmox-nuc-e1000e-instability-runbook.md](monitoring-operations/proxmox-nuc-e1000e-instability-runbook.md)
