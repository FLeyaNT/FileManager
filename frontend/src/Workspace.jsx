import { useCallback, useEffect, useState } from 'react';
import {
  Archive, ArchiveRestore, ArrowDownWideNarrow, ArrowUpWideNarrow, CheckCircle2, ChevronDown,
  ChevronRight, Clock3, Download, File, FileCode2, Files, FileText, FolderClosed, FolderOpen,
  HardDrive, Home, Image, Layers3, LogOut, MoreHorizontal, Pencil, Plus, RefreshCw, Search, Trash2, Upload, X,
} from 'lucide-react';
import { api, downloadFile, readDirectory } from './api';
import { ActionDialog, FileDialog } from './Dialogs';
import { Brand, Dropdown, ErrorBox, extensionOf, fileSize, FolderLink, Loading, megabytes, number, useResource } from './ui';

const views = [
  { page: 'files', label: 'Мои файлы', icon: FolderClosed },
  { page: 'all', label: 'Все файлы', icon: Files },
  { page: 'history', label: 'Журнал', icon: Clock3 },
];
const collator = new Intl.Collator('ru', { numeric: true, sensitivity: 'base' });
const plurals = new Intl.PluralRules('ru-RU');
const date = new Intl.DateTimeFormat('ru-RU', { dateStyle: 'medium', timeStyle: 'short' });

