# 面试准备之Netty要点总结一

> **公众号**: 东阳马生架构  
> **发布时间**: 2025-09-15 09:00  

**大纲(22820字)**

- 1.TCP和UDP的简介
- 2.TCP连接的三次握手
- 3.TCP连接的四次挥手
- 4.Java IO读写的底层流程
- 5.Linux的IO模型详情
- 6.BIO网络编程
- 7.NIO网络编程之Buffer
- 8.NIO网络编程之组件
- 9.NIO网络编程之Reactor模式
- 10.NIO三大核心组件
- 11.NIO服务端的创建流程
- 12.NIO客户端的创建流程
- 13.NIO优点总结
- 14.NIO问题总结
- 15.Netty服务端的启动流程
- 16.Netty客户端的启动流程
- 17.Netty服务端和客户端使用总结
- 18.TCP粘包拆包
- 19.关于NioEventLoop的问题整理
- 20.NioEventLoop的执行总体框架
- 21.Reactor线程执行一次事件轮询
- 22.Reactor线程处理产生IO事件的Channel
- 23.Reactor线程处理任务队列之添加任务
- 24.Reactor线程处理任务队列之执行任务
- 25.NioEventLoop总结
- 26.关于ByteBuf的问题整理
- 27.零拷贝技术总结


简历关键词：深入研究过Netty的启动流程、线程模型、事件传播机制、内存管理机制等相关源码。

## 1.TCP和UDP的简介

TCP是面向连接的、可靠的流协议。TCP通过三次握手建立连接，通讯完成时需要拆除连接。UDP是面向无连接的通讯协议。UDP通讯时不需要接收方进行确认，属于不可靠的传输，因此可能会出现丢包的现象。TCP主要用于在传输层必须要实现可靠传输的情况，UDP主要用于需要高速传输、对实时性要求较高的通信或广播通信。

TCP是面向连接的通信协议，通过三次握手建立连接，通讯完成时拆除连接。由于TCP是面向连接的，所以只能用于端到端的通讯。TCP提供的是一种可靠的数据流服务，采用带重传的肯定确认技术来实现传输的可靠性。TCP还采用一种称为滑动窗口的方式进行流量控制，所谓窗口实际表示接收能力，用以限制发送方的发送速度。

UDP是面向无连接的通讯协议，UDP数据包括目的端口号和源端口号。由于基于UDP的通讯不需要连接，所以UDP可以实现广播发送。UDP通讯时不需要接收方确认，属于不可靠的传输，可能会出现丢包现象。所以实际应用中采用UDP进行通讯时，需要程序员编程验证。

## 2.TCP连接的三次握手

TCP提供面向有连接的通信传输，面向有连接是指在数据通信开始之前先做好两端之间的准备工作。所谓三次握手是指：建立一个TCP连接时，需要客户端和服务器端发送三个包以确认连接建立。在Socket编程中，三次握手的过程由客户端执行connect()方法来触发。

**第一次握手：** 首先客户端将标志位SYN设置为1，并随机产生一个值seq=x。然后将SYN=1,ACK=0,seq=x封装成数据包发送给服务器端，发起连接请求。接着客户端进入SYN_SENT状态，等待服务器端确认。

**第二次握手：** 服务器端收到数据包后，通过标志位SYN=1知道客户端在请求建立连接。于是将标志位SYN和ACK设置为1，值ack=x+1，并随机产生一个值seq=y。然后将SYN=1,ACK=1,ack=x+1,seq=y封装成数据包发送给客户端，确认连接请求。接着服务器端进入SYN_RCVD状态。

**第三次握手：** 客户端收到服务器端返回的确认后，检查ack是否为x+1，ACK是否为1。如果正确则将标志位ACK设置为1，值ack=y+1，并将该数据包发送给服务器端。服务器端收到数据包后检查ack是否为y+1，ACK是否为1。如果是则表明连接建立成功，客户端和服务器端进入ESTABLISHED状态。从而完成三次握手，之后客户端与服务器端就可以开始传输数据了。

![图片](assets/80e0c56bc1e6.webp)

## 3.TCP连接的四次挥手

所谓四次挥手是指：断开一个TCP连接时，需要客户端和服务端发送四个包以确认连接断开。在Socket编程中，这一过程由客户端或服务端任一方执行close()方法触发。

由于TCP连接是全双工的，因此每个方向都必须要单独进行关闭。也就是当一方完成数据发送任务后，发送一个FIN来终止这一方向的连接。收到一个FIN只是意味着这一方向上没有数据流动了，即不会再收到数据。但是在这个TCP连接上仍然能够发送数据，直到这一方向也发送了FIN。首先进行关闭的一方将执行主动关闭，而另一方则执行被动关闭。

**第一次挥手：** 客户端发出断开连接的报文，并且停止发送数据。在断开连接的报文中，FIN=1，序列号seq=u。这个序列号u等于前面已经传送过来的数据的最后一个字节的序号加1，此时客户端会进入FIN-WAIT-1(终止等待1)状态。TCP规定，FIN报文段即使不携带数据，也要消耗一个序号。

**第二次挥手：** 服务器收到断开连接的报文，发出确认报文。在确认报文中，ACK=1，ack=u+1，序列号seq=v。此时服务端就进入了CLOSE-WAIT(关闭等待)状态。这时处于半关闭状态，即客户端已没有数据要发送了。但如果服务器若发送数据给客户端，客户端依然需要接受。这个状态还要持续一段时间，也就是整个CLOSE-WAIT状态持续的时间。客户端收到服务器的确认报文后，就会进入FIN-WAIT-2(终止等待2)状态，等待服务器发送断开连接的报文。在收到服务器的断开连接报文之前，还需要接收服务器发送的最后的数据。

**第三次挥手：** 服务器将最后的数据发送完毕后，会向客户端发送断开连接的报文。由于在半关闭状态下，服务器很可能又发送了一些数据。在断开连接的报文中，FIN=1，ack=u+1，序列号为seq=w。此时服务器就进入了LAST-ACK(最后确认)状态，等待客户端的确认。

**第四次挥手：** 客户端收到服务器的断开连接报文后，必须发出确认。在确认报文中，ACK=1，ack=w+1，序列号seq=u+1。此时客户端就进入了TIME-WAIT(时间等待)状态。注意此时TCP连接还没有释放，必须经过2∗MSL(最长报文段寿命)的时间后，当客户端撤销相应的TCB后，才进入CLOSED状态。服务器只要收到了客户端发出的确认，立即进入CLOSED状态。同样，撤销TCB后，就结束这次的TCP连接。可以看到，服务器结束TCP连接的时间要比客户端早一些。

![图片](assets/a1fe962e19b0.png)

## 4.Java IO读写的底层流程

用户程序进行IO读写，基本上会用到系统调用read和write。系统调用read把数据从内核缓冲区(内核空间)复制到进程缓冲区(用户空间)，系统调用write把数据从用户缓冲区(用户空间)复制到内核缓冲区(内核空间)。它们并不等价数据在内核缓冲区和磁盘之间的交换。

Java服务端处理网络请求的典型过程：

**步骤一：接收客户端请求：** Linux通过网卡，读取客户断的请求数据，将数据读取到内核缓冲区。

**步骤二：获取请求数据：** 服务端从内核缓冲区读取数据到Java进程缓冲区。

**步骤三：服务器端业务处理：** Java服务端在自己的用户空间中处理客户端请求。

**步骤四：服务器端返回数据：** Java服务端已构建好的响应，从Java进程缓冲区写入内核缓冲区。

**步骤五：发送数据给客户端：** Linux内核通过网络IO ，将内核缓冲区中的数据，写入网卡。网卡通过底层的通讯协议，会将数据发送给目标客户端。

由于系统调用是在内核态中运行的，所以进行系统调用时，系统需要从用户态切换到内核态。系统从用户态切换到内核态的这个过程会产生性能损耗。在切换之前需要保存用户态的状态，包括寄存器、程序指令等。然后才能执行内核态的系统调用指令，最后还要恢复用户态。

用户态和内核态表示的是操作系统中的不同执行权限。两者最大的区别在于：运行在用户空间中的进程不能直接访问操作系统内核的指令和程序，运行在内核空间中的进程可以直接访问操作系统内核的指令和程序。进行权限划分是为了避免用户在进程中直接操作危险的系统指令，从而影响进程和系统的稳定。

## 5.Linux的IO模型详情

### (1)同步和异步、阻塞和非阻塞

同步和异步关注的是：结果的通知方式。同步是指：调用方需要主动等待结果的返回。异步是指：调用方不需要主动等待结果的返回，调用方会通过其他方式(如状态通知、回调函数等)来等待结果的返回。

阻塞和非阻塞关注的是：等待结果返回的调用方的状态。阻塞是指：结果返回之前，当前线程被挂起，不做任何事情。非阻塞是指：结果在返回之前，当前线程可以做其他事情，不会被挂起。

