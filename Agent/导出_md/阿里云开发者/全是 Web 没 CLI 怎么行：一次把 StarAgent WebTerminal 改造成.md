# 全是 Web 没 CLI 怎么行：一次把 StarAgent WebTerminal 改造成

> **公众号**: 阿里云开发者  
> **发布时间**: 2026-06-01 08:30  

![图片](assets/a398151e3dd7.webp)

阿里妹导读

全是 Web，没有 CLI，怎么行？Agent 都会写代码了，远程排障还要人肉点网页、复制命令、盯滚动条，这画面多少有点“地铁老人看手机.jpg”。本文记录一次围绕 StarAgent/Drogo WebTerminal 的工具化实践：我们没有把 GPU hang、core dump 调试等场景固化成一个个“祖传脚本套件”，而是把 WebTerminal 抽象成稳定的 CLI 执行面，再用 Skill 描述操作方法。Agent 在任务中动态生成命令、读取结果、继续决策，最终完成远程 GPU hang 分析、文件上传下载、以及 Emacs + eshell + gdb 的交互式 coredump 调试验收。

插播：我对 Skill 的态度很朴素：Skill 不是法器，不是咒语，也不是“复制进去 Agent 就突然开悟”的玄学符纸。Skill 本质上就是说明书，是贴在工具箱盖子上的那张“先拧这个、再接那个、别把手伸进风扇里”的操作指南。真正能把活干成的，必须是 CLI：参数清楚、行为稳定、输出可解析、错误可复现、证据能落盘。 所以这套东西的核心不是“写一个很长的 Skill 让 Agent 背下来”，而是把能制度化的都制度化，把能流程化的都流程化，把以前靠老师傅手感、群里口口相传、网页上点点点的部分，全部压进 wt 这种可执行接口里。Skill 只负责告诉 Agent：什么时候该登录、什么时候该 run、什么时候该 interact、什么时候该停手问人。至于真正挥锤子的活， 必须交给 CLI。否则就是让 Agent 看着说明书徒手修发动机，场面很感人，结果很危险。（文章内容基于作者个人技术实践与独立思考，旨在分享经验，仅代表个人观点。）

## WebTerminal 黑屏模式补充说明

**号外号外，重大更新：
WebTerminal 终于可以像 SSH/SCP 一样用了**

这轮最核心的新能力很直接：新增wsh/wcp，把 WebTerminal 从“打开浏览器点来点去”推进到“直接黑屏操作”。用户可以手动上去敲 shell，程序也可以直接调用命令；传文件也不再靠页面弹窗，而是走 wcp ，用法尽量贴近 ssh / scp 的肌肉记忆。感谢@先濠提供的多屏多容器支持，这让 session -> container -> role -> host 这条链路终于能落到比较完整的模型里，而不是只盯着一个默认页面硬猜。也感谢和@思潜的交流。聊完之后思路突然变得很明确：既然目标是让 WebTerminal 更像原生终端，那就别老想着再包一层 CLI 了，干脆往native terminal 化继续推，连 CLI 味儿都尽量去掉。

### 核心用法

![图片](assets/890fe08c2a74.png)先通过浏览器完成一次官方登录，把 cookie 缓存下来：

  *   *   *   *   *

    $ ./bin/wt auth login --target-ip x.y.z.wwt: waiting for browser login cookies; finish login in the opened browserauthenticated: Trueuser: defaultsource: browser

之后就可以直接黑屏进 shell，或者把它当成可编程的远程命令执行入口：

  *   *   *   *   *

    $ ./bin/wsh x.y.z.wattached direct: x.y.z.w$ ./bin/wsh x.y.z.w -- 'hostname; pwd'hippo-033126067104.na175/home/admin/hippo/worker/slave/drogo-share_worker-h20-na175.worker-h20-na175_11_33/main

