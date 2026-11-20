import { useState } from 'react';
import { Archive, Eye, EyeOff, FileCode2, FolderClosed, LoaderCircle, LockKeyhole, UserRound } from 'lucide-react';
import { api } from './api';
import { Brand, ErrorBox } from './ui';

export function Auth({ expired, onSession }) {
  const [registering, setRegistering] = useState(false);
  const [visible, setVisible] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function submit(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const credentials = { username: form.get('username').trim(), password: form.get('password') };
    setBusy(true);
    setError(null);
    try {
      if (registering) {
        await api.register(credentials);
        // Registration can succeed independently of signing in.
        setRegistering(false);
      }
      await api.login(credentials);
      onSession(await api.me());
    } catch (failure) {
      setError(failure);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-page">
      <header className="auth-brand"><Brand /></header>
      <div className="auth-layout">
        <section className="auth-visual" aria-label="Файловый менеджер">
          <div className="auth-illustration" aria-hidden="true">
            <div className="auth-tile auth-tile-code"><FileCode2 size={30} /></div>
            <div className="auth-tile auth-tile-folder"><FolderClosed size={51} strokeWidth={1.6} /></div>
            <div className="auth-tile auth-tile-zip"><Archive size={29} /></div>
          </div>
          <h1>Личное<br />хранилище</h1>
          <p>Файлы, папки и архивы в одном файловом менеджере.</p>
        </section>
        <section className="auth-card" aria-labelledby="auth-title">
          <div className="auth-lock"><LockKeyhole size={23} /></div>
          <h2 id="auth-title">{registering ? 'Создать аккаунт' : 'Вход в аккаунт'}</h2>
          <p className="muted">{registering ? 'Задайте логин и пароль.' : 'Войдите, чтобы открыть свои файлы.'}</p>
          {expired && !error && <div className="session-notice" role="status">Сессия истекла. Войдите снова.</div>}
          <form className="auth-form" onSubmit={submit}>
            <label className="field">
              <span>Логин</span>
              <span className="input-shell">
                <UserRound size={17} />
                <input name="username" required maxLength={50} minLength={registering ? 3 : undefined} pattern={registering ? '[A-Za-z0-9_.\\-]+' : undefined} autoComplete="username" placeholder="Введите логин" />
              </span>
            </label>
            <label className="field">
              <span>Пароль</span>
              <span className="input-shell">
                <LockKeyhole size={17} />
                <input name="password" type={visible ? 'text' : 'password'} required maxLength={128} minLength={registering ? 8 : undefined} autoComplete={registering ? 'new-password' : 'current-password'} placeholder={registering ? 'Минимум 8 символов' : 'Введите пароль'} />
                <button type="button" className="icon-button" aria-label={visible ? 'Скрыть пароль' : 'Показать пароль'} onClick={() => setVisible(!visible)}>{visible ? <EyeOff size={17} /> : <Eye size={17} />}</button>
              </span>
            </label>
            <ErrorBox error={error} />
            <button className="button primary auth-submit" disabled={busy}>
              {busy && <LoaderCircle size={17} className="spinner" />}
              {registering ? 'Зарегистрироваться' : 'Войти'}
            </button>
          </form>
          <div className="auth-switch">
            <span>{registering ? 'Уже есть аккаунт?' : 'Нет аккаунта?'}</span>
            <button type="button" className="text-button" disabled={busy} onClick={() => { setRegistering(!registering); setError(null); setVisible(false); }}>
              {registering ? 'Войти' : 'Создать аккаунт'}
            </button>
          </div>
        </section>
      </div>
    </main>
  );
}
