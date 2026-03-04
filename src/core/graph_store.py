from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID

import httpx
from pydantic import ValidationError

from src.config_secrets import NEPTUNE_ENDPOINT, NEPTUNE_OPENCYPHER_PATH, NEPTUNE_QUERY_TIMEOUT_SECONDS
from src.models.models import Account, AccountStatus
from src.schemas.schemas import GraphEdgeResponse, GraphNodeResponse


class GraphStoreError(Exception):
    """Raised when a graph backend operation fails."""


@dataclass(slots=True)
class GraphNeighborhoodData:
    nodes: list[GraphNodeResponse]
    edges: list[GraphEdgeResponse]


@dataclass(slots=True)
class GraphPathData:
    found: bool
    nodes: list[GraphNodeResponse]
    edges: list[GraphEdgeResponse]


class GraphStore(Protocol):
    async def close(self) -> None: ...

    async def upsert_account(self, account: Account) -> None: ...

    async def set_vouch_edge(self, account_id: UUID, sponsor_id: UUID | None, created_at: datetime) -> None: ...

    async def upsert_social_identity(
        self,
        account_id: UUID,
        provider: str,
        handle: str,
        provider_user_id: str,
        verified_at: datetime,
    ) -> None: ...

    async def update_account_statuses(
        self,
        account_ids: list[UUID],
        status: AccountStatus,
        trust_started_at: datetime | None,
        recovery_eligible_at: datetime | None,
    ) -> None: ...

    async def get_neighborhood(self, account_id: UUID, depth: int, limit: int) -> GraphNeighborhoodData: ...

    async def get_shortest_path(self, source_account_id: UUID, destination_account_id: UUID, max_depth: int) -> GraphPathData: ...


class NullGraphStore:
    """No-op graph store used when Neptune is not configured."""

    async def close(self) -> None:
        return

    async def upsert_account(self, account: Account) -> None:
        return

    async def set_vouch_edge(self, account_id: UUID, sponsor_id: UUID | None, created_at: datetime) -> None:
        return

    async def upsert_social_identity(
        self,
        account_id: UUID,
        provider: str,
        handle: str,
        provider_user_id: str,
        verified_at: datetime,
    ) -> None:
        return

    async def update_account_statuses(
        self,
        account_ids: list[UUID],
        status: AccountStatus,
        trust_started_at: datetime | None,
        recovery_eligible_at: datetime | None,
    ) -> None:
        return

    async def get_neighborhood(self, account_id: UUID, depth: int, limit: int) -> GraphNeighborhoodData:
        raise GraphStoreError("Graph store is not configured")

    async def get_shortest_path(self, source_account_id: UUID, destination_account_id: UUID, max_depth: int) -> GraphPathData:
        raise GraphStoreError("Graph store is not configured")


