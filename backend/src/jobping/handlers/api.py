from __future__ import annotations

from .. import api
from .common import store


def handler(event, context):
    return api.route(store(), event)