function readRoute() {
  const hash = window.location.hash;
  if (hash === '#history' || hash === '#all') return { page: hash.slice(1), id: null };
  const id = Number(hash.match(/^#folder\/([1-9][0-9]*)$/)?.[1]);
  return { page: 'files', id: id > 0 && id <= 2147483647 ? id : null };
}

function useRoute() {
  const [route, setRoute] = useState(readRoute);
  useEffect(() => {
    function sync() { setRoute(readRoute()); }
    window.addEventListener('hashchange', sync);
    return () => window.removeEventListener('hashchange', sync);
  }, []);
  return route;
}

function countLabel(count, forms) {
  return `${number.format(count)} ${forms[plurals.select(count)] || forms.many}`;
}

function QuotaMeter({ label, used, max, remaining, format, color, icon }) {
  const percent = max ? Math.round(used * 100 / max) : 0;
  return (
    <div className={`quota-meter ${color}`}>
      <div className="meter-title"><span>{icon}{label}</span><strong>{number.format(percent)}%</strong></div>
      <progress aria-label={label} value={Math.min(used, max)} max={max} />
      <div className="meter-numbers"><strong>{format(used)}</strong><span>из {format(max)}</span></div>
      <div className="meter-free">Свободно {format(remaining)}</div>
    </div>
  );
}

function Sidebar({ user, page, quota, logout, leaving }) {
  const counts = quota.data;
  return (
    <aside className="sidebar">
      <div className="sidebar-brand"><Brand /></div>
      <nav className="sidebar-nav" aria-label="Разделы">
        {views.map(({ page: target, label, icon: Icon }) => (
          <a key={target} href={`#${target}`} className={`nav-item${target === page ? ' current' : ''}`} aria-current={target === page ? 'page' : undefined}>
            <Icon size={19} strokeWidth={1.8} /><span>{label}</span>
          </a>
        ))}
      </nav>
      <section className="quota" aria-label="Квота хранилища">
        <h2>Хранилище</h2>
        {quota.loading && !counts && <Loading />}
        {counts && <div className="quota-meters">
          <QuotaMeter label="Место" icon={<HardDrive size={16} />} used={counts.used_bytes} max={counts.max_bytes} remaining={counts.remaining_bytes} format={megabytes} color="violet" />
          <QuotaMeter label="Элементы" icon={<Layers3 size={16} />} used={counts.used_entries} max={counts.max_entries} remaining={counts.remaining_entries} format={(value) => number.format(value)} color="teal" />
        </div>}
        <ErrorBox error={quota.error} retry={quota.retry} />
      </section>
      <div className="account">
        <span className="avatar" aria-hidden="true">{user.username.slice(0, 2).toUpperCase()}</span>
        <span className="account-name" title={user.username}>{user.username}</span>
        <button type="button" className="icon-button" aria-label="Выйти" title="Выйти" onClick={logout} disabled={leaving}><LogOut size={17} /></button>
      </div>
    </aside>
  );
}

function Breadcrumbs({ trail = [], page = 'files' }) {
  if (page !== 'files') {
    const entry = views.find((view) => view.page === page);
    return <span className="breadcrumb-label"><entry.icon size={17} />{entry.label}</span>;
  }
  return (
    <nav className="breadcrumbs" aria-label="Текущая папка">
      <FolderLink className="breadcrumb-root"><Home size={16} /><span>Мои файлы</span></FolderLink>
      {trail.slice(1).map((directory, index) => (
        <span key={directory.id} className="breadcrumb-step">
          <ChevronRight size={15} aria-hidden="true" />
          {index === trail.length - 2
            ? <span title={directory.name} aria-current="location">{directory.name}</span>
            : <FolderLink id={directory.id}>{directory.name}</FolderLink>}
        </span>
      ))}
    </nav>
  );
}

function Topbar({ page, trail, refresh, busy }) {
  const parent = trail?.at(-2);
  return (
    <header className="topbar">
      <Breadcrumbs page={page} trail={trail} />
      <div className="topbar-actions">
        {parent && <FolderLink className="parent-link" id={parent.parent_id === null ? null : parent.id}>Родительская папка</FolderLink>}
        <button type="button" className="icon-button refresh" aria-label="Обновить" title="Обновить" onClick={refresh} disabled={busy}><RefreshCw size={17} className={busy ? 'spinner' : undefined} /></button>
      </div>
    </header>
  );
}

function entryIcon(item) {
  if (item.kind === 'folder') return { Icon: FolderClosed, color: 'folder', label: 'Папка' };
  const ext = extensionOf(item.name);
  if (ext === 'zip') return { Icon: Archive, color: 'archive', label: 'ZIP' };
  if (ext === 'json' || ext === 'xml') return { Icon: FileCode2, color: 'code', label: ext.toUpperCase() };
  if (['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg'].includes(ext)) return { Icon: Image, color: 'image', label: ext.toUpperCase() };
  if (['txt', 'md', 'csv', 'log'].includes(ext)) return { Icon: FileText, color: 'text', label: ext.toUpperCase() };
  return { Icon: File, color: 'other', label: ext.toUpperCase() || 'Файл' };
}

function ItemMenu({ item, openAction, download, archive }) {
  const folder = item.kind === 'folder';
  const zip = extensionOf(item.name) === 'zip';
  return (
    <Dropdown label={`Действия для ${item.name}`} className="icon-button row-menu" icon={<MoreHorizontal size={19} />}>
      {(close) => <>
        {folder ? <FolderLink id={item.id} onClick={close}><FolderOpen size={16} />Открыть</FolderLink> : <>
          <button type="button" onClick={() => { close(); openAction('open', item); }}><FileText size={16} />Открыть</button>
          <button type="button" onClick={() => { close(); download(item); }}><Download size={16} />Скачать</button>
          <FolderLink id={item.directoryId} onClick={close}><FolderOpen size={16} />Перейти в папку</FolderLink>
          <button type="button" onClick={() => { close(); openAction('rename', item); }}><Pencil size={16} />Переименовать</button>
          <button type="button" onClick={() => { close(); openAction('replace', item); }}><RefreshCw size={16} />Заменить содержимое</button>
        </>}
        <button type="button" onClick={() => { close(); archive([item]); }}><Archive size={16} />Создать ZIP</button>
        {!folder && zip && <button type="button" onClick={() => { close(); openAction('extract', item); }}><ArchiveRestore size={16} />Распаковать</button>}
        <button type="button" className="menu-danger" onClick={() => { close(); openAction('remove', item); }}><Trash2 size={16} />Удалить</button>
      </>}
    </Dropdown>
  );
}

function FileTable({ items, selected, toggle, toggleAll, ascending, flipSort, openAction, download, archive }) {
  return (
    <table className="file-table">
      <thead><tr>
        <th className="selection-cell"><input type="checkbox" aria-label="Выбрать все видимые элементы" checked={items.every((item) => selected.has(item.key))} onChange={toggleAll} /></th>
        <th aria-sort={ascending ? 'ascending' : 'descending'}><button type="button" className="sort" onClick={flipSort}>Имя {ascending ? <ArrowDownWideNarrow size={14} /> : <ArrowUpWideNarrow size={14} />}</button></th>
        <th className="type-cell">Тип</th><th className="size-cell">Размер</th><th className="actions-cell"><span className="sr-only">Действия</span></th>
      </tr></thead>
      <tbody>{items.map((item) => {
        const { Icon, color, label } = entryIcon(item);
        const folder = item.kind === 'folder';
        return (
          <tr key={item.key} className={selected.has(item.key) ? 'selected' : undefined}>
            <td className="selection-cell"><input type="checkbox" aria-label={`Выбрать ${item.name}`} checked={selected.has(item.key)} onChange={() => toggle(item.key)} /></td>
            <td className="filename-cell">
              {folder ? <FolderLink className="entry-name" id={item.id}><span className={`entry-icon ${color}`}><Icon size={18} /></span><span title={item.name}>{item.name}</span></FolderLink>
                : <button type="button" className="entry-name" onClick={() => openAction('open', item)}><span className={`entry-icon ${color}`}><Icon size={17} /></span><span title={item.name}>{item.name}</span></button>}
            </td>
            <td className="type-cell"><span className={`type-label ${color}`}>{label}</span></td>
            <td className="size-cell">{folder ? '—' : fileSize(item.size)}</td>
            <td className="actions-cell"><div className="row-actions">
              {!folder && <button type="button" className="icon-button row-download" aria-label={`Скачать ${item.name}`} title="Скачать" onClick={() => download(item)}><Download size={16} /></button>}
              <ItemMenu item={item} openAction={openAction} download={download} archive={archive} />
            </div></td>
          </tr>
        );
      })}</tbody>
    </table>
  );
}

function EmptyFiles({ filtering, action }) {
  return (
    <div className="empty-files">
      <div className="empty-mark"><FolderOpen size={41} strokeWidth={1.4} /></div>
      <h2>{filtering ? 'Ничего не найдено' : 'Пока пусто'}</h2>
      <p>{filtering ? 'Попробуйте изменить поисковый запрос.' : 'Загрузите первый файл или создайте папку.'}</p>
      {!filtering && <button className="button secondary" type="button" onClick={() => action('upload')}><Upload size={16} />Загрузить файлы</button>}
    </div>
  );
}

function FilesView({ route, revision, refresh, notify, changed }) {
  const [search, setSearch] = useState('');
  const [ascending, setAscending] = useState(true);
  const [selection, setSelection] = useState(new Set());
  const [action, setAction] = useState(null);
  const all = route.page === 'all';

  const load = useCallback(async (signal) => {
    if (!all) return readDirectory(route.id, signal);
    const [directory, files] = await Promise.all([api.directory(null, signal), api.files(signal)]);
    return { directory, trail: [], allFiles: files };
  }, [all, route.id, revision]);
  const { data, error, loading, retry } = useResource(load);

  const directory = data?.directory;
  const prefix = (data?.trail ?? []).slice(1).map((entry) => entry.name).join('/');
  const folders = all ? [] : directory?.directories ?? [];
  const files = all ? data?.allFiles ?? [] : directory?.files ?? [];
  const items = [
    ...folders.map((folder) => ({ key: `folder-${folder.id}`, kind: 'folder', id: folder.id, name: folder.name })),
    ...files.map((file) => ({ key: `file-${file.id}`, kind: 'file', id: file.id, directoryId: file.directory_id, name: file.filename, size: file.size })),
  ];
  const needle = search.trim().toLocaleLowerCase('ru-RU');
  const shown = items.filter((item) => item.name.toLocaleLowerCase('ru-RU').includes(needle)).sort((left, right) => {
    if (left.kind !== right.kind) return left.kind === 'folder' ? -1 : 1;
    return (ascending ? 1 : -1) * collator.compare(left.name, right.name);
  });
  const selected = items.filter((item) => selection.has(item.key));

  function launch(kind, item) { setAction({ kind, item }); }
  function archive(input) {
    const sources = input.map((item) => item.kind === 'folder' ? [prefix, item.name].filter(Boolean).join('/') : item.id);
    if (sources.length > 100) {
      notify('В один архив можно добавить до 100 выбранных элементов.', true);
      return;
    }
    setAction({ kind: 'archive', sources });
  }
  async function download(item) {
    try { await downloadFile({ id: item.id, filename: item.name }); }
    catch (failure) { notify(failure.message, true); }
  }
  function toggle(key) {
    setSelection((previous) => {
      const next = new Set(previous);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  }
  function toggleAll() {
    setSelection((previous) => {
      const next = new Set(previous);
      const remove = shown.every((item) => previous.has(item.key));
      for (const item of shown) {
        if (remove) next.delete(item.key); else next.add(item.key);
      }
      return next;
    });
  }
  function complete(message, nextDirectory) {
    setAction(null);
    setSelection(new Set());
    changed(message);
    if (nextDirectory != null) window.location.hash = `#folder/${nextDirectory}`;
  }

  const title = all ? 'Все файлы' : directory?.name || 'Мои файлы';
  const fileCount = countLabel(files.length, { one: 'файл', few: 'файла', many: 'файлов' });
  const folderCount = countLabel(folders.length, { one: 'папка', few: 'папки', many: 'папок' });

  return (
    <main className="workspace">
      <Topbar page={route.page} trail={data?.trail} refresh={refresh} busy={loading} />
      <div className="canvas">
        <div className="page-heading">
          <div className="page-identity"><div className="page-icon">{all ? <Files size={26} /> : <FolderOpen size={27} />}</div><div>
            <h1>{title}</h1>
            {directory && <p>{all ? fileCount : `${folderCount} · ${fileCount}`}</p>}
          </div></div>
          {directory && !all && <div className="page-actions">
            <Dropdown label="Создать" icon={<><Plus size={17} />Создать <ChevronDown size={15} className="button-chevron" /></>}>
              {(close) => <>
                <button type="button" onClick={() => { close(); launch('directory'); }}><FolderClosed size={16} />Новая папка</button>
                <button type="button" onClick={() => { close(); launch('create'); }}><FileText size={16} />Новый файл</button>
              </>}
            </Dropdown>
            <button className="button primary" type="button" onClick={() => launch('upload')}><Upload size={17} />Загрузить</button>
          </div>}
        </div>

        <ErrorBox error={error} retry={retry} />
        {!directory && !error && <Loading />}
        {directory && <section className="file-panel" aria-label="Список файлов и папок" aria-busy={loading}>
          <div className="panel-tools">
            <label className="search"><Search size={17} /><input aria-label={all ? 'Поиск по файлам' : 'Поиск в папке'} placeholder={all ? 'Поиск по файлам' : 'Поиск в папке'} type="search" value={search} onChange={(event) => setSearch(event.target.value)} /></label>
            {selected.length > 0 ? <div className="selection-tools">
              <span>Выбрано {number.format(selected.length)}</span>
              <button className="button secondary compact" type="button" onClick={() => archive(selected)}><Archive size={16} />В ZIP</button>
              <button className="icon-button" type="button" aria-label="Снять выбор" title="Снять выбор" onClick={() => setSelection(new Set())}><X size={16} /></button>
            </div> : <span className="listing-count">{countLabel(shown.length, { one: 'элемент', few: 'элемента', many: 'элементов' })}</span>}
          </div>
          {shown.length ? <FileTable items={shown} selected={selection} toggle={toggle} toggleAll={toggleAll} ascending={ascending} flipSort={() => setAscending(!ascending)} openAction={launch} download={download} archive={archive} />
            : <EmptyFiles filtering={Boolean(needle)} action={launch} />}
        </section>}
      </div>
      {action && directory && (action.kind === 'open'
        ? <FileDialog key={`open-${action.item.id}`} item={action.item} close={() => setAction(null)} switchAction={launch} changed={changed} />
        : <ActionDialog key={`${action.kind}-${action.item?.id ?? ''}`} action={action} directory={directory} close={() => setAction(null)} complete={complete} changed={changed} />)}
    </main>
  );
}

const operationNames = {
  create: 'Создание', read: 'Чтение', modify: 'Изменение', delete: 'Удаление', archive: 'Архивация', extract: 'Распаковка',
};

function HistoryView({ revision, refresh }) {
  const [operation, setOperation] = useState('');
  const load = useCallback(async (signal) => {
    const [history, files] = await Promise.all([api.history(signal), api.files(signal)]);
    return { history, files: new Map(files.map((file) => [file.id, file.filename])) };
  }, [revision]);
  const { data, error, loading, retry } = useResource(load);
  const events = data?.history.filter((item) => !operation || item.operation_type === operation) ?? [];

  return (
    <main className="workspace">
      <Topbar page="history" refresh={refresh} busy={loading} />
      <div className="canvas">
        <div className="page-heading"><div className="page-identity"><div className="page-icon"><Clock3 size={26} /></div><div><h1>Журнал операций</h1><p>Последние операции с файлами</p></div></div></div>
        <ErrorBox error={error} retry={retry} />
        {!data && !error && <Loading />}
        {data && <section className="file-panel" aria-label="Журнал операций">
          <div className="panel-tools"><span className="listing-count">{countLabel(events.length, { one: 'запись', few: 'записи', many: 'записей' })}</span><select aria-label="Тип операции" value={operation} onChange={(event) => setOperation(event.target.value)}>
            <option value="">Все операции</option>{Object.entries(operationNames).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
          </select></div>
          {events.length > 0 ? <table className="history-table"><thead><tr><th>Операция</th><th>Файл</th><th>Время</th></tr></thead><tbody>
            {events.map((row) => <tr key={row.id}>
              <td><span className={`operation ${row.operation_type}`}>{operationNames[row.operation_type] || row.operation_type}</span></td>
              <td>{data.files.get(row.file_id) || (row.file_id ? `Файл #${row.file_id}` : '—')}</td>
              <td><time dateTime={row.timestamp}>{date.format(new Date(row.timestamp))}</time></td>
            </tr>)}
          </tbody></table> : <div className="empty-files"><div className="empty-mark"><Clock3 size={39} strokeWidth={1.4} /></div><h2>Записей пока нет</h2></div>}
        </section>}
      </div>
    </main>
  );
}

export function Workspace({ user, onLogout }) {
  const route = useRoute();
  const [revision, setRevision] = useState(0);
  const [leaving, setLeaving] = useState(false);
  const [notification, setNotification] = useState(null);
  const loadQuota = useCallback((signal) => api.usage(signal), [revision]);
  const quota = useResource(loadQuota);

  useEffect(() => {
    if (!notification) return;
    const timer = window.setTimeout(() => setNotification(null), 5000);
    return () => window.clearTimeout(timer);
  }, [notification]);

  function refresh() { setRevision((value) => value + 1); }
  function notify(message, error = false) { setNotification({ message, error }); }
  function changed(message) { refresh(); notify(message); }

  async function logout() {
    setLeaving(true);
    try { await api.logout(); onLogout(); }
    catch (error) { notify(error.message, true); setLeaving(false); }
  }

  return (
    <div className="shell">
      <Sidebar user={user} page={route.page} logout={logout} leaving={leaving} quota={quota} />
      {route.page === 'history'
        ? <HistoryView revision={revision} refresh={refresh} />
        : <FilesView key={`${route.page}-${route.id}`} route={route} revision={revision} refresh={refresh} notify={notify} changed={changed} />}
      {notification && <div className={`toast${notification.error ? ' failed' : ''}`} role={notification.error ? 'alert' : 'status'}>
        {!notification.error && <CheckCircle2 size={19} />}<span>{notification.message}</span>
        <button className="icon-button" type="button" onClick={() => setNotification(null)} aria-label="Закрыть уведомление"><X size={16} /></button>
      </div>}
    </div>
  );
}
