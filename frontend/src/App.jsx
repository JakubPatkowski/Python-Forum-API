import { Navigate, Route, Routes } from 'react-router-dom';
import { Layout } from './components/Layout';
import { HomePage } from './pages/HomePage';
import { ProfilePage } from './pages/ProfilePage';
import { OpinionsPage } from './pages/OpinionsPage';

/**
 * Drzewo tras aplikacji. Trzy widoki publiczne renderowane pod wspólnym `<Layout />`.
 * Nieznane ścieżki przekierowujemy na `/`.
 */
export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index           element={<HomePage />} />
        <Route path="profile"  element={<ProfilePage />} />
        <Route path="opinions" element={<OpinionsPage />} />
        <Route path="*"        element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