class NeptuneGraphStore:
    """Neptune openCypher backend implementation."""

    def __init__(self, endpoint: str, open_cypher_path: str, timeout_seconds: float) -> None:
        self._open_cypher_path = open_cypher_path
        self._client = httpx.AsyncClient(base_url=endpoint.rstrip("/"), timeout=timeout_seconds)

    async def close(self) -> None:
        await self._client.aclose()

    async def upsert_account(self, account: Account) -> None:
        query = """
        MERGE (a:Account {id: $id})
        SET a.username = $username,
            a.status = $status,
            a.demerit_count = $demerit_count,
            a.trust_started_at = $trust_started_at,
            a.recovery_eligible_at = $recovery_eligible_at,
            a.updated_at = $updated_at,
            a.created_at = coalesce(a.created_at, $created_at)
        """
        await self._execute(
            query,
            {
                "id": str(account.id),
                "username": account.username,
                "status": account.status.value,
                "demerit_count": account.demerit_count,
                "trust_started_at": _iso_or_none(account.trust_started_at),
                "recovery_eligible_at": _iso_or_none(account.recovery_eligible_at),
                "updated_at": _iso_or_none(account.updated_at),
                "created_at": _iso_or_none(account.created_at),
            },
        )

    async def set_vouch_edge(self, account_id: UUID, sponsor_id: UUID | None, created_at: datetime) -> None:
        if sponsor_id is None:
            query = """
            MATCH (child:Account {id: $account_id})
            OPTIONAL MATCH (:Account)-[r:VOUCHED_FOR]->(child)
            DELETE r
            """
            await self._execute(query, {"account_id": str(account_id)})
            return

        query = """
        MATCH (child:Account {id: $account_id})
        OPTIONAL MATCH (:Account)-[old:VOUCHED_FOR]->(child)
        DELETE old
        WITH child
        MATCH (sponsor:Account {id: $sponsor_id})
        MERGE (sponsor)-[r:VOUCHED_FOR]->(child)
        SET r.created_at = $created_at
        """
        await self._execute(
            query,
            {
                "account_id": str(account_id),
                "sponsor_id": str(sponsor_id),
                "created_at": _iso_or_none(created_at),
            },
        )

    async def upsert_social_identity(
        self,
        account_id: UUID,
        provider: str,
        handle: str,
        provider_user_id: str,
        verified_at: datetime,
    ) -> None:
        query = """
        MATCH (a:Account {id: $account_id})
        MERGE (s:SocialIdentity {provider: $provider, provider_user_id: $provider_user_id})
        SET s.handle = $handle,
            s.verified_at = $verified_at
        MERGE (a)-[r:LINKED_HANDLE]->(s)
        SET r.verified_at = $verified_at
        """
        await self._execute(
            query,
            {
                "account_id": str(account_id),
                "provider": provider,
                "provider_user_id": provider_user_id,
                "handle": handle,
                "verified_at": _iso_or_none(verified_at),
            },
        )

    async def update_account_statuses(
        self,
        account_ids: list[UUID],
        status: AccountStatus,
        trust_started_at: datetime | None,
        recovery_eligible_at: datetime | None,
    ) -> None:
        if not account_ids:
            return

        query = """
        UNWIND $account_ids AS account_id
        MATCH (a:Account {id: account_id})
        SET a.status = $status,
            a.trust_started_at = $trust_started_at,
            a.recovery_eligible_at = $recovery_eligible_at,
            a.updated_at = $updated_at
        """
        await self._execute(
            query,
            {
                "account_ids": [str(account_id) for account_id in account_ids],
                "status": status.value,
                "trust_started_at": _iso_or_none(trust_started_at),
                "recovery_eligible_at": _iso_or_none(recovery_eligible_at),
                "updated_at": _iso_or_none(datetime.now(UTC).replace(tzinfo=None)),
            },
        )

    async def get_neighborhood(self, account_id: UUID, depth: int, limit: int) -> GraphNeighborhoodData:
        query = f"""
        MATCH (origin:Account {{id: $account_id}})
        OPTIONAL MATCH p=(origin)-[:VOUCHED_FOR*1..{depth}]-(neighbor:Account)
        WITH origin, collect(DISTINCT neighbor) AS neighbors
        WITH [origin] + neighbors AS raw_nodes
        UNWIND raw_nodes AS node
        WITH collect(DISTINCT node)[..$limit] AS selected_nodes
        WITH selected_nodes, [node IN selected_nodes | node.id] AS node_ids
        OPTIONAL MATCH (a:Account)-[r:VOUCHED_FOR]->(b:Account)
        WHERE a.id IN node_ids AND b.id IN node_ids
        RETURN {{
            nodes: [node IN selected_nodes | {{
                id: node.id,
                username: node.username,
                status: node.status,
                demerit_count: node.demerit_count,
                trust_started_at: node.trust_started_at,
                recovery_eligible_at: node.recovery_eligible_at
            }}],
            edges: collect(DISTINCT {{
                source: a.id,
                target: b.id,
                relationship: type(r),
                created_at: r.created_at
            }})
        }} AS payload
        """
        rows = await self._execute(query, {"account_id": str(account_id), "limit": limit})
        payload = _extract_payload(rows)

        nodes = [_parse_node(node) for node in payload.get("nodes", [])]
        edges = [_parse_edge(edge) for edge in payload.get("edges", [])]
        filtered_nodes = [node for node in nodes if node is not None]
        filtered_edges = [edge for edge in edges if edge is not None]
        return GraphNeighborhoodData(nodes=filtered_nodes, edges=filtered_edges)

    async def get_shortest_path(self, source_account_id: UUID, destination_account_id: UUID, max_depth: int) -> GraphPathData:
        query = f"""
        MATCH (source:Account {{id: $source_id}}), (destination:Account {{id: $destination_id}})
        OPTIONAL MATCH p = shortestPath((source)-[:VOUCHED_FOR*..{max_depth}]-(destination))
        RETURN {{
            found: p IS NOT NULL,
            nodes: CASE
                WHEN p IS NULL THEN []
                ELSE [node IN nodes(p) | {{
                    id: node.id,
                    username: node.username,
                    status: node.status,
                    demerit_count: node.demerit_count,
                    trust_started_at: node.trust_started_at,
                    recovery_eligible_at: node.recovery_eligible_at
                }}]
            END,
            edges: CASE
                WHEN p IS NULL THEN []
                ELSE [rel IN relationships(p) | {{
                    source: startNode(rel).id,
                    target: endNode(rel).id,
                    relationship: type(rel),
                    created_at: rel.created_at
                }}]
            END
        }} AS payload
        """
        rows = await self._execute(
            query,
            {
                "source_id": str(source_account_id),
                "destination_id": str(destination_account_id),
            },
        )
        payload = _extract_payload(rows)
        raw_found = payload.get("found")
        found = bool(raw_found) if isinstance(raw_found, (bool, int)) else False

        nodes = [_parse_node(node) for node in payload.get("nodes", [])]
        edges = [_parse_edge(edge) for edge in payload.get("edges", [])]
        filtered_nodes = [node for node in nodes if node is not None]
        filtered_edges = [edge for edge in edges if edge is not None]
        return GraphPathData(found=found, nodes=filtered_nodes, edges=filtered_edges)

    async def _execute(self, query: str, parameters: dict[str, Any]) -> list[dict[str, Any]]:
        response = await self._client.post(
            self._open_cypher_path,
            json={"query": query, "parameters": parameters},
        )
        if response.status_code >= 400:
            detail = response.text[:1000]
            raise GraphStoreError(f"Neptune openCypher request failed ({response.status_code}): {detail}")

        try:
            payload = response.json()
        except ValueError as exc:
            raise GraphStoreError("Neptune openCypher response was not valid JSON") from exc

        return _extract_rows(payload)


