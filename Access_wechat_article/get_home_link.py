"""
get_home_link.py — 由一篇文章链接, 算出该公众号的"主页链接"

用法:
    python get_home_link.py <一篇文章URL>

输出: 公众号名称、__biz、profile_ext?action=home 主页链接。

用途: 把主页链接发到微信PC端"文件传输助手"并点击, 打开该号的历史文章列表页,
      此时才能在 Fiddler 抓到 /mp/profile_ext?action=home 的 token(含 uin/key/pass_ticket)。
"""
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

# 保证从任意 cwd 都能 import 引擎的 src/
_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.core.base_spider import BaseSpider


def main():
    if len(sys.argv) < 2:
        print('用法: python get_home_link.py <一篇文章URL>')
        return
    url = sys.argv[1]
    sp = BaseSpider()
    c = sp.get_an_article(url)
    if c.get('content_flag') != 1:
        print('获取文章内容失败 (链接可能失效或触发验证)。')
        return
    sp.format_content(c['content'])
    print('\n公众号名称:', sp.nickname)
    print('__biz     :', sp.biz)
    print('主页链接   :')
    print(sp.public_main_link)
    print('\n下一步: 把上面的主页链接发到微信PC端"文件传输助手"并点击打开,'
          ' 然后在 Fiddler 抓 /mp/profile_ext?action=home 的请求(Ctrl+U 复制)。')


if __name__ == '__main__':
    main()
