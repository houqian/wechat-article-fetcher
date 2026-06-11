# 面试准备之Netty要点总结二

> **公众号**: 东阳马生架构  
> **发布时间**: 2025-09-16 09:00  

**大纲(11635字)**

- 1.关于Netty客户端连接接入问题整理
- 2.Reactor线程模型和服务端启动流程
- 3.Netty新连接接入的整体处理逻辑
- 4.新连接接入之检测新连接
- 5.新连接接入之创建NioSocketChannel
- 6.新连接接入之绑定NioEventLoop线程
- 7.新连接接入之注册Selector和注册读事件
- 8.注册Reactor线程总结
- 9.新连接接入总结
- 10.Pipeline和Handler的作用和构成
- 11.ChannelHandler的分类
- 12.几个特殊的ChannelHandler
- 13.ChannelHandler的生命周期
- 14.ChannelPipeline的事件处理
- 15.关于ChannelPipeline的问题整理
- 16.ChannelPipeline主要包括三部分内容
- 17.ChannelPipeline的初始化
- 18.ChannelPipeline添加ChannelHandler
- 19.ChannelPipeline删除ChannelHandler
- 20.Inbound事件的传播
- 21.Outbound事件的传播
- 22.ChannelPipeline中异常的传播
- 23.ChannelPipeline总结


## 1.关于Netty客户端连接接入问题整理

**一.Netty是在哪里检测有新连接接入的？**

答：boss线程第一个过程轮询出ACCEPT事件，然后boss线程第二个过程通过JDK底层Channel的accept()方法创建一条连接。

**二.新连接是怎样注册到NioEventLoop线程的？**

答：boss线程调用chooser的next()方法拿到一个NioEventLoop，然后将新连接注册到NioEventLoop的Selector上。

## 2.Reactor线程模型和服务端启动流程

### (1)Netty中的Reactor线程模型

Netty中最核心的是两种类型的Reactor线程，这两种类型的Reactor线程可以看作Netty中的两组发动机，驱动着Netty整个框架的运转。一种类型是boss线程，专门用来接收新连接，然后将连接封装成Channel对象传递给worker线程。另一种类型是worker线程，专门用来处理连接上的数据读写。

boss线程和worker线程所做的事情均分为3步。第一是轮询注册在Selector上的IO事件，第二是处理IO事件，第三是执行异步任务。对boss线程来说，第一步轮询出来的基本都是ACCEPT事件，表示有新的连接。对worker线程来说，第一步轮询出来的基本都是READ事件或WRITE事件，表示网络的读写。

### (2)服务端启动流程

服务端是在用户线程中开启的，通过ServerBootstrap.bind()方法，在第一次添加异步任务的时候启动boss线程。启动之后，当前服务器就可以开启监听。

## 3.Netty新连接接入的整体处理逻辑

新连接接入的处理总体就是：检测新连接 \+ 注册Reactor线程，具体就可以分为如下4个过程。

#### 一.检测新连接

服务端Channel对应的NioEventLoop会轮询该Channel绑定的Selector中是否发生了ACCEPT事件，如果是则说明有新连接接入了。

#### 二.创建NioSocketChannel

检测出新连接之后，便会基于JDK NIO的Channel创建出一个NioSocketChannel，也就是客户端Channel。

#### 三.分配worker线程及注册Selector

接着Netty给客户端Channel分配一个NioEventLoop，也就是分配worker线程。然后把这个客户端Channel注册到这个NioEventLoop对应的Selector上，之后这个客户端Channel的读写事件都会由这个NioEventLoop进行处理。

#### 四.向Selector注册读事件

最后向这个客户端Channel对应的Selector注册READ事件，注册的逻辑和服务端Channel启动时注册ACCEPT事件的一样。

## 4.新连接接入之检测新连接

### (1)何时会检测到有新连接

当调用辅助启动类ServerBootstrap的bind()方法启动服务端之后，服务端的Channel也就是NioServerSocketChannel就会注册到boss的Reactor线程上。boss的Reactor线程会不断检测是否有新的事件，直到检测出有ACCEPT事件发生即有新连接接入。此时boss的Reactor线程将通过服务端Channel的unsafe变量来进行实际操作。注意：服务端Channel的unsafe变量是一个NioMessageUnsafe对象，客户端Channel的unsafe变量是一个NioByteUnsafe对象。

### (2)新连接接入的流程梳理

#### 一.NioMessageUnsafe的read()方法说明

首先使用一条断言确保该read()方法必须来自Reactor线程调用，然后获得Channel对应的Pipeline和RecvByteBufAllocator.Handle。

接着调用NioServerSocketChannel的doReadMessages()方法不断地读取新连接到readBuf容器。然后使用for循环处理readBuf容器里的新连接，也就是通过pipeline.fireChannelRead()方法让每个新连接都经过一层服务端Channel的Pipeline逻辑处理，最后清理容器并执行pipeline.fireChannelReadComplete()。

#### 二.新连接接入的流程梳理

首先会从服务端Channel对应的NioEventLoop的run()方法的第二个步骤处理IO事件开始。然后会调用服务端Channel的unsafe变量的read()方法，也就是NioMessageUnsafe对象的read()方法。

接着循环调用NioServerSocketChannel的doReadMessages()方法来创建新连接对象NioSocketChannel。其中创建新连接对象最核心的方法就是调用JDK Channel的accept()方法来创建JDK Channel。与服务端启动一样，Netty会把JDK底层Channel包装成Netty自定义的NioSocketChannel。

