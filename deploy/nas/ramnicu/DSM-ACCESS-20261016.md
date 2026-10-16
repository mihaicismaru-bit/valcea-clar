# DSM access checkpoint — 16 October 2026

Repository: `mihaicismaru-bit/valcea-clar`, PR #55, branch
`feat/ramnicu-institutional-agents-pilot`. Baseline: `9bb0151`.

## Observed evidence

- The requested DSM URL was opened through the Windows default URL handler:
  `https://mihaicismaru.synology.me:5001/`.
- Windows discovery returned Microsoft Edge, window 264404, titled
  `Acasa - Synology NAS - Personal - Microsoft Edge`. On the resumed attempt,
  the same window was still present. The title alone does not establish an
  authenticated DSM session or NAS health.
- The initial Windows state capture returned: `Computer Use has been stopped
  for this turn because it could not determine the current browser URL on
  Windows with enough confidence to enforce policy. Stop your work and send
  a final message noting why Computer Use ended.` No DSM input followed.
- On resume, binding the existing DSM URL with the browser connector and
  `browser: edge` returned `Browser is not available: edge`.

## Status at this checkpoint

NAS health, storage capacity, storage pool/volume state, service UID/GID,
Container Manager availability and existing container inventory are **unknown**.
There is no evidence of a NAS outage: the demonstrated blocker is the automation
access path. No NAS data or existing services were changed. No collector image
was built, no persistent NAS directory was created, and no collection was run.
Neither a complete council meeting nor an urbanism case, including annexes, has
been validated. Local branch checkout is not proof of NAS deployment.

Publication remains disabled: this checkpoint introduces no publisher,
credentials, schedule, deployment or publication configuration changes. The
module stays collect-only until documents are validated and one publisher is
integrated under the controlled migration plan.

## Resume criteria and next steps

Restore supported browser access to the existing default-browser DSM session
(including reliable URL identification), or provide an authorized NAS execution
channel. Do not bypass the browser policy guard or infer credentials from the
desktop. Once accessible, inspect health/storage and existing containers first.
Select a new dedicated persistent directory and verify UID/GID/write access
before following `README.md` for the one-shot collector. Preserve all existing
services and volumes. Validate originals, extracted text and annex relationships
against the official source for one complete council meeting and one urbanism
case; save run IDs, counts, hashes and unresolved gaps. Keep publication off.

This checkpoint records only observations available before the final native
browser retry; it does not claim that retry succeeded or failed.

## Superseding result: DSM recovered, NAS build blocked (12:00 Europe/Bucharest)

Native Windows capture subsequently succeeded, identified the exact requested
URL and showed the authenticated DSM desktop. The earlier browser blocker is
resolved for this session. The current blocker is NAS build-context handling.

### Observed health and inventory

Storage Manager reported `Healthy` / `System is healthy.` Both volume indicators
were green. This overview is not an extended SMART test, scrub or restore test.

| Volume / pool | Used | Free |
| --- | --- | --- |
| Volume 1 / Storage Pool 1 | 381.3 GB | 467.3 GB |
| Volume 2 / Storage Pool 2 | 1.4 TB | 2.1 TB |

Container Manager reported `Healthy`, `All services are healthy.`, and
`12 containers are healthy.`, **also** `Errors occurred in 3 of 9 running
projects.` Image inventory: 14 images, 19.1 GB, 2 updates available; no updates
were applied. The project errors are distinct from the container health summary.

All 12 existing containers had green status and `Up for 1 day`:
fatbelly-home-assistant, threadfin, civora-romania-nas-runner, jellyfin,
qbittorrent, gfp-v01-gfp-1, mysmis-copilot-gateway, mysmis-copilot,
flaresolverr, calibre-web, calibre, advplyr-audiobookshelf-2-1-1-1.

Original projects: calibre-web, fatbelly-home-pilot, jellyfin, calibre, gfp-v01,
civora-romania-nas-runner, threadfin, civora-romania-runner, qbittorrent.
Red project indicators: fatbelly-home-pilot (1 container), gfp-v01 (3),
civora-romania-runner (0). Their causes were not investigated or changed.
Existing project paths are under `/volume1/docker`.

### Isolated NAS changes and exact failures

Created only the new directory/project `valcea-clar-ramnicu-pilot` at
`/volume1/docker/valcea-clar-ramnicu-pilot`. Existing services, volumes,
configurations and schedules were not modified or restarted. No credentials or
publication permissions were introduced. The final Containers tab showed
`0 items` and `No containers. Click Action to build your project.`

Three build attempts failed before a collector image/container could run:

1. Git context pinned to `ca6c1ce69fdf8890dc9fc9b1f3a773fe8acbbb9e`:

   ```text
   unable to prepare context: unable to find 'git': exec: "git": executable file not found in $PATH
   ```

2. Codeload gzip archive pinned to
   `38a8f8768465e52a0df6ceaec61ff9d5a098d519`:

   ```text
   Sending build context to Docker daemon  164.2kB
   Error response from daemon: archive/tar: invalid tar header
   ```

3. GitHub `/archive/38a8f8768465e52a0df6ceaec61ff9d5a098d519.tar.gz`
   with explicit extension: same 164.2kB / invalid tar header failure.

`compose.dsm.yml` reproduces the last attempted config, with two additional
repository warning comments. It is **experimental and fails on this NAS**.
It declares project-scoped named volume `ramnicu-evidence:/data`, UID/GID 1000,
read-only root filesystem, temporary `/tmp`, dropped capabilities, no restart,
no exposed ports and no publisher. Actual volume creation, ownership, writes
and persistence are unverified because build never completed.

The Dockerfile now initializes `/data` for owner 1000:1000 and accepts
`SOURCE_ROOT` for nested archives (default `.` for local contexts). These changes
have not been runtime-validated on the NAS.

The Windows upload dialog was visible, but setting its observed File name
element twice (including after refreshing) returned
`element 884 is not available in cached app state for msedge.exe`.
A coordinate attempt was rejected as over a non-target window. The dialog was
dismissed; DSM's YAML editor was used instead. No security barrier was bypassed.

### Current validation and next action

**No real collection ran.** No run ID, verified document count, council meeting,
urbanism case or annex validation exists from this attempt. Publication stays
off; existing CIVORA production workflows remain unchanged. A created project
is not evidence of successful deployment.

Resume with a local NAS build context: transfer and extract the pinned source
into the dedicated project directory, then use the existing Dockerfile and a
local-context compose. Alternatively import a separately built, verified image.
A working file-transfer or authorized NAS execution channel is needed for this
route. Do not alter existing services to obtain it. Both tested remote archive
routes fail before Dockerfile execution; the exact archive failure root cause
is not established. Docker documents remote tarball contexts at
https://docs.docker.com/build/concepts/context/#remote-tarballs .

After build: verify volume write access, run the one-shot collector, preserve
`latest_run.json`, SQLite, originals, text and annex links, then compare a full
council meeting and an urbanism case to the official document inventories.
Do not schedule or publish until validation and single-publisher integration.
Preserve this failed project for diagnosis; do not prune volumes.

Local verification after the Dockerfile changes: all 14 collector unit tests
passed, including the publication-disabled guard. The first test invocation
failed because sandbox TEMP denied file access; rerunning with a writable
temporary directory under the task's `work/` passed. This does not validate
the Docker image, live source coverage or NAS persistent-volume behavior.
