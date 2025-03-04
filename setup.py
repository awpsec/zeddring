from setuptools import setup, find_packages

setup(
    name="zeddring",
    version="0.1.0",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "flask>=2.2.3",
        "flask-cors>=3.0.10",
    ],
    dependency_links=[
        "git+https://github.com/tahnok/colmi_r02_client.git#egg=colmi_r02_client"
    ],
    entry_points={
        "console_scripts": [
            "zeddring=zeddring.app:main",
        ],
    },
) 