FizzBuzz Example
================

This directory contains a very simple Python function that can be deployed to
AWS Lambda.

The deployment procedure is as follows:

1. Ensure you have valid AWS credentials for your account installed on your
   system. Use `aws configure` to set these.

2. Create a virtual environment and install slam in it.

        $ virtualenv venv
        $ source venv/bin/activate
        (venv) $ pip install slam

3. Create a slam configuration with `slam init`:

        (venv) $ slam init fizzbuzz:fizzbuzz

4. Deploy to AWS!

        (venv) $ slam deploy

5. Once the deployment completes, you can invoke the function with `slam
   invoke`:

        (venv) $ slam invoke number:=1
        1

        (venv) $ slam invoke number:=3
        fizz

        (venv) $ slam invoke number:=15
        fizz buzz
