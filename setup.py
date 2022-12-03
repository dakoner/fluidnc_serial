from setuptools import setup, find_packages


setup(
    name="fluidnc_serial",
    version="1.0",
    packages=find_packages("fluidnc_serial"),
    scripts=['scripts/fluidnc-serial']
)
