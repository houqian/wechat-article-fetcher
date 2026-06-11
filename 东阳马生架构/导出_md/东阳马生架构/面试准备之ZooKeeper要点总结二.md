# 面试准备之ZooKeeper要点总结二

> **公众号**: 东阳马生架构  
> **发布时间**: 2025-09-24 09:37  

**大纲(25826字)**

- 1.zk实现数据发布订阅
- 2.zk实现负载均衡
- 3.zk实现分布式命名服务
- 4.zk实现分布式协调(Master-Worker协同)
- 5.zk实现分布式通信
- 6.zk实现Master选举
- 7.zk实现分布式锁
- 8.zk实现分布式队列和分布式屏障
- 9.基于Curator进行基本的zk数据操作
- 10.基于Curator实现Leader选举
- 11.基于Curator实现分布式Barrier
- 12.基于Curator实现分布式计数器
- 13.基于Curator实现zk的节点和子节点监听机制
- 14.基于Curator创建客户端实例的源码分析
- 15.Curator在启动时是如何跟zk建立连接的
- 16.基于Curator进行增删改查节点的源码分析
- 17.基于Curator的节点监听回调机制的实现源码
- 18.基于Curator的Leader选举机制的实现源码


## 1.zk实现数据发布订阅

### (1)发布订阅系统一般有推模式和拉模式

推模式：服务端主动将更新的数据发送给所有订阅的客户端。

拉模式：客户端主动发起请求来获取最新数据(定时轮询拉取)。

### (2)zk采用了推拉相结合来实现发布订阅

首先客户端需要向服务端注册自己关注的节点(添加Watcher事件)。一旦该节点发生变更，服务端就会向客户端发送Watcher事件通知。客户端接收到消息通知后，需要主动到服务端获取最新的数据。所以，zk的Watcher机制有一个缺点就是：客户端不能定制服务端回调，需要客户端收到Watcher通知后再次向服务端发起请求获取数据，多进行一次网络交互。

如果将配置信息放到zk上进行集中管理，那么：

一.应用启动时需主动到zk服务端获取配置信息，然后在指定节点上注册一个Watcher监听。

二.只要配置信息发生变更，zk服务端就会实时通知所有订阅的应用，让应用能实时获取到订阅的配置信息节点已发生变更的消息。

注意：原生zk客户端可以通过getData()、exists()、getChildren()三个方法，向zk服务端注册Watcher监听，而且注册的Watcher监听具有一次性，所以zk客户端获得服务端的节点变更通知后需要再次注册Watcher。

### (3)使用zk来实现数据发布订阅总结

步骤一：将配置信息存储到zk的节点上。

步骤二：应用启动时首先从zk节点上获取配置信息，然后再向该zk节点注册一个数据变更的Watcher监听。一旦该zk节点数据发生变更，所有订阅的客户端就能收到数据变更通知。

步骤三：应用收到zk服务端发过来的数据变更通知后重新获取最新数据。

### (4)zk原生实现分布式配置(也就是实现注册发现或者数据发布订阅)

配置可以使用数据库、Redis、或者任何一种可以共享的存储位置。使用zk的目的，主要就是利用它的回调机制。任何zk的使用方不需要去轮询zk，Redis或者数据库可能就需要主动轮询去看看数据是否发生改变。使用zk最大的优势是只要对数据添加Watcher，数据发生修改时zk就会回调指定的方法。注意：new一个zk实例和向zk获取数据都是异步的。

如下的做法其实是一种Reactor响应式编程：使用CoundownLatch阻塞及通过调用一次数据来触发回调更新本地的conf。我们并没有每个场景都线性写一个方法堆砌起来，而是用相应的回调和Watcher事件来粘连起来。其实就是把所有事件发生前后要做的事情粘连起来，等着回调来触发。

#### 一.先定义一个工具类可以获取zk实例

```java
public class ZKUtils {
    private static ZooKeeper zk;
    private static String address = "192.168.150.11:2181,192.168.150.12:2181,192.168.150.13:2181,192.168.150.14:2181/test";
    private static DefaultWatcher defaultWatcher = new DefaultWatcher();
    private static CountDownLatch countDownLatch = new CountDownLatch(1);

    public static ZooKeeper getZK() {
        try {
            zk = new ZooKeeper(address, 1000, defaultWatcher);
            defaultWatcher.setCountDownLatch(countDownLatch);
            //阻塞直到建立好连接拿到可用的zk
            countDownLatch.await();
        } catch (Exception e) {
            e.printStackTrace();
        }
        return zk;
    }
}
```

#### 二.定义和zk建立连接时的Watcher

```cs
public class DefaultWatcher implements Watcher {
    CountDownLatch countDownLatch ;

    public void setCountDownLatch(CountDownLatch countDownLatch) {
        this.countDownLatch = countDownLatch;
    }

    @Override
    public void process(WatchedEvent event) {
        System.out.println(event.toString());
        switch (event.getState()) {
            case Unknown:
                break;
            case Disconnected:
                break;
            case NoSyncConnected:
                break;
            case SyncConnected:
                countDownLatch.countDown();
                break;
            case AuthFailed:
                break;
            case ConnectedReadOnly:
                break;
            case SaslAuthenticated:
                break;
            case Expired:
                break;
        }
    }
}
```

#### 三.定义分布式配置的核心类WatcherCallBack

这个WatcherCallBack类不仅实现了Watcher，还实现了两个异步回调。

首先通过zk.exists()方法判断配置的znode是否存在并添加监听(自己) + 回调(自己)，然后通过countDownLatch.await()方法进行阻塞。

在回调中如果发现存在配置的znode，则设置配置并执行countDown()方法不再进行阻塞。

在监听中如果发现数据变化，则会调用zk.getData()方法获取配置的数据，并且获取配置的数据时也会继续监听(自己) + 回调(自己)。

```typescript
public class WatcherCallBack implements Watcher, AsyncCallback.StatCallback, AsyncCallback.DataCallback {
    ZooKeeper zk;
    MyConf conf;
    CountDownLatch countDownLatch = new CountDownLatch(1);

    public MyConf getConf() {
        return conf;
    }

    public void setConf(MyConf conf) {
        this.conf = conf;
    }

    public ZooKeeper getZk() {
        return zk;
    }

    public void setZk(ZooKeeper zk) {
        this.zk = zk;
    }

    //判断配置是否存在并监听配置的znode
    public void aWait(){
        zk.exists("/AppConf", this, this ,"ABC");
        try {
            countDownLatch.await();
        } catch (InterruptedException e) {
            e.printStackTrace();
        }
    }

    //回调自己，这是执行完zk.exists()方法或者zk.getData()方法的回调
    //在回调中如果发现存在配置的znode，则设置配置并执行countDown()方法不再进行阻塞。
    @Override
    public void processResult(int rc, String path, Object ctx, byte[] data, Stat stat) {
        if (data != null) {
            String s = new String(data);
            conf.setConf(s);
            countDownLatch.countDown();
        }
    }

    //监听自己，这是执行zk.exists()方法或者zk.getData()方法时添加的Watcher监听
    //在监听中如果发现数据变化，则会继续调用zk.getData()方法获取配置的数据，并且获取配置的数据时也会继续监听(自己) + 回调(自己)
    @Override
    public void processResult(int rc, String path, Object ctx, Stat stat) {
        if (stat != null) {//stat不为空, 代表节点已经存在
            zk.getData("/AppConf", this, this, "sdfs");
        }
    }

    @Override
    public void process(WatchedEvent event) {
        switch (event.getType()) {
            case None:
                break;
            case NodeCreated:
                //调用一次数据, 这会触发回调更新本地的conf
                zk.getData("/AppConf", this, this, "sdfs");
                break;
            case NodeDeleted:
                //容忍性, 节点被删除, 把本地conf清空, 并且恢复阻塞
                conf.setConf("");
                countDownLatch = new CountDownLatch(1);
                break;
            case NodeDataChanged:
                //数据发生变更, 需要重新获取调用一次数据, 这会触发回调更新本地的conf
                zk.getData("/AppConf", this, this, "sdfs");
                break;
            case NodeChildrenChanged:
                break;
        }
    }
}
```

分布式配置的核心配置类：

```typescript
//MyConf是配置中心的配置
public class MyConf {
    private  String conf ;
    public String getConf() {
        return conf;
    }

    public void setConf(String conf) {
        this.conf = conf;
    }
}
```

#### 四.通过WatcherCallBack的方法判断配置是否存在并尝试获取数据

```cs
public class TestConfig {
    ZooKeeper zk;

    @Before
    public void conn () {
        zk = ZKUtils.getZK();
    }

    @After
    public void close () {
        try {
            zk.close();
        } catch (InterruptedException e) {
            e.printStackTrace();
        }
    }

    @Test
    public void getConf() {
        WatchCallBack watchCallBack = new WatchCallBack();
        //传入zk和配置conf
        watchCallBack.setZk(zk);
        MyConf myConf = new MyConf();
        watchCallBack.setConf(myConf);
        //节点不存在和节点存在, 都尝试去取数据, 取到了才往下走
        watchCallBack.aWait();

        while(true) {
            if (myConf.getConf().equals("")) {
                System.out.println("conf diu le ......");
                watchCallBack.aWait();
            } else {
                System.out.println(myConf.getConf());
            }
            try {
                Thread.sleep(200);
            } catch (InterruptedException e) {
                e.printStackTrace();
            }
        }
    }
}
```

## 2.zk实现负载均衡

### (1)负载均衡算法

常用的负载均衡算法有：轮询法、随机法、原地址哈希法、加权轮询法、加权随机法、最小连接数法。

#### 一.轮询法

轮询法是最为简单的负载均衡算法。当接收到客户端请求后，负载均衡服务器会按顺序逐个分配给后端服务。比如集群中有3台服务器，分别是server1、server2、server3，轮询法会按照sever1、server2、server3顺序依次分发请求给每个服务器。当第一次轮询结束后，会重新开始下一轮的循环。

#### 二.随机法

随机法是指负载均衡服务器在接收到来自客户端请求后，根据随机算法选中后台集群中的一台服务器来处理这次请求。由于当集群中的机器变得越来越多时，每台机器被抽中的概率基本相等，因此随机法的实际效果越来越趋近轮询法。

#### 三.原地址哈希法

原地址哈希法是根据客户端的IP地址进行哈希计算，对计算结果进行取模，然后根据最终结果选择服务器地址列表中的一台机器来处理请求。这种算法每次都会分配同一台服务器来处理同一IP的客户端请求。

#### 四.加权轮询法

由于一个分布式系统中的机器可能部署在不同的网络环境中，每台机器的配置性能各不相同，因此其处理和响应请求的能力也各不相同。

如果采用上面几种负载均衡算法，都不太合适。这会造成能力强的服务器在处理完业务后过早进入空闲状态，而性能差或网络环境不好的服务器一直忙于处理请求造成任务积压。

为了解决这个问题，可以采用加权轮询法。加权轮询法的方式与轮询法的方式很相似，唯一的不同在于选择机器时，不只是单纯按照顺序的方式选择，还根据机器的配置和性能高低有所侧重，让配置性能好的机器优先分配。

#### 五.加权随机法

加权随机法和上面提到的随机法一样，在采用随机法选举服务器时，会考虑系统性能作为权值条件。

#### 六.最小连接数法

最小连接数法是指：根据后台处理客户端的请求数，计算应该把新请求分配给哪一台服务器。一般认为请求数最少的机器，会作为最优先分配的对象。

### (2)使用zk来实现负载均衡

实现负载均衡服务器的关键是：探测和发现业务服务器的运行状态 \+ 分配请求给最合适的业务服务器。

#### 一.状态收集之实现zk的业务服务器列表

首先利用zk的临时子节点来标记业务服务器的状态。在业务服务器上线时：通过向zk服务器创建临时子节点来实现服务注册，表示业务服务器已上线。在业务服务器下线时：通过删除临时节点或者与zk服务器断开连接来进行服务剔除。最后通过统计临时节点的数量，来了解业务服务器的运行情况。

在代码层面的实现中，首先定义一个BlanceSever接口类。该类用于业务服务器启动或关闭后：第一.向zk服务器地址列表注册或注销服务，第二.根据接收到的请求动态更新负载均衡情况。

```cs
public class BlanceSever {
    //向zk服务器地址列表进行注册服务
    public void register()
    //向zk服务器地址列表进行注销服务
    public void unregister()
    //根据接收到的请求动态更新负载均衡情况
    public void addBlanceCount()
    public void takeBlanceCount()
}
```

之后创建BlanceSever接口的实现类BlanceSeverImpl，在BlanceSeverImpl类中首先定义：业务服务器运行的Session超时时间、会话连接超时时间、zk客户端地址、服务器地址列表节点SERVER_PATH等基本参数。并通过构造函数，在类被引用时进行初始化zk客户端对象实例。

