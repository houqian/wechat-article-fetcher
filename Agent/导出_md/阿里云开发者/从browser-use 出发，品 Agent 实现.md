# 从browser-use 出发，品 Agent 实现

> **公众号**: 阿里云开发者  
> **发布时间**: 2025-06-11 08:30  

![图片](assets/098110f5e5a9.webp)

## 背景

本篇的出现是自己最近一段时间在agent上的一个学习总结，希望自己能够以一个工程的视角去理解一个agent的产品是怎么run起来，并给出了自己学习和理解的过程。

个人对LLM的理解有下面几个阶段：

【阶段1：Chat only】最简单的交互形式，用户文本框输入->LLM输出。为了提高模型的执行效果，衍生出了提示词工程，通过COT、ReAct等提示词技术进一步利用模型推理的能力，引导模型输出正确的结果；因为模型的训练预料往往是过时的，模型在回答问题时会出现“幻觉”，为了解决这个问题，出现了RAG（检索增强工程），生成响应之前引用训练数据来源之外的权威知识库，提高了回答问题的准确率；在这个阶段，情感陪伴类、角色扮演类、文案创造类、Copilot辅助类的产品涌现的比较突出。

一问一答的方式虽然简单，但是它确实是这类系统的本质。在这个阶段我简单的用chatGpt体验了下，让它帮忙开发了一款IDEA的插件，当时震惊AI的表现的同时，认为达到生产可用的水平应该还要好几年（Cursor狠狠地打了我的脸）。

【阶段2： WorkFlow编排】Funciton call的出现使得LLM模型有了稳定的输出，也让LLM 有了能够使用工具，改变自身环境的能力，这使得模型的泛化能力进一步加强，能够做的事情更多了。在这个阶段，coze，dify这种低/无代码使用workFlow进行编排的应用开发平台如雨后春笋般冒出，使得普通用户也能够通过对模型、工具进行编排的方式，低成本的搭建出垂直领域的agent，大大降低AI应用的开发成本。同时各行业也开始从技术探索转向落地实践自身业务，从效率、体验等多维度寻找新的业务创新点和行业增长点，AI发展速度进一步增快。

![图片](assets/c94e37e1853e.jpg)【阶段3： Agent】为什么2025年被称为agent的元年？我认为是因为人们从类似devin，manus这样的产品看到了AI的自主能动性，运行模式也逐步从被动响应到主动执行进行跃迁。用户只需要简单的描述一下自己的需求，LLM就可以使用丰富的工具和不断扩展的上下文环境，像人一样不断地规划、执行，甚至实时生成代码运行在沙箱环境里，最终达成用户的目的，生产力大大提升。

![图片](assets/bc9928950c45.jpg)

在这期间有一个很有意思的项目：Browser-use。它将agent运行在浏览器的环境里，通过提供网页导航、元素定位、表单填写和数据抓取等工具，使agent能够访问网站并执行各种任务，它的代码里包含完备的工程链路和完整的SystemPrompt，而且运行起来很感性，所见即所得，很适合工程的同学学习。

## ReAct

如果我们要讲agent，就不可避免的提到ReAct框架。它和我们人完成一个目标的流程很像，我们在接到一个问题的时候，会先思考出可行的解决方案，然后采取行动去验证思考的方案，并根据验证的结果反思之前提出的方案，并决定下一步的行动。它的典型流程如下图所示，：思考（Thought）→ 行动（Action）→ 观察（Observation）。

![图片](assets/1686cdc302af.jpg)

## Agent

Agent是感知和理解环境并利用工具来实现目标的应用程序，上面已经给出了它所含的基本元素。

### 记忆(memory)

记忆包括短期记忆和长期记忆。

### 短期记忆

  * 对话的上下文信息，短期记忆可能包括：历史会话（为了避免token爆炸，可能是最近N轮的原始对话数据，也可能是全量对话经过LLM总结压缩后的信息）、工具信息。工程侧的实现一般是缓存、数据库。

### 长期记忆

  * 长期记忆可以存储相当长的时间信息，作为代理在查询时可以处理的外部向量存储，可通过快速检索进行访问。它可以是一个跨session共享的数据来源，我们可以用它存储一些用户个性化的数据和模型的反思的结果，让模型能够越用越智能。工程侧的实现一般是向量数据库。