```javascript
NioEventLoop.processSelectedKeys(key, channel) //入口
  NioMessageUnsafe.read() //新连接接入处理
    NioServerSocketChannel.doReadMessages() //创建新连接对象NioSocketChannel
      javaChannel.accept() //创建JDK Channel
```

### (3)新连接接入的总结

在服务端Channel对应的NioEventLoop的run()方法的processSelectedKeys()方法里，发现产生的IO事件是ACCEPT事件之后，会通过JDK Channel的accept()方法取创建JDK的Channel，并把它包装成Netty自定义的NioSocketChannel。在这个过程中会通过一个RecvByteBufAllocator.Handle对象控制连接接入的速率，默认一次性读取16个连接。

## 5.新连接接入之创建NioSocketChannel

### (1)doReadMessages()方法相关说明

首先通过javaChannel().accept()创建一个JDK的Channel，即客户端Channel。然后把服务端Channel和这个客户端Channel作为参数传入NioSocketChannel的构造方法中，从而把JDK的Channel封装成Netty自定义的NioSocketChannel。最后把封装好的NioSocketChannel添加到一个List里，以便外层可以遍历List进行处理。

### (2)创建NioSocketChannel的流程梳理

NioServerSocketChannel和NioSocketChannel都有同一个父类AbstractNioChannel，所以创建NioSocketChannel的模版和创建NioServerSocketChannel保持一致。

但要注意的是：客户端Channel是通过new关键字创建的，服务端Channel是通过反射的方式创建的。此外，Nagle算法会让小数据包尽量聚合成大的数据包再发送出去，Netty为了使数据能够及时发送出去会禁止该算法。

```javascript
new NioSocketChannel(p, ch) //入口，客户端Channel是通过new关键字创建的，服务端Channel是通过反射的方式创建的
new AbstractNioByteChannel(p, ch) //逐层调用父类的构造方法
new AbstractNioChannel(p, ch, op_read) //逐层调用父类的构造方法
        ch.configureBlocking(false) + save op //配置此Channel为非阻塞，以及将感兴趣的读事件保存到成员变量以方便后续注册到Selector
new AbstractChannel() //创建Channel的相关组件：
          newId() //id作为Channel的唯一标识
            newUnsafe() //unsafe用来进行底层数据读写
            newChannelPipeline() //pipeline作为业务逻辑载体
new NioSocketChannelConfig() //创建和NioSocketChannel绑定的配置类
    setTcpNoDelay(true) //禁止Nagle算法
```

### (3)创建NioSocketChannel的总结

创建NioSocketChannel的逻辑可以分成两部分。

第一部分是逐层调用父类的构造方法，其中会设置这个客户端Channel的阻塞模式为false，然后再把感兴趣的读事件OP_READ保存到这个Channel的成员变量中以便后续注册到Selector，接着会创建一系列的组件，包括作为Channel唯一标识的Id组件、用来进行底层数据读写的unsafe组件、用来作为业务逻辑载体的pipeline组件。

第二部分是创建和这个客户端Channel相关的config对象，该config对象会设置关闭Nagle算法，从而让小数据包尽快发送出去、降低延时。

### (4)Netty中的Channel分类

说明一：Channel继承Comparable表示Channel是一个可以比较的对象。

说明二：Channel继承AttributeMap表示Channel是一个可以绑定属性的对象，我们经常在代码中使用channel.attr(...)来给Channel绑定属性，其实就是把属性设置到AttributeMap中。

说明三：AbstractChannel用来实现Channel的大部分方法，在AbstractChannel的构造方法中会创建一个Channel对象所包含的基本组件，这里的Channel通常是指SocketChannel和ServerSocketChannel。

说明四：AbstractNioChannel继承了AbstractChannel，然后通过Selector处理一些NIO相关的操作。比如它会保存JDK底层SelectableChannel的引用，并且在构造方法中设置Channel为非阻塞模式。注意：设置非阻塞模式是NIO编程必须的。

说明五：Netty的两大Channel是指：服务端的NioServerSocketChannel和客户端NioSocketChannel，分别对应着服务端接收新连接的过程和服务端新连接读写数据的过程。

说明六：服务端Channel和客户端Channel的区别是：服务端Channel通过反射方式创建，客户端Channel通过new关键字创建。服务端Channel注册的是ACCEPT事件，对应接收新连接。客户端Channel注册的是READ事件，对应新连接读写。服务端Channel和客户端Channel底层都会依赖一个unsafe对象，这个unsafe对象会用来实现这两种Channel底层的数据读写操作。对于读操作，服务端的读是读一条连接doReadMessages()，客户端的读是读取数据doReadBytes()。最后每一个Channel都会绑定一个ChannelConfig，每一个ChannelConfig都会实现Channel的一些配置。

## 6.新连接接入之绑定NioEventLoop线程

### (1)将新连接绑定到Reactor线程的入口

创建完NioSocketChannel后，接下来便要对NioSocketChannel进行一些设置，并且需要将它绑定到一个正在执行的Reactor线程中。

NioMessageUnsafe.read()方法里的readBuf容器会承载着所有新建的连接，如果某个时刻Netty轮询到多个连接，那么通过使用for循环就可以批量处理这些NioSocketChannel连接。

处理每个NioSocketChannel连接时，是通过NioServerSocketChannel的pipeline的fireChannelRead()方法来处理的。

### (2)服务端Channel的Pipeline介绍

在Netty的各种类型的Channel中，都会包含一个Pipeline。Pipeline可理解为一条流水线，流水线有起点有结束，中间还会有各种各样的流水线关卡。对Channel的处理会在流水线的起点开始，然后经过各个流水线关卡的加工，最后到达流水线的终点结束。