```java
public class BlanceSeverImpl implements BlanceSever {
    private static final Integer SESSION_TIME_OUT;
    private static final Integer CONNECTION_TIME_OUT;
    private final ZkClient zkclient;
    private static final SERVER_PATH = "/Severs";

    public BlanceSeverImpl() {
        init...
    }
}
```

接下来定义，业务服务器启动时，向zk注册服务的register方法。

在如下代码中，会通过在SERVER_PATH路径下创建临时子节点的方式来注册服务。首先获取业务服务器的IP地址，然后利用IP地址作为临时节点的path来创建临时节点。

```java
public register() throws Exception {
    //首先获取业务服务器的IP地址
    InetAddress address = InetAddress.getLocalHost();
    String serverIp = address.getHostAddress();
    //然后利用IP地址作为临时节点的path来创建临时节点
    zkclient.createEphemeral(SERVER_PATH + serverIp);
}
```

接下来定义，业务服务器关机或不对外提供服务时的unregister()方法。通过调用unregister()方法，注销该台业务服务器在zk服务器列表中的信息。注销后的机器不会被负载均衡服务器分发处理会话。在如下代码中，会通过删除SERVER_PATH路径下临时节点的方式来注销业务服务器。

```cs
public unregister() throws Exception {
    zkclient.delete(SERVER_PATH + serverIp);
}
```

#### 二.请求分配之如何选择业务服务器

以最小连接数法为例，来确定如何均衡地分配请求给业务服务器，整个实现步骤如下：

步骤一：首先负载均衡服务器在接收到客户端的请求后，通过getData()方法获取已成功注册的业务服务器列表，也就是"/Servers"节点下的各个临时节点，这些临时节点都存储了当前服务器的连接数。

步骤二：然后选取连接数最少的业务服务器作为处理当前请求的业务服务器，并通过setData()方法将该业务服务器对应的节点值(连接数)加1。

步骤三：当该业务服务器处理完请求后，调用setData()方法将该节点值(连接数)减1。

下面定义，当业务服务器接收到请求后，增加连接数的addBlance()方法。在如下代码中，首先通过readData()方法获取服务器最新的连接数，然后将该连接数加1。接着通过writeData()方法将最新的连接数写入到该业务服务器对应的临时节点。

```java
public void addBlance() throws Exception {
    InetAddress address = InetAddress.getLocalHost();
    String serverIp = address.getHostAddress();
    Integer con_count = zkClient.readData(SERVER_PATH + serverIp);
    ++con_count;
    zkClient.writeData(SERVER_PATH + serverIp, con_count);
}
```

## 3.zk实现分布式命名服务

命名服务是分布式系统最基本的公共服务之一。在分布式系统中，被命名的实体可以是集群中的机器、提供的服务地址等。Java中的JNDI便是一种典型的命名服务。

### (1)ID编码的特性

分布式ID生成器就是通过分布式的方式，自动生成ID编码的程序或服务。生成的ID编码一般具有唯一性、递增性、安全性、扩展性这几个特性。

### (2)通过UUID方式生成分布式ID

UUID能非常简便地保证分布式环境中ID的唯一性。它由32位字符和4个短线字符组成，比如e70f1357-f260-46ff-a32d-53a086c57ade。

由于UUID在本地应用中生成，所以生成速度比较快，不依赖其他服务和网络。但缺点是：长度过长、含义不明、不满足递增性。

### (3)通过TDDL生成分布式ID

MySQL的自增主键是一种有序的ID生成方式，还有一种性能更好的数据库序列生成方式：TDDL中的ID生成方式。TDDL是Taobao Distributed Data Layer的缩写，是一种数据库中间件，主要应用于数据库分库分表的应用场景中。

TDDL生成ID编码的大致过程如下：首先数据库中有一张Sequence序列化表，记录当前已被占用的ID最大值。然后每个需要ID编码的客户端在请求TDDL的ID编码生成器后，TDDL都会返回给该客户端一段ID编码，并更新Sequence表中的信息。

客户端接收到一段ID编码后，会将该段编码存储在内存中。在本机需要使用ID编码时，会首先使用内存中的ID编码。如果内存中的ID编码已经完全被占用，则再重新向编码服务器获取。

TDDL通过分批获取ID编码的方式，减少了客户端访问服务器的频率，避免了网络波动所造成的影响，并减轻了服务器的内存压力。不过TDDL高度依赖数据库，不能作为独立的分布式ID生成器对外提供服务。

### (4)通过zk生成分布式ID

每个需要ID编码的业务服务器可以看作是zk的客户端，ID编码生成器可以看作是zk的服务端，可以利用zk数据模型中的顺序节点作为ID编码。

客户端通过create()方法来创建一个顺序子节点。服务端成功创建节点后会响应客户端请求，把创建好的节点发送给客户端。客户端以顺序节点名称为基础进行ID编码，生成ID后就可以进行业务操作。

### (5)SnowFlake算法

SnowFlake算法是Twitter开源的一种用来生成分布式ID的算法，通过SnowFlake算法生成的编码会是一个64位的二进制数。

第一个bit不用，接下来的41个bit用来存储毫秒时间戳，再接下来的10个bit用来存储机器ID，剩余的12个bit用来存储流水号和0。

![图片](assets/4867d4599b9b.png)

SnowFlake算法主要的实现手段就是对二进制数位的操作，SnowFlake算法理论上每秒可以生成400多万个ID编码，SnowFlake是业界普遍采用的分布式ID生成算法。

## 4.zk实现分布式协调(Master-Worker协同)

### (1)Master-Worker架构

Master-Work是一个广泛使用的分布式架构，系统中有一个Master负责监控Worker的状态，并为Worker分配任务。

说明一：在任何时刻，系统中最多只能有一个Master。不可以出现两个Master，多个Master共存会导致脑裂。

说明二：系统中除了Active状态的Master还有一个Bakcup的Master。如果Active失败，Backup可以很快进入Active状态。

说明三：Master实时监控Worker的状态，能够及时收到Worker成员变化的通知。Master在收到Worker成员变化通知时，会重新进行任务分配。

![图片](assets/e20aeb574822.png)

### (2)Master-Worker架构示例—HBase

HBase采用的就是Master-Worker的架构。HMBase是系统中的Master，HRegionServer是系统中的Worker。HMBase会监控HBase Cluster中Worker的成员变化，HMBase会把region分配给各个HRegionServer。系统中有一个HMaster处于Active状态，其他HMaster处于备用状态。

![图片](assets/3cb70cf1aabf.png)

### (3)Master-Worker架构示例—Kafka

一个Kafka集群由多个Broker组成，这些Borker是系统中的Worker，Kafka会从这些Worker选举出一个Controller。这个Controlle是系统中的Master，负责把Topic Partition分配给各个Broker。

![图片](assets/f2ad754bb938.png)

### (4)Master-Worker架构示例—HDFS

HDFS采用的也是一个Master-Worker的架构。NameNode是系统中的Master，DataNode是系统中的Worker。NameNode用来保存整个分布式文件系统的MetaData，并把数据块分配给Cluster中的DataNode进行保存。

![图片](assets/821f7bd80a7a.png)

### (5)如何使用zk实现Master-Worker

步骤1：使用一个临时节点"/master"表示Master。Master在行使Master的职能之前，首先要创建这个znode。如果创建成功，进入Active状态，开始行使Master职能。如果创建失败，则进入Backup状态，并使用Watcher机制监听"/master"。假设系统中有一个Active Master和一个Backup Master。如果Active Master故障了，那么它创建的"/master"就会被zk自动删除。这时Backup Master会收到通知，再次创建"/master"成为新Active Master。

步骤2：使用一个持久节点"/workers"下的临时子节点来表示Worker，Worker通过在"/workers"节点下创建临时节点来加入集群。

步骤3：处于Active状态的Master会通过Watcher机制，监控"/workers"下的子节点列表来实时获取Worker成员的变化。

## 5.zk实现分布式通信

在大部分的分布式系统中，机器间的通信有三种类型：心跳检测、工作进度汇报、系统调度。

### (1)心跳检测

机器间的心跳检测是指：在分布式环境中，不同机器间需要检测彼此是否还在正常运行。其中，心跳检测有如下三种方法。

方法一：通常会通过机器间是否可以相互PING通来判断对方是否正常运行。

方法二：在机器间建立长连接，通过TCP连接固有的心跳检测机制来实现上层机器的心跳检测。

方法三：基于zk的临时子节点来实现心跳检测，让不同的机器都在zk的一个指定节点下创建临时子节点，不同机器间可以根据这个临时子节点来判断对应的客户端是否存活。基于zk的临时节点来实现的心跳检测，可以大大减少系统的耦合。因为检测系统和被检测系统之间不需要直接关联，只需要通过zk临时节点间接关联。

### (2)工作进度汇报

在一个任务分发系统中，任务被分发到不同的机器上执行后，需要实时地将自己的任务执行进度汇报给分发系统。

通过zk的临时子节点来实现工作进度汇报：可以在zk上选择一个节点，每个任务机器都在该节点下创建临时子节点。然后通过判断临时子节点是否存在来确定任务机器是否存活，各个任务机器会实时地将自己的任务执行进度写到其对应的临时节点上，以便中心系统能够实时获取到任务的执行进度。

### (3)系统调度

一个分布式系统由控制台和一些客户端系统组成，控制台的职责是将一些指令信息发送给所有客户端。

使用zk实现系统调度时：先让控制台的一些操作指令对应到zk的某些节点数据，然后让客户端系统注册对这些节点数据的监听。当控制台进行一些操作时，便会触发修改这些节点的数据，而zk会将这些节点数据的变更以事件通知的形式发送给监听的客户端。

这样就能省去大量底层网络通信和协议设计上的重复工作了，也大大降低了系统间的耦合，方便实现异构系统的灵活通信。

## 6.zk实现Master选举

Master选举的需求是：在集群的所有机器中选举出一台机器作为Master。

### (1)通过创建临时节点实现

集群的所有机器都往zk上创建一个临时节点如"/master"。在这个过程中只会有一个机器能成功创建该节点，则该机器便成为Master。同时其他没有成功创建节点的机器会在"/master"节点上注册Watcher监听，一旦当前Master机器挂了，那么其他机器就会重新往zk上创建临时节点。

### (2)通过临时顺序子节点来实现

使用临时顺序子节点来表示集群中的机器发起的选举请求，然后让创建最小后缀数字节点的机器成为Master。

## 7.zk实现分布式锁

可以利用zk的临时节点来解决死锁问题，可以利用zk的Watcher监听机制实现锁释放后重新竞争锁，可以利用zk数据节点的版本来实现乐观锁。

### (1)死锁的解决方案

在单机环境下，多线程之间会产生死锁问题。同样，在分布式系统环境下，也会产生分布式死锁的问题。常用的解决死锁问题的方法有超时方法和死锁检测。

#### 一.超时方法

在解决死锁问题时，超时方法可能是最简单的处理方式了。超时方式是在创建分布式线程时，对每个线程都设置一个超时时间。当该线程的超时时间到期后，无论该线程是否执行完毕，都要关闭该线程并释放该线程所占用的系统资源，之后其他线程就可以访问该线程释放的资源，这样就不会造成死锁问题。

但这种设置超时时间的方法最大的缺点是很难设置一个合适的超时时间。如果时间设置过短，可能造成线程未执行完相关的处理逻辑，就因为超时时间到期就被迫关闭，最终导致程序执行出错。

#### 二.死锁检测

死锁检测是处理死锁问题的另一种方法，它解决了超时方法的缺陷。死锁检测方法会主动检测发现线程死锁，在控制死锁问题上更加灵活准确。

可以把死锁检测理解为一个运行在各服务器系统上的线程或方法，该方法专门用来发现应用服务上的线程是否发生死锁。如果发生死锁，就会触发相应的预设处理方案。

### (2)zk如何实现排他锁

#### 一.获取锁

获取排他锁时，所有的客户端都会试图通过调用create()方法，在"/exclusive_lock"节点下创建临时子节点"/exclusive_lock/lock"。zk会保证所有的客户端中只有一个客户端能创建成功，从而获得锁。没有创建成功的客户端也就没能获得锁，需要到"/exclusive_lock"节点上，注册一个子节点变更的Watcher监听，以便可以实时监听lock节点的变更情况。

#### 二.释放锁

如果获取锁的客户端宕机，那么zk上的这个临时节点(lock节点)就会被移除。如果获取锁的客户端执行完，也会主动删除自己创建的临时节点(lock节点)。

### (3)zk如何实现共享锁(读写锁)

#### 一.获取锁

获取共享锁时，所有客户端会到"/shared_lock"下创建一个临时顺序节点。如果是读请求，那么就创建"/shared_lock/read001"的临时顺序节点。如果是写请求，那么就创建"/shared_lock/write002"的临时顺序节点。

#### 二.判断读写顺序

