from urllib.parse import urlparse


def database_kind(database_url):
    scheme = urlparse(database_url).scheme
    if scheme in {'postgres', 'postgresql'}:
        return 'postgres'
    if scheme == 'sqlite':
        return 'sqlite'
    raise ValueError(f'Unsupported database URL scheme: {scheme}')


def placeholder(kind):
    return '%s' if kind == 'postgres' else '?'


def qmarks(kind, count):
    return ','.join(placeholder(kind) for _ in range(count))