流水线Pipeline的开始是HeadContext，结束是TailContext。HeadContext中会调用Unsafe进行具体的操作，TailContext中会向用户抛出流水线Pipeline中未处理异常和未处理消息的警告。

在服务端的启动过程中，Netty会给服务端Channel自动添加一个Pipeline处理器ServerBootstrapAcceptor，并且会将用户代码中设置的一系列参数传入到这个ServerBootstrapAcceptor的构造方法中。服务端Channel的Pipeline在传播ChannelRead事件时首先会从HeadContext处理器开始，然后传播到ServerBootstrapAcceptor处理器，最后传播到TailContext处理器结束。

### (3)服务端Channel默认的Pipeline处理器

首先，服务端启动时会给服务端Channel的Pipeline添加一个ServerBootstrapAcceptor处理器。然后，新连接接入调用到服务端Channel的Pipeline的fireChannelRead()方法时，便会触发调用ServerBootstrapAcceptor处理器的channelRead()方法。最终会调用NioEventLoop的register()方法注册这个新连接Channel，即给新连接Channel绑定一个Reactor线程。

### (4)服务端Channel处理新连接的步骤

ServerBootstrapAcceptor处理新连接的步骤：

**步骤一：给客户端Channel添加childHandler 。**给客户端Channel添加childHandler也就是将用户自定义的childHandler添加到新连接的pipeline里。

pipeline.fireChannelRead(NioSocketChannel)最终会调用到ServerBootstrapAcceptor的channelRead()方法，而且这个channelRead()方法一上来就会把入参的msg强制转换为Channel。

拿到新连接的Channel后就可以拿到其对应的Pipeline，这个Pipeline是在调用AbstractChannel构造方法时创建的。于是可以将用户代码中的childHandler添加到Pipeline中，而childHandler其实就是用户代码中的ChannelInitializer。所以新连接Channel的Pipeline的构成是：Head -> ChannelInitializer -> Tail。

**步骤二：设置客户端Channel的options和attr 。**所设置的childOptions和childAttrs也是在用户代码中设置的，这些设置项最终会传递到ServerBootstrapAcceptor的channelRead()方法中进行具体设置。

**步骤三：选择NioEventLoop绑定客户端Channel 。**childGroup.register(child)中的childGroup就是用户代码里创建的workerNioEventLoopGroup。NioEventLoopGroup的register()方法会调用next()由其父类通过线程选择器chooser返回一个NioEventLoop。所以childGroup.register(child)最终会调用到NioEventLoop的register()方法，这和注册服务端Channel时调用config().group().register(channel)一样。

### (5)总结

服务端Channel在检测到新连接并且创建完客户端Channel后，会通过服务端Channel的Pipeline的一个处理器ServerBootstrapAcceptor做一些处理。这些处理包括：给客户端Channel的Pipeline添加childHandler处理器、设置客户端Channel的options和attrs、调用线程选择器chooser选择一个NioEventLoop进行绑定。绑定时会将该客户端Channel注册到NioEventLoop的Selector上，此时还不会关心事件。

## 7.新连接接入之注册Selector和注册读事件

NioEventLoop的register()方法是由其父类SingleThreadEventLoop实现的，并最终调用到AbstractChannel的内部类AbstractUnsafe的register0()方法。

**步骤一：注册Selector 。**和服务端启动过程一样，先调用AbstractNioChannel的doRegister()方法进行注册。其中javaChannel().register()会将新连接NioSocketChannel绑定到Reactor线程的Selector上，这样后续这个新连接NioSocketChannel所有的事件都由绑定的Reactor线程的Selector来轮询。

**步骤二：配置自定义Handler 。**此时新连接NioSocketChannel的Pipeline中有三个Handler：Head -> ChannelInitializer -> Tail。invokeHandlerAddedIfNeeded()最终会调用ChannelInitializer的handlerAdded()方法。

**步骤三：传播ChannelRegistered事件 。**pipeline.fireChannelRegistered()会把新连接的注册事件从HeadContext开始往下传播，调用每一个ChannelHandler的channelRegistered()方法。

**步骤四：注册读事件 。**接着还会传播ChannelActive事件。传播完ChannelActive事件后，便会继续调用HeadContetx的readIfIsAutoRead()方法注册读事件。由于创建NioSocketChannel时已将SelectionKey.OP_READ的事件代码保存到其成员变量中，所以AbstractNioChannel的doBeginRead()方法，就可以将SelectionKey.OP_READ事件注册到Selector中完成读事件的注册。

## 8.注册Reactor线程总结

一.首先当boss Reactor线程在检测到有ACCEPT事件之后，会创建JDK底层的Channel。

二.然后使用一个NioSocketChannel包装JDK底层的Channel，把用户设置的ChannelOption、ChannelAttr、ChannelHandler都设置到该NioSocketChannel中。

三.接着从worker Reactor线程组中，也就是worker NioEventLoopGroup中，通过线程选择器chooser选择一个NioEventLoop出来。

四.最后把NioSocketChannel包装的JDK底层Channel当作key，自身NioSocketChannel当作attachment，注册到NioEventLoop对应的Selector上。这样后续有读写事件发生时，就可以从底层Channel直接获得attachment即NioSocketChannel来进行读写数据的逻辑处理。

## 9.新连接接入总结

新连接接入整体可以分为两部分：一是检测新连接，二是注册Reactor线程。