步骤一：客户端在创建完节点后，会获取"/shared_lock"节点下的所有子节点，并对"/shared_lock"节点注册子节点变更的Watcher监听。

步骤二：然后确定自己的节点序号在所有子节点中的顺序(包括读节点和写节点)。

步骤三：对于读请求：如果没有比自己序号小的写请求子节点，或所有比自己小的子节点都是读请求，那么表明可以成功获取共享锁。如果有比自己序号小的子节点是写请求，那么就需要进入等待。对于写请求：如果自己不是序号最小的子节点，那么就需要进入等待。

步骤四：如果客户端在等待过程中接收到Watcher通知，则重复步骤一。

#### 三.释放锁

如果获取锁的客户端宕机，那么zk上的对应的临时顺序节点就会被移除。如果获取锁的客户端执行完，也会主动删除自己创建的临时顺序节点。

### (4)羊群效应

#### 一.排他锁的羊群效应

如果有大量的客户端在等待锁的释放，那么就会出现大量的Watcher通知。然后这些客户端又会发起创建请求，但最后只有一个客户端能创建成功。这个Watcher事件通知其实对绝大部分客户端都不起作用，极端情况可能会出现zk短时间向其余客户端发送大量的事件通知，这就是羊群效应。出现羊群效应的根源在于：没有找准客户端真正的关注点。

#### 二.共享锁的羊群效应

如果有大量的客户端在等待锁的释放，那么不仅会出现大量的Watcher通知，还会出现大量的获取"/shared_lock"的子节点列表的请求，但最后大部分客户端都会判断出自己并非是序号最小的节点。所以客户端会接收过多和自己无关的通知和发起过多查询节点列表的请求，这就是羊群效应。出现羊群效应的根源在于：没有找准客户端真正的关注点。

### (5)改进后的排他锁

使用临时顺序节点来表示获取锁的请求，让创建出后缀数字最小的节点的客户端成功拿到锁。

步骤一：首先客户端调用create()方法在"/exclusive_lock"下创建一个临时顺序节点。

步骤二：然后客户端调用getChildren()方法返回"/exclusive_lock"下的所有子节点，接着对这些子节点进行排序。

步骤三：排序后，看看是否有后缀比自己小的节点。如果没有，则当前客户端便成功获取到排他锁。如果有，则调用exist()方法对排在自己前面的那个节点注册Watcher监听。

步骤四：当客户端收到Watcher通知前面的节点不存在，则重复步骤二。

### (6)改进后的共享锁

步骤一：客户端调用create()方法在"/shared_lock"节点下创建临时顺序节点。如果是读请求，那么就创建"/shared_lock/read001"的临时顺序节点。如果是写请求，那么就创建"/shared_lock/write002"的临时顺序节点。

步骤二：然后调用getChildren()方法返回"/shared_lock"下的所有子节点，接着对这些子节点进行排序。

步骤三：对于读请求：如果排序后发现有比自己序号小的写请求子节点，则需要等待，且需要向比自己序号小的最后一个写请求子节点注册Watcher监听。对于写请求：如果排序后发现自己不是序号最小的子节点，则需要等待，并且需要向比自己序号小的最后一个请求子节点注册Watcher监听。注意：这里注册Watcher监听也是调用exist()方法。此外，不满足上述条件则表示成功获取共享锁。

步骤四：如果客户端在等待过程中接收到Watcher通知，则重复步骤二。

### (7)zk原生实现分布式锁的示例

#### 一.分布式锁的实现步骤

步骤一：每个线程都通过"临时顺序节点 + zk.create()方法 \+ 添加回调"去创建节点。

步骤二：线程执行完创建临时顺序节点后，先通过CountDownLatch.await()方法进行阻塞。然后在创建成功的回调中，通过zk.getChildren()方法获取根目录并继续回调。

步骤三：某线程在获取根目录成功后的回调中，会对目录排序。排序后如果发现其创建的节点排第一，那么就执行countDown()方法不再阻塞，表示获取锁成功。排序后如果发现其创建的节点不是第一，则通过zk.exists()方法监听前一节点。

步骤四：获取到锁的线程会通过zk.delete()方法来删除其对应的节点实现释放锁。在等候获取锁的线程掉线时其对应的节点也会被删除。而一旦节点被删除，那些监听根目录的线程就会重新zk.getChildren()方法，获取成功后其回调又会进行排序以及通过zk.exists()方法监听前一节点。

#### 二.WatchCallBack对分布式锁的具体实现

```typescript
public class WatchCallBack implements Watcher, AsyncCallback.StringCallback, AsyncCallback.Children2Callback, AsyncCallback.StatCallback {
    ZooKeeper zk ;
    String threadName;
    CountDownLatch countDownLatch = new CountDownLatch(1);
    String pathName;

    public String getPathName() {
        return pathName;
    }

    public void setPathName(String pathName) {
        this.pathName = pathName;
    }

    public String getThreadName() {
        return threadName;
    }

    public void setThreadName(String threadName) {
        this.threadName = threadName;
    }

    public ZooKeeper getZk() {
        return zk;
    }

    public void setZk(ZooKeeper zk) {
        this.zk = zk;
    }

    public void tryLock() {
        try {
            System.out.println(threadName + " create....");
            //创建一个临时的有序的节点
            zk.create("/lock", threadName.getBytes(), ZooDefs.Ids.OPEN_ACL_UNSAFE, CreateMode.EPHEMERAL_SEQUENTIAL, this, "abc");
            countDownLatch.await();
        } catch (InterruptedException e) {
            e.printStackTrace();
        }
    }

    //当前线程释放锁, 删除节点
    public void unLock() {
        try {
            zk.delete(pathName, -1);
            System.out.println(threadName + " over work....");
        } catch (InterruptedException e) {
            e.printStackTrace();
        } catch (KeeperException e) {
            e.printStackTrace();
        }
    }

    //上面zk.create()方法的回调
    //创建临时顺序节点后的回调, 10个线程都能同时创建节点
    //创建完后获取根目录下的子节点, 也就是这10个线程创建的节点列表, 这个不用watch了, 但获取成功后要执行回调
    //这个回调就是每个线程用来执行节点排序, 看谁是第一就认为谁获得了锁
    @Override
    public void processResult(int rc, String path, Object ctx, String name) {
        if (name != null ) {
            System.out.println(threadName  + "  create node : " +  name );
            setPathName(name);
            //一定能看到自己前边的, 所以这里的watch要是false
            zk.getChildren("/", false, this ,"sdf");
        }
    }

    //核心方法: 各个线程获取根目录下的节点时, 上面zk.getChildren("/", false, this ,"sdf")的回调
    @Override
    public void processResult(int rc, String path, Object ctx, List<String> children, Stat stat) {
        //一定能看到自己前边的节点
        System.out.println(threadName + "look locks...");
        for (String child : children) {
            System.out.println(child);
        }
        //根目录下的节点排序
        Collections.sort(children);
        //获取当前线程创建的节点在根目录中排第几
        int i = children.indexOf(pathName.substring(1));
        //是不是第一个, 如果是则说明抢锁成功; 如果不是, 则watch当前线程创建节点的前一个节点是否被删除(删除);
        if (i == 0) {
            System.out.println(threadName + " i am first...");
            try {
                //这里的作用就是不让第一个线程获得锁释放锁跑得太快, 导致后面的线程还没建立完监听第一个节点就被删了
                zk.setData("/", threadName.getBytes(), -1);
                countDownLatch.countDown();
            } catch (KeeperException e) {
                e.printStackTrace();
            } catch (InterruptedException e) {
                e.printStackTrace();
            }
        } else {
            //9个没有获取到锁的线程都去调用zk.exists, 去监控各自自己前面的节点, 而没有去监听父节点
            //如果各自前面的节点发生删除事件的时候才回调自己, 并关注被删除的事件(所以会执行process回调)
            zk.exists("/" + children.get(i-1), this, this, "sdf");
        }
    }

    //上面zk.exists()的监听
    //监听的节点发生变化的Watcher事件监听
    @Override
    public void process(WatchedEvent event) {
        //如果第一个获得锁的线程释放锁了, 那么其实只有第二个线程会收到回调事件
        //如果不是第一个哥们某一个挂了, 也能造成他后边的收到这个通知, 从而让他后边那个去watch挂掉这个哥们前边的, 保持顺序
        switch (event.getType()) {
            case None:
                break;
            case NodeCreated:
                break;
            case NodeDeleted:
                zk.getChildren("/", false, this ,"sdf");
                break;
            case NodeDataChanged:
                break;
            case NodeChildrenChanged:
                break;
        }
    }

    @Override
    public void processResult(int rc, String path, Object ctx, Stat stat) {
        //TODO
    }
}
```

#### 三.分布式锁的测试类

```java
public class TestLock {
    ZooKeeper zk;

    @Before
    public void conn () {
        zk  = ZKUtils.getZK();
    }

    @After
    public void close () {
        try {
            zk.close();
        } catch (InterruptedException e) {
            e.printStackTrace();
        }
    }

    @Test
    public void lock() {
        //10个线程都去抢锁
        for (int i = 0; i < 10; i++) {
            new Thread() {
                @Override
                public void run() {
                    WatchCallBack watchCallBack = new WatchCallBack();
                    watchCallBack.setZk(zk);
                    String threadName = Thread.currentThread().getName();
                    watchCallBack.setThreadName(threadName);
                    //每一个线程去抢锁
                    watchCallBack.tryLock();
                    //抢到锁之后才能干活
                    System.out.println(threadName + " working...");
                    try {
                        Thread.sleep(1000);
                    } catch (InterruptedException e) {
                        e.printStackTrace();
                    }
                    //干完活释放锁
                    watchCallBack.unLock();
                }
            }.start();
        }
        while(true) {
        }
    }
}
```

## 8.zk实现分布式队列和分布式屏障

### (1)分布式队列的实现

步骤一：所有客户端都到"/queue"节点下创建一个临时顺序节点。

步骤二：通过调用getChildren()方法来获取"/queue"节点下的所有子节点。

步骤三：客户端确定自己的节点序号在所有子节点中的顺序。

步骤四：如果自己不是序号最小的子节点，那么就需要进入等待，同时调用exists()方法向比自己序号小的最后一个节点注册Watcher监听。

步骤五：如果客户端收到Watcher事件通知，重复步骤二。

### (2)分布式屏障的实现

"/barrier"节点是一个已存在的默认节点，"/barrier"节点的值是数字n表示Barrier值，比如10。

步骤一：首先，所有客户端都需要到"/barrier"节点下创建一个临时节点。

步骤二：然后，客户端通过getData()方法获取"/barrier"节点的数据内容，比如10。

步骤三：接着，客户端通过getChildren()方法获取"/barrier"节点下的所有子节点，同时注册对子节点列表变更的Watcher监听。

步骤四：如果客户端发现"/barrier"节点的子节点个数不足10个，那么就需要进入等待。

步骤五：如果客户端接收到了Watcher事件通知，那么就重复步骤三。

## 9.基于Curator进行基本的zk数据操作

Curator实现对znode进行增删改查的示例如下，其中CuratorFramework代表一个客户端实例。注意：可以通过creatingParentsIfNeeded()方法进行指定节点的级联创建。

```cs
public class CrudDemo {
    public static void main(String[] args) throws Exception {
        RetryPolicy retryPolicy = new ExponentialBackoffRetry(1000, 3);
        CuratorFramework client = CuratorFrameworkFactory.newClient("localhost:2181", 5000, 3000, retryPolicy);
        client.start();//启动客户端并建立连接

        System.out.println("已经启动Curator客户端");

        client.create()
            .creatingParentsIfNeeded()//进行级联创建
            .withMode(CreateMode.PERSISTENT)//指定节点类型
            .forPath("/my/path", "10".getBytes());//增

        byte[] dataBytes = client.getData().forPath("/my/path");//查
        System.out.println(new String(dataBytes));

        client.setData().forPath("/my/path", "11".getBytes());//改
        dataBytes = client.getData().forPath("/my/path");
        System.out.println(new String(dataBytes));

        List<String> children = client.getChildren().forPath("/my");//查
        System.out.println(children);

        client.delete().forPath("/my/path");//删
        Thread.sleep(Integer.MAX_VALUE);
    }
}
```

## 10.基于Curator实现Leader选举

### (1)Curator实现Leader选举的第一种方式之LeaderLatch

通过Curator的LeaderLatch来实现Leader选举：

```java
public class LeaderLatchDemo {
    public static void main(String[] args) throws Exception {
        RetryPolicy retryPolicy = new ExponentialBackoffRetry(1000, 3);
        CuratorFramework client = CuratorFrameworkFactory.newClient("localhost:2181", 5000, 3000, retryPolicy);
        client.start();

        //"/leader/latch"这其实是一个znode顺序节点
        LeaderLatch leaderLatch = new LeaderLatch(client, "/leader/latch");
        leaderLatch.start();
        leaderLatch.await();//直到等待他成为Leader再往后执行

        //类似于HDFS里，两台机器，其中一台成为了Leader就开始工作
        //另外一台机器可以通过await阻塞在这里，直到Leader挂了，自己就会成为Leader继续工作
        Boolean hasLeaderShip = leaderLatch.hasLeadership();//判断是否成为Leader
        System.out.println("是否成为leader：" + hasLeaderShip);
        Thread.sleep(Integer.MAX_VALUE);
    }
}
```

