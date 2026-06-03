"""
export_md.py — 把散落在各文件夹的 article.md 汇总导出

把 all_data/公众号----<名称>/<日期 标题>/article.md 整理成:

    导出_md/
      <公众号名称>/
        <文章标题>.md        ← 文件名就是文章标题
        assets/<图片>        ← 该公众号所有文章的图片(md5命名, 同图不重复)

特点:
    - 按公众号归类, md 文件名 = 文章标题
    - 图片重写为指向 assets/, 不会裂图; 远程图片(未本地化的)保持原样
    - 纯复制, 不动 all_data 里的原文件; 重复运行会覆盖导出目录里的同名文件
    - 标题重名时自动加日期后缀避免覆盖

用法:
    python export_md.py            # 导出 all_data 下全部公众号
    python export_md.py "all_data/公众号----阿里云开发者"   # 只导出某个号
"""
import re
import sys
import shutil
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

SRC_ROOT = Path('all_data')
OUT_ROOT = Path('导出_md')
_IMG_REF = re.compile(r'resources/images/([^\s)"\']+)')


def _safe_filename(name: str, maxlen: int = 80) -> str:
    name = re.sub(r'[\\/*?:"<>|\r\n\t]', '_', name).strip()
    name = name.rstrip('. ')          # Windows 文件名不能以点/空格结尾
    return name[:maxlen] or '未命名'


def _title_from_md(md_path: Path, fallback: str) -> str:
    """取 md 第一行的 # 标题; 没有则用 fallback(目录名去掉日期前缀)"""
    try:
        for line in md_path.read_text(encoding='utf-8', errors='ignore').splitlines():
            if line.startswith('# '):
                return line[2:].strip()
    except Exception:
        pass
    return fallback


def _strip_date_prefix(folder_name: str) -> str:
    # 形如 "2026-02-24 标题" -> "标题"
    m = re.match(r'^\d{4}-\d{2}-\d{2}\s+(.*)$', folder_name)
    return m.group(1) if m else folder_name


def export_account(account_dir: Path) -> int:
    # 公众号名称: 去掉 "公众号----" 前缀
    raw = account_dir.name
    nickname = raw.split('----', 1)[1] if '----' in raw else raw
    out_dir = OUT_ROOT / _safe_filename(nickname)
    assets_dir = out_dir / 'assets'

    article_mds = sorted(account_dir.glob('*/article.md'))
    if not article_mds:
        return 0
    out_dir.mkdir(parents=True, exist_ok=True)
    assets_dir.mkdir(exist_ok=True)

    used_names = {}
    ok = 0
    for md_path in article_mds:
        art_dir = md_path.parent
        folder = art_dir.name
        title = _title_from_md(md_path, _strip_date_prefix(folder))
        base = _safe_filename(title)

        # 重名处理: 加日期前缀
        date_m = re.match(r'^(\d{4}-\d{2}-\d{2})', folder)
        if base in used_names:
            prefix = (date_m.group(1) + ' ') if date_m else f'{used_names[base]+1}_'
            fname = _safe_filename(prefix + title)
        else:
            fname = base
        used_names[base] = used_names.get(base, 0) + 1

        md = md_path.read_text(encoding='utf-8', errors='ignore')

        # 复制被引用的图片到 assets/, 并把链接改为 assets/<file>
        for m in _IMG_REF.finditer(md):
            img_file = m.group(1)
            src_img = art_dir / 'resources' / 'images' / img_file
            if src_img.exists():
                dst_img = assets_dir / img_file
                if not dst_img.exists():
                    shutil.copy2(src_img, dst_img)
        md = _IMG_REF.sub(r'assets/\1', md)

        (out_dir / f'{fname}.md').write_text(md, encoding='utf-8')
        ok += 1

    print(f'  {nickname}: 导出 {ok} 篇 -> {out_dir}')
    return ok


def main():
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else SRC_ROOT
    if not target.exists():
        print(f'路径不存在: {target.resolve()}')
        return

    # 确定要处理的公众号目录列表
    if '公众号----' in target.name:
        accounts = [target]
    else:
        accounts = sorted(p for p in target.glob('公众号----*') if p.is_dir())

    if not accounts:
        print(f'在 {target.resolve()} 下未找到 "公众号----*" 目录')
        return

    print(f'开始导出 {len(accounts)} 个公众号 -> {OUT_ROOT.resolve()}\n')
    total = sum(export_account(a) for a in accounts)
    print(f'\n完成: 共导出 {total} 篇 Markdown 到 {OUT_ROOT.resolve()}')


if __name__ == '__main__':
    main()