文件传输也直接走wcp：

  *   *   *   *

    $ ./bin/wcp /tmp/wcp-demo.txt x.y.z.w:/tmp/wcp-demo.txt --forceuploaded: /tmp/wcp-demo.txt -> /tmp/wcp-demo.txt$ ./bin/wcp x.y.z.w:/tmp/wcp-demo.txt /tmp/wcp-demo.down.txt --forcedownloaded: /tmp/wcp-demo.txt -> /tmp/wcp-demo.down.txt

### 这次补上的关键体验

认证只需要浏览器进一次门，后续操作复用 auth cache。默认 cache 在~/.drogo-webterminal-helper/direct/default.auth.json，wsh/wcp会直接复用；如果换机器，也可以把这个 cache 拷过去继续用。shell 终于像个正常终端。exit不再卡死，远端 EOF / closed / reset 会正确退出；本地 terminal 的 rows / cols 会同步给 WebTerminal，窗口 resize 后也会继续同步，不再是一个小得离谱的假 shell。浏览器模式还保留，但不再是主路径。wtsh/wtcp --transport browser仍然可以作为兜底；默认使用 direct HTTP/WebSocket 做黑屏操作。

### 一点遗憾

纯黑屏登录暂时没有硬上。阿里 SSO 的 HTTP 登录链路会进入 RSA、风控、账号安全检查，继续硬怼收益不高，还容易把账号搞进风险提示。所以当前最稳的路线是：浏览器负责合规授权，真正干活走黑屏 shell。不算 100 分的“全黑屏”，但已经把最高频、最烦、最容易误操作的部分从网页里拽出来了。

## 以下是 V1 内容

### 前言：先把仓库拍你脸上

代码仓库在这里：foundation_models/webterminal-cli。先说结论：如果你也受够了“打开网页、点登录、复制命令、盯输出、再复制下一条”的人工智障流水线，那这个仓库就是给你准备的。它不负责让 WebTerminal 变得更漂亮，它负责让 WebTerminal 终于长出 CLI。是的，2026 年了，我们还在为“能不能别用手点网页”而奋斗，听起来很离谱，但工位现实就是这么朴素又残酷。这玩意儿的目标也很直接：让 Codex / Cursor / Claude Code 这类 Agent 不再隔着 DOM 猜命，而是通过wt像普通 shell 一样控制远端。能跑命令，能传文件，能开 gdb，能一条条交互，能把证据落盘。少一点“我好像看到了”，多一点“日志在这，别装死”。仓库欢迎试用、拍砖、提 MR，尤其欢迎那些一边骂“tmd 怎么全是 Web”，一边还能把工具补上的同学。

### 背景：Agent 要的不是另一个网页按钮，它要手脚

最近很多 AI Coding / Agent 实践都会落到同一个问题：模型会想、会写代码，甚至能一本正经地给你写 800 行设计文档；但真正接入企业内部系统时，经常卡在“可执行接口”上。它脑子很大，手却被绑在网页按钮上。远程机器排障就是典型场景。人可以打开 WebTerminal，点击登录，输入命令，看输出，再决定下一步；但 Agent 如果只能操作浏览器 DOM，它看到的是按钮、输入框、滚动区域，而不是一个稳定、可组合、可回放的执行协议。然后场面就变成：Agent 在旁边吟诗，人类在网页里点点点。这不就是“AI 时代的纯手工流水线”吗？这次实践的起点很朴素：希望 Agent 能在目标机器上完成 GPU hang 分析。结果做着做着发现，坑不是 GPU hang 一个坑，而是“WebTerminal 没有 Agent 友好执行面”这个大坑。于是需求开始膨胀，像线上故障群一样，消息一条接一条：

  * 目标 IP、操作步骤都必须参数化，框架和具体案例隔离。
  * 不做固定 suite，Agent 应该像工程师一样动态发送命令。
  * WebTerminal 浏览器会话要持续存在，不能每次操作都重新登录。
  * 上传下载要走 WebTerminal 后端 API 或协议，不能靠 DOM 自动化点弹窗。
  * 调试要是真交互：Agent 可以一条条给 gdb / emacs / eshell 发命令，拿到 response 后继续判断，而不是“一把梭，听天命”。

