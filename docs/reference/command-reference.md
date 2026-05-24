# Command Reference

Quick lookup for common infrastructure, cloud, automation, security, and troubleshooting commands.

## Notes

- Replace anything in `<angle-brackets>` before running.
- Review destructive commands carefully.
- Prefer check commands before change commands.

## Proxmox

```bash
# List VMs
qm list

# Show VM config
qm config <vmid>

# Rebuild cloud-init ISO
qm cloudinit update <vmid>
```

## Ceph

```bash
# Check Ceph health
ceph -s

# Show detailed health
ceph health detail

# Show OSD tree
ceph osd tree
```

## Docker

```bash
# List running containers
docker ps

# Show Compose services
docker compose ps

# Show container logs
docker logs <container-name>
```