### (2)Curator实现Leader选举的第二种方式之LeaderSelector

通过Curator的LeaderSelector来实现Leader选举如下：其中，LeaderSelector有两个监听器，可以关注连接状态。

```java
public class LeaderSelectorDemo {
    public static void main(String[] args) throws Exception {
        RetryPolicy retryPolicy = new ExponentialBackoffRetry(1000, 3);
        CuratorFramework client = CuratorFrameworkFactory.newClient("localhost:2181", 5000, 3000, retryPolicy);
        client.start();

        LeaderSelector leaderSelector = new LeaderSelector(
            client,
            "/leader/election",
            new LeaderSelectorListener() {
                public void takeLeadership(CuratorFramework curatorFramework) throws Exception {
                    System.out.println("你已经成为了Leader......");
                    //在这里干Leader所有的事情，此时方法不能退出
                    Thread.sleep(Integer.MAX_VALUE);
                }

                public void stateChanged(CuratorFramework curatorFramework, ConnectionState connectionState) {
                    System.out.println("连接状态的变化，已经不是Leader......");
                    if (connectionState.equals(ConnectionState.LOST)) {
                        throw new CancelLeadershipException();
                    }
                }
            }
        );
        leaderSelector.start();//尝试和其他节点在节点"/leader/election"上进行竞争成为Leader
        Thread.sleep(Integer.MAX_VALUE);
    }
}
```

11.基于Curator实现的分布式Barrier

### (1)分布式Barrier

很多台机器都可以创建一个Barrier，此时它们都被阻塞了。除非满足一个条件(setBarrier()或removeBarrier())，才能不再阻塞它们。

```java
//DistributedBarrier
public class DistributedBarrierDemo {
    public static void main(String[] args) throws Exception {
        RetryPolicy retryPolicy = new ExponentialBackoffRetry(1000, 3);
        CuratorFramework client = CuratorFrameworkFactory.newClient("localhost:2181", 5000, 3000, retryPolicy);
        client.start();

        DistributedBarrier barrier = new DistributedBarrier(client, "/barrier");
        barrier.waitOnBarrier();
    }
}
```

### (2)分布式双重Barrier

```java
//DistributedDoubleBarrier
public class DistributedDoubleBarrierDemo {
    public static void main(String[] args) throws Exception {
        RetryPolicy retryPolicy = new ExponentialBackoffRetry(1000, 3);
        CuratorFramework client = CuratorFrameworkFactory.newClient("localhost:2181", 5000, 3000, retryPolicy);
        client.start();

        DistributedDoubleBarrier doubleBarrier = new DistributedDoubleBarrier(client, "/barrier/double", 10);
        doubleBarrier.enter();//每台机器都会阻塞在enter这里

        //直到10台机器都调用了enter，就会从enter这里往下执行
        //此时可以做一些计算任务
        doubleBarrier.leave();//每台机器都会阻塞在leave这里，直到10台机器都调用了leave
        //此时就可以继续往下执行
    }
}
```

## 12.基于Curator实现分布式计数器

如果真的要实现分布式计数器，最好用Redis来实现。因为Redis的并发量更高，性能更好，功能更加的强大，而且还可以使用lua脚本嵌入进去实现复杂的业务逻辑。但是Redis天生的异步同步机制，存在机器宕机导致的数据不同步风险。然而zk在ZAB协议下的数据同步机制，则不会出现宕机导致数据不同步的问题。

```java
//SharedCount：通过一个节点的值来实现
public class SharedCounterDemo {
    public static void main(String[] args) throws Exception {
        RetryPolicy retryPolicy = new ExponentialBackoffRetry(1000, 3);
        CuratorFramework client = CuratorFrameworkFactory.newClient("localhost:2181", 5000, 3000, retryPolicy);
        client.start();

        SharedCount sharedCount = new SharedCount(client, "/shared/count", 0);
        sharedCount.start();

        sharedCount.addListener(new SharedCountListener() {
            public void countHasChanged(SharedCountReader sharedCountReader, int i) throws Exception {
                System.out.println("分布式计数器变化了......");
            }
            public void stateChanged(CuratorFramework curatorFramework, ConnectionState connectionState) {
                System.out.println("连接状态变化了.....");
            }
        });

        Boolean result = sharedCount.trySetCount(1);
        System.out.println(sharedCount.getCount());
    }
}
```

## 13.基于Curator实现zk的节点和子节点监听机制

我们使用zk主要用于：

#### 一.对元数据进行增删改查、监听元数据的变化

#### 二.进行Leader选举

有三种类型的节点可以监听：

#### 一.子节点监听PathCache

#### 二.节点监听NodeCache

#### 三.整个节点以下的树监听TreeCache

### (1)基于Curator实现zk的子节点监听机制

下面是PathCache实现的子节点监听示例：

```java
public class PathCacheDemo {
    public static void main(String[] args) throws Exception {
        RetryPolicy retryPolicy = new ExponentialBackoffRetry(1000, 3);
        CuratorFramework client = CuratorFrameworkFactory.newClient("localhost:2181", 5000, 3000, retryPolicy);

        client.start();
        PathChildrenCache pathChildrenCache = new PathChildrenCache(client, "/cluster", true);

        //cache就是把zk里的数据缓存到客户端里来
        //可以针对这个缓存的数据加监听器，去观察zk里的数据的变化
        pathChildrenCache.getListenable().addListener(new PathChildrenCacheListener() {
            public void childEvent(CuratorFramework curatorFramework, PathChildrenCacheEvent pathChildrenCacheEvent) throws Exception {
            }
        });
        pathChildrenCache.start();
    }
}
```

### (2)基于Curator实现zk的节点数据监听机制

下面是NodeCache实现的节点监听示例：

```java
public class NodeCacheDemo {
    public static void main(String[] args) throws Exception {
        RetryPolicy retryPolicy = new ExponentialBackoffRetry(1000, 3);
        final CuratorFramework client = CuratorFrameworkFactory.newClient("localhost:2181", 5000, 3000, retryPolicy);
        client.start();

        final NodeCache nodeCache = new NodeCache(client, "/cluster");
        nodeCache.getListenable().addListener(new NodeCacheListener() {
            public void nodeChanged() throws Exception {
                Stat stat = client.checkExists().forPath("/cluster");
                if (stat == null) {

                } else {
                    nodeCache.getCurrentData();
                }
            }
        });
        nodeCache.start();
    }
}
```

## 14.基于Curator创建客户端实例的源码分析

### (1)创建CuratorFramework实例使用了构造器模式

CuratorFrameworkFactory.newClient()方法使用了构造器模式。首先通过builder()方法创建出Builder实例对象，然后把参数都设置成Builder实例对象的属性，最后通过build()方法把Builder实例对象传入目标类的构造方法中。

```java
public class Demo {
    public static void main(String[] args) throws Exception {
      RetryPolicy retryPolicy = new ExponentialBackoffRetry(1000, 3);
      CuratorFramework client = CuratorFrameworkFactory.newClient(
              "127.0.0.1:2181",//zk的地址
              5000,//客户端和zk的心跳超时时间，超过该时间没心跳，Session就会被断开
              3000,//连接zk时的超时时间
              retryPolicy
      );
      client.start();
      System.out.println("已经启动Curator客户端");
    }
}

public class CuratorFrameworkFactory {
    //创建CuratorFramework实例使用了构造器模式
    public static CuratorFramework newClient(String connectString, int sessionTimeoutMs, int connectionTimeoutMs, RetryPolicy retryPolicy) {
        return builder().
            connectString(connectString).
            sessionTimeoutMs(sessionTimeoutMs).
            connectionTimeoutMs(connectionTimeoutMs).
            retryPolicy(retryPolicy).
            build();
    }
    ...

    public static Builder builder() {
        return new Builder();
    }

    public static class Builder {
        ...
        private EnsembleProvider ensembleProvider;
        private int sessionTimeoutMs = DEFAULT_SESSION_TIMEOUT_MS;
        private int connectionTimeoutMs = DEFAULT_CONNECTION_TIMEOUT_MS;
        private RetryPolicy retryPolicy;
        ...
        public Builder connectString(String connectString) {
            ensembleProvider = new FixedEnsembleProvider(connectString);
            return this;
        }

        public Builder sessionTimeoutMs(int sessionTimeoutMs) {
            this.sessionTimeoutMs = sessionTimeoutMs;
            return this;
        }

        public Builder connectionTimeoutMs(int connectionTimeoutMs) {
            this.connectionTimeoutMs = connectionTimeoutMs;
            return this;
        }

        public Builder retryPolicy(RetryPolicy retryPolicy) {
            this.retryPolicy = retryPolicy;
            return this;
        }
        ...

        public CuratorFramework build() {
            return new CuratorFrameworkImpl(this);
        }
    }
    ...
}

public class CuratorFrameworkImpl implements CuratorFramework {
    ...
    public CuratorFrameworkImpl(CuratorFrameworkFactory.Builder builder) {
        ZookeeperFactory localZookeeperFactory = makeZookeeperFactory(builder.getZookeeperFactory());
        this.client = new CuratorZookeeperClient(
            localZookeeperFactory,
            builder.getEnsembleProvider(),
            builder.getSessionTimeoutMs(),
            builder.getConnectionTimeoutMs(),
            builder.getWaitForShutdownTimeoutMs(),
            new Watcher() {//这里注册了一个zk的watcher
                @Override
                public void process(WatchedEvent watchedEvent) {
                    CuratorEvent event = new CuratorEventImpl(CuratorFrameworkImpl.this, CuratorEventType.WATCHED, watchedEvent.getState().getIntValue(), unfixForNamespace(watchedEvent.getPath()), null, null, null, null, null, watchedEvent, null, null);
                    processEvent(event);
                }
            },
            builder.getRetryPolicy(),
            builder.canBeReadOnly(),
            builder.getConnectionHandlingPolicy()
        );
        ...
    }
    ...
}
```

(2)创建CuratorFramework实例会初始化CuratorZooKeeperClient实例

CuratorFramework实例代表了一个zk客户端，CuratorFramework初始化时会初始化一个CuratorZooKeeperClient实例。

CuratorZooKeeperClient是Curator封装ZooKeeper的客户端。

初始化CuratorZooKeeperClient时会传入一个Watcher监听器。

所以CuratorFrameworkFactory的newClient()方法的主要工作是：初始化CuratorFramework -> 初始化CuratorZooKeeperClient -> 初始化ZookeeperFactory + 注册一个Watcher。

客户端发起与zk的连接，以及注册Watcher监听器，则是由CuratorFramework的start()方法触发的。

15.Curator启动时是如何跟zk建立连接的

ConnectionStateManager的start()方法会启动一个线程处理eventQueue。eventQueue里存放了与zk的网络连接变化事件，eventQueue收到这种事件便会通知ConnectionStateListener。

CuratorZookeeperClient的start()方法会初始化好原生zk客户端，和zk服务器建立一个TCP长连接，而且还会注册一个ConnectionState类型的Watcher监听器，以便能收到zk服务端发送的通知事件。

