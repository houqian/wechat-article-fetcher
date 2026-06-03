"""
make_index.py — 为某个公众号的导出目录生成"按子主题归类"的目录索引 README.md

用法:
    python make_index.py <导出账号目录> [categories.json路径]

例:
    python make_index.py "导出_md/阿里云开发者"
    python make_index.py "导出_md/阿里云开发者" my_cats.json

categories.json 格式 (有序: 分类名 -> 标题关键词列表, 大小写不敏感子串匹配):
    {
      "入门 · 概念": ["什么是", "十问", "为什么"],
      "多智能体":   ["multi-agent", "多智能体", "编排"],
      "其他": []
    }
归类规则:
    - 每篇文章按 JSON 顺序, 落入第一个"标题命中其任一关键词"的分类。
    - 关键词列表为空的分类只作兜底(放未匹配到的文章)。
    - 若没有任何兜底分类, 自动追加一个"其他"分类收纳未匹配文章。

categories.json 查找顺序(未显式传第二参数时):
    <导出账号目录>/categories.json  ->  当前目录 categories.json
若都没有, 则不分类, 全部放在"全部文章"下。
"""
import re
import sys
import json
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass


def load_categories(base: Path, explicit: str = None):
    """返回有序 list[(分类名, [关键词...])]; 找不到配置返回 None"""
    candidates = []
    if explicit:
        candidates.append(Path(explicit))
    candidates.append(base / 'categories.json')
    candidates.append(Path('categories.json'))
    for p in candidates:
        if p.exists():
            data = json.loads(p.read_text(encoding='utf-8'))
            # dict 保序 (Python 3.7+ / json 解析保持插入顺序)
            return [(name, [k.lower() for k in kws]) for name, kws in data.items()], p
    return None, None


def collect_articles(base: Path):
    """读取导出目录下所有文章, 返回 [(date, title_stem)], 按 (date,title) 排序"""
    rows = []
    for f in sorted(base.glob('*.md')):
        if f.name == 'README.md':
            continue
        date = ''
        for line in f.read_text(encoding='utf-8', errors='ignore').splitlines()[:8]:
            m = re.search(r'发布时间.*?(\d{4}-\d{2}-\d{2})', line)
            if m:
                date = m.group(1)
                break
        rows.append((date, f.stem))
    rows.sort()
    return rows


def categorize(rows, categories):
    """把文章分配到分类。返回有序 list[(分类名, [(date,title)...])]"""
    if not categories:
        return [('全部文章', rows)]

    # 确定兜底分类(关键词为空的最后一个); 没有则追加"其他"
    cats = [(name, kws) for name, kws in categories]
    fallback = None
    for name, kws in cats:
        if not kws:
            fallback = name
    if fallback is None:
        fallback = '其他'
        cats.append((fallback, []))

    buckets = {name: [] for name, _ in cats}
    for date, title in rows:
        tl = title.lower()
        placed = False
        for name, kws in cats:
            if kws and any(k in tl for k in kws):
                buckets[name].append((date, title))
                placed = True
                break
        if not placed:
            buckets[fallback].append((date, title))

    # 保持配置顺序, 跳过空分类
    return [(name, buckets[name]) for name, _ in cats if buckets[name]]


def _anchor(name: str) -> str:
    return (name.replace(' ', '-').replace('·', '')
            .replace('(', '').replace(')', '').replace('/', ''))


def main():
    if len(sys.argv) < 2:
        print('用法: python make_index.py <导出账号目录> [categories.json路径]')
        return
    base = Path(sys.argv[1])
    explicit = sys.argv[2] if len(sys.argv) > 2 else None
    if not base.is_dir():
        print(f'目录不存在: {base.resolve()}')
        return

    rows = collect_articles(base)
    if not rows:
        print(f'{base} 下没有可索引的 .md 文章')
        return

    categories, cat_path = load_categories(base, explicit)
    grouped = categorize(rows, categories)

    nickname = base.name
    total = len(rows)
    lines = [f'# {nickname} · 文章目录索引', '',
             f'共 **{total}** 篇，按子主题归类（点击标题打开对应 Markdown）。', '']
    if cat_path:
        lines.append(f'> 分类配置: `{cat_path.name}`；由 `make_index.py` 自动生成。')
    else:
        lines.append('> 未提供 categories.json，未分类。由 `make_index.py` 生成。')
    lines += ['', '## 子主题', '']
    for name, items in grouped:
        lines.append(f'- [{name}](#{_anchor(name)}) ({len(items)})')
    lines += ['', '---', '']

    for name, items in grouped:
        lines.append(f'## {name}')
        lines.append('')
        for date, stem in items:
            lines.append(f'- `{date}` [{stem}](<{stem}.md>)')
        lines.append('')

    out = base / 'README.md'
    out.write_text('\n'.join(lines), encoding='utf-8')

    # 校验链接目标存在
    missing = [stem for _, items in grouped for _, stem in items
               if not (base / f'{stem}.md').exists()]
    print(f'已生成: {out}')
    print(f'共 {total} 篇, {len(grouped)} 个子主题, 链接缺失: {len(missing)}')
    for m in missing[:10]:
        print('  缺失:', m)


if __name__ == '__main__':
    main()