一.首先在Netty服务端的Channel(也就是NioServerSocketChannel)绑定的NioEventLoop(也就是boss线程)中，轮询到ACCEPT事件。

二.然后调用JDK的服务端Channel的accept()方法获取一个JDK的客户端Channel，并且将其封装成Netty的客户端Channel(即NioSocketChannel)。

三.封装过程中会创建这个NioSocketChannel一系列的组件，如unsafe组件和pipeline组件。unsafe组件主要用于进行Channel的读写，pipeline组件主要用于处理Channel数据的业务逻辑。

四.接着Netty服务端Channel的Pipeline的一个处理器ServerBootstrapAcceptor，会给当前Netty客户端Channel分配一个NioEventLoop并将客户端Channel绑定到Selector上。

五.最后会传播ChannelRegistered事件和ChannelActive事件，并将客户端Channel的读事件注册到Selector上。

至此，新连接NioSocketChannel便可以开始正常读写数据了。

## 10.Pipeline和Handler的作用和构成

### (1)Pipeline和Handler的作用

可以在处理复杂的业务逻辑时避免if else的泛滥，可以实现对业务逻辑的模块化处理，不同的逻辑放置到单独的类中进行处理。最后将这些逻辑串联起来，形成一个完整的逻辑处理链。Netty通过责任链模式来组织代码逻辑，能够支持逻辑的动态添加和删除，能够支持各类协议的扩展。

### (2)Pipeline和Handler的构成

在Netty里，一个连接对应着一个Channel。这个Channel的所有处理逻辑都在一个叫ChannelPipeline的对象里，ChannelPipeline是双向链表结构，它和Channel之间是一对一的关系。ChannelPipeline里的每个结点都是一个ChannelHandlerContext对象，这个ChannelHandlerContext对象能够获得和Channel相关的所有上下文信息。每个ChannelHandlerContext对象都包含一个逻辑处理器ChannelHandler，每个逻辑处理器ChannelHandler都处理一块独立的逻辑。

## 11.ChannelHandler的分类

ChannelHandler有两大子接口，分别为Inbound和Outbound类型：第一个子接口是ChannelInboundHandler，用于处理读数据逻辑，最重要的方法是channelRead()。第二个子接口是ChannelOutboundHandler，用于处理写数据逻辑，最重要的方法是write()。

这两个子接口默认的实现分别是：ChannelInboundHandlerAdapter和ChannelOutboundHandlerAdapter。它们分别实现了两个子接口的所有功能，在默认情况下会把读写事件传播到下一个Handler。

InboundHandler的事件通常只会传播到下一个InboundHandler，OutboundHandler的事件通常只会传播到下一个OuboundHandler，InboundHandler的执行顺序与实际addLast的添加顺序相同，OutboundHandler的执行顺序与实际addLast的添加顺序相反。

Inbound事件通常由IO线程触发，如TCP链路的建立事件、关闭事件、读事件、异常通知事件等。其触发方法一般带有fire字眼，如下所示：

ctx.fireChannelRegister()、

ctx.fireChannelActive()、

ctx.fireChannelRead()、

ctx.fireChannelReadComplete()、

ctx.fireChannelInactive()。

Outbound事件通常由用户主动发起的网络IO操作触发，如用户发起的连接操作、绑定操作、消息发送等操作。其触发方法一般如：ctx.bind()、ctx.connect()、ctx.write()、ctx.flush()、ctx.read()、ctx.disconnect()、ctx.close()。

## 12.几个特殊的ChannelHandler

### (1)ChannelInboundHandlerAdapter

ChannelInboundHandlerAdapter主要用于实现ChannelInboundHandler接口的所有方法，这样我们在继承它编写自己的ChannelHandler时就不需要实现ChannelHandler里的每种方法了，从而避免了直接实现ChannelHandler时需要实现其所有方法而导致代码显得冗余和臃肿。

### (2)ChannelOutboundHandlerAdapter

ChannelOutboundHandlerAdapter主要用于实现ChannelOutboundHandler接口的所有方法，这样我们在继承它编写自己的ChannelHandler时就不需要实现ChannelHandler里的每种方法了，从而避免了直接实现ChannelHandler时需要实现其所有方法而导致代码显得冗余和臃肿。

### (3)ByteToMessageDecoder

基于这个ChannelHandler可以实现自定义解码，而不用关心ByteBuf的强转和解码结果的传递。Netty里的ByteBuf默认下使用的是堆外内存，ByteToMessageDecoder会自动进行内存的释放，不用操心内存管理。我们自定义的ChannelHandler继承了ByteToMessageDecoder后，需要实现decode()方法。

### (4)SimpleChannelInboundHandler

基于这个ChannelHandler可以实现每一种指令的处理，不再需要强转、不再有冗长的if else逻辑、不再需要手动传递对象。同时还可以自动释放没有往下传播的ByteBuf，因为我们编写指令处理ChannelHandler时，可能会编写不用关心的if else判断，然后手动传递无法处理的对象至下一个指令处理器。

### (5)MessageToByteEncoder

基于这个ChannelHandler可以实现自定义编码，而不用关心ByteBuf的创建，不用把创建完的ByteBuf进行返回。

## 13.ChannelHandler的生命周期

### (1)ChannelHandler回调方法的执行顺序

ChannelHandler回调方法的执行顺序可以称为ChannelHandler的生命周期。

新建连接时ChannelHandler回调方法的执行顺序是：handlerAdded() -> channelRegistered() -> channelActive() -> channelRead() -> channelReadComplete()。

