# 面试准备之ZooKeeper要点总结三

> **公众号**: 东阳马生架构  
> **发布时间**: 2025-09-26 09:00  

**大纲(22890字)**

- 1.ZooKeeper的数据模型与节点类型及应用
- 2.发布订阅模式之用Watcher机制实现分布式通知
- 3.ZooKeeper的网络通信协议
- 4.客户端核心组件HostProvider
- 5.客户端核心组件ClientCnxn
- 6.客户端工作原理之会话创建过程
- 7.单机版的zk服务端的启动过程
- 8.集群版的zk服务端的启动过程
- 9.创建会话
- 10.分桶策略和会话管理


## 1.ZooKeeper的数据模型与节点类型及应用

### (1)数据模型之树形结构

计算机最根本的作用其实就是处理和存储数据，作为一款分布式一致性框架，zk也是如此。数据模型就是zk用来存储和处理数据的一种逻辑结构，zk数据模型最根本的功能就像一个数据库。接下来按如下步骤做一些简单操作，最终会在zk服务器上得到一个具有层级关系的数据结构。

zk中的数据模型是一种树形结构，有一个根文件夹，下面有很多子文件夹。zk的数据模型也具有一个固定的根节点"/"，可以在根节点下创建子节点，并在子节点下继续创建下一级节点。zk树中的每一层级用斜杠"/"分隔开，只能用绝对路径的方式查询zk节点，如"get /work/task1"，不能用相对路径的方式查询zk节点。

### (2)ZNode节点类型与特性

zk中的数据节点分为持久节点、临时节点和顺序节点三种类型。

#### 一.持久节点

持久节点在zk最为常用的，几乎所有业务场景中都会包含持久节点的创建。之所以叫作持久节点是因为：一旦将节点创建为持久节点，节点数据就会一直存储在ZK服务器上。即使创建该节点的客户端与服务端的会话关闭了，该节点依然不会被删除。如果想要删除持久节点，需要显式调用delete函数进行删除。

#### 二.临时节点

临时节点从名称上可以看出它最重要的一个特性就是临时性。所谓临时性是指：如果将节点创建为临时节点，那么该节点数据不会一直存储在zk服务器上。当创建该临时节点的客户端，因会话超时或发生异常而关闭时，该节点也相应在zk服务器上被删除。同样，可以像删除持久节点一样主动删除临时节点。

可以利用临时节点的临时特性来进行服务器集群内机器运行情况的统计。比如将集群设置为"/servers"节点，并为集群下的每台服务器创建一个临时节点"/servers/host"，当服务器下线时其对应的临时节点就会自动被删除，最后统计临时节点个数就可以知道集群中的运行情况。

#### 三.顺序节点

其实顺序节点并不算是一种单独种类的节点，而是在持久节点和临时节点特性的基础上，增加一个节点有序的性质。所谓节点有序是指：创建顺序节点时，zk服务器会自动使用一个单调递增的数字作为后缀追加到所创建节点后面。

例如一个客户端创建了一个路径为"works/task-"的有序节点，那么zk将会生成一个序号并追加到该节点的路径后，最后该节点的路径就会变为"works/task-1"。通过这种方式可以直观查看到节点的创建顺序。

小结：zk服务器上存储数据的模型是一种树形结构。zk中的数据节点类型有：持久节点、持久顺序节点、临时节点和临时顺序节点。这几种数据节点虽然类型不同，但每个数据节点都有一个二进制数组(byte data[])，每个数据节点都有一个记录自身状态信息的字段stat。其中二进制数组会用来存储节点的数据、ACL访问控制信息、子节点数据。

注意：因为临时节点不允许有子节点，所以临时节点的子节点为null。

### (3)使用ZooKeeper实现锁

#### 一.悲观锁

悲观锁认为线程对数据资源的竞争总是会出现。为了保证线程在操作数据时，该条数据不会被其他线程修改，那么该条数据要一直处于被锁定的状态。

假设有n个线程同时访问和修改某一数据资源，为了实现线程安全，可以让线程通过创建zk节点"/locks"的方式获取锁。线程A成功创建zk节点"/locks"后获取到锁继续执行，这时线程B也要访问该数据资源，于是线程B尝试创建zk节点"/locks"来尝试获取锁。但是因为线程A已创建该节点，所以线程B创建节点失败而无法获得锁。这样线程A操作数据时，数据就不会被其他线程修改，从而实现了一个简单的悲观锁。

不过存在一个问题：

就是如果进程A因为异常而中断，那么就会导致"/locks"节点始终存在。此时其他线程就会因为无法再次创建节点而无法获取锁，从而产生死锁问题。针对这个问题，可以通过将节点设置为临时节点来进行避免，并通过在服务器端添加监听事件来实现锁被释放时可以通知其他线程重新获取锁。

#### 二.乐观锁

乐观锁认为线程对数据资源的竞争不会总是出现。所以相对悲观锁而言，加锁方式没有那么激烈，不会全程锁定数据。而是在数据进行提交更新时，才对数据进行冲突检测，如果发现冲突才拒绝操作。

乐观锁基本可以分为读取、校验、写入三个步骤。CAS(Compare-And-Swap即比较并替换)就是一个乐观锁的实现。CAS有3个操作数：内存值V、旧的预期值A、要修改的新值B，当且仅当预期值A和内存值V相同时，才会将内存值V修改为B。

zk中的version属性就是用来实现乐观锁机制中的"校验"的，zk每个节点都有数据版本的概念。在调用更新操作时，假如有一个客户端试图进行更新操作，该客户端会携带上次获取到的version值进行更新。如果在这段时间内，zk服务器上该节点的数值恰好被其他客户端更新了，那么该节点的数据版本version值一定也会发生变化，从而导致与客户端携带的version无法匹配，于是无法成功更新。因此有效避免了分布式更新的并发安全问题。

在zk的底层实现中，当服务端处理每一个数据更新请求(SetDataRequest)时，首先会调用checkAndIncVersion()方法进行数据版本校验：

步骤一：从SetDataRequest请求中获取version。

步骤二：通过getRecordForPath()方法获取服务器数据记录nodeRecord，然后从nodeRecord中获取当前服务器上该数据的最新版本currentversion。如果version是-1，表示该请求操作不使用乐观锁，可以忽略版本对比。如果version不是-1，则对比version和currentversion。若相等则进行更新，否则抛出BadVersionException异常中断。

## 2.发布订阅模式之用Watcher机制实现分布式通知

zk的Watcher机制的整个流程：客户端在向zk服务端注册Watcher的同时，会将Watcher对象存储在客户端的WatchManger中。当zk服务端触发Watcher事件后，会向客户端发送通知。客户端线程会从WatchManager中取出对应的Watcher对象来执行回调逻辑。

zk的Watcher机制主要包括三部分：客户端线程、客户端WatchManager、zk服务端；

zk的Watcher机制主要包括三个过程：即客户端注册Watcher、服务端处理Watcher、客户端回调Watcher，这三个过程其实也是发布订阅功能的几个核心点。

### (1)Watcher机制是如何实现的

#### 一.客户端向服务端添加Watcher监控事件的方式

zk的客户端可以通过Watcher机制来订阅服务端上某一节点的数据，以便当该节点的数据状态发生变化时能收到相应的通知。

比如可以通过向zk客户端的构造方法中传递Watcher参数的方式实现添加Watcher监控事件。下面代码的意思是定义了一个了zk客户端对象实例，并传入三个参数。这个Watcher将作为整个zk会话期间的默认Watcher，一直被保存在客户端ZKWatchManager的defaultWatcher中。

除此之外，zk客户端也可以通过getData()、getChildren()和exists()三个接口，向zk服务端注册Watcher，从而方便地在不同的情况下添加Watcher事件。

#### 二.触发服务端Watcher监控事件通知的条件

zk中的接口类Watcher用于表示一个标准的事件处理器，Watcher接口类定义了事件通知的相关逻辑。Watcher接口类中包含了KeeperState和EventType两个枚举类，其中KeeperState枚举类代表会话通知状态，EventType枚举类代表事件类型。

### (2)Watcher机制的底层原理

Watcher机制的结构其实很像设计模式中的观察者模式。一个对象或者数据节点可能会被多个客户端监控，当对应事件被触发时，会通知这些对象或客户端。可以将Watcher机制理解为是分布式环境下的观察者模式，所以接下来以观察者模式的角度来看zk底层Watcher是如何实现的。

在实现观察者模式时，最关键的代码就是创建一个列表来存放观察者。而在zk中则是在客户端和服务端分别实现了两个存放观察者列表：也就是客户端的ZKWatchManager和服务端的WatchManager。zk的Watcher机制的核心操作其实就是围绕这两个列表展开的。

### (3)客户端Watcher注册实现过程

先看客户端的实现过程。当发送一个带有Watcher事件的会话请求时，zk客户端主要会做两个工作：一.标记该会话请求是一个带有Watcher事件的请求，二.将Watcher事件存储到ZKWatchManager中。

以getData接口为例，当zk客户端发送一个带有Watcher事件的会话请求时：

#### 一.首先将数据节点和Watcher的对应关系封装到DataWatchRegistration

然后把该请求标记为带有Watcher事件的请求，这里说的封装其实指的是new一个对象。

#### 二.接着将请求封装成一个Packet对象并添加到发送队列outgoingQueue

Packet对象被添加到发送队列outgoingQueue后，会进行阻塞等待。也就是通过Packet对象的wait()方法进行阻塞，直到Packet对象标记为完成。

#### 三.随后通过客户端SendThread线程向服务端发送outgoingQueue里的请求

