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


def to_driver_sql(sql, kind):
    if kind != 'postgres':
        return sql
    converted = []
    in_single_quote = False
    index = 0
    while index < len(sql):
        char = sql[index]
        if char == "'":
            converted.append(char)
            if in_single_quote and index + 1 < len(sql) and sql[index + 1] == "'":
                converted.append(sql[index + 1])
                index += 2
                continue
            in_single_quote = not in_single_quote
            index += 1
            continue
        if char == '?' and not in_single_quote:
            converted.append('%s')
        else:
            converted.append(char)
        index += 1
    return ''.join(converted)


def insert_returning_id_sql(sql, kind):
    converted = to_driver_sql(sql, kind)
    if kind != 'postgres':
        return converted
    if converted.rstrip().upper().endswith('RETURNING ID'):
        return converted
    return converted.rstrip() + ' RETURNING id'


def last_insert_id(cursor, kind):
    if kind == 'postgres':
        row = cursor.fetchone()
        return row['id'] if isinstance(row, dict) else row[0]
    return cursor.lastrowid


def insert_ignore_sql(table, columns, conflict_columns, kind):
    column_sql = ', '.join(columns)
    values_sql = ', '.join(placeholder(kind) for _ in columns)
    if kind == 'postgres':
        conflict_sql = ', '.join(conflict_columns)
        return f'INSERT INTO {table} ({column_sql}) VALUES ({values_sql}) ON CONFLICT ({conflict_sql}) DO NOTHING'
    return f'INSERT OR IGNORE INTO {table} ({column_sql}) VALUES ({values_sql})'


def upsert_setting_sql(kind):
    if kind == 'postgres':
        return (
            'INSERT INTO app_settings (setting_key, setting_value, updated_at) VALUES (%s, %s, %s) '
            'ON CONFLICT (setting_key) DO UPDATE SET setting_value = EXCLUDED.setting_value, updated_at = EXCLUDED.updated_at'
        )
    return 'INSERT OR REPLACE INTO app_settings (setting_key, setting_value, updated_at) VALUES (?, ?, ?)'