关闭连接时ChannelHandler回调方法的执行顺序是：channelInactive() -> channelUnregistered() -> handlerRemoved()。

接下来是ChannelHandler具体的回调方法说明，其中一二三的顺序可以参考AbstractChannel的内部类AbstractUnsafe的register0()方法。

#### 一.handlerAdded()

检测到新连接后调用"ch.pipeline().addLast(...)"之后的回调，表示当前Channel已成功添加一个ChannelHandler。

#### 二.channelRegistered()

表示当前Channel已和某个NioEventLoop线程建立了绑定关系，已经创建了一个Reactor线程来处理当前这个Channel的读写。

#### 三.channelActive()

当Channel的Pipeline已经添加完所有的ChannelHandler以及绑定好一个NioEventLoop线程，这个Channel对应的连接才算真正被激活，接下来就会回调该方法。

#### 四.channelRead()

服务端每次收到客户端发送的数据时都会回调该方法，表示有数据可读。

#### 五.channelReadComplete()

服务端每次读完一条完整的数据都会回调该方法，表示数据读取完毕。

#### 六.channelInactive()

表示这个连接已经被关闭，该连接在TCP层已经不再是ESTABLISH状态。

#### 七.channelUnregister()

表示与这个连接对应的NioEventLoop线程移除了对这个连接的处理。

#### 八.handlerRemoved()

表示给这个连接添加的所有的ChannelHandler都被移除了。

### (2)ChannelHandler回调方法的应用场景

一.handlerAdded()方法与handlerRemoved()方法通常可用于一些资源的申请和释放。

二.channelActive()方法与channelInactive()方法表示的是TCP连接的建立与释放，可用于统计单机连接数或IP过滤。

三.channelRead()方法可用于根据自定义协议进行拆包。每次读到一定数据就累加到一个容器里，然后看看能否拆出完整的包。

四.channelReadComplete()方法可用于实现批量刷新。如果每次向客户端写数据都通过writeAndFlush()方法写数据并刷新到底层，其实并不高效。所以可以把调用writeAndFlush()方法的地方换成调用write()方法，然后再在channelReadComplete()方法里调用ctx.channel().flush()。

## 14.ChannelPipeline的事件处理

### (1)消息读取和发送被Pipeline处理的过程

消息的读取和发送被ChannelPipeline的ChannelHandler链拦截和处理的全过程：

一.首先AbstractNioChannel内部类NioUnsafe的read()方法读取ByteBuf时会触发ChannelRead事件，也就是由NioEventLoop线程调用ChannelPipeline的fireChannelRead()方法将ByteBuf消息传输到ChannelPipeline中。

二.然后ByteBuf消息会依次被HeadContext、xxxChannelHandler、...、TailContext拦截处理。在这个过程中，任何ChannelHandler都可以中断当前的流程，结束消息的传递。

三.接着用户可能会调用ChannelHandlerContext的write()方法发送ByteBuf消息。此时ByteBuf消息会从TailContext开始，途径xxxChannelHandler、...、HeadContext，最终被添加到消息发送缓冲区中等待刷新和发送。在这个过程中，任何ChannelHandler都可以中断当前的流程，中断消息的传递。

### (2)ChannelPipeline的主要特征

#### 一.ChannelPipeline支持运行时动态地添加或者删除ChannelHandler

例如业务高峰时对系统做拥塞保护。处于业务高峰期时，则动态地向当前的ChannelPipeline添加ChannelHandler。高峰期过后，再移除ChannelHandler。

#### 二.ChannelPipeline是线程安全的

多个业务线程可以并发操作ChannelPipeline，因为使用了synchronized关键字。但ChannelHandler却不一定是线程安全的，这由用户保证。

## 15.关于ChannelPipeline的问题整理

**一.Netty是如何判断ChannelHandler类型的？**

即如何判断一个ChannelHandler是Inbound类型还是Outbound类型？

答：当调用Pipeline去添加一个ChannelHandler结点时，旧版Netty会使用instanceof关键字来判断该结点是Inbound类型还是Outbound类型，并分别用一个布尔类型的变量来进行标识。新版Netty则使用一个整形的executionMask来具体区分详细的Inbound事件和Outbound事件。这个executionMask对应一个16位的二进制数，是哪一种事件就对应哪一个Mask。

**二.添加ChannelHandler时应遵循什么样的顺序？**

答：Inbound类型的事件传播跟添加ChannelHandler的顺序一样，Outbound类型的事件传播跟添加ChannelHandler的顺序相反。

**三.用户手动触发事件传播的两种方式有什么区别？**

这两种方式是分别是：ctx.writeAndFlush()和ctx.channel().writeAndFlush()。

答：当通过Channel去触发一个事件时，那么该事件会沿整个ChannelPipeline传播。如果是Inbound类型事件，则从HeadContext结点开始向后传播到最后一个Inbound类型的结点。如果是Outbound类型事件，则从TailContext结点开始向前传播到第一个Outbound类型的结点。当通过当前结点去触发一个事件时，那么该事件只会从当前结点开始传播。如果是Inbound类型事件，则从当前结点开始一直向后传播到最后一个Inbound类型的结点。如果是Outbound类型事件，则从当前结点开始一直向前传播到第一个Outbound类型的结点。

## 16.ChannelPipeline主要包括三部分内容

#### 一.ChannelPipeline的初始化

服务端Channel和客户端Channel在何时初始化ChannelPipeline？在初始化时又做了什么事情？

#### 二.添加和删除ChannelHandler

Netty是如何实现业务逻辑处理器动态编织的？

#### 三.事件和异常的传播