也就是通过ClientCnxnSocket的doTransport()方法处理请求发送和响应。

#### 四.完成请求发送后，客户端SendThread线程会监听并处理服务端响应

也就是由ClientCnxn的内部类SendThread的readResponse()方法负责接处理务端响应，然后执行ClientCnxn的finishPacket()方法从Packet对象中取出对应的Watcher。即通过调用WatchRegistration的register()方法，将Watcher事件注册到ZooKeeper的ZKWatchManager中。

因为客户端一开始将Watcher事件封装到DataWatchRegistration对象中，所以在调用WatchRegistration的register()方法时，客户端就会将之前封装在DataWatchRegistration的Watcher事件交给ZKWatchManager，并最终保存到ZKWatchManager的dataWatches中。

ZKWatchManager的dataWatches是一个Map<String, Set<Watcher>>，用于将数据节点的路径和Watcher事件进行一一映射后管理起来。

注意：客户端每调用一次getData()接口，就会注册一个Watcher，但这些Watcher实体不会随着客户端请求被发送到服务端。如果客户端的所有Watcher都被发送到服务端的话，服务端可能就会出现内存紧张或其他性能问题。虽然封装Packet对象的时候会传入DataWatchRegistration对象，但是在底层实际的网络传输对Packet对象序列化的过程中，并没有将DataWatchRegistration对象序列化到字节数组。

### (4)服务端处理Watcher过程

zk服务端处理Watcher事件基本有两个过程：

#### 一.判断收到的请求是否需要注册Watcher事件

#### 二.将对应的Watcher事件存储到WatchManager

以下是zk服务端处理Watcher的序列图：

![图片](assets/9ac477fd7e12.png)

zk服务端接收到客户端请求后的具体处理：

一.当服务端收到客户端标记了Watcher事件的getData请求时，会调用到FinalRequestProcessor的processRequest()方法，判断当前客户端请求是否需要注册Watcher事件。

二.当getDataRequest.getWatch()的值为true时，则表明当前客户端请求需要进行Watcher注册。

三.然后将当前的ServerCnxn对象(即Watcher事件)和数据节点路径，传入到zks.getZKDatabase()的getData()方法中来实现Watcher事件的注册，也就是实现存储Watcher事件到WatchManager中。具体就是：调用DataTree.dataWatches这个WatchManager的addWatch()方法，将该客户端请求的Watcher事件(也就是ServerCnxn对象)存储到DataTree.dataWatches这个WatchManager的两个HashMap(watchTable和watch2Paths)中。

补充说明：

首先，ServerCnxn对象代表了一个客户端和服务端的连接。ServerCnxn接口的默认实现是NIOServerCnxn，也可以选NettyServerCnxn。由于NIOServerCnxn和NettyServerCnxn都实现了Watcher的process接口，所以可以把ServerCnxn对象看作是一个Watcher对象。

然后，zk服务端的数据库DataTree中会有两个WatchManager，分别是dataWatches和childWatches，分别对应节点和子节点数据变更。

接着，WatchManager中有两个HashMap：watch2Paths和watchTable。当前的ServerCnxn对象和数据节点路径最终会被存储在这两HashMap中。watchTable可以根据数据节点路径来查找对应的Watcher，watch2Paths可以根据Watcher来查找对应的数据节点路径。

同时，WatchManager除了负责添加Watcher事件，还负责触发Watcher事件，以及移除那些已经被触发的Watcher事件。

### (5)服务端Watch事件的触发过程

对于标记了Watcher注册的请求，zk会将其对应的ServerCnxn对象(Watcher事件)存储到DataTree里的WatchManager的HashMap(watchTable和watch2Paths)中。之后，当服务端对指定节点进行数据更新后，会通过调用DataTree里的WatchManager的triggerWatch()方法来触发Watcher。

无论是触发DataTree的dataWatches，还是触发DataTree的childWatches，Watcher的触发逻辑都是一样的。

具体的Watcher触发逻辑如下：

步骤一：首先封装一个具有这三个属性的WatchedEvent对象：通知状态(KeeperState)、事件类型(EventType)、数据节点路径(path)。

步骤二：然后根据数据节点路径从DateTree的WatchManager中取出Watcher。如果为空，则说明没有任何客户端在该数据节点上注册过Watcher。如果存在，则将Watcher事件添加到自定义的Wathcers集合中，并且从DataTree的WatchManager的watchTable和watch2Paths中移除。最后调用Watcher的process()方法向客户端发送通知。

具体的Watcher的process()方法，会由NIOServerCnxn来实现。Watcher的process()方法的具体逻辑如下：

步骤一：标记响应头ReplyHeader的xid为-1，表示当前响应是一个通知。

步骤二：将触发WatchManager.triggerWatch()方法时封装的WatchedEvent，包装成WatcherEvent，以便进行网络传输序列化。

步骤三：向客户端发送响应。

### (6)客户端回调Watcher的处理过程

对于来自服务端的响应：客户端会使用SendThread的readResponse()方法来进行统一处理。如果反序列化后得到的响应头replyHdr的xid为-1，则表明这是一个通知类型的响应。

SendThread接收事件通知的处理步骤如下：

步骤一：反序列化成WatcherEvent对象。zk客户端接收到请求后，首先将字节流反序列化成WatcherEvent对象。

步骤二：处理chrootPath。如果客户端设置了chrootPath为/app，而服务端响应的节点路径为/app/a，那么经过chrootPath处理后，就会统一变成一个相对路径：/a。

步骤三：还原成WatchedEvent对象。将WatcherEvent对象转换成WatchedEvent对象。

步骤四：回调Watcher。通过调用EventThread的queueEvent()方法，将WatchedEvent对象交给EventThread线程来回调Watcher。所以服务端的Watcher事件通知，最终会交给EventThread线程来处理。

EventThread线程是zk客户端专门用来处理服务端事件通知的线程。

EventThread处理事件通知的步骤如下：

步骤一：EventThread的queueEvent()方法首先会根据WatchedEvent对象，从ZKWatchManager中取出所有注册过的客户端Watcher。

步骤二：然后从ZKWatchManager的管理中删除这些Watcher。这也说明客户端的Watcher机制是一次性的，触发后就会失效。

步骤三：接着将所有获取到的Watcher放入waitingEvents队列中。

步骤四：最后EventThread线程的run()方法，通过循环的方式，每次都会从waitingEvents队列中取出一个Watcher进行串行同步处理。也就是调用EventThread线程的processEvent()方法来最终执行实现了Watcher接口的process()方法，从而实现回调处理。

总结zk的Watcher机制处理过程：

一.zk是通过在客户端和服务端创建观察者信息列表来实现Watcher机制的。

二.客户端调用getData()、getChildren()、exist()等方法时，会将Watcher事件放到本地的ZKWatchManager中进行管理。

三.服务端在接收到客户端的请求后首先判断是否需要注册Watcher，若是则将ServerCnxn对象当成Watcher事件放入DataTree的WatchManager中。

四.服务端触发Watcher事件时，会根据节点路径从WatchManager中取出对应的Watcher，然后发送通知类型的响应给客户端。

五.客户端在接收到通知类型的响应后，首先通过SendThread线程提取出WatchedEvent对象。然后将WatchedEvent对象交给EventThread线程来回调Watcher。也就是查询本地的ZKWatchManager获得对应的Watcher事件，删除ZKWatchManager的Watcher并将Watcher放入waitingEvents队列。后续EventThread线程便会在其run()方法中串行出队waitingEvents，执行Watcher的process()回调。

客户端的Watcher管理器是ZKWatchManager。

服务端的Watcher管理器是WatchManager。

以上的处理设计实现了一个分布式环境下的观察者模式，通过将客户端和服务端处理Watcher事件时所需要的信息分别保存在两端，减少了彼此通信的内容，大大提升了服务的处理性能。

### (7)利用Watcher实现发布订阅

#### 一.发布订阅系统一般有推模式和拉模式

推模式是指服务端主动将数据更新发送给所有订阅的客户端，拉模式是指客户端主动发起请求来获取最新数据(定时轮询拉取)。

#### 二.zk采用了推拉相结合来实现发布和订阅功能

首先客户端需要向服务端注册自己关注的节点(添加Watcher事件)。一旦该节点发生变更，服务端就会向客户端发送Watcher事件通知。客户端接收到消息通知后，需要主动到服务端获取最新的数据。

如果将配置信息放到zk上进行集中管理，那么应用启动时需要主动到zk服务端获取配置信息，然后在指定节点上注册一个Watcher监听。接着只要配置信息发生变更，zk服务端就会实时通知所有订阅的应用。从而让应用能实时获取到订阅的配置信息节点已发生变更的消息。

注意：原生zk客户端可以通过getData()、exists()、getChildren()三个方法，向zk服务端注册Watcher监听。而且注册到Watcher监听具有一次性，所以zk客户端获得服务端的节点变更通知后需要再次注册Watcher。

#### 三.使用zk来实现发布订阅功能总结

步骤一：将配置信息存储到zk的节点上。

步骤二：应用启动时先从zk节点上获取配置信息，然后再向该zk节点注册一个数据变更的Watcher监听。一旦该zk节点数据发生变更，所有订阅的客户端就能收到数据变更通知。

步骤三：应用收到zk服务端发过来的数据变更通知后重新获取最新数据。

### (8)Watcher具有的特性

#### 一.一次性

