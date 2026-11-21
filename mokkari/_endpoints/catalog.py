"""Catalog endpoints for ``Session``.

This module provides the following class:

- CatalogEndpoints: Creators, characters, publishers, teams, arcs, series, issues, universes and imprints.
"""

from __future__ import annotations

__all__ = ["CatalogEndpoints"]

# Imported at runtime, not only for type checking, so typing.get_type_hints() can
# resolve the detail methods' if_modified_since annotations.
from datetime import datetime  # noqa: TC003
from typing import TYPE_CHECKING, overload

from mokkari.cache import ResourceEndpoint
from mokkari.schemas.arc import Arc, ArcPost
from mokkari.schemas.base import BaseResource
from mokkari.schemas.character import Character, CharacterPost, CharacterPostResponse
from mokkari.schemas.creator import Creator, CreatorPost
from mokkari.schemas.generic import GenericItem
from mokkari.schemas.imprint import Imprint
from mokkari.schemas.issue import (
    BaseIssue,
    CoverMatch,
    CreditPost,
    CreditPostResponse,
    Issue,
    IssuePost,
    IssuePostResponse,
)
from mokkari.schemas.publisher import Publisher, PublisherPost
from mokkari.schemas.series import BaseSeries, Series, SeriesPost, SeriesPostResponse
from mokkari.schemas.team import Team, TeamPost, TeamPostResponse
from mokkari.schemas.universe import Universe, UniversePost, UniversePostResponse
from mokkari.schemas.variant import VariantPost, VariantPostResponse
from mokkari.utils import _COVER_HASH_RE, hamming_distance

if TYPE_CHECKING:
    from mokkari._endpoints._helpers import EndpointHelpers as _Base
else:
    _Base = object


