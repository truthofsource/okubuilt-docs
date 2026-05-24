---
title: "Docker Compose Stack Deploy Failure: Memos Image Tag Not Found"
track: "infrastructure"
category: "containers-apps"
type: "runbook"
logical_order: 40
date_rule: "Dates are removed from filenames, visible headings, indexes, generated metadata, and runbook body content."
---

# Docker Compose Stack Deploy Failure: Memos Image Tag Not Found

## Summary
A Docker Compose application stack failed to deploy because one service referenced a container image tag that did not exist in the registry. The work session focused on identifying the failing image reference and updating the Compose stack to a valid tag so the stack could pull and start successfully.

## Environment
- Platform: Homelab Docker host
- Container runtime: Docker
- Orchestration/configuration: Docker Compose
- Reverse proxy: Traefik
- Public/internal domain used by Traefik labels: `dulynoted.cloud`
- External Docker network:
  - `traefik-proxy`
- Internal Docker network:
  - `joplin`
- Persistent storage root:
  - `/opt/docker-apps/`
- Applications in the stack:
  - Linkding
  - Memos
  - Mealie
  - BookStack
  - BookStack MariaDB
  - Vaultwarden
  - ArchiveBox
  - Draw.io
  - Joplin Server
  - Joplin PostgreSQL

## Problem
The stack failed during image pull because the **Memos** service referenced an image tag that Docker could not resolve:

```yaml
image: neosmemo/memos:latest
```

Docker attempted to pull:

```text
docker.io/neosmemo/memos:latest
```

but that tag was not found.

## Symptoms
The observed Docker error was:

```text
Error response from daemon: failed to resolve reference "docker.io/neosmemo/memos:latest": docker.io/neosmemo/memos:latest: not found
```

The failure occurred during Docker image resolution/pull, before the Memos container could start.

## Actions Taken
1. Reviewed the Docker error message to identify the failed image reference.
2. Located the affected service in the Compose stack:
   - Service: `memos`
   - Original image: `neosmemo/memos:latest`
3. Determined that the problem was specific to the Memos image tag, not the full Docker Compose stack.
4. Updated the Memos service to use a valid tag:

```yaml
image: neosmemo/memos:stable
```

5. Produced an updated Compose stack with the Memos image corrected.

## Key Findings
- The issue was not caused by Traefik routing, service labels, Docker networking, bind mounts, or published ports.
- The failure happened at the image pull/reference resolution stage.
- The invalid reference was:

```text
neosmemo/memos:latest
```

- The corrected image reference was:

```text
neosmemo/memos:stable
```

## Resolution
The Memos service image was changed from:

```yaml
image: neosmemo/memos:latest
```

to:

```yaml
image: neosmemo/memos:stable
```

This should allow Docker Compose to pull the Memos image successfully and continue deploying the stack.

## Validation
Recommended validation after applying the change:

```bash
docker compose pull memos
```

Purpose: Confirm that the corrected Memos image tag can be pulled successfully.

```bash
docker compose up -d memos
```

Purpose: Start or recreate only the Memos service after the image tag correction.

```bash
docker compose ps
```

Purpose: Confirm that the Memos container is running.

```bash
docker logs memos --tail 200
```

Purpose: Check the Memos startup logs for application-level errors.

```bash
curl -I https://memos.dulynoted.cloud
```

Purpose: Validate that the Traefik route, TLS endpoint, DNS, and backend service are responding.

## Follow-Up Tasks
- Rotate any passwords or secrets that were pasted into chat or stored directly in the Compose file.
- Move sensitive values into an `.env` file or secret-management workflow.
- Consider pinning versions for important services instead of using floating tags like `latest`.
- Consider changing key app images to stable or versioned tags where supported.
- Add a pre-deployment pull check to catch invalid image tags before a full stack rollout.
- Review which services actually need host port publishing when already routed through Traefik.

## Lessons Learned
- Not every Docker image publishes a `latest` tag.
- A Docker `not found` error during pull often means the tag or repository name is invalid, not that the container itself is misconfigured.
- For homelab stability, `stable` or pinned version tags are often safer than `latest`.
- Traefik routing labels only matter after the container image has been pulled and the container is running.
- Avoid storing real credentials directly in Compose files that may be copied, shared, committed, or pasted into support conversations.

---

# Command Reference

## Command
```bash
docker compose pull
```

### What it does
Pulls all container images defined in the current Docker Compose file.

### Important flags or arguments
- No service name was specified, so this command applies to every service in the Compose project.

### Why it was used
This is the likely command that exposed the invalid Memos image reference.

### Expected result
Docker should download or update all referenced images.

### Success indicates
All image repositories and tags are valid and reachable.