无论是客户端还是服务端，一旦Watcher被触发或者回调，zk都会将其移除，所以使用zk的Watcher时需要反复注册。这样的设计能够有效减轻服务端的压力。否则，如果一个Watcher注册后一直有效，那么频繁更新的节点就会频繁发送通知给客户端，这样就会影响网络性能和服务端性能。

#### 二.客户端串行执行

客户端Watcher回调的过程是一个串行同步的过程，这为我们保证了顺序。注意不要因一个Watcher的处理逻辑而影响整个客户端的Watcher回调。

#### 三.轻量

WatchedEvent是Watcher机制的最小通知单元，WatchedEvent只包含三部分内容：通知状态、事件类型和节点路径。所以Watcher通知非常简单，只告诉客户端发生的事件，不包含具体内容。所以原始数据和变更后的数据无法从WatchedEvent中获取，需要客户端主动重新去获取数据。

客户端向服务端注册Watcher时：不会把客户端真实的Watcher对象传递到服务端，只会在客户端请求中使用boolean属性来标记Watcher对象，服务端也只会保存当前连接的ServerCnxn对象。

这种轻量的Watcher设计机制，在网络开销和服务端内存开销上都是很低的。

## 3.ZooKeeper的网络通信协议

### (1)ZooKeeper协议简述

zk基于TCP/IP协议，实现了自己的通信协议来完成网络通信。zk通信协议整体上的设计非常简单。一次客户端的请求，主要由请求头和请求体组成。一次服务端的响应，主要由响应头和响应体组成。zk中的网络通信协议是通过不同的类具体实现的。

### (2)ZooKeeper通信协议的底层实现之请求协议

请求协议就是客户端向服务端发送请求的协议，比如常用的会话创建、数据节点查询等操作，都会使用请求协议来完成客户端与服务端的网络通信。

#### 一.请求头RequestHeader

在zk中请求头是通过RequestHeader类实现的，RequestHeader类实现了Record接口，用于网络传输时进行序列化操作。可以看到RequestHeader类中只有两个属性字段，分别是xid和type。其中xid字段表示客户端序号用于记录客户端请求的发起顺序，type字段表示请求操作的类型。

#### 二.请求体Request

请求协议的请求体部分是指请求的主体内容部分，包含了请求的所有内容。不同的请求类型，其请求体部分的结构是不同的。接下来介绍会话创建、数据节点查询、数据节点更新的三种请求体实现。

实现一：会话创建请求ConnectRequest

zk客户端发起会话时，会向服务端发送一个会话创建请求。该请求的作用就是通知zk服务端需要处理一个来自客户端的访问连接。服务端处理会话创建请求时所需要的所有信息都包括在请求体内。

会话创建请求的请求体是通过ConnectRequest类实现的。ConnectRequest类实现了Record接口，用于网络传输时进行序列化操作。可以看到，ConnectRequest类一共有五种属性字段，分别是：protocolVersion表示该请求协议的版本信息，lastZxidSeen表示最后一次接收到的服务器的zxid序号，timeOut表示会话的超时时间，sessionId表示会话标识符，password表示会话密码。zk服务端在接收一个请求时，就会根据请求体的这些信息进行相关操作。

实现二：节点数据查询请求GetDataRequest

当zk客户端向服务端发送一个节点数据查询请求时，节点数据查询请求的请求体是通过GetDataRequest类实现的。GetDataRequest类实现了Record接口，用于网络传输时进行序列化操作。可以看到，GetDataRequest类具有两个属性字段，分别是：path表示要请求的数据节点路径，watch表示该节点是否注册Watcher事件。

实现三：节点数据更新请求SetDataRequest

当zk客户端向服务端发送一个节点数据更新请求时，节点数据更新请求的请求体是通过SetDataRequest类实现的。SetDataRequest类实现了Record接口，用于网络传输时进行序列化操作。可以看到，SetDataRequest类具有三个属性，分别是：path表示节点的路径，data表示节点数据信息，version表示节点数据的期望版本号，用于乐观锁的验证。

### (3)ZooKeeper协议的底层实现之响应协议

响应可理解为服务端在处理完客户端的请求后，返回相关信息给客户端。服务端采用的响应协议类型需要根据客户端的请求协议类型来选择。在zk服务端向客户端返回的响应中，包括了响应头和响应体，所以响应协议包含了响应头和响应体两部分。

#### 一.响应头ReplyHeader

与客户端的请求头不同的是，服务端的响应头多了一个错误状态字段，服务端的响应头的具体实现类是ReplyHeader。

#### 二.响应体Response

响应协议的响应体部分是指响应的主体内容部分，包含了响应的所有数据。不同的响应类型，其响应体部分的结构是不同的。接下来介绍会话创建、数据节点查询、数据节点更新的三种响应体实现。

实现一：会话创建响应ConnectResponse

针对客户端的会话创建请求，服务端会返回一个会话创建响应。会话创建响应的响应体是通过ConnectRespose类来实现的。ConnectRespose类实现了Record接口，用于网络传输时进行序列化操作。可以看到，ConnectRespose类具有四个属性，分别是：protocolVersion表示请求协议的版本信息，timeOut表示会话超时时间，sessionId表示会话标识符，passwd表示会话密码。

实现二：节点数据查询响应GetDataResponse

针对客户端的节点数据查询请求，服务端会返回一个节点数据查询响应。节点数据查询响应的响应体是通过GetDataResponse类来实现的。GetDataResponse类实现了Record接口，用于网络传输时进行序列化操作。可以看到，GetDataResponse类具有两个属性，分别是：data表示节点数据的内容，stat表示节点的状态信息。

实现三：节点数据更新响应SetDataResponse

针对客户端的节点数据更新请求，服务端会返回一个节点数据更新响应。节点数据更新响应的响应体是通过SetDataResponse类来实现的。SetDataResponse类实现了Record接口，用于网络传输时进行序列化操作。可以看到，SetDataResponse类只有一个属性：stat表示该节点数据更新后的最新状态信息。

## 4.客户端核心组件HostProvider

### (1)HostProvider的创建

在使用zk的构造方法时会传入zk服务器地址列表，即connectString参数。zk客户端内部接收到这个服务器地址列表后，会首先将该列表放入ConnectStringParser解析器中封装起来。ConnectStringParser解析器会对传入的connectString进行如下处理：

#### 一.解析chrootPath

通过设置chrootPath，可以让客户端应用与zk服务端的一棵子树相对应。在多个应用共用一个zk集群的场景下，可以实现不同应用间的相互隔离。

#### 二.保存服务器地址列表

在ConnectStringParser解析器中会对服务器地址进行如下处理：先将服务器地址和相应的端口封装成一个InetSocketAddress对象，然后以ArrayList的形式保存在ConnectStringParser的serverAddresses属性中。

经过ConnectStringParser解析器对connectString解析后，便获取处理好的服务器地址列表，然后封装到StaticHostProvider中。

### (2)HostProvider的next()方法

#### 一.StaticHostProvider的next()方法需要返回已解析的地址

需要注意的是：在ConnectStringParser的serverAddresses属性中保存的服务器地址列表，都是还没有被解析的InetSocketAddress。

所以HostProvider的方法就会负责对InetSocketAddress列表进行解析，然后HostProvider的next()方法返回的必须是已被解析的InetSocketAddress。

#### 二.StaticHostProvider解析服务器地址时会随机打散列表

针对ConnectStringParser.serverAddresses中没有被解析的服务器地址，StaticHostProvider会对这些地址逐个解析然后放入其serverAddresses中，同时会使用Collections.shuffle()方法来随机打散服务器地址列表。

调用StaticHostProvider的next()方法时，会从其serverAddresses中获取一个可用的地址。这个next()方法会先将随机打散后的地址列表拼装成一个环形循环队列。然后在之后的使用过程中，一直按拼装的顺序来获取服务器地址。这个随机打散的过程是一次性的。

#### 三.StaticHostProvider中的环形循环队列实现

StaticHostProvider会为循环队列创建两个游标：currentIndex和lastIndex。currentIndex表示循环队列中当前遍历到的那个元素位置，初始值为-1。lastIndex表示当前正在使用的服务器地址位置，初始值为-1。每次执行next()方法时，都会先将currentIndex游标向前移动1位。如果发现游标移动超过了整个地址列表的长度，那么就重置为0。

对于服务器地址列表提供得比较少的场景：如果发现当前游标的位置和上次已经使用过的地址位置一样，也就是currentIndex和lastIndex游标值相同时，就进行spinDelay毫秒等待。

## 5.客户端核心组件ClientCnxn

### (1)客户端核心类ClientCnxn和Packet

#### 一.ClientCnxn

ClientCnxn是zk客户端的核心工作类，负责维护客户端与服务端间的网络连接并进行一系列网络通信。

#### 二.Packet

Packet是ClientCnxn内部定义的、作为zk客户端中请求与响应的载体。也就是说Packet可以看作是一个用来进行网络通信的数据结构，Packet的主要作用是封装网络通信协议层的数据。

Packet中包含了一些请求协议的相关属性字段：请求头信息requestHeader、响应头信息replyHeader、请求体request、响应体response、节点路径clientPath以及serverPath、Watcher监控信息。

Packet的createBB()方法负责对Packet对象进行序列化，最终生成可用于底层网络传输的ByteBuffer对象。该方法只会将requestHeader、request和readOnly三个属性进行序列化。Packet的其余属性保存在客户端的上下文，不进行服务端的网络传输。

### (2)请求队列outgoingQueue与响应等待队列pendingQueue

ClientCnxn中有两个核心的队列outgoingQueue和pendingQueue，分别代表客户端的请求发送队列和服务端的响应等待队列。

