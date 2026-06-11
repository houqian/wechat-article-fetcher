# Dubbo原理—1.URL配置总线+SPI

> **公众号**: 东阳马生架构  
> **发布时间**: 2025-07-17 09:00  

**大纲(23540字)**

- 1.Dubbo源码简介
- 2.Dubbo的配置总线(通过URL理解Dubbo)
- 3.Dubbo SPI精析(接口实现两极反转)
- 4.Java SPI详细说明


## 1.Dubbo源码简介

### (1)Dubbo核心架构图

### (2)Dubbo源码环境搭建

### (3)Dubbo源码核心模块

### (4)Dubbo源码中的Demo示例

### (5)关于Dubbo的几个入门问题

### (1)Dubbo核心架构图

Dubbo核心架构图如下：

![图片](assets/f601a2c13fdb.png)

#### 一.Registry：注册中心

负责服务地址的注册与查找，服务的Provider和Consumer只在启动时与注册中心交互。注册中心通过长连接感知Provider的存在，在Provider出现宕机时，注册中心会立即推送相关事件通知Consumer。

#### 二.Provider：服务提供者

在Provider启动时会向Registry进行注册操作：将自己服务的地址和相关配置信息封装成URL添加到ZK中。

#### 三.Consumer：服务消费者

在Consumer启动时会向Registry进行订阅操作：订阅操作会从ZK中获取Provider注册的URL，并在ZK中添加相应的监听器。获取到Provider URL之后，Consumer会根据负载均衡算法从多个Provider中选择一个Provider并与其建立连接。最后Consumer发起对Provider的RPC调用。

如果Provider URL发生变更：Consumer将会通过之前订阅过程中在注册中心添加的监听器，获取到最新的Provider URL信息，进行相应的调整。比如Consumer会断开与宕机Provider的连接，并与新的Provider建立连接。Consumer与Provider建立的是长连接，而且Consumer会缓存Provider信息。所以一旦连接建立，即使注册中心宕机，也不会影响已运行的Provider和Consumer。

#### 四.Monitor：监控中心

用于统计服务的调用次数和调用时间。Provider和Consumer在运行过程中，会在内存中统计调用次数和调用时间，定时每分钟发送一次统计数据到监控中心。监控中心在上面的架构图中并不是必要角色。监控中心宕机不会影响Provider、Consumer以及Registry的功能，只会丢失监控数据而已。

### (2)Dubbo源码环境搭建

当然，要搭建 Dubbo 源码环境，首先需要下载源码。可以直接从官方仓库"https://github.com/apache/dubbo"Fork到自己的仓库，直接执行下面的命令去下载代码：

```bash
git clone git@github.com:xxxxxxxx/dubbo.git
```

然后切换分支，如2.7.7：

```apache
git checkout -b dubbo-2.7.7 dubbo-2.7.7
```

接下来，执行 mvn 命令进行编译：

```nginx
mvn clean install -Dmaven.test.skip=true
```

最后，执行下面的命令转换成 IDEA 项目：

```javascript
mvn idea:idea //要是执行报错，就执行这个mvn idea:workspace
```

### (3)Dubbo源码核心模块

在IDEA成功导入Dubbo源码之后，项目结构如下图所示：

![图片](assets/1877cc264117.png)

下面简单介绍一下这些核心模块的功能：

#### 一.dubbo-common模块

这是Dubbo的一个公共模块，其中有很多工具类以及公共逻辑。例如Dubbo SPI实现、时间轮实现、动态编译器等。

![图片](assets/281abc8ce196.png)

#### 二.dubbo-remoting模块

这是Dubbo的远程通信模块，其中的子模块依赖各种开源组件实现远程通信。在dubbo-remoting-api子模块中定义该模块的抽象概念，在其他子模块中依赖其他开源组件进行实现。例如dubbo-remoting-netty4子模块依赖Netty 4实现远程通信，dubbo-remoting-zookeeper则通过Curator实现与ZK集群的交互。

![图片](assets/917df827c676.png)

#### 三.dubbo-rpc模块

这是Dubbo中对远程调用协议进行抽象的模块，其中抽象了各种协议，依赖于dubbo-remoting模块的远程调用功能。dubbo-rpc-api子模块是核心抽象，其他子模块是针对具体协议的实现。例如dubbo-rpc-dubbo子模块是对Dubbo协议的实现，依赖了dubbo-remoting-netty4等dubbo-remoting子模块。dubbo-rpc模块的实现中只包含一对一的调用，不关心集群的相关内容。

![图片](assets/bbbdee5e7d1c.png)

#### 四.dubbo-cluster模块

这是Dubbo中负责管理集群的模块，提供了负载均衡、容错、路由等一系列集群相关的功能。最终的目的是将多个Provider伪装为一个Provider，这样Consumer就可以像调用一个Provider那样调用Provider集群了。

#### 五.dubbo-registry模块

这是Dubbo中负责与多种开源注册中心进行交互的模块，提供注册中心的能力。其中dubbo-registry-api子模块是顶层抽象，其他子模块是针对具体开源注册中心组件的具体实现。例如dubbo-registry-zookeeper子模块是Dubbo接入ZK的具体实现。

![图片](assets/5c6491abe27f.png)

#### 六.dubbo-monitor模块

这是Dubbo的监控模块，主要用于统计服务调用次数、调用时间以及实现调用链跟踪的服务。

#### 七.dubbo-config模块

Dubbo对外暴露的配置都是由该模块进行解析的。例如dubbo-confifig-api子模块负责处理API方式使用时的相关配置，dubbo-confifig-spring子模块负责处理与Spring集成使用时的相关配置方式。有了dubbo-confifig模块，用户只需要了解Dubbo配置的规则即可，无须了解Dubbo内部的细节。

![图片](assets/30e611cbb1fb.png)

#### 八.dubbo-metadata模块

这是Dubbo的元数据模块。dubbo-metadata模块的实现套路也是有一个api子模块进行抽象，然后其他子模块进行具体实现。

![图片](assets/9813dceebb85.png)

#### 九.dubbo-confifigcenter模块

这是Dubbo的动态配置模块。主要负责外部化配置以及服务治理规则的存储与通知，提供了多个子模块用来接入多种开源的服务发现组件。

![图片](assets/c7d7ad3b2817.png)

### (4)Dubbo源码中的Demo示例

在Dubbo源码中我们可以看到一个dubbo-demo模块，共包括三个非常基础的Dubbo示例项目。分别是：使用XML配置的Demo示例、使用注解配置的Demo示例以及直接使用API的Demo示例。

下面从这三个示例的角度简单介绍Dubbo的基本使用。同时这三个项目也将作为后续Debug Dubbo源码的入口，我们会根据需要在其之上进行修改。不过在这之前，需要先启动ZooKeeper作为注册中心，然后编写一个业务接口作为Provider和Consumer的公约。

启动ZooKeeper：在前面Dubbo的架构图中，可以看到Provider的地址以及配置信息是通过注册中心传递给Consumer的。Dubbo支持的注册中心尽管有很多，但在生产环境中基本都是用ZooKeeper作为注册中心。因此在调试Dubbo源码时，自然需要在本地启动ZooKeeper。

```powershell
$ tar -zxf zookeeper-3.4.14.tar.gz
$ sudo ./bin/zkServer.sh start
# 下面为输出内容
ZooKeeper JMX enabled by default
Using config: /Users/xxx/zookeeper-3.4.14/bin/../conf/zoo.cfg # 配置文件
Starting zookeeper ... STARTED # 启动成功
```

业务接口：在使用Dubbo之前还需要一个业务接口。这个业务接口可以认为是Dubbo Provider和Dubbo Consumer的公约，反映出很多信息：

a.Provider，如何提供服务、提供的服务名称是什么、需要接收什么参数、需要返回什么响应。

b.Consumer，如何使用服务、使用的服务名称是什么、需要传入什么参数、会得到什么响应。

dubbo-demo-interface模块就是定义业务接口的地方，如下图示：

![图片](assets/33a9c5601933.png)

其中DemoService接口中定义了两个方法：

```typescript
public interface DemoService {
    String sayHello(String name);

    default CompletableFuture<String> sayHelloAsync(String name) {
        return CompletableFuture.completedFuture(sayHello(name));
    }
}
```

#### 一.Demo 1：基于XML配置

在dubbo-demo模块下的dubbo-demo-xml模块，提供了基于Spring XML的Provider和Consumer。

模块一：dubbo-demo-xml-provider模块

![图片](assets/39ebea2bfbdc.png)

在其pom.xml中除了一堆dubbo的依赖之外，还有依赖了DemoService这个公共接口。而DemoServiceImpl实现了DemoService接口：其sayHello()方法直接返回一个字符串，sayHelloAsync()方法返回一个CompletableFuture对象。

```xml
<dependency>
    <groupId>org.apache.dubbo</groupId>
    <artifactId>dubbo-demo-interface</artifactId>
    <version>${project.parent.version}</version>
</dependency>
```

在dubbo-provider.xml配置文件中：会将DemoServiceImpl配置成一个Spring Bean，并作为DemoService服务暴露出去。以及指定注册中心地址(即前面ZooKeeper的地址)，这样Dubbo才能把暴露的DemoService服务注册到ZooKeeper中。

```cs
<dubbo:registry address="zookeeper://127.0.0.1:2181"/>
<dubbo:service interface="org.apache.dubbo.demo.DemoService" ref="demoService"/>
```

最后，在Application中写个main()方法，指定Spring配置文件并启动ClassPathXmlApplicationContext即可。

```java
public class Application {
    public static void main(String[] args) throws Exception {
        ClassPathXmlApplicationContext context = new ClassPathXmlApplicationContext("spring/dubbo-provider.xml");
        context.start();
        System.in.read();
    }
}
```

模块二：dubbo-demo-xml-consumer模块

![图片](assets/b56af55dd92d.png)

在pom.xml中同样依赖了dubbo-demo-interface这个公共模块。

```xml
<dependency>
    <groupId>org.apache.dubbo</groupId>
    <artifactId>dubbo-demo-interface</artifactId>
    <version>${project.parent.version}</version>
</dependency>
```

在dubbo-consumer.xml配置文件中：会指定注册中心地址(就是前面ZooKeeper的地址)，这样Dubbo才能从ZooKeeper中拉取到Provider暴露的服务列表信息。以及使用dubbo:reference引入DemoService服务，后面可以作为Spring Bean使用了。

```xml
<dubbo:registry address="zookeeper://127.0.0.1:2181"/>
<dubbo:reference check="false" interface="org.apache.dubbo.demo.DemoService"/>
```

最后，在Application中写个main()方法，指定Spring配置文件并启动ClassPathXmlApplicationContext之后，就可以远程调用Provider端的DemoService的sayHello()方法了。

```java
public class Application {
    public static void main(String[] args) throws Exception {
        ClassPathXmlApplicationContext context = new ClassPathXmlApplicationContext("spring/dubbo-consumer.xml");
        context.start();
        DemoService demoService = context.getBean("demoService", DemoService.class);
        String hello = demoService.sayHello("world");
        System.out.println("result: " + hello);
    }
}
```

