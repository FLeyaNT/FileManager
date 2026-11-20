import { useCallback, useState } from 'react';
import { Archive, ArchiveRestore, Download, File as FileIcon, FilePlus2, FolderClosed, FolderPlus, LoaderCircle, Pencil, RefreshCw, Trash2, Upload } from 'lucide-react';
import { api, downloadFile } from './api';
import { Dialog, ErrorBox, fileSize, Loading, useResource } from './ui';

const details = {
  directory: { title: 'Новая папка', submit: 'Создать папку', icon: FolderPlus },
  create: { title: 'Новый файл', submit: 'Создать файл', icon: FilePlus2 },
  upload: { title: 'Загрузка файлов', submit: 'Загрузить', icon: Upload },
  rename: { title: 'Переименовать файл', submit: 'Переименовать', icon: Pencil },
  replace: { title: 'Заменить содержимое', submit: 'Заменить', icon: RefreshCw },
  remove: { title: 'Удаление', submit: 'Удалить', icon: Trash2 },
  archive: { title: 'Создать ZIP', submit: 'Создать архив', icon: Archive },
  extract: { title: 'Распаковать ZIP', submit: 'Распаковать', icon: ArchiveRestore },
};

const fileFormats = {
  text: { label: 'Текст', placeholder: 'notes.txt', sample: '' },
  json: { label: 'JSON', placeholder: 'data.json', sample: '{\n  "name": "Документ"\n}' },
  xml: { label: 'XML', placeholder: 'document.xml', sample: '<document>Текст</document>' },
};

function withExtension(name, extension) {
  return name.toLowerCase().endsWith(`.${extension}`) ? name : `${name}.${extension}`;
}

function DirectoryPicker({ value, onChange }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="field">
      <span>Папка назначения</span>
      <div className="destination">
        <FolderClosed size={17} />
        <span>{value.name || 'Мои файлы'}</span>
        <button type="button" className="text-button" aria-expanded={expanded} onClick={() => setExpanded(!expanded)}>{expanded ? 'Свернуть' : 'Изменить'}</button>
      </div>
      {expanded && <PickDirectory current={value.id} choose={(item) => { onChange(item); setExpanded(false); }} />}
    </div>
  );
}

function PickDirectory({ current, choose }) {
  const [id, setId] = useState(current);
  const load = useCallback((signal) => api.directory(id, signal), [id]);
  const { data, error, loading, retry } = useResource(load);

  return (
    <div className="picker">
      <ErrorBox error={error} retry={retry} />
      {loading ? <Loading /> : data && !error && <>
        <div className="picker-current">
          <strong>{data.name || 'Мои файлы'}</strong>
          {data.parent_id !== null && <button className="text-button" type="button" onClick={() => setId(data.parent_id)}>Родительская папка</button>}
        </div>
        <div className="picker-items">
          {data.directories.map((child) => <button type="button" key={child.id} onClick={() => setId(child.id)}><FolderClosed size={16} />{child.name}</button>)}
        </div>
        <button type="button" className="button secondary compact" onClick={() => choose(data)}>Выбрать эту папку</button>
      </>}
    </div>
  );
}

