==============
Basic Tutorial
==============

In this section you will learn how to deploy a Python function to AWS using
Slam.

Installing the Tutorial Project
===============================

To do this tutorial, you need to download a small Python project that consists
of two files:

- `fizzbuzz.py <https://github.com/miguelgrinberg/slam/raw/master/examples/fizzbuzz/fizzbuzz.py>`_
- `requirements.txt <https://github.com/miguelgrinberg/slam/raw/master/examples/fizzbuzz/requirements.txt>`_

Download these two files by right-clicking on the links above and selecting
"Save link as..." to write them to your disk. Please put the files in a brand
new directory.

This project is a version of the popular Fizz Buzz coding exercise. To become
familiar with this application, you can run it as follows::

    $ python3 fizzbuzz.py 2
    2
    $ python3 fizzbuzz.py 12
    fizz
    $ python3 fizzbuzz.py 15
    fizz buzz
    $ python3 fizzbuzz.py 5
    buzz

If you prefer, you can also use Python 2.7 to run this function.

Configuration
=============

To prepare to deploy this application to Lambda, begin by installing the Slam
utility with pip in a brand new virtual environment::

    $ python3 -m venv venv
    $ . venv/bin/activate
    (venv) $ pip install slam

This will add a ``slam`` command to your virtual environment. You can use
``slam --help`` to see what are all the available options.

The ``slam init`` command can be used to create a starter configuration file::

    (venv) $ slam init fizzbuzz:fizzbuzz
    The configuration file for your project has been generated. Remember to add slam.yaml to source control.

The above command generates a *slam.yaml* configuration file, with some initial
settings. When you are working on a real project, you would want to add this
file to source control, along with your own files. As your project evolves, you
will hand edit this configuration file to make changes to your deployment.

The ``fizzbuzz:fizzbuzz`` argument tells Slam that the function is located in
a module named ``fizzbuzz`` (the one on the left of the colon), and that the
function that we want to deploy from that module is also named ``fizzbuzz``
(the one on the right of the colon).

Note that up to this point your AWS account has not been touched. All that has
happened so far is configuration.

AWS Credentials
===============

Slam expects AWS credentials for your account to be installed in your system. As
explained
`here <http://docs.aws.amazon.com/cli/latest/topic/config-vars.html>`_, there
are many possible sources of configuration, including environment variables or
credential files.

If you are familiar with how AWS stores credentials, then feel free to use your
preferred way. The following instructions use the AWS command-line utility to
store credentials in configuration files in your home directory.

To be able to access AWS service from the command line, you first need to set up
access keys on the AWS Console. If you are not familiar with AWS account
security, it is highly recommended that you read the `AWS Security Credentials
<http://docs.aws.amazon.com/general/latest/gr/aws-security-credentials.html>`_
section of the AWS documentation.

Once you have obtained your access and secret keys on the AWS Console, you can
use the AWS command-line utility to store them in your system.

Install the AWS command-line utility with pip::

    (venv) $ pip install awscli

Then use the ``aws configure`` command to enter your credentials. The command
will prompt you to type them one by one::

    (venv) $ aws configure
    AWS Access Key ID [None]:
    AWS Secret Access Key [None]:
    Default region name [None]:
    Default output format [None]:

The first two prompts are for your access keys. For the third prompt you have to
pick one of the AWS regions. If you have no preference, use ``us-east-1``, or
pick the region closest to where you are located. In the screencast above, the
``us-west-2`` region is used.

Deployment
==========

With the AWS credentials installed, you can now proceed to deploy this project
to AWS with the ``slam deploy`` command::

    (venv) $ slam deploy
    Building lambda package...
    Deploying fizzbuzz:dev...
    fizzbuzz is deployed!
      Function name: fizzbuzz-Function-1CUMOX2834PA0
      S3 bucket: fizzbuzz-J5FTHI40
      Stages:
        dev:$LATEST

The deployment process will take between about a minute. After the command
finishes, you will have the function deployed and ready to be used!

The output from the ``deploy`` command indicates that the function was deployed
to a ``dev`` stage, and that its version is ``$LATEST``. Do not worry about
this for this tutorial, stages and versioning will be covered in the second
tutorial.

Invoking your Lambda Function
=============================

The ``slam invoke`` command can be used to quickly test that the function
hosted on AWS Lambda. If you look at the code of the function, you'll notice
that the input is an argument named ``number``. Below you can see how to invoke
the function and pass a value for this argument using the ``invoke`` command::

    (venv) $ slam invoke number:=2
    2
    (venv) $ slam invoke number:=12
    fizz
    (venv) $ slam invoke number:=15
    fizz buzz
    (venv) $ slam invoke number:=5
    buzz

The ``invoke`` command needs to know the correct type of the arguments you are
passing to your function. For each argument, you have to include the name of
each argument and its value. For string arguments, you can use the
``argument=value`` syntax. If the argument is not a string, use
``argument:=value`` to have the argument intrepreted as JSON.

Cloudformation Template
=======================

The deployment that you just finished was done through Cloudformation, the
AWS orchestration service. If you are curious to see what resources were
created, you can go to the Cloudformation section of the AWS console and view
the stack that corresponds to this deployment.

You can also use the ``slam template`` command to view the Cloudformation
template that was used for the deployment.

Deleting the Project
====================

A deployment orchestrated with Slam contains two high-level resources:

- A Cloudformation stack
- A S3 bucket with the Lambda zip file package inside

Every other resource allocated for the deployment is owned by the
Cloudformation stack, which is very convenient, as this prevents resources to
inadvertently be left behind or orphaned.

When you are done experimenting with this example project, you may want to
remove it from your AWS account. If you want to perform a manual delete, you
can just delete the Cloudformation stack and the S3 bucket, and that will leave
your account clean of this deployment.

As a convenience to users, there is a ``slam delete`` command that performs the
above two tasks for you::

    (venv) $ slam delete
    Deleting fizzbuzz...
    Deleting logs...
    Deleting files...

Congratulations! You have reached the end of this first tutorial. The second
tutorial covers more advanced usages that include the deployment of a REST API
project.
