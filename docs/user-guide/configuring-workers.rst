##########################################
Configuring Noteburst's JupyterLab workers
##########################################

Noteburst works by operating a cluster of workers that each manages their own JupyterLab pods.
This page describes how these workers are configured.

Background: Kubernetes architecture
===================================

In Kubernetes, the workers are deployed as a Kubernetes Deployment.
A Deployment enables multiple Noteburst worker instances to run at the same time.
These workers share the same configuration (typically through a Kubernetes ConfigMap).
This means that individual workers can't be assigned specific RSP/JupyterLab user accounts.
Noteburst works around this by configuring the deployment of Noteburst workers with a pool of identities.
When a worker starts up, it picks an available identity from the pool and uses that identity to run the JupyterLab pod.
See the next section for details.

.. _worker-identities-yaml:

Worker identities
=================

Each Noteburst worker pod runs a JupyterLab server under a specific, and unique, identity.
These identities are bot accounts.
In some RSP environments, such as the USDF, these identities need to be associated with actual user accounts.

When a Noteburst worker pod starts up, it picks an available identity from a pool of available identities.
These identifies are configured in a file, that path of which is specified with :envvar:`NOTEBURST_WORKER_IDENTITIES_PATH`.
This file is a YAML-formatted file that looks like this:

.. code-block:: yaml
   :caption: identities.yaml

   - username: "bot-noteburst00"
   - username: "bot-noteburst01"
   - username: "bot-noteburst02"
   - username: "bot-noteburst03"
   - username: "bot-noteburst04"
   - username: "bot-noteburst05"

The YAML file consists of a list of identities.
At a minimum, an identity requires a ``username`` field.

In some environments where Gafaelfawr cannot provide a uid for a user, a ``uid`` must be specified:

.. code-block:: yaml
   :caption: identities.yaml

   - username: "bot-noteburst00"
     uid: 90000
   - username: "bot-noteburst01"
     uid: 90001
   - username: "bot-noteburst02"
     uid: 90002
   - username: "bot-noteburst03"
     uid: 90003
   - username: "bot-noteburst04"
     uid: 90004
   - username: "bot-noteburst05"
     uid: 90005