读写事件和异常在ChannelPipeline中的传播。

## 17.ChannelPipeline的初始化

### (1)ChannelPipeline的初始化时机

在服务端启动和客户端连接接入的过程中，在创建NioServerSocketChannel和NioSocketChannel时，会逐层执行父类的构造方法，最后执行到AbstractChannel的构造方法。AbstractChannel的构造方法会将Netty的核心组件创建出来。而核心组件中就包含了DefaultChannelPipeline类型的ChannelPipeline组件。

### (2)ChannelPipeline的初始化内容

ChannelPipeline的初始化主要涉及三部分内容：

#### 一.Pipeline在创建Channel时被创建

#### 二.Pipeline的结点是ChannelHandlerContext

#### 三.Pipeline两大哨兵HeadContext和TailContext

### (3)ChannelPipeline的说明

ChannelPipeline中保存了Channel的引用，ChannelPipeline中每个结点都是一个ChannelHandlerContext对象，每个ChannelHandlerContext结点都包裹着一个ChannelHandler执行器，每个ChannelHandlerContext结点都保存了它包裹的执行器ChannelHandler执行操作时所需要的上下文ChannelPipeline。由于ChannelPipeline又保存了Channel的引用，所以每个ChannelHandlerContext结点都可以拿到所有的上下文信息。

ChannelHandlerContext接口多继承自AttributeMap、ChannelInboundInvoker、ChannelOutboundInvoker。

ChannelHandlerContext的关键方法有：channel()、executor()、handler()、pipeline()、alloc()。ChannelHandlerContext默认是由AbstractChannelHandlerContext去实现的，它实现了大部分功能。

ChannelPipeline初始化时会初始化两个结点：HeadContext和TailContext，并构成双向链表。HeadContext结点会比TailContext结点多一个unsafe成员变量。

## 18.ChannelPipeline添加ChannelHandler

### (1)常见的客户端代码

首先用一个拆包器Spliter对二进制数据流进行拆包，然后解码器Decoder会将拆出来的包进行解码，接着业务处理器BusinessHandler会处理解码出来的Java对象，最后编码器Encoder会将业务处理完的结果编码成二进制数据进行输出。

整个ChannelPipeline的结构如下所示：

![图片](assets/5514c3311829.png)

这里共有两种不同类型的结点，结点之间通过双向链表连接。一种是ChannelInboundHandler，用来处理Inbound事件，比如读取数据流进行加工处理。一种是ChannelOutboundHandler，用来处理Outbound事件，比如当调用writeAndFlush()方法时就会经过这种类型的Handler。

### (2)ChannelPipeline添加ChannelHandler入口

当服务端Channel的Reactor线程轮询到新连接接入的事件时，就会调用AbstractNioChannel的内部类NioUnsafe的read()方法，也就是调用AbstractNioMessageChannel的内部类NioMessageUnsafe的read()方法。

然后会触发执行代码pipeline.fireChannelRead()传播ChannelRead事件，从而最终触发调用ServerBootstrapAcceptor接入器的channelRead()方法。

在ServerBootstrapAcceptor的channelRead()方法中，便会通过执行代码channel.pipeline().addLast()添加ChannelHandler，也就是通过调用DefaultChannelPipeline的addLast()方法添加ChannelHandler。

### (3)DefaultChannelPipeline的addLast()方法

使用synchronized关键字是为了防止多线程并发操作ChannelPipeline底层的双向链表，添加ChannelHandler结点的过程主要分为4个步骤：

步骤一：判断ChannelHandler是否重复添加

步骤二：创建结点

步骤三：添加结点到链表

步骤四：回调添加完成事件

这个结点便是ChannelHandlerContext，Pipeline里每个结点都是一个ChannelHandlerContext。addLast()方法便是把ChannelHandler包装成一个ChannelHandlerContext，然后添加到链表。

### (4)检查是否重复添加ChannelHandler结点

Netty使用了一个成员变量added来表示一个ChannelHandler是否已经添加。如果当前要添加的ChannelHandler是非共享的并且已经添加过，那么抛出异常，否则标识该ChannelHandler已添加。

如果一个ChannelHandler支持共享，那么它就可以无限次被添加到ChannelPipeline中。如果要让一个ChannelHandler支持共享，只需要加一个@Sharable注解即可。而ChannelHandlerAdapter的isSharable()方法正是通过判断该ChannelHandler对应的类是否标有@Sharable注解来实现的。

Netty为了性能优化，还使用了ThreadLocal来缓存ChannelHandler是否共享的情况。在高并发海量连接下，每次有新连接添加ChannelHandler都会调用isSharable()方法，从而优化性能。

### (5)创建ChannelHandlerContext结点

根据ChannelHandler创建ChannelHandlerContext类型的结点时，会将该ChannelHandler的引用保存到结点的成员变量中。

### (6)添加ChannelHandlerContext结点

使用尾插法向双向链表添加结点。

### (7)回调handerAdded()方法

向ChannelPipeline添加完新结点后，会使用CAS修改结点的状态为ADD_COMPLETE表示结点添加完成，然后执行ctx.handler().handlerAdded(ctx)，回调用户在这个要添加的ChannelHandler中实现的handerAdded()方法。

最典型的一个回调就是用户代码的ChannelInitializer被添加完成后，会先调用其initChannel()方法将用户自定义的ChannelHandler添加到ChannelPipeline，然后再调用pipeline.remove()方法将自身结点进行删除。

### (8)ChannelPipeline添加ChannelHandler总结