```java
public class CuratorFrameworkImpl implements CuratorFramework {
    private final CuratorZookeeperClient client;
    private final ConnectionStateManager connectionStateManager;
    private volatile ExecutorService executorService;
    ...

    public CuratorFrameworkImpl(CuratorFrameworkFactory.Builder builder) {
        ...
        this.client = new CuratorZookeeperClient(...);
        connectionStateManager = new ConnectionStateManager(this, builder.getThreadFactory(),
            builder.getSessionTimeoutMs(),
            builder.getConnectionHandlingPolicy().getSimulatedSessionExpirationPercent(),
            builder.getConnectionStateListenerDecorator()
        );
        ...
    }
    ...

    @Override
    public void start() {
        log.info("Starting");
        if (!state.compareAndSet(CuratorFrameworkState.LATENT, CuratorFrameworkState.STARTED)) {
            throw new IllegalStateException("Cannot be started more than once");
        }
        ...

        //1.启动一个线程监听和zk网络连接的变化事件
        connectionStateManager.start();

        //2.添加一个监听器监听和zk网络连接的变化
        final ConnectionStateListener listener = new ConnectionStateListener() {
            @Override
            public void stateChanged(CuratorFramework client, ConnectionState newState) {
                if (ConnectionState.CONNECTED == newState || ConnectionState.RECONNECTED == newState) {
                    logAsErrorConnectionErrors.set(true);
                }
            }
            @Override
            public boolean doNotDecorate() {
                return true;
            }
        };
        this.getConnectionStateListenable().addListener(listener);

        //3.创建原生zk客户端
        client.start();

        //4.创建一个线程池，执行后台的操作
        executorService = Executors.newSingleThreadScheduledExecutor(threadFactory);
        executorService.submit(new Callable<Object>() {
            @Override
            public Object call() throws Exception {
                backgroundOperationsLoop();
                return null;
            }
        });

        if (ensembleTracker != null) {
            ensembleTracker.start();
        }
        log.info(schemaSet.toDocumentation());
    }
    ...
}

public class ConnectionStateManager implements Closeable {
    private final ExecutorService service;
    private final BlockingQueue<ConnectionState> eventQueue = new ArrayBlockingQueue<ConnectionState>(QUEUE_SIZE);
    ...

    public ConnectionStateManager(CuratorFramework client, ThreadFactory threadFactory, int sessionTimeoutMs, int sessionExpirationPercent, ConnectionStateListenerDecorator connectionStateListenerDecorator) {
        ...
        service = Executors.newSingleThreadExecutor(threadFactory);
        ...
    }
    ...

    public void start() {
        Preconditions.checkState(state.compareAndSet(State.LATENT, State.STARTED), "Cannot be started more than once");
        //启动一个线程
        service.submit(
            new Callable<Object>() {
                @Override
                public Object call() throws Exception {
                    processEvents();
                    return null;
                }
            }
        );
    }

    private void processEvents() {
        while (state.get() == State.STARTED) {
            int useSessionTimeoutMs = getUseSessionTimeoutMs();
            long elapsedMs = startOfSuspendedEpoch == 0 ? useSessionTimeoutMs / 2 : System.currentTimeMillis() - startOfSuspendedEpoch;
            long pollMaxMs = useSessionTimeoutMs - elapsedMs;
            final ConnectionState newState = eventQueue.poll(pollMaxMs, TimeUnit.MILLISECONDS);
            if (newState != null) {
                if (listeners.size() == 0) {
                    log.warn("There are no ConnectionStateListeners registered.");
                }
                listeners.forEach(listener -> listener.stateChanged(client, newState));
            } else if (sessionExpirationPercent > 0) {
                synchronized(this) {
                    checkSessionExpiration();
                }
            }
        }
    }
    ...
}

public class CuratorZookeeperClient implements Closeable {
    private final ConnectionState state;
    ...

    public CuratorZookeeperClient(ZookeeperFactory zookeeperFactory, EnsembleProvider ensembleProvider,
            int sessionTimeoutMs, int connectionTimeoutMs, int waitForShutdownTimeoutMs, Watcher watcher,
            RetryPolicy retryPolicy, boolean canBeReadOnly, ConnectionHandlingPolicy connectionHandlingPolicy) {
        ...
        state = new ConnectionState(zookeeperFactory, ensembleProvider, sessionTimeoutMs, connectionTimeoutMs, watcher, tracer, canBeReadOnly, connectionHandlingPolicy);
        ...
    }
    ...

    public void start() throws Exception {
        log.debug("Starting");
        if (!started.compareAndSet(false, true)) {
            throw new IllegalStateException("Already started");
        }
        state.start();
    }
    ...
}

class ConnectionState implements Watcher, Closeable {
    private final HandleHolder zooKeeper;

    ConnectionState(ZookeeperFactory zookeeperFactory, EnsembleProvider ensembleProvider,
            int sessionTimeoutMs, int connectionTimeoutMs, Watcher parentWatcher,
            AtomicReference<TracerDriver> tracer, boolean canBeReadOnly, ConnectionHandlingPolicy connectionHandlingPolicy) {
        this.ensembleProvider = ensembleProvider;
        this.sessionTimeoutMs = sessionTimeoutMs;
        this.connectionTimeoutMs = connectionTimeoutMs;
        this.tracer = tracer;
        this.connectionHandlingPolicy = connectionHandlingPolicy;
        if (parentWatcher != null) {
            parentWatchers.offer(parentWatcher);
        }
        //把自己作为Watcher注册给HandleHolder
        zooKeeper = new HandleHolder(zookeeperFactory, this, ensembleProvider, sessionTimeoutMs, canBeReadOnly);
    }
    ...

    void start() throws Exception {
        log.debug("Starting");
        ensembleProvider.start();
        reset();
    }

    synchronized void reset() throws Exception {
        log.debug("reset");
        instanceIndex.incrementAndGet();
        isConnected.set(false);
        connectionStartMs = System.currentTimeMillis();
        //创建客户端与zk的连接
        zooKeeper.closeAndReset();
        zooKeeper.getZooKeeper();//initiate connection
    }
    ...
}

class HandleHolder {
    private final ZookeeperFactory zookeeperFactory;
    private final Watcher watcher;
    private final EnsembleProvider ensembleProvider;
    private final int sessionTimeout;
    private final boolean canBeReadOnly;
    private volatile Helper helper;
    ...

    HandleHolder(ZookeeperFactory zookeeperFactory, Watcher watcher, EnsembleProvider ensembleProvider, int sessionTimeout, boolean canBeReadOnly) {
        this.zookeeperFactory = zookeeperFactory;
        this.watcher = watcher;
        this.ensembleProvider = ensembleProvider;
        this.sessionTimeout = sessionTimeout;
        this.canBeReadOnly = canBeReadOnly;
    }

    private interface Helper {
        ZooKeeper getZooKeeper() throws Exception;
        String getConnectionString();
        int getNegotiatedSessionTimeoutMs();
    }

    ZooKeeper getZooKeeper() throws Exception {
        return (helper != null) ? helper.getZooKeeper() : null;
    }

    void closeAndReset() throws Exception {
        internalClose(0);
        helper = new Helper() {
            private volatile ZooKeeper zooKeeperHandle = null;
            private volatile String connectionString = null;

            @Override
            public ZooKeeper getZooKeeper() throws Exception {
                synchronized(this) {
                    if (zooKeeperHandle == null) {
                        connectionString = ensembleProvider.getConnectionString();
                        //创建和zk的连接，初始化变量zooKeeperHandle
                        zooKeeperHandle = zookeeperFactory.newZooKeeper(connectionString, sessionTimeout, watcher, canBeReadOnly);
                    }
                    ...
                    return zooKeeperHandle;
                }
            }

            @Override
            public String getConnectionString() {
                return connectionString;
            }

            @Override
            public int getNegotiatedSessionTimeoutMs() {
                return (zooKeeperHandle != null) ? zooKeeperHandle.getSessionTimeout() : 0;
            }
        };
    }
    ...
}

//创建客户端与zk的连接
public class DefaultZookeeperFactory implements ZookeeperFactory {
    @Override
    public ZooKeeper newZooKeeper(String connectString, int sessionTimeout, Watcher watcher, boolean canBeReadOnly) throws Exception {
        return new ZooKeeper(connectString, sessionTimeout, watcher, canBeReadOnly);
    }
}
```

## 16.基于Curator进行增删改查节点的源码分析

Curator的CURD操作，底层都是通过调用zk原生的API来完成的。

### (1)基于Curator创建znode节点

创建节点也使用了构造器模式：首先通过CuratorFramework的create()方法创建一个CreateBuilder实例，然后通过CreateBuilder的withMode()等方法设置CreateBuilder的变量，最后通过CreateBuilder的forPath()方法 \+ 重试调用来创建znode节点。

创建节点时会调用CuratorFramework的getZooKeeper()方法获取zk客户端实例，之后就是通过原生zk客户端的API去创建节点了。

```java
public class Demo {
    public static void main(String[] args) throws Exception {
        RetryPolicy retryPolicy = new ExponentialBackoffRetry(1000, 3);
        CuratorFramework client = CuratorFrameworkFactory.newClient(
            "127.0.0.1:2181",//zk的地址
            5000,//客户端和zk的心跳超时时间，超过该时间没心跳，Session就会被断开
            3000,//连接zk时的超时时间
            retryPolicy
        );
        client.start();
        System.out.println("已经启动Curator客户端");
        //创建节点
        client.create().creatingParentsIfNeeded().withMode(CreateMode.PERSISTENT).forPath("/my/path", "100".getBytes());
    }
}

public class CuratorFrameworkImpl implements CuratorFramework {
    ...
    @Override
    public CreateBuilder create() {
        checkState();
        return new CreateBuilderImpl(this);
    }
    ...
}

public class CreateBuilderImpl implements CreateBuilder, CreateBuilder2, BackgroundOperation<PathAndBytes>, ErrorListenerPathAndBytesable<String> {
    private final CuratorFrameworkImpl client;
    private CreateMode createMode;
    private Backgrounding backgrounding;
    private boolean createParentsIfNeeded;
    ...

    CreateBuilderImpl(CuratorFrameworkImpl client) {
        this.client = client;
        createMode = CreateMode.PERSISTENT;
        backgrounding = new Backgrounding();
        acling = new ACLing(client.getAclProvider());
        createParentsIfNeeded = false;
        createParentsAsContainers = false;
        compress = false;
        setDataIfExists = false;
        storingStat = null;
        ttl = -1;
    }

    @Override
    public String forPath(final String givenPath, byte[] data) throws Exception {
        if (compress) {
            data = client.getCompressionProvider().compress(givenPath, data);
        }
        final String adjustedPath = adjustPath(client.fixForNamespace(givenPath, createMode.isSequential()));
        List<ACL> aclList = acling.getAclList(adjustedPath);
        client.getSchemaSet().getSchema(givenPath).validateCreate(createMode, givenPath, data, aclList);
        String returnPath = null;
        if (backgrounding.inBackground()) {
            pathInBackground(adjustedPath, data, givenPath);
        } else {
            //创建节点
            String path = protectedPathInForeground(adjustedPath, data, aclList);
            returnPath = client.unfixForNamespace(path);
        }
        return returnPath;
    }

    private String protectedPathInForeground(String adjustedPath, byte[] data, List<ACL> aclList) throws Exception {
        return pathInForeground(adjustedPath, data, aclList);
    }

    private String pathInForeground(final String path, final byte[] data, final List<ACL> aclList) throws Exception {
        OperationTrace trace = client.getZookeeperClient().startAdvancedTracer("CreateBuilderImpl-Foreground");
        final AtomicBoolean firstTime = new AtomicBoolean(true);
        //重试调用
        String returnPath = RetryLoop.callWithRetry(
            client.getZookeeperClient(),
            new Callable<String>() {
                @Override
                public String call() throws Exception {
                    boolean localFirstTime = firstTime.getAndSet(false) && !debugForceFindProtectedNode;
                    protectedMode.checkSetSessionId(client, createMode);
                    String createdPath = null;
                    if (!localFirstTime && protectedMode.doProtected()) {
                        debugForceFindProtectedNode = false;
                        createdPath = findProtectedNodeInForeground(path);
                    }
                    if (createdPath == null) {
                        //在创建znode节点的时候，首先会调用CuratorFramework.getZooKeeper()获取zk客户端实例
                        //之后就是通过原生zk客户端的API去创建节点了
                        try {
                            if (client.isZk34CompatibilityMode()) {
                                createdPath = client.getZooKeeper().create(path, data, aclList, createMode);
                            } else {
                                createdPath = client.getZooKeeper().create(path, data, aclList, createMode, storingStat, ttl);
                            }
                        } catch (KeeperException.NoNodeException e) {
                            if (createParentsIfNeeded) {
                                //这就是级联创建节点的实现
                                ZKPaths.mkdirs(client.getZooKeeper(), path, false, acling.getACLProviderForParents(), createParentsAsContainers);
                                if (client.isZk34CompatibilityMode()) {
                                    createdPath = client.getZooKeeper().create(path, data, acling.getAclList(path), createMode);
                                } else {
                                    createdPath = client.getZooKeeper().create(path, data, acling.getAclList(path), createMode, storingStat, ttl);
                                }
                            } else {
                                throw e;
                            }
                        } catch (KeeperException.NodeExistsException e) {
                            if (setDataIfExists) {
                                Stat setStat = client.getZooKeeper().setData(path, data, setDataIfExistsVersion);
                                if (storingStat != null) {
                                    DataTree.copyStat(setStat, storingStat);
                                }
                                createdPath = path;
                            } else {
                                throw e;
                            }
                        }
                    }
                    if (failNextCreateForTesting) {
                        failNextCreateForTesting = false;
                        throw new KeeperException.ConnectionLossException();
                    }
                    return createdPath;
                }
            }
        );
        trace.setRequestBytesLength(data).setPath(path).commit();
        return returnPath;
    }
    ...
}

public class CuratorFrameworkImpl implements CuratorFramework {
    private final CuratorZookeeperClient client;

    public CuratorFrameworkImpl(CuratorFrameworkFactory.Builder builder) {
        ZookeeperFactory localZookeeperFactory = makeZookeeperFactory(builder.getZookeeperFactory());
        this.client = new CuratorZookeeperClient(
            localZookeeperFactory,
            builder.getEnsembleProvider(),
            builder.getSessionTimeoutMs(),
            builder.getConnectionTimeoutMs(),
            builder.getWaitForShutdownTimeoutMs(),
            new Watcher() {
                ...
            },
            builder.getRetryPolicy(),
            builder.canBeReadOnly(),
            builder.getConnectionHandlingPolicy()
        );
        ...
    }
    ...

    ZooKeeper getZooKeeper() throws Exception {
        return client.getZooKeeper();
    }
    ...
}

public class CuratorZookeeperClient implements Closeable {
    private final ConnectionState state;
    ...

    public ZooKeeper getZooKeeper() throws Exception {
        Preconditions.checkState(started.get(), "Client is not started");
        return state.getZooKeeper();
    }
    ...
}

class ConnectionState implements Watcher, Closeable {
    private final HandleHolder zooKeeper;
    ...

    ZooKeeper getZooKeeper() throws Exception {
        if (SessionFailRetryLoop.sessionForThreadHasFailed()) {
            throw new SessionFailRetryLoop.SessionFailedException();
        }
        Exception exception = backgroundExceptions.poll();
        if (exception != null) {
            new EventTrace("background-exceptions", tracer.get()).commit();
            throw exception;
        }
        boolean localIsConnected = isConnected.get();
        if (!localIsConnected) {
            checkTimeouts();
        }
        //通过HandleHolder获取ZooKeeper实例
        return zooKeeper.getZooKeeper();
    }
    ...
}
```