#### 二.Demo 2：基于注解配置

dubbo-demo-annotation模块是基于Spring注解配置的示例，无非就是将XML的那些配置信息转移到了注解上。

模块一：dubbo-demo-annotation-provider

```java
public class Application {
    public static void main(String[] args) throws Exception {
        AnnotationConfigApplicationContext context = new AnnotationConfigApplicationContext(ProviderConfiguration.class);
        context.start();
        System.in.read();
    }

    @Configuration
    @EnableDubbo(scanBasePackages = "org.apache.dubbo.demo.provider")
    @PropertySource("classpath:/spring/dubbo-provider.properties")
    static class ProviderConfiguration {
        @Bean
        public RegistryConfig registryConfig() {
            RegistryConfig registryConfig = new RegistryConfig();
            registryConfig.setAddress("zookeeper://127.0.0.1:2181");
            return registryConfig;
        }
    }
}
```

这里同样会有一个DemoServiceImpl实现了DemoService接口，并且在provider目录下，能被扫描到暴露成Dubbo服务。

模块二：dubbo-demo-annotation-consumer

其中Application中也是通过AnnotationConfifigApplicationContext初始化Spring容器，也会扫描指定目录下的Bean，会扫到DemoServiceComponent这个Bean，然后通过@Reference注解注入Dubbo服务相关的Bean：

```typescript
public class Application {
    public static void main(String[] args) {
        AnnotationConfigApplicationContext context = new AnnotationConfigApplicationContext(ConsumerConfiguration.class);
        context.start();
        DemoService service = context.getBean("demoServiceComponent", DemoServiceComponent.class);
        String hello = service.sayHello("world");
        System.out.println("result :" + hello);
    }

    @Configuration
    @EnableDubbo(scanBasePackages = "org.apache.dubbo.demo.consumer.comp")
    @PropertySource("classpath:/spring/dubbo-consumer.properties")
    @ComponentScan(value = {"org.apache.dubbo.demo.consumer.comp"})
    static class ConsumerConfiguration {
    }
}

@Component("demoServiceComponent")
public class DemoServiceComponent implements DemoService {
    @Reference
    private DemoService demoService;

    @Override
    public String sayHello(String name) {
        return demoService.sayHello(name);
    }

    @Override
    public CompletableFuture<String> sayHelloAsync(String name) {
        return null;
    }
}
```

#### 三.Demo 3：基于API配置

在有的场景中不能依赖于Spring框架，只能使用API来构建Dubbo Provider和Consumer，比较典型的一种场景就是在写SDK的时候。先来看dubbo-demo-api-provider模块，其中Application.main()方法是入口：

```cs
public class Application {
    public static void main(String[] args) throws Exception {
        ServiceConfig<DemoServiceImpl> service = new ServiceConfig<>();
        service.setInterface(DemoService.class);

        //指定业务接口的实现，由该对象来处理Consumer的请求
        service.setRef(new DemoServiceImpl());
        DubboBootstrap bootstrap = DubboBootstrap.getInstance();
        bootstrap.application(new ApplicationConfig("dubbo-demo-api-provider"))
            .registry(new RegistryConfig("zookeeper://127.0.0.1:2181"))
            .service(service)
            .start()
            .await();
    }
}
```

这里同样会有一个DemoServiceImpl实现了DemoService接口，并且在provider目录下，能被扫描到暴露成Dubbo服务。

再来看dubbo-demo-api-consumer模块，其中Application中包含一个普通的main()方法入口：

```java
public class Application {
    public static void main(String[] args) throws Exception {
        ReferenceConfig<DemoService> reference = new ReferenceConfig<>();
        reference.setInterface(DemoService.class);
        reference.setGeneric("false");

        //创建DubboBootstrap，指定ApplicationConfig以及RegistryConfig
        DubboBootstrap bootstrap = DubboBootstrap.getInstance();
        bootstrap.application(new ApplicationConfig("dubbo-demo-api-consumer"))
            .registry(new RegistryConfig("zookeeper://127.0.0.1:2181"))
            .reference(reference)
            .start();

        DemoService demoService = ReferenceConfigCache.getCache().get(reference);
        String message = demoService.sayHello("dubbo");
        System.out.println(message);
    }
}
```

### (5)关于Dubbo的几个基础问题

```
一.Dubbo是如何与ZooKeeper等注册中心进行交互的？
二.Provider与Consumer之间是如何交互的？
三.为什么我们在编写业务代码时，感受不到任何网络交互？
四.Dubbo Provider发布到注册中心的数据是什么？
五.Consumer为何能正确识别注册中心的数据？
六.Provider与Consumer两者的统一契约是什么？
七.这个契约是如何做到可扩展的？
八.这个契约还会用在Dubbo的哪些地方？
```

## 2.Dubbo的配置总线(通过URL理解Dubbo)

### (1)抓住URL就理解了半个Dubbo

### (2)Dubbo中的URL

### (3)契约的力量

### (4)Dubbo中的URL示例

### (5)总结

### (1)抓住URL就理解了半个Dubbo

在互联网领域，每个信息资源都有统一的且在网上唯一的地址。该地址就叫URL(Uniform Resource Locator，统一资源定位符)，它是互联网的统一资源定位标志，也就是指网络地址。URL本质上就是一个特殊格式的字符串，一个标准的 URL 格式可以包含如下的几个部分：

```bash
protocol://username:password@host:port/path?key1=value1&key2=value2
```

```bash
protocol：URL的协议，比如常见的HTTP协议和HTTPS协议、FTP协议、SMTP协议等；
username/password：用户名 / 密码；
host/port：主机 / 端口，在实践中一般会使用域名，而不是使用具体的host和port；
path：请求的路径；
parameters：参数键值对，一般在GET请求中会将参数放到URL中，POST请求会将参数放到请求体中；
```

URL是整个Dubbo中非常基础，也是非常核心的一个组件。源码中很多方法都是以URL作为参数，在方法内部解析传入的URL得到有用的参数。所以有人将URL称为Dubbo的配置总线：例如在Dubbo SPI核心实现中，URL参与了扩展实现的确定。在注册中心实现中，Provider会将自身的信息封装成URL注册到ZK中，从而暴露自己的服务， Consumer也是通过URL来确定自己订阅了哪些Provider的。由此可见，URL之于Dubbo是非常重要的，所以说"抓住URL，就理解了半个Dubbo"。

### (2)Dubbo中的URL

Dubbo中任意的一个实现都可以抽象为一个URL。Dubbo使用URL来统一描述了所有对象和配置信息，并贯穿在整个Dubbo框架之中。这里来看Dubbo中一个典型URL示例，如下是Demo Provider注册到ZK上的URL信息：

```apache
dubbo://172.17.32.91:20880/org.apache.dubbo.demo.DemoService?anyhost=true&application=dubbo-demo-api-provider&dubbo=2.0.2&interface=org.apache.dubbo.demo.DemoService&methods=sayHello,sayHelloAsync&pid=32508&release=&side=provider×=tamp=1593253404714
```

简单解析一下这个URL的各部分：

```bash
protocol：dubbo协议；
username/password：没有用户名和密码；
host/port：172.17.32.91:20880；
path：org.apache.dubbo.demo.DemoService；
parameters：参数键值对，这里是问号后面的参数；
```

在Dubbo中使用Url这个类来抽象所有的URL信息，下面是URL的构造方法，可以看到其核心字段与前文分析的URL基本一致：

```typescript
public URL(String protocol,
    String username,
    String password,
    String host,
    int port,
    String path,
    Map<String, String> parameters,
    Map<String, Map<String, String>> methodParameters) {

    if (StringUtils.isEmpty(username) && StringUtils.isNotEmpty(password)) {
    	throw new IllegalArgumentException("Invalid url");
    }

    this.protocol = protocol;
    this.username = username;
    this.password = password;
    this.host = host;
    this.port = Math.max(port, 0);
    this.address = getAddress(this.host, this.port);

    while (path != null && path.startsWith("/")) {
    	path = path.substring(1);
    }
    this.path = path;

    if (parameters == null) {
    	parameters = new HashMap<>();
    } else {
    	parameters = new HashMap<>(parameters);
    }

    this.parameters = Collections.unmodifiableMap(parameters);
    this.methodParameters = Collections.unmodifiableMap(methodParameters);
}
```

另外，在dubbo-common包中还提供了URL的辅助类：

URLBuilder，辅助构造URL对象

URLStrParser，将字符串解析成URL对象

### (3)契约的力量

对于Dubbo中的URL，很多人称之为"配置总线"，也有人称之为"统一配置模型"。虽然说法不同，但都是在表达一个意思，就是URL在Dubbo中被当作是"公共的契约"。一个URL可以包含非常多的扩展点参数，URL作为上下文信息贯穿整个扩展点设计体系。

其实一个优秀的开源产品都有一套灵活清晰的扩展契约，不仅第三方可以按照这个契约进行扩展，其自身内核也可以按照这个契约进行搭建。

如果没有一个公共的契约，只针对每个接口或方法进行约定，就会导致不同的接口甚至同一接口中的不同方法，以不同的参数类型进行传参，一会儿传递Map，一会儿传递字符串，而且字符串的格式也不确定，需要自己进行解析，这就多了一层没有明确表现出来的隐含的约定。

所以说，在Dubbo中使用URL的好处多多，增加了便捷性：

好处一：使用URL这种公共契约进行上下文信息传递，最重要的就是代码更加易读、易懂，不用花大量时间去揣测传递数据的格式和含义，进而形成一个统一的规范，使得代码易写、易读。

好处二：使用URL作为方法的入参(相当于一个Key/Value都是String的Map)，它所表达的含义比单个参数更丰富，当代码需要扩展的时候，可以将新的参数以Key/Value的形式追加到URL之中，而不需要改变入参或是返回值的结构。

好处三：使用URL这种"公共契约"可以简化沟通，人与人之间的沟通消耗是非常大的，信息传递的效率非常低，使用统一的契约、术语、词汇范围，可以省去很多沟通成本，尽可能地提高沟通效率。

### (4)Dubbo中的URL示例

#### 一.URL在SPI中的应用

#### 二.URL在服务暴露中的应用

#### 三.URL在服务订阅中的应用

了解了URL的结构以及Dubbo使用URL的原因之后，下面来看Dubbo中的三个示例，进一步感受URL的重要性。

#### 一.URL在SPI中的应用

Dubbo SPI中有一个依赖URL的重要场景——适配器方法，是被@Adaptive注解标注的，URL一个很重要的作用就是与@Adaptive注解一起选择合适的扩展实现类。

例如在dubbo-registry-api模块中可以看到RegistryFactory这个接口的getRegistry()方法上有@Adaptive({"protocol"})注解。说明这是一个适配器方法，Dubbo在运行时会为其动态生成相应的"$Adaptive"类型，如下所示：

