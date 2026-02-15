# Glupper Codebase Guidelines

This document serves as a guide to the Glupper codebase structure, patterns, and conventions.

## Project Structure

```
/glupper/
├── archivebox_backend/    # Archiving service integration
├── src/                   # Main application code
│   ├── api/               # API endpoints
│   ├── core/              # Core infrastructure
│   ├── models/            # Database models
│   ├── schemas/           # Pydantic schemas
│   ├── services/          # Business logic
│   │   └── queues/        # Message queue services
│   └── utils/             # Utility functions
├── run.py                 # Application entry point
├── __init__.py
└── pyproject.toml         # Project dependencies
```

## Architectural Patterns

### API Layer (`/src/api/`)

- Each resource has its own router file (e.g., `feed.py`, `posts.py`, `users.py`)
- Routes are prefixed with `/api/v1/{resource}`
- Endpoints use dependency injection for auth via `get_current_user`
- All endpoints have detailed docstrings with parameters, returns, and raises sections
- Uses FastAPI's typing system for request/response validation

### Service Layer (`/src/services/`)

- Contains business logic separated by domain
- Services interact with the database via the core DB module
- Implements caching strategies as needed
- Services should not depend on API layer
- Services can interact with other services

### Database Layer (`/src/core/db.py`)

- Uses asyncpg for asynchronous PostgreSQL access
- Connection pooling for performance
- Query functions are optimized for specific data access patterns
- Complex queries use WITH clauses and proper indexing
- Cursor-based pagination is preferred over offset-based

### Caching Layer (`/src/core/cache.py`)

- Redis-based caching for high-performance data access
- Implements proper serialization/deserialization
- Cache invalidation patterns for data consistency
- Uses pipeline batching for efficiency

### Schemas (`/src/schemas/`)

- Pydantic models for request/response validation
- Clear separation between input and output schemas
- Implements validation logic via validators
- Redis-specific models include serialization helpers
- Consistent naming: `{Entity}Create`, `{Entity}Response`

## Feed Implementation

- Two feed algorithms are supported:
  1. `chronological`: Shows posts from followed users in time order
  2. `for_you`: Personalized feed with content recommendations
- Cursor-based pagination for optimal performance
- Redis caching for fast timeline access
- Fanout-on-write for efficient content distribution

## Database Schema

- Users table with auth information and profile data
- Posts table for all content (top-level posts, comments, reposts)
- Follows table for user relationships
- Likes table for post engagement
- Mutes table for content filtering
- Archived URLs table for content preservation
- Messages table for direct messaging

## API Conventions

### Common Patterns

- GET collections: cursor-based pagination
- POST for resource creation
- Consistent error responses
- Authentication via JWT tokens

### Status Codes

- 200: Success for GET, PUT, PATCH
- 201: Success for POST (creation)
- 204: Success for DELETE
- 400: Bad Request (invalid input)
- 401: Unauthorized (auth required)
- 403: Forbidden (insufficient permissions)
- 404: Not Found
- 422: Validation Error
- 500: Server Error

## Performance Considerations

- Use optimized database queries with proper indexing
- Implement caching for frequently accessed data
- Use cursor-based pagination for large datasets
- Batch operations where possible
- Use background tasks for non-critical operations

## Testing

- Tests should be placed in a `/tests` directory
- Unit tests for services
- Integration tests for API endpoints
- Database tests with proper setup/teardown
- Mock external services for tests

### Development

- We use `uv` and `ruff` for this project
- Mypy hinting should be rigorously enforced


## Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Pydantic Documentation](https://pydantic-docs.helpmanual.io/)
- [Asyncpg Documentation](https://magicstack.github.io/asyncpg/current/)
- [Redis Documentation](https://redis.io/documentation)
