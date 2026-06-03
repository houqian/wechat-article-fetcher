# 拆完Hermes源码，我发现Agent的"自我进化"根本不需要训练模型

> **公众号**: 腾讯云开发者  
> **发布时间**: 2026-05-12 08:45  

## 关注腾讯云开发者，一手技术干货提前解锁👇

注：本文有使用 AI 进行辅助写作，特此说明。

两个月 5.2 万 Star，Hermes Agent 用一个"LLM 审判官"机制实现了 Agent 的自我进化——不改模型权重，只改"怎么用模型"的策略。我逐行读完源码后发现：所谓的"自动学习"，本质是 Prompt Engineering + 文件持久化的一次精妙工程化实践。本文从源码层面拆解它的三大核心机制，并与 OpenClaw 做一次硬核对比。

引言：Agent 赛道杀出一匹"爱马仕"

2026 年 2 月，Nous Research 悄悄开源了一个项目——Hermes Agent。

没有铺天盖地的发布会，没有大佬站台背书，只有 GitHub 上一句简洁的 Slogan："The agent that grows with you."

两个月后，它的 Star 数突破了 5.2 万，日均增长超过 800，多次霸榜 GitHub Trending 全球第一。社区里开始出现一种声音："换掉 OpenClaw 太爽了。"

这让我很好奇——在 OpenClaw 已经拿下 30 万+ Star、Claude Code 和 Codex 打得不可开交的 2026 年，一个新框架凭什么能杀出重围？

于是我做了一件事：逐行读完了 Hermes Agent 的核心源码。

读完之后，我的结论是：Hermes Agent 的核心创新不在于"它能做什么"，而在于"它做完之后会发生什么"。

# 01

## 一个根本性的分歧——做完就走 vs 越用越强

要理解 Hermes Agent 的设计哲学，最好的方式是把它和 OpenClaw 放在一起看。

1.1 OpenClaw：全能管家，但记忆像金鱼

OpenClaw（社区昵称"龙虾"🦞）是 2025-2026 年最火的开源 Agent 框架，30 万+ Star，插件市场 ClawHub 里有数千个插件，能接入 Telegram、WhatsApp、Slack、飞书、企业微信——几乎是一个"个人 AI 操作系统"。

但它有一个根本性的问题：无状态。

每次任务独立执行，做完即结束。除非你手动配置 `AGENTS.md` 、SOUL.md、USER.md 等四层配置文件，否则它不会记住上次的偏好。你今天教它"我喜欢简洁的代码风格"，明天它就忘了。

更关键的是——即使你在一次复杂任务中摸索出了一套高效的工作流，OpenClaw 也不会自动把这个经验保存下来。你必须手动告诉它："帮我把刚才的流程总结成一个 Skill。"

1.2 Hermes Agent：不那么全能，但会"长记性"

Hermes Agent 的定位完全不同。它不追求"什么都能做"，而是追求"做过的事情，下次做得更好"。

用一张表来对比：

维度| OpenClaw 🦞| Hermes Agent ☤
---|---|---
**核心哲学**|  全能助手，插件生态| 自我进化，越用越强
**记忆能力**|  无状态（需手动配置）| 四维持久记忆（自动）
**技能管理**|  用户手动安装/编写 Skill| Agent 自动从经验中创建 Skill
**学习方式**|  不学习| 内置闭环学习系统
**插件生态**|  数千个（ClawHub）| 较少，但在快速增长
**部署门槛**|  中等| 极低（5 美元 VPS）
**适合场景**|  一次性任务、多平台集成| 长期使用、个性化需求

一句话总结：OpenClaw 是一个"什么都能干但不长记性的全能管家"，Hermes Agent 是一个"能力在成长的专属员工"。

# 02

## 源码拆解——"自我进化"到底是怎么实现的？

这是全文最硬核的部分。我从 Hermes Agent 的源码中提炼出三大核心机制，逐一拆解。

2.1 四维持久记忆系统

Hermes Agent 的记忆不是一个扁平的文本文件，而是一个四维系统：

  *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *

    ┌─────────────────────────────────────────────┐│              Hermes 记忆架构                 │├─────────────────────────────────────────────┤│                                             ││  📋 身份记忆 (IDENTITY)                      ││  └─ Agent 的角色定义、行为准则                ││                                             ││  📝 Agent 笔记 (MEMORY.md)                  ││  └─ 用户偏好、项目上下文、经验教训              ││                                             ││  ⚡ 程序性记忆 (SKILL.md)                    ││  └─ 可复用的工作流程、操作步骤                 ││                                             ││  💬 对话历史 (Conversation History)         ││  └─ 当前会话的完整上下文                      ││                                             │└─────────────────────────────────────────────┘