```java
//dubbo-registry-api模块的RegistryFactory接口
public interface RegistryFactory {
    @Adaptive({"protocol"})
    Registry getRegistry(URL url);
}

//运行时动态生成$Adaptive类型的方法
public class RegistryFactory$Adaptive implements RegistryFactory {
    public Registry getRegistry(org.apache.dubbo.common.URL arg0) {
    	if (arg0 == null) throw new IllegalArgumentException("...");
     	org.apache.dubbo.common.URL url = arg0;

      	//尝试获取URL的Protocol，如果Protocol为空，则使用默认值"dubbo"
    	String extName = (url.getProtocol() == null ? "dubbo" : url.getProtocol());
    	if (extName == null) throw new IllegalStateException("...");

     	//根据扩展名选择相应的扩展实现，Dubbo SPI的核心原理与此相关
    	RegistryFactory extension = (RegistryFactory) ExtensionLoader.getExtensionLoader(RegistryFactory.class).getExtension(extName);
    	return extension.getRegistry(arg0);
    }
}
```

可以看到，在生成的RegistryFactory$Adaptive类中会自动实现getRegistry()方法，其中会根据URL的Protocol确定扩展名称，从而确定使用的具体扩展实现类。我们可以找到RegistryProtocol这个类，并在其getRegistry()方法中打一个断点。

```java
public class RegistryProtocol implements Protocol {
    ...
    protected Registry getRegistry(final Invoker<?> originInvoker) {
        URL registryUrl = getRegistryUrl(originInvoker);
        return registryFactory.getRegistry(registryUrl);
    }
    ...
}
```

如果传入的registryUrl值为："zookeeper://127.0.0.1:2181/org.apache.dubbo.registry.Regis..."，那么在RegistryFactory$Adaptive中得到的扩展名称为zookeeper，此次使用的Registry扩展实现类就是：ZookeeperRegistryFactory。

#### 二.URL在服务暴露中的应用

已经知道Provider在启动时，会将自身暴露的服务注册到ZK上，具体是注册哪些信息到ZK上呢？我们来看ZookeeperRegistry.doRegister()方法，在其中打个断点，然后Debug启动Provider：

```typescript
public class ZookeeperRegistry extends FailbackRegistry {
    ...
    @Override
    public void doRegister(URL url) {
        try {
            zkClient.create(toUrlPath(url), url.getParameter(DYNAMIC_KEY, true));
        } catch (Throwable e) {
            throw new RpcException("Failed to register " + url + " to zookeeper " + getUrl() + ", cause: " + e.getMessage(), e);
        }
    }
    ...
}
```

可以看到，传入的URL中包含了Provider的地址、暴露的接口等信息：toUrlPath()方法会根据传入的URL参数确定在ZK上创建的节点路径，还会通过URL中的dynamic参数值确定创建的ZNode是临时节点还是持久节点。

#### 三.URL在服务订阅中的应用

Consumer启动后会向注册中心进行订阅操作，并监听自己关注的Provider。那Consumer是如何告诉注册中心自己关注哪些Provider呢？我们来看ZookeeperRegistry这个实现类，它是由上面的ZookeeperRegistryFactory工厂类创建的Registry接口实现。其中的doSubscribe()方法是订阅操作的核心实现，在其中打一个断点，并Debug启动Demo中Consumer：

```typescript
public class ZookeeperRegistry extends FailbackRegistry {
    ...
    @Override
    public void doSubscribe(final URL url, final NotifyListener listener) {
        try {
            if (ANY_VALUE.equals(url.getServiceInterface())) {
                String root = toRootPath(); // 获取根节点
                // 获取NotifyListener对应的ChildListener
                ConcurrentMap<NotifyListener, ChildListener> listeners = zkListeners.computeIfAbsent(url, k -> new ConcurrentHashMap<>());
                ChildListener zkListener = listeners.computeIfAbsent(listener, k -> (parentPath, currentChilds) -> {
                    for (String child : currentChilds) {
                        child = URL.decode(child);
                        if (!anyServices.contains(child)) {
                            anyServices.add(child); // 记录该节点已经订阅过
                            // 该ChildListener要做的就是触发对具体Service节点的订阅
                            subscribe(url.setPath(child).addParameters(INTERFACE_KEY, child, Constants.CHECK_KEY, String.valueOf(false)), k);
                        }
                    }
                });

                zkClient.create(root, false); // 保证根节点存在
                // 第一次订阅的时候，要处理当前已有的Service层节点
                List<String> services = zkClient.addChildListener(root, zkListener);
                if (CollectionUtils.isNotEmpty(services)) {
                    for (String service : services) {
                        service = URL.decode(service);
                        anyServices.add(service);
                        subscribe(url.setPath(service).addParameters(INTERFACE_KEY, service, Constants.CHECK_KEY, String.valueOf(false)), listener);
                    }
                }
            } else {
                List<URL> urls = new ArrayList<>();
                for (String path : toCategoriesPath(url)) { // 要订阅的所有path
                    // 一个NotifyListener关联一个ChildListener，这个ChildListener会回调
                    // ZookeeperRegistry.notify()方法，其中会回调当前NotifyListener
                    ConcurrentMap<NotifyListener, ChildListener> listeners = zkListeners.computeIfAbsent(url, k -> new ConcurrentHashMap<>());
                    ChildListener zkListener = listeners.computeIfAbsent(listener, k -> (parentPath, currentChilds) -> ZookeeperRegistry.this.notify(url, k, toUrlsWithEmpty(url, parentPath, currentChilds)));
                    // 尝试创建持久节点，主要是为了确保当前path在Zookeeper上存在
                    zkClient.create(path, false);
                    // 这一个ChildListener会添加到多个path上
                    List<String> children = zkClient.addChildListener(path, zkListener);
                    if (children != null) {
                        // 如果没有Provider注册，toUrlsWithEmpty()方法会返回empty协议的URL
                        urls.addAll(toUrlsWithEmpty(url, path, children));
                    }
                }
                // 初次订阅的时候，会主动调用一次notify()方法，通知NotifyListener处理当前已有的URL等注册数据
                notify(url, listener, urls);
            }
        } catch (Throwable e) {
            throw new RpcException("Failed to subscribe " + url + " to zookeeper " + getUrl() + ", cause: " + e.getMessage(), e);
        }
    }
    ...
}
```

假如传入的URL参数如下：

```ini
url="consumer://192.168.124.4/...&category=providers,configurators,rooters&...&interface=org.apache.dubbo.demo.DemoService&..."
```

那么其中Protocol为consumer表示是Consumer的订阅协议。其中的category参数表示要订阅的分类，这里要订阅providers、confifigurators以及routers三个分类。其中interface参数表示订阅哪个服务接口，这里要订阅的是org.apache.dubbo.demo.DemoService实现的Provider。通过URL中的上述参数，ZookeeperRegistry会在toCategoriesPath()方法中将其整理成一个ZooKeeper路径，然后调用zkClient在其上添加监听。

### (5)总结

这里重点介绍了：Dubbo对URL的封装以及相关的工具类，然后说明了统一契约的好处，当然也是Dubbo使用URL作为统一配置总线的好处。最后介绍了Dubbo SPI、Provider注册、Consumer订阅场景中URL发挥的作用和实现。

## 3.Dubbo SPI精析(接口实现两极反转)

### (1)微内核架构简介

### (2)JDK SPI简介

### (3)JDK SPI机制

### (4)JDK SPI源码分析

### (5)JDK SPI在JDBC中的应用

### (6)Dubbo SPI简介

### (7)Dubbo SPI之@SPI注解

### (8)Dubbo SPI之@Adaptive注解与适配器

### (9)Dubbo SPI之自动包装特性

### (10)Dubbo SPI之自动装配特性

### (11)Dubbo SPI之@Activate注解与自动激活特性

### (12)总结

### (1)微内核架构简介

Dubbo为了更好地达到OCP原则，即"对扩展开放，对修改封闭"的原则，采用了"微内核 + 插件"的架构。

那什么是微内核架构呢？微内核架构也被称为插件化架构，这是一种面向功能进行拆分的可扩展性架构。内核功能是比较稳定的，只负责管理插件的生命周期，不会因为系统功能的扩展而不断进行修改。功能上的扩展全部封装到插件之中，插件模块是独立存在的模块，包含特定的功能，能拓展内核系统的功能。

微内核架构中，内核通常采用Factory、IoC、OSGi等方式管理插件生命周期。Dubbo最终决定采用SPI机制来加载插件，Dubbo SPI参考JDK原生的SPI机制，进行了性能优化以及功能增强。因此，在讲解Dubbo SPI之前，我们有必要先来介绍一下JDK SPI的工作原理。

### (2)JDK SPI简介

SPI(Service Provider Interface)主要是被框架开发人员使用的一种技术。例如，使用Java语言访问数据库时我们会使用到java.sql.Driver接口：不同数据库产品底层的协议不同，提供的 java.sql.Driver实现也不同，在开发java.sql.Driver接口时，框架开发人员并不清楚用户(业务开发人员)最终会使用哪个数据库，在这种情况下就可以使用Java SPI机制，在实际运行过程中为java.sql.Driver接口寻找具体的实现。

### (3)JDK SPI机制

说明一：当服务的提供者提供了一种接口的实现之后(比如MySQL数据库连接服务提供了java.sql.Driver实现)，需要在Classpath下的META-INF/services/目录里创建一个以服务接口命名的文件，此文件记录了该jar包提供的服务接口的具体实现类。

说明二：当某个应用引入了该jar包且需要使用该服务时(比如业务开发人员引入了MySQL数据库连接服务)，JDK SPI机制就可以通过查找这个jar包的META-INF/services/中的配置文件来获得具体的实现类名，进而实现类的加载和实例化，最终使用该实现类完成业务功能。

下面我们通过一个简单的示例演示JDK SPI的基本使用方式：

步骤一：首先需要创建一个Log接口，来模拟日志打印的功能：

```cs
public interface Log {
    void log(String info);
}
```

步骤二：接下来提供两个实现—Logback和Log4j，分别代表两个不同日志框架的实现，如下所示：

```typescript
public class Logback implements Log {
    @Override
    public void log(String info) {
    	System.out.println("Logback:" + info);
    }
}

public class Log4j implements Log {
    @Override
    public void log(String info) {
    	System.out.println("Log4j:" + info);
    }
}
```

步骤三：在项目的resources/META-INF/services目录下添加一个名为 com.xxx.Log 的文件。这是JDK SPI需要读取的配置文件，具体内容如下：

```
com.xxx.impl.Log4j
com.xxx.impl.Logback
```

步骤四：最后创建main()方法，其中会加载上述配置文件，创建全部Log接口实现的实例并执行其log()方法，如下所示：

```cpp
public class Main {
    public static void main(String[] args) {
        ServiceLoader<Log> serviceLoader = ServiceLoader.load(Log.class);
        Iterator<Log> iterator = serviceLoader.iterator();
        while (iterator.hasNext()) {
            Log log = iterator.next();
            log.log("JDK SPI");
        }
    }
}
// 输出如下:
// Log4j:JDK SPI
// Logback:JDK SPI
```

### (4)JDK SPI源码分析