outgoingQueue队列是一个客户端的请求发送队列，专门用于存储那些需要发送到服务端的Packet集合。

pendingQueue队列是一个服务端的响应等待队列，用于存储已从客户端发送到服务端，但是需要等待服务端响应的Packet集合。

当zk客户端对请求信息进行封装和序列化后，zk不会立刻就将一个请求信息通过网络直接发送给服务端，而是会先将请求信息添加到请求队列中，之后通过SendThread线程来处理相关的请求发送操作。

#### 一.请求发送

SendThread线程在调用ClientCnxnSocket的doTransport()方法时，会从ClientCnxn的outgoingQueue队列中提取出一个可发送的Packet对象，同时生成一个客户端请求序号XID并将其设置到Packet对象的请求头中，然后再调用Packet对象的createBB方法进行序列化，最后才发送出去。

请求发送完毕后，会立即将该Packet对象保存到pendingQueue队列中，以便等待服务端的响应返回后可以进行相应的处理。

#### 二.响应接收

客户端获取到来自服务端的响应后，其中的SendThread线程在调用ClientCnxnSocket的doTransport()方法时，便会调用ClientCnxnSocket的doIO()方法，根据不同的响应进行不同的处理。

情况一：如果检测到当前客户端尚未进行初始化，则客户端和服务端还在创建会话，那么此时就直接将收到的ByteBuffer序列化成ConnectResponse对象。

情况二：如果接收到的服务端响应是一个事件，那么此时就会将接收到的ByteBuffer序列化成WatcherEvent对象，并将WatchedEvent对象放入待处理队列waitingEvents中。

情况三：如果接收到的服务端响应是一个常规的请求响应，那么就从pendingQueue队列中取出一个Packet对象来进行处理；此时zk客户端会检验服务端响应中包含的XID值来确保请求处理的顺序性，然后再将接收到的ByteBuffer序列化成相应的Response对象。

最后，会在finishPacket()方法中处理Packet对象中关联的Watcher事件。

### (3)SendThread

SendThread是客户端ClientCnxn内部的一个IO调度线程，SendThread的作用是用于管理客户端和服务端之间的所有网络IO操作。

在zk客户端的实际运行过程中：

#### 一.一方面SendThread会维护客户端与服务端之间的会话生命周期

通过在一定的周期频率内向服务端发送一个PING包来实现心跳检测。同时如果客户端和服务端出现TCP连接断开，就会自动完成重连操作。

#### 二.另一方面SendThread会管理客户端所有的请求发送和响应接收操作

将上层客户端API操作转换成相应的请求协议并发送到服务端，并且完成对同步调用的返回和异步调用的回调，同时SendThread还负责将来自服务端的事件传递给EventThread去处理。

注意：为了向服务端证明自己还存活，客户端会周期性发送Ping包给服务端。服务端收到Ping包之后，会根据当前时间重置与客户端的Session时间，更新该Session的请求延迟时间，进而保持客户端与服务端的连接状态。

### (4)EventThread

EventThread是客户端ClientCnxn内部的另一个核心线程，EventThread负责触发客户端注册的Watcher监听和异步接口注册的回调。

EventThread中有一个waitingEvents队列，临时存放要被触发的Object，这些Object包括客户端注册的Watcher监听和异步接口中注册的回调。

EventThread会不断从waitingEvents队列中取出Object，然后识别出具体类型是Watcher监听还是AsyncCallback回调，最后分别调用process()方法和processResult()方法来实现事件触发和回调。

### (5)总结

客户端ClientCnxn的工作原理：当客户端向服务端发送请求操作时，首先会将请求信息封装成Packet对象并加入outgoingQueue请求队列中，之后通过SendThread网络IO调度线程将请求发送给服务端。当客户端接收到服务端响应时，通过EventThread线程来处理服务端响应及触发Watcher监听和异步回调。

## 6.客户端工作原理之会话创建过程

### (1)初始化阶段：实例化ZooKeeper对象

#### 一.初始化ZooKeeper对象

通过调用ZooKeeper的构造方法来实例化一个ZooKeeper对象。在初始化过程中，会创建客户端的Watcher管理器ZKWatchManager。

#### 二.设置会话默认的Watcher

如果在ZooKeeper的构造方法中传入了一个Watcher对象，那么客户端会将该对象作为默认的Watcher，保存在客户端的Watcher管理器ZKWatchManager中。

#### 三.构造服务器地址管理器StaticHostProvider

在ZooKeeper构造方法中传入的服务器地址字符串，客户端会将其存放在服务器地址列表管理器StaticHostProvider中。

#### 四.创建并初始化客户端的网络连接器ClientCnxn

创建的网络连接器ClientXnxn是用来管理客户端与服务端的网络交互。ClientCnxn中有两个核心的队列outgoingQueue和pendingQueue，分别代表客户端的请求发送队列和服务端的响应等待队列。ClientCnxn是客户端的网络连接器，ClientCnxnSocket是客户端的网络连接，ClientCnxn构造方法会传入ClientCnxnSocket。

#### 五.初始化SendThread和EventThread

ClientCnxn的构造方法会创建两个核心线程SendThread和EventThread。SendThread用于管理客户端和服务端之间的所有网络IO，EventThread用于处理客户端的事件，比如Watcher和回调等。

初始化SendThread时，会将ClientCnxnSocket分配给SendThread作为底层网络IO处理器。初始化EventThread时，会初始化队列waitingEvents用于存放所有等待被客户端处理的事件。

### (2)会话创建阶段：建立连接并发送会话创建请求

#### 一.启动SendThread和EventThread

即执行SendThread和EventThread的run()方法。

#### 二.获取一个服务端地址

在开始创建TCP连接前，SendThread需要先获取一个zk服务端地址，也就是通过StaticHostProvider的next()方法获取出一个地址。然后把该地址委托给初始化SendThread时传入的ClientCnxnSocket去创建一个TCP连接。

#### 三.创建TCP连接

首先在SocketChannel中注册OP_CONNECT，表明发起建立TCP连接的请求。然后执行SendThread的primeConnection()方法发起创建TCP长连接的请求。

#### 四.构造ConnectRequest请求

SendThread的primeConnection()方法会构造出一个ConnectRequest请求，ConnectRequest请求代表着客户端向服务端发起的是一个创建会话请求。

SendThread的primeConnection()方法会将该请求包装成IO层的Packet对象，然后将该Packet对象放入outgoingQueue请求发送队列中。

#### 五.发送ConnectRequest请求

ClientCnxnSocket会从outgoingQueue请求发送队列取出待发送的Packet，然后将其序列化成ByteBuffer后再发送给服务端。ClientCnxnSocket是客户端的网络连接，ClientCnxn是客户端的网络连接器。

### (3)响应处理阶段：接收会话创建请求的响应

#### 一.接收服务端对会话创建请求的响应

客户端的网络连接接收到服务端响应后，会先判断自己是否已被初始化。如果尚未初始化，那么就认为该响应是会话创建请求的响应，直接通过ClientCnxnSocket的readConnectResult()方法进行处理。ClientCnxnSocket是客户端的网络连接，ClientCnxn是客户端的网络连接器。

#### 二.处理会话创建请求的响应

ClientCnxnSocket的readConnectResult()方法会对响应进行反序列化，也就是反序列化成ConnectResponse对象，然后再从该对象中获取出会话ID。

#### 三.更新ClientCnxn客户端连接器

服务端的响应表明连接成功，那么就需要通知SendThread线程，通过SendThread线程进一步更新ClientCnxn客户端连接器的信息，包括readTimeout、connectTimeout、会话状态、HostProvider.lastIndex。

#### 四.生成SyncConnected-None事件

为了让上层应用感知会话已成功创建，SendThread会生成一个SyncConnected-None事件代表会话创建成功，并将该事件通过EventThread的queueEvent()方法传递给EventThread线程。

#### 五.从ZKWatchManager查询Watcher

EventThread线程通过queueEvent方法收到事件后，会从ZKWatchManager管理器查询出对应的Watcher，然后将Watcher放到EventThread的waitingEvents队列中。

客户端的Watcher管理器是ZKWatchManager。

服务端的Watcher管理器是WatchManager。

#### 六.EventThread线程触发处理Watcher

EventThread线程会不断从waitingEvents队列取出待处理的Watcher对象，然后调用Watcher的process()方法来触发Watcher。

## 7.单机版的zk服务端的启动过程

单机版zk服务端的启动，主要分为两个阶段：预启动阶段和初始化阶段，其启动流程图如下：

![图片](assets/a3e71234bf15.png)

### (1)预启动阶段

在zk服务端进行初始化之前，首先要对配置文件等信息进行解析和载入，而zk服务端的预启动阶段的主要工作流程如下：

#### 一.启动程序

QuorumPeerMain类是zk服务的启动入口，可理解为Java中的main函数。通常我们执行zkServer.sh脚本启动zk服务时，就会运行这个类。QuorumPeerMain的main()方法会调用它的initializeAndRun()方法来启动程序。

#### 二.解析zoo.cfg配置文件

在QuorumPeerMain的main()方法中，会执行它的initializeAndRun()方法。

在QuorumPeerMain的initializeAndRun()方法中，便会解析zoo.cfg配置文件。

在ZooKeeperServerMain的initializeAndRun()方法中，也会解析zoo.cfg配置文件。

zoo.cfg配置文件配置了zk运行时的基本参数，包括tickTime、dataDir等。

#### 三.创建和启动历史文件清理器

