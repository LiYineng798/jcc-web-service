"""Data-driven reference layouts, independent of season and upstream filenames."""

LEGACY_KINDS = frozenset({'charm', 'wand', 'god', 'monster', 'none'})
PRESENTATIONS = frozenset({'cards.v1', 'variants.v1', 'stages.v1', 'table.v1', 'legacy.v1'})
OVERVIEW_CAPABILITY = 'reference.overview.v1'


def presentation_for(mechanic):
    presentation = mechanic.get('presentation')
    if presentation is None:
        presentation = 'legacy.v1' if mechanic.get('kind') in LEGACY_KINDS else 'cards.v1'
    if presentation not in PRESENTATIONS:
        raise ValueError(f'不支持的玩法展示模板：{presentation}')
    if presentation == 'legacy.v1' and mechanic.get('kind') not in LEGACY_KINDS:
        raise ValueError('新玩法请使用通用展示模板')
    return presentation


def reference_metadata(mechanic):
    result = {'presentation': presentation_for(mechanic)}
    if 'description' in mechanic:
        description = mechanic['description']
        if not isinstance(description, str) or len(description) > 4000:
            raise ValueError('玩法简介必须为不超过4000字的文本')
        result['description'] = description
    return result