最后沉淀出来的不是一个“GPU hang 工具”，而是一个面向 Agent 的 WebTerminal CLI：wt。不是再造一个网页，不是写一个固定脚本，也不是在 DOM 上跳舞，而是给 Agent 一双能干活的手。![图片](assets/3930bb183aa8.png)

### 先看效果：别先讲架构，先看能不能干活

在实现完成后，我们用目标机器 x.y.z.w 做了三类验收。先把 PPT 收一收，工具这种东西，能不能跑比“愿景很大”重要。第一类是普通命令执行。Agent 通过 wt run 发送命令，命令输出会被捕获成本地证据文件，包括 raw ANSI、去 ANSI 的 plain text，以及 xterm snapshot。换句话说，不再是“我刚刚屏幕上好像看见了”，而是“证据在这，别耍赖”：

  *   *

    bin/wt run --capture captures/gpu-hang/env.raw.log -- \"hostname; date; uname -a; nvidia-smi -L || true; nvidia-smi || true"

第二类是文件传输。上传下载不再点击页面弹窗，不再祈祷浏览器下载目录没抽风，而是复用已登录浏览器上下文，直接调用 WebTerminal 文件 API：

  *   *   *

    bin/wt ls-files /home/adminbin/wt download /home/admin/remote.log captures/remote.logbin/wt upload ./local.txt /home/admin/local.txt

第三类是交互式调试。 wt interact 会启动一个本地 HTTP 控制面，远端交互程序保持运行；Agent 每次只发送下一条命令，拿到结果后再决定下一步。这才叫调试，不叫“把 gdb 命令写进遗书”：

  *   *   *   *   *   *   *

    bin/wt interact \--start "cd /tmp && gdb -q ./app core.wtdebug" \--prompt-regex "\\(gdb\\)\\s*$" \--host 127.0.0.1 \--port 8765 \--capture captures/debug/gdb.raw.log \--summary-json captures/debug/gdb.summary.json

  *   *   *   *

    curl -s -X POST http://127.0.0.1:8765/command -d '{"send":"bt"}'curl -s -X POST http://127.0.0.1:8765/command -d '{"send":"frame 0"}'curl -s -X POST http://127.0.0.1:8765/command -d '{"send":"info locals"}'curl -s -X POST http://127.0.0.1:8765/command -d '{"send":"print item.id"}'

这不是“把一组 gdb 命令一次性塞进去”。每个 /command 都是一次独立观察，Agent 可以根据上一条输出决定下一条动作。前一秒 bt ，后一秒 frame 0 ，再后一秒 print item.id ，像个正常工程师，而不是像个 bash 复读机。

**1\. 目标：把 WebTerminal 变成
Agent 友好的执行面**

这类工具最容易走偏的地方，是一上来就写一个场景套件。比如 gpu-hang 命令里内置十几条检查项，然后给出一个固定报告。看起来很智能，实际像“祖传 shell + 自动排版”。第一次看很香，第二次遇到分支就开始 tmd。这种方式短期有效，但它和 Agent 的能力是冲突的：

  * 场景逻辑被写死后，Agent 只能“调用工具”，不能“分析现场”，智商被强行锁死。
  * 每新增一个诊断路径，都要修改 CLI 代码。
  * 远端状态复杂时，固定脚本很难处理分支，例如进程是否存在、gdb 是否可用、权限是否足够、core 文件是否生成成功。
  * 安全边界不清晰，读操作、写操作、侵入式操作容易混在一起。