文件清理器在日常的使用中非常重要。面对大流量的网络访问，zk会产生海量的数据。如果磁盘数据过多或者磁盘空间不足，可能会导致zk服务端不能正常运行，所以zk采用DatadirCleanupManager类去清理历史文件。

其中DatadirCleanupManager类有5个属性，如上代码所示。DatadirCleanupManager会对事务日志和数据快照文件进行定时清理，这种自动清理历史数据文件的机制可以尽量避免zk磁盘空间的浪费。

#### 四.判断集群模式还是单机模式

根据从zoo.cfg文件解析出来的集群服务器地址列表来判断是否是单机模式。如果是单机模式，则会调用ZooKeeperServerMain的main()方法来进行启动。如果是集群模式，则会调用QuorumPeerMain的runFromConfig()方法来进行启动。

### (2)初始化阶段

初始化阶段会根据预启动解析出的配置信息，初始化服务器实例。该阶段的主要工作流程如下：

#### 一.创建数据持久化工具实例FileTxnSnapLog

可以通过FileTxnSnapLog对zk服务器的内存数据进行持久化，具体会将内存数据持久化到配置文件里的事务日志文件 \+ 快照数据文件中。

所以在执行ZooKeeperServerMain的runFromConfig()方法启动zk服务端时，首先会根据zoo.cfg配置文件中的dataDir数据快照目录和dataLogDir事务日志目录，通过"new FileTxnSnapLog()"来创建持久化工具类FileTxnSnapLog的实例。

#### 二.创建服务端统计工具实例ServerStats

ServerStats用于统计zk服务端运行时的状态信息，主要统计的数据包括：服务端向客户端发送的响应包次数、接收客户端发送的请求包次数、服务端处理请求的延迟情况、处理客户端的请求次数。

在执行ZooKeeperServerMain.runFromConfig()方法时，执行到ZooKeeperServer的构造方法就会首先创建ServerStats实例。

#### 三.根据两个工具实例创建单机版服务器实例

ZooKeeperServer是单机版服务端的核心实体类。在执行ZooKeeperServerMain.runFromConfig()方法时，创建完zk数据管理器——持久化工具类FileTxnSnapLog的实例后，就会通过"new ZooKeeperServer()"来创建单机版服务器实例ZooKeeperServer。

此时会传入从zoo.cfg配置文件中解析出的tickTime和会话超时时间来创建服务器实例。创建完服务器实例ZooKeeperServer后，接下来才会对该ZooKeeperServer服务器实例进行更多的初始化工作，包括网络连接器、内存数据库和请求处理器等组件的初始化。

#### 四.创建网络连接工厂实例

zk中客户端和服务端的网络通信，本质是通过Java的IO数据流进行通信的。zk一开始就是使用自己实现的NIO进行网络通信的，但之后引入了Netty框架来满足不同使用情况下的需求。

在执行ZooKeeperServerMain的runFromConfig()方法时，创建完服务器实例ZooKeeperServer后，就会通过ServerCnxnFactory的createFactory()方法来创建服务端网络连接工厂实例ServerCnxnFactory。

ServerCnxnFactory的createFactory()方法首先会获取配置值，判断是使用NIO还是使用Netty，然后再通过反射去实例化服务端网络连接工厂。

可以通过配置zookeeper.serverCnxnFactory来指定使用：zk自己实现的NIO还是Netty框架，来构建服务端网络连接工厂ServerCnxnFactory。

#### 五.初始化网络连接工厂实例

在执行ZooKeeperServerMain的runFromConfig()方法时，创建完服务端网络连接工厂ServerCnxnFactory实例后，就会调用网络连接工厂ServerCnxnFactory的configure()方法来初始化网络连接工厂ServerCnxnFactory实例。

这里以NIOServerCnxnFactory的configure()方法为例，该方法主要会启动一个NIO服务器，以及创建三类线程：

#### 一.处理客户端连接的AcceptThread线程

#### 二.处理客户端请求的一批SelectorThread线程

#### 三.处理过期连接的ConnectionExpirerThread线程

初始化完ServerCnxnFactory实例后，虽然此时NIO服务器已对外开放端口，客户端也能访问到2181端口，但此时zk服务端还不能正常处理客户端请求。

#### 六.启动网络连接工厂实例的线程

在执行ZooKeeperServerMain的runFromConfig()方法时，调用完网络连接工厂ServerCnxnFactory的configure()方法初始化网络连接工厂ServerCnxnFactory实例后，便会调用ServerCnxnFactory的startup()方法去启动ServerCnxnFactory的线程。

注意：对过期连接进行处理是由一个ConnectionExpirerThread线程负责的。

#### 七.恢复单机版服务器实例的本地数据

启动zk服务端需要从本地快照数据文件 \+ 事务日志文件中进行数据恢复。在执行ZooKeeperServerMain的runFromConfig()方法时，调用完ServerCnxnFactory的startup()方法启动ServerCnxnFactory的线程后，就会调用单机版服务器实例ZooKeeperServer的startdata()方法来恢复本地数据。

#### 八.创建并启动服务器实例的会话管理器

会话管理器SessionTracker主要负责zk服务端的会话管理。在执行ZooKeeperServerMain的runFromConfig()方法时，调用完单机版服务器实例ZooKeeperServer的startdata()方法完成本地数据恢复后，就会调用ZooKeeperServer的startup()方法来开始创建并启动会话管理器，也就是在startup()方法中会调用createSessionTracker()和startSessionTracker()方法。SessionTracker其实也是一个继承了ZooKeeperThread的线程。

#### 九.初始化单机版服务器实例的请求处理链

在执行ZooKeeperServerMain的runFromConfig()方法时，在ZooKeeperServer的startup()方法中调用方法创建并启动好会话管理器后，就会继续在ZooKeeperServer的startup()方法中调用方法初始化请求处理链，也就是在startup()方法中会调用setupRequestProcessors()方法。

zk处理请求的方式是典型的责任链模式，zk服务端会使用多个请求处理器来依次处理一个客户端请求。所以在服务端启动时，会将这些请求处理器串联起来形成一个请求处理链。

单机版服务器的请求处理链包括3个请求处理器：

第一个请求处理器是：PrepRequestProcessor

第二个请求处理器是：SyncRequestProcessor

第三个请求处理器是：FinalRequestProcessor

zk服务端会严格按照顺序分别调用这3个请求处理器处理客户端的请求，其中PrepRequestProcessor和SyncRequestProcessor其实也是一个线程。服务端收到的客户端请求会不断被添加到请求处理器的请求队列中，然后请求处理器线程启动后就会不断从请求队列中提取请求出来进行处理。

#### 十.注册单机版服务器实例到网络连接工厂实例

就是调用ServerCnxnFactory的startup()方法中的setZooKeeperServer()方法，将初始化好的单机版服务器实例ZooKeeperServer注册到网络连接工厂实例ServerCnxnFactory。同时，也会将网络连接工厂实例ServerCnxnFactory注册到单机版服务器实例ZooKeeperServer。此时，zk服务端就可以对外提供正常的服务了。

## 8.集群版的zk服务端的启动过程

zk中的集群模式：zk集群会将服务器分成Leader、Follower、Observer三种角色的服务器。在集群运行期间这三种角色的服务器所负责的工作各不相同。

#### 一.Leader角色服务器(处理事务性请求 + 管理其他服务器)

负责处理事务性请求，以及管理集群中的其他服务器。Leader服务器是集群中工作的分配和调度者。

#### 二.Follower服务器(处理非事务性请求 + 选举Leader服务器)

负责处理非事务性请求，以及选举出Leader服务器。发生Leader选举时，系统会从Follow服务器中，根据过半投票原则选举出一个Follower作为Leader服务器。

#### 三.Observer服务器(处理非事务性请求 + 不参与选举和被选举)

负责处理非事务性请求，不参与Leader服务器的选举，也不会作为候选者被选举为Leader服务器。

zk服务端整体架构图如下：

![图片](assets/439ab12f4200.png)

集群版zk服务端的启动分为四个阶段：

预启动阶段、初始化阶段、Leader选举阶段、Leader和Follower启动阶段

集群版zk服务端的启动流程图如下：

![图片](assets/9f946248ac31.png)

### (1)预启动阶段

在zk服务端进行初始化之前，首先要对配置文件等信息进行解析和载入，而zk服务端的预启动阶段的主要工作流程如下：

#### 一.QuorumPeerMain启动程序

#### 二.解析zoo.cfg配置文件

#### 三.创建和启动历史文件清理器

#### 四.根据配置判断是集群模式还是单机模式

首先zk服务端会调用QuorumPeerMain类中的main()方法，然后在QuorumPeerMain的initializeAndRun()方法里解析zoo.cfg配置文件。接着继续在initializeAndRun()方法中创建和启动历史文件清理器，以及根据配置文件和启动参数，即args参数和config.isDistributed()方法，来判断zk服务端的启动方式是集群模式还是单机模式。如果配置参数中配置了相关的配置项，并且已经指定了集群模式运行，那么在服务启动时就会调用runFromConfig()方法完成集群模式的初始化。

### (2)初始化阶段

#### 一.创建网络连接工厂实例ServerCnxnFactory

在执行QuorumPeerMain的runFromConfig()方法时，首先会通过ServerCnxnFactory的createFactory()方法来创建服务端网络连接工厂。

ServerCnxnFactory的createFactory()方法首先会获取配置值，判断是使用NIO还是使用Netty，然后再通过反射去实例化服务端网络连接工厂。

可以通过配置zookeeper.serverCnxnFactory来指定使用：zk自己实现的NIO还是Netty框架，来构建服务端网络连接工厂。

