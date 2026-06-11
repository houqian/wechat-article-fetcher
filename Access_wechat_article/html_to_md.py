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
import json
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


# ---------------------------------------------------------------------------
# 微信代码块还原 (code-snippet)
# 微信编辑器的代码结构: <section class="code-snippet__fix">
#   <ul class="code-snippet__line-index"><li/>×N</ul>   <- 行号列(空li, 转md后变 * * * 噪声)
#   <pre data-lang="java"><code>每行一个code</code>...</pre>
# 直接交给 html2text 会丢失换行且混入行号噪声, 故先抽出原文, 转完再回填 fenced block。
# ---------------------------------------------------------------------------
_CODE_TOKEN = 'WXCODEBLOCKTOKEN{}END'


def _extract_code_blocks(content) -> list:
    """把代码块整体替换为占位符文本, 返回 [(lang, code_text), ...]"""
    blocks = []
    pres = [p for p in content.find_all('pre')
            if p.find('code') or 'code-snippet' in ' '.join(p.get('class') or [])]
    for pre in pres:
        lang = (pre.get('data-lang') or '').strip().lower()
        code_lines = [c.get_text().replace('\xa0', ' ').rstrip()
                      for c in pre.find_all('code')]
        text = '\n'.join(code_lines).strip('\n') if code_lines else \
            pre.get_text().replace('\xa0', ' ').strip('\n')
        if not text.strip():
            continue
        # 替换目标: 含行号ul的外层 section 整体; 否则 pre 自身
        target = pre
        parent = pre.parent
        if parent is not None and parent.name == 'section' and \
                parent.find('ul', class_=re.compile(r'code-snippet')) is not None:
            target = parent
        holder = BeautifulSoup('', 'lxml').new_tag('p')
        holder.string = _CODE_TOKEN.format(len(blocks))
        target.replace_with(holder)
        blocks.append((lang, text))
    # 残留的孤儿行号列 (ul 不在 pre 的 section 里) 直接删除
    for ul in content.find_all('ul', class_=re.compile(r'code-snippet__line-index')):
        ul.decompose()
    return blocks


def _restore_code_blocks(md: str, blocks: list) -> str:
    """把占位符回填为 fenced code block"""
    for i, (lang, text) in enumerate(blocks):
        fenced = f'```{lang}\n{text}\n```'
        md = md.replace(_CODE_TOKEN.format(i), fenced)
    return md


# ---------------------------------------------------------------------------
# 按公众号定制的"文本编号大纲" (heading_profiles.json)
# 适用纯文本编号风格的公众号 (如 东阳马生架构):
#   文首"大纲(N字)"块列出一级目录 1.xxx ~ N.xxx, 正文原样重现这些行作章节标题,
#   章节内再用 (1)xxx / 一.xxx 分层。
# ---------------------------------------------------------------------------
_PROFILE_PATH = Path(__file__).parent / 'heading_profiles.json'
_profiles_cache = None


def _load_profiles() -> dict:
    global _profiles_cache
    if _profiles_cache is None:
        try:
            raw = json.loads(_PROFILE_PATH.read_text(encoding='utf-8'))
            _profiles_cache = {k: v for k, v in raw.items() if not k.startswith('_')}
        except Exception:
            _profiles_cache = {}
    return _profiles_cache


def _unbold(s: str) -> str:
    """去掉 markdown 粗体标记 (微信编辑器常把标题整行加粗, 甚至拆碎成多段 **)"""
    return s.replace('**', '').strip()


def _split_glued_toc(s: str, start_n: int) -> list:
    """把粘连成一行的目录拆开: '6.aaa7.bbb8.ccc' -> ['6.aaa','7.bbb','8.ccc']

    按序号递增顺序切分; 要求 s 以 '<start_n>.' 开头, 否则返回 []。
    """
    if not re.match(rf'^{start_n}\.(?!\d)', s):
        return []
    items, n, pos = [], start_n, 0
    while True:
        m = re.search(rf'(?<!\d){n + 1}\.(?!\d)', s[pos + 2:])
        if not m:
            items.append(s[pos:].strip())
            break
        cut = pos + 2 + m.start()
        items.append(s[pos:cut].strip())
        pos, n = cut, n + 1
    return items