源码中，记忆的读写通过 memory_tool.py 实现。关键设计是"冻结快照"模式——每次会话开始时，系统提示词会加载当前的 MEMORY.md 和 SKILL.md 内容作为快照。会话过程中即使后台更新了这些文件，当前会话看到的仍然是开始时的版本。

为什么这么设计？因为如果记忆在会话中途被修改，模型可能会产生混乱——它的系统提示词和实际文件内容不一致了。冻结快照保证了单次会话内的一致性。

2.2 技能自动创造系统

这是 Hermes Agent 最核心的创新。

在传统 Agent（包括 OpenClaw）中，Skill 的生命周期是这样的：

  *   *   *

    用户编写 Skill → 安装到 Agent → Agent 执行 → 结束                                    ↑                          （用户手动说"更新 Skill"才会触发）

在 Hermes Agent 中，Skill 的生命周期变成了：

  *   *   *

    Agent 执行任务 → 后台自动审查 → 判断是否有价值 → 自动创建/更新 Skill                                                        ↓                                              下次会话自动加载

源码中，技能管理通过 skill_manager_tool.py 实现，提供三个核心操作：

  * create：从零创建一个新 Skill

  * patch：精准更新已有 Skill 的某个部分

  * delete：删除不再需要的 Skill

每个 Skill 本质上就是一个 Markdown 文件（SKILL.md），内容是自然语言描述的工作流程。比如：

  *   *   *   *   *   *   *   *   *   *   *   *   *   *

    # 数据爬取与分析 Skill
    ## 触发条件用户要求爬取网页数据并进行分析
    ## 执行步骤1. 先确认目标 URL 的 robots.txt 协议2. 使用 web_search 工具获取页面内容3. 提取关键数据点，按用户要求的格式整理4. 如果数据量大，分批处理并汇总
    ## 注意事项- 用户偏好 Markdown 表格格式输出- 每批次不超过 20 条数据

没有代码，没有 API 调用，纯自然语言。 这意味着 Skill 的创建和修改完全不需要编程能力——LLM 自己就能读懂、写出、修改这些 Skill。

2.3 KEPA：对"提示"做反向传播

这是 Hermes Agent 最精妙的设计，也是"自我进化"的核心引擎。

社区把这个机制称为 KEPA（Knowledge-Enhanced Prompt Adaptation），我更喜欢用一个类比来解释它：

传统深度学习：

  *   *

    前向传播：输入 → 模型 → 输出反向传播：根据损失函数，更新模型权重

Hermes 的做法：

  *   *

    前向传播：用户意图 → Hermes（LLM + 工具）→ 执行结果反向传播：周期性回顾执行过程 → 检测失败点 → 更新 Skill/记忆

关键差异：不是更新"模型权重"，而是更新"如何使用模型"的策略——包括提示模板、工具调用顺序、技能定义等。

在源码中，这个机制的实现出奇地简洁。核心在 run_agent.py 的 _spawn_background_review 函数：

  *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *   *

    # 伪代码还原核心逻辑class BackgroundReview:    def __init__(self):        self.tool_call_counter = 0        self.threshold = 10  # 每 10 次工具调用触发一次
        def on_tool_call(self):        self.tool_call_counter += 1        if self.tool_call_counter >= self.threshold:            self.tool_call_counter = 0            self._spawn_review()  # 启动后台审查
        def _spawn_review(self):        # 在后台线程中运行，不阻塞主 Agent        review_agent = create_agent(            system_prompt=SKILL_REVIEW_PROMPT,            tools=[skill_manager, memory_tool],            max_iterations=8  # 最多 8 次工具调用        )        # 把当前对话历史喂给审查 Agent        review_agent.run(conversation_history)

审查 Agent 收到的 Prompt（_SKILL_REVIEW_PROMPT）大意是：

> ## "你是一个经验审查员。请回顾刚才的对话历史，判断：
>
> ## 1\. 任务过程中是否有 试错 或 中途改变策略 ？
>
> ## 2\. 最终方案是否具有 可复用性 ？
>
> 3\. 如果值得保存，请调用 skill_manager 创建或更新 Skill。
>
> ## 4\. 如果不值得保存，请回复 'Nothing to save.'"

整个"自我进化"的核心，就是这么一段 Prompt + 一个后台线程 + 文件持久化。

没有强化学习，没有模型微调，没有向量数据库——纯粹的 Prompt Engineering + 文件系统。

