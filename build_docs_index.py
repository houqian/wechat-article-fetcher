# -*- coding: utf-8 -*-
"""
生成 docsify 站点的导航索引(_sidebar.md)与首页(home.md)。

扫描规则:仓库根下每个「主题文件夹」里的 导出_md/<公众号>/*.md。
新增主题后重新运行本脚本即可刷新导航:  python build_docs_index.py
"""
import os
from urllib.parse import quote

ROOT = os.path.dirname(os.path.abspath(__file__))
EXPORT_DIRNAME = "导出_md"


def url(path_segments):
    """把路径各段做 URL 编码后拼成以 / 开头的绝对站内链接。"""
    return "/" + "/".join(quote(s) for s in path_segments)


def collect():
    """返回 [(topic, [(account, [md_filename,...]), ...]), ...]"""
    topics = []
    for topic in sorted(os.listdir(ROOT)):
        topic_dir = os.path.join(ROOT, topic)
        export_dir = os.path.join(topic_dir, EXPORT_DIRNAME)
        if not os.path.isdir(export_dir):
            continue
        accounts = []
        for account in sorted(os.listdir(export_dir)):
            acc_dir = os.path.join(export_dir, account)
            if not os.path.isdir(acc_dir):
                continue
            mds = sorted(f for f in os.listdir(acc_dir) if f.endswith(".md"))
            if mds:
                accounts.append((account, mds))
        if accounts:
            topics.append((topic, accounts))
    return topics


def build_sidebar(topics):
    lines = ["- [🏠 首页](/home.md)", ""]
    for topic, accounts in topics:
        lines.append(f"- **📂 {topic}**")
        for account, mds in accounts:
            lines.append(f"  - **{account}** ({len(mds)})")
            for md in mds:
                title = md[:-3]  # 去掉 .md
                link = url([topic, EXPORT_DIRNAME, account, md])
                lines.append(f"    - [{title}]({link})")
    return "\n".join(lines) + "\n"


def build_home(topics):
    total = sum(len(mds) for _, accs in topics for _, mds in accs)
    lines = [
        "# 📚 公众号文章库",
        "",
        "> 按主题与公众号整理的文章合集，点击左侧导航即可在线阅读（含原文图片）。",
        "",
        f"目前共收录 **{total}** 篇文章。",
        "",
    ]
    for topic, accounts in topics:
        sub_total = sum(len(mds) for _, mds in accounts)
        lines.append(f"## 📂 {topic}（{sub_total} 篇）")
        lines.append("")
        lines.append("| 公众号 | 文章数 |")
        lines.append("| --- | ---: |")
        for account, mds in accounts:
            lines.append(f"| {account} | {len(mds)} |")
        lines.append("")
    return "\n".join(lines) + "\n"


def main():
    topics = collect()
    if not topics:
        print("未找到任何 导出_md 主题，跳过。")
        return
    with open(os.path.join(ROOT, "_sidebar.md"), "w", encoding="utf-8") as f:
        f.write(build_sidebar(topics))
    with open(os.path.join(ROOT, "home.md"), "w", encoding="utf-8") as f:
        f.write(build_home(topics))
    total = sum(len(mds) for _, accs in topics for _, mds in accs)
    print(f"已生成 _sidebar.md 与 home.md：{len(topics)} 个主题，共 {total} 篇文章。")


if __name__ == "__main__":
    main()
