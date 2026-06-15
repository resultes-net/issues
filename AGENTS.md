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

## Deployment
Most top-level repos will create and publish a Docker image when commits are pushed to `main`. `:latest` images will automatically
be picked up by `keel` running inside the Kubernetes cluster and updated the running containers inside the cluster.

Pushes to `system`'s main will upload the latests `systems.zip` file to OpenStack's Swift, to be consumed by the runners.

## A note on changing the parameters classes in `pydantic-models`
The structure of the simulation parmaters passed via the web UI through the server into the database are defined in `pydantic-models`
(source of truth). They end up in the paramters column of the simulation table. That column is a PostgreSQL/SQLModel/SQLAlchemy JSON column.
Be sure to generate `alembic` migrations in the `server` repo when changing the paramters `pydantic` models. Make use of the JSON field
operators `->`, `->>`, etc. when writing these migrations. If these migrations are omitted, existing simulations cannot be accessed
as they lead to `pydantic` deserialization errors when retrieving stale JSON parameters from the DB.

## A note on referencing pull requests and issues across `results-net`
In comments on GitHub always reference pull requests/issue/... references with the full URI (e.g.: https://github.com/resultes-net/server/pull/4 not #4)
as we're operating accross multiple repos and it's less error-prone this way.