### Failure indicates
A referenced image cannot be pulled because of an invalid repository name, missing tag, registry/network issue, or authentication problem.

### Risk
Low. This command pulls images but does not recreate running containers by itself.

---

## Command
```bash
docker compose pull memos
```

### What it does
Pulls only the image used by the `memos` service.

### Important flags or arguments
- `memos`: limits the pull operation to the Memos service.

### Why it was used
Useful after changing the Memos image from `neosmemo/memos:latest` to `neosmemo/memos:stable`.

### Expected result
Docker successfully pulls the corrected Memos image.

### Success indicates
The corrected Memos image tag exists and is reachable.

### Failure indicates
The image reference is still wrong, Docker Hub is unreachable, or there is a registry/authentication problem.

### Risk
Low. This is a targeted image pull and does not recreate containers by itself.

---

## Command
```bash
docker compose up -d
```

### What it does
Creates, updates, and starts the full Docker Compose stack in detached mode.

### Important flags or arguments
- `up`: creates and starts services from the Compose file.
- `-d`: detached mode; containers run in the background.

### Why it was used
Used to deploy the stack after the Compose configuration was updated.

### Expected result
All services start successfully.

### Success indicates
The Compose file is valid, required images are available, networks exist or can be created, and containers started without immediate failure.

### Failure indicates
There may be an invalid image tag, Compose syntax issue, missing external network, port conflict, permissions problem, or application startup error.

### Risk
Medium. This can recreate or restart containers and may cause service downtime.

### Safer alternative
For targeted validation, restart only the affected service:

```bash
docker compose up -d memos
```

---

## Command
```bash
docker compose up -d memos
```

### What it does
Creates, updates, and starts only the `memos` service.

### Important flags or arguments
- `memos`: limits the operation to the Memos service.
- `-d`: detached mode.

### Why it was used
Useful for applying the corrected image tag without unnecessarily restarting the entire stack.

### Expected result
The Memos container starts successfully.

### Success indicates
The corrected image can be pulled and the Memos container can start.

### Failure indicates
There may still be an image issue, filesystem permission problem, port conflict, or application startup problem.

### Risk
Low to medium. It may recreate the Memos container, but avoids touching unrelated services.

---

## Command
```bash
docker compose ps
```

### What it does
Shows the current status of services in the Compose project.

### Important flags or arguments
No extra flags were used.

### Why it was used
Useful to confirm that the Memos container is running after the image tag fix.

### Expected result
The `memos` service should show as running.

### Success indicates
Docker successfully created and started the container.

### Failure indicates
If the service is missing, exited, or restarting, further log review is needed.

### Risk
Low. Read-only status check.

---

## Command
```bash
docker logs memos --tail 200
```

### What it does
Shows the most recent log output from the `memos` container.

### Important flags or arguments
- `memos`: the container name.
- `--tail 200`: displays only the last 200 log lines.

### Why it was used
Useful to verify that Memos started cleanly after the image fix.

### Expected result
Logs should show normal application startup.

### Success indicates
The container is running and the application is not immediately crashing.

### Failure indicates
Errors in the logs may point to volume permissions, configuration issues, database problems, or port binding problems.

### Risk
Low. Read-only log review.

---

## Command
```bash
curl -I https://memos.dulynoted.cloud
```

### What it does
Sends an HTTP HEAD request to the Memos public URL.

### Important flags or arguments
- `-I`: fetches response headers only.
- `https://memos.dulynoted.cloud`: the Traefik-routed hostname for Memos.

### Why it was used
Useful to validate DNS, TLS, Traefik routing, and backend connectivity after the container starts.

### Expected result
An HTTP response such as `200`, `301`, `302`, or another valid application response.

### Success indicates
The request reached Traefik and Traefik successfully routed to the Memos backend.

### Failure indicates
Possible DNS issue, certificate/TLS issue, Traefik router issue, Docker network issue, or Memos backend problem.

### Risk
Low. Read-only network/application check.

---

# Corrected Memos Compose Snippet

```yaml
memos:
  image: neosmemo/memos:stable
  container_name: memos
  volumes:
    - /opt/docker-apps/Memos/config:/var/opt/memos
  networks:
    - traefik-proxy
  labels:
    - traefik.enable=true
    - traefik.http.routers.memos.rule=Host(`memos.dulynoted.cloud`)
    - traefik.http.routers.memos.entrypoints=websecure
    - traefik.http.routers.memos.tls=true
    - traefik.http.services.memos.loadbalancer.server.port=5230
  ports:
    - 5230:5230
  mem_limit: 512m
  mem_reservation: 256m
  cpus: "0.8"
  cpu_shares: 256
  restart: always
```
