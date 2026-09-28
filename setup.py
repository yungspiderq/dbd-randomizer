import os
from setuptools import setup


def read_requirements():
    path = os.path.join(os.path.dirname(__file__), "requirements.txt")
    reqs = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    reqs.append(line)
    return reqs


def read_long_description():
    path = os.path.join(os.path.dirname(__file__), "README.md")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return f.read()
    return ""


setup(
    name="dbd-randomizer",
    version="1.1.1",
    description="DBD Ultimate Search Randomizer — рандомайзер билдов и авто-экипировка для Dead by Daylight",
    long_description=read_long_description(),
    long_description_content_type="text/markdown",
    author="yungspiderq",
    url="https://github.com/yungspiderq/dbd-randomizer",
    py_modules=["dbd_randomizer"],
    install_requires=read_requirements(),
    python_requires=">=3.8",
    entry_points={
        "gui_scripts": [
            "dbd-randomizer=dbd_randomizer:main",
        ],
        "console_scripts": [
            "dbd-rand=dbd_randomizer:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: Microsoft :: Windows",
        "Topic :: Games/Entertainment",
    ],
)