同步和异步关注的是：是否亲自主动获取消息，是否由其他人通知自己。阻塞和非阻塞关注的是：当前事情还没好时是否还能做其他事情。

**同步阻塞：** 同步阻塞基本也是编程中最常见的模型。比如客户去商店买衣服，去了之后发现衣服卖完了，就在店里面一直等，期间不做任何事(包括看手机)，等着商家进货，直到有货为止，效率很低。

**同步非阻塞：** 同步非阻塞在编程中可以抽象为一个轮询模式。客户去了商店之后，发现衣服卖完了，这个时候不需要傻傻的等着，客户可以去其他地方比如奶茶店买杯水，但是还是需要客户时不时的主动去商店问老板新衣服到了没有。

**异步阻塞：** 异步阻塞这个编程里面用的较少。这类似于写了个线程池，submit()后马上future.get()，此时线程还是挂起的。客户去商店买衣服，发现衣服没有了，于是就给老板留给电话，告诉老板说衣服到了就打电话进行通知，然后就一直守着电话不做其他事情。

**异步非阻塞：** 客户去商店买衣服，衣服没了，然后给老板留下电话，衣服到了就打电话通知。然后客户就可以随心所欲地去做其他事情，也不用操心衣服什么时候到。只要衣服一到，老板就会打电话进行通知，收到通知后再去买衣服即可。

### (2)Linux的IO模型之阻塞IO模型(同步)

应用程序调用recv()方法进行IO操作时，导致应用程序阻塞，等待数据准备好。如果数据没有准备好，则一直等待。如果数据准备好，则将数据从内核空间拷贝到用户空间，然后返回是否成功。

**阻塞IO(BIO)的优点：** 程序简单，在阻塞等待数据期间，用户线程挂起，用户线程基本不会占用CPU资源。

**阻塞IO(BIO)的缺点：** 一般情况下，需要为每个连接配套一条独立的线程，或者说一条线程维护一个连接成功的IO流的读写。在并发量小的情况下，这没什么问题，内存和线程切换开销比较小。但是当在高并发的场景下，需要大量的线程来维护大量的网络连接。因此，基本上BIO模型在高并发场景下是不可用的。

### (3)Linux的IO模型之非阻塞IO模型(同步)

把一个Socket设置为非阻塞就是告诉系统内核：当所请求的IO操作无法完成时，不要将进程睡眠，而是返回一个错误。这样IO操作函数将不断测试数据是否已经准备好。如果没有准备好，则继续测试，直到数据准备好为止。在这个不断测试的过程中，会大量的占用CPU的时间，所以该模型不应该被推荐。

**非阻塞IO(NIO)的特点：** 应用程序线程需不断进行IO系统调用，轮询数据是否已准备好。如果还没准备好，则继续轮询，直到完成系统调用为止。

**非阻塞IO(NIO)的优点：** 每次发起IO系统调用，在内核等待数据过程中可以立即返回。用户线程不会阻塞，实时性较好。

**非阻塞IO(NIO)的缺点：** 需要不断重复发起IO系统调用，不断询问内核。这种不断的轮询将会占用大量的CPU时间，系统资源利用率比较低。

### (4)Linux的IO模型之IO复用模型(同步)

(两次调用，两次返回)：IO多路复用模型，是通过一种新的系统调用来实现的。一个进程可以监视多个文件描述符，一旦某个描述符就绪(可读/可写)，那么内核就会通知程序进行相应的IO系统调用。非阻塞的BIO就是一个线程只能轮询自己的一个文件描述符。

IO多路复用模型的基本原理就是select/epoll系统调用。单个线程不断的轮询select/epoll系统调用所负责的成百上千的Socket连接，当某个或某些Socket网络连接有数据到达了，就返回这些可以读写的连接。好处是通过一次select/epoll调用，就能查询可读写的成百上千个网络连接。

在这种模式中首先不是进行read系统调动，而是进行select/epoll系统调用。当然前提是要将目标网络连接提前注册到select/epoll可查询的Socket列表，然后才可以开启整个IO多路复用模型的读流程。

**步骤一：** 首先进行select/epoll系统调用，查询可以读的连接。内核会通过select系统调用查询所有可查询的Socket列表。当任何一个Socket中的数据准备好了，select系统调用就会返回。注意：当用户线程调用了select系统调用时，整个线程是会被阻塞的。

**步骤二：** 用户线程获得了目标连接后，会发起read系统调用，此时用户线程被阻塞。然后内核开始将数据从内核缓冲区复制到用户缓冲区，接着内核返回结果。

**步骤三：** 用户线程才解除阻塞的状态，此时用户线程终于读取到数据，继续执行。

**多路复用IO(NIO)的特点：** 多路复用IO需要用到两个系统调用：一个是select/epoll查询调用，一个是IO的读取调用。负责select/epoll查询调用的线程需要不断进行select/epoll轮询，查找出可以进行IO操作的连接。

**多路复用IO(NIO)的优点：** 使用select/epoll的优势是：可以同时处理成千上万个连接。与一条线程维护一个连接相比，IO多路复用技术的最大优势是：系统不必创建线程，也不必维护这些线程，从而大大减小了系统的开销。Java的NIO技术，使用的就是IO多路复用模型。

**多路复用IO(NIO)的缺点：** select/epoll系统调用，本质上也是属于同步IO \+ 阻塞IO。都需要在读写事件就绪后，自己负责进行读写，这个读写过程是阻塞的。

## 6.BIO网络编程

### (1)BIO模型的问题与改进

BIO模型的最大问题是缺乏弹性伸缩能力。当客户端并发访问量增加后，服务端线程个数和客户端并发访问数呈1:1关系。线程是比较宝贵的系统资源，线程数量快速膨胀后，系统的性能将急剧下降。随着访问量的继续增大，系统最终可能会挂掉。

为了改进这种一个连接一个线程的模型，可以使用线程池来管理这些线程，从而实现1个或多个线程处理N个客户端的模型。但是这种改进后的模型的底层还是使用同步阻塞IO，通常这种通过线程池进行改进的模型被称为伪异步IO模型。

如果线程池使用的是CachedThreadPool线程池，那么除了能自动管理线程外，客户端 : 线程数看起来也像是1 : 1。如果线程池使用的是FixedThreadPool线程池，那么就能有效控制线程数量，实现客户端 : 线程数 = N : M的伪异步IO模型。但是正因为限制了线程数量，如果发生读取数据慢(比如数据量大、网络传输慢等)且存在大量并发的情况，那么对其他连接请求的处理就只能一直等待，可能引起的级联故障。

### (2)BIO编程的标准模式

说明一：客户端指定服务端的IP地址和端口，对服务端发起连接请求。

说明二：服务端需要有一个ServerSocket，来处理客户端发起的连接请求。服务端收到连接请求后，ServerSocket的accept()方法会创建一个Socket。然后将这个Socket打包成一个Runable型的任务并放到一个线程池里执行。

说明三：在这个Runable任务里便会根据这个Socket进行具体的读写和业务处理。

以上就是BIO编程的标准模式。BIO受限于并发下的线程数量，一般用于客户端较多。尽管早期的Tomcat也使用了线程池的BIO，但毕竟性能不高。

## 7.NIO网络编程之Buffer

### (1)Buffer的作用

Buffer的作用是方便读写通道(Channel)中的数据。首先数据是从通道(Channel)读入缓冲区，从缓冲区写入通道(Channel)的。应用程序发送数据时，会先将数据写入缓冲区，然后再通过通道发送缓冲区的数据。应用数据读取数据时，会先将数从通道中读到缓冲区，然后再读取缓冲区的数据。

缓冲区本质上是一块可以写入数据、可以读取数据的内存。这块内存被包装成NIO的Buffer对象，并提供了一组方法用来方便访问该块内存。所以Buffer的本质是一块可以写入数据、可以读取数据的内存。

Buffer缓冲区本质上是一个数组。通常它是一个字节数组ByteBuffer，当然还有其他基本类型的数组如CharBuffer。Buffer缓冲区不仅仅是一个数组，还可以对数据进行访问和对读写位置进行维护。所以Buffer缓冲区引入了4个核心概念：capacity、limit、position、mark。

### (2)Buffer的重要属性

**capacity：** Buffer作为一个内存块有一个固定的大小值，叫capacity。我们只能往Buffer中写capacity个byte、long，char等类型。一旦Buffer满了，需要将其清空(读取数据或清除数据)才能继续写数据。

**position：** 当往Buffer中写数据时，position表示当前的位置，position的初始值为0。当一个数据写到Buffer后，position会移动到下一个可插入数据的位置。所以position的最大值为capacity – 1。当从Buffer中读取数据时，需要从某个特定的position位置读数据。如果将Buffer从写模式切换到读模式，那么position会被重置为0。当从Buffer的position处读到一个数据时，position会移动到下一个可读位置。

