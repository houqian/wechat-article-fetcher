# wechat-article-fetcher

> 面向研究的微信公众号文章抓取工具集：**抓取文章 → 关键词筛选 → 转为高质量 Markdown（含本地图片）→ 按公众号/主题归档建索引**。
>
> 仅限学习与研究、非商业用途，请遵守微信平台协议及相关法律法规。

---

## 这是什么

本仓库在开源项目 [Access_wechat_article](https://github.com/yeximm/Access_wechat_article)（作者 [@yeximm](https://github.com/yeximm)，CC BY-NC-SA 4.0）的基础上，新增了**关键词筛选**与 **Markdown 转换/汇总/索引**能力，并按「一个研究主题 = 一个独立子文件夹」的方式组织产物。

它解决的核心问题：微信没有公开的文章搜索接口，想系统性地收集「某个公众号下与某主题相关的文章」并整理成可阅读、可检索的资料库，手工做非常繁琐。本工具把这条链路自动化。

## 仓库结构

```
wechat-article-fetcher/
├── Access_wechat_article/   # 引擎：爬虫内核 + 转 md / 筛选 / 导出脚本（固定不动）
│   ├── src/                 # 原项目爬虫内核（base_spider / wechat_funcs / storage ...）
│   ├── main.py              # 原项目交互菜单（获取列表 / 阅读量等，功能 2/4 需 Fiddler）
│   ├── search_md.py         # 指定公众号 + 关键词 → 筛选 + 下载 + 转 md
│   ├── download_md.py       # 已有文章链接 → 直接下载并转 md（不用 Fiddler）
│   ├── html_to_md.py        # 把已下载 index.html 转为 Markdown（含图片本地化）
│   ├── export_md.py         # 汇总导出：按公众号归类，文件名 = 标题
│   ├── make_index.py        # 按 categories.json 生成分类索引 README
│   ├── *.bat                # 一键启动脚本（自动设 UTF-8 与 Playwright 内核路径）
│   └── 使用说明.md           # ⭐ 详细操作手册（强烈先读这个）
│
└── Agent/                   # 一个研究主题示例（“Agent / 智能体” 主题的数据产物）
    ├── keywords.txt         # 该主题的标题筛选关键词
    ├── categories.json      # 分类名 → 标题关键词，用于生成分类索引
    ├── all_data/            # 抓取/转换的原始产物
    └── 导出_md/             # 按公众号归类、文件名=标题的整洁版本
```

> 约定：**引擎目录 `Access_wechat_article/` 固定不动**；每个研究主题建一个与它平级的独立子文件夹（如 `Agent/`），脚本在主题文件夹里运行，产物落在该文件夹内。

## 三种典型用法

| 场景 | 用哪个 | 是否需要 Fiddler |
|------|--------|------------------|
| **A. 已有一批文章链接**，只想下载并转 md | `download_md.py` | ❌ |
| **B. 指定公众号 + 关键词筛选**（主用法） | `search_md.py` / `search_to_md.bat` | ✅ 每个号抓一次 token |
| 把已下载的 html 批量转 md | `html_to_md.py` | ❌ |
| 原项目交互菜单（文章列表 / 阅读量 / 点赞等） | `main.py` / `run.bat` | 功能 2/4 需要 |

详细步骤（含 Fiddler 抓 token、关键词配置、输出目录说明）见 **[`Access_wechat_article/使用说明.md`](Access_wechat_article/使用说明.md)**。

## 快速开始

```bash
cd Access_wechat_article

# 1. 创建并激活虚拟环境
python -m venv .venv
.\.venv\Scripts\activate          # Windows
# source .venv/bin/activate       # Linux / macOS

# 2. 安装依赖
pip install -r requirements.txt

# 3. 安装 Playwright Chromium 内核（详见 使用说明.md 第 0/3.4 节）
playwright install chromium

# 4. 运行（任选其一）
python search_md.py               # 方案 B：关键词筛选
python download_md.py <文章链接>   # 方案 A：已有链接
python main.py                    # 原项目交互菜单
```

- 环境要求：Python ≥ 3.13、微信 **PC 版**、[Fiddler Classic](https://www.telerik.com/fiddler/fiddler-classic)（仅方案 B / 功能 2、4 需要）。
- Windows 用户可直接双击对应 `.bat` 一键运行（已处理 UTF-8 控制台与内核路径）。

## 输出形态

```
all_data/公众号----<名称>/
└── <发布日期> <标题>/
    ├── article.md          # Markdown 正文 + 本地图片
    ├── index.html          # 原始网页
    └── resources/images    # 本地化图片

导出_md/<公众号名称>/
├── <文章标题>.md           # 文件名即标题
└── assets/                 # 该号所有图片（自动去重）
```

## 配合 Claude Code 技能使用

本工具已封装为 Claude Code 技能 **`wechat-agent-research`**。在对话里直接说「研究 XX 主题，把相关公众号文章抓下来转 md 并建分类索引」即可触发，由 Claude 按流程驱动引擎脚本、自动分主题归档。

## 致谢与许可

- 爬虫内核基于 [@yeximm / Access_wechat_article](https://github.com/yeximm/Access_wechat_article)，遵循 **[CC BY-NC-SA 4.0](http://creativecommons.org/licenses/by-nc-sa/4.0/)**（署名-非商业性使用-相同方式共享）。原始 `LICENSE` 保留在 `Access_wechat_article/` 目录中。
- 本仓库新增的筛选 / 转换 / 导出 / 索引脚本同样**仅供学习研究、非商业用途**。
- 使用者须遵守微信平台服务协议及相关法律法规，由使用行为产生的一切后果由使用者自行承担。