#### 二.初始化网络连接工厂实例ServerCnxnFactory

在执行QuorumPeerMain的runFromConfig()方法时，创建完服务端网络连接工厂实例ServerCnxnFactory后，就会调用网络连接工厂ServerCnxnFactory的configure()方法来初始化ServerCnxnFactory实例。

这里以NIOServerCnxnFactory的configure()方法为例，该方法主要会启动一个NIO服务器，以及创建三类线程：

#### 一.处理客户端连接的AcceptThread线程

#### 二.处理客户端请求的一批SelectorThread线程

#### 三.处理过期连接的ConnectionExpirerThread线程

初始化完ServerCnxnFactory实例后，虽然此时NIO服务器已对外开放端口，客户端也能访问到2181端口，但此时zk服务端还不能正常处理客户端请求。

#### 三.创建集群版服务器实例QuorumPeer

在执行QuorumPeerMain的runFromConfig()方法时，创建和初始化完网络连接工厂实例ServerCnxnFactory后，接着就会调用QuorumPeerMain的getQuorumPeer()方法创建集群版服务器实例。

ZooKeeperServer是单机版服务端的核心实体类。

QuorumPeer是集群版服务端的核心实体类。

可以将每个QuorumPeer类实例看作是集群中的一台服务器。在zk集群模式中，一个QuorumPeer类实例一般具有3种状态，分别是：

状态一：参与Leader节点的选举

状态二：作为Follower节点同步Leader节点的数据

状态三：作为Leader节点管理集群的Follower节点

在执行QuorumPeerMain的runFromConfig()方法时，创建完QuorumPeer实例后，接着会将集群版服务运行中需要的核心工具类注册到QuorumPeer实例中。这些核心工具类也是单机版服务端运行时需要的，比如：数据持久化类FileTxnSnapLog、NIO工厂类ServerCnxnFactory等。然后还会将配置文件中的服务器地址列表、Leader选举算法、会话超时时间等设置到QuorumPeer实例中。

#### 四.创建数据持久化工具FileTxnSnapLog并设置到QuorumPeer实例中

可以通过FileTxnSnapLog对zk服务器的内存数据进行持久化，具体会将内存数据持久化到配置文件的事务日志文件 \+ 快照数据文件中。

在执行QuorumPeerMain的runFromConfig()方法时，创建完QuorumPeer实例后，首先会根据zoo.cfg配置文件中的dataDir数据快照目录和dataLogDir事务日志目录，通过"new FileTxnSnapLog()"来创建FileTxnSnapLog类实例，然后设置到QuorumPeer实例中。

#### 五.创建内存数据库ZKDatabase并设置到QuorumPeer实例中

ZKDatabase是zk的内存数据库，主要负责管理zk的所有会话记录以及DataTree和事务日志的存储。

在执行QuorumPeerMain的runFromConfig方法时，创建完QuorumPeer实例以及创建完数据持久化工具FileTxnSnapLog并设置到QuorumPeer后，就会将持久化工具FileTxnSnapLog作为参数去创建ZKDatabase实例，然后设置到QuorumPeer实例。

#### 六.初始化集群版服务器实例QuorumPeer

除了需要将一些核心组件注册到服务器实例QuorumPeer中去，还需要对服务器实例QuorumPeer根据zoo.cfg配置文件设置一些参数，比如服务器地址列表、Leader选举算法、会话超时时间等。其中这些核心组件包括：数据持久化工具FileTxnSnapLog、服务端网络连接工厂ServerCnxnFactory、内存数据库ZKDatabase。

完成初始化QuorumPeer实例并启动QuorumPeer线程后，便会通过QuorumPeer的join()方法将main线程挂起，等待QuorumPeer线程结束后再执行。

#### 七.恢复集群版服务器实例QuorumPeer本地数据

在执行QuorumPeerMain的runFromConfig()方法时，初始化完QuorumPeer实例后，就会调用QuorumPeer的start()方法来启动集群中的服务器。

在QuorumPeer的start()方法中，首先会调用QuorumPeer的loadDataBase()方法来恢复数据。

#### 八.启动网络连接工厂ServerCnxnFactory主线程

在QuorumPeer的start()方法中，在调用完QuorumPeer的loadDataBase()方法来恢复本地数据之后，便会调用QuorumPeer的startServerCnxnFactory()方法来启动网络连接工厂的主线程。

### (3)Leader选举阶段

在QuorumPeer的start()方法中，调用完loadDataBase()和startServerCnxnFactory()方法，恢复好本地数据以及启动完网络连接工厂ServerCnxnFactory的线程后，便会调用QuorumPeer的startLeaderElection()方法进行Leader选举。

#### 一.初始化Leader选举(初始化当前投票 + 监听选举端口 + 启动选举守护线程)

Leader选举是集群版的zk服务端和单机版的zk服务端的最大不同点。首先QuorumPeer的startLeaderElection()方法会通过"new Vote()"，根据服务器ID、最新的事务ID和当前的服务器epoch，来初始化当前投票。也就是在Leader选举的初始化过程中，集群版zk的每个服务器都会给自己投票。

然后当QuorumPeer的startLeaderElection()方法完成初始化当前投票后，会调用QuorumPeer的createElectionAlgorithm()方法去初始化选举算法，即监听选举端口3888 \+ 启动选举守护线程。

而在QuorumPeer的createElectionAlgorithm()方法中：首先会创建Leader选举所需的网络IO实例QuorumCnxManager。QuorumCnxManager实例会启动Listener线程对Leader选举端口进行监听，用来等待集群中其他服务器发送的请求。

然后会创建FastLeaderElection选举算法实例，zk默认使用FastLeaderElection选举算法，每一个QuorumPeer实例都会有一个选举算法实例。

接着会启动选举算法FastLeaderElection实例使用的守护线程，其中发送投票的守护线程会不断从发送队列中取出消息进行发送，接收投票的守护线程会不断从接收队列中取出消息进行处理。

#### 二.启动QuorumPeer线程检测当前服务器状态

QuorumPeer也是一个继承了ZooKeeperThread的线程。当QuorumPeer的startLeaderElection()方法完成初始化Leader选举后，便会启动QuorumPeer线程通过while循环不断检查当前服务器状态。

QuorumPeer线程的核心工作就是不断地检测当前服务器的状态并做相应处理。服务器状态会在LOOKING、LEADING、FOLLOWING/OBSERVING之间进行切换。在集群版zk服务端启动时，QuorumPeer的初始状态是LOOKING，所以QuorumPeer线程就会判断此时需要更新当前投票进行Leader选举。

#### 三.进行Leader选举

zk的Leader选举过程，其实就是集群中所有机器相互间进行一系列投票，选举产生最合适的机器成为Leader，其余机器成为Follower或Observer，然后对这些已经确定集群角色的机器通过QuorumPeer线程进行初始化的过程。

Leader选举算法：

就是集群中哪个机器处理的数据越新，就越有可能成为Leader。先通过每个服务器处理过的最大ZXID来比较谁的数据最新，如果每个机器处理的ZXID一致，那么最大SID的服务器就成为Leader。

### (4)Leader和Follower启动阶段

当zk完成Leader选举后，集群中每个服务器基本都已确定自己的角色。zk将集群中的机器分为Leader、Follower、Obervser三种角色，每种角色在集群中起到的作用都各不相同。

Leader角色主要负责处理客户端发送的数据变更等事务性请求，并管理协调集群中Follower角色的服务器。Follower角色则主要处理客户端的获取数据等非事务性请求。Observer角色的服务器的功能和Follower角色的服务器的功能相似，唯一的不同就是不会参与Leader的选举工作。

zk中的这三种角色服务器，在服务启动过程中也有各自的不同，下面分析Leader角色和Follower角色在启动过程中的工作原理，也就是Leader角色和Follower角色启动过程中的交互步骤。

Leader服务端和Follower客户端的启动交互：

![图片](assets/5294fe675f1f.png)

#### 一.创建Leader服务端实例和Follower客户端实例

由于QuorumPeer线程会不断检测当前服务器的状态并做相应处理，所以当QuorumPeer线程 + FastLeaderElection守护线程完成Leader选举后，每个zk服务器都会根据节点状态创建相应的角色实例来完成数据同步。

比如zk服务器QuorumPeer实例，如果通过getPeerState()方法发现自己的节点状态为LEADING，那么就会调用QuorumPeer的makeLeader()方法来创建Leader服务端实例。如果通过getPeerState()方法发现自己的节点状态为FOLLOWERING，那么就会调用QuorumPeer的makeFollower()方法来创建Follower客户端实例。

#### 二.Leader启动时会创建LearnerCnxAcceptor监听Learner的连接

当QuorumPeer线程通过makeLeader()方法创建好Leader服务端实例后，就会通过调用Leader的lead()方法来启动Leader服务端实例。

首先在Leader的构造方法中，会创建BIO的ServerSocket并监听2888端口。然后在Leader的lead()方法中，会创建Learner接收器LearnerCnxAcceptor。而Leader的lead()方法里会有一个while循环，不断处理与Learner的心跳等。

所有非Leader角色都可称为Learner角色，Follower会继承Learner。LearnerCnxAcceptor接收器则用于接收所有Learner客户端的连接请求。

#### 三.Learner启动时会发起请求建立和Leader的连接

