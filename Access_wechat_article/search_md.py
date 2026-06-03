"""
search_md.py — 方案B: 指定公众号 + 关键词过滤, 自动下载并转 Markdown

两种用法:
  A) 交互模式 (双击 search_to_md.bat 或直接运行):
        python search_md.py [关键词...]
     按提示粘贴每个公众号的 Fiddler token, 可连续处理多个号。

  B) 非交互模式 (供脚本/Claude 调用, 单个公众号):
        python search_md.py --token "<profile_ext URL>" [--pages 0] [--data-root .] [关键词...]
     直接传 token 跑一个号后退出, 无任何提示。

关键词来源 (优先级从高到低):
    - 命令行位置参数:  python search_md.py Agent 智能体 RAG
    - keywords.txt 文件 (当前目录, 每行一个, # 开头为注释)
    - 交互模式下手动输入

token 获取方法 (每个公众号一次):
    见 README.md / 使用说明.md: 微信PC端打开该号"主页/历史文章列表页" -> Fiddler 找到
    Host=mp.weixin.qq.com 且 URL 以 /mp/profile_ext?action=home 开头的请求 ->
    选中后 Ctrl+U 复制完整 URL。

输出 (相对 --data-root, 默认当前目录):
    all_data/公众号----<名称>/<发布日期> <标题>/article.md  (+ index.html + 本地图片)
    all_data/公众号----<名称>/_命中清单.txt
"""
import os
import re
import sys
import argparse
from pathlib import Path

# 强制 UTF-8 输出, 避免 Windows GBK 控制台打印 emoji 报错
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

# 保证无论从哪个 cwd 调用, 都能 import 引擎自身的 src/ 与 html_to_md
_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Playwright 使用引擎本地浏览器内核
os.environ.setdefault(
    'PLAYWRIGHT_BROWSERS_PATH',
    str(_PROJECT_ROOT / '.venv' / '.playwright-browsers'),
)

from src.core.wechat_funcs import ArticleDetail
from src.storage.save_to_html import SaveWebpageToHtml
from src.utils.tools import set_nickname_path, set_article_path
from html_to_md import convert_one


def load_keywords(cli_keywords) -> list:
    """关键词: 命令行位置参数 > keywords.txt(cwd) > (交互)手动输入"""
    if cli_keywords:
        return cli_keywords
    kw_file = Path('keywords.txt')
    if kw_file.exists():
        kws = [l.strip() for l in kw_file.read_text(encoding='utf-8').splitlines()
               if l.strip() and not l.strip().startswith('#')]
        if kws:
            return kws
    return []


def title_matched(title: str, keywords: list) -> bool:
    t = title.lower()
    return any(kw.lower() in t for kw in keywords)


def parse_pages(raw: str) -> tuple:
    """'N' -> (1,N); 'N-M' -> (N,M); '' 或 '0' -> (0,1)=全部"""
    raw = (raw or '').strip()
    if not raw or raw == '0':
        return (0, 1)
    if '-' in raw:
        a, b = raw.split('-')
        return (int(a), int(b))
    return (1, int(raw))


