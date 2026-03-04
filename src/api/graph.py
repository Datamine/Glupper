from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from src.core.graph_store import GraphStoreError
from src.schemas.schemas import GraphNeighborhoodResponse, GraphPathResponse
from src.services.account_service import get_account_by_username
from src.services.graph_service import get_graph_neighborhood, get_graph_shortest_path

router = APIRouter(prefix="/api/v1/graph", tags=["graph"])


@router.get("/accounts/{username}/neighborhood", response_model=GraphNeighborhoodResponse, status_code=status.HTTP_200_OK)
async def get_account_neighborhood(
    username: str,
    depth: int = Query(default=2, ge=1, le=6),
    limit: int = Query(default=200, ge=1, le=2000),
) -> GraphNeighborhoodResponse:
    """Return an account-centered neighborhood subgraph for explorer views."""
    account = await get_account_by_username(username)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    try:
        neighborhood = await get_graph_neighborhood(account.id, depth, limit)
    except GraphStoreError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    return GraphNeighborhoodResponse(
        center_account_id=account.id,
        depth=depth,
        nodes=neighborhood.nodes,
        edges=neighborhood.edges,
    )


@router.get("/path", response_model=GraphPathResponse, status_code=status.HTTP_200_OK)
async def get_shortest_path(
    source_username: str = Query(min_length=1),
    destination_username: str = Query(min_length=1),
    max_depth: int = Query(default=6, ge=1, le=10),
) -> GraphPathResponse:
    """Return shortest vouch path between two accounts when one exists."""
    source_account = await get_account_by_username(source_username)
    if source_account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source account not found")

    destination_account = await get_account_by_username(destination_username)
    if destination_account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Destination account not found")

    try:
        path_data = await get_graph_shortest_path(
            source_account_id=source_account.id,
            destination_account_id=destination_account.id,
            max_depth=max_depth,
        )
    except GraphStoreError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    return GraphPathResponse(
        source_account_id=source_account.id,
        destination_account_id=destination_account.id,
        found=path_data.found,
        nodes=path_data.nodes,
        edges=path_data.edges,
    )
