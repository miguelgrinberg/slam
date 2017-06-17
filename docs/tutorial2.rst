=================
Advanced Tutorial
=================

In this second tutorial you will learn how to deploy a Python API project with
Slam through a hands-on tutorial. In this tutorial you will use most features
of Slam, and will have a small Python API deployed to AWS Lambda and API
Gateway.

The screencast below is a recorded run through the entire tutorial. Feel free
to use it as a reference when you go through the steps yourself, but note that
it was created for an older release of Slam, so there are minor variations in
the commands used.

.. raw:: html

    <iframe width="660" height="371" src="https://www.youtube.com/embed/9eoL6oGiodw" frameborder="0" allowfullscreen></iframe>

Installing the Tutorial Project
===============================

To do this tutorial, you need to download a small API project that consists of
two files:

- `tasks_api.py <https://github.com/miguelgrinberg/slam/raw/master/examples/tasks-api/tasks_api.py>`_
- `requirements.txt <https://github.com/miguelgrinberg/slam/raw/master/examples/tasks-api/requirements.txt>`_

Download these two files by right-clicking on the links above and selecting
"Save link as..." to write them to your disk. Please put the files in a brand
new directory.

The project uses a `DynamoDB <https://aws.amazon.com/dynamodb>`_ database, which
is a AWS managed database service. To be able to run this project locally, you
will need to download and run
`dynamodb-local <https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/DynamoDBLocal.html>`_.

Assuming you have dynamodb-local running, you set up and run this API with
these commands::

    $ virtualenv venv
    $ source venv/bin/activate
    (venv) $ pip install -r requirements.txt
    (venv) $ python tasks_api.py

If you are following this tutorial on Windows, the virtual environment
activation command (2nd line above) is ``venv\Scripts\activate.bat``.

Once the API server is running, you can send requests to it at the address
*http://localhost:5000*.

Configuration
=============

This is going to be similar to what you did in the first tutorial. To begin,
install the Slam utility with pip::

    (venv) $ pip install slam

Now use the ``slam init`` command to create a starter configuration file::

    (venv) $ slam init tasks_api:app --wsgi --stages dev,prod --dynamodb-tables tasks
    The configuration file for your project has been generated. Remember to add slam.yaml to source control.

The above command generates a *slam.yaml* configuration file, with some initial
settings. When you are working on a real project, you would want to add this
file to source control, along with your own files. As your project evolves, you
will hand edit this configuration file to make changes to your deployment.

Let's go over the options included in the ``slam init`` command above one by
one:

- ``tasks_api:app`` is a standard notation used by Python web servers to
  designate the WSGI entry point of the application. What appears to the left of
  the colon, is the package or module where the WSGI callable instance is
  located. The name that appears to the right of the colon is the variable that
  holds the WSGI application instance. Slam uses this information to know where
  it needs to forward HTTP requests as they come into the Lambda function.
- ``--wsgi`` indicates that this project should be deployed as a WSGI complaint
  web application.
- ``--stages dev,prod`` creates two *stages*, named ``dev`` and ``prod``. In
  slam, stages are independent versions of your deployed project. Having
  multiple stages allows you to deploy new features on one stage for development
  and testing purposes, while having a stable version of your project on
  another. You can create as many stages as you want. The first defined stage
  is configured as the default stage to receive new deployments. You will see
  later that Slam provides the tooling necessary to control what's deployed to
  the additional stages.
- ``--dynamodb-tables tasks`` creates a DynamoDB table called ``tasks`` for each
  defined stage. To make table names unique, Slam prefixes the requested name
  with the stage name. In this case, two DynamoDB tables will be created as
  part of this deployment, with names ``dev.tasks`` and ``prod.tasks``.

Note that up to this point your AWS account has not been touched. All that has
happened so far is configuration.

AWS Credentials
===============

If you haven't configured your AWS credentials yet, please go over the
instructions to do so in the first tutorial.

Deployment
==========

With the AWS credentials installed, you can now proceed to deploy this API
project to AWS with the ``slam deploy`` command::

    (venv) $ slam deploy
    Building lambda package...
    Deploying simple-api...
    simple-api is deployed!
      dev:$LATEST: https://ukhhy78b6a.execute-api.us-west-2.amazonaws.com/dev
      prod:$LATEST: https://ukhhy78b6a.execute-api.us-west-2.amazonaws.com/prod

The deployment process can take between one and two minutes. After the command
finishes, you will have the API deployed!

The command shows the URLs where the two stages are exposed. Since this is the
first deployment, both ``dev`` and ``prod`` are unversioned stages that are
reported as ``$LATEST``, which means that the track the most current version of
the code. We will see how to create versions in the next secion of this
tutorial.

At this point, you can send requests to the ``dev`` request URL and it should
behave exactly like the version you tested locally on your computer.

Publishing a Version
====================

Slam promotes a development cycle in which new versions of your project are
deployed to your development stage, tested there, and then *published* to
another stage, which could be a production stage, or maybe a staging stage.

When the project is published to a stage, it receives a permanent version
number, which ensures the version running on that stage does not change
regardless of what other code is deployed or published on other stages.

To publish the version of the API deployed in the previous section to the
``prod`` stage, the ``slam publish`` command is used::

    (venv) $ slam publish prod
    Publishing simple-api:dev to prod...
    simple-api is deployed!
      dev:$LATEST: https://ukhhy78b6a.execute-api.us-west-2.amazonaws.com/dev
      prod:1: https://ukhhy78b6a.execute-api.us-west-2.amazonaws.com/prod

Note that after the publish command completes, the ``prod`` stage is shown as
``prod:1``, indicating that this stage is running version 1.

You can now continue working on the project, and run ``slam deploy`` to deploy
the changes to the ``dev`` stage, and that is not going to affect the version of
the project running on ``prod``. If you want to upgrade the ``prod`` stage to a
newer version of the project, just issue issue another ``slam publish prod``
command, and the current code in the ``dev`` stage will be used to upgrade
``prod``, with a new version number.

Project Status
==============

The status report that is shown after the deploy or publish commands run can
also be requested on its own using the ``slam status`` command::

    (venv) $ slam status
    simple-api is deployed!
      dev: https://ukhhy78b6a.execute-api.us-west-2.amazonaws.com/dev
      prod:1: https://ukhhy78b6a.execute-api.us-west-2.amazonaws.com/prod

Deleting the Project
====================

When you are done experimenting with this example project, you may want to
remove it from your AWS account. If you want to perform a manual delete, you
can just delete the Cloudformation stack and the S3 bucket used by this
project, and that will leave your account clean of this deployment.

Alternatively, you can use the ``slam delete`` command, which performs the
above two tasks for you::

    (venv) $ slam delete
    Deleting API...
    simple-api has been deleted.

The End
=======

Congratulations! You have reached the end of the second and last tutorial.

Please review the reference sections in this documentation for complete
information on all the commands and the options available through the
configuration file.
