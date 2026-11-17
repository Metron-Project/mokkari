"""The ``Session`` helpers that the endpoint mixins call.

This private module provides the following class:

- EndpointHelpers: The request, cache and validation helpers of ``Session`` the mixins use
"""

from __future__ import annotations

__all__ = ["EndpointHelpers"]

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from datetime import datetime

    from pydantic import BaseModel

    from mokkari.cache import CacheKind
    from mokkari.schemas.issue import BaseIssue


class EndpointHelpers(Protocol):
    """The helpers of ``Session`` that the endpoint mixins call.

    The mixins inherit this only while type checking, so they can call these helpers
    without importing ``mokkari.session``, which imports them. At runtime they inherit
    ``object`` and get the real helpers from ``Session``. ``mokkari.session`` checks that
    it still provides everything declared here. See ``Session`` for what each one does.
    """

    def _get(
        self,
        endpoint: list[str | int],
        params: dict[str, str | int] | None = None,
        *,
        kind: CacheKind = "detail",
    ) -> dict[str, Any]: ...

    def _get_results(
        self,
        endpoint: list[str | int],
        params: dict[str, str | int] | None = None,
        *,
        resource: str | None = None,
    ) -> dict[str, Any]: ...

    def _get_resource(
        self,
        resource_name: str,
        _id: int,
        response_class: type,
        if_modified_since: datetime | None = None,
    ) -> Any: ...

    def _post_resource(self, resource_name: str, data: BaseModel, response_class: type) -> Any: ...

    def _patch_resource(
        self, resource_name: str, _id: int, data: BaseModel, response_class: type
    ) -> Any: ...

    def _list_resources(
        self, resource_name: str, params: dict[str, str | int] | None, response_class: type
    ) -> list[Any]: ...

    def _get_resource_issues(self, resource_name: str, _id: int) -> list[BaseIssue]: ...

    def _handle_write_request(
        self,
        method: str,
        endpoint: list[str | int],
        data: BaseModel | list[Any],
        response_class: type,
        *,
        also_invalidates: tuple[str, ...] = (),
    ) -> Any: ...

    def _send_void(
        self,
        method: str,
        endpoint: list[str | int],
        data: BaseModel | None = None,
        *,
        also_invalidates: tuple[str, ...] = (),
    ) -> None: ...

    @staticmethod
    def _validate_response(resp: dict[str, Any], adapter_class: type) -> Any: ...

    @staticmethod
    def _validate_list_response(resp: dict[str, Any], item_class: type) -> list[Any]: ...
