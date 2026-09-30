# Blog Management API

FastAPI blog API with SQLite, SQLAlchemy, JWT authentication, ownership checks, comments, likes, and optional email notifications.

## Run locally

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:SECRET_KEY = "replace-with-a-long-random-secret"
uvicorn main:app --reload
```

Open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs). Tables are created in `blog.db` on startup. The default database is SQLite; `DATABASE_URL` can override it.

## Try the API in Swagger

1. `POST /auth/register` with a username (3–30 characters), valid email, and password (at least 8 characters).
2. `POST /auth/login` with `username` set to either the username or email. Copy `access_token`.
3. Use **Authorize** in Swagger and paste the `access_token` value.
4. Create a post, then try the comment and like routes. Post list/detail and comment reads are public. A like is idempotent; `DELETE /posts/{id}/like` removes your like.
5. To confirm ownership rules, register a second account and try editing/deleting the first account's post; the API returns 403.

## Notifications

Comment and first-like events notify the post author. Without SMTP configured, events are logged by the API process. For delivery, set `SMTP_HOST`, `SMTP_PORT` (default 587), `SMTP_USERNAME`, `SMTP_PASSWORD`, and optionally `SMTP_FROM`. SMTP delivery is performed as a background task.

## Schema and security

The database contains `users`, `posts`, `comments`, and `likes`; each user's password is stored as a salted PBKDF2-SHA256 hash. JWTs use HS256 and expire after 60 minutes by default (`ACCESS_TOKEN_MINUTES` can change this). Set a private random `SECRET_KEY` before deployment.

## Table screenshots

Screenshots can be captured from the generated SQLite database with DB Browser for SQLite or the SQLite CLI after launching the API. Use **Browse Data** to view the `users`, `posts`, `comments`, and `likes` tables. The database is created on first app startup.
