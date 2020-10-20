import pathlib
from setuptools import find_packages, setup


HERE = pathlib.Path(__file__).parent


def read(f):
    return (HERE / f).read_text('utf-8').strip()


setup(
    name='aiohttp_retry',
    version='1.1',
    description='Simple retry cient for aiohttp',
    long_description=read('README.rst'),
    long_description_content_type="text/x-rst",
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
