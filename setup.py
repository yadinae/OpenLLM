from setuptools import setup, find_packages

setup(
    name="openllm",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "fastapi>=0.109.0",
        "uvicorn[standard]>=0.27.0",
        "pydantic>=2.5.0",
        "httpx>=0.26.0",
        "python-dotenv>=1.0.0",
        "typer>=0.9.0",
        "pyyaml>=6.0.0",
        "tiktoken>=0.5.0",
    ],
    entry_points={
        "console_scripts": [
            "openllm=openllm.cli:main",
        ],
    },
    python_requires=">=3.10",
)
