########################################
How to execute a notebook with Noteburst
########################################

This page shows how to execute a Jupyter Notebook programmatically on the Rubin Science Platform with Noteburst's web API.
This approach is applicable to developers who want to integrate notebook execution into their own applications.
Most users won't use this method directly, but instead use Notebook through an application like Times Square.

Prerequisites
=============

HTTP client
-----------

To use the Noteburst web API, you need an HTTP client.
For this tutorial, we'll use HTTPie_, a command-line HTTP client.
You can also use curl or a Python library like Requests if you're more comfortable with that.

Rubin Science Platform token
----------------------------

To use the Noteburst web API, you need a token from the appropriate Rubin Science Platform instance.
This token generally needs the ``exec:notebook`` scope.

For more information on getting a token, see `the Rubin Science Platform documentation <https://rsp.lsst.io/guides/auth/creating-user-tokens.html>`__.

Once you get a token, it's convenient to store in an environment variable in your shell:

.. prompt:: bash

   export RSP_TOKEN="gt-..."

Send a Notebook to Noteburst
============================

To execute a Jupyter Notebook (``.ipynb`` file), first send a ``POST`` request:

.. prompt:: bash

   http -A bearer -a $RSP_TOKEN post https://usdf-rsp.slac.stanford.edu/noteburst/v1/notebooks/ ipynb=@example.ipynb

Set the ``ipynb`` field to the contents of the notebook (HTTPie_\ ’s ``@`` syntax automatically loads the content from a file).
Change the hostname as appropriate for your `Rubin Science Platform environment`_.

The response contains a ``Location`` header with a unique URL for this execution request (you can also get the same URL from the ``self_url`` field in the JSON response body).
You'll use this URL in the next step.

.. code-block:: http
   :caption: Example response headers
   :emphasize-lines: 7

   HTTP/1.1 202 Accepted
   Connection: keep-alive
   Content-Length: 226
   Content-Type: application/json
   Date: Thu, 04 Jan 2024 19:53:15 GMT
   Strict-Transport-Security: max-age=31536000; includeSubDomains
   location: https://data-dev.lsst.cloud/noteburst/v1/notebooks/821bd07de5e645b9b30a4e48a0a38b64

.. code-block:: json
   :caption: Example response body
   :emphasize-lines: 5

   {
     "enqueue_time": "2024-01-04T19:53:15.045000Z",
     "job_id": "821bd07de5e645b9b30a4e48a0a38b64",
     "kernel_name": "lsst",
     "self_url": "https://data-dev.lsst.cloud/noteburst/v1/notebooks/821bd07de5e645b9b30a4e48a0a38b64",
     "status": "queued"
   }

Get the executed notebook
=========================

Now make another request, this time a ``GET``, to that ``Location`` URL to get the executed notebook:

.. prompt:: bash

   http -A bearer -a $RSP_TOKEN get https://data-dev.lsst.cloud/noteburst/v1/notebooks/821bd07de5e645b9b30a4e48a0a38b64

The HTTP response body will look similar to the original response from the ``POST`` you made earlier.
Look at the ``status`` field, though.
If it's still ``queued``, the notebook hasn't been scheduled to execute yet.
If the status is ``in_progress``, the notebook is being executed, but has not yet finished.
You can periodically send more ``GET`` requests to check the status until it finally reads ``completed``.

.. code-block:: json
   :caption: Example response body

   {
     "enqueue_time": "2024-01-04T19:53:15.045000Z",
     "finish_time": "2024-01-04T19:53:22.229000Z",
     "ipynb": "{...}",
     "job_id": "821bd07de5e645b9b30a4e48a0a38b64",
     "kernel_name": "lsst",
     "self_url": "https://data-dev.lsst.cloud/noteburst/v1/notebooks/821bd07de5e645b9b30a4e48a0a38b64",
     "start_time": "2024-01-04T19:53:15.548000Z",
     "status": "complete",
     "success": true
   }

In the response, the executed notebook is in the ``ipynb`` field.

You can use the other fields to get statistics and information about the notebook execution.
For example, the difference between ``finish_time`` and ``start_time`` is the overall execution time.

Notebooks that raise an exception
=================================

If the notebook raised an exception, the partially notebook is still returned (and the ``success`` field is still ``true``).
However, now there will be an ``ipynb_error`` field with information about the exception:

.. code-block:: json
   :caption: Example response body with exception information
   :emphasize-lines: 5,6,7,8

   {
     "enqueue_time": "2024-01-04T19:53:15.045000Z",
     "finish_time": "2024-01-04T19:53:22.229000Z",
     "ipynb": "{...}",
     "ipynb_error": {
       "message": "An error occurred while executing the following cell:\n------------------\nraise RuntimeError(\"This is an error.\")\n",
       "name": "RuntimeError"
     },
     "job_id": "821bd07de5e645b9b30a4e48a0a38b64",
     "kernel_name": "lsst",
     "self_url": "https://data-dev.lsst.cloud/noteburst/v1/notebooks/821bd07de5e645b9b30a4e48a0a38b64",
     "start_time": "2024-01-04T19:53:15.548000Z",
     "status": "complete",
     "success": true
   }

Further reading
===============

For more information about the Noteburst API, see the :doc:`API reference </api>`.