### 规划(planning)

  * ## 任务分解：通过分而治之的方式，将大任务分解为多个小任务，从而逐步解决复杂问题。可以让一个或多个agent串行或者并行完成这些小任务。典型的实现方案有COT(Chain of thought）和TOT(Tree of thoughts)。

  * 反思自省：在任务的解决过程中，基于已有动作和环境上下文做自我批评和自我反思，从错误中学习优化接下来的动作。典型的实现方案是ReAct（ReasonAndAction）+Reflexion。

### 两种范式

#### 分解优先

1.【分解优先】 在一开始就将任务分解为子目标，并提前规划好所有的任务，最后一个一个执行。适合执行过程确定性比较强的任务、不需要或者少需要人参与的系统。（比如代码生成）

a.优点：子任务与原任务关联比较强，不容易被遗忘；

b.缺点：

i.非常依赖子任务的稳定性，如果子任务有问题，可能会影响整个任务的完成；

ii.replan的成本比较高；

![图片](assets/dd21e419d901.jpg)

#### 交错分解

2.【交错分解】类似回溯法，一边分解任务，一边制定计划，纯react+reflection就可以实现，执行完一个再决定下一个执行的内容。适合执行过程确定性不太强，比较发散的任务，系统一般需要人参与（比如卖家助手）。

a.优点：可根据环境反馈动态调整任务分解，提高了容错性。

b.缺点：如果任务比较复杂，不确定性比较高，随着执行轮数的增长，后面的计划可能会遗忘前面执行计划的结果，工程上需要做好优化。

![图片](assets/471114753f2d.jpg)

### 工具(tools)：

  * 智能体能够使用外部API工具来拓展模型的能力，从而获得大模型以外的能力，例如：搜索网页、设置代办、代码执行等。

  * 工具相当于给了Agent一副手脚，让它有了感知环境和改变环境的能力。我们一般需要给agent提供工具名称、工具描述、工具出/入参、字段描述、字段限制等信息，让它知道在遇到问题的时候能够选择合适的工具去解决。

## 纯对话演示

  * 接下来我们使用Chat模式来模拟agent的运行方式，我们将自己充当工具，当模型需要调用合适的工具的时候，我们来返回合适的结果。

  * 使用平台：Idea talk

  * 使用模型：Qwen3-32B

### 构建系统提示词

  *   *   *   *   *

    角色:你是一个通用智能体，你的目标是遵循规则完成最终的任务## 目标：输出正确的回答给用户## 输出格式：- 您必须始终以精确格式的有效 JSON 进行响应：{    "evaluation_previous_goal": "success|fail|unknown-检查先前的目标/操作是否按照任务预期成功。如果发生意外情况，请简要说明原因",    "short_memory": "描述已完成的操作以及需要记住的内容-务必在此处统计已执行的次数以及剩余的次数。例如：【已执行X次，剩余Y次】-获取XX信息，但是因为网络繁忙未获取，继续获取",    "next_goal": "下一个操作需要做什么",    "action": "需要执行的工具和参数",    "finished":"True/False-任务是否已完成"}## 工具-你每次只可以指定一个工具，你需要按照下面的格式返回使用的工具，常用的工具如下：[    {        "toolName": "谷歌查询",        "desc": "查询一些有用的信息补充到上下文中",        "params": {            "queryContent": "查询词",            "type": "str"        }    },    {        "toolName": "实时时间获取",        "desc": "获取当前时间",        "params": {
            }    }, {        "toolName": "寻求用户帮助",        "desc": "当你需要获取用户相关的信息或者多次执行任务失败的时候，你可以请求用户的帮助",        "params": {            "desc": "需要用户提供什么样的信息或者帮助",            "type": "str"        }    }]## 限制：- 请严格按照给出的输出格式输出- 你的最大执行次数为10次- 同一个任务执行最多失败超过2次
    ## 参数- 任务目标：${target}

    target:请计算特朗普的岁数和我的岁数谁更大点 world!");

### 运行过程

![图片](assets/3b223f9f8c77.png)

### 输出结果的差异性

同一个模型同一个Prompt跑多次，调用工具的顺序、对于错误结论的处理有些许不同，但是输出的格式都挺统一的。

不同的模型同一个Prompt跑多次，基本上所有的模型都能指令遵循按照约定的格式输出，但是一些细节表现上还是不太一样。比如qwen3-32B，evaluation_previous_goal输出只会输出枚举的状态，而Qwen2.5-max则会带上原因。