通过上述示例，可以看到JDK SPI的入口方法是ServiceLoader.load()方法，接下来对其具体实现进行深入分析。

在ServiceLoader.load()方法中：

首先会尝试获取当前使用的ClassLoader(获取当前线程绑定的ClassLoader，查找失败后使用SystemClassLoader)，然后调用ServiceLoader.reload()方法。

调用链关系如下所示：

```xml
->ServiceLoader.load(Class<S>) (java.util)
    ServiceLoader.load(Class<S>, ClassLoader) (java.util)
      ServiceLoader.ServiceLoader(Class<S>, ClassLoader) (java.util)
        ServiceLoader.reload() (java.util)
```

在ServiceLoader.reload()方法中：

首先会清理providers缓存(LinkedHashMap类型集合)，该缓存用来记录ServiceLoader创建的实现对象。其中providers缓存的Key为实现类的完整类名，Value为实现类的对象。之后创建LazyIterator迭代器，用于读取SPI配置文件并实例化实现类对象。

ServiceLoader.reload()方法的具体实现，如下所示：

```typescript
private LinkedHashMap<String,S> providers = new LinkedHashMap<>();

public void reload() {
    providers.clear();
    lookupIterator = new LazyIterator(service, loader);
}
```

在前面的示例中，main()方法中使用的迭代器底层就是通过ServiceLoader.LazyIterator实现的。Iterator接口有两个关键方法：hasNext()方法和next()方法。

这里LazyIterator中的next()方法最终调用的是其nextService()方法，hasNext()方法最终调用的是hasNextService()方法，调用链关系如下所示：

```shell
->LazyIterator in ServiceLoader.hasNext() (java.util)
    LazyIterator in ServiceLoader.hasNextService() (java.util)

->LazyIterator in ServiceLoader.next() (java.util)
    LazyIterator in ServiceLoader.nextService() (java.util)
```

首先看LazyIterator.hasNextService()方法：该方法主要负责查找META-INF/services目录下的SPI配置文件并进行遍历解析，大致实现如下：

```typescript
private static final String PREFIX = "META-INF/services/";
Enumeration<URL> configs = null;
Iterator<String> pending = null;
String nextName = null;

private boolean hasNextService() {
    if (nextName != null) {
 	return true;
    }

    if (configs == null) {
  	String fullName = PREFIX + service.getName();

    	//加载配置文件
    	if (loader == null) {
     	    configs = ClassLoader.getSystemResources(fullName);
  	} else {
    	    configs = loader.getResources(fullName);
  	}

    	//按行读取SPI配置文件的内容
    	while ((pending == null) || !pending.hasNext()) {
     	    if (!configs.hasMoreElements()) {
       	        return false;
       	    }
            pending = parse(service, configs.nextElement());
	}

  	nextName = pending.next();
    	return true;
    }
}
```

在hasNextService()方法中完成SPI配置文件的解析后，再来看LazyIterator.nextService()方法：该方法负责实例化hasNextService()方法读取到的实现类，其中会将实例化的对象放到providers集合中缓存起来。核心实现如下所示：

```typescript
private S nextService() {
    String cn = nextName;
    nextName = null;

    //加载指定的实现类
    Class<?> c = Class.forName(cn, false, loader);
    if (!service.isAssignableFrom(c)) {
    	fail(service, "Provider " + cn + " not a subtype");
    }

    //创建实现类对象并进行强制类型转换
    S p = service.cast(c.newInstance());
    providers.put(cn, p);

    return p;
}
```

以上就是在main()方法中使用的迭代器的底层实现。

最后再来看一下main()方法中使用ServiceLoader.iterator()方法拿到的迭代器是如何实现的。这个迭代器是依赖LazyIterator实现的一个匿名内部类，核心实现如下：

```typescript
public Iterator<S> iterator() {
    return new Iterator<S>() {
        //knownProviders用来迭代providers缓存
        Iterator<Map.Entry<String,S>> knownProviders = providers.entrySet().iterator();

        //先查缓存，查不到再通过LazyIterator进行加载
        public boolean hasNext() {
            if (knownProviders.hasNext()) return true;
            return lookupIterator.hasNext();
        }

        //先查缓存，查不到再通过LazyIterator进行加载
        public S next() {
            if (knownProviders.hasNext()) return knownProviders.next().getValue();
            return lookupIterator.next();
 	}
    };
}
```

### (5)JDK SPI在JDBC中的应用

了解了JDK SPI实现的原理之后，我们再来看实践中JDBC是如何使用JDK SPI机制加载不同数据库厂商的实现类。JDK中只定义了一个java.sql.Driver接口，具体的实现是由不同数据库厂商来提供的，这里我们就以MySQL提供的JDBC实现包为例进行分析。

在mysql-connector-java-*.jar包中的META-INF/services目录下，有一个名为java.sql.Driver的文件，其中只有一行内容，如下所示，在使用mysql-connector-java-*.jar包连接MySQL数据库时，我们会用到DriverManager创建数据库连接：

```java
String url = "jdbc:xxx://xxx:xxx/xxx";
Connection conn = DriverManager.getConnection(url, username, pwd);
```

DriverManager是JDK提供的数据库驱动管理器，其中的static静态代码片段如下：

```javascript
static {
    loadInitialDrivers();
    println("JDBC DriverManager initialized");
}
```

在调用getConnection()方法的时候，DriverManager类会被Java虚拟机加载、解析并触发static代码块的执行。在loadInitialDrivers()方法中通过JDK SPI扫描Classpath下java.sql.Driver接口实现类并进行实例化，核心实现如下：

```typescript
private static void loadInitialDrivers() {
    String drivers = System.getProperty("jdbc.drivers");
    ServiceLoader<Driver> loadedDrivers = ServiceLoader.load(Driver.class);
    Iterator<Driver> driversIterator = loadedDrivers.iterator();

    while(driversIterator.hasNext()) {
    	driversIterator.next();
    }

    String[] driversList = drivers.split(":");
    for (String aDriver : driversList) {
        // 初始化Driver实现类
        Class.forName(aDriver, true, ClassLoader.getSystemClassLoader());
    }
}
```

在MySQL提供的com.mysql.cj.jdbc.Driver实现类中，同样有一段static静态代码块。这段代码会创建一个com.mysql.cj.jdbc.Driver对象并注册到DriverManager的registeredDrivers集合中，如下所示，其中DriverManager的registeredDrivers是一个CopyOnWriteArrayList类型。

```javascript
static {
    java.sql.DriverManager.registerDriver(new Driver());
}
```

在getConnection()方法中，DriverManager从registeredDrivers集合中获取对应的Driver对象创建Connection，核心实现如下所示：

```java
private static Connection getConnection(String url, java.util.Properties info, Class<?> caller) throws SQLException {
    for (DriverInfo aDriver : registeredDrivers) {
    	Connection con = aDriver.driver.connect(url, info);
     	return con;
    }
}
```

### (6)Dubbo SPI简介

Dubbo并没有直接使用JDK SPI机制，而是借鉴其思想，实现了自身的一套SPI机制。在开始介绍Dubbo SPI实现之前，我们先来统一下面两个概念。

#### 一.扩展点或扩展接口

通过SPI机制查找并加载实现的接口(又称"扩展接口")，前文示例中介绍的Log接口、com.mysql.cj.jdbc.Driver接口，都是扩展点。

#### 二.扩展点实现或扩展实现类

实现了扩展接口的实现类。JDK SPI在查找扩展实现类的过程中，需要遍历SPI配置文件中定义的所有实现类，该过程中会将这些实现类全部实例化。

如果SPI配置文件中定义了多个实现类，而我们只需要使用其中一个实现类时，就会生成不必要的对象。例如，org.apache.dubbo.rpc.Protocol接口有DubboProtocol、HttpProtocol、HessianProtocol、ThriftProtocol等多个实现。如果使用JDK SPI，就会加载全部实现类并进行初始化，导致资源的浪费。Dubbo SPI不仅解决了上述资源浪费的问题，还对SPI配置文件扩展和修改。

首先，Dubbo按照SPI配置文件的用途，将其分成了三类目录：

```swift
1.META-INF/services/目录：
该目录下的SPI配置文件用来兼容JDK SPI；

2.META-INF/dubbo/目录：
该目录用于存放用户自定义SPI配置文件；

3.META-INF/dubbo/internal/目录：
该目录用于存放Dubbo内部使用的SPI配置文件；
```

然后，Dubbo将SPI配置文件改成了KV格式，例如：

```ini
dubbo=org.apache.dubbo.rpc.protocol.dubbo.DubboProtocol
```

其中key被称为扩展名，当我们在为一个接口查找具体实现类时，可以指定扩展名来选择相应的扩展实现。例如这里指定扩展名为dubbo，Dubbo SPI就知道我们要使用：org.apache.dubbo.rpc.protocol.dubbo.DubboProtocol这个扩展实现类，只实例化这一个扩展实现即可，无须实例化SPI配置文件中的其他扩展实现类。

使用KV格式的SPI配置文件的另一个好处是：让我们更容易定位到问题。假设我们使用的一个扩展实现类所在的jar包没有引入到项目中，那么Dubbo SPI在抛出异常时会携带该扩展名信息，而不是简单地提示扩展实现类无法加载，这些更加准确的异常信息降低了排查问题的难度，提高了排查问题的效率。

### (7)Dubbo SPI之@SPI注解

Dubbo中某个接口被@SPI注解修饰时，就表示该接口是扩展接口。下面示例中的org.apache.dubbo.rpc.Protocol接口就是一个扩展接口：

```java
@SPI("dubbo")
public interface Protocol {
    int getDefaultPort(); // 默认端口

    // 将一个Invoker发布出去，export()方法实现需要是幂等的，即同一个服务暴露多次和暴露一次的效果是相同的
    @Adaptive
    <T> Exporter<T> export(Invoker<T> invoker) throws RpcException;

    // 引用一个Invoker，refer()方法会根据参数返回一个Invoker对象，Consumer端可以通过这个Invoker请求到Provider端的服务
    @Adaptive
    <T> Invoker<T> refer(Class<T> type, URL url) throws RpcException;

    // 销毁export()方法以及refer()方法使用到的Invoker对象，释放当前Protocol对象底层占用的资源
    void destroy();

    // 返回当前Protocol底层的全部ProtocolServer
    default List<ProtocolServer> getServers() {
        return Collections.emptyList();
    }
}
```

@SPI注解的value值指定了默认的扩展名称：例如在通过Dubbo SPI加载Protocol接口实现时，如果没有明确指定扩展名，则默认会将@SPI注解的value值作为扩展名，即加载dubbo这个扩展名对应的org.apache.dubbo.rpc.protocol.dubbo.DubboProtocol这个扩展实现类。相关的SPI配置文件在dubbo-rpc-dubbo模块中，如下所示：

![图片](assets/7ec859b35417.png)

那么ExtensionLoader是如何处理@SPI注解的？ExtensionLoader位于dubbo-common模块中的extension包中，功能类似于JDK SPI中的java.util.ServiceLoader。Dubbo SPI的核心逻辑几乎都封装在ExtensionLoader之中(包括@SPI注解的处理逻辑)，其使用方式如下所示：

