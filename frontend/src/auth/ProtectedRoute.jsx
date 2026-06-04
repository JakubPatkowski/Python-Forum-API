import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from './AuthContext';

/**
 * Bramka tras wymagających zalogowania. W trakcie odtwarzania sesji
 * ('loading') pokazujemy lekki placeholder, żeby nie mignąć ekranem logowania
 * zalogowanemu użytkownikowi po odświeżeniu strony.
 */
export function ProtectedRoute({ children }) {
  const { status } = useAuth();
  const location = useLocation();

  if (status === 'loading') {
    return <div className="route-loading mono">Wczytywanie sesji…</div>;
  }
  if (status !== 'authenticated') {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return children;
}
