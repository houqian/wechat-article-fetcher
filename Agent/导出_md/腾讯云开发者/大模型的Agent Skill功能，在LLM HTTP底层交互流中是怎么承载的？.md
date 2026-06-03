# 大模型的Agent Skill功能，在LLM HTTP底层交互流中是怎么承载的？

> **公众号**: 腾讯云开发者  
> **发布时间**: 2026-05-28 08:45  

## 关注腾讯云开发者，一手技术干货提前解锁👇

# 01

## 前言

前几天我在司内论坛的一个问答中提到了要写一个拉取网络文章文本的 skill，昨天我实现了之后也就开始好奇起 Skills 的底层原理了——相比起各种花里胡哨的 agrnt 应用，我一直以来都很对大模型在纯粹的 HTTP 交互层面是如何交互的更感兴趣。

我们知道，大模型只会对话，聊天，所谓的工具调用也只不过是特化的聊天功能而已。但是各种天花乱坠的 skills，是如何在底层的 HTTP 中，与大模型——这个只会嘴遁的工具交互的呢？

# 02

## 前置知识

本文面向对 OpenAI 兼容协议 有了解的同学，如果不了解的话，可以参考协议文档，或者是我的 两篇老文章 https://cloud.tencent.com/developer/article/2518981 简单了解。

# 03

## 核心结论先说：Skills 不是协议层概念

在 OpenAI 兼容协议中，根本不存在 "Skill" 这个字段或角色。 Skills 是一个纯粹的应用层抽象，它最终被 Cursor（或类似的 AI IDE）"编译"成三种协议原语的组合：

  1. System/Developer Message — 把 Skill 的指令文本注入到 system prompt 中

  2. Tools Definition — 把 Skill 需要用到的工具（如 Shell、Read 等）注册为 `tools`数组

  3. Multi-turn Tool Calling Loop — LLM 根据注入的指令，自主决策发起 tool_calls，宿主执行后把结果喂回去

用一句话总结：Skill = 动态注入的 system prompt 片段 + 预定义的 tool schema + 多轮 tool calling 循环。这里我们用 Cursor 以及我实现的 skill mp-read 来举例，其他工具（OpenClaw）也是一样的——

# 04

## 第 0 步：Skill 发现与描述摘要注入

在你打开 Cursor、还没说话的时候，Cursor 就已经扫描了 .cursor/skills/、.agents/skills/ 等目录，收集了所有 Skill 的 name + description（来自 YAML frontmatter），然后把它们作为静态上下文塞进 system prompt。

以你的 mp-read 为例，SKILL.md 的 frontmatter 是：

  *   *   *   *   *

    name: mp-readdescription: >-  Extract plain text from Tencent MP (mp.weixin.qq) articles using a headless  Chrome browser. Use when the user wants to read, fetch, extract, summarize,  or reference a MP article, or when a mp.weixin.qq URL appears in conversation.

这段信息会被注入成类似这样的 system prompt 片段（Cursor 真实行为的简化版）：

  *   *   *   *   *   *   *

    <available_skills><agent_skill fullPath="/path/to/mp-read/SKILL.md">  Extract plain text from Tencent MP (mp.weixin.qq) articles using a headless  Chrome browser. Use when the user wants to read, fetch, extract, summarize,  or reference a MP article, or when a mp.weixin.qq URL appears in conversation.</agent_skill></available_skills>

注意：此时 SKILL.md 的正文还没有被读取。这就是 Cursor 文档里说的 "Progressive Loading"——只先放名字和描述，不浪费 token。

# 05

## 第 1 步：用户发问，触发 Skill

假设用户发了一句：

> 帮我读一下这篇公众号文章：https://mp.weixin.qq.com/s/HHPK6QvclYaxlDg28elN8w

