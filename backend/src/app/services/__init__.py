"""
Lazy-loading package init.

Accessing any of the names below triggers the import on first use,
so that importing submodules (e.g. app.services.warm_cache) does not
eagerly pull in the entire handler/processor/jobs chain.
"""

__all__ = [
    "BriefingService",
    "CalendarService",
    "DigestService",
    "PolarService",
    "ThreadStateService",
    "get_polar_service",
]

_lazy = {
    "BriefingService":  (".briefing",      "BriefingService"),
    "CalendarService":  (".calendar",      "CalendarService"),
    "DigestService":    (".digest",        "DigestService"),
    "PolarService":     (".polar",         "PolarService"),
    "get_polar_service":(".polar",         "get_polar_service"),
    "ThreadStateService":(".thread_state", "ThreadStateService"),
}


def __getattr__(name: str):
    if name in _lazy:
        module_path, attr = _lazy[name]
        import importlib
        mod = importlib.import_module(module_path, package=__name__)
        value = getattr(mod, attr)
        # Cache in module dict so subsequent access skips __getattr__
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