def _extract_toc(lines: list, marker_re) -> tuple:
    """定位文首目录块, 返回 (目录项列表, 块起始行号(含标记行), 块结束行号(不含))"""
    for i, ln in enumerate(lines[:60]):
        if not marker_re.match(_unbold(ln)):
            continue
        items, expect, j, end = [], 1, i + 1, i + 1
        while j < len(lines) and j - i < 300:
            s = _unbold(lines[j])
            if not s:
                j += 1
                continue
            if items and re.sub(r'\s+', '', s) == re.sub(r'\s+', '', items[0]):
                break          # 正文从第一条重现开始
            got = _split_glued_toc(s, expect)
            if not got:
                break          # 不再是连续编号 -> 目录块结束
            if len(got) > 1:
                # 校验粘连拆分: 标题里的 "2.x" 这类文本会被误拆。
                # 拆出多项后, 下一非空行应衔接上 (以 expect+len(got) 号开头);
                # 若它反而衔接"不拆"的序号 (expect+1), 说明拆错, 回退为整行一条。
                nxt = ''
                for k in range(j + 1, min(j + 6, len(lines))):
                    if _unbold(lines[k]):
                        nxt = _unbold(lines[k])
                        break
                if not re.match(rf'^{expect + len(got)}\.(?!\d)', nxt) and \
                        re.match(rf'^{expect + 1}\.(?!\d)', nxt):
                    got = [s]
            items.extend(got)
            expect += len(got)
            end = j + 1
            j += 1
        if items:
            return items, i, end
    return [], -1, -1


def _apply_text_outline(md: str, profile: dict) -> str:
    """按 profile 的文本规则把编号行提升为 markdown 标题; 目录块重排为列表"""
    lines = md.split('\n')
    toc_items, t0, t1 = [], -1, -1
    marker = profile.get('toc_marker')
    if marker:
        toc_items, t0, t1 = _extract_toc(lines, re.compile(marker))
    toc_set = {re.sub(r'\s+', '', it) for it in toc_items}
    max_len = profile.get('max_len', 45)
    bad_end = profile.get('exclude_trailing_punct', '。！？!?；;，,')
    rules = [(re.compile(r['pattern']), r['level'], r.get('require_in_toc', False))
             for r in profile.get('rules', [])]

    out, in_fence = [], False
    for idx, line in enumerate(lines):
        if t0 != -1 and t0 < idx < t1:
            continue                       # 原目录块行, 由下方统一重排
        s = line.strip()
        if s.startswith('```'):
            in_fence = not in_fence
            out.append(line)
            continue
        if in_fence or line.startswith('    '):
            out.append(line)               # 代码内不动
            continue
        sc = _unbold(s)                    # 标题行常被整行加粗(甚至拆碎), 剥掉再匹配
        if t0 != -1 and idx == t0:         # 目录标记行 -> 重排整个目录块
            out.append(f'**{sc}**')
            out.append('')
            out.extend(f'- {it}' for it in toc_items)
            out.append('')
            continue
        promoted = False
        if sc and len(sc) <= max_len and sc[-1] not in bad_end:
            for pat, level, need_toc in rules:
                if not pat.match(sc):
                    continue
                if need_toc and toc_set and re.sub(r'\s+', '', sc) not in toc_set:
                    continue
                out.append('#' * level + ' ' + sc)
                promoted = True
                break
        if not promoted:
            out.append(line)
    return '\n'.join(out)


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
    code_blocks = _extract_code_blocks(content)   # 先抽出代码块(占位), 防止换行丢失

    # 有专属文本大纲规则的公众号跳过通用视觉规则, 防止两套规则给出错误层级
    profile = _load_profiles().get(meta.get('公众号', ''))
    if not profile:
        _promote_headings(content)   # 还原标题层级 (大纲, 通用视觉规则)

    # html2text 不把 <section> 当块级元素, 相邻 section 的文本会粘连成一行;
    # 统一改名为 <div> (html2text 识别为块级), 保证段落/标题各占一行
    for sec in content.find_all('section'):
        sec.name = 'div'

    h = html2text.HTML2Text()
    h.body_width = 0          # 不自动换行
    h.ignore_links = False
    h.ignore_images = False
    h.protect_links = True
    h.unicode_snob = True     # 保留中文/Unicode 原样
    md_body = _cleanup_md(h.handle(str(content)).strip())
    md_body = _restore_code_blocks(md_body, code_blocks)

    # 公众号专属文本大纲规则 (heading_profiles.json)
    if profile:
        md_body = _apply_text_outline(md_body, profile)

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
