---
title: "Create External Docker Network for Traefik"
track: "infrastructure"
category: "containers-apps"
type: "runbook"
logical_order: 50
date_rule: "Dates are removed from filenames, visible headings, indexes, generated metadata, and runbook body content."
---

# Create External Docker Network for Traefik

## Summary
A Docker network named `traefik-proxy` was created for use as a shared external network between Traefik and application stacks. The goal was to establish a standard network that multiple Docker Compose projects could attach to so Traefik could reach backend containers across separate stacks.

## Environment
- Docker host in the homelab
- Docker CLI
- Docker Compose-based application stacks
- Traefik reverse proxy
- External shared Docker bridge network: `traefik-proxy`

## Problem
A dedicated shared Docker network was needed so Traefik and other containers could communicate consistently across Compose projects.

## Symptoms
- No explicit error was recorded in this chat.
- The requirement was stated as a configuration task: create a Docker network called `traefik-proxy` using the CLI.

## Actions Taken
1. Created the Docker network from the CLI.

```bash
docker network create traefik-proxy
```

Purpose: Create a shared Docker bridge network named `traefik-proxy`.

2. Noted the explicit driver form as an equivalent option.

```bash
docker network create --driver bridge traefik-proxy
```

Purpose: Create the same network while explicitly specifying the standard single-host bridge driver.

3. Documented how Docker Compose stacks should reference the network as an external network.

```yaml
networks:
  traefik-proxy:
    external: true
```

Purpose: Allow Compose-managed services to attach to the pre-existing shared network instead of trying to create their own isolated network.

## Key Findings
- `docker network create traefik-proxy` is sufficient for creating the network in normal single-host Docker setups.
- Explicitly setting `--driver bridge` is optional in this case because bridge is the expected driver for a standard local Docker network.
- Marking the network as `external: true` in Compose is important when multiple stacks need to join the same pre-created network.
- This pattern is useful for Traefik because it often runs in one stack while proxied applications run in others.

## Resolution
The required Docker network creation command was identified and documented. The final operational command was:

```bash
docker network create traefik-proxy
```

Current status: the runbook step is defined and ready to execute on the Docker host.

## Validation
Success would be confirmed by:
- the command completing without error
- the network appearing in Docker's network list
- Traefik and application containers being able to attach to `traefik-proxy`
- Compose stacks successfully using `external: true` for that network

Likely validation command:

```bash
docker network ls
```

Purpose: Verify that `traefik-proxy` exists.

## Follow-Up Tasks
- Verify that Traefik is attached to `traefik-proxy`
- Ensure all proxied app stacks join the same external network
- Standardize Compose files so they all reference the same network name
- Optionally inspect the network after creation to confirm attached containers and subnet assignment
- Document this as a reusable baseline step in the homelab reverse proxy setup guide

## Lessons Learned
- A shared external Docker network is a clean way to connect Traefik to containers spread across multiple Compose projects.
- Pre-creating the network avoids duplicate per-stack networks that Traefik cannot automatically use across projects.
- Keeping the network name standardized reduces routing and service discovery mistakes in homelab deployments.

---

# Command Reference

## Command
```bash
docker network create traefik-proxy
```

**What it does**  
Creates a Docker network named `traefik-proxy`.

**Why it was used**  
A shared network was needed so Traefik and other containers from separate Compose projects could communicate on the same Docker network.

**Important arguments**  
- `network create`: Tells Docker to create a new network.
- `traefik-proxy`: The name assigned to the network.

**Expected result**  
Docker creates the network and returns either the network ID or a success response.

**What success indicates**  
The Docker host now has a network named `traefik-proxy` available for container attachment.

**What failure would indicate**  
- The network may already exist
- Docker may not be running
- The user may lack permission to access the Docker socket

**Risk level**  
Low risk.

**Safer alternative**  
Check whether the network already exists before creating it:

```bash
docker network ls
```

---

## Command
```bash
docker network create --driver bridge traefik-proxy
```

**What it does**  
Creates the `traefik-proxy` network and explicitly sets the driver to `bridge`.

**Why it was used**  
This makes the network type explicit. In most single-host Docker homelab setups, this is the standard network driver for inter-container communication.

**Important arguments**  
- `--driver bridge`: Uses Docker's local bridge networking driver.

**Expected result**  
A bridge network named `traefik-proxy` is created.

**What success indicates**  
The network exists and uses the standard local bridge model.

**What failure would indicate**  
- Same issues as above
- Invalid driver selection, if mistyped

**Risk level**  
Low risk.

**Homelab relevance**  
For Docker and Traefik, bridge networks are the standard way to let reverse proxy containers reach backend app containers on the same host.

---

## Command
```yaml
networks:
  traefik-proxy:
    external: true
```

**What it does**  
This is a Docker Compose network definition telling Compose to use an already existing Docker network rather than create a new one.

**Why it was used**  
Traefik commonly runs in one Compose stack while apps run in others. Using `external: true` lets all those stacks join the same network.

**Important fields**  
- `traefik-proxy`: The network name referenced by the Compose project.
- `external: true`: Tells Compose not to create the network and instead attach to an existing one.

**Expected result**  
When the stack starts, its containers attach to the pre-created `traefik-proxy` network.

**What success indicates**  
The stack is using the shared network correctly, which supports Traefik routing across stacks.

**What failure would indicate**  
If the network does not already exist, Compose will fail when bringing the stack up.

**Risk level**  
Low risk.

**Safer note**  
Create the network first before deploying the Compose stack.

---

## Command
```bash
docker network ls
```

**Likely command used**

**What it does**  
Lists Docker networks on the host.

**Why it was likely used**  
This is the most direct way to verify that `traefik-proxy` was created successfully.

**Expected result**  
A network list that includes `traefik-proxy`.

**What success indicates**  
The network exists and is available for use by Traefik and app containers.

**What failure would indicate**  
If `traefik-proxy` is absent, the creation step may not have been run successfully.

**Risk level**  
Low risk.

---

## Command
```bash
docker network inspect traefik-proxy
```

**Likely command used**

**What it does**  
Shows detailed information about the `traefik-proxy` network, including driver, subnet, gateway, and attached containers.

**Why it was likely useful**  
This is a strong validation step after creation, especially in a Traefik homelab where network attachment directly affects proxy routing.

**Expected result**  
Detailed JSON output describing the network.

**What success indicates**  
The network exists and can be inspected; attached containers can also be verified here.

**What failure would indicate**  
The named network does not exist or Docker is not responding.

**Risk level**  
Low risk.

**Homelab relevance**  
Useful when troubleshooting Traefik routing, label-based discovery, or cross-stack connectivity issues.
