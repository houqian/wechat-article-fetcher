"""
html_to_md.py — 将功能3下载的微信公众号文章 (index.html) 批量转换为 Markdown

用法:
    # 转换 all_data 下所有已下载的文章
    python html_to_md.py

    # 只转换某个公众号目录
    python html_to_md.py "all_data/公众号----新华网"

    # 转换单个文章目录 (包含 index.html 的目录) 或单个 index.html
    python html_to_md.py "all_data/公众号----新华网/2025-12-03 12_00_00 某标题"

说明:
    - 每篇文章在其自身目录下生成 article.md
    - 仅提取微信正文区域 (#js_content)，并保留指向本地 resources/images 的图片
    - 不联网、不二次抓取，纯本地转换
"""
import os
import re
import sys
import hashlib
from pathlib import Path

# Windows 默认控制台为 GBK, 强制 stdout 使用 UTF-8 以避免 emoji/特殊字符打印报错
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

from bs4 import BeautifulSoup
import html2text


def _extract_title(soup: BeautifulSoup) -> str:
    """提取文章标题"""
    for sel in ['#activity-name', 'h1.rich_media_title', 'h2.rich_media_title']:
        el = soup.select_one(sel)
        if el and el.get_text(strip=True):
            return el.get_text(strip=True)
    if soup.title and soup.title.get_text(strip=True):
        return soup.title.get_text(strip=True)
    return '未命名文章'


def _extract_meta(soup: BeautifulSoup) -> dict:
    """提取公众号名称 / 发布时间等元信息 (尽力而为)"""
    meta = {}
    name_el = soup.select_one('#js_name')
    if name_el and name_el.get_text(strip=True):
        meta['公众号'] = name_el.get_text(strip=True)
    # 发布时间常被 JS 渲染，优先取 HTML 里的 var ct / createTime
    html = str(soup)
    m = re.search(r"var createTime\s*=\s*'([^']+)'", html)
    if m:
        meta['发布时间'] = m.group(1)
    return meta


def _build_local_index(doc_dir: Path) -> dict:
    """读取 resources/images 目录, 建立 {md5前12位: 相对路径} 索引

    save_to_html.py 以 "实际加载图片 URL 的 md5 前12位" 命名本地文件,
    因此可用同样规则把文章中的远程图片 URL 映射回本地已下载文件。
    """
    index = {}
    img_dir = doc_dir / 'resources' / 'images'
    if img_dir.is_dir():
        for p in img_dir.iterdir():
            if p.is_file():
                index[p.stem] = f'resources/images/{p.name}'
    return index


def _normalize_images(content, doc_dir: Path):
    """将文章中的图片指向本地已下载文件 (离线可用); 匹配不到则保留远程 URL"""
    local_index = _build_local_index(doc_dir)
    for img in content.find_all('img'):
        src = img.get('src') or ''
        # 已是本地相对路径, 直接保留
        if src.startswith('resources/'):
            continue
        # 优先用 src (save_to_html 处理后此处即实际加载的 URL), 其次用懒加载属性
        candidate = src
        if not candidate or candidate.startswith('data:'):
            for attr in ('data-src', 'data-original', 'data-actualsrc'):
                lazy = img.get(attr)
                if lazy:
                    candidate = lazy
                    break
        # 丢弃无效图片 (空 src / JS 模板占位 / data: 占位), 避免生成 ![]() 噪声
        if (not candidate or candidate.startswith('data:')
                or not (candidate.startswith('http') or candidate.startswith('resources/'))):
            img.decompose()
            continue
        if candidate.startswith('http'):
            base = candidate.split('#')[0]
            h12 = hashlib.md5(base.encode()).hexdigest()[:12]
            if h12 in local_index:
                img['src'] = local_index[h12]   # 映射到本地文件
            else:
                img['src'] = candidate          # 兜底: 保留远程 URL
        else:
            img['src'] = candidate
        # 清理懒加载属性, 避免 html2text 误用
        for attr in ('data-src', 'data-original', 'data-actualsrc', 'data-lazy-src'):
            if img.has_attr(attr):
                del img[attr]


_PX_RE = re.compile(r'font-size:\s*([\d.]+)px')
_FW_RE = re.compile(r'font-weight:\s*(bold|[6-9]00)')
# 正文常见字号 (微信默认多为 14-16px); 超过此值视为"大字"
_BIG_FONT_PX = 17.0
_HEADING_MAX_LEN = 42       # 标题文字长度上限
_H3_MAX_LEN = 30


def _merged_style(el, depth: int = 4) -> str:
    """合并元素自身及最多 depth 层祖先的 style, 用于综合判断视觉强调"""
    parts = []
    node = el
    for _ in range(depth):
        if node is None:
            break
        parts.append((node.get('style') or '').lower())
        node = node.parent
    return ' || '.join(parts)


def _is_full_bold(block, text: str) -> bool:
    """整块文字是否被 <strong>/<b> 完整包裹"""
    for b in block.find_all(['strong', 'b']):
        if b.get_text(strip=True) == text:
            return True
    return False


