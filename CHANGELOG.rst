##########
Change log
##########

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