class CatalogEndpoints(_Base):
    """Creators, characters, publishers, teams, arcs, series, issues, universes and imprints methods of ``Session``.

    A mixin: it relies on the request, cache and validation helpers of ``Session``
    (see ``EndpointHelpers``).
    """

    # Creator methods
    @overload
    def creator(self, _id: int, if_modified_since: None = None) -> Creator: ...
    @overload
    def creator(self, _id: int, if_modified_since: datetime) -> Creator | None: ...
    def creator(self, _id: int, if_modified_since: datetime | None = None) -> Creator | None:
        """Retrieve detailed information about a creator by ID.

        Args:
            _id: The unique identifier for the creator.
            if_modified_since: Optional datetime for conditional requests. When provided,
                the server may return 304 Not Modified and this method returns ``None``.
                Typically you would pass a previously fetched creator's ``modified`` field.

        Returns:
            A Creator object, or ``None`` if the resource has not been modified.

        Raises:
            ApiError: If the creator is not found or if there's an API error.
            RateLimitError: If the Metron API rate limit has been exceeded.

        Examples:
            >>> session = Session("your-api-token")
            >>> creator = session.creator(1)
            >>> print(creator.name)
            >>> # Later, check if updated:
            >>> updated = session.creator(1, if_modified_since=creator.modified)
            >>> if updated is None:
            ...     print("Not modified")
        """
        return self._get_resource(ResourceEndpoint.CREATOR, _id, Creator, if_modified_since)

    def creator_post(self, data: CreatorPost) -> Creator:
        """Create a new creator in the database.

        Note: This function requires Admin permissions at Metron.

        Args:
            data: CreatorPost object containing the creator information to create.

        Returns:
            Creator: The newly created Creator object.

        Raises:
            ApiError: If creation fails or if user lacks permissions.
            RateLimitError: If the Metron API rate limit has been exceeded.

        Examples:
            >>> session = Session("your-api-token")
            >>> creator_data = CreatorPost(name="Jane Doe", birth_date="1980-01-01")
            >>> new_creator = session.creator_post(creator_data)
        """
        return self._post_resource(ResourceEndpoint.CREATOR, data, Creator)

    def creator_patch(self, _id: int, data: CreatorPost) -> Creator:
        """Update an existing creator in the database.

        Note: This function requires Admin permissions at Metron.

        Args:
            _id: The unique identifier for the creator to update.
            data: CreatorPost object containing the updated creator information.

        Returns:
            Creator: The updated Creator object.

        Raises:
            ApiError: If update fails or if user lacks permissions.
            RateLimitError: If the Metron API rate limit has been exceeded.

        Examples:
            >>> session = Session("your-api-token")
            >>> creator_data = CreatorPost(name="Jane Doe", birth_date="1980-01-01")
            >>> updated_creator = session.creator_patch(1, creator_data)
        """
        return self._patch_resource(ResourceEndpoint.CREATOR, _id, data, Creator)

    def creators_list(self, params: dict[str, str | int] | None = None) -> list[BaseResource]:
        """Retrieve a list of creators with optional filtering.

        Args:
            params: Optional dictionary of query parameters for filtering results.
                   Common parameters include 'name', 'modified_gt', 'modified_lt'.

        Returns:
            list[BaseResource]: A list of BaseResource objects representing creators.

        Examples:
            >>> session = Session("your-api-token")
            >>> creators = session.creators_list({"name": "Stan Lee"})
            >>> all_creators = session.creators_list()
        """
        return self._list_resources(ResourceEndpoint.CREATOR, params, BaseResource)

    # Character methods
    @overload
    def character(self, _id: int, if_modified_since: None = None) -> Character: ...
    @overload
    def character(self, _id: int, if_modified_since: datetime) -> Character | None: ...
    def character(self, _id: int, if_modified_since: datetime | None = None) -> Character | None:
        """Retrieve detailed information about a character by ID.

        Args:
            _id: The unique identifier for the character.
            if_modified_since: Optional datetime for conditional requests. When provided,
                the server may return 304 Not Modified and this method returns ``None``.

        Returns:
            A Character object, or ``None`` if the resource has not been modified.

        Raises:
            ApiError: If the character is not found or if there's an API error.
            RateLimitError: If the Metron API rate limit has been exceeded.

        Examples:
            >>> session = Session("your-api-token")
            >>> character = session.character(1)
            >>> print(character.name)
        """
        return self._get_resource(ResourceEndpoint.CHARACTER, _id, Character, if_modified_since)

    def character_post(self, data: CharacterPost) -> CharacterPostResponse:
        """Create a new character in the database.

        Note: This function requires Admin permissions at Metron.

        Args:
            data: CharacterPost object containing the character information to create.

        Returns:
            CharacterPostResponse: The newly created character response.

        Raises:
            ApiError: If creation fails or if user lacks permissions.
        """
        return self._post_resource(ResourceEndpoint.CHARACTER, data, CharacterPostResponse)

    def character_patch(self, _id: int, data: CharacterPost) -> CharacterPostResponse:
        """Update an existing character in the database.

        Note: This function requires Admin permissions at Metron.

        Args:
            _id: The unique identifier for the character to update.
            data: CharacterPost object containing the updated character information.

        Returns:
            CharacterPostResponse: The updated character response.

        Raises:
            ApiError: If update fails or if user lacks permissions.
        """
        return self._patch_resource(ResourceEndpoint.CHARACTER, _id, data, CharacterPostResponse)

    def characters_list(self, params: dict[str, str | int] | None = None) -> list[BaseResource]:
        """Retrieve a list of characters with optional filtering.

        Args:
            params: Optional dictionary of query parameters for filtering results.
                   Common parameters include 'name', 'modified_gt', 'modified_lt'.

        Returns:
            list[BaseResource]: A list of BaseResource objects representing characters.
        """
        return self._list_resources(ResourceEndpoint.CHARACTER, params, BaseResource)

    def character_issues_list(self, _id: int) -> list[BaseIssue]:
        """Retrieve a list of issues featuring a specific character.

        Args:
            _id: The unique identifier for the character.

        Returns:
            list[BaseIssue]: A list of BaseIssue objects.

        Examples:
            >>> session = Session("your-api-token")
            >>> issues = session.character_issues_list(1)
            >>> print(f"Character appears in {len(issues)} issues")
        """
        return self._get_resource_issues(ResourceEndpoint.CHARACTER, _id)

    # Publisher methods
    @overload
    def publisher(self, _id: int, if_modified_since: None = None) -> Publisher: ...
    @overload
    def publisher(self, _id: int, if_modified_since: datetime) -> Publisher | None: ...
    def publisher(self, _id: int, if_modified_since: datetime | None = None) -> Publisher | None:
        """Retrieve detailed information about a publisher by ID.

        Args:
            _id: The unique identifier for the publisher.
            if_modified_since: Optional datetime for conditional requests. When provided,
                the server may return 304 Not Modified and this method returns ``None``.

        Returns:
            A Publisher object, or ``None`` if the resource has not been modified.

        Raises:
            ApiError: If the publisher is not found or if there's an API error.
            RateLimitError: If the Metron API rate limit has been exceeded.
        """
        return self._get_resource(ResourceEndpoint.PUBLISHER, _id, Publisher, if_modified_since)

    def publisher_post(self, data: PublisherPost) -> Publisher:
        """Create a new publisher in the database.

        Note: This function requires Admin permissions at Metron.

        Args:
            data: PublisherPost object containing the publisher information to create.

        Returns:
            Publisher: The newly created Publisher object.

        Raises:
            ApiError: If creation fails or if user lacks permissions.
        """
        return self._post_resource(ResourceEndpoint.PUBLISHER, data, Publisher)

    def publisher_patch(self, _id: int, data: PublisherPost) -> Publisher:
        """Update an existing publisher in the database.

        Note: This function requires Admin permissions at Metron.

        Args:
            _id: The unique identifier for the publisher to update.
            data: PublisherPost object containing the updated publisher information.

        Returns:
            Publisher: The updated Publisher object.

        Raises:
            ApiError: If update fails or if user lacks permissions.
        """
        return self._patch_resource(ResourceEndpoint.PUBLISHER, _id, data, Publisher)

    def publishers_list(self, params: dict[str, str | int] | None = None) -> list[BaseResource]:
        """Retrieve a list of publishers with optional filtering.

        Args:
            params: Optional dictionary of query parameters for filtering results.
                   Common parameters include 'name', 'modified_gt', 'modified_lt'.

        Returns:
            list[BaseResource]: A list of BaseResource objects representing publishers.
        """
        return self._list_resources(ResourceEndpoint.PUBLISHER, params, BaseResource)

    # Team methods
    @overload
    def team(self, _id: int, if_modified_since: None = None) -> Team: ...
    @overload
    def team(self, _id: int, if_modified_since: datetime) -> Team | None: ...
    def team(self, _id: int, if_modified_since: datetime | None = None) -> Team | None:
        """Retrieve detailed information about a team by ID.

        Args:
            _id: The unique identifier for the team.
            if_modified_since: Optional datetime for conditional requests. When provided,
                the server may return 304 Not Modified and this method returns ``None``.

        Returns:
            A Team object, or ``None`` if the resource has not been modified.

        Raises:
            ApiError: If the team is not found or if there's an API error.
            RateLimitError: If the Metron API rate limit has been exceeded.
        """
        return self._get_resource(ResourceEndpoint.TEAM, _id, Team, if_modified_since)

    def team_post(self, data: TeamPost) -> TeamPostResponse:
        """Create a new team in the database.

        Note: This function requires Admin permissions at Metron.

        Args:
            data: TeamPost object containing the team information to create.

        Returns:
            TeamPostResponse: The newly created team response.

        Raises:
            ApiError: If creation fails or if user lacks permissions.
            RateLimitError: If the Metron API rate limit has been exceeded.
        """
        return self._post_resource(ResourceEndpoint.TEAM, data, TeamPostResponse)

    def team_patch(self, _id: int, data: TeamPost) -> TeamPostResponse:
        """Update an existing team in the database.

        Note: This function requires Admin permissions at Metron.

        Args:
            _id: The unique identifier for the team to update.
            data: TeamPost object containing the updated team information.

        Returns:
            TeamPostResponse: The updated team response.

        Raises:
            ApiError: If update fails or if user lacks permissions.
            RateLimitError: If the Metron API rate limit has been exceeded.
        """
        return self._patch_resource(ResourceEndpoint.TEAM, _id, data, TeamPostResponse)

    def teams_list(self, params: dict[str, str | int] | None = None) -> list[BaseResource]:
        """Retrieve a list of teams with optional filtering.

        Args:
            params: Optional dictionary of query parameters for filtering results.
                   Common parameters include 'name', 'modified_gt', 'modified_lt'.

        Returns:
            list[BaseResource]: A list of BaseResource objects representing teams.
        """
        return self._list_resources(ResourceEndpoint.TEAM, params, BaseResource)

    def team_issues_list(self, _id: int) -> list[BaseIssue]:
        """Retrieve a list of issues featuring a specific team.

        Args:
            _id: The unique identifier for the team.

        Returns:
            list[BaseIssue]: A list of BaseIssue objects.
        """
        return self._get_resource_issues(ResourceEndpoint.TEAM, _id)

    # Arc methods
    @overload
    def arc(self, _id: int, if_modified_since: None = None) -> Arc: ...
    @overload
    def arc(self, _id: int, if_modified_since: datetime) -> Arc | None: ...
    def arc(self, _id: int, if_modified_since: datetime | None = None) -> Arc | None:
        """Retrieve detailed information about a story arc by ID.

        Args:
            _id: The unique identifier for the arc.
            if_modified_since: Optional datetime for conditional requests. When provided,
                the server may return 304 Not Modified and this method returns ``None``.

        Returns:
            An Arc object, or ``None`` if the resource has not been modified.

        Raises:
            ApiError: If the arc is not found or if there's an API error.
            RateLimitError: If the Metron API rate limit has been exceeded.
        """
        return self._get_resource(ResourceEndpoint.ARC, _id, Arc, if_modified_since)

    def arc_post(self, data: ArcPost) -> Arc:
        """Create a new story arc in the database.

        Note: This function requires Admin permissions at Metron.

        Args:
            data: ArcPost object containing the arc information to create.

        Returns:
            Arc: The newly created Arc object.

        Raises:
            ApiError: If creation fails or if user lacks permissions.
            RateLimitError: If the Metron API rate limit has been exceeded.
        """
        return self._post_resource(ResourceEndpoint.ARC, data, Arc)

    def arc_patch(self, _id: int, data: ArcPost) -> Arc:
        """Update an existing story arc in the database.

        Note: This function requires Admin permissions at Metron.

        Args:
            _id: The unique identifier for the arc to update.
            data: ArcPost object containing the updated arc information.

        Returns:
            Arc: The updated Arc object.

        Raises:
            ApiError: If update fails or if user lacks permissions.
            RateLimitError: If the Metron API rate limit has been exceeded.
        """
        return self._patch_resource(ResourceEndpoint.ARC, _id, data, Arc)

    def arcs_list(self, params: dict[str, str | int] | None = None) -> list[BaseResource]:
        """Retrieve a list of story arcs with optional filtering.

        Args:
            params: Optional dictionary of query parameters for filtering results.
                   Common parameters include 'name', 'modified_gt', 'modified_lt'.

        Returns:
            list[BaseResource]: A list of BaseResource objects representing arcs.
        """
        return self._list_resources(ResourceEndpoint.ARC, params, BaseResource)

    def arc_issues_list(self, _id: int) -> list[BaseIssue]:
        """Retrieve a list of issues that are part of a specific story arc.

        Args:
            _id: The unique identifier for the arc.

        Returns:
            list[BaseIssue]: A list of BaseIssue objects.
        """
        return self._get_resource_issues(ResourceEndpoint.ARC, _id)

    # Series methods
    @overload
    def series(self, _id: int, if_modified_since: None = None) -> Series: ...
    @overload
    def series(self, _id: int, if_modified_since: datetime) -> Series | None: ...
    def series(self, _id: int, if_modified_since: datetime | None = None) -> Series | None:
        """Retrieve detailed information about a series by ID.

        Args:
            _id: The unique identifier for the series.
            if_modified_since: Optional datetime for conditional requests. When provided,
                the server may return 304 Not Modified and this method returns ``None``.

        Returns:
            A Series object, or ``None`` if the resource has not been modified.

        Raises:
            ApiError: If the series is not found or if there's an API error.
            RateLimitError: If the Metron API rate limit has been exceeded.
        """
        return self._get_resource(ResourceEndpoint.SERIES, _id, Series, if_modified_since)

    def series_post(self, data: SeriesPost) -> SeriesPostResponse:
        """Create a new series in the database.

        Note: This function requires Admin permissions at Metron.

        Args:
            data: SeriesPost object containing the series information to create.

        Returns:
            SeriesPostResponse: The newly created series response.

        Raises:
            ApiError: If creation fails or if user lacks permissions.
            RateLimitError: If the Metron API rate limit has been exceeded.
        """
        return self._post_resource(ResourceEndpoint.SERIES, data, SeriesPostResponse)

    def series_patch(self, _id: int, data: SeriesPost) -> SeriesPostResponse:
        """Update an existing series in the database.

        Note: This function requires Admin permissions at Metron.

        Args:
            _id: The unique identifier for the series to update.
            data: SeriesPost object containing the updated series information.

        Returns:
            SeriesPostResponse: The updated series response.

        Raises:
            ApiError: If update fails or if user lacks permissions.
            RateLimitError: If the Metron API rate limit has been exceeded.
        """
        return self._patch_resource(ResourceEndpoint.SERIES, _id, data, SeriesPostResponse)

    def series_list(self, params: dict[str, str | int] | None = None) -> list[BaseSeries]:
        """Retrieve a list of series with optional filtering.

        Args:
            params: Optional dictionary of query parameters for filtering results.
                   Common parameters include 'name', 'publisher', 'year_began', 'modified_gt', 'modified_lt'.

        Returns:
            list[BaseSeries]: A list of BaseSeries objects representing series.
        """
        return self._list_resources(ResourceEndpoint.SERIES, params, BaseSeries)

    def series_issues_list(self, _id: int) -> list[BaseIssue]:
        """Retrieve a list of issues that are part of a specific series.

        Args:
            _id: The unique identifier for the series.

        Returns:
            list[BaseIssue]: A list of BaseIssue objects.
        """
        return self._get_resource_issues(ResourceEndpoint.SERIES, _id)

    def series_type_list(self, params: dict[str, str | int] | None = None) -> list[GenericItem]:
        """Retrieve a list of available series types.

        Args:
            params: Optional dictionary of query parameters for filtering results.

        Returns:
            list[GenericItem]: A list of GenericItem objects representing series types.
        """
        resp = self._get_results([ResourceEndpoint.SERIES_TYPE], params)
        return self._validate_list_response(resp, GenericItem)

    # Issue methods
    @overload
    def issue(self, _id: int, if_modified_since: None = None) -> Issue: ...
    @overload
    def issue(self, _id: int, if_modified_since: datetime) -> Issue | None: ...
    def issue(self, _id: int, if_modified_since: datetime | None = None) -> Issue | None:
        """Retrieve detailed information about an issue by ID.

        Args:
            _id: The unique identifier for the issue.
            if_modified_since: Optional datetime for conditional requests. When provided,
                the server may return 304 Not Modified and this method returns ``None``.

        Returns:
            An Issue object, or ``None`` if the resource has not been modified.

        Raises:
            ApiError: If the issue is not found or if there's an API error.
            RateLimitError: If the Metron API rate limit has been exceeded.

        Examples:
            >>> session = Session("your-api-token")
            >>> issue = session.issue(1)
            >>> print(f"Issue #{issue.number} of {issue.series.name}")
            >>> # Later, check if updated:
            >>> updated = session.issue(1, if_modified_since=issue.modified)
            >>> if updated is None:
            ...     print("Not modified")
        """
        return self._get_resource(ResourceEndpoint.ISSUE, _id, Issue, if_modified_since)

    def issue_post(self, data: IssuePost) -> IssuePostResponse:
        """Create a new issue in the database.

        Note: This function requires Admin permissions at Metron.

        Args:
            data: IssuePost object containing the issue information to create.

        Returns:
            IssuePostResponse: The newly created issue response.

        Raises:
            ApiError: If creation fails or if user lacks permissions.
            RateLimitError: If the Metron API rate limit has been exceeded.
        """
        return self._post_resource(ResourceEndpoint.ISSUE, data, IssuePostResponse)

    def issue_patch(self, _id: int, data: IssuePost) -> IssuePostResponse:
        """Update an existing issue in the database.

        Note: This function requires Admin permissions at Metron.

        Args:
            _id: The unique identifier for the issue to update.
            data: IssuePost object containing the updated issue information.

        Returns:
            IssuePostResponse: The updated issue response.

        Raises:
            ApiError: If update fails or if user lacks permissions.
            RateLimitError: If the Metron API rate limit has been exceeded.
        """
        return self._patch_resource(ResourceEndpoint.ISSUE, _id, data, IssuePostResponse)

    def issues_list(self, params: dict[str, str | int] | None = None) -> list[BaseIssue]:
        """Retrieve a list of issues with optional filtering.

        Args:
            params: Optional dictionary of query parameters for filtering results.
                   Common parameters include 'series', 'number', 'cover_date', 'modified_gt', 'modified_lt'.

        Returns:
            list[BaseIssue]: A list of BaseIssue objects representing issues.

        Examples:
            >>> session = Session("your-api-token")
            >>> issues = session.issues_list({"series": 1})
            >>> recent_issues = session.issues_list({"modified_gt": "2023-01-01"})
        """
        return self._list_resources(ResourceEndpoint.ISSUE, params, BaseIssue)

    def issues_by_cover_hash(
        self,
        cover_hash: str,
        max_distance: int | None = None,
        params: dict[str, str | int] | None = None,
    ) -> list[CoverMatch]:
        """Retrieve the issues whose covers are near a perceptual hash.

        Metron returns the matches closest first but doesn't say how close each is, so
        the distance is worked out from each issue's ``cover_hash``.

        Args:
            cover_hash: The cover's 64-bit perceptual hash (pHash) as 16 hex digits.
                Surrounding whitespace is stripped.
            max_distance: The widest Hamming distance to return, at most
                ``mokkari.utils.MAX_COVER_HASH_DISTANCE``. ``None`` leaves it to Metron,
                which uses ``mokkari.utils.DEFAULT_COVER_HASH_DISTANCE``.
            params: Further ``issues_list()`` filters to narrow the search by, such as
                ``series_id`` or ``number``.

        Returns:
            list[CoverMatch]: Every match in Metron's order, closest first, with its distance.

        Raises:
            ValueError: If ``cover_hash`` isn't 16 hex digits.
            ApiError: If Metron refuses a value, such as a distance out of range, or the
                request fails.
            RateLimitError: If the Metron API rate limit has been exceeded.

        Examples:
            >>> session = Session("your-api-token")
            >>> matches = session.issues_by_cover_hash("c3a1e1f0f8d8c0c0", max_distance=6)
            >>> exact = [m.issue for m in matches if m.distance == 0]
        """
        cover_hash = cover_hash.strip()
        if not _COVER_HASH_RE.fullmatch(cover_hash):
            msg = f"cover_hash must be 16 hex digits, got {cover_hash!r}"
            raise ValueError(msg)
        query: dict[str, str | int] = dict(params or {})
        if max_distance is not None:
            query["cover_hash_max_distance"] = max_distance
        query["cover_hash_near"] = cover_hash
        return [
            CoverMatch(issue=issue, distance=hamming_distance(cover_hash, issue.cover_hash))
            for issue in self.issues_list(query)
        ]

    def credits_post(self, data: list[CreditPost]) -> list[CreditPostResponse]:
        """Create new credits for issues in bulk.

        Note: This function requires Admin permissions at Metron.

        Args:
            data: List of CreditPost objects containing credit information to create.

        Returns:
            list[CreditPostResponse]: A list of newly created credit responses.

        Raises:
            ApiError: If creation fails or if user lacks permissions.
            RateLimitError: If the Metron API rate limit has been exceeded.

        Examples:
            >>> session = Session("your-api-token")
            >>> credits_ = [CreditPost(issue=1, creator=1, role=[1])]
            >>> new_credits = session.credits_post(credits_)
        """
        # Credits are read back as part of their issue.
        return self._handle_write_request(
            "POST",
            ["credit"],
            data,
            list[CreditPostResponse],
            also_invalidates=(ResourceEndpoint.ISSUE,),
        )

    def variant_post(self, data: VariantPost) -> VariantPostResponse:
        """Create a new variant cover for an issue.

        Note: This function requires Admin permissions at Metron.

        Args:
            data: VariantPost object containing the variant cover information to create.

        Returns:
            VariantPostResponse: The newly created variant cover response.

        Raises:
            ApiError: If creation fails or if user lacks permissions.
            RateLimitError: If the Metron API rate limit has been exceeded.
        """
        # Variants are read back as part of their issue.
        return self._handle_write_request(
            "POST",
            ["variant"],
            data,
            VariantPostResponse,
            also_invalidates=(ResourceEndpoint.ISSUE,),
        )

    def role_list(self, params: dict[str, str | int] | None = None) -> list[GenericItem]:
        """Retrieve a list of available creator roles.

        Args:
            params: Optional dictionary of query parameters for filtering results.

        Returns:
            list[GenericItem]: A list of GenericItem objects representing creator roles
                              (e.g., Writer, Artist, Colorist, etc.).
        """
        resp = self._get_results([ResourceEndpoint.ROLE], params)
        return self._validate_list_response(resp, GenericItem)

    # Universe methods
    @overload
    def universe(self, _id: int, if_modified_since: None = None) -> Universe: ...
    @overload
    def universe(self, _id: int, if_modified_since: datetime) -> Universe | None: ...
    def universe(self, _id: int, if_modified_since: datetime | None = None) -> Universe | None:
        """Retrieve detailed information about a universe by ID.

        Args:
            _id: The unique identifier for the universe.
            if_modified_since: Optional datetime for conditional requests. When provided,
                the server may return 304 Not Modified and this method returns ``None``.

        Returns:
            A Universe object, or ``None`` if the resource has not been modified.

        Raises:
            ApiError: If the universe is not found or if there's an API error.
            RateLimitError: If the Metron API rate limit has been exceeded.
        """
        return self._get_resource(ResourceEndpoint.UNIVERSE, _id, Universe, if_modified_since)

    def universe_post(self, data: UniversePost) -> UniversePostResponse:
        """Create a new universe in the database.

        Note: This function requires Admin permissions at Metron.

        Args:
            data: UniversePost object containing the universe information to create.

        Returns:
            UniversePostResponse: The newly created universe response.

        Raises:
            ApiError: If creation fails or if user lacks permissions.
            RateLimitError: If the Metron API rate limit has been exceeded.
        """
        return self._post_resource(ResourceEndpoint.UNIVERSE, data, UniversePostResponse)

    def universe_patch(self, _id: int, data: UniversePost) -> UniversePostResponse:
        """Update an existing universe in the database.

        Note: This function requires Admin permissions at Metron.

        Args:
            _id: The unique identifier for the universe to update.
            data: UniversePost object containing the updated universe information.

        Returns:
            UniversePostResponse: The updated universe response.

        Raises:
            ApiError: If update fails or if user lacks permissions.
            RateLimitError: If the Metron API rate limit has been exceeded.
        """
        return self._patch_resource(ResourceEndpoint.UNIVERSE, _id, data, UniversePostResponse)

    def universes_list(self, params: dict[str, str | int] | None = None) -> list[BaseResource]:
        """Retrieve a list of universes with optional filtering.

        Args:
            params: Optional dictionary of query parameters for filtering results.
                   Common parameters include 'name', 'modified_gt', 'modified_lt'.

        Returns:
            list[BaseResource]: A list of BaseResource objects representing universes.
        """
        return self._list_resources(ResourceEndpoint.UNIVERSE, params, BaseResource)

    # Imprint methods
    @overload
    def imprint(self, _id: int, if_modified_since: None = None) -> Imprint: ...
    @overload
    def imprint(self, _id: int, if_modified_since: datetime) -> Imprint | None: ...
    def imprint(self, _id: int, if_modified_since: datetime | None = None) -> Imprint | None:
        """Retrieve detailed information about an imprint by ID.

        Args:
            _id: The unique identifier for the imprint.
            if_modified_since: Optional datetime for conditional requests. When provided,
                the server may return 304 Not Modified and this method returns ``None``.

        Returns:
            An Imprint object, or ``None`` if the resource has not been modified.

        Raises:
            ApiError: If the imprint is not found or if there's an API error.
            RateLimitError: If the Metron API rate limit has been exceeded.
        """
        return self._get_resource(ResourceEndpoint.IMPRINT, _id, Imprint, if_modified_since)

    def imprints_list(self, params: dict[str, str | int] | None = None) -> list[BaseResource]:
        """Retrieve a list of imprints with optional filtering.

        Args:
            params: Optional dictionary of query parameters for filtering results.
                   Common parameters include 'name', 'publisher', 'modified_gt', 'modified_lt'.

        Returns:
            list[BaseResource]: A list of BaseResource objects representing imprints.
        """
        return self._list_resources(ResourceEndpoint.IMPRINT, params, BaseResource)