一.判断ChannelHandler是否重复添加的依据是：如果该ChannelHandler不是共享的且已被添加过，则拒绝添加。

二.否则就创建一个ChannelHandlerContext结点(ctx)，并把这个ChannelHandler包装进去，也就是保存ChannelHandler的引用到ChannelHandlerContext的成员变量中。由于创建ctx时保存了ChannelHandler的引用、ChannelPipeline的引用到成员变量，ChannelPipeline又保存了Channel的引用，所以每个ctx都拥有一个Channel的所有信息。

三.接着通过双向链表的尾插法，将这个ChannelHandlerContext结点添加到ChannelPipeline中。

四.最后回调用户在这个要添加的ChannelHandler中实现的handerAdded()方法。

## 19.ChannelPipeline删除ChannelHandler

Netty最大的特征之一就是ChannelHandler是可插拔的，可以动态编织ChannelPipeline。比如在客户端首次连接服务端时，需要进行权限认证，认证通过后就可以不用再认证了。下面的AuthHandler便实现了只对第一个传来的数据包进行认证校验。如果通过验证则删除此AuthHandler，这样后续传来的数据包便不会再校验了。

ChannelPipeline删除ChannelHandler的步骤：

一.遍历双向链表，根据ChannelHandler找到对应的ChannelHandlerContext结点。

二.通过调整ChannelPipeline中双向链表的指针来删除对应的ChannelHandlerContext结点。

三.回调用户在这个要删除的ChannelHandler实现的handlerRemoved()方法，比如进行资源清理。

## 20.Inbound事件的传播

### (1)Unsafe的介绍

Unsafe和ChannelPipeline密切相关，ChannelPipeline中有关IO的操作最终都会落地到Unsafe的。Unsafe是不安全的意思，即不要在应用程序里直接使用Unsafe及它的衍生类对象。Unsafe是在Channel中定义的，是属于Channel的内部类。Unsafe中的接口操作都和JDK底层相关，包括：分配内存、Socket四元组信息、注册事件循环、绑定端口、Socket的连接和关闭、Socket的读写。

### (2)Unsafe的分类

有两种类型的Unsafe：一种是与连接的字节数据读写相关的NioByteUnsafe，另一种是与新连接建立操作相关的NioMessageUnsafe。

#### 一.NioByteUnsafe的读和写

NioByteUnsafe的读会被委托到NioByteChannel的doReadBytes()方法进行读取处理，doReadBytes()方法会将JDK的SelectableChannel的字节数据读取到Netty的ByteBuf中。

NioByteUnsafe中的写有两个方法，一个是write()方法，一个是flush()方法。write()方法是将数据添加到Netty的缓冲区，flush()方法是将Netty缓冲区的字节流写到TCP缓冲区，并最终委托到NioSocketChannel的doWrite()方法通过JDK底层Channel的write()方法写数据。

#### 二.NioMessageUnsafe的读

NioMessageUnsafe的读会委托到NioServerSocketChannel的doReadMessages()方法进行处理。doReadMessages()方法会调用JDK的accept()方法新建立一个连接，并将这个连接放到一个List里以方便后续进行批量处理。

### (3)ChannelPipeline中Inbound事件传播

当新连接已准备接入或者已经存在的连接有数据可读时，会在NioEventLoop的processSelectedKey()方法中执行unsafe.read()。

如果是新连接已准备接入，执行的是NioMessageUnsafe的read()方法。如果是已经存在的连接有数据可读，执行的是NioByteUnsafe的read()方法。

最后都会执行pipeline.fireChannelRead()引发ChannelPipeline的读事件传播。首先会从HeadContext结点开始，也就是调用HeadContext的channelRead()方法。然后触发调用AbstractChannelHandlerContext的fireChannelRead()方法，接着通过findContextInbound()方法找到HeadContext的下一个结点，然后通过invokeChannelRead()方法继续调用该结点的channelRead()方法，直到最后一个结点TailContext。

### (4)ChannelPipeline中的头结点和尾结点

HeadContext是一个同时属于Inbound类型和Outbound类型的ChannelHandler，TailContext则只是一个属于Inbound类型的ChannelHandler。

HeadContext结点的作用就是作为头结点开始传递读写事件并调用unsafe进行实际的读写操作。比如Channel读完一次数据后，HeadContext的channelReadComplete()方法会被调用。然后继续执行如下的调用流程：readIfAutoRead() -> channel.read() -> pipeline.read() -> HeadContext.read() -> unsafe.beginRead() -> 再次注册读事件。所以Channel读完一次数据后，会继续向Selector注册读事件。这样只要Channel活跃就可以连续不断地读取数据，然后数据又会通过ChannelPipeline传递到HeadContext结点。

TailContext结点的作用是通过让方法体为空来终止大部分事件的传播，它的exceptionCaugh()方法和channelRead()方法分别会发出告警日志以及释放到达该结点的对象。

### (5)Inbound事件的传播总结

一般用户自定义的ChannelInboundHandler都继承自ChannelInboundHandlerAdapter。如果用户代码没有覆盖ChannelInboundHandlerAdapter的channelXXX()方法，那么Inbound事件会从HeadContext开始遍历ChannelPipeline的双向链表进行传播，并默认情况下传播到TailContext结点。

如果用户代码覆盖了ChannelInboundHandlerAdapter的channelXXX()方法，那么事件传播就会在当前结点结束。所以如果此时这个ChannelHandler又忘记了手动释放业务对象ByteBuf，则可能会造成内存泄露，而SimpleChannelInboundHandler则可以帮用户自动释放业务对象。

