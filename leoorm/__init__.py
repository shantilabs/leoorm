from warnings import warn

try:
    from .core import LeoORM
except ModuleNotFoundError:
    warn('runtime compile')
    import pyximport
    pyximport.install()
    from .core import LeoORM
