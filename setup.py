from os import path

from setuptools import find_packages, setup

# requirements from requirements.txt
root_dir = path.dirname(path.abspath(__file__))
with open(path.join(root_dir, "requirements.txt"), "r") as f:
    requirements = f.read().splitlines()

# long description from README
with open(path.join(root_dir, "README.md"), encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="d3b-redcap-api",
    version="0.2.0",
    description="REDCap API interface",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/d3b-center/d3b-redcap-api-python",
    packages=setuptools.find_packages(),
    python_requires=">=3.6, <4",
    install_requires=requirements,
)