所以这个实现刻意把职责拆开：层次| 职责| 不做什么
---|---|---
WebTerminal 页面| 登录、角色选择、审计、心跳、官方连接链路| 不承载任务逻辑
`wt` CLI| 会话复用、命令发送、输出捕获、文件 API、交互控制面| 不内置具体排障 suite
Skill| 描述操作方法、风险边界、推荐命令模板| 不绑定某个 IP 或某个案例
Agent| 动态规划、执行、观察、复盘| 不绕过授权链路
一句话总结：CLI 提供稳定手脚，Skill 提供行动章法，Agent 负责临场判断。别把 Agent 当高级 crontab 用，它会委屈，我们也亏。

### 2\. 会话设计：授权留在浏览器，执行交给 CLI

企业内部 WebTerminal 通常不是一个裸 SSH。它背后有 SSO、角色、审批、审计、心跳、跳板、容器选择等一串逻辑。把这些全部重写进 CLI，不现实，也不应该。真要硬写，大概率写到一半开始怀疑人生：我是谁，我在哪，我为什么在复刻登录宇宙？因此 wt session start 的设计是：启动或复用一个持久 Chromium，会话仍由官方 WebTerminal 页面建立；用户完成登录后，CLI 只复用页面里已经存在的终端实例。

  *   *

    bin/wt session start --target-ipbin/wt session status

会话 ready 后，后续所有命令复用同一个浏览器上下文。浏览器不会在一次任务中被自动关闭，这样 Agent 可以持续操作一个远端现场。不要每跑一条命令就重新登录一次，那是自动化，不是自动折磨。这个设计带来几个直接收益：

  * 授权、审计、心跳仍走官方页面链路。
  * CLI 不保存 SSO token，也不绕过登录流程。
  * 目标 IP 是参数，不会写死在实现里。
  * 多轮排障可以共享同一个远端 shell 状态。

实现上，CLI 从页面里读取 window.terminalMap[wsSessionId] 对应的终端实例，使用页面暴露的 writeMsg2Session(data) 发送输入，同时 hook xterm 输出做本地捕获。

  *   *   *   *   *   *

    {"": {"type": "data","data": "pwd\r"}}

这保留了 WebTerminal 的官方连接路径，又把 Agent 需要的“命令输入/结果输出”抽象成了 CLI。授权规规矩矩，执行清清楚楚，审计也不用半夜来找你喝茶。

### 3\. 命令执行：不做 suite，做动态闭环

wt run 是最基础的能力：发送一条 shell 命令，等待结束标记，返回远端 exit code，并把输出落盘。

  *

    bin/wt run --capture captures/task/name.raw.log -- ""

为了可靠识别命令完成，wt run 会在远端命令后追加唯一 marker：

  *

    printf '\n__WT_DONE___:%s\n' "$?"

这比单纯依赖 prompt 更稳，因为远端 prompt 可能被用户配置、conda 环境、容器 shell、颜色控制字符影响。prompt 这东西，平时看着人畜无害，一到自动化里就开始整活。输出捕获也分三份：

  * *.raw.log：原始 ANSI 输出，适合保留完整现场。
  * *.plain：去 ANSI 后的文本，适合 Agent 解析。
  * *.snapshot.json：xterm buffer 快照，适合排查全屏程序或显示问题。

以 GPU hang 为例，Skill 只给出建议命令，不把诊断固化进 CLI：

  *   *   *   *   *   *

    bin/wt run --capture captures/gpu-hang/env.raw.log -- \"hostname; date; uname -a; id; pwd; which nvidia-smi || true; nvidia-smi -L || true; nvidia-smi || true"bin/wt run --capture captures/gpu-hang/processes.raw.log -- \"ps -eo pid,ppid,stat,etime,%cpu,%mem,wchan:32,cmd --sort=-%cpu | head -200; GPU_PIDS=\"$(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null | sort -u | tr '\n' ' ')\"; echo GPU_PIDS=$GPU_PIDS"bin/wt run --capture captures/gpu-hang/kernel.raw.log -- \"dmesg -T | egrep -i 'nvrm|xid|gpu|cuda|uvm|pcie|ecc|oom|hung|reset' | tail -300 || true"

