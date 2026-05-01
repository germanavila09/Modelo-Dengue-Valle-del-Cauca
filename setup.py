"""
Setup configuration for observatorio_geosalud package.

Install:
    pip install -e .
    pip install -e ".[dev]"  # with development dependencies
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text(encoding="utf-8") if readme_file.exists() else ""

# Read requirements
requirements_file = Path(__file__).parent / "requirements.txt"
requirements = (
    requirements_file.read_text(encoding="utf-8").strip().split("\n")
    if requirements_file.exists()
    else []
)
# Filter out comments and empty lines
requirements = [
    req.strip()
    for req in requirements
    if req.strip() and not req.strip().startswith("#")
]

setup(
    name="observatorio_geosalud",
    version="0.1.0",
    description="Análisis descriptivo espacial de dengue — Valle del Cauca, Colombia",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Germán Avila",
    author_email="germanavila09@gmail.com",
    url="https://github.com/germanavila09/Observatorio-GeoSalud",
    license="MIT",
    packages=find_packages(include=["src", "src.*"]),
    python_requires=">=3.10",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.0",
            "pytest-cov>=3.0",
            "black>=22.0",
            "flake8>=4.0",
            "mypy>=0.950",
            "jupyter>=1.0",
            "jupyterlab>=3.0",
        ],
        "gpu": [
            "torch>=2.0; sys_platform != 'win32'",
            "torch>=2.0; sys_platform == 'win32'",
        ],
    },
    entry_points={
        "console_scripts": [
            "geosalud-run=scripts.run_all:main",
            "geosalud-check=scripts.verificar_conexion:main",
        ],
    },
    include_package_data=True,
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Science/Research",
        "Intended Audience :: Healthcare Industry",
        "Topic :: Scientific/Engineering :: Bio-Informatics",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
    ],
    keywords=[
        "dengue",
        "epidemiology",
        "geospatial",
        "gis",
        "machine-learning",
        "time-series",
        "forecasting",
        "valle-del-cauca",
    ],
    project_urls={
        "Documentation": "https://github.com/germanavila09/Observatorio-GeoSalud",
        "Source": "https://github.com/germanavila09/Observatorio-GeoSalud",
        "Tracker": "https://github.com/germanavila09/Observatorio-GeoSalud/issues",
    },
)
