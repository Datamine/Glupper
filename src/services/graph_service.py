from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import ValidationError

from src.config_secrets import GRAPH_CACHE_TTL_SECONDS
from src.core.cache import build_graph_cache_key, bump_graph_cache_epoch, get_graph_cache_epoch, get_graph_cache_json, set_graph_cache_json
from src.core.graph_store import GraphNeighborhoodData, GraphPathData, GraphStoreError, get_graph_store
from src.models.models import Account, AccountStatus
from src.schemas.schemas import GraphEdgeResponse, GraphNodeResponse

logger = logging.getLogger(__name__)


async def sync_account_node(account: Account) -> None:
    """Upsert one account node into graph store and invalidate graph cache epoch."""
    try:
        graph_store = await get_graph_store()
        await graph_store.upsert_account(account)
        await graph_store.set_vouch_edge(
            account_id=account.id,
            sponsor_id=account.sponsor_id,
            created_at=account.created_at,
        )
        await bump_graph_cache_epoch()
    except GraphStoreError as exc:
        logger.warning("Graph sync failed for account %s: %s", account.id, exc)


async def sync_vouch_edge(account_id: UUID, sponsor_id: UUID | None, created_at: datetime) -> None:
    """Update inbound vouch edge for one account and invalidate graph cache."""
    try:
        graph_store = await get_graph_store()
        await graph_store.set_vouch_edge(
            account_id=account_id,
            sponsor_id=sponsor_id,
            created_at=created_at,
        )
        await bump_graph_cache_epoch()
    except GraphStoreError as exc:
        logger.warning("Graph vouch-edge sync failed for account %s: %s", account_id, exc)


async def sync_social_identity(
    account_id: UUID,
    provider: str,
    handle: str,
    provider_user_id: str,
    verified_at: datetime,
) -> None:
    """Upsert one social identity node/link and invalidate graph cache."""
    try:
        graph_store = await get_graph_store()
        await graph_store.upsert_social_identity(
            account_id=account_id,
            provider=provider,
            handle=handle,
            provider_user_id=provider_user_id,
            verified_at=verified_at,
        )
        await bump_graph_cache_epoch()
    except GraphStoreError as exc:
        logger.warning("Graph social identity sync failed for account %s: %s", account_id, exc)


async def sync_account_statuses(
    account_ids: list[UUID],
    status: AccountStatus,
    trust_started_at: datetime | None,
    recovery_eligible_at: datetime | None,
) -> None:
    """Bulk sync account status fields and invalidate graph cache."""
    if not account_ids:
        return

    try:
        graph_store = await get_graph_store()
        await graph_store.update_account_statuses(
            account_ids=account_ids,
            status=status,
            trust_started_at=trust_started_at,
            recovery_eligible_at=recovery_eligible_at,
        )
        await bump_graph_cache_epoch()
    except GraphStoreError as exc:
        logger.warning("Graph status sync failed for %s accounts: %s", len(account_ids), exc)


async def get_graph_neighborhood(account_id: UUID, depth: int, limit: int) -> GraphNeighborhoodData:
    """Return cached graph neighborhood for one account."""
    epoch = await get_graph_cache_epoch()
    cache_key = build_graph_cache_key("neighborhood", str(epoch), str(account_id), str(depth), str(limit))
    cached_payload = await get_graph_cache_json(cache_key)
    if cached_payload is not None:
        nodes_raw = cached_payload.get("nodes")
        edges_raw = cached_payload.get("edges")
        if isinstance(nodes_raw, list) and isinstance(edges_raw, list):
            try:
                return GraphNeighborhoodData(
                    nodes=[GraphNodeResponse.model_validate(item) for item in nodes_raw],
                    edges=[GraphEdgeResponse.model_validate(item) for item in edges_raw],
                )
            except ValidationError:
                pass

    graph_store = await get_graph_store()
    neighborhood = await graph_store.get_neighborhood(account_id=account_id, depth=depth, limit=limit)
    await set_graph_cache_json(
        cache_key,
        {
            "nodes": [node.model_dump(mode="json") for node in neighborhood.nodes],
            "edges": [edge.model_dump(mode="json") for edge in neighborhood.edges],
        },
        GRAPH_CACHE_TTL_SECONDS,
    )
    return neighborhood


async def get_graph_shortest_path(source_account_id: UUID, destination_account_id: UUID, max_depth: int) -> GraphPathData:
    """Return cached shortest path between two accounts."""
    epoch = await get_graph_cache_epoch()
    cache_key = build_graph_cache_key(
        "path",
        str(epoch),
        str(source_account_id),
        str(destination_account_id),
        str(max_depth),
    )
    cached_payload = await get_graph_cache_json(cache_key)
    if cached_payload is not None:
        found_raw = cached_payload.get("found")
        nodes_raw = cached_payload.get("nodes")
        edges_raw = cached_payload.get("edges")
        if isinstance(found_raw, bool) and isinstance(nodes_raw, list) and isinstance(edges_raw, list):
            try:
                return GraphPathData(
                    found=found_raw,
                    nodes=[GraphNodeResponse.model_validate(item) for item in nodes_raw],
                    edges=[GraphEdgeResponse.model_validate(item) for item in edges_raw],
                )
            except ValidationError:
                pass

    graph_store = await get_graph_store()
    path_data = await graph_store.get_shortest_path(
        source_account_id=source_account_id,
        destination_account_id=destination_account_id,
        max_depth=max_depth,
    )
    await set_graph_cache_json(
        cache_key,
        {
            "found": path_data.found,
            "nodes": [node.model_dump(mode="json") for node in path_data.nodes],
            "edges": [edge.model_dump(mode="json") for edge in path_data.edges],
        },
        GRAPH_CACHE_TTL_SECONDS,
    )
    return path_data


def neighborhood_to_cache_payload(neighborhood: GraphNeighborhoodData) -> dict[str, Any]:
    """Serialize neighborhood response payload for caches/logs."""
    return {
        "nodes": [node.model_dump(mode="json") for node in neighborhood.nodes],
        "edges": [edge.model_dump(mode="json") for edge in neighborhood.edges],
    }
