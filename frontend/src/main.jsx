import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import { LangProvider } from './i18n/LangContext';
import { ThemeProvider } from './theme/ThemeContext';
import './styles/globals.css';

/**
 * Bootstrap aplikacji. Kolejność providerów: Theme → Lang → Router → App.
 * Theme jest niezależny od języka, ale używany przez wszystkie strony,
 * więc trzymamy go najwyżej.
 */
ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ThemeProvider>
      <LangProvider>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </LangProvider>
    </ThemeProvider>
  </React.StrictMode>,
);
