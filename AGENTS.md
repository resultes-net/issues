# Guidance for LLM-based software development agents for working on the ResulTES project

## Intro
ResulTES is a software for runnining dynamical simulations of renewable energy systems including thermal energey storages in online. It uses the
TRNSYS simulation software as its core computational engine, but wraps it in a FastAPI REST API, exposes that to the Internet and connects as
Svelte web client to it.

## Very broad architecture
ResulTES consist of the following components:

1. The client (in repo `client`): the web UI that connects to the "external server" (see below). Written in Svelte/TS.
    Allows user to choose between the three systems (Tank/Pit/Borehole thermal energy storage or [T|P|B]TES), parameterize them
    (size of solar collector field, size of storage, etc.) and submit them for simulation.
1. The external server (in repo `server`): the external server (exposed to the web, authenticated) with which the client
    communicates.
1. The internal server (in repo `server` as well): the internal server which is only accessible from within the ResulTES
    Kubernetes cluster, unauthenticated. The `server` repo includes the database schemas for database access. Technologies used:
    `SQLModel`/`SQLAlchemy` for ORM, `alembic` for migrations. The database is `PostgreSQL`. One database is shared between the internal
    and external server.
1. The scheduler (repo `scheduler`) which queries the internal servers for submitted simulations, schedules them for
    execution (while trying to be "fair" to the various users) and updates the simulation states which the client
    queries (pulls) repeatedly to update the user UI. The scheduler also orchestrates the runners which see below.
1. The runner(s) (repo `runner`): They actually run the TRNSYS simulations. Unlike all other components which run on Linux docker
    containers inside a Kubernetes cluster, runners run on OpenStack Windows machines (one runner per machine).
    A runner can run up to eight simulations in parallel. Runners are created and deleted by the scheduler. Runners get their inputs
    (except for the parameters which are passed along with a request for running a simulation by the scheduler) from and write their
    outputs to OpenStack's Swift. Runners and the scheduler communicate via JSON-RPC. The runners keep the scheduler informed about
    simulation logs, progress, errors, etc. (but results end up on Swift as specified above).

Other important repos inside the `resultes-net` org:

1. `pydantic-models`: These define the pydantic models which are re-used in many of the components/repos inside the org. Often they're
    even re-used as the basis for the database models in the `server` repo.
1. `openapi-schema`: Contains the OpenAPI-schema exported from the FastAPI REST APIs of the internal and external server.
    Can be updated from the `server` repo which contains `openapi-schema` as a subrepo using the `scripts\export_openapi_json.py`
    script. To use the schema in the `client`, its `openapi-schema` subrepo needs to be updated. Then, the TS models need to be
    generated using `npm run api:gen-model`.
1. `system`: Defines the [T|P|B]TES (py)TRNSYS system simulations.

## Dependencies
Most - if not all - Python repos contain a requirements file under `requirements/dev.txt` or similiar (e.g. `requirements-3.13\dev.txt`).
Don't install any package version: ALWAYS use the check-in requirements files for installing packages. You'll very seldom need to install
new packages. If you do find yourself needing to do so, however, add the package to the relevant `.in` file, not the pinned `.txt` files
and run `pip-compile-multi -d requirements --uv --backtracking --no-upgrade` or similar to generated updated, pinned `.txt` files.

The `runner` runs on Windows, so its requirements (`requirements-3.13`) must be compiled on Windows:
`pip-compile-multi -d requirements-3.13 --uv --no-upgrade --use-cache --backtracking`. The `dev-utils/pip-compile-multi-linux.sh`
script (in, e.g., `server` and `scheduler`) doesn't run there, and compiling on Linux pins the wrong packages, so don't
compile the runner's requirements from a Linux (e.g. cloud) session: leave that to a human.

## Python imports
After changing the imports of a Python file, sort them like VS Code does. VS Code uses the isort extension
(`ms-python.isort`) with default settings; no repo has an isort config. Run the repo's isort on the changed files only,
e.g. `venv/bin/isort src/foo.py` from the repo root. Run it from the root of the repo *the file belongs to*: for a
submodule like `pydantic-models` that's the submodule's root (`../venv/bin/isort ...`), otherwise isort misclassifies
first-party imports. Don't re-sort files you didn't touch: a few existing ones aren't sorted.

Don't run isort on files that started out as a tool's template or are generated, e.g. the server's `alembic/env.py` or
the alembic migrations: place the new import next to the existing ones by hand, so they stay close to the template.

## Deployment
Most top-level repos will create and publish a Docker image when commits are pushed to `main`. `:latest` images will automatically
be picked up by `keel` running inside the Kubernetes cluster and updated the running containers inside the cluster.

Pushes to `system`'s main will upload the latests `systems.zip` file to OpenStack's Swift, to be consumed by the runners.

Pushes to `runner`'s `main` build a new runner disk image in CI: building it isn't a manual step.

A runner keeps the disk image it was created from, and with it its `pydantic-models`, even after the scheduler deletes that
image as stale. The scheduler creates runners on demand, and also keeps one with a free job slot while any user has logged
in within the last 35 minutes (`workflow.py`), so a runner can be created at any time, e.g. right after a scheduler
deployment. So when a change needs the new runner (e.g. a `pydantic-models` change), restart the scheduler deployment
after `runner`'s CI has uploaded the new image, when no simulations are running: it deletes all runners on startup (unless
it's configured to keep them alive), and creates new ones from the new image.

