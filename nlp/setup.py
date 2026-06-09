from setuptools import setup, find_packages

setup(
    name="ai-ecommerce-nlp",
    version="0.1.0",
    description="NLP models for AI E-commerce Review Analysis System",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.10",
    install_requires=[
        "torch>=2.1.0",
        "transformers>=4.37.0",
        "datasets>=2.16.0",
        "numpy>=1.24.0",
        "pandas>=2.0.0",
        "scikit-learn>=1.3.0",
        "jieba>=0.42.1",
        "onnxruntime>=1.16.0",
    ],
    extras_require={
        "gpu": ["bitsandbytes>=0.42.0", "accelerate>=0.27.0"],
        "train": ["tensorboard>=2.15.0", "evaluate>=0.4.0"],
        "dev": ["jupyter>=1.0.0", "matplotlib>=3.7.0", "seaborn>=0.13.0"],
    },
)
