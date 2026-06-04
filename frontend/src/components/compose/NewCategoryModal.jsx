import { useState } from 'react';
import { useTranslation } from '../../i18n/LangContext';
import { Modal } from '../Modal';
import { IconPicker } from './IconPicker';
import { useCreateCategory } from '../../hooks/useContentQueries';
import { useSetCategoryImage } from '../../hooks/useFiles';

/** Formularz nowej kategorii. Slug generuje backend, więc nie pytamy o niego. */
export function NewCategoryModal({ onClose }) {
  const t = useTranslation();
  const c = t.compose;
  const createCategory = useCreateCategory();
  const setCategoryImage = useSetCategoryImage();

  const [form, setForm] = useState({ name: '', description: '' });
  const [iconFile, setIconFile] = useState(null); // ikona — upload po create
  const [error, setError] = useState(null);

  const pending = createCategory.isPending || setCategoryImage.isPending;

  const onChange = (e) =>
    setForm((f) => ({ ...f, [e.target.name]: e.target.value }));

  const onSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    try {
      const created = await createCategory.mutateAsync({
        name: form.name.trim(),
        description: form.description.trim() || null,
      });
      // Ikonę ustawiamy po utworzeniu — endpoint wymaga istniejącej kategorii.
      if (iconFile && created?.id) {
        await setCategoryImage.mutateAsync({ categoryId: created.id, file: iconFile });
      }
      onClose();
    } catch (err) {
      setError(err?.message ?? t.common.error);
    }
  };

  return (
    <Modal title={c.newCategory} onClose={onClose}>
      <form onSubmit={onSubmit}>
        {error && <div className="form-error" role="alert">{error}</div>}

        <label className="field">
          <span className="field-label">{c.categoryName}</span>
          <input
            name="name"
            value={form.name}
            onChange={onChange}
            minLength={1}
            maxLength={100}
            required
          />
        </label>

        <label className="field">
          <span className="field-label">{c.categoryDesc}</span>
          <textarea
            name="description"
            value={form.description}
            onChange={onChange}
            rows={3}
          />
        </label>

        <IconPicker
          label={c.categoryIcon}
          hint={c.iconHint}
          file={iconFile}
          onChange={setIconFile}
        />

        <div className="form-actions">
          <button type="button" className="btn" onClick={onClose}>
            {t.common.cancel}
          </button>
          <button
            type="submit"
            className="btn primary"
            disabled={pending}
          >
            {pending ? c.creating : c.create}
          </button>
        </div>
      </form>
    </Modal>
  );
}
