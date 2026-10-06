import logging
from pathlib import Path
from uuid import uuid4
from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, Query, UploadFile, status
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from models import Comment, Like, Post, User
from services.notification_service import notify_post_activity
from schemas import CommentCreate, CommentOut, LikeOut, LoginRequest, PaginatedPosts, PostCreate, PostOut, PostUpdate, Token, UserCreate, UserOut
from security import create_access_token, get_current_user, hash_password, verify_password

logging.basicConfig(level=logging.INFO)
Base.metadata.create_all(bind=engine)
app = FastAPI(title="Blog Management API", description="JWT authenticated blogging API with SQLite and optional SMTP notifications.", version="1.0.0")
MEDIA_ROOT = Path(__file__).resolve().parent / "media"
POST_MEDIA = MEDIA_ROOT / "posts"
POST_MEDIA.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=MEDIA_ROOT), name="media")

# create_all creates new tables but does not evolve existing ones.
if "image" not in {column["name"] for column in inspect(engine).get_columns("posts")}:
    with engine.begin() as connection:
        connection.exec_driver_sql("ALTER TABLE posts ADD COLUMN image VARCHAR(500)")
if "created_at" not in {column["name"] for column in inspect(engine).get_columns("likes")}:
    with engine.begin() as connection:
        connection.exec_driver_sql("ALTER TABLE likes ADD COLUMN created_at DATETIME")


async def store_post_image(image: UploadFile | None) -> str | None:
    if image is None or not image.filename:
        return None
    allowed = {"image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif", "image/webp": ".webp"}
    extension = allowed.get(image.content_type or "")
    if extension is None:
        raise HTTPException(status_code=415, detail="Upload a JPEG, PNG, GIF, or WebP image")
    data = await image.read(10 * 1024 * 1024 + 1)
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image must be 10 MB or smaller")
    filename = f"{uuid4().hex}{extension}"
    (POST_MEDIA / filename).write_bytes(data)
    return f"posts/{filename}"


@app.get("/", tags=["health"])
def root():
    return {"message": "Blog Management API", "docs": "/docs"}


@app.post("/auth/register", response_model=UserOut, status_code=status.HTTP_201_CREATED, tags=["auth"])
def register(data: UserCreate, db: Session = Depends(get_db)):
    user = User(username=data.username, email=str(data.email).lower(), password=hash_password(data.password))
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Username or email is already registered")
    return user


@app.post("/auth/login", response_model=Token, tags=["auth"])
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where((User.username == data.username) | (User.email == data.username.lower())))
    if user is None or not verify_password(data.password, user.password):
        raise HTTPException(status_code=401, detail="Incorrect username/email or password", headers={"WWW-Authenticate": "Bearer"})
    return Token(access_token=create_access_token(user.id))