**limit：** 在写模式下，Buffer的limit表示最多能往Buffer里写多少数据。在写模式下，Buffer的limit等于Buffer的capacity。当Buffer从写模式切换到读模式时， limit表示最多能读到多少数据。因此，当Buffer切换到读模式时，limit会被设置成写模式下的position值。

### (3)Buffer的分配

要想获得一个Buffer对象首先要进行分配，每一个Buffer类都有allocate()方法。可以在堆上分配，也可以在直接内存上分配。一般建议使用在堆上分配。如果应用偏计算，就用堆上分配。如果应用偏网络通讯频繁，就用直接内存。

### (4)Buffer的读写步骤

步骤一：写入数据到Buffer

步骤二：调用flip()方法

步骤三：从Buffer中读取数据

步骤四：调用clear()方法或compact()方法

flip()方法会将Buffer从写模式切换到读模式，调用flip()方法会将position设回0，并将limit设置成之前的position值。当向buffer写入数据时，buffer会记录下写了多少数据。一旦要读取数据，需要通过flip()方法将Buffer从写模式切换到读模式。在读模式下，可以读取之前写入到buffer的所有数据。一旦读完了所有的数据，就需要清空缓冲区，让它可以再次被写入。有两种方式能清空缓冲区：调用clear()方法或compact()方法。clear()方法会清空整个缓冲区，compact()方法只会清除已经读过的数据。任何未读的数据都被移到缓冲区的起始处，新写入的数据将放到缓冲区未读数据的后面。

## 8.NIO网络编程之组件

### (1)Selector

Selector的含义是选择器，也可以称为轮询代理器、事件订阅器。Selector的作用是注册事件和对Channel进行管理。应用程序可以向Selector对象注册它关注的Channel，以及具体的某一个Channel会对哪些IO事件感兴趣，Selector中会维护一个已经注册的Channel的容器。

### (2)Channel

Channel可以和操作系统进行内容传递，应用程序可以通过Channel读数据，也可以通过Channel向操作系统写数据，当然写数据和读数据都要通过Buffer来实现。

所有被Selector注册的Channel都是继承SelectableChannel的子类，通道中的数据总是要先读到一个Buffer，或者总是要从一个Buffer中写入。ScoketChannel和ServerSocketChannel都是SelectableChannel类的子类。

Channel是一个通道，网络数据通过Channel读取和写入。通道可以用于读、写或者二者同时进行。通道与流的区别在于：通道是双向的，流是单向的，一个流必须是InputStream和OutputStream的子类。

因为Channel是全双工的，所以它可以比流更好映射底层操作系统的API。在UNIX网络编程中，底层操作系统的通道都是全双工的，同时支持读写操作。

### (3)SelectionKey

NIO中的SelectionKey共定义了四种事件类型：OP_ACCEPT、OP_READ、OP_WRITE、OP_CONNECT，分别对应接受连接、读、写、请求连接的网络Socket操作。

ServerSocketChannel和SocketChannel可以注册自己感兴趣的操作类型，当对应操作类型的就绪条件满足时操作系统就会通知这些Channel。

### (4)NIO的开发流程

步骤一：服务端启动ServerSocketChannel，关注OP_ACCEPT事件。

步骤二：客户端启动SocketChannel，连接服务端，关注OP_CONNECT事件。

步骤三：服务端接受连接，然后启动一个SocketChannel。该SocketChannel可以关注OP_READ、OP_WRITE事件，一般连接建立后会直接关注OP_READ事件。

步骤四：客户端的SocketChannel发现连接建立后，关注OP_READ、OP_WRITE事件，一般客户端需要发送数据了才能关注OP_READ事件。

步骤五：连接建立后，客户端与服务器端开始相互发送消息(读写)，然后根据实际情况来关注OP_READ、OP_WRITE事件。

## 9.NIO网络编程之Reactor模式

### (1)单线程Reactor模式的问题

单线程的Reactor模式中的单线程主要是针对IO操作而言的，也就是所有的IO的accept、read、write、connect操作都在一个线程上完成。由于在单线程Reactor模式中，不仅IO操作在Reactor线程上，而且非IO的业务操作也在Reactor线程上进行处理，这会大大降低IO请求的响应。所以应将非IO的业务操作从Reactor线程上剥离，以提高Reactor线程对IO请求的响应。

为了改善单线程Reactor模式中Reactor线程还要处理业务逻辑，可以添加一个工作线程池。将非IO操作(解码、计算、编码)从Reactor线程中移出，然后转交给这个工作线程池来执行。所有IO操作依旧由单个Reactor线程来完成，如IO的accept、read、write以及connect操作。这样就能提高Reactor线程的IO响应，避免因耗时的业务逻辑而降低对后续IO请求的处理。

### (2)单线程Reactor不适合高并发场景

对于一些小容量的应用场景，可以使用单线程Reactor模型，但是对于一些高负载、大并发或大数据量的应用场景却不合适。

原因一：一个NIO线程同时处理成百上千的链路，性能上无法支撑。即便NIO线程的CPU负荷达到100%，也无法满足海量消息的读取和发送。

原因二：当NIO线程负载过重之后，处理速度将变慢，这会导致大量客户端连接超时。超时之后往往会进行重发，这更加重了NIO线程的负载。最终会导致大量消息积压和处理超时，成为系统的性能瓶颈。

### (3)多线程的Reactor模式介绍

在多线程的Reactor模式下，存在一个Reactor线程池，Reactor线程池里的每一个Reactor线程都有自己的Selector和事件分发逻辑。

Reactor线程池里的主反应器线程mainReactor可以只有一个，但子反应器线程subReactor一般会有多个，通常subReactor也是一个线程池。

主反应器线程mainReactor主要负责接收客户端的连接请求，然后将接收到的SocketChannel传递给子反应器线程subReactor，由subReactor来完成和客户端的通信。

### (4)多线程的Reactor模式流程

首先服务端的Reactor变成了多个线程对象，分为mainReactor和subReactor。这些Reactor对象也会启动事件循环，并使用Selector(选择器)来实现IO多路复用。

然后服务端在启动时会注册一个Acceptor事件处理器到mainReactor中。这个Acceptor事件处理器会关注accept事件，这样mainReactor监听到accept事件就会交给Acceptor事件处理器进行处理。

当客户端向服务端发起一个连接请求时，mainReactor就会监听到一个accept事件，于是就会将这个accept事件派发给Acceptor处理器来进行处理。

接着Acceptor处理器通过accept()方法便能得到这个客户端对应的连接(SocketChannel)，然后将这个连接SocketChannel传递给subReactor线程池进行处理。

subReactor线程池会分配一个subReactor线程给这个SocketChannel，并将SocketChannel关注的read事件及对应的read事件处理器注册到这个subReactor线程中。当然也会注册关注的write事件及write事件处理器到subReactor线程中以完成IO写操作。

总之，Reactor线程池中的每一Reactor线程都会有自己的Selector和事件分发逻辑。当有IO事件就绪时，相关的subReactor就将事件派发给响应的处理器处理。

注意，这里subReactor线程只负责完成IO的read()操作，在读取到数据后将业务逻辑的处理放入到工作线程池中完成。若完成业务逻辑后需要返回数据给客户端，则IO的write()操作还是会被提交回subReactor线程来完成。这样所有的IO操作依旧在Reactor线程(mainReactor或subReactor)中完成，而工作线程池仅用来处理非IO操作的逻辑。

多Reactor线程模式将"接收客户端的连接请求"和"与该客户端进行读写通信"分在了两个Reactor线程来完成。mainReactor完成接收客户端连接请求的操作，它不负责与客户端的通信，而是将建立好的连接转交给subReactor线程来完成与客户端的通信，这样就不会因为read()操作的数据量太大而导致后面的客户端连接请求得不到及时处理。并且多Reactor线程模式在海量的客户端并发请求的情况下，还可以通过subReactor线程池将海量的连接分发给多个subReactor线程，在多核的操作系统中这能大大提升应用的负载和吞吐量。

Netty服务端就是使用了多线程的Reactor模式。

## 10.NIO三大核心组件

NIO的三大核心组件分别是：Buffer、Channel、Selector。

### (1)Buffer缓冲区

Buffer缓冲区是用来封装数据的，也就是把数据写入到Buffer、或者从Buffer中读取数据。

### (2)Channel数据通道

Channel就是一个数据管道，负责传输数据(封装好数据的Buffer)，比如把数据写入到文件或网络、从文件或网络中读取数据。

### (3)Selector多路复用器

Selector会不断地轮询注册在其上的Channel。如果某个Channel上发生读或写事件，那么这个Channel就处于就绪状态。然后就绪的Channel就会被Selector轮询出来，具体就是通过Selector的SelectionKey来获取就绪的Channel集合。获取到就绪的Channel后，就可以进行后续的IO操作了。