```cs
Protocol protocol = ExtensionLoader.getExtensionLoader(Protocol.class).getExtension("dubbo");
```

这里首先来了解一下ExtensionLoader中三个核心的静态字段：

```swift
一.strategies(LoadingStrategy[] 类型)
其中LoadingStrategy 接口有三个实现(通过JDK SPI方式加载的)，
分别对应前面介绍的三个Dubbo SPI配置文件所在的目录，且都继承了Prioritized这个优先级接口。

默认优先级是：
ServicesLoadingStrateg < DubboLoadingStrategy < DubboInternalLoadingStrategy

二.EXTENSION_LOADERS(ConcurrentMap<Class, ExtensionLoader>类型)
Dubbo中一个扩展接口对应一个ExtensionLoader实例，该集合缓存了全部ExtensionLoader实例。
其中的Key为扩展接口，Value为加载其扩展实现的ExtensionLoader实例。

三.EXTENSION_INSTANCES(ConcurrentMap<Class<?>, Object>类型)
该集合缓存了扩展实现类与其实例对象的映射关系。
在前面示例中，Key为Class，Value为DubboProtocol对象。
```

下面再来看一下ExtensionLoader的五个实例字段：

```swift
一.type(Class<?>类型)
当前ExtensionLoader实例负责加载扩展接口。

二.cachedDefaultName(String类型)
记录了type这个扩展接口上@SPI注解的value值，也就是默认扩展名。

三.cachedNames(ConcurrentMap<Class<?>, String>类型)
缓存了该ExtensionLoader加载的扩展实现类与扩展名之间的映射关系。

四.cachedClasses(Holder<Map<String, Class<?>>>类型)
缓存了该ExtensionLoader加载的扩展名与扩展实现类之间的映射关系，cachedNames集合的反向关系缓存。

五.cachedInstances(ConcurrentMap<String, Holder<Object>>类型)
缓存了该ExtensionLoader加载的扩展名与扩展实现对象之间的映射关系。
```

```swift
public class ExtensionLoader<T> {
    ...
    //当前ExtensionLoader实例负责加载扩展接口
    private final Class<?> type;

    //记录了type这个扩展接口上@SPI注解的value值，也就是默认扩展名
    private String cachedDefaultName;

    //缓存了该ExtensionLoader加载的扩展实现类与扩展名之间的映射关系
    private final ConcurrentMap<Class<?>, String> cachedNames = new ConcurrentHashMap<>();

    //缓存了该ExtensionLoader加载的扩展名与扩展实现类之间的映射关系，cachedNames集合的反向关系缓存
    private final Holder<Map<String, Class<?>>> cachedClasses = new Holder<>();

    //缓存了该ExtensionLoader加载的扩展名与扩展实现对象之间的映射关系
    private final ConcurrentMap<String, Holder<Object>> cachedInstances = new ConcurrentHashMap<>();
    ...
}
```

ExtensionLoader.getExtensionLoader()会根据扩展接口从EXTENSION_LOADERS中查找相应的ExtensionLoader实例。核心实现如下：

```typescript
public static <T> ExtensionLoader<T> getExtensionLoader(Class<T> type) {
    ExtensionLoader<T> loader = (ExtensionLoader<T>) EXTENSION_LOADERS.get(type);
    if (loader == null) {
    	EXTENSION_LOADERS.putIfAbsent(type, new ExtensionLoader<T>(type));
     	loader = (ExtensionLoader<T>) EXTENSION_LOADERS.get(type);
    }
    return loader;
}
```

得到接口对应的ExtensionLoader对象之后会调用其getExtension()方法：根据传入的扩展名称从cachedInstances缓存中查找扩展实现的实例，最终将其实例化后返回。

```typescript
public T getExtension(String name) {
    //getOrCreateHolder()方法中封装了查找cachedInstances缓存的逻辑
    Holder<Object> holder = getOrCreateHolder(name);
    Object instance = holder.get();

    //dubbo-check防止并发问题
    if (instance == null) {
        synchronized (holder) {
            instance = holder.get();
            if (instance == null) {
                //根据扩展名从SPI配置文件中查找对应的扩展实现类
                instance = createExtension(name);
                holder.set(instance);
            }
    	}
    }
    return (T) instance;
}
```

在createExtension()方法中：完成了SPI配置文件的查找以及相应扩展实现类的实例化，同时还实现了自动装配以及自动Wrapper包装等功能，其核心流程如下：

步骤一：获取cachedClasses缓存，根据扩展名从cachedClasses缓存中获取扩展实现类。如果cachedClasses未初始化，则会扫描前面介绍的三个SPI目录获取查找相应的SPI配置文件。然后加载其中的扩展实现类，最后将扩展名和扩展实现类的映射关系记录到cachedClasses缓存中。这部分逻辑在loadExtensionClasses()和loadDirectory()方法中。

步骤二：根据扩展实现类从EXTENSION_INSTANCES缓存中查找相应的实例。如果查找失败，会通过反射创建扩展实现对象。

步骤三：自动装配扩展实现对象中的属性(即调用其setter)，这里涉及ExtensionFactory以及自动装配的相关内容。

步骤四：自动包装扩展实现对象，这里涉及Wrapper类以及自动包装特性的相关内容。

步骤五：如果扩展实现类实现了Lifecycle接口，在initExtension()方法中会调用initialize()方法进行初始化。

```typescript
private T createExtension(String name) {
    //获取cachedClasses缓存，根据扩展名从cachedClasses缓存中获取扩展实现类；
    //如果cachedClasses未初始化，则会扫描前面介绍的三个SPI目录获取查找相应的SPI配置文件；
    //然后加载其中的扩展实现类，最后将扩展名和扩展实现类的映射关系记录到cachedClasses缓存中；
    //这部分逻辑在loadExtensionClasses()和loadDirectory()方法中；
    Class<?> clazz = getExtensionClasses().get(name);
    if (clazz == null) {
        throw findException(name);
    }

    try {
        //根据扩展实现类从EXTENSION_INSTANCES缓存中查找相应的实例；
        //如果查找失败，会通过反射创建扩展实现对象；
        T instance = (T) EXTENSION_INSTANCES.get(clazz);
        if (instance == null) {
            EXTENSION_INSTANCES.putIfAbsent(clazz, clazz.newInstance());
            instance = (T) EXTENSION_INSTANCES.get(clazz);
        }

        //自动装配扩展实现对象中的属性(即调用其setter)；这里涉及ExtensionFactory以及自动装配的相关内容；
        injectExtension(instance);

        //自动包装扩展实现对象；这里涉及Wrapper类以及自动包装特性的相关内容；
        Set<Class<?>> wrapperClasses = cachedWrapperClasses;
        if (CollectionUtils.isNotEmpty(wrapperClasses)) {
            for (Class<?> wrapperClass : wrapperClasses) {
                instance = injectExtension((T);
                wrapperClass.getConstructor(type).newInstance(instance));
            }
        }

        //如果扩展实现类实现了Lifecycle接口，在initExtension()方法中会调用initialize()方法进行初始化；
        initExtension(instance);
        return instance;
    } catch (Throwable t) {
        throw new IllegalStateException("Extension instance (name: " + name + ", class: " + type + ") couldn't be instantiated: " + t.getMessage(), t);
    }
}
```

### (8)Dubbo SPI之@Adaptive注解与适配器

@Adaptive注解用来实现Dubbo的适配器功能。那什么是适配器呢？这里通过一个示例进行说明。Dubbo中的ExtensionFactory接口有三个实现类，如下图所示：ExtensionFactory接口上有@SPI注解，AdaptiveExtensionFactory实现类上有@Adaptive注解。

![图片](assets/de375b598e89.png)

AdaptiveExtensionFactory不实现任何具体的功能。AdaptiveExtensionFactory是用来适配ExtensionFactory的SpiExtensionFactory和SpringExtensionFactory这两种实现。AdaptiveExtensionFactory会根据运行时的一些状态来选择具体调用ExtensionFactory的哪个实现。

@Adaptive注解还可以加到接口方法之上，Dubbo会动态生成适配器类。例如，Transporter接口有两个被@Adaptive注解修饰的方法：

```java
@SPI("netty")
public interface Transporter {
    @Adaptive({Constants.SERVER_KEY, Constants.TRANSPORTER_KEY})
    RemotingServer bind(URL url, ChannelHandler handler) throws RemotingException;

    @Adaptive({Constants.CLIENT_KEY, Constants.TRANSPORTER_KEY})
    Client connect(URL url, ChannelHandler handler) throws RemotingException;
}
```

Dubbo会生成一个Transporter$Adaptive适配器类，该类继承了Transporter接口：

```java
public class Transporter$Adaptive implements Transporter {
    public org.apache.dubbo.remoting.Client connect(URL arg0, ChannelHandler arg1) throws RemotingException {
    	//必须传递URL参数
     	if (arg0 == null) throw new IllegalArgumentException("url == null");
     	URL url = arg0;

      	//确定扩展名，优先从URL中的client参数获取，其次是transporter参数
    	//这两个参数名称由@Adaptive注解指定，最后是@SPI注解中的默认值
      	String extName = url.getParameter("client", url.getParameter("transporter", "netty"));
       if (extName == null) throw new IllegalStateException("...");

       //通过ExtensionLoader加载Transporter接口指定扩展实现
       Transporter extension = (Transporter) ExtensionLoader.getExtensionLoader(Transporter.class).getExtension(extName);
       return extension.connect(arg0, arg1);
    }
    ...
}
```

生成Transporter$Adaptive这个类的逻辑位于ExtensionLoader.createAdaptiveExtensionClass()方法，其中涉及到了javassist等方面的知识。

明确了@Adaptive注解的作用后，回到ExtensionLoader.createExtension()方法。其中在扫描SPI配置文件的时候，会调用loadClass()方法加载SPI配置文件中指定的类，调用链如下所示：

```typescript
->ExtensionLoader.loadClass(Map<String, Class<?>>, URL, Class<?>, String, boolean)
    ExtensionLoader.loadResource(Map<String, Class<?>>, ClassLoader, URL, boolean, String...)
      ExtensionLoader.loadDirectory(Map<String, Class<?>>, String, String, boolean, boolean, String...)
        ExtensionLoader.loadExtensionClasses()
          ExtensionLoader.getExtensionClasses()
            ExtensionLoader.createExtension(String)
```

loadClass()方法中会识别加载扩展实现类上的@Adaptive注解，然后将该扩展实现的类型缓存到cachedAdaptiveClass这个实例字段上(volatile修饰)：

```cs
private void loadClass() {
    if (clazz.isAnnotationPresent(Adaptive.class)) {
    	// 缓存到cachedAdaptiveClass字段
     	cacheAdaptiveClass(clazz, overridden);
    } else {
    	...
    }
}
```

我们可以通过ExtensionLoader.getAdaptiveExtension()方法获取适配器实例，并将该实例缓存到cachedAdaptiveInstance字段(Holder类型)中，核心流程如下：