@app.post("/posts", response_model=PostOut, status_code=201, tags=["posts"])
def create_post(data: PostCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    post = Post(**data.model_dump(), author_id=user.id)
    db.add(post)
    db.commit()
    db.refresh(post)
    return post


@app.post("/posts/create", response_model=PostOut, status_code=201, tags=["posts"])
async def create_post_with_image(title: str = Form(..., min_length=1, max_length=200), content: str = Form(..., min_length=1, max_length=50000), image: UploadFile | None = File(default=None), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    image_path = await store_post_image(image)
    post = Post(title=title, content=content, image=image_path, author_id=user.id)
    db.add(post)
    try:
        db.commit()
        db.refresh(post)
    except Exception:
        db.rollback()
        if image_path:
            (MEDIA_ROOT / image_path).unlink(missing_ok=True)
        raise
    return post


@app.get("/posts", response_model=PaginatedPosts, tags=["posts"])
def list_posts(page: int = Query(1, ge=1), limit: int = Query(10, ge=1, le=100), search: str | None = Query(None, max_length=200), skip: int | None = Query(None, ge=0), db: Session = Depends(get_db)):
    query = select(Post)
    count_query = select(func.count(Post.id))
    if search and search.strip():
        term = f"%{search.strip()}%"
        filter_clause = Post.title.ilike(term) | Post.content.ilike(term)
        query = query.where(filter_clause)
        count_query = count_query.where(filter_clause)
    total = db.scalar(count_query) or 0
    posts = db.scalars(query.order_by(Post.created_at.desc(), Post.id.desc()).offset(skip if skip is not None else (page - 1) * limit).limit(limit)).all()
    return {"items": posts, "total": total, "page": page, "limit": limit, "total_pages": (total + limit - 1) // limit}


@app.get("/posts/mine", response_model=list[PostOut], tags=["posts"])
def my_posts(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.scalars(select(Post).where(Post.author_id == user.id).order_by(Post.created_at.desc())).all()


@app.get("/posts/{post_id}", response_model=PostOut, tags=["posts"])
def get_post(post_id: int, db: Session = Depends(get_db)):
    post = db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post


@app.patch("/posts/{post_id}", response_model=PostOut, tags=["posts"])
def update_post(post_id: int, data: PostUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    post = db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.author_id != user.id:
        raise HTTPException(status_code=403, detail="Only the post owner can update it")
    for key, value in data.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(post, key, value)
    db.commit()
    db.refresh(post)
    return post


@app.put("/posts/{post_id}/update", response_model=PostOut, tags=["posts"])
async def update_post_with_image(post_id: int, title: str | None = Form(default=None, min_length=1, max_length=200), content: str | None = Form(default=None, min_length=1, max_length=50000), image: UploadFile | None = File(default=None), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.author_id != user.id:
        raise HTTPException(status_code=403, detail="Only the post owner can update it")
    if title is not None:
        post.title = title
    if content is not None:
        post.content = content
    new_image = await store_post_image(image)
    if new_image:
        previous = post.image
        post.image = new_image
    else:
        previous = None
    try:
        db.commit()
        db.refresh(post)
    except Exception:
        db.rollback()
        if new_image:
            (MEDIA_ROOT / new_image).unlink(missing_ok=True)
        raise
    if previous:
        (MEDIA_ROOT / previous).unlink(missing_ok=True)
    return post


@app.delete("/posts/{post_id}", status_code=204, tags=["posts"])
def delete_post(post_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    post = db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.author_id != user.id:
        raise HTTPException(status_code=403, detail="Only the post owner can delete it")
    db.delete(post)
    db.commit()


@app.get("/posts/{post_id}/comments", response_model=list[CommentOut], tags=["comments"])
def list_comments(post_id: int, db: Session = Depends(get_db)):
    if db.get(Post, post_id) is None:
        raise HTTPException(status_code=404, detail="Post not found")
    return db.scalars(select(Comment).where(Comment.post_id == post_id).order_by(Comment.created_at)).all()


@app.post("/posts/{post_id}/comments", response_model=CommentOut, status_code=201, tags=["comments"])
def add_comment(post_id: int, data: CommentCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    comment = Comment(post_id=post.id, user_id=user.id, text=data.text)
    db.add(comment)
    db.commit()
    db.refresh(comment)
    notify_post_activity(background_tasks, post, user, "comment", comment.created_at)
    return comment


@app.post("/posts/{post_id}/like", response_model=LikeOut, tags=["likes"])
def like_post(post_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    existing = db.scalar(select(Like).where(Like.post_id == post_id, Like.user_id == user.id))
    if existing is None:
        like = Like(post_id=post_id, user_id=user.id)
        db.add(like)
        db.commit()
        db.refresh(like)
        notify_post_activity(background_tasks, post, user, "like", like.created_at)
    count = db.scalar(select(func.count(Like.id)).where(Like.post_id == post_id)) or 0
    return LikeOut(liked=True, likes_count=count)


@app.delete("/posts/{post_id}/like", response_model=LikeOut, tags=["likes"])
def unlike_post(post_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if db.get(Post, post_id) is None:
        raise HTTPException(status_code=404, detail="Post not found")
    existing = db.scalar(select(Like).where(Like.post_id == post_id, Like.user_id == user.id))
    if existing is not None:
        db.delete(existing)
        db.commit()
    count = db.scalar(select(func.count(Like.id)).where(Like.post_id == post_id)) or 0
    return LikeOut(liked=False, likes_count=count)
