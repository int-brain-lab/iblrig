try:
    from _version import __version__
except ModuleNotFoundError:
    from importlib import metadata
    __version__ = metadata.version('iblrig')
