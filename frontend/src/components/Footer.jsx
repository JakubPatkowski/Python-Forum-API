import { useLang } from '../i18n/LangContext';

export function Footer() {
  const { t } = useLang();
  return (
    <footer className="shell footer">
      <div className="status">
        <span className="pulse" />
        <span>{t.online}</span>
        <span style={{ opacity: 0.4, marginLeft: 16 }}>·</span>
        <span style={{ marginLeft: 16 }}>{t.sync}</span>
      </div>
      <div>{t.build}</div>
    </footer>
  );
}
