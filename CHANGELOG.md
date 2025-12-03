# Change log

<!-- scriv-insert-here -->

<a id='changelog-0.25.1'></a>
## 0.25.1 (2025-12-03)

### Bug fixes

- Use updated Safir so that app metrics won't break the app in rare situations if the underlying Kafka infrastructure is down.

<a id='changelog-0.25.0'></a>
## 0.25.0 (2025-11-13)

### New features

- Use service discovery via [Repertoire](https://repertoire.lsst.io/) to locate the Nublado API.

### Bug fixes

- Authenticate to JupyterLab before sending a keep-alive probe, thereby hopefully refreshing the XSRF token first.

<a id='changelog-0.24.0'></a>
## 0.24.0 (2025-09-23)

### Other changes

- Update error reporting and Kafka deps to be compatible with [Safir 13.0.0](https://github.com/lsst-sqre/safir/releases/tag/13.0.0)

<a id='changelog-0.23.0'></a>
## 0.23.0 (2025-08-07)

### Other changes

- Import Safir arq metrics items from new location

<a id='changelog-0.22.0'></a>
## 0.22.0 (2025-08-04)

### New features

- Added a script to publish a metric for the number of messages in the Arq queue. This is meant to be run periodically, probably with a Kubernetes CronJob.

- Enable [Safir generic arq metrics](https://safir.lsst.io/user-guide/arq.html#generic-metrics-for-arq-queues)

<a id='changelog-0.21.0'></a>
## 0.21.0 (2025-07-22)

### Other changes

- Get the index into the identities list from an env var, which is probably provided as a Kubernetes StatefulSet index. This lets each worker instance have a consistent RSP identity without needing the redis-based locking and tracking system.

<a id='changelog-0.20.0'></a>

## 0.20.0 (2025-05-21)

### New features

- Noteburst now sets the `X-Kernel-Name` header in the notebook execution request with the `/rubin/execution` endpoint to the JupyterLab server. This fixes a long-standing issue where the kernel name specified by the user in the `POST /noteburst/v1/notebook` request was not being used by the JupyterLab server. This caused the notebook to execute with the default kernel (which may be `python3` rather than `lsst`), or with the kernel named by the `kernelspec` metadata in the notebook.

<a id='changelog-0.19.0'></a>

## 0.19.0 (2025-05-15)

### New features

- Added the `exception_type` field to the `noteburst_error` field in the response model for `GET /noteburst/v1/notebooks/:notebook_id` to provide more detailed information about the error type. This field can be used to identify the specific type of error that occurred during the notebook execution for "unknown" error types.

- Improved reliability of notebook execution by no longer creating a Websocket connection with the JupyterLab pod for each notebook execution (`nbexec`) job. This reverts behavior added in version 0.14.0 (adoption of `rubin-nublado-client`).

- Add "hourly" and "daily" options for the `NOTEBURST_WORKER_KEEPALIVE` environment variable configuration. These are slower keep-alive intervals that are more suitable for more relaxed notebook culler settings.

<a id='changelog-0.18.0'></a>

## 0.18.0 (2025-05-07)

### New features

- Improve error handling in the worker startup. We're now catching the JupyterWebError, among others, which is related to orphaned JupyterLab pods already existing. This should allow the workers to gracefully handle the error and try new bot user identities. If the pool of users is exhausted, we now report an enriched error message to Sentry.

- Improve the worker keep alive functionality to cause a worker restart on any type of error.

<a id='changelog-0.17.0'></a>

## 0.17.0 (2025-04-30)

### New features

- [Sentry](https://sentry.io) integration.
  - Enabled by setting `SENTRY_DSN` in the environment, which is injected in Phalanx.
  - Sends errors and traces to the [noteburst project](https://rubin-observatory.sentry.io/projects/noteburst/?project=4509170139594752), which was created by [Prodromos](https://prodromos.lsst.io).
  - The [traces sample rate](https://docs.sentry.io/concepts/key-terms/sample-rates/#tracing) can be configured. It comes from Phalanx values.

<a id='changelog-0.16.0'></a>

## 0.16.0 (2025-03-17)

### New features

- Add support for per-user subdomains for Nublado-managed JupyterLab instances.

<a id='changelog-0.15.1'></a>

## 0.15.1 (2025-03-12)

### Bug fixes

- Catch more exceptions in the keepalive cron to trigger a worker to restart.

<a id='changelog-0.15.0'></a>

## 0.15.0 (2025-02-26)

### Backwards-incompatible changes

- Upgrade to Python 3.13

### New features

- Added [Application Metrics](https://safir.lsst.io/user-guide/metrics/index.html) scaffolding, and a single pair of metrics for counting the number of notebook execution tasks that are enqueued.

### Other changes

- Update `make update` to use the `--universal` flag for `uv pip compile`.
- Use `Annotated` for `Query` dependencies in the path operations.

<a id='changelog-0.14.0'></a>

## 0.14.0 (2024-11-07)

### New features

- Replace internal Nublado Client with version from rubin-nublado-client.

<a id='changelog-0.13.0'></a>

## 0.13.0 (2024-09-12)

### New features

- Notebook execution jobs can now set _timeouts_. In requests, set a timeout in the `timeout` request field. This can be a number of seconds, or a [human-readable duration string](https://safir.lsst.io/user-guide/datetime.html#parsing-time-intervals) (e.g. "1h30m"). The specified timeout is also repeated in the response body. This timeout applies to the notebook execution, not any time in the queue.

- Errors that prevented a notebook from being executed are now reported in the notebook job response body in the `error` field. The field is an object with a `code` field and a `message` field. The `code` field is a string that can be used to identify the error. Currently the codes are `timeout`, `jupyter_error`, and `unknown`. Note that exceptions raised in the Jupyter notebook aren't considered errors, but are instead reported in the `ipynb_error` field.

<a id='changelog-0.12.1'></a>

## 0.12.1 (2024-08-02)

### Bug fixes

- When logging into JupyterHub, a Noteburst now looks for XRSF tokens from each redirect.

### Other changes

- Adopt `ruff-shared.toml` from https://github.com/lsst/templates
- Adopt uv for dependency management and resolution.
- Adopt explicit ASGITransport for setting up test HTTPX client.

<a id='changelog-0.12.0'></a>

## 0.12.0 (2024-05-15)

### New features

- Create Gafaelfawr service tokens instead of user tokens for authenticated calls to JupyterHub and JupyterLab. Gafaelfawr is standardizing on the new service token type for all service-to-service authentication.

- Reduced the frequency of keep alive tasks for the Noteburst workers to once every 15 minutes, from once every 5 minutes. This is intended to clean up the logging output.

### Bug fixes

- Correctly extract cookies from the middle of the redirect chain caused by initial authentication to a Nublado lab. This fixes failures seen with labs containing JupyterHub 4.1.3.

<a id='changelog-0.11.0'></a>

## 0.11.0 (2024-04-24)

### New features

- Add support for `gid` as well as `uid` fields in the worker identity configuration. Both `uid` and `gid` are now validated as integers

<a id='changelog-0.10.0'></a>

## 0.10.0 (2024-03-26)

### New features

- Add a `NOTEBURST_WORKER_MAX_CONCURRENT_JOBS` environment variable configuration to limit the number of concurrent jobs a worker can run. The default is 3. Previously this was 10. This should be set to be equal or less than the number of CPUs available to the JupyterLab pod.

- The notebook execution client now waits as long as possible for the `/execution` endpoint in the JupyterLab pod to return the executed notebook. Previously the client would wait for a fixed amount of time, which could be too short for long-running notebooks. The JupyterLab server may still time-out the request, though.

### Bug fixes

- Improved handling of the XSRF token when authenticated to JupyterHub and JupyterLab pods. This is required in JupyterLab 4.1.

<a id='changelog-0.9.1'></a>

## 0.9.1 (2024-03-21)

### Bug fixes

- Fix Slack error messaging in the `nbexec` worker function.
- Extract and use the actual XSRF token when communicating with the Hub and Lab.

<a id='changelog-0.9.0'></a>

## 0.9.0 (2024-03-13)

### New features

- Add formatted errors when a job is not found for the `GET /v1/notebooks/:job_id` endpoint.

- Errors and uncaught exceptions are now sent to Slack via a Slack webhook. The webhook URL is set via the `SLACK_WEBHOOK_URL` environment variable.

### Other changes

- The code base now uses Ruff for linting and formatting, replacing black, isort, and flake8. This change is part of the ongoing effort to standardize SQuaRE code bases and improve the developer experience.

<a id='changelog-0.8.0'></a>

## 0.8.0 (2024-01-04)

### New features

- The response to `GET /notebooks/:job_id` now includes an `ipynb_error` field that contains structured information about any exception that occurred when executing the notebook. As well, if an exception occurred, the resultant notebook is still included in the response. That is, notebook failures are no longer considered failed jobs.

- The `job_id` is now included in log messages when running the `nbexec` job under arq.

- The user guide includes a new tutorial for using the Noteburst web API.

### Other changes

- Update to Pydantic 2
- Adopt FastAPI's lifespan feature
- Adopt scriv for changelog management

- Update GitHub Actions workflows, including integrating Neophile for dependency updates.

- Update to Python 3.12.

## 0.7.1 (2023-07-23)

### Bug fixes

- Add additional logging of JupyterLab spawning failures in workers.

### Other changes

- Added documentation for configuration environment variables.
- Added OpenAPI docs, rendered by Redoc, to the Sphinx documentation site.

## 0.7.0 (2023-05-22)

### New features

- The JupyterHub service's URL path prefix is now configurable with the `NOTEBURST_JUPYTERHUB_PATH_PREFIX` environment variable. The default is `/nb/`, which is the existing value.
- The Nublado JupyterLab Controller service's URL path prefix is configurable with the `NOTEBURST_NUBLADO_CONTROLLER_PATH_PREFIX` environment variable. The default is `/nublado`, which is the existing value.

## 0.6.3 (2023-04-20)

### Bug fixes

- Fix how failed notebook executions are handled. Previously failed notebooks would prevent Noteburst from getting the results of the execution job. Now the job is shown as concluded but unsuccessful by the `/v1/notebooks/{job_id}` endpoint.
- Structure uvicorn server logging.

## 0.6.2 (2023-04-12)

### Bug fixes

- Stop following redirects from the `hub/login` endpoint.
- Explicitly shut down the lab pod on worker shutdown.

## 0.6.1 (2023-03-28)

### Bug fixes

- Additional updates for JupyterLab Controller image API endpoint.

## 0.6.0 (2023-02-16)

### New features

- Migrated from the Cachemachine API to the new JupyterLab Controller API for obtaining the list of available Docker images for JupyterLab workers.

### Other changes

- Migrated to Python 3.11
- Adopted pyproject.toml for project metadata and dropped setup.cfg.

## 0.5.0 (2022-07-04)

### New features

- Its now possible to skip retries on notebook execution failures in the `nbexec` task by passing an `enable_retry=False` keyword argument. This is useful for applications that use Noteburst for continuous integration.

## 0.4.0 (2022-06-15)

### New features

- The worker identity configuration can now omit the `uid` field for environments where Gafaelfawr is able to assign a UID (e.g. through an LDAP backend).
- New configurations for workers:
  - The new `NOTEBURST_WORKER_TOKEN_LIFETIME` environment variable enables you to configure the lifetime of the workers' authentication tokens. The default matches the existing behavior, 28 days.
  - `NOTEBURST_WORKER_TOKEN_SCOPES` environment variable enables you to set what token scopes the nublado2 bot users should have, as a comma-separated list.
  - `NOTEBURST_WORKER_IMAGE_SELECTOR` allows you to specify what stream of Nublado image to select. Can be `recommended`, `weekly` or `reference`. If the latter, you can specify the specific Docker image with `NOTEBURST_WORKER_IMAGE_REFERENCE`.
  - The `NOTEBURST_WORKER_KEEPALIVE` configuration controls whether the worker keep alive function is run (to defeat the Nublado pod culler), and at what frequency. Set to `disabled` to disable; `fast` to run every 30 seconds; or `normal` to run every 5 minutes.
- Noteburst now uses the arq client and dependency from Safir 3.2, which was originally developed from Noteburst.

## 0.3.0 (2022-05-24)

### New features

Improved handling of the JupyterLab pod for noteburst workers:

- If the JupyterLab pod goes away (such as if it is culled), the Noteburst workers shuts down so that Kubernetes creates a new worker with a new JupyterLab pod. A lost JupyterLab pod is detected by a 400-class response when submitting a notebook for execution.

- If a worker starts up and a JupyterLab pod already exists for an unclaimed identity, the noteburst worker will continue to cycle through available worker identities until the JupyterLab start up is successful. This handles cases where a Noteburst worker restarts, but the JupyterLab pod did not shut down and thus is "orphaned."

- Each JupyterLab worker runs a "keep alive" function that exercises the JupyterLab pod's Python kernel. This is meant to counter the "culler" that deletes dormant JupyterLab pods in the Rubin Science Platform. Currently the keep alive function runs every 30 seconds.

- The default arq job execution timeout is now configurable with the `NOTEBURST_WORKER_JOB_TIMEOUT` environment variable. By default it is 300 seconds (5 minutes).

## 0.2.0 (2022-03-14)

### New features

- Initial version of the `/v1/` HTTP API.
- Migration to Safir 3 and its database framework.
- Noteburst is now cross-published to the GitHub Container Registry, `ghcr.io/lsst-sqre/noteburst`.
- Migration to Python 3.10.

## 0.1.0 (2021-09-29)

### New features

- Initial development version of Noteburst.