### (2)基于Curator查询znode节点

查询节点也使用了构造器模式：首先通过CuratorFramework的getData()方法创建一个GetDataBuilder实例，然后通过GetDataBuilder的forPath()方法 \+ 重试调用来查询znode节点。

```java
public class Demo {
    public static void main(String[] args) throws Exception {
        RetryPolicy retryPolicy = new ExponentialBackoffRetry(1000, 3);
        CuratorFramework client = CuratorFrameworkFactory.newClient(
            "127.0.0.1:2181",//zk的地址
            5000,//客户端和zk的心跳超时时间，超过该时间没心跳，Session就会被断开
            3000,//连接zk时的超时时间
            retryPolicy
        );
        client.start();
        System.out.println("已经启动Curator客户端");
        //查询节点
        byte[] dataBytes = client.getData().forPath("/my/path");
        System.out.println(new String(dataBytes));
        //查询子节点
        List<String> children = client.getChildren().forPath("/my");
        System.out.println(children);
    }
}

public class CuratorFrameworkImpl implements CuratorFramework {
    ...
    @Override
    public GetDataBuilder getData() {
        checkState();
        return new GetDataBuilderImpl(this);
    }

    @Override
    public GetChildrenBuilder getChildren() {
        checkState();
        return new GetChildrenBuilderImpl(this);
    }
    ...
}

public class GetDataBuilderImpl implements GetDataBuilder, BackgroundOperation<String>, ErrorListenerPathable<byte[]> {
    private final CuratorFrameworkImpl  client;
    ...

    @Override
    public byte[] forPath(String path) throws Exception {
        client.getSchemaSet().getSchema(path).validateWatch(path, watching.isWatched() || watching.hasWatcher());
        path = client.fixForNamespace(path);
        byte[] responseData = null;
        if (backgrounding.inBackground()) {
            client.processBackgroundOperation(new OperationAndData<String>(this, path, backgrounding.getCallback(), null, backgrounding.getContext(), watching), null);
        } else {
            //查询节点
            responseData = pathInForeground(path);
        }
        return responseData;
    }

    private byte[] pathInForeground(final String path) throws Exception {
        OperationTrace trace = client.getZookeeperClient().startAdvancedTracer("GetDataBuilderImpl-Foreground");
        //重试调用
        byte[] responseData = RetryLoop.callWithRetry(
            client.getZookeeperClient(),
            new Callable<byte[]>() {
                @Override
                public byte[] call() throws Exception {
                    byte[] responseData;
                    //通过CuratorFramework获取原生zk客户端实例，然后调用其getData()获取节点
                    if (watching.isWatched()) {
                        responseData = client.getZooKeeper().getData(path, true, responseStat);
                    } else {
                        responseData = client.getZooKeeper().getData(path, watching.getWatcher(path), responseStat);
                        watching.commitWatcher(KeeperException.NoNodeException.Code.OK.intValue(), false);
                    }
                    return responseData;
                }
            }
        );
        trace.setResponseBytesLength(responseData).setPath(path).setWithWatcher(watching.hasWatcher()).setStat(responseStat).commit();
        return decompress ? client.getCompressionProvider().decompress(path, responseData) : responseData;
    }
    ...
}
```

### (3)基于Curator修改znode节点

修改节点也使用了构造器模式：首先通过CuratorFramework的setData()方法创建一个SetDataBuilder实例，然后通过SetDataBuilder的forPath()方法 \+ 重试调用来修改znode节点。

```java
public class Demo {
    public static void main(String[] args) throws Exception {
        RetryPolicy retryPolicy = new ExponentialBackoffRetry(1000, 3);
        CuratorFramework client = CuratorFrameworkFactory.newClient(
            "127.0.0.1:2181",//zk的地址
            5000,//客户端和zk的心跳超时时间，超过该时间没心跳，Session就会被断开
            3000,//连接zk时的超时时间
            retryPolicy
        );
        client.start();
        System.out.println("已经启动Curator客户端");
        //修改节点
        client.setData().forPath("/my/path", "110".getBytes());
        byte[] dataBytes = client.getData().forPath("/my/path");
        System.out.println(new String(dataBytes));
    }
}

public class CuratorFrameworkImpl implements CuratorFramework {
    ...
    @Override
    public SetDataBuilder setData() {
        checkState();
        return new SetDataBuilderImpl(this);
    }
    ...
}

public class SetDataBuilderImpl implements SetDataBuilder, BackgroundOperation<PathAndBytes>, ErrorListenerPathAndBytesable<Stat> {
    private final CuratorFrameworkImpl client;
    ...

    @Override
    public Stat forPath(String path, byte[] data) throws Exception {
        client.getSchemaSet().getSchema(path).validateGeneral(path, data, null);
        if (compress) {
            data = client.getCompressionProvider().compress(path, data);
        }
        path = client.fixForNamespace(path);
        Stat resultStat = null;
        if (backgrounding.inBackground()) {
            client.processBackgroundOperation(new OperationAndData<>(this, new PathAndBytes(path, data), backgrounding.getCallback(), null, backgrounding.getContext(), null), null);
        } else {
            //修改节点
            resultStat = pathInForeground(path, data);
        }
        return resultStat;
    }

    private Stat pathInForeground(final String path, final byte[] data) throws Exception {
        OperationTrace trace = client.getZookeeperClient().startAdvancedTracer("SetDataBuilderImpl-Foreground");
        //重试调用
        Stat resultStat = RetryLoop.callWithRetry(
            client.getZookeeperClient(),
            new Callable<Stat>() {
                @Override
                public Stat call() throws Exception {
                    //通过CuratorFramework获取原生zk客户端实例，然后调用其setData()修改节点
                    return client.getZooKeeper().setData(path, data, version);
                }
            }
        );
        trace.setRequestBytesLength(data).setPath(path).setStat(resultStat).commit();
        return resultStat;
    }
    ...
}
```

### (4)基于Curator删除znode节点

删除节点也使用了构造器模式：首先通过CuratorFramework的delete()方法创建一个DeleteBuilder实例，然后通过DeleteBuilder的forPath()方法 \+ 重试调用来删除znode节点。

```java
public class Demo {
    public static void main(String[] args) throws Exception {
        RetryPolicy retryPolicy = new ExponentialBackoffRetry(1000, 3);
        CuratorFramework client = CuratorFrameworkFactory.newClient(
            "127.0.0.1:2181",//zk的地址
            5000,//客户端和zk的心跳超时时间，超过该时间没心跳，Session就会被断开
            3000,//连接zk时的超时时间
            retryPolicy
        );
        client.start();
        System.out.println("已经启动Curator客户端");
        //删除节点
        client.delete().forPath("/my/path");
    }
}

public class CuratorFrameworkImpl implements CuratorFramework {
    ...
    @Override
    public DeleteBuilder delete() {
        checkState();
        return new DeleteBuilderImpl(this);
    }
    ...
}

public class DeleteBuilderImpl implements DeleteBuilder, BackgroundOperation<String>, ErrorListenerPathable<Void> {
    private final CuratorFrameworkImpl client;
    ...

    @Override
    public Void forPath(String path) throws Exception {
        client.getSchemaSet().getSchema(path).validateDelete(path);
        final String unfixedPath = path;
        path = client.fixForNamespace(path);
        if (backgrounding.inBackground()) {
            OperationAndData.ErrorCallback<String> errorCallback = null;
            if (guaranteed) {
                errorCallback = new OperationAndData.ErrorCallback<String>() {
                    @Override
                    public void retriesExhausted(OperationAndData<String> operationAndData) {
                        client.getFailedDeleteManager().addFailedOperation(unfixedPath);
                    }
                };
            }
            client.processBackgroundOperation(new OperationAndData<String>(this, path, backgrounding.getCallback(), errorCallback, backgrounding.getContext(), null), null);
        } else {
            //删除节点
            pathInForeground(path, unfixedPath);
        }
        return null;
    }

    private void pathInForeground(final String path, String unfixedPath) throws Exception {
        OperationTrace trace = client.getZookeeperClient().startAdvancedTracer("DeleteBuilderImpl-Foreground");
        //重试调用
        RetryLoop.callWithRetry(
            client.getZookeeperClient(),
            new Callable<Void>() {
                @Override
                public Void call() throws Exception {
                    try {
                        //通过CuratorFramework获取原生zk客户端实例，然后调用其delete()删除节点
                        client.getZooKeeper().delete(path, version);
                    } catch (KeeperException.NoNodeException e) {
                        if (!quietly) {
                            throw e;
                        }
                    } catch (KeeperException.NotEmptyException e) {
                        if (deletingChildrenIfNeeded) {
                            ZKPaths.deleteChildren(client.getZooKeeper(), path, true);
                        } else {
                            throw e;
                        }
                    }
                    return null;
                }
            }
        );
        trace.setPath(path).commit();
    }
}
```

17.Curator节点监听回调机制的实现源码

### (1)PathCache子节点监听机制的实现源码

PathChildrenCache会调用原生zk客户端对象的getChildren()方法，并往该方法传入一个监听器childrenWatcher。当子节点发生事件，就会通知childrenWatcher这个原生的Watcher，然后该Watcher便会调用注册到PathChildrenCache的Listener。注意：在传入的监听器Watcher中会实现重复注册Watcher。

