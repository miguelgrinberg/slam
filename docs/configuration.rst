=======================
Configuration Reference
=======================

This section enumerates all the options that can be provided in the *slam.yaml*
configuration file.

Core Options
============

- ``name``

  The name of the project.

- ``description``

  A description for the project.

- ``type``

  The project type. At this time, the only supported project type is ``wsgi``.

- ``wsgi``

  Options that apply to projects of type ``wsgi``.

  - ``module``

    The Python module or package that contains the WSGI application callable.

  - ``app``

    The name of the variable that holds the WSGI application callable.

- ``requirements``

  The project's requirements filename.

- ``devstage``

  The name of the stage designated as the development stage.

- ``environment``

  A collection of variables, specified as key-value pairs, that are made
  available to the Lambda function as environment variables.

  Example::

    environment:
      IN_LAMBDA: "1"
      ADMIN_URL: "1.2.3.4"

- ``stage_environments``

  A collection of stages. Each stage, can have a sub-collection of variables,
  specified as key-value pairs, that are made available to the Lambda function
  as environment variables, but only for the appropriate stage.

  Example::

    stage_environments:
      dev:
        DEBUG: "1"
      prod:
        DEBUG: "0"

- ``aws``

  A collection of settings specific to AWS.

  - ``s3_bucket``

    The bucket on S3 where Lambda packages are to be stored. If this bucket does
    not exist, it is created during the deployment.

  - ``lambda_timeout``

    The timeout, in seconds, for the Lambda function.

  - ``lambda_memory``

    The memory size, in megabytes, for the Lambda function.

DynamoDB Plugin
===============

- ``dynamodb_tables``

  A collection of DynamoDB tables to create for each stage. Each table entry
  is defined by the table name, and contains a sub-collection of settings that
  define the table schema.

  Tables created by this plugin have a name with the format *stage.name*, so for
  example, for a project that defines ``dev`` and ``prod`` stages, a table named
  ``mytable`` in the configuration will result in DynamoDB tables
  ``dev.mytable`` and ``prod.mytable`` created.

  - ``attributes``

    A collection of attributes, as key-value pairs where the key is the
    attribute name, and the value is the attribute type. Attribute types are
    defined by DynamoDB and can be ``"S"`` for string, ``"N"`` for number,
    ``"B"`` for binary, and ``"BOOL"`` for boolean.

  - ``key``

    The name of the attribute that is the table's hash key, or a list of two
    elements with the attributes that are the table's hash and range keys.

  - ``read_throughput``

    The read throughput units for the table.

  - ``write_throughput``

    The write throughput units for the table.

  - ``local_secondary_indexes``

    A collection of local secondary indexes to define for the table. The
    indexes are defined by their name, and contain a sub-collection that
    specifies their structure.

    - ``key``

      Same as the table-level ``key`` attribute. For a local secondary index,
      the hash key must match the key selected for the table-level index.

    - ``project``

      The attributes to project on this index. If set to ``"all"`` all table
      attributes are projected. Else it can be set to a list of attribute
      names to project, or to an empty list to only project the key
      attributes.

  - ``global_secondary_indexes``

    A collection of global secondary indexes to define for the table. The
    indexes are defined by their name, and contain a sub-collection that
    specifies their structure.

    - ``key``

      Same as the table-level ``key`` attribute.

    - ``project``

      The attributes to project on this index. If set to ``"all"`` all table
      attributes are projected. Else it can be set to a list of attribute
      names to project, or to an empty list to only project the key
      attributes.

    - ``read_throughput``

      The read throughput units for the index.

    - ``write_throughput``

      The write throughput units for the index.

  Example::

    dynamodb_tables:
      # a simple table with "id" as hash key
      mytable:
        attributes:
          id: "S"
        key: "id"
        read_throughput: 1
        write_throughput: 1

      # a more complex table with hash/sort keys and secondary indexes
      mytable2:
        attributes:
          id: "S"
          name: "S"
          age: "N"
        key: ["id", "name"]
        read_throughput: 1
        write_throughput: 1
        local_secondary_indexes:
          myindex:
            key: ["id", "age"]
            project: ["name"]
        global_secondary_indexes:
          myindex2:
            key: ["age", "name"]
            project: "all"
            read_throughput: 1
            write_throughput: 1