步骤一：首先检查cachedAdaptiveInstance字段中是否已缓存了适配器实例，如果已缓存则直接返回该实例即可。否则会调用getExtensionClasses()方法，其中就会触发loadClass()方法，完成cachedAdaptiveClass字段的填充。

步骤二：如果存在@Adaptive注解修饰的扩展实现类，该类就是适配器类，通过newInstance()方法将其实例化即可。如果不存在@Adaptive注解修饰的扩展实现类，就需要通过createAdaptiveExtensionClass()方法，扫描扩展接口中方法上的@Adaptive注解，动态生成适配器类，然后实例化。

步骤三：接下来调用injectExtension()方法进行自动装配，就能得到一个完整的适配器实例。

步骤四：最后将适配器实例缓存到cachedAdaptiveInstance字段，然后返回适配器实例。

getAdaptiveExtension()方法的具体源码如下：

```typescript
public T getAdaptiveExtension() {
    //检查cachedAdaptiveInstance字段中是否已缓存了适配器实例，如果已缓存，则直接返回该实例即可。
    Object instance = cachedAdaptiveInstance.get();

    if (instance == null) {
        if (createAdaptiveInstanceError != null) {
            throw new IllegalStateException("Failed to create adaptive instance: " +
                    createAdaptiveInstanceError.toString(),
                    createAdaptiveInstanceError);
        }

        synchronized (cachedAdaptiveInstance) {
            instance = cachedAdaptiveInstance.get();
            if (instance == null) {
                try {
                    instance = createAdaptiveExtension();
                    //将适配器实例缓存到cachedAdaptiveInstance字段，然后返回适配器实例
                    cachedAdaptiveInstance.set(instance);
                } catch (Throwable t) {
                    createAdaptiveInstanceError = t;
                    throw new IllegalStateException("Failed to create adaptive instance: " + t.toString(), t);
                }
            }
        }
    }

    return (T) instance;
}

private T createAdaptiveExtension() {
    try {
        //调用injectExtension()方法进行自动装配，就能得到一个完整的适配器实例
        return injectExtension((T) getAdaptiveExtensionClass().newInstance());
    } catch (Exception e) {
        throw new IllegalStateException("Can't create adaptive extension " + type + ", cause: " + e.getMessage(), e);
    }
}

private Class<?> getAdaptiveExtensionClass() {
    //调用getExtensionClasses()方法，其中就会触发loadClass()方法，完成cachedAdaptiveClass字段的填充
    getExtensionClasses();

    //如果存在@Adaptive注解修饰的扩展实现类，该类就是适配器类，通过newInstance()将其实例化即可
    if (cachedAdaptiveClass != null) {
        return cachedAdaptiveClass;
    }

    //如果不存在@Adaptive注解修饰的扩展实现类，
    //就需要通过createAdaptiveExtensionClass()方法扫描扩展接口中方法上的@Adaptive注解，
    //动态生成适配器类，然后实例化
    return cachedAdaptiveClass = createAdaptiveExtensionClass();
}
```

此外我们还可以通过API方式(addExtension()方法)设置cachedAdaptiveClass这个字段，指定适配器类型(知道即可)。总之，适配器什么实际工作都不用做，就是根据参数和状态选择其他扩展实现来完成工作。

Dubbo SPI中，自己写代码提供适配器实现时，在适配器类上添加@Adaptive注解即可。如果想通过动态生成的方式生成适配器类，可以在扩展接口方法上添加@Adaptive注解，这样便会由上述流程生成适配器类。生成的适配器类会根据URL参数选择具体的扩展实现。

### (9)Dubbo SPI之自动包装特性

Dubbo中的一个扩展接口可能有多个扩展实现类，这些扩展实现类可能会包含一些相同的逻辑，如果在每个实现类中都写一遍，那么这些重复代码就会变得很难维护。

Dubbo提供的自动包装特性，就可以解决这个问题。Dubbo将多个扩展实现类的公共逻辑，抽象到Wrapper类中。Wrapper类与普通的扩展实现类一样也实现了扩展接口，在获取真正的扩展实现对象时，在其外面包装一层Wrapper对象。Wrapper类可以理解成一层装饰器。

了解了Wrapper类的基本功能，回到ExtensionLoader.loadClass()方法中，可以看到：

步骤一：在isWrapperClass()方法中，会判断该扩展实现类是否包含拷贝构造函数(即构造函数只有一个参数且为扩展接口类型)。如果包含，则为Wrapper类，这就是判断Wrapper类的标准。

步骤二：将Wrapper类记录到cachedWrapperClasses(clazz)这个实例字段中进行缓存。

```cs
private void loadClass() {
    ...
    } else if (isWrapperClass(clazz)) {
        //1.在isWrapperClass()方法中，会判断该扩展实现类是否包含拷贝构造函数(即构造函数只有一个参数且为扩展接口类型)，
        //如果包含，则为Wrapper类，这就是判断Wrapper类的标准。
        //2.将Wrapper类记录到cachedWrapperClasses(Set<Class<?>>)这个实例字段中进行缓存
    	cacheWrapperClass(clazz);
    } else
    ...
}
```

前面在介绍createExtension()方法的步骤四时，有下面这段代码。其中会遍历全部Wrapper类并一层层包装到真正的扩展实例对象外层。

```powershell
Set<Class<?>> wrapperClasses = cachedWrapperClasses;
if (CollectionUtils.isNotEmpty(wrapperClasses)) {
    for (Class<?> wrapperClass : wrapperClasses) {
    	instance = injectExtension((T) wrapperClass.getConstructor(type).newInstance(instance));
    }
}
```

### (10)Dubbo SPI之自动装配特性(自动加载)

在createExtension()方法中我们看到，Dubbo SPI在拿到扩展实现类的对象(以及Wrapper类的对象)后，还会调用injectExtension()方法扫描其全部setter方法，并根据setter方法的名称以及参数的类型，加载相应的扩展实现，然后调用相应的setter方法填充属性，这就实现了Dubbo SPI的自动装配特性。

简单来说，自动装配属性就是在加载一个扩展点时将其依赖的扩展点一并加载并进行装配。下面看一下injectExtension()方法的具体实现：

```kotlin
private T injectExtension(T instance) {
    if (objectFactory == null) {
        return instance;
    }

    for (Method method : instance.getClass().getMethods()) {
        if (!isSetter(method)) {
            //如果不是setter方法，忽略该方法
            continue;
        }
        if (method.getAnnotation(DisableInject.class) != null) {
            //如果方法上明确标注了@DisableInject注解，忽略该方法
            continue;
        }
        Class<?> pt = method.getParameterTypes()[0];
        ...

        //根据setter方法的名称确定属性名称
        String property = getSetterProperty(method);

        //加载并实例化扩展实现类
        Object object = objectFactory.getExtension(pt, property);
        if (object != null) {
            //利用反射调用setter方法进行装配
            method.invoke(instance, object);
        }
    }
    return instance;
}
```

injectExtension()方法实现的自动装配依赖了ExtensionFactory(即objectFactory字段)。前面提到过ExtensionFactory有SpringExtensionFactory和SpiExtensionFactory两个真正的实现，还有一个实现AdaptiveExtensionFactory是适配器。下面分别介绍下这两个真正的实现：

#### 一.SpiExtensionFactory

根据扩展接口获取相应的适配器：

```typescript
@Override
public <T> T getExtension(Class<T> type, String name) {
    if (type.isInterface() && type.isAnnotationPresent(SPI.class)) {
        //查找type对应的ExtensionLoader实例
        ExtensionLoader<T> loader = ExtensionLoader.getExtensionLoader(type);
        if (!loader.getSupportedExtensions().isEmpty()) {
            return loader.getAdaptiveExtension();//获取适配器
        }
    }
    return null;
}
```

#### 二.SpringExtensionFactory

将属性名称作为Spring Bean的名称，从Spring容器中获取Bean：

```typescript
public <T> T getExtension(Class<T> type, String name) {
    //检查:type必须为接口且必须包含@SPI注解(略)
    if (type.isInterface() && type.isAnnotationPresent(SPI.class)) {
        return null;
    }

    //从Spring容器中查找Bean
    for (ApplicationContext context : CONTEXTS) {
        T bean = BeanFactoryUtils.getOptionalBean(context, name, type);
        if (bean != null) {
            return bean;
        }
    }
    return null;
}
```

### (11)Dubbo SPI之@Activate注解与自动激活特性

这里以Dubbo中的Filter为例说明自动激活特性的含义：org.apache.dubbo.rpc.Filter接口有非常多的扩展实现类，在一个场景中可能需要某几个Filter扩展实现类协同工作，而另一个场景中可能需要另外几个实现类一起工作，这样就需要一套配置来指定当前场景中哪些Filter实现是可用的，这就是@Activate注解要做的事情。

@Activate注解标注在扩展实现类上，有group、value以及order三个属性：

```sql
一.group属性
修饰的实现类是在Provider端被激活还是在Consumer端被激活。

二.value属性
修饰的实现类只在URL参数中出现指定的key时才会被激活。

三.order属性
用来确定扩展实现类的排序。
```

我们先来看loadClass()方法对@Activate的扫描：该方法会将包含@Activate注解的实现类缓存到cachedActivates这个实例字段。cachedActivates这个实例字段是Map类型，其中Key为扩展名，Value为@Activate注解。

```typescript
private void loadClass() {
    if (clazz.isAnnotationPresent(Adaptive.class)) {
        //处理@Adaptive注解
        cacheAdaptiveClass(clazz, overridden);
    } else if (isWrapperClass(clazz)) {
        //处理Wrapper类
        cacheWrapperClass(clazz);
    } else {//处理真正的扩展实现类
        //扩展实现类必须有无参构造函数
        clazz.getConstructor();
        ...
        //兜底:SPI配置文件中未指定扩展名称，则用类的简单名称作为扩展名
        String[] names = NAME_SEPARATOR.split(name);
        if (ArrayUtils.isNotEmpty(names)) {
            //将包含@Activate注解的实现类缓存到cachedActivates集合中
            cacheActivateClass(clazz, names[0]);

            for (String n : names) {
                //在cachedNames集合中缓存实现类->扩展名的映射
                cacheName(clazz, n);

                //在cachedClasses集合中缓存扩展名->实现类的映射
                saveInExtensionClass(extensionClasses, clazz, n, overridden);
            }
        }
    }
}
```

使用cachedActivates这个集合的地方是getActivateExtension()方法。getActivateExtension()参数是：url中包含了配置信息，values是配置中指定的扩展名，group为Provider或Consumer。下面是getActivateExtension()方法的核心逻辑：

步骤一：首先获取默认激活的扩展集合，默认激活的扩展实现类有几个条件：

```sql
条件一：在cachedActivates集合中存在。
条件二：@Activate注解指定的group属性与当前group匹配。
条件三：扩展名没有出现在values中(即未在配置中明确指定，也未在配置中明确指定删除)。
条件四：URL中出现了@Activate注解中指定的Key。
```

步骤二：然后按照@Activate注解中的order属性对默认激活的扩展集合进行排序。