```java
public class Demo {
    public static void main(String[] args) throws Exception {
        RetryPolicy retryPolicy = new ExponentialBackoffRetry(1000, 3);
        CuratorFramework client = CuratorFrameworkFactory.newClient(
            "127.0.0.1:2181",//zk的地址
            5000,//客户端和zk的心跳超时时间，超过该时间没心跳，Session就会被断开
            3000,//连接zk时的超时时间
            retryPolicy
        );
        client.start();
        System.out.println("已经启动Curator客户端");
        //PathCache，监听/cluster下的子节点变化
        PathChildrenCache pathChildrenCache = new PathChildrenCache(client, "/cluster", true);
        pathChildrenCache.getListenable().addListener(new PathChildrenCacheListener() {
            public void childEvent(CuratorFramework curatorFramework, PathChildrenCacheEvent pathChildrenCacheEvent) throws Exception {
                ...
            }
        });
        pathChildrenCache.start();
    }
}

public class PathChildrenCache implements Closeable {
    private final WatcherRemoveCuratorFramework client;
    private final String path;
    private final boolean cacheData;
    private final boolean dataIsCompressed;
    private final CloseableExecutorService executorService;
    private final ListenerContainer<PathChildrenCacheListener> listeners = new ListenerContainer<PathChildrenCacheListener>();
    ...

    //初始化
    public PathChildrenCache(CuratorFramework client, String path, boolean cacheData, boolean dataIsCompressed, final CloseableExecutorService executorService) {
        this.client = client.newWatcherRemoveCuratorFramework();
        this.path = PathUtils.validatePath(path);
        this.cacheData = cacheData;
        this.dataIsCompressed = dataIsCompressed;
        this.executorService = executorService;
        ensureContainers = new EnsureContainers(client, path);
    }

    //获取用来存放Listener的容器listeners
    public ListenerContainer<PathChildrenCacheListener> getListenable() {
        return listeners;
    }

    //启动对子节点的监听
    public void start() throws Exception {
        start(StartMode.NORMAL);
    }

    private volatile ConnectionStateListener connectionStateListener = new ConnectionStateListener() {
        @Override
        public void stateChanged(CuratorFramework client, ConnectionState newState) {
            //处理连接状态的变化
            handleStateChange(newState);
        }
    };

    public void start(StartMode mode) throws Exception {
        ...
        //对建立的zk连接添加Listener
        client.getConnectionStateListenable().addListener(connectionStateListener);
        ...
        //把PathChildrenCache自己传入RefreshOperation中
        //下面的代码其实就是调用PathChildrenCache的refresh()方法
        offerOperation(new RefreshOperation(this, RefreshMode.STANDARD));
        ...
    }

    //提交一个任务到线程池进行处理
    void offerOperation(final Operation operation) {
        if (operationsQuantizer.add(operation)) {
            submitToExecutor(
                new Runnable() {
                    @Override
                    public void run() {
                        ...
                        operationsQuantizer.remove(operation);
                        //其实就是调用PathChildrenCache的refresh()方法
                        operation.invoke();
                        ...
                    }
                }
            );
        }
    }

    private synchronized void submitToExecutor(final Runnable command) {
        if (state.get() == State.STARTED) {
            //提交一个任务到线程池进行处理
            executorService.submit(command);
        }
    }
    ...
}

class RefreshOperation implements Operation {
    private final PathChildrenCache cache;
    private final PathChildrenCache.RefreshMode mode;

    RefreshOperation(PathChildrenCache cache, PathChildrenCache.RefreshMode mode) {
        this.cache = cache;
        this.mode = mode;
    }

    @Override
    public void invoke() throws Exception {
        //调用PathChildrenCache的refresh方法，也就是发起对子节点的监听
        cache.refresh(mode);
    }
    ...
}

public class PathChildrenCache implements Closeable {
    ...
    private volatile Watcher childrenWatcher = new Watcher() {
        //重复注册监听器
        //当子节点发生变化事件时，该方法就会被触发调用
        @Override
        public void process(WatchedEvent event) {
            //下面的代码其实依然是调用PathChildrenCache的refresh()方法
            offerOperation(new RefreshOperation(PathChildrenCache.this, RefreshMode.STANDARD));
        }
    };

    void refresh(final RefreshMode mode) throws Exception {
        ensurePath();
        //创建一个回调，在下面执行client.getChildren()成功时会触发执行该回调
        final BackgroundCallback callback = new BackgroundCallback() {
            @Override
            public void processResult(CuratorFramework client, CuratorEvent event) throws Exception {
                if (reRemoveWatchersOnBackgroundClosed()) {
                    return;
                }
                if (event.getResultCode() == KeeperException.Code.OK.intValue()) {
                    //处理子节点数据
                    processChildren(event.getChildren(), mode);
                } else if (event.getResultCode() == KeeperException.Code.NONODE.intValue()) {
                    if (mode == RefreshMode.NO_NODE_EXCEPTION) {
                        log.debug("KeeperException.NoNodeException received for getChildren() and refresh has failed. Resetting ensureContainers but not refreshing. Path: [{}]", path);
                        ensureContainers.reset();
                    } else {
                        log.debug("KeeperException.NoNodeException received for getChildren(). Resetting ensureContainers. Path: [{}]", path);
                        ensureContainers.reset();
                        offerOperation(new RefreshOperation(PathChildrenCache.this, RefreshMode.NO_NODE_EXCEPTION));
                    }
                }
            }
        };
        //下面的代码最后会调用到原生zk客户端的getChildren方法发起对子节点的监听
        //并且添加一个叫childrenWatcher的监听，一个叫callback的后台异步回调
        client.getChildren().usingWatcher(childrenWatcher).inBackground(callback).forPath(path);
    }
    ...
}

//子节点发生变化事件时，最后都会触发执行EventOperation的invoke()方法
class EventOperation implements Operation {
    private final PathChildrenCache cache;
    private final PathChildrenCacheEvent event;

    EventOperation(PathChildrenCache cache, PathChildrenCacheEvent event) {
        this.cache = cache;
        this.event = event;
    }

    @Override
    public void invoke() {
        //调用PathChildrenCache的Listener
        cache.callListeners(event);
    }
    ...
}
```

### (2)NodeCache节点监听机制的实现源码

NodeCache会调用原生zk客户端对象的exists()方法，并往该方法传入一个监听器watcher。当子节点发生事件，就会通知watcher这个原生的Watcher，然后该Watcher便会调用注册到NodeCache的Listener。注意：在传入的监听器Watcher中会实现重复注册Watcher。

```java
public class Demo {
    public static void main(String[] args) throws Exception {
        RetryPolicy retryPolicy = new ExponentialBackoffRetry(1000, 3);
        CuratorFramework client = CuratorFrameworkFactory.newClient(
            "127.0.0.1:2181",//zk的地址
            5000,//客户端和zk的心跳超时时间，超过该时间没心跳，Session就会被断开
            3000,//连接zk时的超时时间
            retryPolicy
        );
        client.start();
        System.out.println("已经启动Curator客户端");

        //NodeCache
        final NodeCache nodeCache = new NodeCache(client, "/cluster");
        nodeCache.getListenable().addListener(new NodeCacheListener() {
            public void nodeChanged() throws Exception {
                Stat stat = client.checkExists().forPath("/cluster");
                if (stat == null) {
                } else {
                    nodeCache.getCurrentData();
                }
            }
        });
        nodeCache.start();
    }
}

public class NodeCache implements Closeable {
    private final WatcherRemoveCuratorFramework client;
    private final String path;
    private final ListenerContainer<NodeCacheListener> listeners = new ListenerContainer<NodeCacheListener>();
    ...

    private ConnectionStateListener connectionStateListener = new ConnectionStateListener() {
        @Override
        public void stateChanged(CuratorFramework client, ConnectionState newState) {
            if ((newState == ConnectionState.CONNECTED) || (newState == ConnectionState.RECONNECTED)) {
                if (isConnected.compareAndSet(false, true)) {
                    reset();
                }
            } else {
                isConnected.set(false);
            }
        }
    };

    //初始化一个Watcher，作为监听器添加到下面reset()方法执行的client.checkExists()方法中
    private Watcher watcher = new Watcher() {
        //重复注册监听器
        @Override
        public void process(WatchedEvent event) {
            reset();
        }
    };

    //初始化一个回调，在下面reset()方法执行client.checkExists()成功时会触发执行该回调
    private final BackgroundCallback backgroundCallback = new BackgroundCallback() {
        @Override
        public void processResult(CuratorFramework client, CuratorEvent event) throws Exception {
            processBackgroundResult(event);
        }
    };

    //初始化NodeCache
    public NodeCache(CuratorFramework client, String path, boolean dataIsCompressed) {
        this.client = client.newWatcherRemoveCuratorFramework();
        this.path = PathUtils.validatePath(path);
        this.dataIsCompressed = dataIsCompressed;
    }

    //获取存放Listener的容器ListenerContainer
    public ListenerContainer<NodeCacheListener> getListenable() {
        Preconditions.checkState(state.get() != State.CLOSED, "Closed");
        return listeners;
    }

    //启动对节点的监听
    public void start() throws Exception {
        start(false);
    }

    public void start(boolean buildInitial) throws Exception {
        Preconditions.checkState(state.compareAndSet(State.LATENT, State.STARTED), "Cannot be started more than once");
        //对建立的zk连接添加Listener
        client.getConnectionStateListenable().addListener(connectionStateListener);
        if (buildInitial) {
            //调用原生的zk客户端的exists()方法，对节点进行监听
            client.checkExists().creatingParentContainersIfNeeded().forPath(path);
            internalRebuild();
        }
        reset();
    }

    private void reset() throws Exception {
        if ((state.get() == State.STARTED) && isConnected.get()) {
            //下面的代码最后会调用原生的zk客户端的exists()方法，对节点进行监听
            //并且添加一个叫watcher的监听，一个叫backgroundCallback的后台异步回调
            client.checkExists().creatingParentContainersIfNeeded().usingWatcher(watcher).inBackground(backgroundCallback).forPath(path);
        }
    }

    private void processBackgroundResult(CuratorEvent event) throws Exception {
        switch (event.getType()) {
            case GET_DATA: {
                if (event.getResultCode() == KeeperException.Code.OK.intValue()) {
                    ChildData childData = new ChildData(path, event.getStat(), event.getData());
                    setNewData(childData);
                }
                break;
            }
            case EXISTS: {
                if (event.getResultCode() == KeeperException.Code.NONODE.intValue()) {
                    setNewData(null);
                } else if (event.getResultCode() == KeeperException.Code.OK.intValue()) {
                    if (dataIsCompressed) {
                        client.getData().decompressed().usingWatcher(watcher).inBackground(backgroundCallback).forPath(path);
                    } else {
                        client.getData().usingWatcher(watcher).inBackground(backgroundCallback).forPath(path);
                    }
                }
                break;
            }
        }
    }
    ...
}
```

### (3)getChildren()方法对子节点注册监听器和后台异步回调说明

getChildren()方法注册的Watcher只有一次性，其注册的回调是一个异步回调。

```cs
public class Demo {
    public static void main(String[] args) throws Exception {
        RetryPolicy retryPolicy = new ExponentialBackoffRetry(1000, 3);
        CuratorFramework client = CuratorFrameworkFactory.newClient(
            "127.0.0.1:2181",//zk的地址
            5000,//客户端和zk的心跳超时时间，超过该时间没心跳，Session就会被断开
            3000,//连接zk时的超时时间
            retryPolicy
        );
        client.start();
        System.out.println("已经启动Curator客户端，完成zk的连接");

        client.create().creatingParentsIfNeeded().withMode(CreateMode.PERSISTENT).forPath("/test", "10".getBytes());
        System.out.println("创建节点'/test");

        client.getChildren().usingWatcher(new CuratorWatcher() {
            public void process(WatchedEvent event) throws Exception {
                //只要通知过一次zk节点的变化，这里就不会再被通知了
                //也就是第一次的通知才有效，这里被执行过一次后，就不会再被执行
                System.out.println("收到一个zk的通知: " + event);
            }
        }).inBackground(new BackgroundCallback() {
            //后台回调通知，表示会让zk.getChildren()在后台异步执行
            //后台异步执行client.getChildren()方法完毕，便会回调这个方法进行通知
            public void processResult(CuratorFramework client, CuratorEvent event) throws Exception {
                System.out.println("收到一个后台回调通知: " + event);
            }
        }).forPath("/test");
    }
}
```

### (4)PathCache实现自动重复注册监听器的效果

每当节点发生变化时，就会触发childEvent()方法的调用。

```java
public class Demo {
    public static void main(String[] args) throws Exception {
        RetryPolicy retryPolicy = new ExponentialBackoffRetry(1000, 3);
        final CuratorFramework client = CuratorFrameworkFactory.newClient(
            "127.0.0.1:2181",//zk的地址
            5000,//客户端和zk的心跳超时时间，超过该时间没心跳，Session就会被断开
            3000,//连接zk时的超时时间
            retryPolicy
        );

        client.start();
        System.out.println("已经启动Curator客户端，完成zk的连接");

        final PathChildrenCache pathChildrenCache = new PathChildrenCache(client, "/test", true);
        pathChildrenCache.getListenable().addListener(new PathChildrenCacheListener() {
            //只要子节点发生变化，无论变化多少次，每次变化都会触发这里childEvent的调用
            public void childEvent(CuratorFramework curatorFramework, PathChildrenCacheEvent pathChildrenCacheEvent) throws Exception {
                System.out.println("监听的子节点发生变化，收到了事件通知：" + pathChildrenCacheEvent);
            }
        });
        pathChildrenCache.start();
        System.out.println("完成子节点的监听和启动");
    }
}
```

### (5)NodeCache实现节点变化事件监听的效果

每当节点发生变化时，就会触发nodeChanged()方法的调用。

```java
public class Demo {
    public static void main(String[] args) throws Exception {
        RetryPolicy retryPolicy = new ExponentialBackoffRetry(1000, 3);
        final CuratorFramework client = CuratorFrameworkFactory.newClient(
            "127.0.0.1:2181",//zk的地址
            5000,//客户端和zk的心跳超时时间，超过该时间没心跳，Session就会被断开
            3000,//连接zk时的超时时间
            retryPolicy
        );

        client.start();
        System.out.println("已经启动Curator客户端，完成zk的连接");

        final NodeCache nodeCache = new NodeCache(client, "/test/child/id");
        nodeCache.getListenable().addListener(new NodeCacheListener() {
            //只要节点发生变化，无论变化多少次，每次变化都会触发这里nodeChanged的调用
            public void nodeChanged() throws Exception {
                Stat stat = client.checkExists().forPath("/test/child/id");
                if (stat != null) {
                    byte[] dataBytes = client.getData().forPath("/test/child/id");
                    System.out.println("节点数据发生了变化：" + new String(dataBytes));
                } else {
                    System.out.println("节点被删除");
                }
            }
        });
        nodeCache.start();
    }
}
```

