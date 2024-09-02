import os
import sys
from datetime import date

sys.path.insert(0, os.path.abspath('../..'))
from iblrig import __version__


project = 'iblrig'
copyright = f'2018 – {date.today().year} International Brain Laboratory'
author = 'International Brain Laboratory'
version = '.'.join(__version__.split('.')[:3])
release = '.'.join(__version__.split('.')[:3])

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

templates_path = ['_templates']
extensions = [
    'sphinx_lesson',
    'sphinx.ext.autosectionlabel',
    'sphinx_simplepdf',
    'sphinx.ext.intersphinx',
    'sphinx.ext.napoleon',
    'sphinx.ext.autodoc',
    'sphinx.ext.autosummary',
    'sphinx.ext.inheritance_diagram',
    'sphinx.ext.viewcode',
]
autodoc_typehints = 'none'
autosummary_generate = True
autosummary_imported_members = False
autosectionlabel_prefix_document = True
source_suffix = ['.rst', '.md']
exclude_patterns = []
intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
    'sphinx': ('https://www.sphinx-doc.org/en/master/', None),
    'matplotlib': ('https://matplotlib.org/stable/', None),
    'numpy': ('https://numpy.org/doc/stable/', None),
    'pandas': ('https://pandas.pydata.org/docs/', None),
    'scipy': ('https://docs.scipy.org/doc/scipy/', None),
    'one:': ('https://int-brain-lab.github.io/ONE/', None),
    'pydantic': ('https://docs.pydantic.dev/latest/', None),
    'iblenv': ('https://int-brain-lab.github.io/iblenv/', None),
    'pyserial': ('https://pyserial.readthedocs.io/en/latest/', None),
    'Sphinx': ('https://www.sphinx-doc.org/en/master/', None),
}

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_rtd_theme'

simplepdf_vars = {
    'primary': '#004f8c',
    'secondary': '#004f8c',
    'cover': 'white',
    'cover-bg': 'linear-gradient(180deg, #004f8c 0%, #00a1d9 50%, #cc3399 100%)',
}
simplepdf_file_name = f'iblrig_{__version__}_reference.pdf'
simplepdf_weasyprint_flags = ['-j70', '-D150', '--hinting']
html_context = {
    'docs_scope': 'external',
    'cover_meta_data': 'International Brain Laboratory',
}

# -- Napoleon Settings -------------------------------------------------------
napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = True
napoleon_include_special_with_doc = False
napoleon_use_admonition_for_examples = True
napoleon_use_admonition_for_notes = True
napoleon_use_admonition_for_references = True
napoleon_use_ivar = True
napoleon_use_param = True
napoleon_use_rtype = True
napoleon_preprocess_types = True
napoleon_type_aliases = None
napoleon_attr_annotations = True