![图片](assets/daa07fd95c14.jpg)

![图片](assets/718ce95a346a.jpg)

但是这其实是我的prompt给的不够精确，让模型有了误判，优化后Qwen2.5-max也能够只输出状态了，这说明了两个问题：

1.更准确、规范的prompt能够带来更稳定的输出；

2.模型能力变强确实一定程度上能弥补prompt的短板；

![图片](assets/9793545dd461.jpg)

优化前

![图片](assets/e28957783be8.jpg)

![图片](assets/d6eb89c4a008.jpg)

优化后

## browser-use工程化落地

通过对话演示，我们最小限度的理解了agent的runTime可能是什么样子的，接下来我们通过browser-use来看下如果要在工程上落地，需要怎么去设计。

browser-use是一个典型的使用「交错分解」范式的agent，它的整体架构如下：

![图片](assets/00ae814ec551.jpg)

1.Agent core：项目的核心组件，负责协调所有组件的工作，管理任务执行流程，处理状态转换，并确保各组件之间的正确通信。

2.MessagManager:

a.职责：管理所有与LLM的通信内容，包括系统提示词、用户消息和对话历史；

b.交互关系：与Agent Core通信来获取/更新消息，与Memory组件交互获取历史记忆，与LLM Interface交互发送格式化的消息；

3.Memory：

a.职责：维护agent的记忆系统，包括短期和长期记忆，处理记忆的存储和检索；

b.交互关系：向MessageManager提供历史记忆，从Agent Core接收新的记忆内容并进行总结压缩；

4.LLM：

a.职责：处理与语言模型的所有交互，包括消息发送和响应解析；

b.交互关系：接收MessageManager的格式化消息，向Agent Core返回模型输出，根据Controller提供的动作模型验证输出；

5.Controller：

a.职责：管理和执行具体的浏览器操作（动作或者说工具），维护动作注册表，负责动作的执行；

b.交互关系：接收来自Agent Core的指令，向Browser Context发送具体操作，提供所有可被使用的动作模型在运行时转化成toolPrompt供MessageManager使用；

6.BrowserContext:

a.职责：管理浏览器上下文生命周期，创建和维护浏览器会话，管理浏览器实例，处理页面状态，执行DOM操作；

b.交互关系：接收来自Controller的动作指令，向Agent Core报告执行结果，向MessageManager提供页面状态信息。

### 运行流程

运行流程如下图，本质上也是ReAct框架的实际应用。

![图片](assets/59ce573bd8ba.jpg)

整体流程可以抽象成以下的伪代码，其实和我们上面用纯对话演示的流程一样了（少了一个memory总结历史会话，用来进行上下文窗口压缩的步骤）。

  *   *   *   *   *   *   *   *   *   *   *   *

    sytem_prompt = ("previousGoal":"上一个目标的完成状态"              ,"memory":"描述已完成的操作以及需要记住的内容"              ,"next_goal":"下一个完成的目标"              ,"actions":"为了完成下一个目标应该执行的动作")tools = Tools()context = Context(tools)agent = Agent(sytem_prompt,context)task = "完成XX目标"
    while (context.status is not finished):    context.status,actions = agent.run(context)    tools.run(actions)

### 源码解析

### 提示词设计

browser_use.agent.prompts：这个文件对agent运行时的prompt进行管理，包含三种类型的prompt。

