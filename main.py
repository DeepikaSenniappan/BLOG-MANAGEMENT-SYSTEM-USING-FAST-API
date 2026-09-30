import logging

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from models import Comment, Like, Post, User
from notifications import send_notification
from schemas import CommentCreate, CommentOut, LikeOut, LoginRequest, PostCreate, PostOut, PostUpdate, Token, UserCreate, UserOut
from security import create_access_token, get_current_user, hash_password, verify_password

logging.basicConfig(level=logging.INFO)
Base.metadata.create_all(bind=engine)
app = FastAPI(title="Blog Management API", description="JWT authenticated blogging API with SQLite and optional SMTP notifications.", version="1.0.0")


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


@app.get("/posts", response_model=list[PostOut], tags=["posts"])
def list_posts(skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    return db.scalars(select(Post).order_by(Post.created_at.desc(), Post.id.desc()).offset(skip).limit(limit)).all()


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
    if post.author_id != user.id:
        recipient = db.get(User, post.author_id)
        if recipient:
            background_tasks.add_task(send_notification, recipient, "New comment on your post", f"{user.username} commented on '{post.title}': {data.text}")
    return comment


@app.post("/posts/{post_id}/like", response_model=LikeOut, tags=["likes"])
def like_post(post_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    existing = db.scalar(select(Like).where(Like.post_id == post_id, Like.user_id == user.id))
    if existing is None:
        db.add(Like(post_id=post_id, user_id=user.id))
        db.commit()
        if post.author_id != user.id:
            recipient = db.get(User, post.author_id)
            if recipient:
                background_tasks.add_task(send_notification, recipient, "New like on your post", f"{user.username} liked '{post.title}'.")
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
