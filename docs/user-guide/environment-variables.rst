#####################
Environment variables
#####################

Noteburst uses environment variables for configuration.
In practice, these variables are typically set as Helm values and 1Password/Vault secrets that are injected into the container as environment variables.
See the `Phalanx documentation for Noteburst <https://phalanx.lsst.io/applications/noteburst/index.html>`__ for more information on the Phalanx-specific configurations.

.. envvar:: SAFIR_NAME

   (string, default: "Noteburst") The name of the application.
   This is used in the metadata endpoint.

.. envvar:: SAFIR_PROFILE

   (string enum: "production" [default], "development") The application run profile.
   Use production to enable JSON structured logging.

.. envvar:: SAFIR_LOG_LEVEL

   (string enum: "debug", "info" [default], "warning", "error", "critical") The application log level.

.. envvar:: NOTEBURST_PATH_PREFIX

   (string, default: "/noteburst") The path prefix for the Noteburst application.
   This is used to configure the application's URL.

.. envvar:: NOTEBURST_ENVIRONMENT_URL

   (string) The base URL of the Rubin Science Platform environment.
   This is used for creating URLs to services, such as JupyterHub.

.. envvar:: NOTEBURST_JUPYTERHUB_PATH_PREFIX

   (string, default: "/nb") The path prefix for the JupyterHub application.

.. envvar:: NOTEBURST_NUBLADO_CONTROLLER_PATH_PREFIX

   (string, default: "/nublado") The path prefix for the Nublado controller service.

.. envvar:: NOTEBURST_GAFAELFAWR_TOKEN

   (secret string) This token is used to make an admin API call to Gafaelfawr to get a token for the user.

.. envvar:: NOTEBURST_REDIS_URL

   (string) The URL of the Redis server, used by the worker queue.

.. envvar:: NOTEBURST_ARQ_MODE

   (string enum: "production" [default], "test") The Arq worker mode.
   The production mode uses the Redis server, while the test mode mocks queue interactions for testing the application.

.. envvar:: NOTEBURST_WORKER_IDENTITIES_PATH

   (string) The path to the Science Platform worker identities file.
   See :ref:`worker-identities-yaml`.

.. envvar:: NOTEBURST_WORKER_QUEUE_NAME

   (string) The name of arq queue the workers process.

.. envvar:: NOTEBURST_WORKER_LOCK_REDIS_URL

   (Redis URL) The URL of the Redis server, used by the worker lock.

.. envvar:: NOTEBURST_WORKER_JOB_TIMEOUT

   (integer, default: 300) The backstop timeout, in seconds, for the short worker tasks: ``ping``, ``run_python``, and the ``keep_alive`` cron.
   Notebook execution is not covered by this timeout; it has its own, much longer :envvar:`NOTEBURST_WORKER_NBEXEC_JOB_TIMEOUT`.

.. envvar:: NOTEBURST_WORKER_NBEXEC_JOB_TIMEOUT

   (integer, default: 3660) The arq backstop timeout, in seconds, for notebook execution (``nbexec``) jobs.
   Clients (such as Times Square) supply the notebook execution limit with each request, and the request's own timeout is what ends an over-running notebook, reporting it as a ``timeout`` error.
   The frontend rejects (with a 422 error) any request whose timeout is not at least 60 seconds shorter than this backstop, so arq's timeout stays a backstop: if it ever fires, it cancels the job and records a bare ``TimeoutError``.
   With the default of 3660 seconds, the longest accepted per-request timeout is one hour.

   Both the frontend and the worker read this variable, so it must be set identically for both deployments.
   (The Phalanx chart sets it in both config maps from a single Helm value.)

   Note that a long ``nbexec`` timeout lengthens how long *any* lost job stays unclaimable, not just a notebook execution.
   arq derives the TTL of its in-progress key from the longest timeout registered across all of the worker's functions, plus 10 seconds, and applies that single TTL to every job it starts.
   If a worker pod is killed mid-job — whether the job is ``nbexec``, ``ping``, or ``run_python`` — no other worker can pick that job up until the key expires: roughly :envvar:`NOTEBURST_WORKER_NBEXEC_JOB_TIMEOUT` + 10 seconds, or about 61 minutes at the default, compared to about 5 minutes when the worker-wide timeout was the only one in play.
   The short tasks' own execution timeout (:envvar:`NOTEBURST_WORKER_JOB_TIMEOUT`) is unaffected; only their lost-job recovery latency widens.
   Weigh that recovery latency when raising this setting.

.. envvar:: NOTEBURST_WORKER_TOKEN_LIFETIME

   (integrer, default: 2419200) The worker auth token lifetime in seconds.

.. envvar:: NOTEBURST_WORKER_TOKEN_SCOPES

   (string, default: "exec:notebook") The worker (nublado pod) token scopes, as a comma-separated string.

.. envvar:: NOTEBURST_WORKER_IMAGE_SELECTOR

   (string enum: "recommended" [default], "weekly", "reference") The method for selecting a Jupyter image to run.
   For "reference" see :envvar:`NOTEBURST_WORKER_IMAGE_REFERENCE`.

.. envvar:: NOTEBURST_WORKER_IMAGE_REFERENCE

   (string) The tag of the Jupyter image to run. This is used when :envvar:`NOTEBURST_WORKER_IMAGE_SELECTOR` is set to "reference".

.. envvar:: NOTEBURST_WORKER_KEEPALIVE

   (string, enum: "normal" [default], "fast", "disabled") The worker keep alive mode.
   The regular keep-alive execises the JupyterLab pod every 5 minutes. The fast mode exercises the pod every 30 seconds.
   The disabled mode does not exercise the pod.
