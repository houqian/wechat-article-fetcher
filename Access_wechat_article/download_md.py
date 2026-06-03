"""
download_md.py — 一步到位: 给定微信文章链接, 直接下载并转换为 Markdown (无需 Fiddler)

适用场景:
    你已经收集好若干篇文章的链接 (例如各大厂公众号里 Agent 相关的文章),
    只想把它们下载到本地并保存为 markdown。本脚本跳过"获取文章列表"环节,
    因此不需要微信PC端 + Fiddler。

用法:
    # 方式一: 把链接逐行写入 urls.txt (# 开头为注释), 然后运行:
    python download_md.py

    # 方式二: 直接在命令行传链接:
    python download_md.py https://mp.weixin.qq.com/s/xxxx https://mp.weixin.qq.com/s/yyyy

    # 方式三: 指定一个自定义的链接文件:
    python download_md.py my_links.txt

输出:
    all_data/markdown_articles/<序号>_<标题>/
        ├── index.html        # 原始网页
        ├── article.md        # 转换后的 Markdown
        └── resources/images  # 本地图片
"""
import os
import re
import sys
import time
import random
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

# 设置 Playwright 使用项目本地浏览器内核 (与 all_process.py 保持一致)
os.environ.setdefault(
    'PLAYWRIGHT_BROWSERS_PATH',
    str(_PROJECT_ROOT / '.venv' / '.playwright-browsers'),
)

from src.storage.save_to_html import SaveWebpageToHtml
from html_to_md import convert_one, _extract_title
from bs4 import BeautifulSoup


OUTPUT_ROOT = Path('all_data') / 'markdown_articles'


def _safe_name(name: str, maxlen: int = 60) -> str:
    name = re.sub(r'[\\/*?:"<>|\r\n]', '_', name).strip()
    name = name.replace('.', '')
    return name[:maxlen] or '未命名'


def load_urls() -> list:
    args = [a for a in sys.argv[1:]]
    # 命令行直接给的 http 链接
    url_args = [a for a in args if a.startswith('http')]
    if url_args:
        return url_args
    # 否则把第一个非链接参数当作链接文件, 默认 urls.txt
    file_args = [a for a in args if not a.startswith('http')]
    url_file = Path(file_args[0]) if file_args else Path('urls.txt')
    if not url_file.exists():
        return []
    urls = []
    for line in url_file.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if line and not line.startswith('#'):
            urls.append(line)
    return urls


def main():
    urls = load_urls()
    if not urls:
        print('未找到任何文章链接。')
        print('请把文章链接逐行写入 urls.txt, 或在命令行传入链接。')
        print('示例: python download_md.py https://mp.weixin.qq.com/s/xxxx')
        return

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    print(f'共 {len(urls)} 篇文章待处理。\n')

    saver = SaveWebpageToHtml()
    ok = 0
    for i, url in enumerate(urls, 1):
        print(f'\n========== [{i}/{len(urls)}] {url} ==========')
        tmp_dir = OUTPUT_ROOT / f'_downloading_{i}'
        try:
            success = saver.save_webpage_with_resources(url, str(tmp_dir))
        except Exception as e:
            print(f'下载出错: {e}')
            success = False

        if not success:
            print(f'⚠️  第 {i} 篇下载失败, 已跳过。')
            continue

        # 用文章标题重命名目录
        html_path = tmp_dir / 'index.html'
        title = '未命名'
        try:
            soup = BeautifulSoup(html_path.read_text(encoding='utf-8', errors='ignore'), 'lxml')
            title = _extract_title(soup)
        except Exception:
            pass
        final_dir = OUTPUT_ROOT / f'{i:02d}_{_safe_name(title)}'
        if final_dir.exists():
            final_dir = OUTPUT_ROOT / f'{i:02d}_{_safe_name(title)}_{int(time.time())}'
        try:
            tmp_dir.rename(final_dir)
        except Exception:
            final_dir = tmp_dir  # 重命名失败则沿用临时目录

        # 转换为 markdown
        if convert_one(final_dir / 'index.html'):
            ok += 1

        # 防封禁延时
        if i < len(urls):
            delay = round(random.uniform(2.0, 5.0), 2)
            print(f'为预防被封禁, 延时 {delay} 秒...')
            time.sleep(delay)

    print(f'\n全部完成: {ok}/{len(urls)} 篇已生成 Markdown。')
    print(f'输出目录: {OUTPUT_ROOT.resolve()}')


if __name__ == '__main__':
    main()
