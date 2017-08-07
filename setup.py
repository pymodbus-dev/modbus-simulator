from setuptools import setup, find_packages


def install_requires():
    with open('requirements') as reqs:
        install_req = [
            line for line in reqs.read().split('\n')
        ]
    return install_req


def readme():
    with open("README.md") as f:
        return f.read()


setup(
    name="modbus_simulator",
    url="https://bitbucket.org/riptideio/modbus-simulator",
    version="1.0",
    description="Modbus Simulator using modbus_tk and kivy",
    long_description=readme(),
    keywords="Modbus Simulator",
    author="riptideio",
    packages=find_packages(),
    install_requires=install_requires(),
    entry_points={
        'console_scripts': [
            'modbus.simu = modbus_simulator.main:run',
        ],
    },
    include_package_data=True
)