Agent 读完结果后再决定是否继续查 wait channel、是否需要 gdb attach、是否需要用户批准侵入式操作。这里的关键不是“命令多”，而是“下一步有脑子”。![图片](assets/e599bcbdde77.png)

### 4\. 文件传输：从 DOM 自动化改成 API 调用

WebTerminal 页面里有上传下载能力。第一反应可能是让 Agent 去点按钮、选文件、等弹窗。听起来好像能跑，实际已经开始想：都 2026 年了，文件传输还要模拟鼠标点弹窗？这种方式对 Agent 很不友好：

  * DOM 结构容易变化。
  * 文件选择器和下载行为依赖浏览器设置。
  * 很难做完整校验。
  * 失败时只能看到 UI 结果，不容易拿到协议级错误。报错一句“上传失败”，人也失败了。

实际分析页面行为后，我们把文件传输实现成了直接 API 调用。CLI 复用已登录浏览器上下文里的 cookie 和终端状态，调用 WebTerminal 文件接口。也就是说，页面负责合法登录，CLI 负责正经传文件，大家各干各的，别互相折磨：

  * openFileSystem
  * listFiles
  * getDownloadFileHead
  * downloadFile
  * uploadFile
  * heartbeat

下载路径是：先拿文件 head，获取 fileUuid 、分块数、总大小和 md5；再按 block 下载；最后校验 size/md5，并可选通过远端 sha256sum/stat 二次校验。下载完不校验，等于“我感觉它对了”，这在排障现场基本等价于埋雷。上传路径是：先初始化上传，带上文件大小和 md5；再按 1MB block 发送 multipart；最后同样用远端 sha256/stat 验证。能协议化就协议化，少点玄学，多点 checksum。

  *   *

    bin/wt download /home/admin/remote.log captures/remote.logbin/wt upload ./local.txt /home/admin/local.txt

这里有一个重要边界：文件 API 仍要求 WebTerminal 已经登录到机器。也就是说，用户需要先在页面点击登录并进入终端，CLI 才能拿到完整的 file session 材料。先上车，再让 Agent 开车；没上车就飙，属于纯玄学。![图片](assets/e180ec1bfde7.png)

### 5\. 交互式调试：默认接口应该像普通 shell

远程排障里最难抽象的是交互式程序。比如 gdb、pdb、less、emacs、vim，它们不是“一条命令一个结果”的模型。你不能对 gdb 说“把所有问题一次回答完”，就像你不能在故障群里说“大家别问了，我先一次性猜完”。最初的 interact 是 expect 风格：把所有步骤一次性传进去。这个版本能跑通固定 demo，看起来还有点像那么回事。但用户一句“这好像不是交互式吧？”直接把它打回现实。确实，真正调试时，下一条命令取决于上一条输出：

  * bt 看到崩溃栈，才知道要进哪个 frame。
  * info locals 看到变量，才知道要 print 哪个字段。
  * gdb 缺符号、core 文件异常、路径不对，都需要临时调整。
  * 对 emacs 这类全屏程序，需要发送 raw key，而不是 line command。否则你以为在控制 Emacs，Emacs 以为你在乱按键。

因此最终把 wt interact 改成默认启动一个本地 HTTP server：Endpoint| 用途
---|---
`GET /health`| 查看交互会话是否存活
`GET /summary`| 查看完整步骤摘要
`GET /snapshot`| 获取 xterm 屏幕快照
`POST /command`| 发送一行命令，按 prompt regex 等待结果
`POST /send`| 发送 raw keys，适合 emacs/vim/TUI
`POST /drain`| 读取当前缓冲输出
`POST /close`| 退出远端交互程序并关闭本地 server
关键点是：远端程序只启动一次，状态在多次 HTTP 请求之间保持。gdb 的 $x 、当前 frame、breakpoint、Emacs buffer，都不能每请求一次就失忆。否则不是交互，是每次重启式自动化。

  *   *

    curl -s -X POST http://127.0.0.1:8765/command \-d '{"send":"print item.id"}'

