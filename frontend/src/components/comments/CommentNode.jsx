import { useState } from 'react';
import { useLang } from '../../i18n/LangContext';
import { useAuth } from '../../auth/AuthContext';
import { Avatar } from '../Avatar';
import { LikeButton } from '../LikeButton';
import { Markdown } from '../Markdown';
import { MarkdownEditor } from '../MarkdownEditor';
import { Attachments } from '../files/Attachments';
import { CommentForm } from './CommentForm';
import {
  useDeleteComment,
  useUpdateComment,
} from '../../hooks/useContentQueries';
import { useCommentFiles } from '../../hooks/useFiles';
import { timeAgo } from '../../utils/format';

/**
 * Węzeł drzewa komentarzy + rekurencyjnie dzieci. Obsługuje edycję inline
 * (autor / comment.update.any), usuwanie, odpowiedzi i wyświetlanie załączników.
 */
export function CommentNode({ comment, postId, maxDepth = 5 }) {
  const { t, lang } = useLang();
  const c = t.compose;
  const { isAuthenticated, user, hasPermission } = useAuth();
  const deleteComment = useDeleteComment(postId);
  const updateComment = useUpdateComment(postId);
  const filesQ = useCommentFiles(comment.id, !comment.is_deleted);

  const [replying, setReplying] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(comment.content);

  const isAuthor = user && comment.author?.public_id === user.id;
  const canEdit = !comment.is_deleted && (isAuthor || hasPermission('comment.update.any'));
  const canDelete = !comment.is_deleted && (isAuthor || hasPermission('comment.delete.any'));
  const canReply = isAuthenticated && comment.depth < maxDepth - 1;

  const saveEdit = async () => {
    if (!draft.trim()) return;
    await updateComment.mutateAsync({
      id: comment.id,
      payload: { content: draft.trim(), content_format: 'markdown' },
    });
    setEditing(false);
  };

  return (
    <div className="comment" style={{ marginLeft: comment.depth > 0 ? 20 : 0 }}>
      <div className="comment-main">
        <Avatar userId={comment.author?.public_id} username={comment.author?.username} size="sm" />
        <div className="comment-body">
          <div className="comment-meta">
            <span className="author">@{comment.author?.username ?? '???'}</span>
            <span>·</span>
            <span className="mono dim">{timeAgo(comment.created_at, lang)}</span>
          </div>

          {comment.is_deleted ? (
            <p className="comment-deleted mono mute">{c.deleted}</p>
          ) : editing ? (
            <div className="edit-box">
              <MarkdownEditor value={draft} onChange={setDraft} rows={3} />
              <div className="form-actions">
                <button type="button" className="btn" onClick={() => { setEditing(false); setDraft(comment.content); }}>
                  {t.common.cancel}
                </button>
                <button type="button" className="btn primary" onClick={saveEdit} disabled={updateComment.isPending}>
                  {updateComment.isPending ? c.saving : c.saveChanges}
                </button>
              </div>
            </div>
          ) : (
            <Markdown source={comment.content} format={comment.content_format} className="comment-content" />
          )}

          {!comment.is_deleted && !editing && filesQ.data?.length > 0 && (
            <Attachments files={filesQ.data} />
          )}

          {!comment.is_deleted && !editing && (
            <div className="comment-actions">
              <LikeButton target="comments" publicId={comment.id} size="sm" />
              {canReply && (
                <button type="button" className="link-btn" onClick={() => setReplying((v) => !v)}>
                  {c.reply}
                </button>
              )}
              {canEdit && (
                <button type="button" className="link-btn" onClick={() => setEditing(true)}>
                  {c.edit}
                </button>
              )}
              {canDelete && (
                <button
                  type="button"
                  className="link-btn danger"
                  onClick={() => {
                    if (window.confirm(c.confirmDelete)) deleteComment.mutate(comment.id);
                  }}
                >
                  {c.delete}
                </button>
              )}
            </div>
          )}

          {replying && (
            <CommentForm postId={postId} parentId={comment.id} autoFocus onDone={() => setReplying(false)} />
          )}
        </div>
      </div>

      {comment.children?.length > 0 && (
        <div className="comment-children">
          {comment.children.map((child) => (
            <CommentNode key={child.id} comment={child} postId={postId} maxDepth={maxDepth} />
          ))}
        </div>
      )}
    </div>
  );
}