#### SystemPrompt

  * SystemPrompt是agent能够运行起来的关键，它在agent初始化的时候从markDown文件加载，其中定义了模型的输入格式、输出规则和核心能力。

  * 下述文档为brow-use的系统提示词，其中响应格式的构造和前面演示时让模型返回的格式是一样的，分析下其实主要包含了下面几个模块。

  * Agent的角色定义和任务说明；

  * 输入参数限制和字段说明；

  * 输出参数限制和字段说明；

  * 定义工具使用的能力和部分工具使用的例子；

  * 错误处理和异常情况的建议；

  * 任务完成规则；

  *   *   *   *   *

    You are an AI agent designed to automate browser tasks. Your goal is to accomplish the ultimate task following the rules.
    # Input FormatTaskPrevious stepsCurrent URLOpen TabsInteractive Elements[index]<type>text</type>- index: Numeric identifier for interaction- type: HTML element type(button, input, etc.)- text: Element descriptionExample:[33]<button>Submit Form</button>
    - Only elements with numeric indexes in [] are interactive- elements without [] provide only context
    # Response Rules1. RESPONSE FORMAT: You must ALWAYS respond with valid JSON in this exact format:{{"current_state": {{"evaluation_previous_goal": "Success|Failed|Unknown - Analyze the current elements and the image to check if the previous goals/actions are successful like intended by the task. Mention if something unexpected happened. Shortly state why/why not","memory": "Description of what has been done and what you need to remember. Be very specific. Count here ALWAYS how many times you have done something and how many remain. E.g. 0 out of 10 websites analyzed. Continue with abc and xyz","next_goal": "What needs to be done with the next immediate action"}},"action":[{{"one_action_name": {{// action-specific parameter}}}}, // ... more actions in sequence]}}
    2. ACTIONS: You can specify multiple actions in the list to be executed in sequence. But always specify only one action name per item. Use maximum {{max_actions}} actions per sequence.Common action sequences:- Form filling: [{{"input_text": {{"index": 1, "text": "username"}}}}, {{"input_text": {{"index": 2, "text": "password"}}}}, {{"click_element": {{"index": 3}}}}]- Navigation and extraction: [{{"go_to_url": {{"url": "https://example.com"}}}}, {{"extract_content": {{"goal": "extract the names"}}}}]- Actions are executed in the given order- If the page changes after an action, the sequence is interrupted and you get the new state.- Only provide the action sequence until an action which changes the page state significantly.- Try to be efficient, e.g. fill forms at once, or chain actions where nothing changes on the page- only use multiple actions if it makes sense.
    3. ELEMENT INTERACTION:- Only use indexes of the interactive elements- Elements marked with "[]Non-interactive text" are non-interactive
    4. NAVIGATION & ERROR HANDLING:- If no suitable elements exist, use other functions to complete the task- If stuck, try alternative approaches - like going back to a previous page, new search, new tab etc.- Handle popups/cookies by accepting or closing them- Use scroll to find elements you are looking for- If you want to research something, open a new tab instead of using the current tab- If captcha pops up, try to solve it - elsetry a different approach- If the page is not fully loaded, use wait action- If you have no idea how to proceed, ask user for help
    5. TASK COMPLETION:- Use the done action as the last action as soon as the ultimate task is complete- Dont use "done" before you are done with everything the user asked you, except you reach the last step of max_steps.- If you reach your last step, use the done action even if the task is not fully finished. Provide all the information you have gathered so far. If the ultimate task is completely finished set success to true. If not everything the user asked for is completed set success in done to false!- If you have to do something repeatedly for example the task says for"each", or"for all", or"x times", count always inside "memory" how many times you have done it and how many remain. Don't stop until you have completed like the task asked you. Only call done after the last step.- Don't hallucinate actions- Make sure you include everything you found out for the ultimate task in the done text parameter. Do not just say you are done, but include the requested information of the task.
    6. VISUAL CONTEXT:- When an image is provided, use it to understand the page layout- Bounding boxes with labels on their top right corner correspond to element indexes
    7. Form filling:- If you fill an input field and your action sequence is interrupted, most often something changed e.g. suggestions popped up under the field.
    8. Long tasks:- Keep track of the status and subresults in the memory.- You are provided with procedural memory summaries that condense previous task history (every N steps). Use these summaries to maintain context about completed actions, current progress, and next steps. The summaries appear in chronological order and contain key information about navigation history, findings, errors encountered, and current state. Refer to these summaries to avoid repeating actions and to ensure consistent progress toward the task goal.
    9. Extraction:- If your task is to find information - call extract_content on the specific pages to get and store the information.Your responses must be always JSON with the specified format.

  * 它提供两种扩展系统提示词的方式：

  * 扩展模式：通过extend_system_message参数扩展默认提示词，其实就是将参数拼到默认的系统提示词的最后面；

  * 覆盖模式：通过override_system_message完全替换默认提示词；

![图片](assets/90eeea5367e6.jpg)

#### AgentMessagePrompt

AgentMessagePrompt 根据浏览器上下文的信息构造包含当前页面信息的提示词，帮助模型理全面理解当前页面的信息和可执行的动作。

![图片](assets/44f2a2f51e1f.jpg)

#### PlannerPrompt