此时 Cursor 作为客户端，构造出的第一次 API 请求大致如下（简化但忠实于 OpenAI 协议）：

  *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *

    {  "model": "claude-4.6-opus",  "messages": [    {      "role": "system",      "content": "You are an AI coding assistant...\n\n<available_skills>\n<agent_skill fullPath=\"/Users/123456/.../mp-read/SKILL.md\">\n  Extract plain text from Tencent MP (mp.weixin.qq) articles...\n</agent_skill>\n</available_skills>\n\nWhen a skill is relevant, read and follow it IMMEDIATELY as your first action..."    },    {      "role": "user",      "content": "帮我读一下这篇公众号文章：https://mp.weixin.qq.com/s/HHPK6QvclYaxlDg28elN8w"    }  ],  "tools": [    {      "type": "function",      "function": {        "name": "Read",        "description": "Reads a file from the local filesystem...",        "parameters": {          "type": "object",          "properties": {            "path": { "type": "string", "description": "The absolute path of the file to read." },            "offset": { "type": "integer" },            "limit": { "type": "integer" }          },          "required": ["path"]        }      }    },    {      "type": "function",      "function": {        "name": "Shell",        "description": "Executes a given command in a shell session...",        "parameters": {          "type": "object",          "properties": {            "command": { "type": "string" },            "description": { "type": "string" },            "working_directory": { "type": "string" },            "block_until_ms": { "type": "number" }          },          "required": ["command"]        }      }    }  ],  "tool_choice": "auto"}

关键点：

  * tools 数组是 Cursor 预定义好的，不是 Skill 定义的。Skill 本身不声明工具——它只是告诉 LLM "你可以用 Read 来读文件，用 Shell 来执行命令"。

  * system prompt 里有 Skill 的描述摘要和一条关键指令："When a skill is relevant, read and follow it IMMEDIATELY"

# 06

## 第 2 步：LLM 响应 — 决定先读 SKILL.md

LLM 看到用户提到了 mp.weixin.qq，匹配到了 system prompt 中 mp-read skill 的描述，于是按照指令"先读 Skill 文件"。它返回的响应是：

  *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *

    {  "choices": [    {      "message": {        "role": "assistant",        "content": null,        "tool_calls": [          {            "id": "call_abc123",            "type": "function",            "function": {              "name": "Read",              "arguments": "{\"path\": \"/path/to/mp-read/SKILL.md\"}"            }          }        ]      },      "finish_reason": "tool_calls"    }  ]}

这就是 Skill 的"加载"——本质上就是 LLM 自己发起了一次 Read tool call，读取 SKILL.md 文件。

# 07

## 第 3 步：Cursor 执行 tool call，返回结果

Cursor 在本地执行 Read("/Users/123456/.../mp-read/SKILL.md")，拿到文件内容，然后构造下一轮请求：

  *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *

    {  "messages": [    { "role": "system", "content": "（同上，省略）" },    { "role": "user", "content": "帮我读一下这篇这篇公众号文章：https://mp.weixin.qq.com/s/HHPK6QvclYaxlDg28elN8w" },    {      "role": "assistant",      "content": null,      "tool_calls": [        {          "id": "call_abc123",          "type": "function",          "function": {            "name": "Read",            "arguments": "{\"path\": \"/Users/123456/.../mp-read/SKILL.md\"}"          }        }      ]    },    {      "role": "tool",      "tool_call_id": "call_abc123",      "content": "---\nname: mp-read\ndescription: >-\n  Extract plain text from MP...\n---\n'\n```\n\n（...完整 SKILL.md 内容...）"    }  ],  "tools": [ "（同上，Shell、Read 等工具定义）" ]}

到这一步，SKILL.md 的全部内容已经通过 role: "tool" 消息进入了 LLM 的上下文窗口。 LLM 现在拥有了完整的"技能说明书"。

# 08

## 第 4 步：LLM 按照 Skill 指令行动 — 前置检查

LLM 读完 SKILL.md 后，按照 "Prerequisites Check" 章节的指示（章节中要求用户必须实现准备好一个 cookie.txt 文件），先检查环境。它返回：

  *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *

    {  "choices": [    {      "message": {        "role": "assistant",        "content": null,        "tool_calls": [          {            "id": "call_def456",            "type": "function",            "function": {              "name": "Shell",              "arguments": "{\"command\": \"which mp-read\", \"description\": \"Check mp-read is installed\"}"            }          },          {            "id": "call_ghi789",            "type": "function",            "function": {              "name": "Read",              "arguments": "{\"path\": \".../cookie.txt\"}"            }          }        ]      },      "finish_reason": "tool_calls"    }  ]}