def _heading_level(block) -> int:
    """判断一个短文本块是否是视觉标题; 返回 2/3 表示 H2/H3, 0 表示不是

    依据微信文章排版的通用视觉信号 (经实测校准):
      - 有边框 (border-bottom/left, 常见的彩色下划线) 或非白背景色 -> H2
      - 居中 且 (加粗 或 大字) -> H2
      - 纯加粗的独立短行 -> H3
    仅"大字号"不作为标题依据 (列表项也可能是大字), 必须配合居中/边框/背景。
    """
    text = block.get_text(' ', strip=True)
    if not text or len(text) > _HEADING_MAX_LEN:
        return 0
    # 含内层块 -> 不是最内层文本块, 跳过 (由更内层处理)
    if block.find(['p', 'section', 'h1', 'h2', 'h3', 'h4']):
        return 0
    # 表格内的单元格不当标题 (表头/单元格常带边框背景, 否则会被误判)
    for parent in block.parents:
        if parent.name in ('table', 'thead', 'tbody', 'tr', 'td', 'th', 'li', 'ul', 'ol'):
            return 0
        if parent.name == 'div' and parent.get('id') == 'js_content':
            break
    # 明显是整句正文 (以句号结尾且较长) -> 不当标题
    if len(text) > 18 and text[-1] in '。.！!':
        return 0

    ms = _merged_style(block)
    has_border = ('border-bottom' in ms or 'border-left' in ms
                  or re.search(r'(?<!-)border:\s*[^;]*solid', ms) is not None)
    has_bg = ('background' in ms
              and 'rgb(255, 255, 255)' not in ms
              and 'background: none' not in ms
              and '#fff' not in ms)
    centered = 'text-align: center' in ms
    bold = (_FW_RE.search(ms) is not None) or _is_full_bold(block, text)
    m = _PX_RE.search(ms)
    big = m is not None and float(m.group(1)) >= _BIG_FONT_PX

    if has_border or has_bg or (centered and (bold or big)):
        return 2
    if bold and len(text) <= _H3_MAX_LEN:
        return 3
    return 0


def _promote_headings(content):
    """把视觉上的标题块 (彩色下划线/加粗等) 提升为真实的 <hN> 标签

    html2text 只识别真正的 <h1>~<h6>; 微信文章的小标题常用带样式的
    <section>/<p>, 不处理就会丢失大纲。本函数在转换前重建标题层级。
    """
    candidates = content.find_all(['p', 'section'])
    for block in candidates:
        if block.parent is None:        # 已被替换/移除
            continue
        level = _heading_level(block)
        if level:
            text = block.get_text(' ', strip=True)
            new = BeautifulSoup('', 'lxml').new_tag(f'h{level}')
            new.string = text
            block.replace_with(new)


def _cleanup_md(md: str) -> str:
    """清理转换结果: 去空标题、合并多余空行、去行尾空白"""
    lines = []
    for line in md.split('\n'):
        # 去掉空的标题 (如 '##' 或 '##   ')
        if re.match(r'^#{1,6}\s*$', line):
            continue
        lines.append(line.rstrip())
    md = '\n'.join(lines)
    # 连续 3+ 空行压成 1 个空行
    md = re.sub(r'\n{3,}', '\n\n', md)
    return md.strip()


def convert_one(html_path: Path) -> bool:
    """转换单个 index.html -> 同目录 article.md"""
    try:
        html = html_path.read_text(encoding='utf-8', errors='ignore')
    except Exception as e:
        print(f'  读取失败 {html_path}: {e}')
        return False

    soup = BeautifulSoup(html, 'lxml')
    title = _extract_title(soup)
    meta = _extract_meta(soup)

    content = soup.select_one('#js_content')
    if content is None:
        # 退而求其次：取 rich_media_content 或 body
        content = soup.select_one('.rich_media_content') or soup.body
    if content is None:
        print(f'  未找到正文 {html_path}')
        return False

    _normalize_images(content, html_path.parent)
    _promote_headings(content)   # 还原标题层级 (大纲)

    h = html2text.HTML2Text()
    h.body_width = 0          # 不自动换行
    h.ignore_links = False
    h.ignore_images = False
    h.protect_links = True
    h.unicode_snob = True     # 保留中文/Unicode 原样
    md_body = _cleanup_md(h.handle(str(content)).strip())

    # 组装 markdown
    lines = [f'# {title}', '']
    if meta:
        for k, v in meta.items():
            lines.append(f'> **{k}**: {v}  ')
        lines.append('')
    lines.append(md_body)
    lines.append('')
    md = '\n'.join(lines)

    out_path = html_path.parent / 'article.md'
    out_path.write_text(md, encoding='utf-8')
    print(f'  ✅ {out_path}')
    return True


def find_html_files(target: Path):
    """根据输入路径找出所有待转换的 index.html"""
    if target.is_file() and target.name.lower().endswith('.html'):
        return [target]
    if target.is_dir():
        # 目录本身就含 index.html
        direct = target / 'index.html'
        if direct.exists():
            return [direct]
        # 否则递归查找
        return sorted(target.rglob('index.html'))
    return []


def main():
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('all_data')
    if not target.exists():
        print(f'路径不存在: {target.resolve()}')
        print('请先用 main.py 的功能3下载文章 (生成 index.html) 后再运行本脚本。')
        return

    html_files = find_html_files(target)
    if not html_files:
        print(f'在 {target.resolve()} 下未找到任何 index.html')
        print('请先用 main.py 的功能3下载文章。')
        return

    print(f'共找到 {len(html_files)} 篇文章, 开始转换为 Markdown ...\n')
    ok = 0
    for hp in html_files:
        if convert_one(hp):
            ok += 1
    print(f'\n完成: {ok}/{len(html_files)} 篇转换成功。Markdown 文件 (article.md) 已生成在各文章目录下。')


if __name__ == '__main__':
    main()