一个Selector多路复用器可以同时轮询多个Channel。由于JDK使用了epoll()代替传统的select实现，所以它并没有最大连接句柄1024/2048的限制。这意味着只需要一个线程负责Selector多路复用器的轮询，就可以接入成千上万的客户端。

### (4)BIO和IO多路复用的理解

由于TCP连接的建立需要经过三次握手，所以可理解为客户端向服务端发起的Socket连接就绪需要经过三次握手请求。服务端接收到客户端的第一次握手请求时，会创建Socket连接(即创建一个Channel)。服务端接收客户端的第三次握手请求，这个Socket连接才算准备好(Channel才算就绪)。

在BIO模型下，只有一次系统调用recvfrom。所以服务端从接收到客户端的第一次握手请求开始，就必须同步阻塞等待直到第三次握手请求的完成，这样才能获取准备好的Socket连接并读取请求数据。

在多路复用模型下，会有两次系统调用select和recvfrom。所以服务端接收到客户端的第一次握手请求后，不必创建线程然后通过阻塞来等待第三次握手请求的完成，而是可以直接通过轮询Selector(基于select系统调用)，来获取所有已经完成第三次握手请求(已就绪)的客户端Socket连接，之后对这些Socket连接进行recvfrom系统调用时不需要阻塞也能马上读取到请求数据了。

## 11.NIO服务端的创建流程

步骤一：通过ServerSocketChannel的opne()方法打开ServerSocketChannel。

步骤二：设置ServerSocketChannel为非阻塞模式，绑定监听地址和端口。

步骤三：通过Selector的open()方法创建多路复用器Selector，将已打开的ServerSocketChannel注册到多路复用器Selector上以及监听ACCEPT事件。

步骤四：多路复用器Selector通过select()方法轮询准备就绪的SelectionKey。

步骤五：如果这个SelectionKey是acceptable，说明有客户端发起了连接请求。此时需要调用ServerSocketChannel的accept()方法来处理该接入请求，也就是完成TCP三次握手并建立物理链路以及得到该客户端连接SocketChannel。

步骤六：然后将新接入的客户端连接SocketChannel注册到多路复用器Selector上以及监听READ事件。

步骤七：如果这个SelectionKey是readable，说明有客户端发送了数据过来。此时需要调用SocketChannel的read()方法异步读取客户端发送的数据到ByteBuffer缓冲区，同时将客户端连接SocketChannel注册到多路复用器Selector上以及监听WRITE事件。

步骤八：接着对ByteBuffer缓冲区的数据进行decode解码处理并完成业务逻辑，然后再将处理结果对象encode编码放入ByteBuffer缓冲区，最后调用SocketChannel的write()方法异步发送给客户端，以及将客户端连接SocketChannel注册到多路复用器Selector上以及监听READ事件。

## 12.NIO客户端的创建流程

步骤一：通过SocketChannel的open()方法打开SocketChannel。

步骤二：设置SocketChannel为非阻塞模式，同时设置TCP参数。

步骤三：调用SocketChannel的connect()方法异步连接服务端，完成TCP三次握手并建立物理链路。

步骤四：通过Selector的open()方法创建多路复用器Selector，并将已打开的SocketChannel注册到多路复用器Selector上以及监听CONNECT事件。

步骤五：多路复用器Selector通过select()方法轮询准备就绪的SelectionKey。

步骤六：如果这个SelectionKey是connectable，说明服务端接受了发起的连接请求，于是将SocketChannel注册到多路复用器Selector上以及监听READ事件。

步骤七：如果这个SelectionKey是readable，说明服务端返回了数据。于是调用SocketChannel的read()方法异步读取服务端返回的数据到ByteBuffer缓冲区，同时将客户端连接SocketChannel注册到多路复用器Selector上以及监听WRITE事件。

步骤八：接着对ByteBuffer缓冲区的数据进行decode解码处理并完成业务逻辑，然后再将处理结果对象encode编码放入ByteBuffer缓冲区，最后调用SocketChannel的write()方法异步发送给客户端，以及将客户端连接SocketChannel注册到多路复用器Selector上以及监听READ事件。

## 13.NIO优点总结

**优点一：SocketChannel的连接操作是异步的**

也就是客户端发起的连接操作SocketChannel.connect()是异步的。可以将SocketChannel注册到多路复用器上并关注OP_CONNECT事件等待后续结果，不需要像BIO的客户端那样被同步阻塞。

**优点二：SocketChannel的读写操作都是异步的**

也就是客户端发起的读写操作SocketChannel.read()和write()是异步的。如果没有可读写的数据它不会同步等待，而会直接返回。这样IO通信链路就可以处理其他链路了，不需要同步等待这个链路可用。

**优点三：优化了线程模型**

由于JDK的Selector在Linux等主流操作系统上通过epoll实现，从而没有了连接句柄数的限制。这意味着一个Selector线程可以同时处理成千上万个客户端连接，而且性能不会随客户端增加而线性下降。注意：Selector.select()是同步阻塞的。

******优点四：优化了IO读写**

BIO的读写是面向流的，一次性只能从流中读取一子节或多字节，而且读完后流无法再读取，需要自己缓存数据。NIO的读写是面向Buffer的，可随意读取里面任何字节的数据。不需要自己缓存数据，只需要移动读写指针即可。

## 14.NIO问题总结

**问题一：** NIO的类库和API繁杂，需要熟练掌握Selector、ServerSocketChannel、SocketChannel、ByteBuffer等。

**问题二：** 处理常见问题的工作量和难度比较大，比如客户断连重连、网络闪断、半包读写、失败缓存、网络拥塞和异常码流等。

**问题三：** NIO的epoll bug会导致Selector空轮询，最终导致CPU达到100%。

## 15.Netty服务端的启动流程

**步骤一：** 首先创建两个NioEventLoopGroup实例，bossGroup实例用于接收客户端的连接，workerGroup实例用于处理每个连接的读写。NioEventLoopGroup是个线程组，它包含了一组NIO线程，专门用于处理网络事件。

**步骤二：** 然后创建ServerBootstrap实例，ServerBootstrap是Netty用于启动NIO服务端的启动引导类。

**步骤三：** 接着调用ServerBootstrap的group()方法指定线程模型，也就是将两个NIO线程组传递到ServerBootstrap中。然后调用ServerBootstrap的channel()方法指定IO模型为NIO，也就是指定创建的Channel为NioServerSocketChannel。然后调用ServerBootstrap的option()方法指定TCP参数，也就是配置NioServerSocketChannel的TCP参数。然后调用ServerBootstrap的childHandler()方法指定业务处理逻辑，也就是绑定IO事件的处理类ChildHandler等。

**步骤四：** 完成服务端的辅助启动类的配置后，就调用它的bind()方法来异步绑定监听端口。然后继续调用它的sync()方法进行同步阻塞来等待绑定操作完成，绑定操作完成后会返回一个ChannelFuture。

**步骤五：** 接着使用ChannelFuture的方法进行阻塞，直到服务端链路关闭。

**步骤六：** 最后使用NIO线程组(NioEventLoopGroup)的shutdownGracefully()方法进行优雅退出。

## 16.Netty客户端的启动流程

**步骤一：** 首先创建客户端处理IO读写的NioEventLoopGroup实例。NioEventLoopGroup是个线程组，它包含了一组NIO线程，专门用于处理网络事件。

**步骤二：** 然后创建Bootstrap实例，Bootstrap是Netty用于启动NIO客户端的启动引导类。

**步骤三：** 接着调用Bootstrap的group()、channel()、option()、handler()方法配置好：线程模型、IO模型、TCP参数、业务处理逻辑。

**步骤四：** 完成客户端启动辅助类的配置后，就调用它的connect()方法来异步发起连接，然后调用sync()方法进行同步阻塞来等待连接成功。

**步骤五：** 接着使用ChannelFuture的方法进行阻塞，直到客户端连接关闭。

**步骤六：** 最后使用NIO线程组(NioEventLoopGroup)的shutdownGracefully()方法进行优雅退出。

## 17.Netty服务端和客户端使用总结

### (1)Netty服务端的启动流程

首先创建一个服务端的启动引导类ServerBootstrap，然后给它指定线程模型、IO模型、TCP参数、业务处理逻辑，最后通过它的bind()方法绑定端口后，服务端就启动起来了。

### (2)Netty客户端的启动流程

首先创建一个客户端的启动引导类Bootstrap，然后给它指定线程模型、IO模型、TCP参数、业务处理逻辑，最后通过它的connect()方法连接上服务端后，客户端就启动起来了。

### (3)bind()方法和connect()方法

bind()方法和connect()方法都是异步的，这两方法调用后都会立即返回一个ChannelFuture，都可以通过ChannelFuture的addListener()方法添加监听器监听端口是否绑定成功以及连接是否建立成功。

### (4)Netty的基本组件与BIO的对应