响应里包含本次命令的 prompt-bounded 输出。Agent 看到这一段，就可以继续推理，而不是在一坨全量日志里捞针：

  *   *   *   *   *   *   *   *   *   *

    {"ok": true,"result": {"name": "command","send": "print item.id","matched": true,"timed_out": false,"plain_output": "(gdb) print item.id\r\n$1 = 42\r\n(gdb) "}}

实现上还有一个小坑：Playwright sync API 不能跨线程调用。最初用了 ThreadingHTTPServer ，结果请求进入不同线程后触发 greenlet thread switch 问题，场面一度非常“我是谁我在哪”。最后改成单线程 HTTPServer ，用锁保护 session 操作。对这个使用场景来说，Agent 本来就是顺序调试，单线程反而更符合模型。不是所有并发都高级，有些并发只负责把你送走。![图片](assets/2322a59c8048.png)

**6\. 验收案例：在 Emacs 里写 crash.c，
再用 eshell + gdb 定位 core**

为了证明这不是“批量塞命令”的伪交互，我们做了一个有点离谱但很硬的验收：在远端打开 emacs -nw -Q ，通过 raw key 创建 C 文件，进入 eshell 编译运行，再在 eshell 里启动 gdb 调试 coredump。这个流程像什么？像让 Agent 穿着拖鞋跑了个铁人三项。整个流程发生在同一个 WebTerminal 会话里，中间没有“重新打开一个干净环境假装成功”的魔法：

  1. wt interact启动远端emacs -nw -Q。
  2. /send发送C-x C-f /tmp/wt-emacs-crash.c。
  3. /send插入 C 源码并C-x C-s保存。
  4. /send执行M-x eshell。
  5. 在 eshell 里编译并运行程序，触发 segmentation fault。
  6. 生成core.wtdebug。
  7. 在 eshell 里启动gdb -q ./wt-emacs-crash core.wtdebug。
  8. 分别发送bt、frame 0、info locals、print item.id、print item.name。

触发崩溃的代码很小，但杀伤力很经典：空指针，C 语言永恒保留节目。

  *   *   *   *   *   *   *   *   *   *   *   *   *   *   *

    #includetypedef struct {int id;const char *name;} Item;static int crash(int n) {Item item = {42, "emacs-eshell-core"};int *ptr = 0;printf("about to crash: %s %d %d\n", item.name, item.id, n);return *ptr + item.id + n;}int main(int argc, char **argv) {int input = argc > 1 ? 7 : 3;return crash(input);}

GDB 输出证明调试链路有效。不是截图骗自己，是 gdb 真在 core 上说话：

  *   *   *

    Program terminated with signal SIGSEGV, Segmentation fault.#0  0x0000000000401168 in crash (n=7) at /tmp/wt-emacs-crash.c:1212        return *ptr + item.id + n;

bt 看到调用栈：

  *   *

    #0 crash (n=7) at /tmp/wt-emacs-crash.c:12#1 main (argc=2, argv=...) at /tmp/wt-emacs-crash.c:17

info locals 和 print 给出关键变量：

  *   *   *   *

    item = {id = 42, name = 0x402004 "emacs-eshell-core"}ptr = 0x0print item.id   -> 42print item.name -> "emacs-eshell-core"

最终定位结论很明确： ptr = 0x0 ，第 12 行 return *ptr + item.id + n ;对空指针解引用导致 coredump。凶手就是它，证据链闭合，别让业务同学再背锅。这个验收覆盖了普通 shell、全屏 TUI、文件编辑、编译、程序运行、core 生成、gdb prompt 交互和结果分析。对 Agent 来说，它已经足够接近“我在一台机器上远程调试”的体验。对人来说，终于不用盯着网页终端手搓半小时，属于工位幸福感 +1。

### 7\. GPU hang 分析：场景逻辑留给 Agent