当QuorumPeer线程通过makeFollower()方法创建好Follower客户端实例后，就会调用Follower的followLeader()方法来启动Follower客户端实例。在Follower的followLeader()方法中，也就是在Learner客户端实例创建完后，会通过findLeader()方法从Leader选举的投票结果中找到Leader服务端，然后通过connectToLeader()方法来建立和该Leader服务端之间的连接。connectToLeader()方法尝试建立连接时，最多尝试5次，每次睡眠1秒。Follower的followLeader()方法中，会有一个while循环不断处理心跳等消息。

#### 四.Leader会为请求连接的每个Learner创建一个LearnerHandler

LearnerCnxAcceptor也是一个线程。Leader服务端启动时会创建和启动Learner接收器LearnerCnxAcceptor，LearnerCnxAcceptor线程里会通过while循环不断监听Learner发起的连接。

当Leader服务端实例接收到来自Learner的连接请求后，LearnerCnxAcceptor线程就会通过ServerSocket监听到Learner连接请求。此时，LearnerCnxAcceptor就会创建一个LearnerHandler实例。每个LearnerHandler实例都对应了一个Leader与Learner之间的连接，LearnerHandler负责Leader与Learner间几乎所有的消息通信和数据同步。

LearnerHandler也是一个线程，LearnerHandler会通过BIO + while循环来处理和Learner的通信、数据同步和心跳。

#### 五.Learner建立和Leader的连接后会向Leader发送LearnerInfo进行注册

当Learner通过Learner的connectToLeader()方法和Leader建立起连接后，就会通过Learner的registerWithLeader()方法开始向Leader进行注册。也就是将Learner客户端自己的基本信息LearnerInfo发送给Leader服务端，LearnerInfo中会包括当前服务器的SID和处理事务的最新ZXID。

#### 六.Leader解析LearnerInfo计算出epoch并发送LeaderInfo给Learner

由于Leader的LearnerCnxAcceptor在接收到来自Learner的连接请求后，会创建LearnerHandler来处理Leader与Learner的消息通信和数据同步。所以当Learner通过registerWithLeader()方法向Leader发起注册请求后，Leader服务端下对应的LearnerHandler线程就能收到LearnerInfo信息，于是便会根据LearnerInfo信息解析出Learner的SID和ZXID。

首先调用ZxidUtils的getEpochFromZxid()方法，通过将Learner的ZXID右移32位来解析出Learner的epoch。然后调用Leader的getEpochToPropose()方法比较Learner和Leader的epoch，如果Learner的epoch大，则更新Leader的epoch为Learner的epoch + 1。

接着在Leader的getEpochToPropose()方法中，会将Learner的SID添加到HashSet类型的connectingFollowers中。通过Leader的connectingFollowers的wait()方法和notifyAll()方法，便能实现让LearnerHandler进行等待和唤醒。

直到过半Learner已向Leader进行了注册，同时更新了Leader的epoch，之后Leader就可以确定当前集群的epoch了。可见，可以通过Object的wait()方法和notifyAll()方法来实现过半效果：未过半则进行阻塞，过半则进行通知继续后续处理。

当确定好当前集群的epoch后，Leader的每个LearnerHandler，都会发送一个包含该epoch的LeaderInfo消息给对应的Learner，然后再通过Leader的waitForEpochAck()方法等待过半Learner的响应。

#### 七.Learner收到Leader发送的LeaderInfo后会反馈ackNewEpoch消息

Learner通过Learner的writePacket()方法向Leader发送LearnerInfo消息后，会继续通过Learner的readPacket()方法接收Leader返回的LeaderInfo响应。当Learner接收到Leader的LearnerHandler返回的LeaderInfo消息后，就会解析出epoch和ZXID，然后向Leader反馈一个ackNewEpoch响应。

#### 八.Leader收到过半Learner的ackNewEpoch消息后开始进行数据同步

Leader每收到一个Learner的连接请求，都会启动一个LearnerHandler处理。每个LearnerHandler线程都会首先通过Leader的getEpochToPropose()方法，阻塞等待过半Learner发送LearnerInfo信息发起对Leader的注册。

当过半Learner已经向Leader进行注册后，每个LearnerHandler线程又继续发送LeaderInfo信息给Learner确认epoch，然后通过Leader的waitForEpochAck()方法，阻塞等待过半Learner返回响应。

当Leader接收到过半Learner向Leader发送的ackNewEpoch响应后，每个LearnerHandler线程便会开始执行与Learner间的数据同步，而Learner会通过Learner的syncWithLeader()方法执行与Leader的数据同步。

#### 九.过半Learner完成数据同步就启动Leader和Learner绑定的服务器实例

Follower客户端绑定了FollowerZooKeeperServer服务器实例，Leader服务端绑定了LeaderZooKeeperServer服务器实例。

在Leader的lead()方法中，首先创建Learner接收器LearnerCnxAcceptor监听Learner发起的连接请求，然后Leader的lead()方法会阻塞等待过半Learner完成向Leader的注册，接着Leader的lead()方法会阻塞等待过半Learner返回ackNewEpoch响应，接着Leader的lead()方法会阻塞等待过半Learner完成数据同步，然后执行Leader的startZkServer()方法启动Leader绑定的服务器实例，也就是执行LeaderZooKeeperServer的startup()方法启动服务器。

而在Learner进行数据同步的Learner的syncWithLeader()方法中，完成数据同步后同样会启动Learner绑定的服务器实例，也就是执行LearnerZooKeeperServer的startup()方法启动服务器。

Leader和Learner绑定的服务器实例的启动步骤，主要就是执行ZooKeeperServer的startup()方法，即：创建并启动会话管理器 \+ 初始化服务器的请求处理链。

## 9.创建会话

会话是zk中最核心的概念之一，客户端与服务端的交互都离不开会话的相关操作。其中包括临时节点的生命周期、客户端请求的顺序、Watcher通知机制等。比如会话关闭时，服务端会自动删除该会话所创建的临时节点。当客户端会话退出，通过Watcher机制可向订阅该事件的客户端发送通知。

### (1)客户端的会话状态

当zk客户端与服务端成功建立连接后，就会创建一个会话。在zk客户端的运行过程(会话生命周期)中，会话会经历不同的状态变化。

这些不同的会话状态包括：正在连接(CONNECTING)、已经连接(CONNECTED)、会话关闭(CLOSE)、正在重新连接(RECONNECTING)、已经重新连接(RECONNECTED)等。

如果zk客户端需要与服务端建立连接创建一个会话，那么客户端就必须提供一个使用字符串表示的zk服务端地址列表。

当客户端刚开始创建ZooKeeper对象时，其会话状态就是CONNECTING，之后客户端会根据服务端地址列表中的IP地址分别尝试进行网络连接。如果成功连接上zk服务端，那么客户端的会话状态就会变为CONNECTED。

如果因为网络闪断或者其他原因造成客户端与服务端之间的连接断开，那么zk客户端会自动进行重连操作，同时其会话状态变为CONNECTING，直到重新连接上zk服务端后，客户端的会话状态才变回CONNECTED。

通常 总是在CONNECTING或CONNECTED间切换。如果出现会话超时、权限检查失败、客户端主动退出程序等情况，那么客户端的会话状态就会直接变为CLOSE。

### (2)服务端的会话创建

在zk服务端中，使用SessionImpl表示客户端与服务器端连接的会话实体。SessionImpl由三个部分组成：会话ID(sessionID)、会话超时时间(timeout)、会话关闭状态(isClosing)。

#### 一.会话ID

会话ID是一个会话的标识符，当创建一次会话时，zk服务端会自动为其分配一个唯一的ID。

#### 二.会话超时时间

一个会话的超时时间就是指一次会话从发起后到被服务器关闭的时长。设置会话超时时间后，zk服务端会参考设置的超时时间，最终计算一个服务端自己的超时时间。这个超时时间才是真正被zk服务端用于管理用户会话的超时时间。

#### 三.会话关闭状态

会话关闭状态isClosing表示一个会话是否已经关闭。如果zk服务端检查到一个会话已经因为超时等原因失效时，就会将该会话的isClosing标记为关闭，之后就不再对该会话进行操作。

服务端收到客户端的创建会话请求后，进行会话创建的过程大概分四步：处理ConnectRequest请求、创建会话、请求处理链处理和会话响应。

步骤一：处理ConnectRequest请求

首先由NettyServerCnxn负责接收来自客户端的创建会话请求，然后反序列化出ConnectRequest对象，并完成会话超时时间的协商。

步骤二：创建会话

SessionTrackerImpl的createSession()方法会为该会话分配一个sessionID，并将该sessionID注册到sessionsById和sessionsWithTimeout中，同时通过SessionTrackerImpl的updateSessionExpiry()方法进行会话激活。

步骤三：请求处理链处理

接着调用ZooKeeperServer.firstProcessor的processRequest()方法，让该会话请求会在zk服务端的各个请求处理器之间进行顺序流转。

步骤四：会话响应

最后在请求处理器FinalRequestProcessor的processRequest()方法中进行会话响应。

### (3)会话ID的初始化实现

SessionTracker是zk服务端的会话管理器，zk会话的整个生命周期都离不开SessionTracker的参与。SessionTracker是一个接口类型，规定了会话管理的相关操作行为，具体的会话管理逻辑则由SessionTrackerImpl来完成。

SessionTrackerImpl类实现了SessionTracker接口，其中有四个关键字段：sessionExpiryQueue字段表示的是会话过期队列，用于管理会话自动过期。nextSessionId字段记录了当前生成的会话ID。sessionsById字段用于根据会话ID来管理具体的会话实体。sessionsWithTimeout字段用于根据会话ID管理会话的超时时间。

在SessionTrackerImpl类初始化时，会调用initializeNextSession()方法来生成一个初始化的会话ID。之后在zk的运行过程中，会在该会话ID的基础上为每个会话分配ID。