function UploadField({ files, setFiles, multiple }) {
  const [dragging, setDragging] = useState(false);
  function select(incoming) {
    const selected = Array.from(incoming);
    setFiles(multiple ? selected : selected.slice(0, 1));
  }

  return (
    <div className="upload-picker">
      <label
        className={`upload-zone${dragging ? ' dragging' : ''}`}
        onDragOver={(event) => { event.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => { event.preventDefault(); setDragging(false); select(event.dataTransfer.files); }}
      >
        <input type="file" multiple={multiple} onChange={(event) => { select(event.currentTarget.files); event.currentTarget.value = ''; }} />
        <span className="upload-zone-mark"><Upload size={22} /></span>
        <strong>{multiple ? 'Выберите файлы' : 'Выберите файл'}</strong>
        <span>или перетащите сюда</span>
      </label>
      {files.length > 0 && <ul className="picked-files">
        {files.map((file, index) => <li key={`${file.name}-${index}`}><span>{file.name}</span><span>{fileSize(file.size)}</span></li>)}
      </ul>}
    </div>
  );
}

export function ActionDialog({ action, directory, close, complete, changed }) {
  const { kind, item, sources } = action;
  const info = details[kind];
  const Icon = info.icon;
  const [name, setName] = useState(kind === 'rename' ? item.name : '');
  const [format, setFormat] = useState('text');
  const [content, setContent] = useState('');
  const [files, setFiles] = useState([]);
  const [recursive, setRecursive] = useState(false);
  const [destination, setDestination] = useState(directory);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const filename = name;

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      switch (kind) {
        case 'directory':
          await api.createDirectory(directory.id, filename);
          complete('Папка создана.');
          break;
        case 'create':
          await api.createFile(directory.id, format === 'text' ? filename : withExtension(filename, format), content);
          complete('Файл создан.');
          break;
        case 'upload': {
          const failures = [];
          for (const file of files) {
            try {
              await api.upload(directory.id, file);
            } catch (failure) {
              if (failure.status === 401) throw failure;
              failures.push({ file, failure });
            }
          }
          const count = files.length - failures.length;
          if (failures.length) {
            if (count) changed(`Загружено файлов — ${count}.`);
            setFiles(failures.map(({ file }) => file));
            throw new Error(failures.map(({ file, failure }) => `${file.name} — ${failure.message}`).join('\n'));
          }
          complete(`Загружено файлов — ${count}.`);
          break;
        }
        case 'rename':
          await api.rename(item.id, filename);
          complete('Файл переименован.');
          break;
        case 'replace':
          await api.replace(item.id, files[0]);
          complete('Содержимое заменено.');
          break;
        case 'remove':
          if (item.kind === 'folder') await api.removeDirectory(item.id, recursive);
          else await api.removeFile(item.id);
          complete(item.kind === 'folder' ? 'Папка удалена.' : 'Файл удалён.');
          break;
        case 'archive':
          await api.archive(destination.id, withExtension(filename, 'zip'), sources);
          complete('Архив создан.');
          break;
        case 'extract': {
          const result = await api.extract(item.id, destination.id, filename);
          complete('Архив распакован.', result.directory_id);
          break;
        }
        default:
          break;
      }
    } catch (failure) {
      setError(failure);
    } finally {
      setBusy(false);
    }
  }

  const isUpload = kind === 'upload' || kind === 'replace';
  const targetsArchive = kind === 'archive' || kind === 'extract';
  const hasName = !isUpload && kind !== 'remove';
  const description = kind === 'remove'
    ? `Удалить «${item.name}»?`
    : kind === 'replace' || kind === 'extract' ? item.name : null;

  return (
    <Dialog title={info.title} description={description} icon={<Icon size={20} />} busy={busy} close={close} wide={kind === 'create'}>
      <form onSubmit={submit}>
        <fieldset className="dialog-fields" disabled={busy}>
          {kind === 'create' && <label className="field">
            <span>Формат</span>
            <select value={format} onChange={(event) => setFormat(event.target.value)}>
              {Object.entries(fileFormats).map(([value, data]) => <option key={value} value={value}>{data.label}</option>)}
            </select>
          </label>}
          {targetsArchive && <DirectoryPicker value={destination} onChange={setDestination} />}
          {hasName && <label className="field">
            <span>{kind === 'directory' || kind === 'extract' ? 'Имя папки' : kind === 'archive' ? 'Имя архива' : 'Имя файла'}</span>
            <input autoFocus name="name" value={name} onChange={(event) => setName(event.target.value)} required={kind !== 'extract'} maxLength={255} placeholder={kind === 'directory' ? 'Новая папка' : kind === 'extract' ? 'По имени архива' : kind === 'archive' ? 'archive.zip' : fileFormats[format].placeholder} />
          </label>}
          {kind === 'create' && <label className="field">
            <span>Содержимое</span>
            <textarea className="code-input" rows={9} value={content} onChange={(event) => setContent(event.target.value)} spellCheck={false} placeholder={fileFormats[format].sample} />
          </label>}
          {isUpload && <UploadField files={files} setFiles={setFiles} multiple={kind === 'upload'} />}
          {kind === 'remove' && item.kind === 'folder' && <label className="check-label">
            <input type="checkbox" checked={recursive} onChange={(event) => setRecursive(event.target.checked)} />
            Удалить вложенные папки и файлы
          </label>}
        </fieldset>
        <div className="dialog-errors"><ErrorBox error={error} /></div>
        <div className="dialog-footer">
          <button type="button" className="button secondary" onClick={close} disabled={busy}>Отмена</button>
          <button className={`button ${kind === 'remove' ? 'danger' : 'primary'}`} disabled={busy || (isUpload && !files.length)}>
            {busy && <LoaderCircle className="spinner" size={16} />}{info.submit}
          </button>
        </div>
      </form>
    </Dialog>
  );
}

