from setuptools import find_packages, setup


with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()


setup(
    name='aiohttp_retry',
    version='2.4.5',
    description='Simple retry client for aiohttp',
    long_description=long_description,
    long_description_content_type="text/markdown",
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
