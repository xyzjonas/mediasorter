from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("multimediasorter")
except PackageNotFoundError:
    __version__ = "unknown"