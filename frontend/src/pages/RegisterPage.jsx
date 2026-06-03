import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useTranslation } from '../i18n/LangContext';
import { useAuth } from '../auth/AuthContext';

/**
 * Ekran rejestracji. Walidacja zgodna z backendem:
 *   username 3–50 [a-zA-Z0-9_], email, hasło min. 8 znaków.
 * Po udanej rejestracji AuthContext loguje automatycznie.
 */
export function RegisterPage() {
  const t = useTranslation();
  const a = t.auth;
  const navigate = useNavigate();
  const location = useLocation();
  const { register } = useAuth();

  const [form, setForm] = useState({ username: '', email: '', password: '' });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const onChange = (e) =>
    setForm((f) => ({ ...f, [e.target.name]: e.target.value }));

  const onSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    const result = await register(form);
    setBusy(false);
    if (result.ok) {
      const from = location.state?.from ?? '/';
      navigate(from, { replace: true });
    } else {
      setError(result.error?.message ?? t.common.error);
    }
  };

  return (
    <div className="shell auth-shell">
      <form className="auth-card bracketed" onSubmit={onSubmit}>
        <span className="br-tr" />
        <span className="br-bl" />
        <h1 className="auth-title">{a.registerTitle}</h1>

        {error && <div className="form-error" role="alert">{error}</div>}

        <label className="field">
          <span className="field-label">{a.username}</span>
          <input
            name="username"
            value={form.username}
            onChange={onChange}
            autoComplete="username"
            minLength={3}
            maxLength={50}
            pattern="[a-zA-Z0-9_]+"
            required
          />
          <span className="field-hint">{a.usernameHint}</span>
        </label>

        <label className="field">
          <span className="field-label">{a.email}</span>
          <input
            type="email"
            name="email"
            value={form.email}
            onChange={onChange}
            autoComplete="email"
            required
          />
        </label>

        <label className="field">
          <span className="field-label">{a.password}</span>
          <input
            type="password"
            name="password"
            value={form.password}
            onChange={onChange}
            autoComplete="new-password"
            minLength={8}
            required
          />
          <span className="field-hint">{a.passwordHint}</span>
        </label>

        <button type="submit" className="btn primary full" disabled={busy}>
          {busy ? a.registering : a.registerCta}
        </button>

        <div className="auth-switch">
          {a.haveAccount}{' '}
          <Link to="/login" state={location.state}>
            {a.goLogin}
          </Link>
        </div>
      </form>
    </div>
  );
}