注意这里 一次返回了两个 tool_calls——这是 OpenAI 协议支持的并行 tool calling。LLM 判断这两个检查互相独立，所以同时发起。

# 09

## 第 5 步：工具结果回传

Cursor 并行执行两个 tool call，然后把结果都塞进 messages：

  *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *

    {  "messages": [    "（...之前的所有消息...）",    {      "role": "assistant",      "tool_calls": [        { "id": "call_def456", "function": { "name": "Shell", "arguments": "..." } },        { "id": "call_ghi789", "function": { "name": "Read", "arguments": "..." } }      ]    },    {      "role": "tool",      "tool_call_id": "call_def456",      "content": "/usr/local/go/bin/mp-read"    },    {      "role": "tool",      "tool_call_id": "call_ghi789",      "content": "skey=xxxxxxx; p_skey=yyyyyyy; RIO_TCOA=zzzzzz..."    }  ]}

# 10

## 第 6 步：LLM 执行核心命令

前置检查通过，LLM 按照 SKILL.md 中的 Usage 章节，构造并发起实际的 mp-read 命令：

  *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *

    {  "choices": [    {      "message": {        "role": "assistant",        "content": null,        "tool_calls": [          {            "id": "call_jkl012",            "type": "function",            "function": {              "name": "Shell",              "arguments": "{\"command\": \"mp-read 2026/0316_mp_read/cookie.txt 'https://mp.weixin.qq.com/s/HHPK6QvclYaxlDg28elN8w'\", \"description\": \"Extract MP article text\", \"block_until_ms\": 120000}"            }          }        ]      },      "finish_reason": "tool_calls"    }  ]}

注意 block_until_ms: 120000——这正是 SKILL.md 中明确要求的。LLM 从 Skill 文档中"学到"了这个参数应该设多大。

# 11

## 第 7 步：最终响应

Shell 执行完毕，mp-read 的 stdout 输出（文章全文）通过 role: "tool" 消息回传给 LLM。LLM 最终生成一个 role: "assistant" 的纯文本响应，把文章内容整理后呈现给用户：

  *   *   *   *   *   *   *   *   *   *   *   *

    {  "choices": [    {      "message": {        "role": "assistant",        "content": "这篇公众号文章的内容如下：\n\n# 文章标题\n\n文章正文内容...",        "tool_calls": null      },      "finish_reason": "stop"    }  ]}

# 12

## 全 景图： 从协议视角看 Skill 生命周期

把上面 7 步画成一张协议交互时序图：

  *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *

                    Cursor (客户端)                              LLM (服务端)                     │                                          │   ┌─────────────────┤                                          │   │ 启动时扫描 skill │                                          │   │ 目录，提取 name  │                                          │   │ + description   │                                          │   └────────┬────────┘                                          │            │                                                   │   Round 1  │  POST /chat/completions                           │            │  system: "...skills摘要..." + tools: [Shell,Read] │            │  user: "帮我读一下 https://mp.weixin.qq.com/s/HHPK6QvclYaxlDg28elN8w"     │            │ ─────────────────────────────────────────────────> │            │                                                   │            │  assistant.tool_calls: Read(SKILL.md)             │            │ <───────────────────────────────────────────────── │            │                                                   │   ┌────────┤  执行: Read(SKILL.md)                              │   └────────┤                                                   │            │                                                   │   Round 2  │  tool: (SKILL.md 完整内容)                          │            │ ─────────────────────────────────────────────────> │            │                                                   │  ← LLM 现在 "学会" 了这个 Skill            │  assistant.tool_calls:                             │            │    Shell("which mp-read")                         │            │    Read(cookie.txt)                                │            │ <───────────────────────────────────────────────── │            │                                                   │   ┌────────┤  并行执行两个 tool call                              │   └────────┤                                                   │            │                                                   │   Round 3  │  tool: "/usr/local/go/bin/mp-read"                │            │  tool: "skey=xxx;p_skey=yyy..."                   │            │ ─────────────────────────────────────────────────> │            │                                                   │            │  assistant.tool_calls:                             │            │    Shell("mp-read cookie.txt 'URL'",              │            │           block_until_ms=120000)                   │            │ <───────────────────────────────────────────────── │            │                                                   │   ┌────────┤  执行: mp-read（耗时 ~30s）                          │   └────────┤                                                   │            │                                                   │   Round 4  │  tool: (文章全文)                                   │            │ ─────────────────────────────────────────────────> │            │                                                   │            │  assistant.content: "这篇文章的内容如下：..."         │            │  finish_reason: "stop"                             │            │ <───────────────────────────────────────────────── │            ▼                                                   ▼

