from datetime import date

from iblrig import __version__

project = 'iblrig'
copyright = f'2018 – {date.today().year} International Brain Laboratory'
author = 'International Brain Laboratory'
version = '.'.join(__version__.split('.')[:3])

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = ['sphinx_lesson', 'sphinx.ext.autosectionlabel']
source_suffix = ['.rst', '.md']

templates_path = ['_templates']
exclude_patterns = []


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']