# 03

## 这个设计到底强在哪？弱在哪？

✅ 强在哪

**1.** 零成本进化

传统的 Agent 学习需要收集数据、标注、微调模型——成本高、周期长。Hermes 的方式几乎零额外成本：审查 Agent 的 Token 消耗很小（最多 8 次工具调用），Skill 文件就是普通的 Markdown 文本。

2\. 可解释、可编辑

因为 Skill 是自然语言写的 Markdown 文件，你可以随时打开看看 Agent 学到了什么，觉得不对可以直接手动修改。这比黑箱的模型微调透明得多。

3\. 跨模型迁移

Skill 不依赖特定模型。你今天用 GPT-4o 积累的 Skill，明天换成 Claude 或 DeepSeek 一样能用——因为它们都是自然语言。

4\. 渐进式积累

每次使用都在积累经验，Skill 库会越来越丰富。用三个月后的 Hermes 和刚装好的 Hermes，体验完全不同。

⚠️ 弱在哪

### 1\. "自动"不等于"准确"

审查 Agent 的判断力上限就是底层 LLM 的能力上限。它可能：

  * 保存了不重要的经验（噪声）

  * 遗漏了你认为重要的经验（漏判）

  * 写的 Skill 质量参差不齐

**
**

### 2\. 只有"复杂任务"才会触发

审查 Prompt 明确要求：只有涉及"试错"或"中途改变策略"的任务才值得保存。如果你的任务很简单、一步到位，Hermes 大概率会判断 "Nothing to save." 然后跳过。

场景| 会自动保存吗？
---|---
复杂爬虫任务，试了 3 种方案才成功| ✅ 大概率会
只是改了一个输出格式| ❌ 大概率不会
Skill 有 bug，调试了好几轮| ✅ 大概率会
传了不同参数，正常执行| ❌ 大概率不会

**
**

### 3\. 更新有延迟

由于冻结快照机制，后台更新的 Skill 要到**下一次会话** 才会生效。当前会话感知不到变化。

### 4\. 生态差距明显

OpenClaw 有 ClawHub 数千个插件，Hermes 的第三方生态还在早期。如果你需要大量现成的集成能力，OpenClaw 目前仍然是更好的选择。

# 04

## 一个更深层的思考——Agent 的"学习"该由谁驱动？

拆完源码后，我一直在想一个问题：

> ## Agent 的学习，到底应该是"用户驱动"还是"Agent 自驱动"？

OpenClaw 代表的是用户驱动模式：你想让 Agent 学什么，就手动写什么。SOUL.md 定义人格，AGENTS.md 定义工作流，USER.md 定义偏好——一切都在你的掌控之中。

Hermes Agent 代表的是Agent 自驱动模式：Agent 自己决定学什么、怎么学。你只管用，它在后台默默积累经验。

两种模式各有优劣：

  *   *   *   *   *   *   *   *   *   *   *

    用户驱动（OpenClaw）├── ✅ 精确可控：你写什么它就学什么├── ✅ 无噪声：不会学到无用的东西├── ❌ 成本高：需要用户持续投入精力└── ❌ 容易遗漏：你忘了说的，它就不会学
    Agent 自驱动（Hermes）├── ✅ 零维护：自动积累，无需用户操心├── ✅ 兜底能力：你忘了说的，它可能帮你记住├── ❌ 有噪声：可能学到不重要的东西└── ❌ 不可控：你不知道它什么时候会学、学了什么

我的观点是：最理想的方案是两者结合。

  * 核心的、确定性的知识（如项目规范、个人偏好），应该由用户显式定义——就像 OpenClaw 的 SOUL.md

  * 隐性的、经验性的知识（如"这个 API 容易超时，最好加重试"），应该由 Agent 自动积累——就像 Hermes 的 KEPA

事实上，Hermes Agent 也支持用户手动编辑 Skill 和 Memory。它的"自动进化"是一个兜底机制，而不是唯一的学习途径。

# 05

## 选 OpenClaw 还是 Hermes？一张决策表

如果你是...| 选 OpenClaw 🦞| 选 Hermes ☤
---|---|---
需要接入多个通讯平台（Telegram/Slack/飞书）| ✅| ⚠️ 支持但生态较弱
需要大量现成插件| ✅| ❌
追求数据完全本地化| ✅| ✅
长期使用同一个 Agent，希望它越来越懂你| ❌| ✅
经常做重复性但有微调的任务| ❌| ✅
团队协作，需要统一的 Agent 配置| ✅| ⚠️
预算极低（5 美元/月）| ⚠️| ✅
想要 Agent 自动积累工作经验| ❌| ✅