如果用户代码调用了ChannelHandlerContext的fireXXX()方法来传播事件，那么该事件就从当前结点开始往下传播。

## 21.Outbound事件的传播

### (1)触发Outbound事件传播的入口

在消息推送系统中，可能会有如下代码，意思是根据用户ID获得对应的Channel，然后向用户推送消息。

```makefile
Channelchannel = ChannelManager.getChannel(userId);
channel.writeAndFlush(response);
```

### (2)Outbound事件传播的源码

如果通过Channel来传播Outbound事件，则是从TailContext开始传播的。和Inbound事件一样，Netty为了保证程序的高效执行，所有核心操作都要在Reactor线程中处理。如果业务线程调用了Channel的方法，那么Netty会将该操作封装成一个Task任务添加到任务队列中，随后在Reactor线程的事件循环中执行。

findContextOutbound()方法找Outbound结点的过程和findContextInbound()方法找Inbound结点类似，需要反向遍历ChannelPipeline中的双向链表，一直遍历到第一个Outbound结点HeadCountext。

如果用户的ChannelHandler覆盖了Outbound类型的方法，但没有把事件在方法中继续传播下去，那么会导致该事件的传播中断。

最后一个Inbound结点是TailContext，最后一个Outbound结点是HeadContext，而数据最终会落到HeadContext的write()方法上。

### (3)总结

Outbound事件的传播机制和Inbound事件的传播机制类似。但Outbound事件是从链表尾部开始向前传播，而Inbound事件是从链表头部开始向后传播。Outbound事件传播中的写数据，最终都会落到HeadContext结点中的unsafe进行处理。

## 22.ChannelPipeline中异常的传播

Inbound事件和Outbound事件在传播时发生异常都会调用notifyHandlerExecption()方法，该方法会按Inbound事件的传播顺序找每个结点的异常处理方法exceptionCaught()进行处理。

我们通常在自定义的ChannelHandler中实现一个处理异常的方法exceptionCaught()，统一处理ChannelPipeline过程中的所有异常。这个自定义ChannelHandler一般继承自ChannelDuplexHandler，表示该结点既是一个Inbound结点，又是一个Outbound结点。

如果我们在自定义的ChannelHandler中没有处理异常，由于ChannelHandler通常都继承了ChannelInboundHandlerAdapter，通过其默认实现的exceptionCaught()方法可知异常会一直往下传递，直到最后一个结点的异常处理方法exceptionCaught()中结束。因此如果异常处理方法exceptionCaught()在ChannelPipeline中间的结点实现，则该结点后面的ChannelHandler抛出的异常就没法处理了。所以一般会在ChannelHandler链表的末尾结点实现处理异常的方法exceptionCaught()。

需要注意的是：在任何结点中发生的异常都会向下一个结点进行传递。

## 23.ChannelPipeline总结

### (1)ChannelPipeline的初始化

ChannelPipeline在服务端Channel和客户端Channel被创建时创建，创建ChannelPipeline的类是服务端Channel和客户端Channel的共同父类AbstractChannel。

### (2)ChannelPipeline的数据结构

ChannelPipeline中的数据结构是双向链表结构，每一个结点都是一个ChannelHandlerContext对象。ChannelHandlerContext里包装了用户自定义的ChannelHandler，即前者会保存后者的引用到其成员变量handler中。ChannelHandlerContext中拥有ChannelPipeline和Channel的所有上下文信息。添加和删除ChannelHandler最终都是在ChannelPipeline的链表结构中添加和删除对应的ChannelHandlerContext结点。

### (3)ChannelHandler类型的判断

在旧版Netty中，会使用instanceof关键字来判断ChannelHandler的类型，并使用两个成员变量inbound和outbound来标识。在新版Netty中，会使用一个16位的二进制数executionMask来表示ChannelHandler具体实现的事件类型，若实现则给对应的位标1。

### (4)ChannelPipeline的头尾结点

创建ChannelPipeline时会默认添加两个结点：HeadContext结点和TailContext结点。HeadContext结点的作用是作为头结点，开始传播读写事件，并且通过它的unsafe变量实现具体的读写操作。TailContext结点的作用是起到终止事件传播(方法体为空)以及异常和对象未处理的告警。

### (5)Channel与Unsafe

一个Channel对应一个Unsafe，Unsafe用于处理底层IO操作。NioServerSocketChannel对应NioMessageUnsafe，NioSocketChannel对应NioByteUnsafe。

### (6)ChannelPipeline的事件传播机制

ChannelPipeline中的事件传播机制分为3种：Inbound事件的传播、Outbound事件的传播、异常事件的传播。

#### 一.Inbound事件的传播

如果通过Channel的Pipeline触发这类事件(默认情况下)，那么触发的规则是从head结点开始不断寻找下一个InboundHandler，最终落到tail结点。如果在当前ChannelHandlerContext上触发这类事件，那么事件只会从当前结点开始向下传播。

#### 二.Outbound事件的传播

如果通过Channel的Pipeline触发这类事件(默认情况下)，那么触发的规则是从tail结点开始不断寻找上一个OutboundHandler，最终落到head结点。如果在当前ChannelHandlerContext上触发这类事件，那么事件只会从当前结点开始向上传播。

#### 三.异常事件的传播

异常在ChannelPipeline中的双向链表传播时，无论Inbound结点还是Outbound结点，都是向下一个结点传播，直到tail结点为止。TailContext结点会打印这些异常信息，最佳实践是在ChannelPipeline的最后实现异常处理方法exceptionCaught()。
