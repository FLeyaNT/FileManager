import { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { api } from './api';
import { Auth } from './Auth';
import { Workspace } from './Workspace';
import { Brand, ErrorBox, Loading } from './ui';
import './styles.css';

function App() {
  const [user, setUser] = useState(null);
  const [checking, setChecking] = useState(true);
  const [expired, setExpired] = useState(false);
  const [error, setError] = useState(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setChecking(true);
    api.me(controller.signal).then(
      (session) => { if (!controller.signal.aborted) { setUser(session); setError(null); } },
      (failure) => { if (!controller.signal.aborted && ![401, 404].includes(failure.status)) setError(failure); },
    ).finally(() => { if (!controller.signal.aborted) setChecking(false); });
    return () => controller.abort();
  }, [attempt]);

  useEffect(() => {
    function sessionExpired() { setExpired(true); setUser(null); }
    window.addEventListener('filemanager:session-expired', sessionExpired);
    return () => window.removeEventListener('filemanager:session-expired', sessionExpired);
  }, []);

  if (checking || error) {
    return <main className="boot"><Brand />{checking ? <Loading /> : <ErrorBox error={error} retry={() => setAttempt((n) => n + 1)} />}</main>;
  }

  if (!user) return <Auth expired={expired} onSession={(session) => { setExpired(false); setUser(session); }} />;

  return <Workspace user={user} onLogout={() => { setExpired(false); setUser(null); window.location.hash = '#files'; }} />;
}

createRoot(document.getElementById('root')).render(<App />);