NIO的三大组件是：Buffer、Channel、Selector。NioEventLoop对应于BIO的线程(监听客户端连接 + 处理客户端连接的读写)。Channel对应于BIO的Socket，ByteBuf对应于BIO的IO Bytes，Pipeline对应于BIO的逻辑处理链，ChannelHandler对应于BIO的逻辑处理块。

## 18.TCP粘包拆包

### (1)什么是TCP粘包拆包

TCP协议是一个流协议。所谓流，就是没有界限的一串数据。就像河里的流水，它们是连成一片的，其中并没有分界线。

TCP协议的底层并不了解上层业务数据的具体含义，它会根据TCP缓冲区的实际情况进行包的划分。所以在业务上认为，一个完整的包可能会被拆分成多个包进行发送，也有可能把多个小的包封装成一个大的数据包进行发送。这就是TCP粘包和拆包问题。

### (2)TCP粘包拆包的几种情况

假设客户端发送了两个数据包D1和D2给服务端，由于服务端一次读取到的字节数是不确定的，故可能有如下情况：

情况一：服务端分两次读取到了两个独立的数据包，也就是数据包D1和D2是分开的，没有出现粘包和拆包的情况。

情况二：服务端一次接收到了两个数据包，也就是数据包D1和D2粘在一起了，出现了TCP粘包的情况。

情况三：服务端分两次读取到了两个数据包，第一次读取到了完整的D1包和D2包的部分内容，第二次读取到了D2包的剩余内容，出现了TCP拆包的情况。

情况四：服务端分两次读取到了两个数据包，第一次读取到了D1包的部分内容，第二次读取到了D1包的剩余内容和完整的D2包，出现了TCP拆包的情况。

情况五：服务端分多次读取到两个数据包，如果服务端的TCP接收滑窗非常小，而数据包D1和D2比较大，那么服务端可能要分多次才能将D1和D2包接收完，期间发生了多次拆包。

### (3)TCP粘包问题的原因

由于TCP协议是基于三次握手的可靠的传输协议，会让客户端与服务端维持一个连接。所以在连接不断开的情况下，客户端能够持续不断地将多个数据包发往服务端。

但如果发送的数据包太小，则会因Nagle算法而对较小的数据包进行合并再发送。开启Nagle算法会让TCP的网络延迟高一些，当然可以设置关闭Nagle算法。这样服务端在收到数据包时就无法区分哪些数据包是独立的，从而产生粘包问题。

服务端在收到数据包后会将其放到缓冲区中，如果数据包没有及时从缓存区取走，那么下次获取数据包时就可能会出现一次取出多个数据包的情况，从而产生粘包问题。

由于UDP协议本身作为无连接的不可靠的传输协议(适合频繁发送较小的数据包)，所以不会对数据包进行合并发送(也就不会使用Nagle算法)。每一个数据包都是独立和完整的，但服务端接收的缓冲区大小也会影响是否出现粘包问题。

### (4)TCP半包问题的原因

产生半包问题的核心原因就是一个数据包被分成了多次接收，比如：可能是IP分片传输导致的、可能是传输过程中丢失部分包导致出现半包、可能是一个包被分成了两次传输，在获取数据时先取到一部分、可能与接收的缓冲区大小有关系，在获取数据时先取到一部分。

半包问题更具体的原因有三个，分别如下：应用程序写入数据的字节大小大于Socket套接字发送缓冲区的大小、进行MSS大小的TCP分段、以太网的payload大于MTU进行IP分片。

### (5)粘包问题的解决策略

由于TCP协议的底层无法理解上层的业务数据，所以在底层是无法保证数据包不被拆分和重组的，这个问题只能通过上层的应用协议栈设计来解决。

策略一：消息定长，例如每个报文的大小为固定长度200字节，如果不够，空位补空格。FixedLengthFrameDecoder。

策略二：加分割符，在包尾增加回车换行符等特殊分隔符进行分割，如FTP协议。LineBasedFrameDecoder、DelimiterBasedFrameDecoder。

策略三：消息带上长度字段，比如将消息分为消息头和消息体，消息头中包含消息的总长度。LengthFieldBasedFrameDecoder。

### (6)拆包的原理

拆包的基本原理就是不断从TCP缓冲区中读取数据，每次读取完都要判断是否是一个完整的数据包。如果当前读取的数据不足以拼接成一个完整的业务数据包，那就保留该数据，继续从TCP缓冲区中读取，直到得到一个完整的数据包。如果当前读取的数据加上已读取的数据足以拼接成一个完整的业务数据包，那就将已读取的数据拼接上当前读取的数据，构成一个完整的业务数据包传递到业务逻辑，多余的数据仍然保留，以便和下一次读取的数据进行拼接。

### (7)换行符解码器LineBasedFrameDecoder

LineBasedFrameDecoder也可以称为行拆包器。从字面意思看，发送端发送数据包时，每个数据包之间以换行符作为分隔，接收端通过这个行拆包器将粘过的ByteBuf拆分成一个个完整的应用层数据包。它的工作原理是依次遍历ByteBuf中的可读字节，然后判断是否有"\n"或者"\r\n"。如果有，就以此位置为结束位置，从可读索引到结束位置区间的字节就组成了一行。它是以换行符为结束标志的解码器，支持配置单行的最大长度。如果连续读取到最大长度后仍然没有发现换行符，那么就会抛出异常，并忽略之前读取到的异常码流。

### (8)分隔符解码器DelimiterBasedFrameDecoder

DelimiterBasedFrameDecoder也可以称为分隔符拆包器，它是行拆包器的通用版本，可以传递两个参数，可以自定义分隔符。第一个参数1024表示单条消息的最大长度，当达到该长度后仍然没有查找到分隔符则抛异常。第二个参数就是分隔符ByteBuf对象。

### (9)固定长度解码器FixedLengthFrameDecoder

FixedLengthFrameDecoder也可以称为固定长度拆包器。如果应用层协议非常简单，每个数据包的长度都是固定的，比如100。那么只需要把这个固定长度解码器添加到Pipeline中，Netty就会把一个个长度为100的数据包(ByteBuf)传递到下一个ChannelHandler。

因为利用固定长度解码器，无论一次接收多少数据，都会按照构造函数中设置的固定长度进行解码。如果是半包消息，固定长度解码器会缓存半包消息并等下一个数据包到达后再进行拼包处理。

### (10)基于长度域解码器LengthFieldBasedDecoder

LengthFieldBasedDecoder也可以称为基于长度域的拆包器，这种基于长度域的拆包器是最通用的一种拆包器。只要我们的自定义协议中包含长度域字段，均可以使用这个解码器来实现应用层拆包。

## 19.关于NioEventLoop的问题整理

**(1)默认下Netty服务端起多少线程及何时启动？**

答：默认是2倍CPU核数个线程。在调用EventExcutor的execute(task)方法时，会判断当前线程是否为Netty的Reactor线程，也就是判断当前线程是否为NioEventLoop对应的线程实体。如果是，则说明Netty的Reactor线程已经启动了。如果不是，则说明是外部线程调用EventExcutor的execute()方法。于是会先调用startThread()方法判断当前线程是否已被启动，如果还没有被启动就启动当前线程作为Netty的Reactor线程。

**(2)Netty是如何解决JDK空轮询的？**

答：Netty会判断如果当前阻塞的一个Select()操作并没有花那么长时间，那么就说明此时有可能触发了空轮询Bug。默认情况下如果这个现象达到512次，那么就重建一个Selector，并且把之前Selector上所有的key重新移交到新Selector上。通过以上这种处理方式来避免JDK空轮询Bug。

**(3)Netty是如何保证异步串行无锁化的？**

答：异步串行无锁化有两个场景。

场景一：拿到客户端一个Channel，不需要对该Channel进行同步，直接就可以多线程并发读写。

场景二：ChannelHandler里的所有操作都是线程安全的，不需要进行同步。

Netty在所有外部线程去调用EventLoop或者Channel的方法时，会通过inEventLoop()方法来判断出当前线程是外部线程(非NioEventLoop的线程实体)。在这种情况下，会把所有操作都封装成一个Task放入MPSC队列，然后在NioEventLoop的执行逻辑也就是run()方法里，这些Task会被逐个执行。

### (4)NioEventLoopGroup的创建总结

默认情况下，NioEventLoopGroup会创建2倍CPU核数个NioEventLoop。一个NioEventLoop和一个Selector以及一个MPSC任务队列一一对应。

NioEventLoop线程的命名规则是nioEventLoopGroup-xx-yy，其中xx表示全局第xx个NioEventLoopGroup线程池，yy表示这个NioEventLoop在这个NioEventLoopGroup中是属于第yy个。

线程选择器chooser的作用是为一个连接选择一个NioEventLoop，可通过线程选择器的next()方法返回一个NioEventLoop。如果NioEventLoop的个数为2的幂，则next()方法会使用位与运算进行优化。

一个NioEventLoopGroup会有一个线程执行器executor、一个线程选择器chooser、一个数组children存放2倍CPU核数个NioEventLoop。