步骤三：最后按序添加自定义扩展实现类的对象。

```typescript
public List<T> getActivateExtension(URL url, String[] values, String group) {
    List<T> activateExtensions = new ArrayList<>();

    //values就是扩展名
    List<String> names = values == null ? new ArrayList<>(0) : asList(values);

    if (!names.contains(REMOVE_VALUE_PREFIX + DEFAULT_KEY)) {
        //触发cachedActivates等缓存字段的加载
        getExtensionClasses();
        for (Map.Entry<String, Object> entry : cachedActivates.entrySet()) {
            String name = entry.getKey();//扩展名
            Object activate = entry.getValue();//@Active注解
            String[] activateGroup, activateValue;

            if (activate instanceof Activate) {//@Active注解中的配置
                activateGroup = ((Activate) activate).group();
                activateValue = ((Activate) activate).value();
            } else {
                continue;
            }

            if (isMatchGroup(group, activateGroup) //匹配group
                && !names.contains(name) //匹配扩展名
                && !names.contains(REMOVE_VALUE_PREFIX + name) //如果包含"-"表示不激活该扩展实现
                && isActive(activateValue, url) //检测URL中是否出现了指定的Key
            ) {
                activateExtensions.add(getExtension(name));//加载扩展实现
            }
        }
        //排序
        activateExtensions.sort(ActivateComparator.COMPARATOR);
    }

    List<T> loadedExtensions = new ArrayList<>();
    for (int i = 0; i < names.size(); i++) {
        String name = names.get(i);
        //通过"-"开头的配置明确指定不激活的扩展实现，直接忽略
        if (!name.startsWith(REMOVE_VALUE_PREFIX) && !names.contains(REMOVE_VALUE_PREFIX + name)) {
            if (DEFAULT_KEY.equals(name)) {
                if (!loadedExtensions.isEmpty()) {
                    //按照顺序，将自定义的扩展添加到默认扩展集合前面
                    activateExtensions.addAll(0, loadedExtensions);
                    loadedExtensions.clear();
                }
            } else {
                loadedExtensions.add(getExtension(name));
            }
        }
    }

    if (!loadedExtensions.isEmpty()) {
        //按照顺序，将自定义的扩展添加到默认扩展集合后面
        activateExtensions.addAll(loadedExtensions);
    }
    return activateExtensions;
}
```

最后举个简单的例子说明上述处理流程，假设cachedActivates集合缓存的扩展实现如下表所示：

![图片](assets/a7831ec60b35.png)

在Provider端调用getActivateExtension()方法时传入的values配置为："demoFilter3,demoFilter2,default,demoFilter1"，那么根据上面的逻辑得到默认激活的扩展实实现集合中有[demoFilter4, demoFilter6]，排序后为[demoFilter6, demoFilter4]，按序添加自定义扩展实例之后得到[demoFilter3, demoFilter6, demoFilter4, demoFilter1]。

### (12)总结

首先介绍了JDK提供的SPI机制的基本使用，然后深入分析了JDK SPI的核心原理和底层实现，对其源码进行了深入剖析。最后以MySQL提供的JDBC实现为例，分析了JDK SPI在实践中的使用方式。

JDK SPI机制虽然简单易用，但是也存在一些小瑕疵，就是：JDK SPI在查找扩展实现类的过程中，需要遍历SPI配置文件中定义的所有实现类，该过程中会将这些实现类全部实例化。如果SPI配置文件中定义了多个实现类，而我们只需要使用其中一个实现类时，就会生成不必要的对象。

此外深入全面地介绍了Dubbo SPI的核心实现：首先介绍了@SPI注解的底层实现，这是Dubbo SPI最核心的基础，然后介绍了@Adaptive注解与动态生成适配器类的核心原理和实现。最后分析了Dubbo SPI中的自动包装和自动装配特性，以及自动激活特性的原理。Dubbo SPI是Dubbo框架实现扩展机制的核心，需要仔细研究其实现，才能更好进行Dubbo源码分析。

## 4.Java SPI详细说明

### (1)什么是SPI

### (2)SPI使用演示

### (3)ServiceLoader分析

### (4)总结

### (1)什么是SPI

#### 一.背景

在面向对象的设计原则中，一般推荐模块之间基于接口编程。通常情况下调用方模块是不会感知到被调用方模块的内部具体实现。一旦代码里面涉及具体实现类，就违反了开闭原则，如果需要替换一种实现，就需要修改代码。为了实现在模块装配的时候不用在程序里面动态指明，这就需要一种服务发现机制。Java SPI就是提供了这样一个机制：为某个接口寻找服务实现的机制。这有点类似IOC的思想，将装配的控制权移交到了程序之外。

SPI英文为Service Provider Interface，字面意思就是："服务提供者的接口"。也就是专门提供给服务提供者或者扩展框架功能的开发者去使用的一个接口，SPI将服务接口和具体的服务实现分离开来，将服务调用方和服务实现者解耦，能够提升程序的扩展性、可维护性，修改或者替换服务实现并不需要修改调用方。

#### 二.使用场景

很多框架都使用了Java的SPI机制，比如：数据库加载驱动、日志接口、Dubbo的扩展实现等。

#### 三.SPI和API区别

说到SPI就不得不说API，从广义上来说它们都属于接口，而且很容易混淆，下面先用一张图说明一下：

![图片](assets/f9026589f56b.png)

一般模块之间都是通过接口进行通讯，我们会在服务调用方和服务提供者(实现方/被调用方)之间引入一个"接口"。当提供者提供了接口和实现，可以通过调用提供者的接口从而让调用方拥有提供者给我们提供的能力，这就是API。在API中，接口和实现都是放在提供者的。在SPI中，接口是放在调用方这边，而实现是放在提供者这边。

由接口调用方确定接口规则，然后由不同的厂商去根据这个规则对这个接口进行实现，从而提供服务，这就是SPI。举个例子：公司H是一家科技公司，新设计了一款芯片，然后现在需要量产了，而市面上有好几家芯片制造业公司，这时只要H公司指定好了这芯片接口的标准，那么这些合作的芯片公司(服务提供者)就按照标准交付自家特色的芯片。

区别总结：

API(Application Programming Interface)在大多数情况下，都是实现方制定接口并完成对接口的实现，调用方仅仅依赖接口调用且无权选择不同实现，从使用人员上来说，API直接被应用开发人员使用。

SPI(Service Provider Interface)是调用方来制定接口规范，提供给外部来实现，调用方在调用时则选择自己需要的外部实现，从使用人员上来说，SPI被框架扩展人员使用。

### (2)SPI使用演示

Spring框架提供的日志服务SLF4J其实只是一个日志门面(接口)，但是SLF4J的具体实现可以有几种。比如Logback、Log4j、Log4j2等等，而且还可以切换，在切换日志具体实现的时候我们是不需要更改项目代码的。只需要在Maven依赖里面修改一些pom依赖就好了，这就是依赖SPI机制实现的。

![图片](assets/7c5b1c2f1fb3.png)

接下来就实现一个简易版本的日志框架：

#### 一.Service Provider Interface项目

新建一个Java项目service-provider-interface目录结构如下：

```css
├─.idea
└─src
    ├─META-INF
    └─org
        └─spi
            └─service
                ├─Logger.java
                ├─LoggerService.java
                ├─Main.java
                └─MyServicesLoader.java
```

新建Logger接口，这个就是SPI，服务提供者接口，后面的服务提供者就要针对这个接口进行实现。

```java
package org.spi.service;

public interface Logger {
    void info(String msg);
    void debug(String msg);
}
```

接下来新建LoggerService类，这个主要是为服务调用方提供特定功能。

```java
package org.spi.service;

import java.util.ArrayList;
import java.util.List;
import java.util.ServiceLoader;

public class LoggerService {
    private static final LoggerService SERVICE = new LoggerService();
    private final Logger logger;
    private final List<Logger> loggerList;

    private LoggerService() {
        ServiceLoader<Logger> loader = ServiceLoader.load(Logger.class);
        List<Logger> list = new ArrayList<>();
        for (Logger log : loader) {
            list.add(log);
        }

        // LoggerList是所有ServiceProvider
        loggerList = list;
        if (!list.isEmpty()) {
            // 但Logger只取一个即可
            logger = list.get(0);
        } else {
            logger = null;
        }
    }

    public static LoggerService getService() {
        return SERVICE;
    }

    public void info(String msg) {
        if (logger == null) {
            System.out.println("info中没有发现Logger服务提供者");
        } else {
            logger.info(msg);
        }
    }

    public void debug(String msg) {
        if (loggerList.isEmpty()) {
            System.out.println("debug中没有发现Logger服务提供者");
        }
        loggerList.forEach(log -> log.debug(msg));
    }
}
```

新建Main类(服务调用方)，启动程序查看结果。

```typescript
package org.spi.service;

public class Main {
    public static void main(String[] args) {
        LoggerService service = LoggerService.getService();
        service.info("Hello SPI");
        service.debug("Hello SPI");
    }
}

// 启动程序输出的结果如下：
info中没有发现Logger服务提供者
debug中没有发现Logger服务提供者
```

接着将整个service-provider-interface直接打包成jar包，可以直接通过IDEA将项目打包成一个jar包。

![图片](assets/e714bd44c784.png)

![图片](assets/a753a1b62b43.png)

![图片](assets/675d8c74ab0b.png)

![图片](assets/d9f4b86dbaba.png)

![图片](assets/04b525cbe1bc.png)

![图片](assets/568359929434.png)

![图片](assets/257918a73a7b.png)

![图片](assets/e525a8c36304.png)

#### 二.Service Provider项目

接下来新建一个项目用来实现Logger接口，新建项目service-provider目录结构如下：

```cs
├─.idea
├─lib
│   └─service-provider-interface.jar
└─src
    ├─META-INF
    │   └─services
    │       └─org.spi.service.Logger
    └─org
        └─spi
            └─provider
                 └─Logback.java
```

新建Logback类：

```typescript
package org.spi.provider;
import org.spi.service.Logger;

public class Logback implements Logger {
    @Override
    public void info(String msg) {
        System.out.println("Logback info 的输出：" + msg);
    }

    @Override
    public void debug(String msg) {
        System.out.println("Logback debug 的输出：" + msg);
    }
}
```

将service-provider-interface的jar导入项目中，新建lib目录，然后将jar包拷贝过来，再添加到项目中。

![图片](assets/4bf7029ab638.png)

![图片](assets/5038cdd28b85.png)

再点击OK：

![图片](assets/f2cbe1be9751.png)

接下来就可以在项目中导入jar包里面的一些类和方法了，就像JDK工具类导包一样。

实现Logger接口后，在src目录下新建META-INF/services文件夹，然后新建文件org.spi.service.Logger(SPI的全类名)，文件里面的内容是"org.spi.provider.Logback"，也就是Logback的全类名，即SPI的实现类的包名 + 类名。这是JDK SPI机制ServiceLoader约定好的标准。

