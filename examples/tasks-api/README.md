Tasks API Example
=================

This directory contains a small Python API that can be deployed to AWS Lambda.

The deployment procedure is as follows:

1. Ensure you have valid AWS credentials for your account installed on your
   system. Use `aws configure` to set these.

2. Create a virtual environment and install slam in it.

        $ virtualenv venv
        $ source venv/bin/activate
        (venv) $ pip install slam

3. Create a slam configuration with `slam init`:

        (venv) $ slam init tasks_api:app --wsgi --dynamodb_tables tasks

4. Deploy to AWS!

        (venv) $ slam deploy

5. Once the deployment completes, you can make requests to the endpoint that
   is associated with the deployment. For example, you can use httpie:

        (venv) $ pip install httpie
        (venv) $ http GET https://ukhhy78b6a.execute-api.us-west-2.amazonaws.com/dev
        HTTP/1.1 200 OK
        Connection: keep-alive
        Content-Length: 47
        Content-Type: application/json
        Date: Fri, 06 Jan 2017 07:02:05 GMT
        Via: 1.1 f1a40337a32137e1c23ceffead6a50d5.cloudfront.net (CloudFront)
        X-Amz-Cf-Id: Is5U2ez7ua9NzaqCQYTsu6NeulRfuEqM9J0UeJdbauEHvaSK0x8Irw==
        X-Amzn-Trace-Id: Root=1-586f40e5-90bec120881918050e5f9e3d
        X-Cache: Miss from cloudfront
        x-amzn-Remapped-Content-Length: 47
        x-amzn-RequestId: 0395ad7b-d3de-11e6-bbed-4b0d48b7d9e4
        
        {
            "name": "tasks",
            "version": "$LATEST"
        }