export function FileDialog({ item, close, switchAction, changed }) {
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');
  const [error, setError] = useState(null);
  const [revision, setRevision] = useState(0);

  const load = useCallback(async (signal) => {
    const file = await api.file(item.id, signal);
    if (file.filename.toLowerCase().endsWith('.zip')) return { file, text: null, reason: 'ZIP-архив можно скачать или распаковать.' };
    const blob = await api.content(item.id, signal);
    try {
      const text = new TextDecoder('utf-8', { fatal: true }).decode(await blob.arrayBuffer());
      if (/[\x00-\x08\x0b\x0c\x0e-\x1f]/.test(text)) return { file, text: null, reason: 'Встроенный просмотр доступен для текстовых файлов.' };
      return { file, text, reason: null };
    } catch {
      return { file, text: null, reason: 'Встроенный просмотр доступен для текста в UTF-8.' };
    }
  }, [item.id, revision]);
  const resource = useResource(load);

  async function save(event) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const file = new File([draft], item.name, { type: 'text/plain;charset=utf-8' });
      await api.replace(item.id, file);
      setEditing(false);
      setRevision((n) => n + 1);
      changed('Файл сохранён.');
    } catch (failure) {
      setError(failure);
    } finally {
      setBusy(false);
    }
  }

  async function download() {
    setBusy(true);
    setError(null);
    try {
      await downloadFile({ id: item.id, filename: item.name });
    } catch (failure) {
      setError(failure);
    } finally {
      setBusy(false);
    }
  }

  const content = resource.data;
  const isZip = item.name.toLowerCase().endsWith('.zip');
  return (
    <Dialog title={item.name} description={fileSize(content?.file.size ?? item.size)} icon={<FileIcon size={20} />} busy={busy} close={close} wide>
      <form onSubmit={save}>
        <div className="dialog-fields">
          <ErrorBox error={resource.error} retry={resource.retry} />
          {resource.loading && <Loading />}
          {content && !resource.error && !resource.loading && (
            editing ? <label className="field"><span>Содержимое</span><textarea autoFocus className="code-input editor" rows={13} spellCheck={false} disabled={busy} value={draft} onChange={(event) => setDraft(event.target.value)} /></label>
              : content.text === null ? <p className="preview-placeholder">{content.reason}</p> : <pre className="file-preview">{content.text || 'Пустой файл'}</pre>
          )}
          <ErrorBox error={error} />
        </div>
        <div className="dialog-footer">
          {editing ? <>
            <button type="button" className="button secondary" disabled={busy} onClick={() => { setEditing(false); setError(null); }}>Отмена</button>
            <button className="button primary" disabled={busy}>{busy && <LoaderCircle size={16} className="spinner" />}Сохранить</button>
          </> : <>
            <button type="button" className="button secondary" onClick={download} disabled={busy}><Download size={16} />Скачать</button>
            <button type="button" className="button secondary" onClick={() => switchAction('replace', item)} disabled={busy}>Заменить</button>
            {isZip && <button type="button" className="button primary" onClick={() => switchAction('extract', item)} disabled={busy}><ArchiveRestore size={16} />Распаковать</button>}
            {content?.text != null && !resource.loading && !resource.error && <button type="button" className="button primary" onClick={() => { setDraft(content.text); setError(null); setEditing(true); }}><Pencil size={16} />Редактировать</button>}
          </>}
        </div>
      </form>
    </Dialog>
  );
}
