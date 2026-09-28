import os
import re

from setuptools import setup

HERE = os.path.dirname(os.path.abspath(__file__))


def read(name):
    path = os.path.join(HERE, name)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return f.read()
    return ""


def read_version():
    """Версия берётся из dbd_github.py — единственного места, где она задана."""
    m = re.search(r'APP_VERSION\s*=\s*"([\d.]+)"', read("dbd_github.py"))
    return m.group(1) if m else "0.0.0"


def read_requirements():
    reqs = []
    for line in read("requirements.txt").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            reqs.append(line)
    return reqs


setup(
    name="dbd-randomizer",
    version=read_version(),
    description="DBD Ultimate Search Randomizer — рандомизатор билдов и авто-экипировка для Dead by Daylight",
    long_description=read("README.md"),
    long_description_content_type="text/markdown",
    author="yungspiderq",
    url="https://github.com/yungspiderq/dbd-randomizer",
    py_modules=["dbd_randomizer", "dbd_data", "dbd_github"],
    install_requires=read_requirements(),
    extras_require={"ocr": ["pytesseract>=0.3.10", "Pillow>=9.0.0"]},
    python_requires=">=3.8",
    entry_points={
        "gui_scripts": ["dbd-randomizer=dbd_randomizer:main"],
        "console_scripts": ["dbd-rand=dbd_randomizer:main"],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: Microsoft :: Windows",
        "Topic :: Games/Entertainment",
    ],
)
