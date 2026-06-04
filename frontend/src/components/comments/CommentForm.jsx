import { useState } from 'react';
import { useTranslation } from '../../i18n/LangContext';
import { useAddComment } from '../../hooks/useContentQueries';
import { filesApi } from '../../api/resources';
import { FileUploader } from '../files/FileUploader';
import { MarkdownEditor } from '../MarkdownEditor';

/**
 * Formularz komentarza (top-level lub odpowiedź). Po dodaniu komentarza
 * podpina ewentualne wgrane pliki przez POST /comments/{id}/files.
 */
export function CommentForm({ postId, parentId = null, onDone, autoFocus = false }) {
  const t = useTranslation();
  const c = t.compose;
  const addComment = useAddComment(postId);
  const [content, setContent] = useState('');
  const [uploaded, setUploaded] = useState([]);
  const [error, setError] = useState(null);

  const onSubmit = async (e) => {
    e.preventDefault();
    if (!content.trim()) return;
    setError(null);
    try {
      const created = await addComment.mutateAsync({
        post_id: postId,
        parent_id: parentId,
        content: content.trim(),
        content_format: 'markdown',
      });
      const fileIds = uploaded.map((f) => f.id);
      if (fileIds.length && created?.id) {
        await filesApi.attachToComment(created.id, fileIds);
      }
      setContent('');
      setUploaded([]);
      if (onDone) onDone();
    } catch (err) {
      setError(err?.message ?? t.common.error);
    }
  };

  return (
    <form className="comment-form" onSubmit={onSubmit}>
      {error && <div className="form-error" role="alert">{error}</div>}
      <MarkdownEditor
        value={content}
        onChange={setContent}
        placeholder={c.comment}
        rows={parentId ? 2 : 3}
      />
      <div className="comment-form-foot">
        <FileUploader onChange={setUploaded} />
        <div className="form-actions">
          {parentId && onDone && (
            <button type="button" className="btn" onClick={onDone}>
              {t.common.cancel}
            </button>
          )}
          <button type="submit" className="btn primary" disabled={addComment.isPending}>
            {addComment.isPending ? c.sending : c.send}
          </button>
        </div>
      </div>
    </form>
  );
}