dev.resultes.net is public and semi-production: besides the team, external early users have used it since 2026-10-05.
Their results and uptime matter: keep old results working (https://github.com/resultes-net/issues/issues/50) and avoid
outages, e.g. don't roll out changes that restart the scheduler while simulations are running (see `scheduler/AGENTS.md`).
Read-only database queries are fine. Destructive changes (data migrations that delete or rewrite rows, deletions) need
approval.

## Logs
TRNSYS writes one log per variation. The runner uploads it to Swift with the other results: container `resultes-results`,
`results/<variation ID>/<deck name>.log` (e.g. `complete-0.log`). The client's "Logs" page shows that file. A simulation
that fails while its variations are being created has no variation, and so no TRNSYS log.

Besides the log, Swift has `results/<variation ID>.zip`, the variation's whole working directory: the generated `.dck`,
the per-time-step printer files (`*.prt`), `processing.log` and, for TTES, `hourly.csv`. A listing with
`--prefix results/<variation ID>/` doesn't show it.

The logs of the components in Kubernetes (scheduler, internal and external server, client, ...) are collected in Loki,
with one month of retention. `kubectl logs` only goes back to the start of the current pod, so query Loki for anything
older, e.g. a scheduler crash. How to access it is described in the `argocd` repo's `AGENTS.md` (private).

## A note on changing the parameters classes in `pydantic-models`
The structure of the simulation parmaters passed via the web UI through the server into the database are defined in `pydantic-models`
(source of truth). They end up in the paramters column of the simulation table. That column is a PostgreSQL/SQLModel/SQLAlchemy JSON column.
Be sure to generate `alembic` migrations in the `server` repo when changing the paramters `pydantic` models. Make use of the JSON field
operators `->`, `->>`, etc. when writing these migrations. If these migrations are omitted, existing simulations cannot be accessed
as they lead to `pydantic` deserialization errors when retrieving stale JSON parameters from the DB.

## Submodules (`pydantic-models`, `openapi-schema`, ...)
1. `server`, `scheduler` and `runner` each have their *own* `pydantic-models` submodule, and each parses the simulation with it
    (the runner also runs the `systems` scripts with it). After changing `pydantic-models`, update the pin in all three, not only
    where the changed model is used. Pydantic ignores unknown fields by default, so a component with an outdated checkout doesn't
    fail on a new (e.g. defaulted) field: it silently drops it, e.g. the scheduler then passes parameters on to the runner without it.
1. `pydantic-models` and `openapi-schema` have no CI, and the other repos' CI checks out submodules at their pinned commits. So
    pushing a submodule repo deploys nothing; pushing a pin in a top-level repo does.
1. To use an unpushed submodule commit from another local checkout: in `<repo>/<submodule>`, `git fetch <path to the checkout
    with the commit> main`, then check out or rebase onto `FETCH_HEAD`, and commit the new pin in `<repo>`.

## Commits
Don't add a `Co-Authored-By` trailer (or any other agent attribution) to commit messages or PR bodies, even if older
commits in the repo have one. When matching a repo's commit message style, copy the subject and body style only.

## A note on referencing pull requests and issues across `results-net`
In comments on GitHub always reference pull requests/issue/... references with the full URI (e.g.: https://github.com/resultes-net/server/pull/4 not #4)
as we're operating accross multiple repos and it's less error-prone this way.

## Issues and the project board
The issues in this repo are the backlog. When work finishes, changes or reveals a follow-up for an issue, suggest updating
it (tick a checklist item, comment, close it with a reference to the fixing commit, or open a (sub-)issue), and ask before
writing, since it's visible to others.

Add new issues to the org's "ResulTES" project, with status "Backlog" unless told otherwise.

Issues that are implemented and waiting to be tested go to "In review" in the org's "ResulTES" project (there's no "To test" column;
add the issue to the project first if it isn't on it). Close them only after they have been tested.

Move the issues you work on through the project's statuses yourself, without asking: "In progress" when you start,
"In review" when it's implemented (pushed or ready to push) and waiting to be tested. Status changes aren't "writing" in
the sense above; comments, edits and closing still need asking. The project is number 1 of the `resultes-net` owner
(`gh project item-add 1 --owner resultes-net --url <issue URL> --format json --jq .id` adds an issue and prints its item
ID). To set the status:

```sh
gh project item-edit --project-id PVT_kwDODGNNj84A5AUL --field-id PVTSSF_lADODGNNj84A5AULzgt4HPs \
    --id <item ID> --single-select-option-id <option ID>
```

The options: Backlog `f75ad846`, Ready `61e4505c`, In progress `47fc9ee4`, In review `df73e18b`, Done `98236657`. An
issue's item ID (`gh issue view --json projectItems` doesn't include it; empty means the issue isn't on the project yet):

```sh
gh project item-list 1 --owner resultes-net --limit 500 --format json \
    --jq '.items[] | select(.content.number == <number> and .content.repository == "resultes-net/issues") | .id'
```

The project's workflows link "Done" and closing: moving an issue to "Done" closes it, and closing an issue moves it to "Done".
So do only one of the two.
