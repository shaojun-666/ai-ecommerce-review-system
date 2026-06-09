"""NLP module package.

Sub-modules with heavy dependencies (torch, transformers) are imported
lazily to allow testing of lightweight utilities without installing them.
"""
