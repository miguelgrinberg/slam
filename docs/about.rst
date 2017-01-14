==========
About Slam
==========

In this page you can find some background information on Slam and AWS.

What is Serverless Computing?
=============================

Modern clouds such as `AWS <https://aws.amazon.com>`_, offer different ways to
host applications. At the least involved level, you can create server instances,
which are fully enabled virtual machines that run the operating system of your
choice and are connected to the Internet. Once you have an instance up, you can
login to it and install your software, exactly like you would on a local server.
In AWS, this is the `Elastic Compute Cloud (EC2) <https://aws.amazon.com/ec2>`_
service.

The tendency, however, is to move towards a model in which developers only need
to concentrate on their applications, leaving most or all of the installation
and administration tasks to the cloud operator. This is what serverless
computing is about.

AWS provides a number of services that make the life of the application
developer easier. For example, it offers options for managed databases, message
queues, notifications, emails and so on. You as a developer have the option to
install your own stack on instances or containers, but if you want to spend all
your energy on your application, using the managed services offered by AWS makes
a lot of sense. And in addition to being convenient, these services have very
attractive pricing based on the "you only pay for what you use" model, so in
many cases you even end up saving money.

What are Lambda and API Gateway?
================================

In AWS, `Lambda <https://aws.amazon.com/lambda>`_ is the *function-as-a-service*
or *FaaS* offering. With this service, you can upload your Python, Node.js, Java
or C# code, and Lambda will deploy it and run it for you when you need to. To
work with the Lambda service you upload your project packaged as a zip file that
contains your application code plus all its dependencies. You have to designate
a function in your code as the entry point, and this function will be called by
AWS when the Lambda function is invoked.

Because Lambda functions are supposed to be short lived, and are not running
constantly like a normal web server, there are some types of applications that
are not a good match for this service. In particular, any applications that rely
on the server maintaining a long connection with the client will not work well.
Examples of these applications are those that return live information as a
stream, or those that use long-polling or WebSocket to provide constant updates
to the client.

While having some code ready to be executed on demand on the cloud is nice,
applications that expose their functionality as one or more HTTP based services
cannot directly work on this platform, since they rely servers that need to be
running constantly to receive client requests. In a traditional deployment of
these applications you would maybe use gunicorn or uWSGI.

The Amazon `API Gateway <https://aws.amazon.com/api-gateway>`_ service bridges
this gap, by allowing you to construct API endpoints, and configure what
actions these endpoints trigger when the client sends a request to them. The
service takes care of scaling, rate limiting, and even authentication if you
want to offload that to the cloud too. Among the available actions you can
associate with an API Gateway endpoint, there is invoking a Lambda function.

How does Slam work?
===================

Slam's command-line utility allows you to package and deploy your Python web
application without having to make any changes to it. The idea is that you can
continue to develop your application locally, and deploy it to AWS with a single
command.

Slam takes advantage of the wide support WSGI has in Python web applications, by
converting HTTP requests and responses between the API Gateway and WSGI formats.
When a request is received by API Gateway and passed on to the Lambda function,
this request is converted to the WSGI format and used to invoke your
application. The WSGI response from the application is converted back to the API
Gateway format before the Lambda function ends. Slam makes the deployment
completely automated by generating the code that performs these conversions, so
that your application does not need to be changed at all.

One of the nicest features of Slam how it creates neat and tidy deployments that
are a pleasure to manage. For this, it relies on
`Cloudformation <https://aws.amazon.com/cloudformation>`_, the AWS
orchestration service. Slam uses the project configuration to create a
Cloudformation template, and then it runs this template to make changes on your
cloud account. The end result is that every single resource that is allocated
for your deployment is owned by the Cloudformation template, making it easy to
keep track of what resources are in use. And if you find the need to create a
custom deployment that varies from the standard structure used by Slam, all you
need to do is take Slam's Cloudformation template and modify it to suit your
needs.

Alternatives to Slam
====================

There are other serverless frameworks that create Lambda and API Gateway
deployments similar to Slam. If for any reason Slam does not work for you,
these may be good alternatives to research.

`Chalice <https://github.com/awslabs/chalice>`_ is an open-source framework from
AWS that uses a decorator-based syntax similar to Flask and Bottle to create
API Gateway and Lambda projects. The main disadvantage of Chalice against Slam
is that it is not built on top of WSGI, so a project based on this framework
can only be run on AWS.

`Zappa <https://www.zappa.io/>`_ is another open-source framework that is
more mature than Slam, but overall similar. The main difference with Slam is
that it invokes AWS APIs directly during a deployment, instead of using
Cloudformation to orchestrate the deployment.
