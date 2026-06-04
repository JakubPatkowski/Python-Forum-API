import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from '../../i18n/LangContext';
import { Modal } from '../Modal';
import { FileUploader } from '../files/FileUploader';
import { MarkdownEditor } from '../MarkdownEditor';
import { IconPicker } from './IconPicker';
import {
  useCategories,
  useCreatePost,
  useUpdatePost,
} from '../../hooks/useContentQueries';
import { useAttachToPost } from '../../hooks/useFiles';
import { filesApi } from '../../api/resources';

/**
 * Modal tworzenia / edycji wątku. Tryb edycji włącza `post`.
 * Tagi po przecinku — backend tworzy brakujące sam (CreatePostRequest.tags).
 * Po stworzeniu/edycji podpina nowo wgrane pliki (jeśli są).
 */
export function NewPostModal({ onClose, defaultCategoryId = '', post = null }) {
  const t = useTranslation();
  const c = t.compose;
  const isEdit = Boolean(post);
  const navigate = useNavigate();
  const { data: categories = [] } = useCategories();
  const createPost = useCreatePost();
  const updatePost = useUpdatePost();

  const [form, setForm] = useState({
    title: post?.title ?? '',
    content: post?.content ?? '',
    category_id: post?.category?.public_id ?? defaultCategoryId,
    tags: (post?.tags ?? []).map((x) => x.name).join(', '),
  });
  const [uploaded, setUploaded] = useState([]); // FileResponse[]
  const [iconFile, setIconFile] = useState(null); // ikona wątku (upload po create)
  const [error, setError] = useState(null);

  // Podgląd już ustawionej ikony w trybie edycji (cache-bust po updacie).
  const currentIconUrl = isEdit
    ? `/api/v1/posts/${post.id}/icon?variant=thumb`
    : null;

  const attachToPost = useAttachToPost(post?.id);
  const pending = createPost.isPending || updatePost.isPending;

  const onChange = (e) =>
    setForm((f) => ({ ...f, [e.target.name]: e.target.value }));

  const onSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    if (!form.content.trim()) {
      setError(t.compose.content + ' — ' + t.common.empty);
      return;
    }
    const tags = form.tags
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)
      .slice(0, 10);
    const payload = {
      title: form.title.trim(),
      content: form.content.trim(),
      content_format: 'markdown',
      category_id: form.category_id || null,
      tags,
    };
    try {
      const fileIds = uploaded.map((f) => f.id);
      if (isEdit) {
        await updatePost.mutateAsync({ id: post.id, payload });
        if (fileIds.length) await attachToPost.mutateAsync(fileIds);
        if (iconFile) await filesApi.setPostIcon(post.id, iconFile);
        onClose();
      } else {
        const created = await createPost.mutateAsync(payload);
        if (fileIds.length) await filesApi.attachToPost(created.id, fileIds);
        if (iconFile) await filesApi.setPostIcon(created.id, iconFile);
        onClose();
        navigate(`/posts/${created.id}`);
      }
    } catch (err) {
      setError(err?.message ?? t.common.error);
    }
  };

  return (
    <Modal title={isEdit ? c.editPost : c.newPost} onClose={onClose}>
      <form onSubmit={onSubmit}>
        {error && <div className="form-error" role="alert">{error}</div>}

        <label className="field">
          <span className="field-label">{c.title}</span>
          <input
            name="title"
            value={form.title}
            onChange={onChange}
            minLength={3}
            maxLength={200}
            required
          />
        </label>

        <label className="field">
          <span className="field-label">{c.category}</span>
          <select name="category_id" value={form.category_id} onChange={onChange}>
            <option value="">{c.noCategory}</option>
            {categories.map((cat) => (
              <option key={cat.id} value={cat.id}>
                {cat.name}
              </option>
            ))}
          </select>
        </label>

        <IconPicker
          label={c.threadIcon}
          hint={c.iconHint}
          file={iconFile}
          onChange={setIconFile}
          currentUrl={currentIconUrl}
        />

        <div className="field">
          <span className="field-label">{c.content}</span>
          <MarkdownEditor
            value={form.content}
            onChange={(v) => setForm((f) => ({ ...f, content: v }))}
            rows={8}
          />
        </div>

        <label className="field">
          <span className="field-label">{c.tags}</span>
          <input name="tags" value={form.tags} onChange={onChange} />
        </label>

        <div className="field">
          <span className="field-label">{t.files.attachments}</span>
          <FileUploader onChange={setUploaded} />
        </div>

        <div className="form-actions">
          <button type="button" className="btn" onClick={onClose}>
            {t.common.cancel}
          </button>
          <button type="submit" className="btn primary" disabled={pending}>
            {pending
              ? isEdit ? c.saving : c.publishing
              : isEdit ? c.saveChanges : c.publish}
          </button>
        </div>
      </form>
    </Modal>
  );
}
