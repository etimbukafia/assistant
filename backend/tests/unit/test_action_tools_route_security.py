from fastapi.routing import APIRoute

from app.routes.v1 import action_tools


def test_meeting_brief_route_requires_active_subscription():
    route = next(
        item
        for item in action_tools.router.routes
        if isinstance(item, APIRoute) and item.path == "/action-tools/meeting-brief"
    )

    dependency_calls = [dependency.call for dependency in route.dependant.dependencies]
    assert action_tools.require_active_subscription in dependency_calls