接下来同样将service-provider项目打包成jar包，这个jar包就是服务提供方的实现。通常我们导入maven的pom依赖就有点类似这种，只不过我们现在没有将这个jar包发布到maven公共仓库中，所以在需要使用的地方只能手动的添加到项目中。

#### 三.效果展示

接下来再回到service-provider-interface项目，导入service-provider jar包，重新运行Main方法，运行结果如下，这说明导入jar包中的实现类生效了。

```nginx
Logback info 的输出：Hello SPI
Logback debug 的输出：Hello SPI
```

通过使用SPI机制，可以看出服务(LoggerService)和服务提供者两者之间的耦合度非常低，如果需要替换一种实现(将Logback换成另外一种实现)，只需要换一个jar包即可，而这就是SLF4J的原理。

如果某一天需求变更了，此时需要将日志输出到消息队列，或者做一些别的操作，这个时候完全不需要更改Logback的实现，只需要新增一个服务实现(service-provider)，可以通过在本项目里面新增实现也可以从外部引入新的服务实现jar包，我们可以在服务(LoggerService)中选择一个具体的服务实现(service-provider)来完成需要的操作。

注意：ServiceLoader在加载具体的服务实现时会去扫描所有包下src目录的META-INF/services的内容，然后通过反射去生成对应的对象，保存在一个list列表里面，所以可以通过迭代或者遍历的方式得到需要的那个服务实现。

### (3)ServiceLoader分析

想要使用Java的SPI机制是需要依赖ServiceLoader来实现的，下面通过一个简化的示例演示JDK SPI的基本使用方式：

首先需要创建一个Log接口，来模拟日志打印的功能：

```cs
public interface Log {
    void log(String info);
}
```

接下来提供两个实现—Logback和Log4j，分别代表两个不同日志框架的实现，如下所示：

```typescript
public class Logback implements Log {
    @Override
    public void log(String info) {
    	System.out.println("Logback:" + info);
    }
}

public class Log4j implements Log {
    @Override
    public void log(String info) {
    	System.out.println("Log4j:" + info);
    }
}
```

在项目的resources/META-INF/services目录下添加一个名为 com.xxx.Log的文件。这是JDK SPI需要读取的配置文件，具体内容如下：

```
com.xxx.impl.Log4j
com.xxx.impl.Logback
```

最后创建main()方法，其中会加载上述配置文件，创建全部Log接口实现的实例并执行其log()方法，如下所示：

```cpp
public class Main {
    public static void main(String[] args) {
        ServiceLoader<Log> serviceLoader = ServiceLoader.load(Log.class);
        Iterator<Log> iterator = serviceLoader.iterator();
        while (iterator.hasNext()) {
            Log log = iterator.next();
            log.log("JDK SPI");
        }
    }
}
// 输出如下:
// Log4j:JDK SPI
// Logback:JDK SPI
```

ServiceLoader源码分析：

首先，ServiceLoader整个流程如下：

```perl
步骤一：ServiceLoader.load(Class service)
步骤二：获取当前线程的ContextClassLoader调用重载load方法
步骤三：创建ServiceLoader对象返回
步骤四：创建LazyIterator用于扫描SPI配置文件(只有调用LazyIterator迭代器的next方法才会去反射创建实现类对象)
步骤五：获取ServiceLoader迭代器并遍历
步骤六：反射创建接口实现类对象
```

然后，ServiceLoader是JDK提供的一个工具类，位于"package java.util;"包下。它是一个final类型的，所以不可被继承修改，同时它实现了Iterable接口。之所以实现了迭代器，是为了方便后续我们能够通过迭代的方式得到对应的服务实现。

```cs
public final class ServiceLoader<S> implements Iterable<S>{
    ...
}
```

它有的常量定义如下：

```java
//配置文件所在目录
private static final String PREFIX = "META-INF/services/";

//创建ServiceLoader时获得的访问控制上下文
private final AccessControlContext acc;

//缓存的提供者，按实例化顺序排序
private LinkedHashMap<String,S> providers = new LinkedHashMap<>();

//惰性查找迭代器，用于扫描SPI配置文件(包括所有引用的jar中的)
//只有调用迭代器的next方法时才会去反射创建实现类对象
private LazyIterator lookupIterator;
```

下面是load方法，可以发现load方法支持两种重载后的入参：

```cs
//SPI入口方法
public static <S> ServiceLoader<S> load(Class<S> service) {
    //上下文类加载器
    ClassLoader cl = Thread.currentThread().getContextClassLoader();

    //调用重载方法
    return ServiceLoader.load(service, cl);
}

public static <S> ServiceLoader<S> load(Class<S> service, ClassLoader loader) {
    //创建ServiceLoader对象，核心在构造方法
    return new ServiceLoader<>(service, loader);
}

private ServiceLoader(Class<S> svc, ClassLoader cl) {
    service = Objects.requireNonNull(svc, "Service interface cannot be null");

    //ClassLoader如果为空就用系统类加载器
    loader = (cl == null) ? ClassLoader.getSystemClassLoader() : cl;

    //获取访问控制上下文对象
    acc = (System.getSecurityManager() != null) ? AccessController.getContext() : null;

    //reload实例
    reload();
}

public void reload() {
    //先清空缓存的，第一次访问本身就为空
    providers.clear();

    //创建惰性加载迭代器
    lookupIterator = new LazyIterator(service, loader);

    //到此实际上ServiceLoader.load()方法就已经执行完了
}
```

根据代码的调用顺序，在reload()方法中是通过一个内部类LazyIterator实现的。ServiceLoader实现了Iterable接口的方法后，具有了迭代的能力。在这个iterator方法被调用时，首先会在ServiceLoader的Provider缓存中进行查找，如果没命中则在LazyIterator中进行查找。

```typescript
public Iterator<S> iterator() {
    return new Iterator<S>() {
        Iterator<Map.Entry<String, S>> knownProviders = providers.entrySet().iterator();

        public boolean hasNext() {
            if (knownProviders.hasNext())
                return true;
            return lookupIterator.hasNext(); // 调用 LazyIterator
        }

        public S next() {
            if (knownProviders.hasNext())
                return knownProviders.next().getValue();
            return lookupIterator.next(); // 调用 LazyIterator
        }

        public void remove() {
            throw new UnsupportedOperationException();
        }
    };
}
```

在调用LazyIterator时，具体实现如下：

```typescript
//内部类-惰性加载迭代器
private class LazyIterator implements Iterator<S> {
    Class<S> service;//接口对象
    ClassLoader loader;//类加载器
    Enumeration<URL> configs = null;//将配置文件信息封装为URL对象的迭代器，是一个CompoundEnumeration对象
    Iterator<String> pending = null;//循环解析配置文件的迭代器，辅助遍历configs/CompoundEnumeration
    String nextName = null;//下一个待遍历元素的名称

    private LazyIterator(Class<S> service, ClassLoader loader) {
        this.service = service;
        this.loader = loader;
    }

    public boolean hasNext() {
        if (acc == null) {
            return hasNextService();
        } else {
            PrivilegedAction<Boolean> action = new PrivilegedAction<Boolean>() {
                public Boolean run() {
                    return hasNextService();
                }
            };
            return AccessController.doPrivileged(action, acc);
        }
    }

    //迭代去判断是否还有元素
    private boolean hasNextService() {
        if (nextName != null) {
            return true;
        }

        //第一次访问configs为空
        if (configs == null) {
            try {
                //通过PREFIX(META-INF/services/)和类名获取对应的配置文件，得到具体的实现类
                String fullName = PREFIX + service.getName();
                if (loader == null)
                    configs = ClassLoader.getSystemResources(fullName);
                else
                    //类加载不为空，通过ClassLoader将配置文件信息封装为CompoundEnumeration<URL>枚举
                    configs = loader.getResources(fullName);
            } catch (IOException x) {
                fail(service, "Error locating configuration files", x);
            }
        }

        //通过pending对象遍历configs
        while ((pending == null) || !pending.hasNext()) {
            if (!configs.hasMoreElements()) {
                return false;
            }
            //将配置文件信息解析到pending
            pending = parse(service, configs.nextElement());
        }

        //拿出下一个元素
        nextName = pending.next();
        return true;
    }

    public S next() {
        if (acc == null) {
            return nextService();
        } else {
            PrivilegedAction<S> action = new PrivilegedAction<S>() {
                public S run() {
                    return nextService();
                }
            };
            return AccessController.doPrivileged(action, acc);
        }
    }

    //遍历获取实现类
    private S nextService() {
        if (!hasNextService())
            throw new NoSuchElementException();
        String cn = nextName;
        nextName = null;
        Class<?> c = null;
        try {
            //获取类对象
            c = Class.forName(cn, false, loader);
        } catch (ClassNotFoundException x) {
            fail(service, "Provider " + cn + " not found");
        }

        //不是接口对象的子对象就失败
        if (!service.isAssignableFrom(c)) {
            fail(service, "Provider " + cn + " not a subtype");
        }

        try {
            //反射创建类对象
            S p = service.cast(c.newInstance());
            //缓存实例对象->reload会清空
            providers.put(cn, p);
            //返回实例对象
            return p;
        } catch (Throwable x) {
            fail(service, "Provider " + cn + " could not be instantiated", x);
        }
        throw new Error();// This cannot happen
    }
    ...
}
```

所以最终使用迭代器next()方法，便会返回实现类对象：

```cpp
public class Main {
    public static void main(String[] args) {
        ServiceLoader<Log> serviceLoader = ServiceLoader.load(Log.class);
        Iterator<Log> iterator = serviceLoader.iterator();

        while (iterator.hasNext()) {
            Log log = iterator.next();
            log.log("JDK SPI");
        }
    }
}
// 输出如下:
// Log4j:JDK SPI
// Logback:JDK SPI
```

### (4)总结

其实不难发现，SPI机制的具体实现本质上还是通过反射完成的，即我们按照规定将要暴露对外使用的具体实现类在META-INF/services/文件下声明。

Java SPI核心总结：

#### 一.需要一个目录

```bash
META-INF/services
放到Classpath下面
```

#### 二.目录下面放置一个配置文件

```
文件名是要扩展的接口全名
文件内部是要实现的接口实现类
```

#### 三.如何进行使用

```python
ServiceLoader.load(xxx.class)
ServiceLoader<Log> serviceLoader = ServiceLoader.load(Log.class)
serviceLoader.iterator().next()
```

其实SPI机制在很多框架中都有应用：Spring框架的基本原理也是类似的反射，还有Dubbo框架提供同样的SPI扩展机制。通过SPI机制能够大大地提高接口设计的灵活性，但是SPI机制也存在一些缺点，比如：

```
缺点一：只能遍历所有的实现类，并全部实例化；
缺点二：配置文件中只简单列出所有的扩展实现，而没有给他们命名，导致在程序中很难去准确的引用它们；
缺点三：扩展如果依赖其他的扩展，做不到自动注入和装配；
缺点四：扩展很难和其他的框架集成，比如扩展里面依赖了一个Spring Bean，原生的Java SPI不支持；
缺点五：当多个ServiceLoader同时load时，会有并发问题；
```