在 x.y.z.w 上，我们基于 Skill 推荐的命令做了一次 GPU hang 分析。这里没有 wt gpu-hang --please-save-me 这种神棍命令，只有 Agent 根据现场一步步查。结果摘要如下：

  * 机器：hippo-xyzw
  * Kernel：5.10.134-010.ali5000.al8.x86_64
  * Driver：580.82.07
  * CUDA：13.0
  * GPU：8 x NVIDIA H20
  * 采集时 GPU compute processes 为空。
  * 采集时 8 张卡利用率均为 0%，显存占用约为基础占用。
  * 当前没有看到 active GPU hang。

但是 kernel log 里有历史信号。机器当场没 hang，不代表历史上没“作过妖”：

  * 反复出现 NVRM: refcntRequestReference_IMPL: Failed to enter state 1 ... status: 0x00000056。
  * NVSwitch 曾出现 SXid 22013 非致命链路中断。
  * 5 月 8 日有一次 Xid 43 ，进程名为 python。
  * 另有一次看起来不直接相关的 memcg OOM。

这就是动态命令闭环的价值：如果当时存在 GPU 进程，Agent 可以继续看 nvidia-smi --query-compute-apps=pid 、 /proc//task/*/wchan ，必要时请求用户批准后再执行 gdb -p 或 strace -p 。但在没有 active 现场时，工具不应该强行 attach 或 reset。排障不是法术，不要没病也上猛药。

**8\. Skill 的角色：
把经验写成操作方法，而不是写死代码**

这次实现里，Skill 不是“更长的 README”，而是 Agent 执行远程任务时的操作规约。README 是给人看的，Skill 是给 Agent 上手干活看的；写法不一样，心态也不一样。它写清楚了：

  * 如何启动或复用 session。
  * 如何确认用户已经登录并进入 WebTerminal。
  * 什么时候用 run ，什么时候用 attach ，什么时候用 interact 。
  * 文件上传下载必须走 API，不能操作 DOM。
  * 侵入式命令需要用户批准。
  * GPU hang 分析的建议命令，但不把它变成固定 suite。
  * coredump demo 的推荐构造方式和清理方式。

这样做的好处是，任务知识可以快速迭代，CLI 的底层抽象保持稳定。新增一个“Java 线程栈分析”或“磁盘 IO hang 分析”，更可能是改 Skill，而不是改 CLI。否则每加一个场景都发版，迟早变成“工具平台版祖传单体”。

### 9\. 几个设计取舍

## 9.1 为什么不直接连 SSH

因为真实企业环境里，WebTerminal 不是 SSH 的薄壳。它承载授权、审计、角色、心跳和访问入口。直接 SSH 可能绕过既有治理链路，也无法复用用户已经完成的登录态。为了一点方便把治理链路打穿，这种“聪明”通常会在复盘会上收费。这个工具选择尊重现有入口：让浏览器负责授权，让 CLI 负责执行抽象。

## 9.2 为什么不把 GPU hang 做成内置命令

GPU hang 的现场差异很大。固定 suite 很容易把 Agent 限制成“报告生成器”。我们更希望 Agent 能根据nvidia-smi、dmesg、进程状态、wchan、业务进程情况动态分支。否则 Agent 说“我看完了”，人一问“那进程栈呢？”，Agent 当场沉默。CLI 内置的是能力：运行命令、捕获证据、交互调试、传输文件。场景方法放在 Skill。

## 9.3 为什么交互控制面用 HTTP

HTTP 的好处是简单、可调试、Agent 容易调用。一个curl就能发下一条命令，response 就是观察结果。相比把所有调试命令预先写成脚本，HTTP 更接近 ReAct loop。简单不是土，简单是线上能救命。后续如果需要更低延迟或双向流，可以在同一抽象下扩展 WebSocket；但默认接口先保持简单。

## 9.4 为什么保留 interact-script

