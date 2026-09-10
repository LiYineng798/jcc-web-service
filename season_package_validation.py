"""Validate the data shapes consumed by the existing reference/simulator renderers."""

from season_package_format import require


def strings(value, label):
    require(
        isinstance(value, list) and all(isinstance(v, str) for v in value),
        f'{label} 必须是文本数组',
    )


def common(row):
    for key in ('description', 'category', 'category_label'):
        require(row.get(key) is None or isinstance(row[key], str), f'{key} 必须是文本')
    for key in ('aliases', 'tags', 'appearance_stages'):
        if key in row:
            strings(row[key], key)
    for key in ('extensions', 'source_ids'):
        require(row.get(key) is None or isinstance(row[key], dict), f'{key} 必须是对象')


def skill(row):
    require(isinstance(row, dict), '技能必须是对象')
    common(row)
    require(row.get('name') is None or isinstance(row['name'], str), '技能名称必须是文本')
    require(isinstance(row.get('variables', []), list), '技能变量必须是数组')
    for variable in row.get('variables', []):
        require(
            isinstance(variable, dict)
            and isinstance(variable.get('label', ''), str)
            and isinstance(variable.get('values', {}), dict),
            '技能变量无效',
        )


def validate_core(rows):
    for name, group in rows.items():
        for row in group:
            common(row)
            img = (row.get('images') or {}).get('icon') if name == 'champions' else row.get('image')
            require(
                isinstance(img, dict)
                and (img.get('local_path') or img.get('optimized_local_path')),
                f'{name}/{row["id"]} 缺少本地图标',
            )
    for row in rows['champions']:
        availability = row.get('availability') or {}
        require(isinstance(availability, dict), '弈子获取条件必须是对象')
        require(
            availability.get('description') is None or isinstance(availability['description'], str),
            '弈子获取条件必须是文本',
        )
        require(isinstance(row.get('images', {}), dict), '弈子 images 必须是对象')
        for value in row.get('skills', []):
            skill(value)
        for level, stats in row.get('stats_by_star', {}).items():
            require(level in ('1', '2', '3', '4') and isinstance(stats, dict), '星级属性无效')
            require(
                all(v is None or type(v) in (int, float) for v in stats.values()),
                '弈子属性必须是数字',
            )
    for row in rows['traits']:
        points = row.get('breakpoints') or []
        require(isinstance(points, list), '羁绊档位必须是数组')
        for point in points:
            require(isinstance(point, dict), '羁绊档位无效')
            # Composite traits can expose a zero threshold; activation is derived from their source traits.
            require(
                type(point.get('min_units')) is int and 0 <= point['min_units'] <= 100,
                '羁绊人数无效',
            )
            require(
                point.get('effect') is None or isinstance(point['effect'], str),
                '羁绊效果必须是文本',
            )
    for row in rows['items']:
        require(isinstance(row.get('effects', []), list), '装备效果必须是数组')
        require(all(isinstance(e, (str, dict)) for e in row.get('effects', [])), '装备效果无效')
        recipe = row.get('recipe') or {}
        strings(recipe.get('component_ids', []), '装备配方')
        granted = (row.get('extensions') or {}).get('trait_id') or (
            row.get('extensions') or {}
        ).get('fetter_id')
        require(
            not granted or str(granted) in {r['id'] for r in rows['traits']},
            '转职装备羁绊引用不存在',
        )
    for row in rows['board_units']:
        require(row.get('can_equip') in (True, False, None), '棋盘对象装备开关无效')
        if row.get('skill'):
            skill(row['skill'])
        require(isinstance(row.get('placement_rules', []), list), '棋盘对象规则必须是数组')
        for rule in row.get('placement_rules', []):
            require(
                set(rule) <= {'trait_id', 'champion_id', 'min_units', 'max_units', 'max_count'},
                '尚不支持此棋盘对象规则，请升级网站能力',
            )
            require(
                bool(rule.get('trait_id')) != bool(rule.get('champion_id')),
                '棋盘对象规则需指定一种激活来源',
            )
            for key in ('min_units', 'max_count'):
                require(type(rule.get(key)) is int and 0 < rule[key] <= 28, '棋盘对象数量规则无效')
            require(
                rule.get('max_units') is None
                or type(rule['max_units']) is int
                and rule['max_units'] >= rule['min_units'],
                '棋盘对象人数区间无效',
            )
