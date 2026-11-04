import json
from pathlib import Path
import re
import sys
import tomllib
from urllib.parse import unquote

import yaml

from release import check_versions


ROOT = Path(__file__).resolve().parents[1]
SKILLS = {'codex-shared-knowledge', 'vaultgoblin-setup'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def frontmatter(path):
    text = path.read_text(encoding='utf-8')
    parts = text.split('---', 2)
    require(len(parts) == 3 and not parts[0].strip(), f'{path}: отсутствует frontmatter')
    data = yaml.safe_load(parts[1])
    require(isinstance(data, dict), f'{path}: frontmatter должен быть объектом')
    return data


def contained_file(root, parent, relative, allow_directory=False):
    path = (parent / relative).resolve()
    require(path.is_relative_to(root.resolve()) and (path.is_file() or (allow_directory and path.is_dir())), f'Нет ресурса: {parent}/{relative}')
    return path


def markdown_targets(text):
    fence = None
    for line in text.splitlines():
        marker = re.match(r' {0,3}(`{3,}|~{3,})', line)
        if marker:
            token = marker.group(1)
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
            continue
        if fence is not None:
            continue
        prose = re.sub(r'(`+).*?\1', '', line)
        yield from re.findall(r'\]\(([^)]+)\)', prose)


def check(root=ROOT):
    manifest = json.loads((root / '.codex-plugin/plugin.json').read_text(encoding='utf-8'))
    require(manifest['name'] == 'vaultgoblin', 'Некорректное имя плагина')
    require(re.fullmatch(r'\d+\.\d+\.\d+', manifest['version']), 'Версия должна быть SemVer')
    check_versions(root)
    require(manifest['skills'] == './skills/', 'Некорректный каталог навыков')
    onboarding = manifest.get('extensions', {}).get('com.openai', {}).get('onboardingSkill')
    if onboarding:
        contained_file(root, root, onboarding)
    hooks = json.loads(contained_file(root, root, manifest['hooks']).read_text(encoding='utf-8'))
    require(set(hooks['hooks']) == {'SessionStart', 'Stop', 'SessionEnd'}, 'Набор hooks изменился')
    catalog = json.loads((root / '.agents/plugins/marketplace.json').read_text(encoding='utf-8'))
    require(catalog['name'] == 'vaultgoblin' and len(catalog['plugins']) == 1, 'Некорректный marketplace')
    entry = catalog['plugins'][0]
    require(entry['name'] == 'vaultgoblin' and entry['source'] == {'source': 'local', 'path': './'}, 'Некорректный source')
    require({p.parent.name for p in (root / 'skills').glob('*/SKILL.md')} == SKILLS, 'Набор навыков изменился')
    for name in sorted(SKILLS):
        folder = root / 'skills' / name
        data = frontmatter(folder / 'SKILL.md')
        require(data.get('name') == name, f'{name}: имя frontmatter отличается от каталога')
        description = data.get('description')
        require(isinstance(description, str) and 20 <= len(description) <= 1024, f'{name}: description')
        ui = yaml.safe_load((folder / 'agents/openai.yaml').read_text(encoding='utf-8'))
        interface = ui['interface']
        require(25 <= len(interface['short_description']) <= 64, f'{name}: длина UI description')
        require(f'${name}' in interface['default_prompt'], f'{name}: default_prompt без имени навыка')
        require(ui.get('policy', {}).get('allow_implicit_invocation', True) is True, f'{name}: изменена доступность')
        for field in ('icon_small', 'icon_large'):
            if interface.get(field):
                contained_file(folder, folder, interface[field])
    interface = manifest['interface']
    for relative in [interface['composerIcon'], interface['logo'], *interface.get('screenshots', [])]:
        asset = contained_file(root, root, relative)
        require(asset.read_bytes().startswith(b'\x89PNG\r\n\x1a\n'), f'{asset}: ожидался PNG')
    for path in root.rglob('*.md'):
        if any(part in {'.git', '.venv', 'work'} for part in path.relative_to(root).parts):
            continue
        text = path.read_text(encoding='utf-8')
        for target in markdown_targets(text):
            target = target.split('#', 1)[0]
            if not target or '://' in target or target.startswith('mailto:'):
                continue
            contained_file(root, path.parent, unquote(target), allow_directory=True)
    print(f'Пакет {manifest["version"]}: {len(SKILLS)} навыков, метаданные, ссылки и ресурсы проверены.')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    check()
