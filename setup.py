from setuptools import setup

setup(
    name='slam',
    version='0.6.0',
    url='https://github.com/miguelgrinberg/slam/',
    license='MIT',
    author='Miguel Grinberg',
    author_email='miguelgrinberg50@gmail.com',
    description='Serverless application manager',
    long_description=__doc__,
    packages=['slam'],
    zip_safe=False,
    include_package_data=True,
    platforms='any',
    entry_points={
        'console_scripts': [
            'slam = slam.cli:main'
        ],
        'slam_plugins': [
           'wsgi = slam.plugins.wsgi',
           'dynamodb_tables = slam.plugins.dynamodb'
        ]
    },
    install_requires=[
        'lambda_uploader',
        'boto3',
        'climax',
        'merry',
        'jinja2',
        'pyyaml',
        'virtualenv'
    ],
    tests_require=[
        'mock',
        'coverage',
        'flake8'
    ],
    test_suite='tests',
    classifiers=[
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 3',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ]
)
