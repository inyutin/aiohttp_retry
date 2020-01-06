from setuptools import find_packages, setup

setup(
    name='aiohttp_retry',
    version='0.1',
    description='Simple retry cient for aiohttp',
    long_description='',
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    keywords='aiohttp retry client',
    author='Dmitry Inyutin',
    author_email='inyutin.da@gmail.com',
    url='https://github.com/inyutin/aiohttp_retry',
    license='MIT',
    include_package_data=True,
    packages=find_packages(exclude=["tests", "tests.*"]),
    platforms=['any'],
    install_requires=[
        'aiohttp',
    ]
)
