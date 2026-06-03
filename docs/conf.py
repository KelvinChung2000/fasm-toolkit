"""Sphinx configuration for fasm-toolkit documentation."""

project = "fasm-toolkit"
copyright = "2026, Kelvin Chung"
author = "Kelvin Chung"

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "sphinx.ext.doctest",
]

autodoc_member_order = "bysource"
napoleon_numpy_docstring = True
myst_enable_extensions = ["colon_fence", "fieldlist"]

# Design specs live under docs/ for convenience but are not part of the rendered
# reference site; keep them (and stale build output) out of the toctree.
exclude_patterns = ["_build", "superpowers/**"]

html_theme = "sphinx_rtd_theme"

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}
