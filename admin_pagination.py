from __future__ import annotations


def parse_page(args) -> int:
    try:
        value = int(args.get('page', 1))
    except (TypeError, ValueError):
        value = 1
    return value if value > 0 else 1


def parse_page_size(args, default: int = 20, maximum: int = 100) -> int:
    try:
        value = int(args.get('page_size', default))
    except (TypeError, ValueError):
        value = default
    if value <= 0:
        value = default
    return min(value, maximum)


def paginate_items(items, page: int, page_size: int) -> dict:
    total = len(items)
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = min(page, total_pages)
    start = (page - 1) * page_size
    end = start + page_size
    return {
        'items': items[start:end],
        'total': total,
        'page': page,
        'page_size': page_size,
        'total_pages': total_pages,
    }


def paginate_rows(db, base_sql, count_sql, params, page: int, page_size: int, serializer=dict) -> dict:
    total = db.execute(count_sql, params).fetchone()['c']
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = min(page, total_pages)
    offset = (page - 1) * page_size
    rows = db.execute(f'{base_sql} LIMIT ? OFFSET ?', [*params, page_size, offset]).fetchall()
    return {
        'items': [serializer(row) for row in rows],
        'total': total,
        'page': page,
        'page_size': page_size,
        'total_pages': total_pages,
    }