### (5)NioEventLoop的启动总结

一.在注册服务端Channel的过程中，主线程最终会调用AbstractUnsafe的register()方法。该方法首先会将一个NioEventLoop绑定到这个服务端Channel上，然后把实际注册Selector的逻辑封装成一个Runnable任务，接着调用NioEventLoop的execute()方法来执行这个Runnable任务。

二.NioEventLoop的execute()方法其实就是其父类SingleThreadEventExecutor的execute()方法，它会先判断当前调用execute()方法的线程是不是Netty的Reactor线程，如果不是就调用startThread()方法来创建一个Reactor线程。

三.startThread()方法会通过线程执行器ThreadPerTaskExecutor的execute()方法来创建一个线程。这个线程是一个FastThreadLocalThread线程，这个线程需要执行如下逻辑：把线程保存到NioEventLoop的成员变量thread中，然后调用NioEventLoop的run()方法来启动NioEventLoop。

### (6)NioEventLoop的启动流程说明

首先bind()方法会将具体绑定端口的操作封装成一个Runnable任务，然后调用NioEventLoop的execute()方法，接着Netty会判断调用execute()方法的线程是否是NIO线程，如果发现不是就会调用startThread()方法开始创建线程。

创建线程是通过线程执行器ThreadPerTaskExecutor来创建的。线程执行器的作用是每执行一个任务都会创建一个线程，而且创建出来的线程就是NioEventLoop底层的一个FastThreadLocalThread线程。

创建完FastThreadLocalThread线程后会执行一个Runnable任务，该Runnable任务首先会将这个线程保存到NioEventLoop对象。保存的目的是为了判断后续对NioEventLoop的相关执行线程是否为本身。如果不是就将封装好的一个任务放入TaskQueue中进行串行执行，实现线程安全。该Runnable任务然后会调用NioEventLoop的run()方法，从而启动NioEventLoop。NioEventLoop的run()方法是驱动Netty运转的核心方法。

## 20.NioEventLoop的执行总体框架

### (1)Reactor线程所做的三件事情

NioEventLoop的run()方法里有个无限for循环，for循环里便是Reactor线程所要做的3件事情。

#### 一.首先是调用select()方法进行一次事件轮询

由于一个NioEventLoop对应一个Selector，所以该select()方法便是轮询注册到这个Reactor线程对应的Selector上的所有Channel的IO事件。注意，select()方法里也有一个无限for循环，但是这个无限for循环可能会被某些条件中断。

#### 二.然后调用processSelectedKeys()方法处理轮询出来的IO事件

#### 三.最后调用runAllTasks()方法来处理外部线程放入TaskQueue的任务

### (2)处理多久IO事件就执行多久任务

在NioEventLoop的run()方法中，有个ioRatio默认是50，代表处理IO事件的时间和执行任务的时间是1:1。也就是执行了多久的processSelectedKeys()方法后，紧接着就执行多久的runAllTasks()方法。

```cs
NioEventLoop.run() -> for(;;)
  select() //执行一次事件轮询检查是否有IO事件
    processSelectedKeys() //处理产生IO事件的Channel
    runAllTasks() //处理异步任务队列
//这3步放在一个线程处理应该是为了节约线程，因为不是总会有IO事件和异步任务的
//同时实现对同一个SocketChannel的处理，实现线程安全
```

## 21.Reactor线程执行一次事件轮询

### (1)执行select操作前设置wakeUp变量

NioEventLoop有个wakenUp成员变量表示是否应该唤醒正在阻塞的select操作。NioEventLoop的run()方法准备执行select()方法进行一次新的循环逻辑之前，都会将wakenUp设置成false，标志新一轮循环的开始。

### (2)定时任务快开始了则中断本次轮询

NioEventLoop中的Reactor线程的select操作也是一个for循环。在for循环第一步，如果发现当前定时任务队列中某个任务的开始时间快到了(小于0.5ms)，那么就跳出循环。在跳出循环之前，如果发现目前为止还没有进行过select操作，就调用一次selectNow()方法执行非阻塞式select操作。

Netty里的定时任务队列是按照延迟时间从小到大进行排序的，所以delayNanos()方法返回的第一个定时任务的延迟时间便是最早截止的时间。

### (3)轮询中发现有任务加入则中断本次轮询

注意：Netty的任务队列包括普通任务和定时任务。定时任务快开始时需要中断本次轮询，普通任务队列非空时也需要中断本次轮询。

Netty为了保证普通任务队列里的普通任务能够及时执行，在调用selector.select()方法进行阻塞式select操作前会判断普通任务队列是否为空。如果不为空，那么就调用selector.selectNow()方法执行一次非阻塞select操作，然后跳出循环。

### (4)执行阻塞式select操作

#### 一.最多阻塞到第一个定时任务的开始时间

执行到这一步，说明Netty的普通任务队列里的队列为空，并且所有定时任务的开始时间还未到(大于0.5ms)。于是便进行一次阻塞式select操作，一直阻塞到第一个定时任务的开始时间，也就是把timeoutMills作为参数传入select()方法中。

#### 二.外部线程提交任务会唤醒Reactor线程

如果第一个定时任务的延迟时间非常长，比如一小时，那么有可能线程会一直阻塞在select操作(select完还是会返回的)。但只要这段时间内有新任务加入，该阻塞就会被释放。

比如当有外部线程执行NioEventLoop的execute()方法添加任务时，就会调用NioEventLoop的wakeUp()方法来通过selector.wakeup()方法，去唤醒正在执行selector.select(timeoutMills)而被阻塞的线程。

#### 三.是否中断本次轮询的判断条件

阻塞式select操作结束后，Netty又会做一系列状态判断来决定是否中断本次轮询，如果满足如下条件就中断本次轮询：

条件一：检测到IO事件

条件二：被用户主动唤醒

条件三：普通任务队列里有任务需要执行

条件四：第一个定时任务即将要被执行

### (5)避免JDK的空轮询Bug

JDK空轮询Bug会导致selector一直空轮询，最终导致CPU的利用率100%。

#### 一.Netty避免JDK空轮询的方法

首先每次执行selector.select(timeoutMillis)之前都会记录开始时间，在阻塞式select操作后记录结束时间。

然后判断阻塞式select操作是否持续了至少timeoutMillis时间。如果阻塞式select操作持续的时间大于等于timeoutMillis，说明这是一次有效的轮询，于是重置selectCnt为1。如果阻塞式select操作持续的时间小于timeoutMillis，则说明可能触发了JDK的空轮询Bug，于是自增selectCnt。当持续时间很短的select操作的次数selectCnt超过了512次，那么就重建Selector。

#### 二.重建Selector的逻辑

重建Selector的逻辑就是通过openSelector()方法创建一个新的Selector，然后执行一个无限的for循环，只要执行过程中出现一次并发修改SelectionKeys异常，那么就重新开始转移，直到转移完成。

具体的转移步骤为：首先拿到有效的key，然后取消该key在旧Selector上的事件注册。接着将该key对应的Channel注册到新的Selector上，最后重新绑定Channel和新的key。

### (6)执行一次事件轮询的总结

关于Reactor线程的select操作所做的事情：

简单来说就是：不断轮询是否有IO事件发生，并且在轮询过程中不断检查是否有任务需要执行，从而保证Netty任务队列中的任务都能够及时执行，以及在轮询过程中会巧妙地使用一个计数器来避开JDK的空轮询Bug。

详细来说就是：NioEventLoop的select()方法首先会判断有没有定时任务快到要开始的时间了、普通任务队列taskQueue里是否存在任务。如果有就调用selector.selectNow()进行非阻塞式的select操作，如果都没有就调用selector.select(timeoutMillis)进行阻塞式select操作。在阻塞式select操作结束后，会判断这次select操作是否阻塞了timeoutMillis这么长时间。如果没有阻塞那么长时间就表明可能触发了JDK的空轮询Bug，接下来就会继续判断可能触发空轮询Bug的次数是否达到了512次，如果达到了就通过替换原来Selector的方式去避开空轮询Bug。

## 22.Reactor线程处理产生IO事件的Channel

### (1)处理IO事件的关键逻辑

Reactor线程执行的第一步是轮询出注册在Selector上的IO事件，第二步便是处理这些IO事件了。

processSelectedKeys()的关键逻辑包含两部分：针对selectedKeys的优化、processSelectedKeysOptimized()方法真正处理IO事件。

### (2)Netty对selectedKeys的优化

Netty对selectedKeys的所有优化都是在NioEventLoop的openSelector()方法中体现的。

这个优化指的是：Selector.select()操作每次都会把就绪状态的IO事件添加到Selector底层的两个HashSet成员变量中，而Netty会通过反射的方式将Selector中用于存放SelectionKey的HashSet替换成数组，使得添加SelectionKey的时间复杂度由HashSet的O(n)降为数组的O(1)。