固定 expect 脚本仍然有价值，比如 smoke test、固定初始化流程、可重复 demo。只是它不应该是默认交互接口。能背稿的场合用脚本，真打架的时候要能临场发挥。所以现在：

  * wt interact：默认 live server，用于动态调试。
  * wt interact-script：固定脚本，用于已知步骤。

### 10\. 可以复用的工程模式

这次实践沉淀出几个对 Agent 工具建设通用的模式。都是踩坑踩出来的，不是坐会议室里脑补出来的。第一，先抽象执行面，再沉淀场景。Agent 缺的往往不是某个具体按钮，而是稳定的 command/observation loop。别一上来就问“能不能做一个 GPU hang 按钮”，按钮救不了复杂现场。第二，授权和执行要解耦。授权可以继续交给官方页面，执行可以通过 CLI 暴露给 Agent。第三，输出必须可保存、可解析、可复盘。raw/plain/snapshot 三份证据比“屏幕上看到了”更适合 Agent 协作。线上排障最怕一句“我刚才好像看到过”，这句话含金量约等于 0。第四，Skill 应该写边界和方法，而不是把所有业务逻辑变成代码。这样更容易扩展，也更符合 Agent 动态规划的方式。Skill 是路线图，不是把每一步都焊死的轨道。第五，交互式程序要按状态机设计。gdb、emacs、eshell 这类工具不是普通命令，必须保留远端进程状态，并允许多轮输入输出。第六，文件传输要协议化。能走 API 就不要点 DOM；能校验 size/md5/sha256 就不要只相信“下载完成”。“下载完成”四个字，在没有校验之前，只是一句祝福。

## 结语

这次 WebTerminal CLI 的核心不是“让 Agent 能远程执行命令”这么简单，而是把一个原本面向人的网页终端，整理成了 Agent 可以稳定消费的执行接口。人不该继续在网页里机械点点点，Agent 也不该隔着 DOM 猜人生。最终结果可以概括成三句话：

  * WebTerminal 继续负责官方授权和连接链路。
  * wt CLI 负责把远程 shell、文件传输、交互式程序变成可调用能力。
  * Skill 负责把排障经验写成可执行方法，让 Agent 根据现场动态闭环。

从 GPU hang 到 coredump 调试，真正有价值的不是某一组命令，而是 Agent 能够像工程师一样：观察、判断、执行、再观察。说白了，就是让 Agent 从“会聊天”进化到“能上手干活”。这中间差的不是一句 prompt，差的是一整套可执行、可观测、可复盘的工程接口。

### 招聘：欢迎底层系统同学跳进 AI 推理这口锅

如果你看到这里，心里冒出一句“这不就是系统工程吗？调度、性能、协议、可观测、debug、自动化，一个都不少”，那你基本懂我们在找什么人。我们现在在招 AI 推理和高性能计算方向的同学，方向概述如下：

  * 大模型推理系统工程：面向 LLM 推理链路做系统设计、稳定性、吞吐、延迟和工程化。
  * AI 高性能计算：面向 GPU/异构计算、通信、调度、算子和推理性能做深度优化。
  * AI 性能研发：把模型服务从“能跑”推进到“跑得快、跑得稳、跑得省”。
  * 多模态推理引擎：面向文本、视觉、语音等多模态推理场景做系统和性能建设。

点击下面“阅读原文”获取详细招聘内容

### 附录 A：当前 CLI 能力速览

  *   *   *   *   *   *   *   *   *   *   *

    wt session           管理持久 WebTerminal 浏览器会话wt status            查看当前终端状态wt run               执行一条 shell 命令并捕获输出wt attach            本地 raw TTY 直接接入 WebTerminalwt interact          启动 live HTTP 交互控制面wt interact-script   执行固定 expect 风格交互脚本wt snapshot          获取 xterm buffer 快照wt ls-files          通过 WebTerminal 文件 API 列目录wt download          通过 WebTerminal 文件 API 下载文件wt upload            通过 WebTerminal 文件 API 上传文件wt direct-info       输出脱敏后的直连协议材料，便于实验
