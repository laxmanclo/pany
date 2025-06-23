from setuptools import setup, find_packages
import os

# Read README for long description
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Read requirements
with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

# Get version
version = "1.0.0"
if os.path.exists("pany/__init__.py"):
    with open("pany/__init__.py", "r") as f:
        for line in f:
            if line.startswith("__version__"):
                version = line.split("=")[1].strip().strip('"').strip("'")
                break

setup(
    name="pany",
    version=version,
    author="Pany Team",
    author_email="hello@pany.ai",
    description="PostgreSQL-native semantic search engine with multi-modal support",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/your-org/pany",
    packages=find_packages(exclude=["tests*", "embedding-service*"]),
    include_package_data=True,
    py_modules=["pany_sdk"],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Database",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Framework :: FastAPI",
    ],
    keywords="semantic-search, vector-database, postgresql, embedding, similarity-search, multimodal, rag",
    python_requires=">=3.9",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "black>=22.0.0",
            "flake8>=4.0.0",
            "mypy>=0.950",
            "pre-commit>=2.20.0",
        ],
        "api": [
            "fastapi>=0.100.0",
            "uvicorn[standard]>=0.23.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "pany=pany.main:main",
            "pany-server=pany.main:main",
        ],
    },
    project_urls={
        "Documentation": "https://github.com/your-org/pany/blob/main/README.md",
        "Source": "https://github.com/your-org/pany",
        "Tracker": "https://github.com/your-org/pany/issues",
    },
)