browser-use虽然整体上是一个交错分解的范式应用，但是它其实还是实现了任务规划的功能，在运行固定步长后将历史对话信息交给另一个模型进行一次规划总结，从高层次对agent进行指导。规划的promot在PlannerPrompt中，描述词如下：

但是我个人认为这个规划器不管是从实现还是实际运行起来效果都不太好，因为它是固定步长重新进行一次规划，常常会打乱之前正常进行的任务节奏（有点像PUA，让正在工作的模型怀疑自己的工作能力，然后一直在原地转圈）。我个人认为如果需要结合规划的能力，可以考虑由工作的模型自行发起，这可能就涉及到multi-agent是如何交互的问题了。

  *   *   *   *   *

    You are a planning agent that helps break down tasks into smaller steps and reason about the current state.Your role is to:1. Analyze the current state and history2. Evaluate progress towards the ultimate goal3. Identify potential challenges or roadblocks4. Suggest the next high-level steps to take
    Inside your messages, there will be AI messages from different agents with different formats.
    Your output format should be always a JSON object with the following fields:{    "state_analysis": "Brief analysis of the current state and what has been done so far",    "progress_evaluation": "Evaluation of progress towards the ultimate goal (as percentage and description)",    "challenges": "List any potential challenges or roadblocks",    "next_steps": "List 2-3 concrete next steps to take",    "reasoning": "Explain your reasoning for the suggested next steps"}
    Ignore the other AI messages output structures.
    Keep your responses concise and focused on actionable insights.

#### toolPrompt

工具相关的prompt注入的方式比较特殊，不同的模型注入的方式不一样：

【程序自行注入】像'deepseek-r1'这种不支持function-call的模型，会在agent初始化的时候塞到message的上下文中，在messageManger初始化的时候作为上下文的信息显示声明在prompt。

![图片](assets/9836182547cf.jpg)

塞到消息上下文

![图片](assets/f490bc2d98a1.jpg)显示声明在prompt里

【框架帮忙注入】像qwen和gpt这种支持function-call的模型，会将所有的工具信息作为输出的schema传给模型，langchain会帮我们将工具绑定到模型的输入里（使用 Pydantic 定义模式）。

![图片](assets/d63d1b00b52d.jpg)

![图片](assets/e388763c6abd.jpg)

### 记忆模块

browser-use记忆相关的模块是通过MessageManager和Memory两个文件共同完成的，其中MessageManager顾名思义就是管理了和大模型交互过程中的所有通信内容， 包括系统提示词、用户输入、模型输出、工具输出等；Memory则使用mem0框架对MessageManager中的历史通信内容进行总结和压缩（刨除掉系统提示词：messageType为'init'的消息类型）。

#### MessageManager

##### 1\. 消息模型

  * MessageMetadata：记录消息的元数据，包括token数和消息类型。

![图片](assets/b58f0bdb2168.jpg)

  * ManagedMessage：包装实际消息和其元数据的容器类。

![图片](assets/ba1d5a0745fb.jpg)

  * MessageHistory：管理消息历史，包括添加、获取和删除消息功能。

![图片](assets/a45bace66712.jpg)

##### 2\. 消息生命周期管理

  * 2.1 Agent初始化的时候，将系统提示词和用户输入任务添加到消息列表里。

![图片](assets/9f834a747973.jpg)

  * 2.2 每个step运行的时候，将浏览器的上下文信息、agent状态信息等添加到消息列表里。

![图片](assets/9b3a8d8c21af.jpg)

  * 2.3 调用LLM后拿到模型的输出，将模型的输出添加到消息列表里。

![图片](assets/92f00afd55ce.jpg)

  * 2.4 工具执行后，将工具执行的结果塞到agent的状态信息里，在下一轮的step开始的时候（2.2）添加到消息列表里。

![图片](assets/45d8dcee2c6c.jpg)

##### 3\. 消息截断

目前的消息截断比较暴力，在token数量达到最大数量的时候，agent会优先移除最久的非系统消息。如果我们自己落地的时候，可以考虑对消息类型按照重要性进行分层加权，并在token数量和对话轮数达到一定阈值的时候进行裁剪或者压缩。

![图片](assets/c2777c629ad5.jpg)

#### Memory