# 13

## 总结：Skill 的协议映射表

Skill 概念| 协议映射
---|---
Skill 发现（scan directories）| 纯客户端行为，不涉及协议
Skill 摘要（name + description）| 注入到 `messages[0].role = "system"` 的文本中
Skill 加载（读取 SKILL.md）| LLM 发起 `tool_calls: [Read(SKILL.md)]`，结果通过 `role: "tool"` 回传
Skill 指令执行| LLM 按读到的 SKILL.md 内容，自主发起后续 `tool_calls`
Skill 的 "Progressive Loading"| 先在 system prompt 放摘要（省 token），LLM 需要时再 Read 全文
Skill 的 "scripts/" 目录| LLM 通过 Shell tool call 执行脚本
Skill 的 "references/" 目录| LLM 通过 Read tool call 按需读取参考文档

核心洞察：Skill 在协议层面完全不存在。它是一种"给 LLM 写使用手册，让 LLM 通过已有工具自己照着做"的设计模式。 整个过程就是：

  1. 在 system prompt 里告诉 LLM "你有这些技能手册可以查"

  2. LLM 通过 Read 工具自己去读手册

  3. LLM 读完手册后，按手册说的步骤，通过 Shell/Read 等工具一步步执行

这种设计的精妙之处在于：它完全复用了 OpenAI 协议已有的 tool calling 机制，不需要任何协议扩展。 Skill 的全部"魔法"都发生在 system prompt 的措辞和 SKILL.md 文件的编写质量上——本质上是一种 prompt engineering + 文件系统的组合。

一个简简单单的对话功能，人类真的是能够玩出花来，语言不愧是高智慧的人类区别于动物的一个重要特征呀！

## -End-

## 原创作者｜张敏

感谢你读到这里，不如关注一下？👇

![图片](assets/9c8c2a04d192.webp)📢📢来抢开发者限席名额！点击下方图片直达👇[![图片](assets/f63214ad8e9f.jpg)](<>)
![图片](assets/c5f4ff4b771e.webp)你对本文内容有哪些看法？同意、反对、困惑的地方是？欢迎留言，我们将邀请作者针对性回复你的评论，欢迎评论留言补充。我们将选取1则优质的评论，送出腾讯云定制文件袋套装1个（见下图）。6月4日中午12点开奖。
![图片](assets/92264cc9b7df.webp)
扫码领取腾讯云开发者专属服务器代金券！![图片](assets/f8561d96ee33.webp)
![图片](assets/b8ca41651a38.webp)[![图片](assets/160edc269f51.webp)](<https://mp.weixin.qq.com/s?__biz=MzI2NDU4OTExOQ==&mid=2247694196&idx=1&sn=151b34f31e6a5cdfe4cc8600668b57cb&scene=21#wechat_redirect>)[![图片](assets/259caf81fc97.webp)](<https://mp.weixin.qq.com/s?__biz=MzI2NDU4OTExOQ==&mid=2247694634&idx=1&sn=1cc86d5e6ac59df5b73303e1f1a4a8f6&scene=21#wechat_redirect>)[![图片](assets/a0d435580892.webp)](<https://mp.weixin.qq.com/s?__biz=MzI2NDU4OTExOQ==&mid=2247694641&idx=1&sn=dff67991264624bf2e7615bd637f4cf6&scene=21#wechat_redirect>)
![图片](assets/7d956dd1ee8f.webp)