我的建议：如果你是"用完即走"型用户，选 OpenClaw；如果你是"长期陪伴"型用户，选 Hermes。

当然，两者并不互斥。你完全可以用 OpenClaw 做多平台集成和一次性任务，用 Hermes 做需要长期积累的个人助手。

# 06

## 结语 ：Agent 的未来，是"会长大的软件"

回顾整篇文章，Hermes Agent 给我最大的启发不是某个具体的技术实现，而是一个理念的转变：

> **传统软件是静态的——你装好什么样，它就是什么样。** **Hermes 代表的新范式是动态的——软件会随着使用而成长。**

这让我想起 Andrej Karpathy 说的那句话：

> "The hottest new programming paradigm is English."

Hermes Agent 把这句话推进了一步：**不仅编程语言变成了英语，连"学习"的载体也变成了英语。** Skill 是英语写的，Memory 是英语写的，审查 Prompt 也是英语写的。整个"进化"过程，没有一行传统意义上的"训练代码"。

这是一个值得所有 Agent 开发者思考的方向：**也许我们不需要微调模型，只需要让 Agent 学会"记笔记"。**

**
**

当然，Hermes Agent 目前还很年轻——两个月的项目，生态、稳定性、企业级特性都还在完善中。但它提出的"自我进化"范式，已经在 5.2 万 Star 的社区验证中得到了初步认可。

最后，用 Hermes Agent 的 Slogan 结束这篇文章：

> ## "The agent that grows with you."

不是"为你工作的 Agent"，而是"和你一起成长的 Agent"。

这个微妙的措辞差异，也许就是 Hermes 和所有传统 Agent 最本质的区别。

* * *

参考来源：

  1. NousResearch/hermes-agent，GitHub，https://github.com/NousResearch/hermes-agent

  2. 《会自我进化的AI有多强？深度拆解Hermes Agent三层机制》，今日头条，2026-04-10

  3. 《两个月 4.7 万星，爆火的 Hermes Agent 是下一个龙虾，还是另一个故事？》，搜狐，2026-04-10

  4. 《Hermes Agent vs OpenClaw：2026年两大AI Agent框架深度对比》，CSDN，2026-04-11

  5. 《深度解析 Hermes Agent：用"提示反向传播"打造可自我进化的 AI 智能体》，CSDN，2026-04-07

  6. 《狂揽4万星！换掉OpenClaw太爽了，5美元就能养个AI打工人》，新智元，2026-04-09

  7. 《Hermes Agent vs OpenClaw：52k Star 背后，谁才是 2026 最强 AI 智能体框架》，腾讯新闻，2026-04-11

  8. 《"同事.skill"不用写了，爱马仕 Hermes 主动"蒸馏"你》，腾讯新闻，2026-04-11

## -End-

## 原创作者｜ 刘庭辉

## 感谢你读到这里，不如关注一下？ 👇

![图片](assets/9c8c2a04d192.webp)📢📢来抢开发者限席名额！点击下方图片直达👇[![图片](assets/cabcc1760529.jpg)](<>)

![图片](assets/c5f4ff4b771e.webp)你对本文内容有哪些看法？同意、反对、困惑的地方是？欢迎留言，我们将邀请作者针对性回复你的评论，欢迎评论留言补充。我们将选取1则优质的评论，送出腾讯云定制文件袋套装1个（见下图）。5月19日中午12点开奖。
![图片](assets/92264cc9b7df.webp)
扫码领取腾讯云开发者专属服务器代金券！![图片](assets/f8561d96ee33.webp)
![图片](assets/b8ca41651a38.webp)[![图片](assets/160edc269f51.webp)](<https://mp.weixin.qq.com/s?__biz=MzI2NDU4OTExOQ==&mid=2247694196&idx=1&sn=151b34f31e6a5cdfe4cc8600668b57cb&scene=21#wechat_redirect>)[![图片](assets/259caf81fc97.webp)](<https://mp.weixin.qq.com/s?__biz=MzI2NDU4OTExOQ==&mid=2247694634&idx=1&sn=1cc86d5e6ac59df5b73303e1f1a4a8f6&scene=21#wechat_redirect>)[![图片](assets/a0d435580892.webp)](<https://mp.weixin.qq.com/s?__biz=MzI2NDU4OTExOQ==&mid=2247694641&idx=1&sn=dff67991264624bf2e7615bd637f4cf6&scene=21#wechat_redirect>)
![图片](assets/7d956dd1ee8f.webp)
