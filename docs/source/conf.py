from datetime import date

from iblrig import __version__
from iblrig.constants import BASE_PATH

project = 'iblrig'
copyright = f'2018 – {date.today().year} International Brain Laboratory'
author = 'International Brain Laboratory'
version = '.'.join(__version__.split('.')[:3])
release = '.'.join(__version__.split('.')[:3])

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = ['sphinx_lesson', 'sphinx.ext.autosectionlabel', 'sphinx_simplepdf']
autosectionlabel_prefix_document = True
source_suffix = ['.rst', '.md']

templates_path = ['_templates']
exclude_patterns = []


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']


simplepdf_vars = {
    'primary': '#FA2323',
    'secondary': '#379683',
    'cover': 'white',
    'cover-bg': 'linear-gradient(180deg, rgb(0, 81, 142) 0%, rgb(0, 158, 214) 50%, rgb(201, 53, 154) 100%)',
}
simplepdf_file_name = f'iblrig_{__version__}_reference.pdf'
simplepdf_weasyprint_flags = ['-j70', '-D150', '--hinting']
html_context = {
    'docs_scope': 'external',
    'cover_meta_data': 'International Brain Laboratory',
}