memory的实现比较简单，就是在开启memory的时候，每一次step的执行都会对根据历史消息对话信息进行总结压缩，将历史的对话信息替换成总结压缩后的记忆信息。实际工程应用的时候，这里可以持久化实现长期记忆，在经过一定轮数的对话后总结沉淀用户相关的特征信息，并能够在之后的任务运行的时候作为初始化数据加载，让agent能够越来越懂用户。

![图片](assets/a32cef1ec6ff.jpg)

![图片](assets/a64b8060db8f.jpg)

在这个项目里，memory相关的信息是存储在本机内存里的，程序重启后就会丢失，我们实际生产环境落地的时候，对话上下文等短期记忆信息可能会用redis去存储和读取，长期记忆可能会通过模型总结后合并输出到向量数据库里。

### 结构化输出

agent运行的稳定性很大一点在于模型能否给出稳定格式的输出，在上面的对话演示中，我将返回的格式进行了限制，让模型按照给出的数据结构以JSON格式进行输出，最后模型也确实按照我给出的格式进行输出，效果还不错。回头看看browser-use，它是如何保证输出的稳定性的呢？

#### 1\. SystemPrompt指定输出格式

在上面对SystemPrompt的分析中，我们可以看到它给出了输出格式的内容，并且对每个参数都做了详细的说明。

#### 2\. 示例格式引导（one-shot）：

在初始化时提供标准输出示例，帮助模型理解正确的输出格式，相当于又强调了一遍输出格式。

  *   *   *   *   *   *   *   *   *   *   *   *   *   *   *

    placeholder_message = HumanMessage(content='Example output:')example_tool_call = AIMessage(    content='',    tool_calls=[{        'name': 'AgentOutput',        'args': {            'current_state': {                'evaluation_previous_goal': '...',                'memory': '...',                'next_goal': '...',            },            'action': [{'click_element': {'index': 0}}],        }    }])

#### 3.强制的数据模型验证