具体来说就是：NioEventLoop的成员变量selectedKeys是一个SelectedSelectionKeySet对象，会在NioEventLoop的openSelector()方法中创建。之后openSelector()方法会通过反射将selectedKeys与Selector的两个成员变量绑定。SelectedSelectionKeySet继承了AbstractSet，但底层是使用数组来存放SelectionKey的。

### (3)处理IO事件的过程说明

**说明一：** 首先取出IO事件。IO事件是以数组的形式从selectedKeys中取的，其对应的Channel则由SelectionKey的attachment()方法返回。此时可以体会到优化过的selectedKeys的好处。因为遍历时遍历的是数组，相对JDK原生的HashSet，效率有所提高。

拿到当前的SelectionKey之后，便将selectedKeys[i]设置为null，这样做是为了方便GC。因为假设一个NioEventLoop平均每次轮询出N个IO事件，高峰期轮询出3N个事件，那么selectedKeys的物理长度要大于等于3N。如果每次处理这些key时不设置selectedKeys[i]为null，那么高峰期一过，这些保存在数组尾部的selectedKeys[i]对应的SelectionKey将一直无法被回收，虽然SelectionKey对应的对象可能不大，但其关联的attachment则可能很大。这些对象如果一直存活无法回收，就可能发生内存泄露。

**说明二：** 然后获取当前SelectionKey对应的attachment。这个attachement就是取出的IO事件对应的Channel了，于是接下来就可以处理该Channel了。

由于Netty在注册服务端Channel时，会将AbstractNioChannel内部的SelectableChannel对象注册到Selector对象上，并且将AbstractNioChannel作为SelectableChannel对象的一个attachment附属。所以当JDK轮询出某个SelectableChannel有IO事件时，就可以通过attachment()方法直接取出AbstractNioChannel进行操作了。

**说明三：** 接着便会调用processSelectedKey()方法对SelectionKey和AbstractNioChannel进行处理。Netty有两大类Channel：一个是NioServerSocketChannel，由bossGroup处理。另一个是NioSocketChannel，由workerGroup处理。对于boss的NioEventLoop来说，轮询到的是连接事件。对于worker的NioEventLoop来说，轮询到的是读写事件。

**说明四：** 最后会判断是否再进行一次轮询。NioEventLoop的run()方法每次在轮询到IO事件后，都会将needsToSelectAgain设置为false。只有当Channel从Selector上移除时，也就是调用NioEventLoop的cancel()方法时，发现被取消的key已经达到256次了，才会将needsToSelectAgain设置为true。当needsToSelectAgain为true，就会调用selectAgain()方法再进行一次轮询。

### (4)处理IO事件的总结

Netty默认情况下会通过反射，将Selector底层用于存放SelectionKey的两个HashSet，转化成一个数组来提升处理IO事件的效率。

在处理每一个SelectionKey时都会拿到对应的一个attachment，而这个attachment就是在服务端Channel注册Selector时所绑定的一个AbstractNioChannel。所以在处理每一个SelectionKey时，都可以找到对应的AbstractNioChannel，然后通过Pipeline将处理串行到ChannelHandler，回调到用户的方法。

## 23.Reactor线程处理任务队列之添加任务

### (1)Reactor线程执行一次事件轮询的过程

Reactor线程通过NioEventLoop的run()方法每进行一次事件轮询，首先会调用select()方法尝试检测出IO事件，然后会调用processSelectedKeys()方法处理检测出的IO事件。其中IO事件主要包括新连接接入事件和连接的数据读写事件，最后会调用runAllTasks()方法处理任务队列中的异步任务。

### (2)任务的分类和添加说明

runAllTasks()方法中的Task包括普通任务和定时任务，分别存放于NioEventLoop不同的队列里。一个是普通的任务队列MpscQueue，另一个是定时的任务队列PriorityQueue。

普通的任务队列MpscQueue在创建NioEventLoop时创建的，然后在外部线程调用NioEventLoop的execute()方法时，会调用addTask()方法将Task保存到普通的任务队列里。

定时的任务队列PriorityQueue则是在添加定时任务时创建的，然后在外部线程调用NioEventLoop的schedule()方法时，会调用scheduleTaskQueue().add()方法将Task保存到定时的任务队列里。

### (3)普通任务的添加

当通过ctx.channel().eventLoop().execute(...)自定义普通任务，或者通过非Reactor线程(外部线程)调用Channel的各类方法时，最后都会执行到SingleThreadEventExecutor的execute()方法。

**场景一：用户自定义普通任务**

不管是外部线程还是Reactor线程执行NioEventLoop的execute()方法，都会调用NioEventLoop的addTask()方法，然后调用offerTask()方法。而offerTask()方法会使用一个taskQueue将Task保存起来。这个taskQueue其实就是一个MPSC队列，每一个NioEventLoop都会有一个MPSC队列。

Netty使用MPSC队列可以方便地将外部线程的异步任务进行聚集，然后在Reactor线程内部用单线程来批量执行以提升性能。可以借鉴Netty的这种任务执行模式来处理类似多线程数据聚合，定时上报应用。

**场景二：外部线程调用Channel的方法**

这个场景是在业务线程里，根据用户标识找到对应的Channel，然后调用Channel的write()方法向该用户推送消息。

外部线程在调用Channel的write()方法时，executor.inEventLoop()会返回false。于是会将write操作封装成一个WriteTask，然后调用safeExecute()方法来执行。默认情况下会获取Channel对应的NIO线程，然后作为参数传入safeExecute()方法中进行执行，从而确保任务会由Channel对应的NIO线程执行，通过单线程执行来实现线程安全。

### (4)定时任务的添加

通常使用ctx.channel().eventLoop().schedule(..)自定义定时任务，其中schedule()方法会通过scheduledTaskQueue().add(task)来添加定时任务。首先scheduledTaskQueue()方法会返回一个优先级队列，然后通过该优先级队列的add()方法将定时任务对象加入到队列中。

注意，这里可以直接使用优先级队列而不用考虑多线程并发问题的原因如下。如果是外部线程调用schedule()方法添加定时任务，那么Netty会将添加定时任务这个逻辑封装成一个普通的Task。这个Task的任务是一个"添加某定时任务"的任务，而不是添加某定时任务。这样，对优先级队列的访问就变成单线程了，也就是只有Reactor线程会访问，从而不存在多线程并发问题。

## 24.Reactor线程处理任务队列之执行任务

### (1)runAllTasks()方法需要传入超时时间

SingleThreadEventExecutor的runAllTasks()方法需要传入参数timeoutNanos，表示尽量在timeoutNanos时间内将所有的任务都取出来执行一遍。因为如果Reactor线程在执行任务时停留的时间过长，那么将会累积许多IO事件无法及时处理，从而导致大量客户端请求阻塞。因此Netty会精细控制内部任务队列的执行时间。

### (2)Reactor线程执行任务的步骤

**一.任务聚合：** 转移定时任务到MPSC队列，这里只是将快到期的定时任务转移到MPSC队列里。

**二.时间计算：** 计算本轮任务执行的截止时间，此时所有截止时间已到达的定时任务均被填充到普通的任务队列(MPSC队列)里了。

**三.任务执行：** 首先不抛异常地同步执行任务，然后累加当前已执行的任务数，接着每隔64次计算一下当前时间是否已超截止时间，最后判断本轮任务是否已经执行完毕。

### (3)Netty性能优化之间隔策略

假设任务队列里有海量的小任务，如果每次执行完任务都需要判断是否到截止时间，那么效率是比较低的。所以Netty选择通过每隔64个任务才判断一下是否到截止时间，那么效率就会高很多。

### (4)NioEventLoop.run()方法执行任务总结

Netty里的任务分两种：一种是普通的任务，另一种是定时的任务。Netty在执行这些任务时首先会把定时任务聚合到普通任务队列里，然后再从普通任务队列里获取任务逐个执行，并且是每执行64个任务之后才判断一下当前时间是否超过最大允许执行时间。如果超过就直接中断，中断之后就会进行下一次NioEventLoop.run()方法的for循环。

## 25.NioEventLoop总结

### (1)NioEventLoop的执行流程总结

一.NioEventLoop在执行过程中首先会不断检测是否有IO事件发生，然后如果检测出有IO事件就处理IO事件，接着处理完IO事件之后再处理外部线程提交过来的异步任务。

二.在检测是否有IO事件发生时，为了保证异步任务的及时处理，只要有任务要处理，那么就立即停止检测去处理任务。

三.外部线程异步执行的任务分为两种：普通任务和定时任务。这两种任务分别保存到MPSC队列和优先级队列，而优先级队列中的任务最终都会转移到MPSC队列里进行处理。

四.Netty每处理完64个任务才会检查一次是否超时而退出执行任务的循环。

### (2)Reactor线程模型总结

一.NioEventLoopGroup在用户代码中被创建，默认情况下会创建两倍CPU核数个NioEventLoop。

