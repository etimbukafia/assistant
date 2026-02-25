"""
Lazy-loading package init.

Accessing any of the names below triggers the import on first use,
so that importing submodules (e.g. app.services.warm_cache) does not
eagerly pull in the entire handler/processor/jobs chain.
"""

__all__ = [
    "BillingProvider",
    "ensure_billing_plan",
    "ensure_configured_plans",
    "get_billing_provider",
    "BriefingService",
    "CalendarService",
    "DodoService",
    "DigestService",
    "PolarService",
    "ThreadStateService",
    "get_dodo_service",
    "get_polar_service",
]

_lazy = {
    "BillingProvider":  (".billing_provider", "BillingProvider"),
    "ensure_billing_plan": (".billing_ledger", "ensure_billing_plan"),
    "ensure_configured_plans": (".billing_ledger", "ensure_configured_plans"),
    "BriefingService":  (".briefing",      "BriefingService"),
    "CalendarService":  (".calendar",      "CalendarService"),
    "DodoService":      (".dodo",          "DodoService"),
    "DigestService":    (".digest",        "DigestService"),
    "get_billing_provider":(".billing_provider", "get_billing_provider"),
    "get_dodo_service": (".dodo",          "get_dodo_service"),
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
