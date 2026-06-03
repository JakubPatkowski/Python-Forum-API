import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useTranslation } from '../i18n/LangContext';
import { useAuth } from '../auth/AuthContext';

/**
 * Ekran logowania. Po sukcesie wraca tam, skąd przyszedł ProtectedRoute
 * (state.from) lub na stronę główną.
 */
export function LoginPage() {
  const t = useTranslation();
  const a = t.auth;
  const navigate = useNavigate();
  const location = useLocation();
  const { login } = useAuth();

  const [form, setForm] = useState({ login: '', password: '' });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const onChange = (e) =>
    setForm((f) => ({ ...f, [e.target.name]: e.target.value }));

  const onSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    const result = await login(form);
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
        <h1 className="auth-title">{a.loginTitle}</h1>

        {error && <div className="form-error" role="alert">{error}</div>}

        <label className="field">
          <span className="field-label">{a.loginField}</span>
          <input
            name="login"
            value={form.login}
            onChange={onChange}
            autoComplete="username"
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
            autoComplete="current-password"
            required
          />
        </label>

        <button type="submit" className="btn primary full" disabled={busy}>
          {busy ? a.loggingIn : a.loginCta}
        </button>

        <div className="auth-switch">
          {a.noAccount}{' '}
          <Link to="/register" state={location.state}>
            {a.goRegister}
          </Link>
        </div>
      </form>
    </div>
  );
}
