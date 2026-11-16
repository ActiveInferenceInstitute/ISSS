"""Atomic JSON publication and immutable, explicitly selected pipeline generations.

Only manifest-selected, source/content-qualified files are active. Old generation
folders and legacy/unowned files are never removed or discovered by directory scan.
"""

import hashlib
import json
import os
import shutil
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path, PurePosixPath

ARTIFACT_SCHEMA = 'isss-artifacts/v1'


def file_identity(path):
    """Return the identity of a regular, non-symlink file without retaining bytes."""
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError(f'not a regular owned input: {path}')
    digest = hashlib.sha256()
    size = 0
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            size += len(chunk)
            digest.update(chunk)
    return {'sha256': digest.hexdigest(), 'size': size}


def atomic_json(path, value):
    """Replace a JSON file only after complete serialization and same-volume staging."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError(f'refusing JSON output symlink: {path}')
    descriptor, temporary = tempfile.mkstemp(prefix=f'.{path.name}-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
            json.dump(value, handle, indent=2, ensure_ascii=False, allow_nan=False)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class ArtifactStore:
    """One invocation's writer for an atomic selection of immutable document sets."""

    def __init__(self, root, kind, manifest_name='active.json'):
        self.root = Path(root)
        self.kind = kind
        self.manifest_path = self.root / manifest_name
        if self.root.is_symlink() or self.manifest_path.is_symlink():
            raise ValueError('artifact roots and manifests must not be symlinks')
        self.documents = {}
        self.failures = {}
        if self.manifest_path.exists():
            data = json.loads(self.manifest_path.read_text(encoding='utf-8'))
            if (not isinstance(data, dict) or data.get('schema') != ARTIFACT_SCHEMA
                    or data.get('kind') != kind or not isinstance(data.get('documents'), list)
                    or not isinstance(data.get('failures'), dict)):
                raise ValueError(f'invalid {kind} manifest: {self.manifest_path}')
            for record in data['documents']:
                if not isinstance(record, dict) or not isinstance(record.get('document_name'), str):
                    raise ValueError('invalid document record')
                name = record['document_name']
                if name in self.documents:
                    raise ValueError(f'duplicate active document: {name}')
                self.documents[name] = record
            self.failures = data['failures']

    def resolve(self, record, relative):
        """Resolve only a declared regular file inside this record's generation."""
        generation = record.get('generation')
        if (not isinstance(generation, str) or len(generation) != 32
                or any(character not in '0123456789abcdef' for character in generation)):
            raise ValueError('invalid generation identity')
        if not isinstance(relative, str):
            raise ValueError('invalid artifact path')
        parts = PurePosixPath(relative).parts
        if (PurePosixPath(relative).is_absolute() or '..' in parts
                or len(parts) < 3 or parts[:2] != ('.generations', generation)):
            raise ValueError(f'artifact outside its generation: {relative}')
        path = self.root
        for part in parts:
            path = path / part
            if path.is_symlink():
                raise ValueError(f'artifact symlink: {path}')
        if relative not in record.get('files', {}):
            raise ValueError(f'undeclared artifact: {relative}')
        return path

    def active_documents(self):
        """Return intact sets still bound to current source and producer selections."""
        active = []
        upstream_sets = {}
        for name, record in sorted(self.documents.items()):
            try:
                source = record['source']
                if file_identity(source['path']) != {
                    'sha256': source['sha256'], 'size': source['size']
                }:
                    raise ValueError('source content changed')
                files = record['files']
                if not isinstance(files, dict) or (
                    not files and not (self.kind == 'figures' and record.get('figures') == [])
                ):
                    raise ValueError('empty or malformed artifact inventory')
                for relative, identity in files.items():
                    if file_identity(self.resolve(record, relative)) != identity:
                        raise ValueError(f'artifact content changed: {relative}')
                if self.kind == 'conversion':
                    self.resolve(record, record['text_file'])
                    for relative in record['page_files']:
                        self.resolve(record, relative)
                elif self.kind == 'figures':
                    upstream = record['upstream']
                    manifest = upstream['manifest']
                    if manifest not in upstream_sets:
                        path = Path(manifest)
                        producer = ArtifactStore(path.parent, 'conversion', path.name)
                        upstream_sets[manifest] = {
                            item['document_name']: item['generation']
                            for item in producer.active_documents()
                        }
                    if upstream_sets[manifest].get(name) != upstream['generation']:
                        raise ValueError('conversion generation is no longer active')
                    for figure in record['figures']:
                        self.resolve(record, figure['figure'])
                active.append(record)
            except (OSError, ValueError, KeyError, TypeError) as error:
                # Never fall back to scanning legacy/unqualified output files.
                self.failures[name] = str(error)
        return active

    def select(self, names):
        """Restrict the next active set without deleting retired generations."""
        names = set(names)
        self.documents = {name: value for name, value in self.documents.items() if name in names}
        self.failures = {name: value for name, value in self.failures.items() if name in names}

    def fail(self, name, error):
        self.documents.pop(name, None)
        self.failures[name] = str(error)

    @contextmanager
    def stage(self):
        generations = self.root / '.generations'
        if generations.is_symlink():
            raise ValueError('generation directory must not be a symlink')
        generations.mkdir(parents=True, exist_ok=True)
        generation = uuid.uuid4().hex
        path = Path(tempfile.mkdtemp(prefix='.staging-', dir=generations))
        try:
            yield generation, path
        finally:
            # Only this invocation's private, unpublished staging directory.
            if path.exists():
                shutil.rmtree(path)

    def publish(self, staged, record):
        """Seal one complete set; activation remains the explicit commit boundary."""
        generation = record['generation']
        prefix = f'.generations/{generation}/'
        record = dict(record)
        record['files'] = {
            prefix + path.relative_to(staged).as_posix(): file_identity(path)
            for path in sorted(staged.rglob('*')) if path.is_file()
        }
        atomic_json(staged / 'record.json', record)
        destination = self.root / '.generations' / generation
        if destination.exists() or destination.is_symlink():
            raise ValueError('generation already exists')
        os.rename(staged, destination)
        self.documents[record['document_name']] = record
        self.failures.pop(record['document_name'], None)
        return record

    def commit(self):
        """Atomically select complete sets, leaving all previous bytes historical."""
        documents = [record for _, record in sorted(self.documents.items())]
        data = {
            'schema': ARTIFACT_SCHEMA,
            'kind': self.kind,
            'document_count': len(documents),
            'documents': documents,
            'failures': dict(sorted(self.failures.items())),
        }
        if self.kind == 'figures':
            data['figure_count'] = sum(len(record['figures']) for record in documents)
        atomic_json(self.manifest_path, data)
        return data