def run_account(token_url, keywords, page_start, page_end, data_root='.'):
    """处理单个公众号(无交互): token -> 列表 -> 关键词过滤 -> 下载 -> 转 md。

    返回成功生成 md 的篇数; token 无效返回 0。
    """
    detail = ArticleDetail()
    if not detail.format_raw_link(token_url):
        print('token 链接参数有误 (缺 __biz/uin/key/pass_ticket)。')
        return 0

    print('开始获取文章列表 ...')
    try:
        article_list = detail.whole_article_list(page_start, page_end)
    except Exception as e:
        print(f'获取文章列表失败: {e}')
        return 0
    if not article_list:
        print('未获取到文章列表 (可能 token 失效或该号被限流)。')
        return 0

    # 关键词过滤 (标题在 index 3, 直连链接在 index 6)
    matched = [a for a in article_list if title_matched(a[3], keywords)]
    print(f'\n共 {len(article_list)} 篇文章, 命中关键词 {keywords} 的有 {len(matched)} 篇:')
    for a in matched:
        print(f'  · [{a[2]}] {a[3]}')
    if not matched:
        print('没有命中的文章, 跳过下载。')
        return 0

    # 获取公众号名称 (用第一篇命中文章)
    nickname = '未知公众号'
    try:
        c = detail.get_an_article(matched[0][6])
        if c['content_flag'] == 1:
            detail.format_content(c['content'])
            nickname = detail.nickname or nickname
    except Exception:
        pass
    print(f'\n公众号: {nickname} — 开始下载 {len(matched)} 篇并转换为 Markdown\n')

    nickname_path = set_nickname_path(nickname, rootpath=str(Path(data_root) / 'all_data'))
    saver = SaveWebpageToHtml()
    ok = 0
    hit_lines = []
    for i, a in enumerate(matched, 1):
        create_time, title, url = a[2], a[3], a[6]
        print(f'\n---------- [{i}/{len(matched)}] {title} ----------')
        article_path = set_article_path(nickname_path, create_time, title)
        try:
            success = saver.save_webpage_with_resources(url, article_path)
        except Exception as e:
            print(f'下载出错: {e}')
            success = False
        if success and convert_one(Path(article_path) / 'index.html'):
            ok += 1
            hit_lines.append(f'[{create_time}] {title}\n    {url}')

    if hit_lines:
        (Path(nickname_path) / '_命中清单.txt').write_text(
            f'关键词: {keywords}\n命中并成功下载 {ok} 篇:\n\n' + '\n\n'.join(hit_lines),
            encoding='utf-8',
        )
    print(f'\n[{nickname}] 完成: {ok}/{len(matched)} 篇已生成 Markdown。')
    return ok


def process_one_account(keywords, data_root='.'):
    """交互式处理单个公众号: 提示输入 token 与页数, 再调用 run_account。"""
    token_url = input(
        '\n粘贴该公众号的 Fiddler token 链接 (profile_ext...), 直接回车跳过: '
    ).strip()
    if not token_url:
        return None
    raw = input(
        '\n获取多少页文章用于筛选? (一页约10-15篇)\n'
        '  直接回车 = 全部; 输入 3 = 前3页; 输入 2-5 = 第2到5页\n请输入: '
    ).strip()
    start, end = parse_pages(raw)
    return run_account(token_url, keywords, start, end, data_root)


def main():
    parser = argparse.ArgumentParser(
        description='指定公众号 + 关键词筛选, 下载并转 Markdown')
    parser.add_argument('keywords', nargs='*', help='关键词(位置参数, 空格分隔)')
    parser.add_argument('--token', help='非交互模式: 该公众号 profile_ext token 链接')
    parser.add_argument('--pages', default=None, help='N / N-M / 0(全部); 非交互默认全部')
    parser.add_argument('--data-root', default='.', help='输出根目录(默认当前目录)')
    args = parser.parse_args()

    keywords = load_keywords(args.keywords)

    # ---------- 非交互模式 ----------
    if args.token:
        if not keywords:
            print('未提供关键词 (命令行位置参数或当前目录 keywords.txt)。')
            return
        print(f'关键词: {keywords}')
        start, end = parse_pages(args.pages)
        run_account(args.token, keywords, start, end, args.data_root)
        return

    # ---------- 交互模式 ----------
    if not keywords:
        raw = input('请输入关键词 (多个用空格或逗号分隔, 如: Agent 智能体 RAG): ').strip()
        keywords = re.split(r'[\s,，]+', raw) if raw else []
    if not keywords:
        print('未提供关键词, 退出。')
        return
    print(f'关键词: {keywords}')
    print('提示: 每个公众号需要各自的 Fiddler token (见 使用说明.md)。可连续处理多个号。')

    total = 0
    n = 0
    while True:
        res = process_one_account(keywords, args.data_root)
        if res is None:          # 用户回车跳过 = 结束
            break
        total += res
        n += 1
        cont = input('\n是否继续处理下一个公众号? (y/直接回车=是, n=结束): ').strip().lower()
        if cont == 'n':
            break

    print(f'\n===== 全部结束: 共处理 {n} 个公众号, 累计生成 {total} 篇 Markdown =====')
    print(f'输出根目录: {(Path(args.data_root) / "all_data").resolve()}')


if __name__ == '__main__':
    main()