## 18.基于Curator的Leader选举机制的实现源码

利用Curator的CRUD+ 监听回调机制，就能满足大部分系统使用zk的场景了。需要注意的是：如果使用原生的zk去注册监听器来监听节点或者子节点，当节点或子节点发生了对应的事件，会通知客户端一次，但是下一次再有对应的事件就不会通知了。使用zk原生的API时，客户端需要每次收到事件通知后，重新注册监听器。然而Curator的PathCache + NodeCache，会自动重新注册监听器。

### (1)第一种Leader选举机制LeaderLatch的源码

Curator客户端会通过创建临时顺序节点的方式来竞争成为Leader的，LeaderLatch这种Leader选举的实现方式与分布式锁的实现几乎一样。

每个Curator客户端创建完临时顺序节点后，就会对/leader/latch目录调用getChildren()方法来获取里面所有的子节点，调用getChildren()方法的结果会通过backgroundCallback回调进行通知，接着客户端便对获取到的子节点进行排序来判断自己是否是第一个子节点。

如果客户端发现自己是第一个子节点，那么就是Leader。如果客户端发现自己不是第一个子节点，就对上一个节点添加一个监听器。在添加监听器时，会使用getData()方法获取自己的上一个节点，getData()方法执行成功后会调用backgrondCallback回调。

当上一个节点对应的客户端释放了Leader角色，上一个节点就会消失，此时就会通知第二个节点对应的客户端，执行getData()方法添加的监听器。

所以如果getData()方法的监听器被触发了，即发现上一个节点不存在了，客户端会调用getChildren()方法重新获取子节点列表，判断是否是Leader。

注意：使用getData()代替exists()，可以避免不必要的Watcher造成的资源泄露。

```java
public class Demo {
    public static void main(String[] args) throws Exception {
        RetryPolicy retryPolicy = new ExponentialBackoffRetry(1000, 3);
        final CuratorFramework client = CuratorFrameworkFactory.newClient(
            "127.0.0.1:2181",//zk的地址
            5000,//客户端和zk的心跳超时时间，超过该时间没心跳，Session就会被断开
            3000,//连接zk时的超时时间
            retryPolicy
        );
        client.getConnectionStateListenable().addListener(new ConnectionStateListener() {
            public void stateChanged(CuratorFramework client, ConnectionState newState) {
                switch (newState) {
                    case LOST:
                        //当Leader与zk断开时，需要暂停当前Leader的工作
                }
            }
        });
        client.start();
        System.out.println("已经启动Curator客户端，完成zk的连接");

        LeaderLatch leaderLatch = new LeaderLatch(client, "/leader/latch");
        leaderLatch.start();
        leaderLatch.await();//阻塞等待直到当前客户端成为Leader
        Boolean hasLeaderShip = leaderLatch.hasLeadership();
        System.out.println("是否成为Leader: " + hasLeaderShip);
    }
}

public class LeaderLatch implements Closeable {
    private final WatcherRemoveCuratorFramework client;

    private final ConnectionStateListener listener = new ConnectionStateListener() {
        @Override
        public void stateChanged(CuratorFramework client, ConnectionState newState) {
            handleStateChange(newState);
        }
    };
    ...

    //Add this instance to the leadership election and attempt to acquire leadership.
    public void start() throws Exception {
        ...
        //对建立的zk连接添加Listener
        client.getConnectionStateListenable().addListener(listener);
        reset();
        ...
    }

    @VisibleForTesting
    void reset() throws Exception {
        setLeadership(false);
        setNode(null);
        //callback作为成功创建临时顺序节点后的回调
        BackgroundCallback callback = new BackgroundCallback() {
            @Override
            public void processResult(CuratorFramework client, CuratorEvent event) throws Exception {
                ...
                if (event.getResultCode() == KeeperException.Code.OK.intValue()) {
                    setNode(event.getName());
                    if (state.get() == State.CLOSED) {
                        setNode(null);
                    } else {
                        //成功创建临时顺序节点，需要通过getChildren()再去获取子节点列表
                        getChildren();
                    }
                } else {
                    log.error("getChildren() failed. rc = " + event.getResultCode());
                }
            }
        };
        //创建临时顺序节点
        client.create().creatingParentContainersIfNeeded().withProtection()
            .withMode(CreateMode.EPHEMERAL_SEQUENTIAL).inBackground(callback)
            .forPath(ZKPaths.makePath(latchPath, LOCK_NAME), LeaderSelector.getIdBytes(id));
    }

    //获取子节点列表
    private void getChildren() throws Exception {
        //callback作为成功获取子节点列表后的回调
        BackgroundCallback callback = new BackgroundCallback() {
            @Override
            public void processResult(CuratorFramework client, CuratorEvent event) throws Exception {
                if (event.getResultCode() == KeeperException.Code.OK.intValue()) {
                    checkLeadership(event.getChildren());
                }
            }
        };
        client.getChildren().inBackground(callback).forPath(ZKPaths.makePath(latchPath, null));
    }

    //检查自己是否是第一个节点
    private void checkLeadership(List<String> children) throws Exception {
        if (debugCheckLeaderShipLatch != null) {
            debugCheckLeaderShipLatch.await();
        }
        final String localOurPath = ourPath.get();
        //对获取到的节点进行排序
        List<String> sortedChildren = LockInternals.getSortedChildren(LOCK_NAME, sorter, children);
        int ourIndex = (localOurPath != null) ? sortedChildren.indexOf(ZKPaths.getNodeFromPath(localOurPath)) : -1;
        if (ourIndex < 0) {
            log.error("Can't find our node. Resetting. Index: " + ourIndex);
            reset();
        } else if (ourIndex == 0) {
            //如果自己是第一个节点，则标记自己为Leader
            setLeadership(true);
        } else {
            //如果自己不是第一个节点，则对前一个节点添加监听
            String watchPath = sortedChildren.get(ourIndex - 1);
            Watcher watcher = new Watcher() {
                @Override
                public void process(WatchedEvent event) {
                    if ((state.get() == State.STARTED) && (event.getType() == Event.EventType.NodeDeleted) && (localOurPath != null)) {
                        //重新获取子节点列表
                        getChildren();
                    }
                }
            };
            BackgroundCallback callback = new BackgroundCallback() {
                @Override
                public void processResult(CuratorFramework client, CuratorEvent event) throws Exception {
                    if (event.getResultCode() == KeeperException.Code.NONODE.intValue()) {
                        reset();
                    }
                }
            };
            //use getData() instead of exists() to avoid leaving unneeded watchers which is a type of resource leak
            //使用getData()代替exists()，可以避免不必要的Watcher造成的资源泄露
            client.getData().usingWatcher(watcher).inBackground(callback).forPath(ZKPaths.makePath(latchPath, watchPath));
        }
    }
    ...

    //阻塞等待直到成为Leader
    public void await() throws InterruptedException, EOFException {
        synchronized(this) {
            while ((state.get() == State.STARTED) && !hasLeadership.get()) {
                wait();//Objetc对象的wait()方法，阻塞等待
            }
        }
        if (state.get() != State.STARTED) {
            throw new EOFException();
        }
    }

    //设置当前客户端成为Leader，并进行notifyAll()通知之前阻塞的线程
    private synchronized void setLeadership(boolean newValue) {
        boolean oldValue = hasLeadership.getAndSet(newValue);
        if (oldValue && !newValue) { // Lost leadership, was true, now false
            listeners.forEach(new Function<LeaderLatchListener, Void>() {
                @Override
                public Void apply(LeaderLatchListener listener) {
                    listener.notLeader();
                    return null;
                }
            });
        } else if (!oldValue && newValue) { // Gained leadership, was false, now true
            listeners.forEach(new Function<LeaderLatchListener, Void>() {
                @Override
                public Void apply(LeaderLatchListener input) {
                    input.isLeader();
                    return null;
                }
            });
        }
        notifyAll();//唤醒之前执行了wait()方法的线程
    }
}
```

### (2)第二种Leader选举机制LeaderSelector的源码

通过判断是否成功获取到分布式锁，来判断是否竞争成为Leader。正因为是通过持有分布式锁来成为Leader，所以LeaderSelector.takeLeadership()方法不能退出，否则就会释放锁。而一旦释放了锁，其他客户端就会竞争锁成功而成为新的Leader。

```java
public class Demo {
    public static void main(String[] args) throws Exception {
        RetryPolicy retryPolicy = new ExponentialBackoffRetry(1000, 3);
        final CuratorFramework client = CuratorFrameworkFactory.newClient(
            "127.0.0.1:2181",//zk的地址
            5000,//客户端和zk的心跳超时时间，超过该时间没心跳，Session就会被断开
            3000,//连接zk时的超时时间
            retryPolicy
        );
        client.start();
        System.out.println("已经启动Curator客户端，完成zk的连接");

        LeaderSelector leaderSelector = new LeaderSelector(
            client,
            "/leader/election",
            new LeaderSelectorListener() {
                public void takeLeadership(CuratorFramework curatorFramework) throws Exception {
                    System.out.println("你已经成为了Leader......");
                    //在这里干Leader所有的事情，此时方法不能退出
                    Thread.sleep(Integer.MAX_VALUE);
                }
                public void stateChanged(CuratorFramework curatorFramework, ConnectionState connectionState) {
                    System.out.println("连接状态的变化，已经不是Leader......");
                    if (connectionState.equals(ConnectionState.LOST)) {
                        throw new CancelLeadershipException();
                    }
                }
            }
        );
        leaderSelector.start();//尝试和其他节点在节点"/leader/election"上进行竞争成为Leader
        Thread.sleep(Integer.MAX_VALUE);
    }
}

public class LeaderSelector implements Closeable {
    private final CuratorFramework client;
    private final LeaderSelectorListener listener;
    private final CloseableExecutorService executorService;
    private final InterProcessMutex mutex;
    ...

    public LeaderSelector(CuratorFramework client, String leaderPath, CloseableExecutorService executorService, LeaderSelectorListener listener) {
        Preconditions.checkNotNull(client, "client cannot be null");
        PathUtils.validatePath(leaderPath);
        Preconditions.checkNotNull(listener, "listener cannot be null");
        this.client = client;
        this.listener = new WrappedListener(this, listener);
        hasLeadership = false;
        this.executorService = executorService;
        //初始化一个分布式锁
        mutex = new InterProcessMutex(client, leaderPath) {
            @Override
            protected byte[] getLockNodeBytes() {
                return (id.length() > 0) ? getIdBytes(id) : null;
            }
        };
    }

    public void start() {
        Preconditions.checkState(state.compareAndSet(State.LATENT, State.STARTED), "Cannot be started more than once");
        Preconditions.checkState(!executorService.isShutdown(), "Already started");
        Preconditions.checkState(!hasLeadership, "Already has leadership");
        client.getConnectionStateListenable().addListener(listener);
        requeue();
    }

    public boolean requeue() {
        Preconditions.checkState(state.get() == State.STARTED, "close() has already been called");
        return internalRequeue();
    }

    private synchronized boolean internalRequeue() {
        if (!isQueued && (state.get() == State.STARTED)) {
            isQueued = true;
            //将选举的工作作为一个任务交给线程池执行
            Future<Void> task = executorService.submit(new Callable<Void>() {
                @Override
                public Void call() throws Exception {
                    ...
                    doWorkLoop();
                    ...
                    return null;
                }
            });
            ourTask.set(task);
            return true;
        }
        return false;
    }

    private void doWorkLoop() throws Exception {
        ...
        doWork();
        ...
    }

    @VisibleForTesting
    void doWork() throws Exception {
        hasLeadership = false;
        try {
            //尝试获取一把分布式锁，获取失败会进行阻塞
            mutex.acquire();
            //执行到这一行代码，说明获取分布式锁成功
            hasLeadership = true;
            try {
                if (debugLeadershipLatch != null) {
                    debugLeadershipLatch.countDown();
                }
                if (debugLeadershipWaitLatch != null) {
                    debugLeadershipWaitLatch.await();
                }
                //回调用户重写的takeLeadership()方法
                listener.takeLeadership(client);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                throw e;
            } catch (Throwable e) {
                ThreadUtils.checkInterrupted(e);
            } finally {
                clearIsQueued();
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw e;
        } finally {
            if (hasLeadership) {
                hasLeadership = false;
                boolean wasInterrupted = Thread.interrupted();  // clear any interrupted tatus so that mutex.release() works immediately
                try {
                    //释放锁
                    mutex.release();
                } catch (Exception e) {
                    if (failedMutexReleaseCount != null) {
                        failedMutexReleaseCount.incrementAndGet();
                    }
                    ThreadUtils.checkInterrupted(e);
                    log.error("The leader threw an exception", e);
                } finally {
                    if (wasInterrupted) {
                        Thread.currentThread().interrupt();
                    }
                }
            }
        }
    }
    ...
}
```
