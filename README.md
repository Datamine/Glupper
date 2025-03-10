# Glupper

High-performance Twitter-like backend built with Python, FastAPI, and PostgreSQL.

## Features

- **High-performance architecture**
  - FastAPI for asynchronous API endpoints
  - PostgreSQL with optimized queries and indexes
  - Redis for caching frequently accessed data
  - Cursor-based pagination for optimal performance

- **Core functionality**
  - User authentication with JWT
  - Posts, comments, likes, and reposts
  - Follow/unfollow users
  - Home timeline feed
  - Explore/trending feed algorithm
  - Trending topics

- **Technical highlights**
  - Asynchronous database access with `asyncpg`
  - Efficient caching strategy with `redis`
  - Well-structured modular architecture
  - Type hints throughout for better reliability

## Getting Started

### Prerequisites

- Python 3.12+
- PostgreSQL
- Redis (optional but recommended for performance)
- `uv` package manager (faster alternative to pip)

### Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/glupper.git
   cd glupper
   ```

2. Install dependencies with `uv`:
   ```
   uv sync
   ```

3. Set up environment variables (or create a `.env` file):
   ```
   export DATABASE_URL=postgresql://postgres:postgres@localhost/glupper
   export REDIS_URL=redis://localhost:6379/0
   export SECRET_KEY=your_secret_key_here
   ```

4. Run the application:
   ```
   python run.py
   ```

5. Access the API documentation at http://localhost:8000/docs

## Project Structure

```
glupper/
├── app/
│   ├── api/           # API endpoints
│   ├── core/          # Core functionality (auth, db, cache)
│   ├── models/        # Data models
│   ├── schemas/       # API schemas (request/response)
│   ├── services/      # Business logic
│   └── main.py        # FastAPI application
```

## API Endpoints

The API is divided into several sections:

- `/auth` - Authentication endpoints (register, login)
- `/users` - User management (profile, followers, following)
- `/posts` - Post operations (create, comment, like, repost)
- `/feed` - Feed algorithms (home timeline, explore, trending)

## Performance Optimizations

- Efficient database queries with proper indexing
- Redis caching for timeline, post data, and user profiles
- Cursor-based pagination for scalable timeline fetching
- Optimized timeline algorithm for feed generation
- Connection pooling for database and cache connections

## Future Enhancements

- Full-text search for posts and users
- Media upload and processing
- Notifications system
- Direct messaging
- Analytics and metrics