_graph_store: GraphStore | None = None


async def init_graph_store() -> GraphStore:
    """Initialize graph store singleton."""
    global _graph_store
    if _graph_store is not None:
        return _graph_store

    endpoint = NEPTUNE_ENDPOINT.strip()
    if endpoint == "":
        _graph_store = NullGraphStore()
    else:
        _graph_store = NeptuneGraphStore(
            endpoint=endpoint,
            open_cypher_path=NEPTUNE_OPENCYPHER_PATH,
            timeout_seconds=NEPTUNE_QUERY_TIMEOUT_SECONDS,
        )
    return _graph_store


async def close_graph_store() -> None:
    """Close graph store singleton."""
    global _graph_store
    if _graph_store is not None:
        await _graph_store.close()
    _graph_store = None


async def get_graph_store() -> GraphStore:
    """Return current graph store singleton."""
    if _graph_store is None:
        return await init_graph_store()
    return _graph_store


def _extract_rows(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []

    for key in ("results", "records"):
        rows = payload.get(key)
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]

    data = payload.get("data")
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]

    return []


def _extract_payload(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"nodes": [], "edges": []}

    first_row = rows[0]
    payload = first_row.get("payload")
    if isinstance(payload, dict):
        return payload

    row_list = first_row.get("row")
    if isinstance(row_list, list) and row_list:
        first_item = row_list[0]
        if isinstance(first_item, dict):
            return first_item

    return first_row


def _parse_node(raw_node: Any) -> GraphNodeResponse | None:
    if not isinstance(raw_node, dict):
        return None
    try:
        return GraphNodeResponse.model_validate(raw_node)
    except ValidationError:
        return None


def _parse_edge(raw_edge: Any) -> GraphEdgeResponse | None:
    if not isinstance(raw_edge, dict):
        return None

    if raw_edge.get("source") is None or raw_edge.get("target") is None:
        return None

    try:
        return GraphEdgeResponse.model_validate(raw_edge)
    except ValidationError:
        return None


def _iso_or_none(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()
