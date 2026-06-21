"""Use-case tests for the content module using in-memory fakes.

These exercise the full application layer (posts, comments, categories, tags)
without a database. Each fake repository keeps domain aggregates in a dict and
projects the ``*Summary`` read models the way the SQL repositories do, so the
use cases run end-to-end: validation, ownership/permission rules, event
publication and the Result envelope.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

import pytest

from app.modules.content.application.commands import (
    AddCommentCommand,
    AuthorSummary,
    CategorySummary,
    CommentSummary,
    CreateCategoryCommand,
    CreatePostCommand,
    CreateTagCommand,
    DeleteCategoryCommand,
    DeleteCommentCommand,
    DeletePostCommand,
    ListPostsQuery,
    PostListPage,
    PostSummary,
    TagSummary,
    UpdateCommentCommand,
    UpdatePostCommand,
)
from app.modules.content.application.errors import (
    CategoryAlreadyExists,
    CategoryNotFound,
    CommentNotFound,
    NotCommentOwner,
    NotPostOwner,
    PostNotFound,
    SlugAlreadyTaken,
    TagAlreadyExists,
)
from app.modules.content.application.pagination import PostCursor
from app.modules.content.application.use_cases import (
    AddCommentUseCase,
    CreateCategoryUseCase,
    CreatePostUseCase,
    CreateTagUseCase,
    DeleteCategoryUseCase,
    DeleteCommentUseCase,
    DeletePostUseCase,
    GetCommentTreeUseCase,
    GetPostUseCase,
    ListCategoriesUseCase,
    ListPostsUseCase,
    ListTagsUseCase,
    UpdateCommentUseCase,
    UpdatePostUseCase,
)
from app.modules.content.domain.category import Category, CategoryId
from app.modules.content.domain.comment import Comment, CommentId
from app.modules.content.domain.post import Post, PostId
from app.modules.content.domain.tag import Tag, TagId
from app.modules.content.domain.value_objects import Slug
from app.shared.application.result import Err, Ok

# --------------------------------------------------------------------------- #
# Fakes                                                                       #
# --------------------------------------------------------------------------- #


class FakeBus:
    def __init__(self) -> None:
        self.published: list[object] = []

    async def publish(self, event: object) -> None:
        self.published.append(event)

    def types(self) -> list[str]:
        return [type(e).__name__ for e in self.published]


class FakePostRepo:
    def __init__(self, uow: FakeContentUoW) -> None:
        self._uow = uow
        self.store: dict[UUID, Post] = {}

    async def get(self, id_: PostId) -> Post | None:
        return self.store.get(id_.value)

    async def add(self, entity: Post) -> None:
        self.store[entity.id.value] = entity

    async def has_slug_for_author(
        self, *, author_public_id: UUID, slug: str, exclude_id: PostId | None = None
    ) -> bool:
        for p in self.store.values():
            if exclude_id is not None and p.id == exclude_id:
                continue
            if p.author_id.value == author_public_id and str(p.slug) == slug:
                return True
        return False

    def _to_summary(self, post: Post) -> PostSummary:
        category = None
        if post.category_id is not None:
            cat = self._uow.categories.store.get(post.category_id.value)
            if cat is not None:
                category = CategorySummary(
                    public_id=cat.id.value,
                    name=cat.name,
                    slug=str(cat.slug),
                    description=cat.description,
                    created_at=cat.created_at,
                )
        return PostSummary(
            public_id=post.id.value,
            title=post.title,
            slug=str(post.slug),
            content=post.content.body,
            content_format=post.content.format.value,
            author=AuthorSummary(public_id=post.author_id.value, username="author"),
            category=category,
            tags=tuple(
                TagSummary(public_id=t.id.value, name=t.name, slug=str(t.slug)) for t in post.tags
            ),
            is_deleted=post.is_deleted,
            created_at=post.created_at,
            updated_at=post.updated_at,
        )

    async def get_with_summary(self, id_: PostId) -> PostSummary | None:
        post = self.store.get(id_.value)
        return self._to_summary(post) if post is not None else None

    async def list_summaries(
        self,
        *,
        limit: int,
        cursor_created_at: datetime | None,
        cursor_id: UUID | None,
        category_public_id: UUID | None = None,
        tag_slug: str | None = None,
        author_public_id: UUID | None = None,
    ) -> PostListPage:
        rows = [p for p in self.store.values() if not p.is_deleted]
        if author_public_id is not None:
            rows = [p for p in rows if p.author_id.value == author_public_id]
        if category_public_id is not None:
            rows = [
                p
                for p in rows
                if p.category_id is not None and p.category_id.value == category_public_id
            ]
        rows.sort(key=lambda p: (p.created_at, p.id.value), reverse=True)
        if cursor_created_at is not None:
            rows = [p for p in rows if (p.created_at, p.id.value) < (cursor_created_at, cursor_id)]
        page = rows[:limit]
        next_cursor = None
        if len(rows) > limit:
            last = page[-1]
            next_cursor = PostCursor(created_at=last.created_at, public_id=last.id.value).encode()
        return PostListPage(items=tuple(self._to_summary(p) for p in page), next_cursor=next_cursor)


class FakeCommentRepo:
    def __init__(self, uow: FakeContentUoW) -> None:
        self._uow = uow
        self.store: dict[UUID, Comment] = {}

    async def get(self, id_: CommentId) -> Comment | None:
        return self.store.get(id_.value)

    async def add(self, entity: Comment) -> None:
        self.store[entity.id.value] = entity

    async def save(self, comment: Comment) -> None:
        self.store[comment.id.value] = comment

    def _to_summary(self, c: Comment) -> CommentSummary:
        return CommentSummary(
            public_id=c.id.value,
            post_public_id=c.post_id.value,
            parent_public_id=c.parent_id.value if c.parent_id else None,
            depth=c.depth,
            path=c.path or "00000001",
            content=c.content.body,
            content_format=c.content.format.value,
            is_deleted=c.is_deleted,
            author=AuthorSummary(
                public_id=c.author_id.value if c.author_id else None, username="author"
            ),
            created_at=c.created_at,
            updated_at=c.updated_at,
        )

    async def get_with_summary(self, id_: CommentId) -> CommentSummary | None:
        c = self.store.get(id_.value)
        return self._to_summary(c) if c is not None else None

    async def parent_path_for(self, parent_id: CommentId) -> tuple[str, int] | None:
        c = self.store.get(parent_id.value)
        return (c.path, c.depth) if c is not None else None

    async def list_tree_for_post(self, post_public_id: UUID) -> list[CommentSummary]:
        rows = [c for c in self.store.values() if c.post_id.value == post_public_id]
        rows.sort(key=lambda c: c.path or "")
        return [self._to_summary(c) for c in rows]


class FakeCategoryRepo:
    def __init__(self) -> None:
        self.store: dict[UUID, Category] = {}

    async def get(self, id_: CategoryId) -> Category | None:
        return self.store.get(id_.value)

    async def get_by_name(self, name: str) -> Category | None:
        return next((c for c in self.store.values() if c.name == name), None)

    async def get_by_slug(self, slug: str) -> Category | None:
        return next((c for c in self.store.values() if str(c.slug) == slug), None)

    async def add(self, entity: Category) -> None:
        self.store[entity.id.value] = entity

    async def remove(self, entity: Category) -> None:
        self.store.pop(entity.id.value, None)

    async def list_all(self) -> list[CategorySummary]:
        return [
            CategorySummary(
                public_id=c.id.value,
                name=c.name,
                slug=str(c.slug),
                description=c.description,
                created_at=c.created_at,
            )
            for c in sorted(self.store.values(), key=lambda c: c.name)
        ]


class FakeTagRepo:
    def __init__(self) -> None:
        self.store: dict[UUID, Tag] = {}

    async def get(self, id_: TagId) -> Tag | None:
        return self.store.get(id_.value)

    async def get_by_name(self, name: str) -> Tag | None:
        return next((t for t in self.store.values() if t.name == name), None)

    async def get_by_slug(self, slug: str) -> Tag | None:
        return next((t for t in self.store.values() if str(t.slug) == slug), None)

    async def add(self, tag: Tag) -> None:
        self.store[tag.id.value] = tag

    async def upsert_many_by_name(self, names: list[str]) -> list[Tag]:
        out: list[Tag] = []
        for name in names:
            existing = await self.get_by_name(name)
            if existing is None:
                existing = Tag.create(name)
                self.store[existing.id.value] = existing
            out.append(existing)
        return out

    async def list_all(self) -> list[Tag]:
        return sorted(self.store.values(), key=lambda t: t.name)


class FakeContentUoW:
    def __init__(self) -> None:
        self.posts = FakePostRepo(self)
        self.comments = FakeCommentRepo(self)
        self.categories = FakeCategoryRepo()
        self.tags = FakeTagRepo()
        self.commits = 0
        self.rollbacks = 0

    async def __aenter__(self) -> FakeContentUoW:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1

    async def resolve_user_id(self, user_public_id: UUID) -> int | None:
        return 1


# --------------------------------------------------------------------------- #
# Fixtures + helpers                                                          #
# --------------------------------------------------------------------------- #


@pytest.fixture
def uow() -> FakeContentUoW:
    return FakeContentUoW()


@pytest.fixture
def bus() -> FakeBus:
    return FakeBus()


def _seed_category(uow: FakeContentUoW, name: str = "Spinning") -> Category:
    cat = Category(id=CategoryId.new(), name=name, slug=Slug.from_text(name))
    uow.categories.store[cat.id.value] = cat
    return cat


def _seed_post(
    uow: FakeContentUoW, *, author: UUID | None = None, title: str = "Seed post title"
) -> Post:
    from app.modules.content.domain.value_objects import ContentFormat, MarkdownContent
    from app.modules.identity.domain.user import UserId

    post = Post.create(
        author_id=UserId(author or uuid4()),
        title=title,
        content=MarkdownContent(body="Seed body content.", format=ContentFormat.MARKDOWN),
    )
    post.pull_events()
    uow.posts.store[post.id.value] = post
    return post


# --------------------------------------------------------------------------- #
# CreatePost                                                                  #
# --------------------------------------------------------------------------- #


class TestCreatePost:
    async def test_creates_post_and_publishes_event(
        self, uow: FakeContentUoW, bus: FakeBus
    ) -> None:
        author = uuid4()
        res = await CreatePostUseCase(uow, bus).execute(
            CreatePostCommand(author_public_id=author, title="My fishing trip", content="Great day")
        )
        assert isinstance(res, Ok)
        assert res.value.title == "My fishing trip"
        assert uow.commits == 1
        assert "PostCreated" in bus.types()

    async def test_upserts_tags(self, uow: FakeContentUoW, bus: FakeBus) -> None:
        res = await CreatePostUseCase(uow, bus).execute(
            CreatePostCommand(
                author_public_id=uuid4(),
                title="Tagged post here",
                content="body",
                tag_names=("Spinning", "spinning", "Karp"),
            )
        )
        assert isinstance(res, Ok)
        # case-folded + de-duplicated → 2 distinct tags
        assert {t.name for t in res.value.tags} == {"spinning", "karp"}

    async def test_unknown_category_returns_error(self, uow: FakeContentUoW, bus: FakeBus) -> None:
        res = await CreatePostUseCase(uow, bus).execute(
            CreatePostCommand(
                author_public_id=uuid4(),
                title="Bad category post",
                content="body",
                category_public_id=uuid4(),
            )
        )
        assert isinstance(res, Err)
        assert isinstance(res.error, CategoryNotFound)
        assert uow.commits == 0

    async def test_links_existing_category(self, uow: FakeContentUoW, bus: FakeBus) -> None:
        cat = _seed_category(uow)
        res = await CreatePostUseCase(uow, bus).execute(
            CreatePostCommand(
                author_public_id=uuid4(),
                title="Categorised post",
                content="body",
                category_public_id=cat.id.value,
            )
        )
        assert isinstance(res, Ok)
        assert res.value.category is not None
        assert res.value.category.public_id == cat.id.value

    async def test_duplicate_slug_for_same_author_rejected(
        self, uow: FakeContentUoW, bus: FakeBus
    ) -> None:
        author = uuid4()
        cmd = CreatePostCommand(author_public_id=author, title="Same title twice", content="body")
        first = await CreatePostUseCase(uow, bus).execute(cmd)
        assert isinstance(first, Ok)
        second = await CreatePostUseCase(uow, bus).execute(cmd)
        assert isinstance(second, Err)
        assert isinstance(second.error, SlugAlreadyTaken)


# --------------------------------------------------------------------------- #
# UpdatePost / DeletePost                                                     #
# --------------------------------------------------------------------------- #


class TestUpdatePost:
    async def test_author_can_update(self, uow: FakeContentUoW, bus: FakeBus) -> None:
        author = uuid4()
        post = _seed_post(uow, author=author)
        res = await UpdatePostUseCase(uow, bus).execute(
            UpdatePostCommand(
                post_public_id=post.id.value,
                actor_public_id=author,
                title="An updated title",
            )
        )
        assert isinstance(res, Ok)
        assert res.value.title == "An updated title"
        assert "PostUpdated" in bus.types()

    async def test_non_owner_without_moderation_rejected(
        self, uow: FakeContentUoW, bus: FakeBus
    ) -> None:
        post = _seed_post(uow, author=uuid4())
        res = await UpdatePostUseCase(uow, bus).execute(
            UpdatePostCommand(
                post_public_id=post.id.value,
                actor_public_id=uuid4(),
                title="Hacked title",
            )
        )
        assert isinstance(res, Err)
        assert isinstance(res.error, NotPostOwner)

    async def test_moderator_can_update_others_post(
        self, uow: FakeContentUoW, bus: FakeBus
    ) -> None:
        post = _seed_post(uow, author=uuid4())
        res = await UpdatePostUseCase(uow, bus).execute(
            UpdatePostCommand(
                post_public_id=post.id.value,
                actor_public_id=uuid4(),
                title="Moderated title",
                actor_can_moderate=True,
            )
        )
        assert isinstance(res, Ok)

    async def test_update_missing_post(self, uow: FakeContentUoW, bus: FakeBus) -> None:
        res = await UpdatePostUseCase(uow, bus).execute(
            UpdatePostCommand(post_public_id=uuid4(), actor_public_id=uuid4(), title="x title")
        )
        assert isinstance(res, Err)
        assert isinstance(res.error, PostNotFound)


class TestDeletePost:
    async def test_author_soft_deletes(self, uow: FakeContentUoW, bus: FakeBus) -> None:
        author = uuid4()
        post = _seed_post(uow, author=author)
        res = await DeletePostUseCase(uow, bus).execute(
            DeletePostCommand(post_public_id=post.id.value, actor_public_id=author)
        )
        assert isinstance(res, Ok)
        assert uow.posts.store[post.id.value].is_deleted is True
        assert "PostDeleted" in bus.types()

    async def test_non_owner_rejected(self, uow: FakeContentUoW, bus: FakeBus) -> None:
        post = _seed_post(uow, author=uuid4())
        res = await DeletePostUseCase(uow, bus).execute(
            DeletePostCommand(post_public_id=post.id.value, actor_public_id=uuid4())
        )
        assert isinstance(res, Err)
        assert isinstance(res.error, NotPostOwner)


# --------------------------------------------------------------------------- #
# GetPost / ListPosts                                                         #
# --------------------------------------------------------------------------- #


class TestGetPost:
    async def test_returns_existing(self, uow: FakeContentUoW) -> None:
        post = _seed_post(uow)
        res = await GetPostUseCase(uow).execute(post.id.value)
        assert isinstance(res, Ok)
        assert res.value.public_id == post.id.value

    async def test_missing_is_not_found(self, uow: FakeContentUoW) -> None:
        res = await GetPostUseCase(uow).execute(uuid4())
        assert isinstance(res, Err)
        assert isinstance(res.error, PostNotFound)

    async def test_soft_deleted_is_not_found(self, uow: FakeContentUoW) -> None:
        post = _seed_post(uow)
        post.soft_delete()
        res = await GetPostUseCase(uow).execute(post.id.value)
        assert isinstance(res, Err)


class TestListPosts:
    async def test_pagination_returns_cursor(self, uow: FakeContentUoW) -> None:
        for i in range(3):
            _seed_post(uow, title=f"Post number {i}")
        res = await ListPostsUseCase(uow).execute(ListPostsQuery(limit=2))
        assert isinstance(res, Ok)
        assert len(res.value.items) == 2
        assert res.value.next_cursor is not None

    async def test_last_page_has_no_cursor(self, uow: FakeContentUoW) -> None:
        _seed_post(uow, title="Only one post")
        res = await ListPostsUseCase(uow).execute(ListPostsQuery(limit=20))
        assert isinstance(res, Ok)
        assert res.value.next_cursor is None

    async def test_limit_is_clamped(self, uow: FakeContentUoW) -> None:
        res = await ListPostsUseCase(uow).execute(ListPostsQuery(limit=10_000))
        assert isinstance(res, Ok)  # no crash; MAX_LIMIT applied internally


# --------------------------------------------------------------------------- #
# Comments                                                                    #
# --------------------------------------------------------------------------- #


class TestComments:
    async def test_add_top_level_comment(self, uow: FakeContentUoW, bus: FakeBus) -> None:
        post = _seed_post(uow)
        res = await AddCommentUseCase(uow, bus).execute(
            AddCommentCommand(
                post_public_id=post.id.value, author_public_id=uuid4(), content="Nice catch!"
            )
        )
        assert isinstance(res, Ok)
        assert res.value.depth == 0
        assert "CommentAdded" in bus.types()

    async def test_reply_increments_depth(self, uow: FakeContentUoW, bus: FakeBus) -> None:
        post = _seed_post(uow)
        parent = await AddCommentUseCase(uow, bus).execute(
            AddCommentCommand(
                post_public_id=post.id.value, author_public_id=uuid4(), content="parent"
            )
        )
        assert isinstance(parent, Ok)
        reply = await AddCommentUseCase(uow, bus).execute(
            AddCommentCommand(
                post_public_id=post.id.value,
                author_public_id=uuid4(),
                content="reply",
                parent_comment_public_id=parent.value.public_id,
            )
        )
        assert isinstance(reply, Ok)
        assert reply.value.depth == 1

    async def test_comment_on_missing_post(self, uow: FakeContentUoW, bus: FakeBus) -> None:
        res = await AddCommentUseCase(uow, bus).execute(
            AddCommentCommand(post_public_id=uuid4(), author_public_id=uuid4(), content="x")
        )
        assert isinstance(res, Err)
        assert isinstance(res.error, PostNotFound)

    async def test_reply_to_missing_parent(self, uow: FakeContentUoW, bus: FakeBus) -> None:
        post = _seed_post(uow)
        res = await AddCommentUseCase(uow, bus).execute(
            AddCommentCommand(
                post_public_id=post.id.value,
                author_public_id=uuid4(),
                content="x",
                parent_comment_public_id=uuid4(),
            )
        )
        assert isinstance(res, Err)
        assert isinstance(res.error, CommentNotFound)

    async def test_update_comment_by_author(self, uow: FakeContentUoW, bus: FakeBus) -> None:
        post = _seed_post(uow)
        author = uuid4()
        added = await AddCommentUseCase(uow, bus).execute(
            AddCommentCommand(
                post_public_id=post.id.value, author_public_id=author, content="original"
            )
        )
        assert isinstance(added, Ok)
        res = await UpdateCommentUseCase(uow, bus).execute(
            UpdateCommentCommand(
                comment_public_id=added.value.public_id,
                actor_public_id=author,
                content="edited",
            )
        )
        assert isinstance(res, Ok)
        assert res.value.content == "edited"

    async def test_update_comment_by_stranger_rejected(
        self, uow: FakeContentUoW, bus: FakeBus
    ) -> None:
        post = _seed_post(uow)
        added = await AddCommentUseCase(uow, bus).execute(
            AddCommentCommand(
                post_public_id=post.id.value, author_public_id=uuid4(), content="original"
            )
        )
        assert isinstance(added, Ok)
        res = await UpdateCommentUseCase(uow, bus).execute(
            UpdateCommentCommand(
                comment_public_id=added.value.public_id,
                actor_public_id=uuid4(),
                content="hijack",
            )
        )
        assert isinstance(res, Err)
        assert isinstance(res.error, NotCommentOwner)

    async def test_delete_comment_soft_deletes(self, uow: FakeContentUoW, bus: FakeBus) -> None:
        post = _seed_post(uow)
        author = uuid4()
        added = await AddCommentUseCase(uow, bus).execute(
            AddCommentCommand(
                post_public_id=post.id.value, author_public_id=author, content="to delete"
            )
        )
        assert isinstance(added, Ok)
        res = await DeleteCommentUseCase(uow, bus).execute(
            DeleteCommentCommand(comment_public_id=added.value.public_id, actor_public_id=author)
        )
        assert isinstance(res, Ok)
        assert uow.comments.store[added.value.public_id].is_deleted is True

    async def test_get_comment_tree(self, uow: FakeContentUoW, bus: FakeBus) -> None:
        post = _seed_post(uow)
        await AddCommentUseCase(uow, bus).execute(
            AddCommentCommand(post_public_id=post.id.value, author_public_id=uuid4(), content="c1")
        )
        res = await GetCommentTreeUseCase(uow).execute(post.id.value)
        assert isinstance(res, Ok)
        assert len(res.value) == 1

    async def test_get_comment_tree_missing_post(self, uow: FakeContentUoW) -> None:
        res = await GetCommentTreeUseCase(uow).execute(uuid4())
        assert isinstance(res, Err)
        assert isinstance(res.error, PostNotFound)


# --------------------------------------------------------------------------- #
# Categories / Tags                                                           #
# --------------------------------------------------------------------------- #


class TestCategories:
    async def test_create_category(self, uow: FakeContentUoW, bus: FakeBus) -> None:
        res = await CreateCategoryUseCase(uow, bus).execute(
            CreateCategoryCommand(name="Karpiowanie", description="Carp fishing")
        )
        assert isinstance(res, Ok)
        assert res.value.slug == "karpiowanie"
        assert "CategoryCreated" in bus.types()

    async def test_duplicate_name_rejected(self, uow: FakeContentUoW, bus: FakeBus) -> None:
        _seed_category(uow, name="Muszka")
        res = await CreateCategoryUseCase(uow, bus).execute(CreateCategoryCommand(name="Muszka"))
        assert isinstance(res, Err)
        assert isinstance(res.error, CategoryAlreadyExists)

    async def test_delete_category(self, uow: FakeContentUoW, bus: FakeBus) -> None:
        cat = _seed_category(uow)
        res = await DeleteCategoryUseCase(uow, bus).execute(
            DeleteCategoryCommand(category_public_id=cat.id.value)
        )
        assert isinstance(res, Ok)
        assert cat.id.value not in uow.categories.store
        assert "CategoryDeleted" in bus.types()

    async def test_delete_missing_category(self, uow: FakeContentUoW, bus: FakeBus) -> None:
        res = await DeleteCategoryUseCase(uow, bus).execute(
            DeleteCategoryCommand(category_public_id=uuid4())
        )
        assert isinstance(res, Err)
        assert isinstance(res.error, CategoryNotFound)

    async def test_list_categories_alphabetical(self, uow: FakeContentUoW) -> None:
        _seed_category(uow, name="Zander")
        _seed_category(uow, name="Amur")
        res = await ListCategoriesUseCase(uow).execute()
        assert isinstance(res, Ok)
        assert [c.name for c in res.value] == ["Amur", "Zander"]


class TestTags:
    async def test_create_tag(self, uow: FakeContentUoW, bus: FakeBus) -> None:
        res = await CreateTagUseCase(uow, bus).execute(CreateTagCommand(name="  Spinning  "))
        assert isinstance(res, Ok)
        assert res.value.name == "spinning"
        assert "TagCreated" in bus.types()

    async def test_duplicate_tag_rejected(self, uow: FakeContentUoW, bus: FakeBus) -> None:
        await CreateTagUseCase(uow, bus).execute(CreateTagCommand(name="karp"))
        res = await CreateTagUseCase(uow, bus).execute(CreateTagCommand(name="KARP"))
        assert isinstance(res, Err)
        assert isinstance(res.error, TagAlreadyExists)

    async def test_list_tags(self, uow: FakeContentUoW, bus: FakeBus) -> None:
        await CreateTagUseCase(uow, bus).execute(CreateTagCommand(name="zander"))
        await CreateTagUseCase(uow, bus).execute(CreateTagCommand(name="amur"))
        res = await ListTagsUseCase(uow).execute()
        assert isinstance(res, Ok)
        assert [t.name for t in res.value] == ["amur", "zander"]
