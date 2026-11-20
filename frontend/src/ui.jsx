import { useEffect, useId, useRef, useState } from 'react';
import { AlertCircle, FolderClosed, LoaderCircle, X } from 'lucide-react';

export const number = new Intl.NumberFormat('ru-RU');
const decimal = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2 });

export function megabytes(bytes) {
  const value = bytes / 1024 ** 2;
  return value > 0 && value < 0.01 ? 'менее 0,01 МБ' : `${decimal.format(value)} МБ`;
}

export function fileSize(bytes) {
  if (bytes < 1024) return `${number.format(bytes)} Б`;
  if (bytes < 1024 ** 2) return `${decimal.format(bytes / 1024)} КБ`;
  return megabytes(bytes);
}

export function extensionOf(filename) {
  const dot = filename.lastIndexOf('.');
  return dot < 0 ? '' : filename.slice(dot + 1).toLowerCase();
}

export function useResource(load) {
  const [state, setState] = useState({ data: null, error: null, loading: true });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setState((previous) => ({ ...previous, loading: true, error: null }));
    load(controller.signal).then(
      (data) => {
        if (!controller.signal.aborted) setState({ data, loading: false, error: null });
      },
      (error) => {
        if (!controller.signal.aborted) setState((previous) => ({ ...previous, loading: false, error }));
      },
    );
    return () => controller.abort();
  }, [load, attempt]);

  return { ...state, retry: () => setAttempt((value) => value + 1) };
}

export function Brand() {
  return (
    <div className="brand">
      <span className="brand-mark"><FolderClosed size={22} strokeWidth={2.1} /></span>
      <span>File<span className="brand-accent">Manager</span></span>
    </div>
  );
}

export function Loading({ children = 'Загрузка…' }) {
  return <div className="loading" role="status"><LoaderCircle className="spinner" size={18} />{children}</div>;
}

export function ErrorBox({ error, retry }) {
  if (!error) return null;
  return (
    <div className="error-box" role="alert">
      <AlertCircle size={17} />
      <span>{error.message || error}</span>
      {retry && <button type="button" className="button subtle compact" onClick={retry}>Повторить</button>}
    </div>
  );
}

export function Dropdown({ label, icon, className = 'button secondary', children }) {
  const [open, setOpen] = useState(false);
  const root = useRef(null);
  const trigger = useRef(null);

  useEffect(() => {
    if (!open) return;
    function outside(event) {
      if (!root.current?.contains(event.target)) setOpen(false);
    }
    function escape(event) {
      if (event.key === 'Escape') {
        setOpen(false);
        trigger.current?.focus();
      }
    }
    document.addEventListener('pointerdown', outside);
    document.addEventListener('keydown', escape);
    return () => {
      document.removeEventListener('pointerdown', outside);
      document.removeEventListener('keydown', escape);
    };
  }, [open]);

  return (
    <div className="dropdown" ref={root}>
      <button type="button" className={className} ref={trigger} aria-label={label} aria-expanded={open} onClick={() => setOpen(!open)}>
        {icon}
      </button>
      {open && <div className="dropdown-panel">{children(() => setOpen(false))}</div>}
    </div>
  );
}

export function Dialog({ title, description, icon, busy, close, children, wide }) {
  const ref = useRef(null);
  const titleId = useId();

  useEffect(() => {
    const dialog = ref.current;
    dialog.showModal();
    return () => dialog.close();
  }, []);

  return (
    <dialog
      ref={ref}
      className={`dialog${wide ? ' wide' : ''}`}
      aria-labelledby={titleId}
      onCancel={(event) => { event.preventDefault(); if (!busy) close(); }}
      onClick={(event) => { if (event.target === event.currentTarget && !busy) close(); }}
    >
      <div className="dialog-inner">
        <header className="dialog-header">
          {icon && <span className="dialog-mark">{icon}</span>}
          <div>
            <h2 id={titleId}>{title}</h2>
            {description && <p>{description}</p>}
          </div>
          <button type="button" className="icon-button dialog-close" aria-label="Закрыть" disabled={busy} onClick={close}><X size={19} /></button>
        </header>
        {children}
      </div>
    </dialog>
  );
}

export function FolderLink({ id, className, onClick, children }) {
  return <a href={id == null ? '#files' : `#folder/${id}`} className={className} onClick={onClick}>{children}</a>;
}
