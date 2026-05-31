"""Panel administratora — server-side rendered HTML (Jinja2).

Auth: cookie `admin_token` (JWT). Dostep wymaga roli ADMIN.
"""
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.core.deps import get_admin_from_cookie
from app.core.security import create_access_token, verify_password
from app.database import get_db
from app.models.comment import Comment
from app.models.post import Post
from app.models.user import User, UserRole

router = APIRouter()

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


# GET /admin/login
@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "admin/login.html", {"error": None})


# POST /admin/login
@router.post("/login", response_model=None)
def login_submit(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    username: str = Form(...),
    password: str = Form(...),
) -> Response:
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse(
            request,
            "admin/login.html",
            {"error": "Nieprawidlowe dane logowania"},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    if user.role != UserRole.ADMIN:
        return templates.TemplateResponse(
            request,
            "admin/login.html",
            {"error": "Brak uprawnien administratora"},
            status_code=status.HTTP_403_FORBIDDEN,
        )

    token = create_access_token(subject=user.username, extra_claims={"role": user.role.value})
    response = RedirectResponse(url="/admin/", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        key=settings.ADMIN_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    return response


# POST /admin/logout
@router.post("/logout")
def logout() -> RedirectResponse:
    response = RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(settings.ADMIN_COOKIE_NAME)
    return response


# GET /admin/
@router.get("/", response_class=HTMLResponse)
def dashboard(
    request: Request,
    admin: Annotated[User, Depends(get_admin_from_cookie)],
    db: Annotated[Session, Depends(get_db)],
) -> HTMLResponse:
    stats = {
        "users": db.query(User).count(),
        "posts": db.query(Post).count(),
        "comments": db.query(Comment).count(),
    }
    return templates.TemplateResponse(
        request, "admin/dashboard.html", {"admin": admin, "stats": stats}
    )


# GET /admin/users
@router.get("/users", response_class=HTMLResponse)
def list_users(
    request: Request,
    admin: Annotated[User, Depends(get_admin_from_cookie)],
    db: Annotated[Session, Depends(get_db)],
) -> HTMLResponse:
    users = db.query(User).order_by(User.id).all()
    return templates.TemplateResponse(
        request,
        "admin/users.html",
        {"admin": admin, "users": users, "roles": list(UserRole)},
    )


# POST /admin/users/{user_id}/role
@router.post("/users/{user_id}/role")
def admin_change_role(
    user_id: int,
    admin: Annotated[User, Depends(get_admin_from_cookie)],
    db: Annotated[Session, Depends(get_db)],
    role: str = Form(...),
) -> RedirectResponse:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Uzytkownik nie istnieje")
    try:
        new_role = UserRole(role)
    except ValueError:
        raise HTTPException(status_code=400, detail="Nieprawidlowa rola")
    if user.id == admin.id and new_role != UserRole.ADMIN:
        raise HTTPException(status_code=400, detail="Nie mozesz odebrac sobie roli administratora")
    user.role = new_role
    db.commit()
    return RedirectResponse(url="/admin/users", status_code=status.HTTP_303_SEE_OTHER)


# POST /admin/users/{user_id}/toggle-active
@router.post("/users/{user_id}/toggle-active")
def admin_toggle_active(
    user_id: int,
    admin: Annotated[User, Depends(get_admin_from_cookie)],
    db: Annotated[Session, Depends(get_db)],
) -> RedirectResponse:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Uzytkownik nie istnieje")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Nie mozesz zmodyfikowac wlasnego konta")
    user.is_active = not user.is_active
    db.commit()
    return RedirectResponse(url="/admin/users", status_code=status.HTTP_303_SEE_OTHER)


# GET /admin/posts
@router.get("/posts", response_class=HTMLResponse)
def list_posts_admin(
    request: Request,
    admin: Annotated[User, Depends(get_admin_from_cookie)],
    db: Annotated[Session, Depends(get_db)],
) -> HTMLResponse:
    posts = db.query(Post).order_by(Post.created_at.desc()).limit(200).all()
    return templates.TemplateResponse(
        request, "admin/posts.html", {"admin": admin, "posts": posts}
    )


# POST /admin/posts/{post_id}/delete
@router.post("/posts/{post_id}/delete")
def delete_post_admin(
    post_id: int,
    _admin: Annotated[User, Depends(get_admin_from_cookie)],
    db: Annotated[Session, Depends(get_db)],
) -> RedirectResponse:
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post nie istnieje")
    db.delete(post)
    db.commit()
    return RedirectResponse(url="/admin/posts", status_code=status.HTTP_303_SEE_OTHER)


# GET /admin/comments
@router.get("/comments", response_class=HTMLResponse)
def list_comments_admin(
    request: Request,
    admin: Annotated[User, Depends(get_admin_from_cookie)],
    db: Annotated[Session, Depends(get_db)],
) -> HTMLResponse:
    comments = db.query(Comment).order_by(Comment.created_at.desc()).limit(200).all()
    return templates.TemplateResponse(
        request, "admin/comments.html", {"admin": admin, "comments": comments}
    )


# POST /admin/comments/{comment_id}/delete
@router.post("/comments/{comment_id}/delete")
def delete_comment_admin(
    comment_id: int,
    _admin: Annotated[User, Depends(get_admin_from_cookie)],
    db: Annotated[Session, Depends(get_db)],
) -> RedirectResponse:
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Komentarz nie istnieje")
    db.delete(comment)
    db.commit()
    return RedirectResponse(url="/admin/comments", status_code=status.HTTP_303_SEE_OTHER)


# Attachments admin view removed in phase 3 (legacy attachments → files module).