二.NioEventLoop是懒启动的，bossNioEventLoop在服务端启动时启动，workerNioEventLoop在新连接接入时启动。

三.当CPU核数为2的幂时，为每一个新连接绑定NioEventLoop之后，都会做一个取模运算转位与运算的优化。

四.每个连接都对应一个Channel，每个Channel都绑定唯一一个NioEventLoop，一个NioEventLoop可能会被绑定多个Channel，每个NioEventLoop都对应一个FastThreadLocalThread线程实体和一个Selector。因此单个连接的所有操作都是在一个线程上执行的，所以是线程安全的。

五.每个NioEventLoop都对应一个Selector，这个Selector可以批量处理注册到它上面的Channel。

六.每个NioEventLoop的执行过程都包括事件检测、事件处理以及异步任务的执行。

七.用户线程池在对Channel进行一些操作时均为线程安全的。这是因为Netty会把外部线程的操作都封装成一个Task放入这个Channel绑定的NioEventLoop中的MPSC队列，然后在该NioEventLoop的执行过程(事件循环)的第三个过程中进行串行执行。

八.所以NioEventLoop的职责不仅仅是处理网络IO事件，用户自定义的普通任务和定时任务也会统一由NioEventLoop处理，从而实现线程模型的统一。

九.从调度层看，也不存在从NioEventLoop线程中再启动其他类型的线程用于异步执行另外的任务，从而避免了多线程并发操作和锁竞争，提升了IO线程的处理性能和调度性能。

### (3)NioEventLoop创建启动执行的总结

一.用户在创建bossGroup和workerGroup时，NioEventLoopGroup被创建，默认不传参时会创建两倍CPU核数个NioEventLoop。

二.每个NioEventLoopGroup都有一个线程执行器executor和一个线程选择器chooser。线程选择器chooser用于进行线程分配，它会针对NioEventLoop的个数进行优化。

三.NioEventLoop在创建时会创建一个Selector和一个MPSC任务队列，创建Selector时Netty会通过反射的方式用数组去替换Selector里的两个HashSet数据结构。

四.Netty的NioEventLoop在首次调用execute()方法时会启动线程，这个线程是一个FastThreadLocalThread对象。启动线程后，Netty会将创建完成的线程保存到成员变量，以便能判断执行NioEventLoop里的逻辑的线程是否是这个创建好的线程。

五.NioEventLoop的执行逻辑在run()方法里，主要包括3部分：第一是检测IO事件，第二是处理IO事件，第三是执行异步任务。

## 26.关于ByteBuf的问题整理

**问题一：Netty的内存类别有哪些？**

答：ByteBuf可以按三个维度来进行分类：一个是堆内和堆外，一个是Unsafe和非Unsafe，一个是Pooled和非Pooled。

堆内是基于byte字节数组内存进行分配，堆外是基于JDK的DirectByteBuffer内存进行分配。

Unsafe是通过JDK的一个unsafe对象基于物理内存地址进行数据读写，非Unsafe是直接调用JDK的API进行数据读写。

Pooled是预先分配的一整块内存，分配时直接用一定的算法从这整块内存里取出一块连续内存。UnPooled是每次分配内存都直接申请内存。

**问题二：如何减少多线程内存分配之间的竞争？如何确保多线程对于同一内存分配不产生冲突？**

答：一个内存分配器里维护着一个PoolArena数组，所有的内存分配都在PoolArena上进行。通过一个PoolThreadCache对象将线程和PoolArena进行一一绑定(利用ThreadLocal原理)。默认一个线程对应一个PoolArena，这样就能做到多线程内存分配相互不受影响。

**问题三：不同大小的内存是如何进行分配的？**

答：对于Page级别的内存分配与释放是直接通过完全二叉树的标记来寻找某一个连续内存的。对于Page级别以下的内存分配与释放，首先是找到一个Page，然后把此Page按照SubPage大小进行划分，最后通过位图的方式来进行内存分配与释放。

不管是Page级别的内存还是SubPage级别的内存，当内存被释放掉时有可能会被加入到不同级别的一个缓存队列供下一次分配使用。

## 27.零拷贝技术总结

### (1)零拷贝简介

零拷贝技术是指计算机执行操作时，CPU不需要先将数据从某处内存复制到另一个特定区域。这种技术通常用于通过网络传输文件时节省CPU周期和内存带宽。

零拷贝技术的主要原理是通过减少数据在用户空间与内核空间之间切换模式的次数，以及减少数据的拷贝次数，来提高数据传输效率。例如，当需要读取一个文件并通过网络发送它时，传统方式下每个读/写周期都需要复制两次数据和切换两次上下文，而零拷贝技术可以将这两个操作合并为一个系统调用(如Linux中的sendfile方法)，从而减少上下文切换次数和数据拷贝次数。

在实现零拷贝时，通常依赖于直接存储器访问(DMA)和内存管理单元(MMU)等硬件支持。DMA控制器可以接管数据读写请求，减少CPU负担，使得CPU能够更高效地完成其他任务。内存管理单元则可以实现内存映射，使得用户空间可以直接访问内核空间的数据，从而避免数据拷贝操作。

零拷贝技术的优点包括提高数据传输效率、减少CPU和内存的使用率、降低上下文切换次数等。然而，零拷贝技术也存在一些缺点，如需要特定的硬件支持、增加了系统的复杂性等。

在Java中，可以通过java.nio.channels包中的FileChannel类来实现零拷贝。其中，transferTo()方法可以将数据从文件通道直接传输到另一个通道，无需将数据先复制到用户空间再进行传输。

总之，零拷贝技术是一种优化数据传输效率的技术，它通过减少数据拷贝和上下文切换次数来提高系统的性能。在实际应用中，需要根据具体的场景和需求来选择合适的零拷贝技术实现方式。

### (2)零拷贝的实现方式

零拷贝技术的主要目的是减少或消除数据在传输或处理过程中的内存拷贝次数，以提高性能。以下是实现零拷贝的几种主要方式：

**方式一.直接内存访问(DMA)：** DMA是一种硬件技术，允许外设(如网卡)直接访问内存，绕过CPU的参与，从而实现高速数据传输。数据传输过程中，DMA控制器会接管数据传输的任务，从源地址读取数据并直接写入目的地址，无需CPU的干预。

**方式二.sendfile系统调用：** sendfile系统调用可以在内核态中直接将文件内容发送到网络设备的缓冲区，避免了数据在用户态和内核态之间的拷贝。它通过减少系统调用的次数和内存拷贝的次数，提高了数据传输的效率。

**方式三.splice系统调用：** splice系统调用可以将一个文件描述符的数据直接传输到另一个文件描述符，也可以将数据从一个文件描述符传输到网络设备的缓冲区。它同样避免了中间的拷贝过程，提高了数据传输的效率。

**方式四.mmap和write系统调用：** mmap系统调用可以将文件映射到内存中，然后使用write系统调用将内存中的数据直接发送到网络设备的缓冲区。这种方式避免了数据在用户态和内核态之间的拷贝，减少了系统调用的开销。

**方式五.内存区域映射技术：** 这种方式是在系统内核中存储数据报的内存区域映射到检测程序的应用程序空间，或者是在用户空间建立一缓存，并将其映射到内核空间。检测程序直接对这块内存进行访问，从而减少了系统内核向用户空间的内存拷贝，同时减少了系统调用的开销。

需要注意的是，零拷贝并不是不复制数据，而是减少不必要的数据拷贝次数，从而提升代码性能。在实际应用中，应该根据具体的应用场景和性能要求来选择最合适的零拷贝方式。

### (3)Java中零拷贝的实现方式

在Java中，零拷贝技术主要用于减少数据在传输或处理过程中的内存拷贝次数，从而提高性能。以下是Java中实现零拷贝的几种主要方式：

FileChannel.transferTo()和FileChannel.transferFrom()：这两个方法允许文件通道FileChannel之间直接传输数据，而无需先将数据拷贝到用户空间的缓冲区中。这通常用于网络套接字SocketChannel和文件通道之间的数据传输。

ByteBuffer.allocateDirect()：使用直接内存(Direct ByteBuffer)可以减少从用户空间到内核空间的内存拷贝。直接缓冲区的内容驻留在JVM堆外的内存，这允许应用程序直接访问物理内存，从而提高了I/O操作的性能。

Linux下的Sendfile系统调用：虽然这不是Java直接提供的API，但可以通过Java的本地方法接口(JNI)或Java NIO.2的Files.copy()方法(在某些实现中)来使用。Sendfile允许进程将文件数据从一个文件描述符发送到另一个文件描述符，而无需将数据拷贝到用户空间。

mmap内存映射文件：内存映射文件(Memory-Mapped Files)是一种将文件或文件的一部分映射到进程地址空间的技术。通过内存映射，可以像访问内存一样访问文件数据，从而避免了不必要的内存拷贝。Java NIO提供了MappedByteBuffer类来支持内存映射文件。****
