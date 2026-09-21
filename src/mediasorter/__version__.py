from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("multimediasorter")
except PackageNotFoundError:
    __version__ = "unknown"
