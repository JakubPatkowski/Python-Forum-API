import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import App from './App';
import { queryClient } from './query/queryClient';
import { AuthProvider } from './auth/AuthContext';
import { LangProvider } from './i18n/LangContext';
import { ThemeProvider } from './theme/ThemeContext';
import './styles/globals.css';

/**
 * Bootstrap aplikacji. Kolejność providerów:
 *   QueryClient → Router → Auth → Theme → Lang → App
 * QueryClient na zewnątrz, bo AuthProvider używa useQueryClient (czyszczenie
 * cache przy wylogowaniu). Auth nad Theme/Lang, bo te nie zależą od sesji,
 * a komponenty UI potrzebują obu kontekstów.
 */
ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <ThemeProvider>
            <LangProvider>
              <App />
            </LangProvider>
          </ThemeProvider>
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
);
