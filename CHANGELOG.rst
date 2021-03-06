##########
Change log
##########

0.5.0 (2022-07-04)
==================

- Its now possible to skip retries on notebook execution failures in the ``nbexec`` task by passing an ``enable_retry=False`` keyword argument.
  This is useful for applications that use Noteburst for continuous integration.
- Updated dependencies.

0.4.0 (2022-06-15)
==================

- The worker identity configuration can now omit the ``uid`` field for environments where Gafaelfawr is able to assign a UID (e.g. through an LDAP backend).
- New configurations for workers:
    - The new ``NOTEBURST_WORKER_TOKEN_LIFETIME`` environment variable enables you to configure the lifetime of the workers' authentication tokens. The default matches the existing behavior, 28 days.
    - ``NOTEBURST_WORKER_TOKEN_SCOPES`` environment variable enables you to set what token scopes the nublado2 bot users should have, as a comma-separated list.
    - ``NOTEBURST_WORKER_IMAGE_SELECTOR`` allows you to specify what stream of Nublado image to select. Can be ``recommended``, ``weekly`` or ``reference``. If the latter, you can specify the specific Docker Image with ``NOTEBURST_WORKER_IMAGE_REFERENCE``.
    - The ``NOTEBURST_WORKER_KEEPALIVE`` configuration controls whether the worker keep alive function is run (to default the Nublado pod culler), and at what frequency. Set to ``disabled`` to disable; ``fast`` to run every 30 seconds; or ``normal`` to run every 5 minutes.
- Noteburst now uses the arq client and dependency from Safir 3.2, which was originally developed from Noteburst.

0.3.0 (2022-05-24)
==================

Improved handling of the JupyterLab pod for noteburst workers:

- If the JupyterLab pod goes away (such as if it is culled), the Noteburst workers shuts down so that Kubernetes creates a new worker with a new JupyterLab pod. A lost JupyterLab pod is detected by a 400-class response when submitting a notebook for execution.

- If a worker starts up and a JupyterLab pod already exists for an unclaimed identity, the noteburst worker will continue to cycle through available worker identities until the JupyterLab start up is successful. This handles cases where a Noteburst worker restarts, but the JupyterLab pod did not shut down and thus is "orphaned."

- Each JupyterLab worker runs a "keep alive" function that exercises the JupyterLab pod's Python kernel. This is meant to counter the "culler" that deletes dormant JupyterLab pods in the Rubin Science Platform. Currently the keep alive function runs every 30 seconds.

- The default arq job execution timeout is now configurable with the ``NOTEBURST_WORKER_JOB_TIMEOUT`` environment variable. By default it is 300 seconds (5 minutes).

0.2.0 (2022-03-14)
==================

- Initial version of the ``/v1/`` HTTP API.
- Migration to Safir 3 and its database framework.
- Noteburst is now cross-published to the GitHub Container Registry, ``ghcr.io/lsst-sqre/noteburst``.
- Migration to Python 3.10.

0.1.0 (2021-09-29)
==================

- Initial development version of Noteburst.
