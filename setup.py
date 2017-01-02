from setuptools import setup

setup(
    name='slam',
    version='0.0.8',
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
        ]
    },
    install_requires=[
        'lambda_uploader',
        'boto',
        'climax',
        'jinja2',
        'pyyaml',
        'virtualenv'
    ],
    tests_require=[],
    test_suite='test_slam',
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
