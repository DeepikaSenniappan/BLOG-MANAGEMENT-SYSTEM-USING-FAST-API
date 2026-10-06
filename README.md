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

## Post images, search, and pagination

Authenticated users can create a post with optional image using `POST /posts/create` (multipart form fields `title`, `content`, optional `image`) or replace its image using `PUT /posts/{id}/update`. Images up to 10 MB in JPEG, PNG, GIF, or WebP format are saved in `media/posts/` and served under `/media/posts/`. The post response includes `image_url` (or `null` when there is no image). Existing JSON `POST /posts` and `PATCH /posts/{id}` routes remain available.

`GET /posts?page=1&limit=10&search=keyword` searches title and content and paginates the matching posts. Its response contains `items`, `total`, `page`, `limit`, and `total_pages`; `search` can be combined with either pagination parameter. See `output/post_api_demo.postman_collection.json` for a short Postman collection.

## Try the API in Swagger

1. `POST /auth/register` with a username (3–30 characters), valid email, and password (at least 8 characters).
2. `POST /auth/login` with `username` set to either the username or email. Copy `access_token`.
3. Use **Authorize** in Swagger and paste the `access_token` value.
4. Create a post, then try the comment and like routes. Post list/detail and comment reads are public. A like is idempotent; `DELETE /posts/{id}/like` removes your like.
5. To confirm ownership rules, register a second account and try editing/deleting the first account's post; the API returns 403.

## Email notifications

The post author receives an email after another user successfully comments or likes a post. Notifications include the post title, actor username, activity, and UTC timestamp. Repeated likes do not send duplicate messages, and users are not notified about their own activity. Email delivery uses FastAPI `BackgroundTasks`, so SMTP work runs after the API response in Starlette's worker thread pool. Delivery errors are logged and do not undo a saved comment or like.

Configure SMTP with environment variables before starting the API:

```powershell
$env:SMTP_HOST = "sandbox.smtp.mailtrap.io"
$env:SMTP_PORT = "2525"
$env:SMTP_USERNAME = "your-mailtrap-username"
$env:SMTP_PASSWORD = "your-mailtrap-password"
$env:SMTP_FROM = "Blog Notifications <notifications@example.com>"
$env:SMTP_USE_STARTTLS = "true"
```

For providers using implicit TLS, set `SMTP_USE_SSL=true` and `SMTP_USE_STARTTLS=false`. If SMTP is not configured, notification details are logged locally. Do not commit SMTP credentials.

### Test notifications without an external SMTP account

Open two PowerShell windows in the project folder. In the first, run `python dev_smtp_inbox.py`. In the second, set `$env:SMTP_HOST = "127.0.0.1"`, `$env:SMTP_PORT = "1025"`, `$env:SMTP_USERNAME = ""`, `$env:SMTP_PASSWORD = ""`, `$env:SMTP_USE_SSL = "false"`, and `$env:SMTP_USE_STARTTLS = "false"`, then run `uvicorn main:app --reload`. Trigger a comment or first-time like in Swagger; the received email content appears in the first window. This is a local capture inbox and does not deliver real email.

## Schema and security

The database contains `users`, `posts`, `comments`, and `likes`; each user's password is stored as a salted PBKDF2-SHA256 hash. JWTs use HS256 and expire after 60 minutes by default (`ACCESS_TOKEN_MINUTES` can change this). Set a private random `SECRET_KEY` before deployment.

## Table screenshots

Screenshots can be captured from the generated SQLite database with DB Browser for SQLite or the SQLite CLI after launching the API. Use **Browse Data** to view the `users`, `posts`, `comments`, and `likes` tables. The database is created on first app startup.