通过 pydantic 的 BaseModel 进行严格的数据验证和序列化，确保输出符合预定义的格式（如果输出不符合规范，在转化的时候pydantic会抛出ValidationError，见下面的错误处理）：

  * current_state（当前的状态）

  * evaluation_previous_goal：上一个步骤完成情况评估

  * memory：模型总结的记忆信息

  * next_goal：下一个步骤的目标

  * action：（待执行动作）

  * 每个动作以键值对形式表示，其中key是动作（方法）的名称，value为动作（方法）的参数对象。

  * 通过pydantic结构化定义的方式告诉模型动作有哪些，模型选择合适的动作后，返回值该动作下的参数对象不为空。

  *   *   *   *   *   *   *

    class AgentOutput(BaseModel):   current_state: AgentBrain  action: list[ActionModel] = Field(    ...,    description='List of actions to execute',    json_schema_extra={'min_items': 1},  # Ensure at least one action is provided  )

#### 4\. 多模型兼容

为了兼容不同模型能力和API的差异，对不同的模型有不同的调用方式和解析方式。

##### 4.1 raw：原始模式

  * 适配deepSeek-r1这种不支持function-call调用的模型；

  * 从模型的原始输出中解析JSON结构；

  *   *   *   *   *   *   *   *   *   *

    # 这里：直接调用大模型output = self.llm.invoke(input_messages)output.content = self._remove_think_tags(str(output.content))try:    #这里：从模型的原始输出中解析JSON结构    parsed_json = extract_json_from_model_output(output.content)    parsed = self.AgentOutput(**parsed_json)except (ValueError, ValidationError) as e:    raise ValueError('Could not parse response.')

##### 4.2 functionCall：函数调用

  * 适配支持function-call调用（OpenAI/Anthropic）的调用的模型

  *   *   *   *   *   *   *

    structured_llm = self.llm.with_structured_output(    self.AgentOutput,     include_raw=True,     method="function_call")response: dict[str, Any] = await structured_llm.ainvoke(input_messages)parsed: AgentOutput | None = response['parsed']

##### 4.3 兜底：结构化输出

  * 使用LangChain的结构化输出机制

  *   *   *

    structured_llm = self.llm.with_structured_output(self.AgentOutput, include_raw=True)response: dict[str, Any] = await structured_llm.ainvoke(input_messages)parsed: AgentOutput | None = response['parsed']

#### 5\. 错误处理和验证

模型的输出如果无法过Pydantic的模型校验，则抛出的异常会被agent捕获，并且将错误信息塞到消息列表中，希望模型能够在下一次执行的时候吸取教训，按照给定的数据格式进行输出。

  *   *   *   *   *   *

    VALIDATION_ERROR = 'Invalid model output format. Please follow the correct schema.'if isinstance(error, ValidationError):  return f'{AgentError.VALIDATION_ERROR}\nDetails: {str(error)}'
    result = await self._handle_step_error(e)self.state.last_result = result

### 工具注册&调用

![图片](assets/1d65f31c8196.png)

1\. 工具注册

工具的注册其实没有什么好说的，不同的语言、不同的开发者有不同的实现方式。你可以Low-level的通过API显示声明，也可以high-level一点的通过注解驱动开发，只要最后你能够给模型一个包含工具名称、工具描述、工具入参的完整工具结构信息就行。Browser-use是使用装饰器模式实现动作注册的，在注解里，你可以申明工具的描述信息和参数模型。

![图片](assets/fa5634a1da24.jpg)

#### 2\. 工具调用

工具调用包含两个部分：

第一个部分是将所有工具的信息以结构化的方式传给模型，让模型知道自己有哪些工具可以调用，这一部分在上面提示词设计和结构化输出里已经有解释了，其实就是将注册到Registy里的工具再转化为AgentOutput的标准输出，模型通过输出结构的定义获得了工具集合，返回值中参数模型的值不为空的工具就是模型选择调用的工具。

第二个部分就是Agent根据模型选择的工具和返回的参数执行工具的调用，这一部分其实就很简单，根据工具名称去registy管理的工具元数据中索引出来对应的工具信息，然后根据模型返回的参数和实际所需的上下文参数重新组装成新的参数，最后执行工具调用即可。

### 个人思考

browser-use这个项目包含了memory，planning，tools这几个agent所必须的工程实现，是一个很不错的agent入门项目，我们可以借鉴它的工程化思路，尝试去做自己的agent项目生产上的落地，同时工具的协议方面我们也可以考虑将MCP集成进去，进一步扩大它的能力边界，让它能够拿到更为精准的上下文信息。

## MCP

### 定义

MCP（Model Context Protocol，模型上下文协议）是一种统一大模型与外部数据源和工具之间的通信协议，期望以一种标准化的方式为 AI 应用提供连接万物的接口。它的协议和内容就不具体展开了，集团内外都有很多文档对他有详细的解释，想要深入了解可以直接去他官网：https://modelcontextprotocol.io/introduction

![图片](assets/1d9930153ed9.jpg)

在MCP之前，如果我们需要为LLM提供工具，每一个工具都需要我们手动的接入到应用程序中，自己维护工具的入参信息和描述信息，甚至为了适配不同数据源的协议差异，你可能还要写点转化层的代码。在MCP之后，维护工具的成本转移给了工具的提供方也就是服务端，工程侧只需要让LLM选择合适的工具用客户端通信服务端调用即可。

### browser-use 集成MCP

browser-use项目可以验证MCP的优越性，通过上面对它源码的剖析我们得知它目前是没有接入MCP的，工具的注册和执行都是本地的，如果你需要扩展它的手脚，让它能够通过工具拿到更多的上下文信息或执行更多的操作，只能够在它的工程里硬编码注册你需要的工具。

在学习MCP的过程中，我们可以尝试将MCP客户端集成到browser-use中，这样可以更有体感的去理解MCP的运行过程，服务端这边我使用了一下HSF官方提供的能力，它可以将存量的HSF接口转化成MCP Server，方便我们快速将已有的能力以工具的形式暴露出来。

源码解析那一章节已经绘出了工具的注册和调用的流程，如果我们要将MCP集成进去，有两种方式：

1\. System_prompt的方式：将MCP的概念和使用说明书统一管理在system_prompt中MCP_SERVERS部分，并提供一个use_mcp的本地工具让模型能够使用MCP暴露出来的工具，依赖模型的指令遵循能力，泛用性较好，但是分出了本地工具和MCP工具两种工具类型，工具使用的协议不统一，增大了模型错误使用工具的风险，Cline是这样实现的。

2\. function_call的方式：对模型屏蔽MCP的概念，将MCP暴露出来的工具封装成本地的工具一起function_call的方式交给模型调用，泛用性较差、依赖模型需要支持function_call能力，但Cursor是这样实现。

brwoser-use具有良好的多模型兼容的能力，它对于工具的调用本身就存在两种情况，不支持function_call的模型走system_prompt的方式，支持function_call的模型直接使用function_call调用。无论是哪种方式，工具都需要需要以工具元数据的形式注册到Registry中，因此我的实现上和cursor类似，让模型不感知MCP的概念，将MCP server端暴露出来的工具信息转化为工具元数据，运行时拿到模型返回的入参后走代理的方式执行工具调用。

![图片](assets/533a2594d417.png)

### 效果

假设我们希望为browser-use集成获得订单相关信息的能力，在集成了MCP后效果如下：（使用的模型为qwen-plus）

![图片](assets/8c87915c1dfc.jpg)

## Coze space

coze space于4月19日开启内测，目的让用户和AI Agent高效协作，完成各种复杂的任务。 核心能力有三个：任务自动化、专家Agent生态、以及打通MCP扩展集成。

它提供了两种agent的使用模式，其实就是上述说的“交错分解”模式和“分解优先”模式的具体实现。

### 探索模式

交错分解模式的实际应用：AI能够根据实时反馈动态调整策略，响应速度较快，适用于时效性要求高的任务。

![图片](assets/e6ec6bea27b4.jpg)

### 规划模式

分解优先模式的实际应用： AI会进行深度思考和规划，适合处理高复杂度的任务。在规划模式下，AI会先给出任务处理计划，用户可以修正任务，点击开始任务后Aagent就会分步骤的开始执行，提高了协作的灵活性和准确性。

![图片](assets/334a4ea4956d.jpg)

![图片](assets/f26fab1b4fbd.jpg)

大家可以试着用上面纯对话的方式模拟一下规划模式的流程是什么样子的，其实就是让AI先给出任务的计划，用户确认后再对每个子任务以探索模式的方式一步一步的进行执行。

## 总结展望

本文以个人的学习路径出发，用browser-use这个开源的项目为例子，通过对话演示、源码解析、MCP集成等方式，希望能够让工程的同学对一个自主规划的agent的实现有个大概的认知。当然browser-use本身也算一个MVP项目，如果要落地一个像coze，manus这样的平台，优秀的产品设计、更稳定的工程架构、强大的模型能力都是必不可少的。

目前我体验到的自主规划的agent，要么是分解优先要么是交错分解模式，但是没看到两种结合的形态，我心目中完美的agent应该有以下几点：

a.自行规划：在问题解决的期间自行选择是否需要做进一步的规划。

b.分层规划：一个大的问题往往需要分层做多次规划才能完成，比如你让agent去解决工单，第一层agent可能主要规划解决工单的主要流程：获得工单内容->去SOP查看解决方案->解决问题；第二层则是agent在SOP中拿到解决方案后根据解决方案规划解决工单的实际操作步骤：查询订单状态->订正订单状态->解决问题。

c.rethink模式：首次规划不一定是对的，在运行期间可能因为各种原因无法按照原来的既定规划执行，你得有一套rethink的机制，能够根据反思后的结果及时调整计划。

d.优秀的人机交互：Agent不能像个I人一样不和别人沟通，匡次匡次的埋头苦干，结果还拿不到好的结果，还被贴上废物的标签，因此Agent需要有向上沟通的能力，在合理的时候向用户请求帮助，提供授权。

随着模型能力的不断加强（大脑进化），模型获取上下文信息越来越多（感知环境的能力），工具集越来越完善（改变环境的能力），可能工程上也不用做特别多的架构设计，提示词也不用特别复杂就能实现上面的效果。

作为工程侧的研发，我可能会比较关心agent运行的稳定性，因此我会持续关注和学习分布式的记忆系统、多模型的兼容、结构化的输出、黑灰产prompt注入等确保Agent健康可持续运行的必要知识。

作为个人消费者，我个人更期待可以在终端上运行表现良好的Agent，丰富的软件生态+厂商的调教+用户行为学习，应该会有不错的Idea诞生，按照现在的发展速度，感觉用不了几年我就能拥有自己的贾维斯了，这真的很酷。

****

### 基于缓存实现应用提速

随着业务发展，承载业务的应用将会面临更大的流量压力，如何降低系统的响应时间，提升系统性能成为了每一位开发人员需要面临的问题，使用缓存是首选方案。本方案介绍如何运用云数据库Redis版构建缓存为应用提速。

## 点击阅读原文查看详情。