在SessionTrackerImpl的initializeNextSession()方法中，生成初始化的会话ID的过程如下：

步骤一：获取当前时间的毫秒表示

步骤二：将得到的毫秒表示的时间先左移24位

步骤三：将左移24位后的结果再右移8位

步骤四：服务器SID左移56位

步骤五：将右移8位的结果和左移56位的结果进行位与运算

算法概述：高8位确定所在机器，低56位使用当前时间的毫秒表示来进行随机。其中左移24位的目的是：将毫秒表示的时间的最高位的1移出，可以防止出现负数。

```javascript
//时间的二进制表示，41位
10100000110000011110001000100110111110111
//左移24位变成，64位
0100000110000011110001000100110111110111000000000000000000000000
//右移8位变成，64位
0000000001000001100000111100010001001101111101110000000000000000
//假设服务器SID为2，那么左移56位变成
0000001000000000000000000000000000000000000000000000000000000000
//位与运算
0000001001000001100000111100010001001101111101110000000000000000
```

### (4)设置的会话超时时间没生效的原因

在平时的开发工作中，最常遇到的场景就是会话超时异常。zk的会话超时异常包括：客户端readTimeout异常和服务端sessionTimeout异常。

需要注意的是：可能虽然设置了超时时间，但实际服务运行时zk并没有按设置的超时时间来管理会话。

这是因为实际起作用的超时时间是由客户端和服务端协商决定的。zk客户端在和服务端建立连接时，会提交一个客户端设置的会话超时时间，而该超时时间会和服务端设置的最大超时时间和最小超时时间进行比较。如果正好在服务端设置允许的范围内，则采用客户端的超时时间管理会话。如果大于或小于服务端设置的超时时间，则采用服务端的超时时间管理会话。

## 10.分桶策略和会话管理

zk作为分布式系统的核心组件，经常要处理大量的会话请求。zk之所以能快速响应大量客户端操作，与它自身的会话管理策略密不可分。

### (1)分桶策略和过期队列

#### 一.会话管理中的心跳消息和过期时间

在zk中为了保持会话的存活状态，客户端要向服务端周期性发送心跳信息。客户端的心跳信息可以是一个PING请求，也可以是一个普通的业务请求。

zk服务端收到请求后，便会更新会话的过期时间，来保持会话的存活状态。因此zk的会话管理，最主要的工作就是管理会话的过期时间。

zk服务端的会话管理是由SessionTracker负责的，会话管理器SessionTracker采用了分桶策略来管理会话的过期时间。

#### 二.分桶策略的原理

会话管理器SessionTracker会按照不同的时间间隔对会话进行划分，超时时间相近的会话将会被放在同一个间隔区间中。

具体的划分原则就是：每个会话的最近过期时间点ExpirationTime，ExpirationTime是指会话最近的过期时间点。

![图片](assets/b1f78293640f.png)

对于一个新会话创建完毕后，zk服务端都会计算其ExpirationTime，会话管理器SessionTracker会每隔ExpirationInterval进行会话超时检查。

```javascript
//CurrentTime是指当前时间，单位毫秒
//SessionTimeout指会话的超时时间，单位毫秒
//SessionTrackerImpl会每隔ExpirationInterval进行会话超时检查
ExpirationTime = CurrentTime + SessionTimeout
ExpirationTime= (ExpirationTime / ExpirationInterval + 1) * ExpirationInterval
```

这种方式避免了对每一个会话进行检查。采用分批次的方式管理会话，可以降低会话管理的难度。因为每次小批量的处理会话过期可以提高会话处理的效率。

#### 三.分桶策略的过期队列和bucket

zk服务端所有会话过期的相关操作都是围绕过期队列来进行的，可以说zk服务端底层就是通过这个过期队列来管理会话过期的。过期队列就是ExpiryQueue类型的sessionExpiryQueue。

什么是bucket：

SessionTracker的过期队列是ExpiryQueue类型的，ExpiryQueue类型的过期队列会由若干个bucket组成。每个bucket是以expirationInterval为单位进行时间区间划分的。每个bucket中会存放一些在某一时间点内过期的会话。

如何实现过期队列：

在zk中会使用ExpiryQueue类来实现一个会话过期队列。ExpiryQueue类中有两个HashMap：elemMap和一个expiryMap。elemMap中存放会话对象SessionImpl及其对应的最近过期时间点，expiryMap中存放的就是过期队列。

expiryMap的key就是bucket的时间划分，即会话的最近过期时间点。expiryMap的value就是bucket中存放的某一时间内过期的会话集合。所以bucket可以理解为一个Set会话对象集合。expiryMap是线程安全的HaspMap，可根据不同的过期时间区间存放会话。expiryMap过期队列中的一个过期时间点就对应一个bucket。

ExpiryQueue中也实现了remove()、update()、poll()等队列的操作方法。超时检查的定时任务一开始会获取最近的会话过期时间点看看当前是否已经到达，然后从过期队列中poll出bucket时会更新下一次的最近的会话过期时间点。

### (2)会话激活

为了保持客户端会话的有效性，客户端要不断发送PING请求进行心跳检测。服务端要不断接收客户端的这个心跳检测，并重新激活对应的客户端会话。这个重新激活会话的过程由SessionTracker的touchSession()方法实现。

由于ZooKeeperServer的submitRequest()方法会调用touch()方法激活会话，所以只要客户端有请求发送到服务端，服务端就会进行一次会话激活。

执行SessionTracker的touchSession()方法进行会话激活的主要流程如下：

#### 一.检查该会话是否已经被关闭

如果该会话已经被关闭，则返回，不用激活会话。

#### 二.计算该会话新的过期时间点newExpiryTime

调用ExpiryQueue的roundToNextInterval()方法计算会话新的过期时间点。通过总时间除以间隔时间然后向上取整再乘以间隔时间来计算新的过期时间点。

#### 三.将该会话添加到新的过期时间点对应的bucket中

从过期队列expiryMap获取新的过期时间点对应的bucket，然后添加该会话到新的过期时间点对应的bucket中。

#### 四.将该会话从旧的过期时间点对应的bucket中移除

从elemMap中获取该会话旧的过期时间点，然后将该会话从旧的过期时间点对应的bucket中移除。

### (3)会话超时检查

SessionTracker中会有一个线程专门进行会话超时检查，该线程会依次对bucket会话桶中剩下的会话进行清理，超时检查线程的定时检查时间间隔其实就是expirationInterval。

当一个会话被激活时，SessionTracker会将其从上一个bucket会话桶迁移到下一个bucket会话桶。所以超时检查线程的任务就是检查bucket会话桶中没被迁移的会话。

超时检查线程是如何进行定时检查的：

由于会话分桶策略会将expirationInterval的倍数作为会话最近过期时间点，所以超时检查线程只要在expirationInterval倍数的时间点进行检查即可。这样既提高了效率，而且由于是批量清理，因此性能也非常好。这也是zk要通过分桶策略来管理客户端会话的最主要原因。一个zk集群的客户端会话可能会非常多，逐个依次检查会非常耗费时间。

### (4)会话清理

当SessionTracker的会话超时检查线程遍历出一些已经过期的会话时，就要进行会话清理了，会话清理的步骤如下：

#### 一.标记会话状态为已关闭

SessionTracker的setSessionClosing()方法会标记会话状态为已关闭，这是因为整个会话清理过程需要一段时间，为了保证在会话清理期间不再处理来自该会话对应的客户端的请求，SessionTracker会首先将该会话的isClosing属性标记为true。

#### 二.发起关闭会话请求

ZooKeeperServer的expire()方法和close()方法会发起关闭会话请求，为了使对该会话的关闭操作在整个服务端集群中都生效，zk使用提交"关闭会话"请求的方式，将请求交给PrepRequestProcessor处理。

#### 三.收集临时节点

PrepRequestProcessor的pRequest2Txn()方法会收集需要清理的临时节点。在zk中，一旦某个会话失效，那么和该会话相关的临时节点也要被清除掉。因此需要首先将服务器上所有和该会话相关的临时节点找出来。

zk的内存数据库会为每个会话都保存一份由该会话维护的临时节点集合。因此在会话清理阶段，只需根据当前即将关闭的会话的sessionID，便可以从zk的内存数据库中获取到该会话的临时节点列表。

#### 四.添加临时节点的删除请求到事务变更队列

将临时节点的删除请求添加到事务变更队列outstandingChanges中。完成该会话相关的临时节点收集后，zk会将这些临时节点逐个转换成节点删除请求，添加到事务变更队列中。

#### 五.删除临时节点

FinalRequestProcessor的processRequest()方法触发删除临时节点。当收集完所有需要删除的临时节点，以及创建了对应的节点删除请求后，便会在FinalRequestProcessor的processRequest()方法中，通过调用ZooKeeperServer的processTxn()方法，调用到ZKDatabase的processTxn()方法，最后调用DataTree的killSession()方法，从而最终删除内存数据库中该会话的所有临时节点。

#### 六.移除会话

在FinalRequestProcessor的processRequest()方法中，会通过调用ZooKeeperServer的processTxn()方法，调用到SessionTracker的removeSession()方法将会话从SessionTracker移除。即从sessionsById、sessionsWithTimeout、sessionExpiryQueue中移除会话。

#### 七.关闭NIOServerCnxn

在FinalRequestProcessor的processRequest()方法中，最后会调用FinalRequestProcessor的closeSession()方法，从NIOServerCnxnFactory的sessionMap中将该会话进行移除。
