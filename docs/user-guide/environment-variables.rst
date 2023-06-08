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

.. envvar:: NOTEBURST_WORKER_QUEUE_NAME

   (string) The name of arq queue the workers process.

.. envvar:: NOTEBURST_WORKER_LOCK_REDIS_URL

   (Redis URL) The URL of the Redis server, used by the worker lock.

.. envvar:: NOTEBURST_WORKER_JOB_TIMEOUT

   (integer, default: 3000) The timeout for a worker job, in seconds.

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
