# Seata源码—8.Seata Saga模式的事务处理

> **公众号**: 东阳马生架构  
> **发布时间**: 2025-05-23 00:10  

**大纲(26818字)**

- 1.Seata Saga案例简介
- 2.Seata Saga案例的状态机定义分析
- 3.Seata Saga分布式事务与状态机关系
- 4.Seata Saga案例的Dubbo服务调用配置分析
- 5.Seata Saga案例的状态机数据库和工程启动
- 6.基于数据库的状态机配置实例的初始化
- 7.状态机配置实例中包含的一些关键组件
- 8.默认的状态机配置类的初始化
- 9.状态机定义的仓储组件解析状态机定义文件
- 10.状态机定义的仓储组件注册StateMachine
- 11.状态机引擎接口的源码
- 12.状态机引擎创建状态机实例的源码
- 13.ProcessContextBuilder构建流程上下文
- 14.StateLogStore记录日志和开启Saga全局事务
- 15.状态操作组件获取状态和State状态类继承体系
- 16.启动状态机实例时发布流程上下文到事件总线
- 17.通过业务处理器处理状态机当前需要执行的状态
- 18.通过服务调用组件来执行State指定的服务方法
- 19.将业务处理器路由到状态机下一个要执行的状态


## 1.Seata Saga案例简介

seata-samples项目下的saga模块，会基于Seata Saga模式，实现了分布式事务的提交和回滚。

在dubbo-saga-sample模块中，一个分布式事务内会有两个Saga事务参与者，这两个Saga事务参与者分别是InventoryAction和BalanceAction。当分布式事务提交时，两者均提交。当分布式事务回滚时，两者均回滚。

这两个Saga事务参与者均是Dubbo服务。这两个Saga事务参与者都有一个reduce方法表示库存扣减或余额扣减，还有一个compensateReduce方法表示补偿扣减操作。

InventoryAction接口定义如下：

```java
public interface InventoryAction {
    boolean reduce(String businessKey, int count);
    boolean compensateReduce(String businessKey);
}
```

BalanceAction接口定义如下：

```typescript
public interface BalanceAction {
    boolean reduce(String businessKey, BigDecimal amount, Map<String, Object> params);
    boolean compensateReduce(String businessKey, Map<String, Object> params);
}
```

运行dubbo-saga-sample模块的Demo工程：

步骤一：启动Seata Server

步骤二：运行DubboSagaProviderStarter

步骤三：运行DubboSagaTransactionStarter

## 2.Seata Saga案例的状态机定义分析

### (1)Saga状态机定义文件详情

### (2)状态机定义的全流程输入输出和流转分析

### (1)Saga状态机定义文件详情

Saga的本质就是一个状态机。

reduce_inventory_and_balance.json

```powershell
{
    "Name": "reduceInventoryAndBalance",
    "Comment": "reduce inventory then reduce balance in a transaction",
    "StartState": "ReduceInventory",
    "Version": "0.0.1",
    "States": {
        "ReduceInventory": {
            "Type": "ServiceTask",
            "ServiceName": "inventoryAction",
            "ServiceMethod": "reduce",
            "CompensateState": "CompensateReduceInventory",
            "Next": "ChoiceState",
            "Input": [
                "$.[businessKey]",
                "$.[count]"
            ],
            "Output": {
                "reduceInventoryResult": "$.#root"
            },
            "Status": {
                "#root == true": "SU",
                "#root == false": "FA",
                "$Exception{java.lang.Throwable}": "UN"
            }
        },
        "ChoiceState": {
            "Type": "Choice",
            "Choices": [{
                "Expression": "[reduceInventoryResult] == true",
                "Next": "ReduceBalance"
            }],
            "Default": "Fail"
        },
        "ReduceBalance": {
            "Type": "ServiceTask",
            "ServiceName": "balanceAction",
            "ServiceMethod": "reduce",
            "CompensateState": "CompensateReduceBalance",
            "Input": [
                "$.[businessKey]",
                "$.[amount]",
                {
                    "throwException": "$.[mockReduceBalanceFail]"
                }
            ],
            "Output": {
                "compensateReduceBalanceResult": "$.#root"
            },
            "Status": {
                "#root == true": "SU",
                "#root == false": "FA",
                "$Exception{java.lang.Throwable}": "UN"
            },
            "Catch": [{
                "Exceptions": [
                    "java.lang.Throwable"
                ],
                "Next": "CompensationTrigger"
            }],
            "Next": "Succeed"
        },
        "CompensateReduceInventory": {
            "Type": "ServiceTask",
            "ServiceName": "inventoryAction",
            "ServiceMethod": "compensateReduce",
            "Input": [
                "$.[businessKey]"
            ]
        },
        "CompensateReduceBalance": {
            "Type": "ServiceTask",
            "ServiceName": "balanceAction",
            "ServiceMethod": "compensateReduce",
            "Input": [
                "$.[businessKey]"
            ]
        },
        "CompensationTrigger": {
            "Type": "CompensationTrigger",
            "Next": "Fail"
        },
        "Succeed": {
            "Type": "Succeed"
        },
        "Fail": {
            "Type": "Fail",
            "ErrorCode": "PURCHASE_FAILED",
            "Message": "purchase failed"
        }
    }
}
```

### (2)状态机定义的全流程输入输出和流转分析

![图片](assets/ddd597924445.png)

![图片](assets/c381b80eb644.png)

## 3.Seata Saga分布式事务与状态机关系

Seata Saga分布式事务基本都是通过状态机一起配合起来使用的，通过状态机来调度编排每一个分布式事务的执行。编排的每一个服务执行时，可能会执行本地事务，也可能会调用远程服务。触发每一个服务的补偿时，可能会回滚本地事务，也可能会补偿远程服务。

![图片](assets/62c77c5ce095.png)

## 4.Seata Saga案例的Dubbo服务调用配置分析

### (1)Dubbo服务提供者的配置

### (2)Dubbo服务调用者的配置

### (3)Seata Saga状态机的Bean的配置

### (1)Dubbo服务提供者的配置

seata-dubbo-provider.xml

```xml
<beans xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
       xmlns:dubbo="http://code.alibabatech.com/schema/dubbo"
       xmlns="http://www.springframework.org/schema/beans"
       xsi:schemaLocation="http://www.springframework.org/schema/beans http://www.springframework.org/schema/beans/spring-beans.xsd
       http://code.alibabatech.com/schema/dubbo
       http://code.alibabatech.com/schema/dubbo/dubbo.xsd" default-autowire="byName">

    <dubbo:application name="saga-sample">
        <dubbo:parameter key="qos.enable" value="true"/>
        <dubbo:parameter key="qos.accept.foreign.ip" value="false"/>
        <dubbo:parameter key="qos.port" value="33333"/>
    </dubbo:application>

    <dubbo:registry address="zookeeper://127.0.0.1:2181"/>
    <dubbo:protocol name="dubbo" port="-1"/>
    <dubbo:provider timeout="10000" threads="10" threadpool="fixed" loadbalance="roundrobin"/>

    <dubbo:service ref="inventoryActionImpl" interface="io.seata.samples.saga.action.InventoryAction"/>
    <dubbo:service ref="balanceActionImpl" interface="io.seata.samples.saga.action.BalanceAction"/>

    <bean id="inventoryActionImpl" class="io.seata.samples.saga.action.impl.InventoryActionImpl"/>
    <bean id="balanceActionImpl" class="io.seata.samples.saga.action.impl.BalanceActionImpl"/>
</beans>
```

![图片](assets/ff122395af7d.png)

### (2)Dubbo服务调用者的配置

seata-dubbo-reference.xml

```xml
<beans xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
       xmlns:dubbo="http://code.alibabatech.com/schema/dubbo"
       xmlns="http://www.springframework.org/schema/beans"
       xsi:schemaLocation="http://www.springframework.org/schema/beans http://www.springframework.org/schema/beans/spring-beans.xsd
       http://code.alibabatech.com/schema/dubbo
       http://code.alibabatech.com/schema/dubbo/dubbo.xsd" default-autowire="byName">

    <dubbo:application name="saga-sample-reference">
        <dubbo:parameter key="qos.enable" value="true"/>
        <dubbo:parameter key="qos.accept.foreign.ip" value="false"/>
        <dubbo:parameter key="qos.port" value="22222"/>
    </dubbo:application>

    <dubbo:registry address="zookeeper://127.0.0.1:2181"/>
    <dubbo:protocol name="dubbo" port="-1"/>

    <dubbo:reference id="inventoryAction" interface="io.seata.samples.saga.action.InventoryAction" check="false" lazy="true"/>
    <dubbo:reference id="balanceAction" interface="io.seata.samples.saga.action.BalanceAction" check="false" lazy="true"/>
</beans>
```

![图片](assets/b033fc75fa10.png)

### (3)Seata Saga状态机的Bean的配置

seata-saga.xml

```xml
<beans xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
       xmlns:jdbc="http://www.springframework.org/schema/jdbc"
       xmlns="http://www.springframework.org/schema/beans"
       xsi:schemaLocation="http://www.springframework.org/schema/beans http://www.springframework.org/schema/beans/spring-beans.xsd
       http://www.springframework.org/schema/jdbc http://www.springframework.org/schema/jdbc/spring-jdbc.xsd"
       default-autowire="byName">

    <bean id="dataSource" class="org.h2.jdbcx.JdbcConnectionPool" destroy-method="dispose">
        <constructor-arg>
            <bean class="org.h2.jdbcx.JdbcDataSource">
                <property name="URL" value="jdbc:h2:mem:seata_saga"/>
                <property name="user" value="sa"/>
                <property name="password" value="sa"/>
            </bean>
        </constructor-arg>
    </bean>

    <jdbc:initialize-database data-source="dataSource">
        <jdbc:script location="classpath:sql/h2_init.sql"/>
    </jdbc:initialize-database>

    <bean id="stateMachineEngine" class="io.seata.saga.engine.impl.ProcessCtrlStateMachineEngine">
        <property name="stateMachineConfig" ref="dbStateMachineConfig"></property>
    </bean>

    <!-- DB是用来保存流程定义去启动状态机的流程实例、记录状态机运行时各个节点的情况 -->
    <bean id="dbStateMachineConfig" class="io.seata.saga.engine.config.DbStateMachineConfig">
        <property name="dataSource" ref="dataSource"></property>
        <property name="resources" value="statelang/*.json"></property>
        <property name="enableAsync" value="true"></property>
        <property name="threadPoolExecutor" ref="threadExecutor"></property>
        <property name="applicationId" value="saga_sample"></property>
        <property name="txServiceGroup" value="my_test_tx_group"></property>
    </bean>

    <bean id="threadExecutor" class="org.springframework.scheduling.concurrent.ThreadPoolExecutorFactoryBean">
        <property name="threadNamePrefix" value="SAGA_ASYNC_EXE_"/>
        <property name="corePoolSize" value="1"/>
        <property name="maxPoolSize" value="20"/>
    </bean>

    <bean class="io.seata.saga.rm.StateMachineEngineHolder">
        <property name="stateMachineEngine" ref="stateMachineEngine"/>
    </bean>
</beans>
```

![图片](assets/2b364c1f9b19.png)

## 5.Seata Saga案例的状态机数据库和工程启动

### (1)状态机相关的数据库表

### (2)Seata Saga案例的工程启动

### (1)状态机相关的数据库表

状态机定义 -> 状态机实例 -> 状态实例

```sql
-- PUBLIC.SEATA_STATE_INST definition
-- 状态实例，每个状态机实例里会有多个状态实例
CREATE CACHED TABLE "PUBLIC"."SEATA_STATE_INST"(
    "ID" VARCHAR NOT NULL COMMENT 'id',
    "MACHINE_INST_ID" VARCHAR NOT NULL COMMENT 'state machine instance id，机器实例ID',
    "NAME" VARCHAR NOT NULL COMMENT 'state name',
    "TYPE" VARCHAR COMMENT 'state type',
    "SERVICE_NAME" VARCHAR COMMENT 'service name',
    "SERVICE_METHOD" VARCHAR COMMENT 'method name',
    "SERVICE_TYPE" VARCHAR COMMENT 'service type',
    "BUSINESS_KEY" VARCHAR COMMENT 'business key',
    "STATE_ID_COMPENSATED_FOR" VARCHAR COMMENT 'state compensated for',
    "STATE_ID_RETRIED_FOR" VARCHAR COMMENT 'state retried for',
    "GMT_STARTED" TIMESTAMP NOT NULL COMMENT 'start time',
    "IS_FOR_UPDATE" TINYINT COMMENT 'is service for update',
    "INPUT_PARAMS" CLOB COMMENT 'input parameters',
    "OUTPUT_PARAMS" CLOB COMMENT 'output parameters',
    "STATUS" VARCHAR NOT NULL COMMENT 'status(SU succeed|FA failed|UN unknown|SK skipped|RU running)',
    "EXCEP" BLOB COMMENT 'exception',
    "GMT_UPDATED" TIMESTAMP COMMENT 'update time',
    "GMT_END" TIMESTAMP COMMENT 'end time'
);

-- PUBLIC.SEATA_STATE_MACHINE_DEF definition
-- 状态机定义，在json文件中定义好的状态流程会存放到这里
CREATE CACHED TABLE "PUBLIC"."SEATA_STATE_MACHINE_DEF"(
    "ID" VARCHAR NOT NULL COMMENT 'id',
    "NAME" VARCHAR NOT NULL COMMENT 'name',
    "TENANT_ID" VARCHAR NOT NULL COMMENT 'tenant id',
    "APP_NAME" VARCHAR NOT NULL COMMENT 'application name',
    "TYPE" VARCHAR COMMENT 'state language type',
    "COMMENT_" VARCHAR COMMENT 'comment',
    "VER" VARCHAR NOT NULL COMMENT 'version',
    "GMT_CREATE" TIMESTAMP NOT NULL COMMENT 'create time',
    "STATUS" VARCHAR NOT NULL COMMENT 'status(AC:active|IN:inactive)',
    "CONTENT" CLOB COMMENT 'content',
    "RECOVER_STRATEGY" VARCHAR COMMENT 'transaction recover strategy(compensate|retry)'
);

-- PUBLIC.SEATA_STATE_MACHINE_INST definition
-- 状态机实例，每执行一次完整的分布式事务就会对应一个状态机实例，每个状态机实例里会有多个状态实例
CREATE CACHED TABLE "PUBLIC"."SEATA_STATE_MACHINE_INST"(
    "ID" VARCHAR NOT NULL COMMENT 'id',
    "MACHINE_ID" VARCHAR NOT NULL COMMENT 'state machine definition id',
    "TENANT_ID" VARCHAR NOT NULL COMMENT 'tenant id',
    "PARENT_ID" VARCHAR COMMENT 'parent id',
    "GMT_STARTED" TIMESTAMP NOT NULL COMMENT 'start time',
    "BUSINESS_KEY" VARCHAR COMMENT 'business key',
    "START_PARAMS" CLOB COMMENT 'start parameters',
    "GMT_END" TIMESTAMP COMMENT 'end time',
    "EXCEP" BLOB COMMENT 'exception',
    "END_PARAMS" CLOB COMMENT 'end parameters',
    "STATUS" VARCHAR COMMENT 'status(SU succeed|FA failed|UN unknown|SK skipped|RU running)',
    "COMPENSATION_STATUS" VARCHAR COMMENT 'compensation status(SU succeed|FA failed|UN unknown|SK skipped|RU running)',
    "IS_RUNNING" TINYINT COMMENT 'is running(0 no|1 yes)',
    "GMT_UPDATED" TIMESTAMP NOT NULL
);
```

### (2)Seata Saga案例的工程启动

ApplicationKeeper启动完之后就会被阻塞住。

```java
public class ApplicationKeeper {
    private static final Logger LOGGER = LoggerFactory.getLogger(ApplicationKeeper.class);
    private final ReentrantLock LOCK = new ReentrantLock();
    private final Condition STOP = LOCK.newCondition();

    //Instantiates a new Application keeper.
    public ApplicationKeeper(AbstractApplicationContext applicationContext) {
        addShutdownHook(applicationContext);
    }

    private void addShutdownHook(final AbstractApplicationContext applicationContext) {
        Runtime.getRuntime().addShutdownHook(new Thread(new Runnable() {
            @Override
            public void run() {
                try {
                    applicationContext.close();
                    LOGGER.info("ApplicationContext " + applicationContext + " is closed.");
                } catch (Exception e) {
                    LOGGER.error("Failed to close ApplicationContext", e);
                }
                try {
                    LOCK.lock();
                    STOP.signal();
                } finally {
                    LOCK.unlock();
                }
            }
        }));
    }

    public void keep() {
        synchronized (LOCK) {
            try {
                LOGGER.info("Application is keep running ... ");
                LOCK.wait();
            } catch (InterruptedException e) {
                e.printStackTrace();
            }
        }
    }
}
```

步骤一：运行DubboSagaProviderStarter，启动Dubbo Provider。

```typescript
public class DubboSagaProviderStarter {
    private static TestingServer server;

    //The entry point of application.
    public static void main(String[] args) throws Exception {
        //mock zk server
        mockZKServer();
        ClassPathXmlApplicationContext applicationContext = new ClassPathXmlApplicationContext(
            new String[]{"spring/seata-dubbo-provider.xml"}
        );
        new ApplicationKeeper(applicationContext).keep();
    }

    private static void mockZKServer() throws Exception {
        //Mock zk server，作为Dubbo配置中心
        server = new TestingServer(2181, true);
        server.start();
    }
}

public class InventoryActionImpl implements InventoryAction {
    private static final Logger LOGGER = LoggerFactory.getLogger(InventoryActionImpl.class);

    @Override
    public boolean reduce(String businessKey, int count) {
        LOGGER.info("reduce inventory succeed, count: " + count + ", businessKey:" + businessKey);
        return true;
    }

    @Override
    public boolean compensateReduce(String businessKey) {
        LOGGER.info("compensate reduce inventory succeed, businessKey:" + businessKey);
        return true;
    }
}

public class BalanceActionImpl implements BalanceAction {
    private static final Logger LOGGER = LoggerFactory.getLogger(BalanceActionImpl.class);

    @Override
    public boolean reduce(String businessKey, BigDecimal amount, Map<String, Object> params) {
        if (params != null) {
            Object throwException = params.get("throwException");
            if (throwException != null && "true".equals(throwException.toString())) {
                throw new RuntimeException("reduce balance failed");
            }
        }
        LOGGER.info("reduce balance succeed, amount: " + amount + ", businessKey:" + businessKey);
        return true;
    }

    @Override
    public boolean compensateReduce(String businessKey, Map<String, Object> params) {
        if (params != null) {
            Object throwException = params.get("throwException");
            if (throwException != null && "true".equals(throwException.toString())) {
                throw new RuntimeException("compensate reduce balance failed");
            }
        }
        LOGGER.info("compensate reduce balance succeed, businessKey:" + businessKey);
        return true;
    }
}
```

步骤二：运行DubboSagaTransactionStarter，启动Demo工程。

```typescript
public class DubboSagaTransactionStarter {
    private static volatile Object lock = new Object();

    private static AsyncCallback CALL_BACK = new AsyncCallback() {
        @Override
        public void onFinished(ProcessContext context, StateMachineInstance stateMachineInstance) {
            synchronized (lock) {
                lock.notifyAll();
            }
        }

        @Override
        public void onError(ProcessContext context, StateMachineInstance stateMachineInstance, Exception exp) {
            synchronized (lock) {
                lock.notifyAll();
            }
        }
    };

    public static void main(String[] args) {
        AbstractApplicationContext applicationContext = new ClassPathXmlApplicationContext(
            new String[]{"spring/seata-saga.xml", "spring/seata-dubbo-reference.xml"}
        );

        StateMachineEngine stateMachineEngine = (StateMachineEngine) applicationContext.getBean("stateMachineEngine");
        transactionCommittedDemo(stateMachineEngine);
        transactionCompensatedDemo(stateMachineEngine);

        new ApplicationKeeper(applicationContext).keep();
    }

    private static void transactionCommittedDemo(StateMachineEngine stateMachineEngine) {
        //设置状态机上下文
        Map<String, Object> startParams = new HashMap<>(3);
        String businessKey = String.valueOf(System.currentTimeMillis());
        startParams.put("businessKey", businessKey);
        startParams.put("count", 10);
        startParams.put("amount", new BigDecimal("100"));

        //sync test，同步启动状态机
        StateMachineInstance inst = stateMachineEngine.startWithBusinessKey("reduceInventoryAndBalance", null, businessKey, startParams);
        Assert.isTrue(ExecutionStatus.SU.equals(inst.getStatus()), "saga transaction execute failed. XID: " + inst.getId());
        System.out.println("saga transaction commit succeed. XID: " + inst.getId());

        //async test，异步启动状态机
        businessKey = String.valueOf(System.currentTimeMillis());
        inst = stateMachineEngine.startWithBusinessKeyAsync("reduceInventoryAndBalance", null, businessKey, startParams, CALL_BACK);
        waittingForFinish(inst);

        Assert.isTrue(ExecutionStatus.SU.equals(inst.getStatus()), "saga transaction execute failed. XID: " + inst.getId());
        System.out.println("saga transaction commit succeed. XID: " + inst.getId());
    }

    private static void transactionCompensatedDemo(StateMachineEngine stateMachineEngine) {
        //设置状态机上下文
        Map<String, Object> startParams = new HashMap<>(4);
        String businessKey = String.valueOf(System.currentTimeMillis());
        startParams.put("businessKey", businessKey);
        startParams.put("count", 10);
        startParams.put("amount", new BigDecimal("100"));
        startParams.put("mockReduceBalanceFail", "true");

        //sync test，同步启动状态机
        StateMachineInstance inst = stateMachineEngine.startWithBusinessKey("reduceInventoryAndBalance", null, businessKey, startParams);

        //async test，异步启动状态机
        businessKey = String.valueOf(System.currentTimeMillis());
        inst = stateMachineEngine.startWithBusinessKeyAsync("reduceInventoryAndBalance", null, businessKey, startParams, CALL_BACK);
        waittingForFinish(inst);

        Assert.isTrue(ExecutionStatus.SU.equals(inst.getCompensationStatus()), "saga transaction compensate failed. XID: " + inst.getId());
        System.out.println("saga transaction compensate succeed. XID: " + inst.getId());
    }

    private static void waittingForFinish(StateMachineInstance inst) {
        synchronized (lock) {
            if (ExecutionStatus.RU.equals(inst.getStatus())) {
                try {
                    lock.wait();
                } catch (InterruptedException e) {
                    e.printStackTrace();
                }
            }
        }
    }
}
```

## 6.基于数据库的状态机配置实例的初始化

基于数据库的状态机配置实例DbStateMachineConfig会将状态机定义、状态机实例、状态实例放在数据库中。由seata-saga.xml配置文件可知，它会被注入到状态机引擎实例StateMachineEngine里。DbStateMachineConfig的初始化源码如下：

```java
//DbStateMachineConfig表示状态机定义、状态机实例、状态实例会放在DB中
public class DbStateMachineConfig extends DefaultStateMachineConfig implements DisposableBean {
    //会通过seata-saga.xml配置文件，注入一个数据库连接池进来，这个DB会用来存放状态机定义、状态机实例、状态实例
    private DataSource dataSource;
    //应用程序ID
    private String applicationId;
    //分布式事务服务的分组
    private String txServiceGroup;
    //DB里存放状态机数据的表的前缀
    private String tablePrefix = "seata_";
    //DB的类型，seata-samples里用的是h2，一般都用MySQL
    private String dbType;
    //Saga分布式事务模版
    private SagaTransactionalTemplate sagaTransactionalTemplate;
    //是否启用RM资源管理器上报成功的机制，默认是不启用的
    private boolean rmReportSuccessEnable = DEFAULT_CLIENT_REPORT_SUCCESS_ENABLE;
    //是否启用Saga分支事务的注册机制，默认是不启用的
    private boolean sagaBranchRegisterEnable = DEFAULT_CLIENT_SAGA_BRANCH_REGISTER_ENABLE;

    //初始化
    public DbStateMachineConfig() {
        try {
            Configuration configuration = ConfigurationFactory.getInstance();
            if (configuration != null) {
                this.rmReportSuccessEnable = configuration.getBoolean(ConfigurationKeys.CLIENT_REPORT_SUCCESS_ENABLE, DEFAULT_CLIENT_REPORT_SUCCESS_ENABLE);
                this.sagaBranchRegisterEnable = configuration.getBoolean(ConfigurationKeys.CLIENT_SAGA_BRANCH_REGISTER_ENABLE, DEFAULT_CLIENT_SAGA_BRANCH_REGISTER_ENABLE);
                //设置Saga状态机定义文件的解析器
                setSagaJsonParser(configuration.getConfig(ConfigurationKeys.CLIENT_SAGA_JSON_PARSER, DEFAULT_SAGA_JSON_PARSER));
                this.applicationId = configuration.getConfig(ConfigurationKeys.APPLICATION_ID);
                this.txServiceGroup = configuration.getConfig(ConfigurationKeys.TX_SERVICE_GROUP);
                //设置Saga重试持久化模式是否为更新模式
                setSagaRetryPersistModeUpdate(configuration.getBoolean(ConfigurationKeys.CLIENT_SAGA_RETRY_PERSIST_MODE_UPDATE, DEFAULT_CLIENT_SAGA_RETRY_PERSIST_MODE_UPDATE));
                //设置Saga补偿持久化模式是否为更新模式
                setSagaCompensatePersistModeUpdate(configuration.getBoolean(ConfigurationKeys.CLIENT_SAGA_COMPENSATE_PERSIST_MODE_UPDATE, DEFAULT_CLIENT_SAGA_COMPENSATE_PERSIST_MODE_UPDATE));
            }
        } catch (Exception e) {
            LOGGER.warn("Load SEATA configuration failed, use default configuration instead.", e);
        }
    }

    //根据数据库连接池获取DB类型
    public static String getDbTypeFromDataSource(DataSource dataSource) throws SQLException {
        try (Connection con = dataSource.getConnection()) {
            DatabaseMetaData metaData = con.getMetaData();
            return metaData.getDatabaseProductName();
        }
    }

    //初始化DB状态机配置DbStateMachineConfig
    //因为DbStateMachineConfig本身就是Spring Bean，当该Bean初始化完毕后，就会执行afterPropertiesSet()方法
    @Override
    public void afterPropertiesSet() throws Exception {
        //先根据数据库连接池获取DB类型
        dbType = getDbTypeFromDataSource(dataSource);
        //如果状态机实例日志和状态实例日志存储组件为null
        if (getStateLogStore() == null) {
            DbAndReportTcStateLogStore dbStateLogStore = new DbAndReportTcStateLogStore();
            dbStateLogStore.setDataSource(dataSource);
            dbStateLogStore.setTablePrefix(tablePrefix);
            dbStateLogStore.setDbType(dbType);
            dbStateLogStore.setDefaultTenantId(getDefaultTenantId());
            dbStateLogStore.setSeqGenerator(getSeqGenerator());

            if (StringUtils.hasLength(getSagaJsonParser())) {
                ParamsSerializer paramsSerializer = new ParamsSerializer();
                paramsSerializer.setJsonParserName(getSagaJsonParser());
                dbStateLogStore.setParamsSerializer(paramsSerializer);
            }

            if (sagaTransactionalTemplate == null) {
                DefaultSagaTransactionalTemplate defaultSagaTransactionalTemplate = new DefaultSagaTransactionalTemplate();
                defaultSagaTransactionalTemplate.setApplicationContext(getApplicationContext());
                defaultSagaTransactionalTemplate.setApplicationId(applicationId);
                defaultSagaTransactionalTemplate.setTxServiceGroup(txServiceGroup);
                defaultSagaTransactionalTemplate.afterPropertiesSet();
                sagaTransactionalTemplate = defaultSagaTransactionalTemplate;
            }

            dbStateLogStore.setSagaTransactionalTemplate(sagaTransactionalTemplate);
            setStateLogStore(dbStateLogStore);
        }

        if (getStateLangStore() == null) {
            DbStateLangStore dbStateLangStore = new DbStateLangStore();
            dbStateLangStore.setDataSource(dataSource);
            dbStateLangStore.setTablePrefix(tablePrefix);
            dbStateLangStore.setDbType(dbType);
            setStateLangStore(dbStateLangStore);
        }

        super.afterPropertiesSet();//must execute after StateLangStore initialized
    }

    @Override
    public void destroy() throws Exception {
        if ((sagaTransactionalTemplate != null) && (sagaTransactionalTemplate instanceof DisposableBean)) {
            ((DisposableBean) sagaTransactionalTemplate).destroy();
        }
    }
    ...
}

//Default state machine configuration
//默认的状态机配置，DB状态机配置DbStateMachineConfig是它的子类
//DefaultStateMachineConfig可以支持不同种类的状态机配置
//即状态机定义、状态机实例、状态实例，既可以放在DB里，也可以放在其他存储里，默认是放在DB里的

//DefaultStateMachineConfig会封装(注入)状态机运行时需要的所有组件
//StateMachineConfig可以获取到状态机需要的各种组件
//ApplicationContextAware可以感知Spring容器上下文
//InitializingBean可以对Spring Bean进行初始化
public class DefaultStateMachineConfig implements StateMachineConfig, ApplicationContextAware, InitializingBean {
    ...
    ...
}
```

![图片](assets/db23922349f7.png)

## 7.状态机配置实例中包含的一些关键组件

### (1)状态机配置组件

### (2)状态机实例和状态实例的仓储组件

### (3)状态机实例日志和状态实例日志的存储组件

### (4)状态机定义的存储组件

### (5)表达式工厂管理器

### (6)状态机定义的仓储组件

### (1)状态机配置组件

StateMachineConfig表示的是状态机配置组件，可以从中获取状态机需要的各种组件。

```cs
//StateMachineConfig
//状态机配置组件接口，可以获取到状态机需要的各种组件
public interface StateMachineConfig {
    //Gets state log store.
    //获取状态机实例和状态实例的仓储组件
    //StateLogRepository可以根据各种条件查询状态机实例和状态实例
    StateLogRepository getStateLogRepository();

    //Gets get state log store.
    //获取状态机实例日志和状态实例日志的存储组件
    //StateLogStore可以对状态机日志和状态日志进行读写、也可以根据各种条件查询状态机实例和状态实例
    StateLogStore getStateLogStore();

    //Gets get state language definition store.
    //获取状态机定义的存储组件
    StateLangStore getStateLangStore();

    //Gets get expression factory manager.
    //获取表达式工厂管理器
    ExpressionFactoryManager getExpressionFactoryManager();

    //Gets get evaluator factory manager.
    //获取表达式计算工厂管理器
    EvaluatorFactoryManager getEvaluatorFactoryManager();

    //Gets get charset.
    //获取字符集编码
    String getCharset();

    //Gets get default tenant id.
    //获取默认的租户ID
    String getDefaultTenantId();

    //Gets get state machine repository.
    //获取状态机定义的仓储组件
    StateMachineRepository getStateMachineRepository();

    //Gets get status decision strategy.
    //获取State执行结果的判定策略组件
    StatusDecisionStrategy getStatusDecisionStrategy();

    //Gets get seq generator.
    //获取序号生成器
    SeqGenerator getSeqGenerator();

    //Gets get process ctrl event publisher.
    //获取流程控制事件的发布器(同步发布)
    ProcessCtrlEventPublisher getProcessCtrlEventPublisher();

    //Gets get async process ctrl event publisher.
    //获取流程控制事件的发布器(异步发布)
    ProcessCtrlEventPublisher getAsyncProcessCtrlEventPublisher();

    //Gets get application context.
    //获取Spring容器上下文
    ApplicationContext getApplicationContext();

    //Gets get thread pool executor.
    //获取异步执行的线程池
    ThreadPoolExecutor getThreadPoolExecutor();

    //Is enable async boolean.
    //是否启用异步
    boolean isEnableAsync();

    //get ServiceInvokerManager
    //获取服务调用的管理器
    ServiceInvokerManager getServiceInvokerManager();

    //get trans operation timeout
    //获取事务操作的超时时间
    int getTransOperationTimeout();

    //get service invoke timeout
    //获取服务调用的超时时间
    int getServiceInvokeTimeout();

    //get ScriptEngineManager
    //获取脚本引擎管理器
    ScriptEngineManager getScriptEngineManager();
}
```

### (2)状态机实例和状态实例的仓储组件

StateLogRepository表示的是状态机实例和状态实例的仓储组件，可以根据不同的条件查询状态机实例和状态实例。

```typescript
//State Log Repository
//状态机实例和状态实例的仓储组件，可以根据各种条件查询状态机实例和状态实例
public interface StateLogRepository {
    //Get state machine instance
    //根据状态机实例ID，获取到具体的状态机实例
    StateMachineInstance getStateMachineInstance(String stateMachineInstanceId);

    //Get state machine instance by businessKey
    //根据业务key获取状态机实例
    StateMachineInstance getStateMachineInstanceByBusinessKey(String businessKey, String tenantId);

    //Query the list of state machine instances by parent id
    //根据父ID查询状态机实例
    List<StateMachineInstance> queryStateMachineInstanceByParentId(String parentId);

    //Get state instance
    //根据状态实例ID查询状态实例
    StateInstance getStateInstance(String stateInstanceId, String machineInstId);

    //Get a list of state instances by state machine instance id
    //根据状态机实例ID查询所有状态实例
    List<StateInstance> queryStateInstanceListByMachineInstanceId(String stateMachineInstanceId);
}
```

### (3)状态机实例日志和状态实例日志的存储组件接口

StateLogStore表示的是状态机实例日志和状态实例日志的存储组件，可以记录各种状态机实例日志和状态实例日志。

```cs
//StateMachine engine log store
//状态机实例日志和状态实例日志的存储组件
public interface StateLogStore {
    //Record state machine startup events
    //记录状态机实例的启动事件日志
    void recordStateMachineStarted(StateMachineInstance machineInstance, ProcessContext context);

    //Record status end event
    //记录状态机实例的完成事件日志
    void recordStateMachineFinished(StateMachineInstance machineInstance, ProcessContext context);

    //Record state machine restarted
    //记录状态机实例的重启事件日志
    void recordStateMachineRestarted(StateMachineInstance machineInstance, ProcessContext context);

    //Record state start execution event
    //记录状态实例的启动事件日志
    void recordStateStarted(StateInstance stateInstance, ProcessContext context);

    //Record state execution end event
    //记录状态实例的完成事件日志
    void recordStateFinished(StateInstance stateInstance, ProcessContext context);

    //Get state machine instance
    //根据状态机实例ID获取状态机实例
    StateMachineInstance getStateMachineInstance(String stateMachineInstanceId);

    //Get state machine instance by businessKey
    //根据业务key获取状态机实例
    StateMachineInstance getStateMachineInstanceByBusinessKey(String businessKey, String tenantId);

    //Query the list of state machine instances by parent id
    //根据父ID查询状态机实例
    List<StateMachineInstance> queryStateMachineInstanceByParentId(String parentId);

    //Get state instance
    //根据状态实例ID和状态机ID获取状态实例
    StateInstance getStateInstance(String stateInstanceId, String machineInstId);

    //Get a list of state instances by state machine instance id
    //根据状态机实例ID查询状态实例
    List<StateInstance> queryStateInstanceListByMachineInstanceId(String stateMachineInstanceId);
}
```

### (4)状态机定义的存储组件接口

StateLangStore表示的是状态机定义的存储组件，可以存储和获取不同的状态机定义。

```typescript
//State language definition store
//状态机定义的存储组件
public interface StateLangStore {
    //Query the state machine definition by id
    //根据状态机ID获取状态机定义
    StateMachine getStateMachineById(String stateMachineId);

    //Get the latest version of the state machine by state machine name
    //根据状态机名称和租户ID，可以获取最新版本的状态机定义
    StateMachine getLastVersionStateMachine(String stateMachineName, String tenantId);

    //Storage state machine definition
    //存储状态机定义
    boolean storeStateMachine(StateMachine stateMachine);
}
```

### (5)表达式工厂管理器

ExpressionFactoryManager表示的是表达式工厂管理器，可以根据不同的表达式类型获取不同的表达式工厂组件。

```typescript
//Expression factory manager
//表达式工厂管理器
public class ExpressionFactoryManager {
    public static final String DEFAULT_EXPRESSION_TYPE = "Default";
    //表达式类型 -> 表达式工厂
    private Map<String, ExpressionFactory> expressionFactoryMap = new ConcurrentHashMap<>();

    //根据不同的表达式类型，去获取不同的表达式工厂组件
    public ExpressionFactory getExpressionFactory(String expressionType) {
        if (StringUtils.isBlank(expressionType)) {
            expressionType = DEFAULT_EXPRESSION_TYPE;
        }
        return expressionFactoryMap.get(expressionType);
    }

    public void setExpressionFactoryMap(Map<String, ExpressionFactory> expressionFactoryMap) {
        this.expressionFactoryMap.putAll(expressionFactoryMap);
    }

    public void putExpressionFactory(String type, ExpressionFactory factory) {
        this.expressionFactoryMap.put(type, factory);
    }
}
```

### (6)状态机定义的仓储组件

StateMachineRepository表示的是状态机定义的仓储组件，可以注册和获取一个状态机定义。

```typescript
//StateMachineRepository
//状态机定义的仓储组件
public interface StateMachineRepository {
    //Gets get state machine by id.
    //根据状态机ID获取一个状态机定义StateMachine
    StateMachine getStateMachineById(String stateMachineId);

    //Gets get state machine.
    //根据状态机名字、租户ID获取一个状态机定义StateMachine
    StateMachine getStateMachine(String stateMachineName, String tenantId);

    //Gets get state machine.
    //根据状态机名字、租户ID、版本号获取一个状态机定义StateMachine
    StateMachine getStateMachine(String stateMachineName, String tenantId, String version);

    //Register the state machine to the repository (if the same version already exists, return the existing version)
    //向状态机定义的仓储组件注册一个状态机定义
    StateMachine registryStateMachine(StateMachine stateMachine);

    //registry by resources
    //向状态机定义的仓储组件注册资源
    void registryByResources(Resource[] resources, String tenantId) throws IOException;
}
```

## 8.默认的状态机配置类的初始化

DefaultStateMachineConfig是默认的状态机配置类，基于数据库的状态机配置组件DbStateMachineConfig是它的子类。它可以支持不同种类的状态机配置，也就是状态机定义、状态机实例、状态实例，既可以放在数据库里，也可以放在其他存储里，默认是放在数据库里的。

```java
//Default state machine configuration
//DefaultStateMachineConfig会封装(注入)状态机运行时需要的所有组件
//StateMachineConfig可以获取到状态机需要的各种组件
//ApplicationContextAware可以感知Spring容器上下文
//InitializingBean可以对Spring Bean进行初始化
public class DefaultStateMachineConfig implements StateMachineConfig, ApplicationContextAware, InitializingBean {
    private static final int DEFAULT_TRANS_OPER_TIMEOUT     = 60000 * 30;
    private static final int DEFAULT_SERVICE_INVOKE_TIMEOUT = 60000 * 5;

    //事务操作的超时时间，默认是30分钟
    private int transOperationTimeout = DEFAULT_TRANS_OPER_TIMEOUT;
    //服务调用的超时时间，默认是5分钟
    private int serviceInvokeTimeout  = DEFAULT_SERVICE_INVOKE_TIMEOUT;

    //状态机实例和状态实例的仓储组件
    private StateLogRepository stateLogRepository;
    //状态机实例日志和状态实例日志的存储组件
    private StateLogStore stateLogStore;
    //状态机定义的存储组件
    private StateLangStore stateLangStore;
    //表达式工厂管理器
    private ExpressionFactoryManager expressionFactoryManager;
    //表达式计算的工厂管理器
    private EvaluatorFactoryManager evaluatorFactoryManager;
    //状态机定义的仓储组件
    private StateMachineRepository stateMachineRepository;
    //State执行结果的判定策略组件
    private StatusDecisionStrategy statusDecisionStrategy;
    //序号生成器
    private SeqGenerator seqGenerator;

    //流程控制的事件发布器(同步发布)
    private ProcessCtrlEventPublisher syncProcessCtrlEventPublisher;
    //流程控制的事件发布器(异步发布)
    private ProcessCtrlEventPublisher asyncProcessCtrlEventPublisher;
    //Spring容器上下文
    private ApplicationContext applicationContext;
    //异步执行的线程池
    private ThreadPoolExecutor threadPoolExecutor;
    //是否启用异步执行，默认是false
    private boolean enableAsync = false;
    //服务调用的管理器
    private ServiceInvokerManager serviceInvokerManager;

    //是否自动注册资源(自动注册流程定义)，默认是true
    private boolean autoRegisterResources = true;
    //默认的状态机定义文件(json文件)
    private String[] resources = new String[]{"classpath*:seata/saga/statelang/**/*.json"};
    //字符集编码
    private String charset = "UTF-8";
    //默认租户ID
    private String defaultTenantId = "000001";
    //脚本引擎管理器
    private ScriptEngineManager scriptEngineManager;
    //状态机定义文件(json文件)解析器
    private String sagaJsonParser = DEFAULT_SAGA_JSON_PARSER;
    //是否更新Saga重试持久化的模式
    private boolean sagaRetryPersistModeUpdate = DEFAULT_CLIENT_SAGA_RETRY_PERSIST_MODE_UPDATE;
    //是否更新Saga补偿持久化的模式
    private boolean sagaCompensatePersistModeUpdate = DEFAULT_CLIENT_SAGA_COMPENSATE_PERSIST_MODE_UPDATE;

    //因为DefaultStateMachineConfig实现了InitializingBean接口
    //所以继承DefaultStateMachineConfig的Spring Bean初始化之后，就会回调afterPropertiesSet()方法
    @Override
    public void afterPropertiesSet() throws Exception {
        init();
    }

    //初始化方法
    protected void init() throws Exception {
        //创建表达式工厂管理器
        if (expressionFactoryManager == null) {
            //创建一个表达式工厂管理器
            expressionFactoryManager = new ExpressionFactoryManager();
            //创建一个Spring EL表达式工厂
            SpringELExpressionFactory springELExpressionFactory = new SpringELExpressionFactory();
            //注入(设置)Spring容器上下文到Spring EL表达式工厂中
            springELExpressionFactory.setApplicationContext(getApplicationContext());
            //将Spring EL表达式工厂放入表达式工厂管理器中
            expressionFactoryManager.putExpressionFactory(ExpressionFactoryManager.DEFAULT_EXPRESSION_TYPE, springELExpressionFactory);

            //创建一个序号表达式工厂
            SequenceExpressionFactory sequenceExpressionFactory = new SequenceExpressionFactory();
            //注入(设置)序号生成器到序号表达式工厂中
            sequenceExpressionFactory.setSeqGenerator(getSeqGenerator());
            //将序号表达式工厂放入表达式工厂管理器中
            expressionFactoryManager.putExpressionFactory(DomainConstants.EXPRESSION_TYPE_SEQUENCE, sequenceExpressionFactory);
        }

        //创建表达式计算工厂管理器
        if (evaluatorFactoryManager == null) {
            //创建一个表达式计算工厂管理器
            evaluatorFactoryManager = new EvaluatorFactoryManager();

            //创建一个表达式计算工厂，并将该表达式计算工厂放入表达式计算工厂管理器中
            ExpressionEvaluatorFactory expressionEvaluatorFactory = new ExpressionEvaluatorFactory();
            expressionEvaluatorFactory.setExpressionFactory(expressionFactoryManager.getExpressionFactory(ExpressionFactoryManager.DEFAULT_EXPRESSION_TYPE));
            evaluatorFactoryManager.putEvaluatorFactory(EvaluatorFactoryManager.EVALUATOR_TYPE_DEFAULT, expressionEvaluatorFactory);
            //创建一个异常匹配计算工厂，并将该异常匹配计算工厂放入表达式计算工厂管理器中
            evaluatorFactoryManager.putEvaluatorFactory(DomainConstants.EVALUATOR_TYPE_EXCEPTION, new ExceptionMatchEvaluatorFactory());
        }
        //创建状态机定义的仓储组件
        if (stateMachineRepository == null) {
            StateMachineRepositoryImpl stateMachineRepository = new StateMachineRepositoryImpl();
            stateMachineRepository.setCharset(charset);//设置字符集编码
            stateMachineRepository.setSeqGenerator(seqGenerator);//设置序号生成器
            stateMachineRepository.setStateLangStore(stateLangStore);//设置状态机定义的存储组件
            stateMachineRepository.setDefaultTenantId(defaultTenantId);//设置默认租户ID
            stateMachineRepository.setJsonParserName(sagaJsonParser);//设置状态机定义文件(json文件)解析器
            this.stateMachineRepository = stateMachineRepository;
        }

        //stateMachineRepository may be overridden, so move `stateMachineRepository.registryByResources()` here.
        //如果需要自动注册资源(比如数据库等)，则获取资源并进行注册
        if (autoRegisterResources && ArrayUtils.isNotEmpty(resources)) {
            try {
                //读取默认的状态机定义文件(json文件)，把这个状态机定义注册到状态机定义的仓储组件中
                Resource[] resources = ResourceUtil.getResources(this.resources);
                stateMachineRepository.registryByResources(resources, defaultTenantId);
            } catch (IOException e) {
                LOGGER.error("Load State Language Resources failed.", e);
            }
        }

        //创建状态机实例和状态实例的仓储组件
        if (stateLogRepository == null) {
            StateLogRepositoryImpl stateLogRepositoryImpl = new StateLogRepositoryImpl();
            stateLogRepositoryImpl.setStateLogStore(stateLogStore);
            this.stateLogRepository = stateLogRepositoryImpl;
        }

        //创建State执行结果的判定策略组件
        if (statusDecisionStrategy == null) {
            statusDecisionStrategy = new DefaultStatusDecisionStrategy();
        }
        //创建流程控制的事件发布器(同步发布)
        if (syncProcessCtrlEventPublisher == null) {
            //创建流程控制的事件发布器
            ProcessCtrlEventPublisher syncEventPublisher = new ProcessCtrlEventPublisher();

            //创建流程控制器
            ProcessControllerImpl processorController = createProcessorController(syncEventPublisher);

            //创建流程控制事件的消费者
            ProcessCtrlEventConsumer processCtrlEventConsumer = new ProcessCtrlEventConsumer();
            processCtrlEventConsumer.setProcessController(processorController);

            //创建事件总线
            DirectEventBus directEventBus = new DirectEventBus();
            syncEventPublisher.setEventBus(directEventBus);
            directEventBus.registerEventConsumer(processCtrlEventConsumer);
            syncProcessCtrlEventPublisher = syncEventPublisher;
        }

        //如果启用了异步化执行 且 流程控制的事件发布器(异步发布)为null
        if (enableAsync && asyncProcessCtrlEventPublisher == null) {
            ProcessCtrlEventPublisher asyncEventPublisher = new ProcessCtrlEventPublisher();
            ProcessControllerImpl processorController = createProcessorController(asyncEventPublisher);

            ProcessCtrlEventConsumer processCtrlEventConsumer = new ProcessCtrlEventConsumer();
            processCtrlEventConsumer.setProcessController(processorController);

            AsyncEventBus asyncEventBus = new AsyncEventBus();
            asyncEventBus.setThreadPoolExecutor(getThreadPoolExecutor());
            asyncEventPublisher.setEventBus(asyncEventBus);

            asyncEventBus.registerEventConsumer(processCtrlEventConsumer);
            asyncProcessCtrlEventPublisher = asyncEventPublisher;
        }

        //创建服务调用管理器
        if (this.serviceInvokerManager == null) {
            this.serviceInvokerManager = new ServiceInvokerManager();

            //创建Spring Bean的服务调用组件
            SpringBeanServiceInvoker springBeanServiceInvoker = new SpringBeanServiceInvoker();
            springBeanServiceInvoker.setApplicationContext(getApplicationContext());
            springBeanServiceInvoker.setThreadPoolExecutor(threadPoolExecutor);
            springBeanServiceInvoker.setSagaJsonParser(getSagaJsonParser());
            //将Spring Bean的服务调用组件放入到服务调用管理器中
            this.serviceInvokerManager.putServiceInvoker(DomainConstants.SERVICE_TYPE_SPRING_BEAN, springBeanServiceInvoker);
        }

        //创建脚本引擎管理器
        if (this.scriptEngineManager == null) {
            this.scriptEngineManager = new ScriptEngineManager();
        }
    }

    protected ProcessControllerImpl createProcessorController(ProcessCtrlEventPublisher eventPublisher) throws Exception {
        //创建状态机流程处理的路由器
        StateMachineProcessRouter stateMachineProcessRouter = new StateMachineProcessRouter();
        stateMachineProcessRouter.initDefaultStateRouters();
        //通过SPI机制加载状态机流程处理路由的拦截器
        loadStateRouterInterceptors(stateMachineProcessRouter.getStateRouters());

        //创建状态机流程处理器
        StateMachineProcessHandler stateMachineProcessHandler = new StateMachineProcessHandler();
        stateMachineProcessHandler.initDefaultHandlers();
        //通过SPI机制加载状态机流程处理器的拦截器
        loadStateHandlerInterceptors(stateMachineProcessHandler.getStateHandlers());

        //创建默认的路由处理器，并设置事件发布器
        DefaultRouterHandler defaultRouterHandler = new DefaultRouterHandler();
        defaultRouterHandler.setEventPublisher(eventPublisher);

        //创建状态机流程处理路由器对应的Map
        Map<String, ProcessRouter> processRouterMap = new HashMap<>(1);
        processRouterMap.put(ProcessType.STATE_LANG.getCode(), stateMachineProcessRouter);
        defaultRouterHandler.setProcessRouters(processRouterMap);

        //创建自定义的业务处理器
        CustomizeBusinessProcessor customizeBusinessProcessor = new CustomizeBusinessProcessor();

        //创建状态机流程处理器对应的Map
        Map<String, ProcessHandler> processHandlerMap = new HashMap<>(1);
        processHandlerMap.put(ProcessType.STATE_LANG.getCode(), stateMachineProcessHandler);
        customizeBusinessProcessor.setProcessHandlers(processHandlerMap);

        //创建路由处理器对应的Map
        Map<String, RouterHandler> routerHandlerMap = new HashMap<>(1);
        routerHandlerMap.put(ProcessType.STATE_LANG.getCode(), defaultRouterHandler);
        customizeBusinessProcessor.setRouterHandlers(routerHandlerMap);

        //创建流程控制器
        ProcessControllerImpl processorController = new ProcessControllerImpl();
        processorController.setBusinessProcessor(customizeBusinessProcessor);
        return processorController;
    }

    protected void loadStateHandlerInterceptors(Map<String, StateHandler> stateHandlerMap) {
        for (StateHandler stateHandler : stateHandlerMap.values()) {
            if (stateHandler instanceof InterceptableStateHandler) {
                InterceptableStateHandler interceptableStateHandler = (InterceptableStateHandler) stateHandler;
                List<StateHandlerInterceptor> interceptorList = EnhancedServiceLoader.loadAll(StateHandlerInterceptor.class);
                for (StateHandlerInterceptor interceptor : interceptorList) {
                    if (interceptor.match(interceptableStateHandler.getClass())) {
                        interceptableStateHandler.addInterceptor(interceptor);
                    }
                    if (interceptor instanceof ApplicationContextAware) {
                        ((ApplicationContextAware) interceptor).setApplicationContext(getApplicationContext());
                    }
                }
            }
        }
    }

    protected void loadStateRouterInterceptors(Map<String, StateRouter> stateRouterMap) {
        for (StateRouter stateRouter : stateRouterMap.values()) {
            if (stateRouter instanceof InterceptableStateRouter) {
                InterceptableStateRouter interceptableStateRouter = (InterceptableStateRouter) stateRouter;
                List<StateRouterInterceptor> interceptorList = EnhancedServiceLoader.loadAll(StateRouterInterceptor.class);
                for (StateRouterInterceptor interceptor : interceptorList) {
                    if (interceptor.match(interceptableStateRouter.getClass())) {
                        interceptableStateRouter.addInterceptor(interceptor);
                    }
                    if (interceptor instanceof ApplicationContextAware) {
                        ((ApplicationContextAware) interceptor).setApplicationContext(getApplicationContext());
                    }
                }
            }
        }
    }
    ...
}
```

## 9.状态机定义的仓储组件解析状态机定义文件

在DefaultStateMachineConfig的init()方法初始化逻辑中，会通过调用状态机定义的仓储组件StateMachineRepository.registryByResources()方法来读取和解析状态机定义文件，并把解析出来的状态机定义StateMachine注册到状态机定义的仓储组件中，也就是存储在stateMachineRepository变量里。

注意：StateMachine就是状态机定义。

![图片](assets/531d041e06c9.png)

```java
public class StateMachineRepositoryImpl implements StateMachineRepository {
    ...
    @Override
    public void registryByResources(Resource[] resources, String tenantId) throws IOException {
        if (resources != null) {
            for (Resource resource : resources) {
                //1.基于IO流把状态机定义文件(json文件)读取出来，放入json字符串
                String json;
                try (InputStream is = resource.getInputStream()) {
                    json = IOUtils.toString(is, charset);
                }

                //2.从状态机解析器工厂中获取一个状态机解析器，然后解析json字符串得到一个状态机定义StateMachine
                StateMachine stateMachine = StateMachineParserFactory.getStateMachineParser(jsonParserName).parse(json);
                if (stateMachine != null) {
                    stateMachine.setContent(json);
                    if (StringUtils.isBlank(stateMachine.getTenantId())) {
                        stateMachine.setTenantId(tenantId);
                    }

                    //3.注册状态机定义StateMachine
                    registryStateMachine(stateMachine);
                    if (LOGGER.isDebugEnabled()) {
                        LOGGER.debug("===== StateMachine Loaded: \n{}", json);
                    }
                }
            }
        }
    }
    ...
}
```

## 10.状态机定义的仓储组件注册StateMachine

![图片](assets/28fb077b729b.png)

```typescript
public class StateMachineRepositoryImpl implements StateMachineRepository {
    private Map<String/** Name_Tenant **/, Item> stateMachineMapByNameAndTenant = new ConcurrentHashMap<>();
    private Map<String/** Id **/, Item> stateMachineMapById = new ConcurrentHashMap<>();
    private StateLangStore stateLangStore;//状态机定义的存储组件
    ...

    @Override
    public StateMachine registryStateMachine(StateMachine stateMachine) {
        String stateMachineName = stateMachine.getName();
        String tenantId = stateMachine.getTenantId();

        if (stateLangStore != null) {
            //1.从状态机定义的存储组件中，根据状态机名称和租户ID，获取最新版本的状态机定义StateMachine
            StateMachine oldStateMachine = stateLangStore.getLastVersionStateMachine(stateMachineName, tenantId);
            if (oldStateMachine != null) {
                byte[] oldBytesContent = null;
                byte[] bytesContent = null;

                try {
                    oldBytesContent = oldStateMachine.getContent().getBytes(charset);
                    bytesContent = stateMachine.getContent().getBytes(charset);
                } catch (UnsupportedEncodingException e) {
                    LOGGER.error(e.getMessage(), e);
                }

                if (Arrays.equals(bytesContent, oldBytesContent) && stateMachine.getVersion() != null && stateMachine.getVersion().equals(oldStateMachine.getVersion())) {
                    LOGGER.info("StateMachine[{}] is already exist a same version", stateMachineName);

                    stateMachine.setId(oldStateMachine.getId());
                    stateMachine.setGmtCreate(oldStateMachine.getGmtCreate());

                    Item item = new Item(stateMachine);
                    stateMachineMapByNameAndTenant.put(stateMachineName + "_" + tenantId, item);
                    stateMachineMapById.put(stateMachine.getId(), item);
                    return stateMachine;
                }
            }

            if (StringUtils.isBlank(stateMachine.getId())) {
                //2.生成新的状态机定义StateMachine的ID
                stateMachine.setId(seqGenerator.generate(DomainConstants.SEQ_ENTITY_STATE_MACHINE));
            }
            stateMachine.setGmtCreate(new Date());
            //3.通过状态机定义的存储组件，把状态机定义StateMachine保存起来，默认就是把状态机定义StateMachine存储到DB中
            stateLangStore.storeStateMachine(stateMachine);
        }

        if (StringUtils.isBlank(stateMachine.getId())) {
            stateMachine.setId(seqGenerator.generate(DomainConstants.SEQ_ENTITY_STATE_MACHINE));
        }

        Item item = new Item(stateMachine);
        //4.把状态机定义放入内存中
        stateMachineMapByNameAndTenant.put(stateMachineName + "_" + tenantId, item);
        stateMachineMapById.put(stateMachine.getId(), item);
        return stateMachine;
    }
    ...
}

public class DbStateLangStore extends AbstractStore implements StateLangStore {
    ...
    @Override
    public boolean storeStateMachine(StateMachine stateMachine) {
        //把状态机定义StateMachine写入到DB中
        return executeUpdate(stateLangStoreSqls.getInsertStateMachineSql(dbType), STATE_MACHINE_TO_STATEMENT, stateMachine) > 0;
    }
    ...
}
```

## 11.状态机引擎接口的源码

从seata-saga.xml配置文件可知，基于数据库的状态机配置实例DbStateMachineConfig会被注入到基于流程控制的状态机引擎实例ProcessCtrlStateMachineEngine中。

```xml
<beans xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
       xmlns:jdbc="http://www.springframework.org/schema/jdbc"
       xmlns="http://www.springframework.org/schema/beans"
       xsi:schemaLocation="http://www.springframework.org/schema/beans http://www.springframework.org/schema/beans/spring-beans.xsd
       http://www.springframework.org/schema/jdbc http://www.springframework.org/schema/jdbc/spring-jdbc.xsd"
       default-autowire="byName">
    ...
    <bean id="stateMachineEngine" class="io.seata.saga.engine.impl.ProcessCtrlStateMachineEngine">
        <property name="stateMachineConfig" ref="dbStateMachineConfig"></property>
    </bean>
    ...
</beans>
```

基于流程控制的状态机引擎ProcessCtrlStateMachineEngine，会实现状态机引擎接口StateMachineEngine。

```typescript
//ProcessCtrl-based state machine engine
//基于流程控制的状态机引擎
public class ProcessCtrlStateMachineEngine implements StateMachineEngine {
    //需要在seata-saga.xml配置文件中注入状态机配置
    private StateMachineConfig stateMachineConfig;
    ...
}

//State machine engine
//状态机引擎接口
public interface StateMachineEngine {
    //start a state machine instance
    //根据状态机的名称、租户ID、启动参数来启动一个状态机实例
    StateMachineInstance start(String stateMachineName, String tenantId, Map<String, Object> startParams) throws EngineExecutionException;

    //start a state machine instance with businessKey
    //根据状态机的名称、租户ID、业务key、启动参数来启动一个状态机实例
    StateMachineInstance startWithBusinessKey(String stateMachineName, String tenantId, String businessKey, Map<String, Object> startParams) throws EngineExecutionException;

    //start a state machine instance asynchronously
    //根据状态机的名称、租户ID、启动参数来启动一个状态机实例
    //也就是状态机实例跑完之后，会回调传入的callback()方法
    StateMachineInstance startAsync(String stateMachineName, String tenantId, Map<String, Object> startParams, AsyncCallback callback) throws EngineExecutionException;

    //start a state machine instance asynchronously with businessKey
    //根据状态机的名称、租户ID、业务key、启动参数来异步化启动一个状态机实例
    //也就是状态机实例跑完之后，会回调传入的callback()方法
    StateMachineInstance startWithBusinessKeyAsync(String stateMachineName, String tenantId, String businessKey, Map<String, Object> startParams, AsyncCallback callback) throws EngineExecutionException;

    //forward restart a failed state machine instance
    //重启一个失败的状态机实例
    StateMachineInstance forward(String stateMachineInstId, Map<String, Object> replaceParams) throws ForwardInvalidException;

    //forward restart a failed state machine instance asynchronously
    //异步化重启一个失败的状态机实例
    StateMachineInstance forwardAsync(String stateMachineInstId, Map<String, Object> replaceParams, AsyncCallback callback) throws ForwardInvalidException;

    //compensate a state machine instance
    //对一个状态机实例进行补偿
    StateMachineInstance compensate(String stateMachineInstId, Map<String, Object> replaceParams) throws EngineExecutionException;

    //compensate a state machine instance asynchronously
    //对一个状态机实例进行异步化补偿
    StateMachineInstance compensateAsync(String stateMachineInstId, Map<String, Object> replaceParams, AsyncCallback callback) throws EngineExecutionException;

    //skip current failed state instance and forward restart state machine instance
    //跳过当前失败的状态机实例，同时重启一个状态机实例
    StateMachineInstance skipAndForward(String stateMachineInstId, Map<String, Object> replaceParams) throws EngineExecutionException;

    //skip current failed state instance and forward restart state machine instance asynchronously
    StateMachineInstance skipAndForwardAsync(String stateMachineInstId, AsyncCallback callback) throws EngineExecutionException;

    //get state machine configurations
    StateMachineConfig getStateMachineConfig();

    //Reload StateMachine Instance
    StateMachineInstance reloadStateMachineInstance(String instId);
}
```

## 12.状态机引擎创建状态机实例的源码

基于流程控制的状态机引擎实例ProcessCtrlStateMachineEngine的start()方法调用其startInternal()方法启动一个状态机实例时，会先创建一个状态机实例StateMachineInstance。

在调用ProcessCtrlStateMachineEngine的createMachineInstance()方法创建一个状态机实例StateMachineInstance的过程中，会先通过状态机定义的仓储组件StateMachineRepository来获取一个状态机定义StateMachine，然后将状态机定义StateMachine注入到状态机实例对象中，以此来完成状态机实例对象的实例化。

![图片](assets/0c4d0d360531.png)

```typescript
//ProcessCtrl-based state machine engine
//基于流程控制的状态机引擎
public class ProcessCtrlStateMachineEngine implements StateMachineEngine {
    //需要在seata-saga.xml配置文件中注入状态机配置实例
    private StateMachineConfig stateMachineConfig;
    ...

    @Override
    public StateMachineInstance start(String stateMachineName, String tenantId, Map<String, Object> startParams) throws EngineExecutionException {
        return startInternal(stateMachineName, tenantId, null, startParams, false, null);
    }

    @Override
    public StateMachineInstance startAsync(String stateMachineName, String tenantId, Map<String, Object> startParams, AsyncCallback callback) throws EngineExecutionException {
        return startInternal(stateMachineName, tenantId, null, startParams, true, callback);
    }

    @Override
    public StateMachineInstance startWithBusinessKey(String stateMachineName, String tenantId, String businessKey, Map<String, Object> startParams) throws EngineExecutionException {
        return startInternal(stateMachineName, tenantId, businessKey, startParams, false, null);
    }

    @Override
    public StateMachineInstance startWithBusinessKeyAsync(String stateMachineName, String tenantId, String businessKey, Map<String, Object> startParams, AsyncCallback callback) throws EngineExecutionException {
        return startInternal(stateMachineName, tenantId, businessKey, startParams, true, callback);
    }
    ...

    //启动状态机实例StateMachineInstance
    //@param stateMachineName 状态机名称
    //@param tenantId 租户ID
    //@param businessKey 业务key
    //@param startParams 状态机实例的启动参数
    //@param async 是否异步化运行
    //@param callback 异步化运行时的回调接口
    private StateMachineInstance startInternal(String stateMachineName, String tenantId, String businessKey, Map<String, Object> startParams, boolean async, AsyncCallback callback) throws EngineExecutionException {
        try {
            //如果指定需要异步运行，但是状态机配置里是不允许异步运行的，则会抛异常
            if (async && !stateMachineConfig.isEnableAsync()) {
                throw new EngineExecutionException("Asynchronous start is disabled. please set StateMachineConfig.enableAsync=true first.", FrameworkErrorCode.AsynchronousStartDisabled);
            }
            if (StringUtils.isEmpty(tenantId)) {
                tenantId = stateMachineConfig.getDefaultTenantId();
            }

            //创建状态机实例StateMachineInstance
            StateMachineInstance instance = createMachineInstance(stateMachineName, tenantId, businessKey, startParams);
            ...
        }
        ...
    }

    private StateMachineInstance createMachineInstance(String stateMachineName, String tenantId, String businessKey, Map<String, Object> startParams) {
        //通过状态机定义的仓储组件StateMachineRepository，来获取一个状态机定义StateMachine
        StateMachine stateMachine = stateMachineConfig.getStateMachineRepository().getStateMachine(stateMachineName, tenantId);
        if (stateMachine == null) {
            throw new EngineExecutionException("StateMachine[" + stateMachineName + "] is not exists", FrameworkErrorCode.ObjectNotExists);
        }

        //根据状态机定义StateMachine，实例化一个状态机实例对象StateMachineInstanceImpl
        StateMachineInstanceImpl inst = new StateMachineInstanceImpl();
        inst.setStateMachine(stateMachine);
        inst.setMachineId(stateMachine.getId());
        inst.setTenantId(tenantId);
        inst.setBusinessKey(businessKey);

        //设置状态机实例的启动参数
        inst.setStartParams(startParams);
        if (startParams != null) {
            if (StringUtils.hasText(businessKey)) {
                startParams.put(DomainConstants.VAR_NAME_BUSINESSKEY, businessKey);
            }
            String parentId = (String)startParams.get(DomainConstants.VAR_NAME_PARENT_ID);
            if (StringUtils.hasText(parentId)) {
                inst.setParentId(parentId);
                startParams.remove(DomainConstants.VAR_NAME_PARENT_ID);
            }
        }

        inst.setStatus(ExecutionStatus.RU);
        inst.setRunning(true);
        inst.setGmtStarted(new Date());
        inst.setGmtUpdated(inst.getGmtStarted());
        return inst;
    }
    ...
}
```

## 13.ProcessContextBuilder构建流程上下文

ProcessCtrlStateMachineEngine.startInternal()方法在执行过程中会创建一个流程上下文构造器ProcessContextBuilder实例，然后根据这个流程上下文构造器ProcessContextBuilder构建出一个流程上下文ProcessContext。

![图片](assets/5756b5106577.png)

```typescript
public class ProcessCtrlStateMachineEngine implements StateMachineEngine {
    ...
    //启动状态机实例StateMachineInstance
    //@param stateMachineName 状态机名称
    //@param tenantId 租户ID
    //@param businessKey 业务key
    //@param startParams 状态机实例的启动参数
    //@param async 是否异步化运行
    //@param callback 异步化运行时的回调接口
    private StateMachineInstance startInternal(String stateMachineName, String tenantId, String businessKey, Map<String, Object> startParams, boolean async, AsyncCallback callback) throws EngineExecutionException {
        try {
            //如果指定需要异步运行，但是状态机配置里是不允许异步运行的，则会抛异常
            if (async && !stateMachineConfig.isEnableAsync()) {
                throw new EngineExecutionException("Asynchronous start is disabled. please set StateMachineConfig.enableAsync=true first.", FrameworkErrorCode.AsynchronousStartDisabled);
            }

            if (StringUtils.isEmpty(tenantId)) {
                tenantId = stateMachineConfig.getDefaultTenantId();
            }

            //创建状态机实例StateMachineInstance
            StateMachineInstance instance = createMachineInstance(stateMachineName, tenantId, businessKey, startParams);

            //创建一个流程上下文构造器ProcessContextBuilder实例，用来构造流程运行时的上下文
            ProcessContextBuilder contextBuilder = ProcessContextBuilder.create()
                .withProcessType(ProcessType.STATE_LANG)//设置流程类型
                .withOperationName(DomainConstants.OPERATION_NAME_START)//设置操作名称
                .withAsyncCallback(callback)//设置异步化时的回调接口
                .withInstruction(new StateInstruction(stateMachineName, tenantId))//设置状态获取组件
                .withStateMachineInstance(instance)//设置状态机实例
                .withStateMachineConfig(getStateMachineConfig())//设置状态机配置
                .withStateMachineEngine(this);//设置状态机引擎

            //上下文变量Map
            Map<String, Object> contextVariables;
            if (startParams != null) {
                contextVariables = new ConcurrentHashMap<>(startParams.size());
                nullSafeCopy(startParams, contextVariables);
            } else {
                contextVariables = new ConcurrentHashMap<>();
            }

            instance.setContext(contextVariables);

            //设置流程上下文构造器ProcessContextBuilder实例
            contextBuilder.withStateMachineContextVariables(contextVariables);
            contextBuilder.withIsAsyncExecution(async);

            //通过流程上下文构造器ProcessContextBuilder构建出一个流程上下文ProcessContext
            ProcessContext processContext = contextBuilder.build();

            //如果状态机定义StateMachine是支持持久化的 且 状态日志的存储组件不为null
            if (instance.getStateMachine().isPersist() && stateMachineConfig.getStateLogStore() != null) {
                //通过状态机实例日志和状态实例日志的存储组件StateLogStore，记录状态机实例StateMachineInstance的启动事件日志 + 开启全局事务
                //比如在DB中更新状态机实例StateMachineInstance的启动状态
                stateMachineConfig.getStateLogStore().recordStateMachineStarted(instance, processContext);
            }

            if (StringUtils.isEmpty(instance.getId())) {
                //生成状态机实例StateMachineInstance的序号
                instance.setId(stateMachineConfig.getSeqGenerator().generate(DomainConstants.SEQ_ENTITY_STATE_MACHINE_INST));
            }

            StateInstruction stateInstruction = processContext.getInstruction(StateInstruction.class);
            Loop loop = LoopTaskUtils.getLoopConfig(processContext, stateInstruction.getState(processContext));
            if (null != loop) {
                stateInstruction.setTemporaryState(new LoopStartStateImpl());
            }

            if (async) {
                stateMachineConfig.getAsyncProcessCtrlEventPublisher().publish(processContext);
            } else {
                stateMachineConfig.getProcessCtrlEventPublisher().publish(processContext);
            }
            return instance;
        } finally {
            if (stateMachineConfig.getStateLogStore() != null) {
                stateMachineConfig.getStateLogStore().clearUp();
            }
        }
    }
    ...
}
```

## 14.StateLogStore记录日志和开启Saga全局事务

在状态机引擎ProcessCtrlStateMachineEngine的startInternal()方法中，会通过调用StateLogStore的recordStateMachineStarted()方法，记录状态机实例StateMachineInstance的启动事件到DB，以及开启Saga全局事务。

![图片](assets/820ef35e66e7.png)

```java
public class DbAndReportTcStateLogStore extends AbstractStore implements StateLogStore {
    private static final Logger LOGGER = LoggerFactory.getLogger(DbAndReportTcStateLogStore.class);
    //插入状态机实例到数据库的SQL语句
    private static final StateMachineInstanceToStatementForInsert STATE_MACHINE_INSTANCE_TO_STATEMENT_FOR_INSERT = new StateMachineInstanceToStatementForInsert();
    //更新数据库状态机实例的SQL语句
    private static final StateMachineInstanceToStatementForUpdate STATE_MACHINE_INSTANCE_TO_STATEMENT_FOR_UPDATE = new StateMachineInstanceToStatementForUpdate();
    //查询数据库中的状态机实例的SQL语句
    private static final ResultSetToStateMachineInstance RESULT_SET_TO_STATE_MACHINE_INSTANCE = new ResultSetToStateMachineInstance();
    //插入状态实例到数据库的SQL语句
    private static final StateInstanceToStatementForInsert STATE_INSTANCE_TO_STATEMENT_FOR_INSERT = new StateInstanceToStatementForInsert();
    //更新数据库中的状态实例的SQL语句
    private static final StateInstanceToStatementForUpdate STATE_INSTANCE_TO_STATEMENT_FOR_UPDATE = new StateInstanceToStatementForUpdate();
    //查询数据库中的状态实例的SQL语句
    private static final ResultSetToStateInstance RESULT_SET_TO_STATE_INSTANCE = new ResultSetToStateInstance();

    //Saga全局事务模版
    private SagaTransactionalTemplate sagaTransactionalTemplate;
    //参数序列化组件
    private Serializer<Object, String> paramsSerializer = new ParamsSerializer();
    //异常序列化组件
    private Serializer<Exception, byte[]> exceptionSerializer = new ExceptionSerializer();
    //状态日志的存储SQL语句
    private StateLogStoreSqls stateLogStoreSqls;
    //默认的租户ID
    private String defaultTenantId;
    //序号生成器
    private SeqGenerator seqGenerator;
    //记录状态机实例的启动事件日志到DB + 开启Saga全局事务

    @Override
    public void recordStateMachineStarted(StateMachineInstance machineInstance, ProcessContext context) {
        if (machineInstance != null) {
            //if parentId is not null, machineInstance is a SubStateMachine, do not start a new global transaction, use parent transaction instead.
            //如果parentId是空的，那么当前事务就是Saga分布式事务的启动入口；
            //如果parentId不是空的，则已经有服务使用状态机启动了Saga分布式事务；
            String parentId = machineInstance.getParentId();
            if (StringUtils.isEmpty(parentId)) {
                //1.开启Saga全局事务
                beginTransaction(machineInstance, context);
            }

            try {
                if (StringUtils.isEmpty(machineInstance.getId()) && seqGenerator != null) {
                    machineInstance.setId(seqGenerator.generate(DomainConstants.SEQ_ENTITY_STATE_MACHINE_INST));
                }
                //bind SAGA branch type
                RootContext.bindBranchType(BranchType.SAGA);
                //save to db
                machineInstance.setSerializedStartParams(paramsSerializer.serialize(machineInstance.getStartParams()));
                //2.记录日志到DB
                int effect = executeUpdate(stateLogStoreSqls.getRecordStateMachineStartedSql(dbType), STATE_MACHINE_INSTANCE_TO_STATEMENT_FOR_INSERT, machineInstance);
                if (effect < 1) {
                    throw new StoreException("StateMachineInstance record start error, Xid: " + machineInstance.getId(), FrameworkErrorCode.OperationDenied);
                }
            } catch (StoreException e) {
                LOGGER.error("Record statemachine start error: {}, StateMachine: {}, XID: {}, Reason: {}", e.getErrcode(), machineInstance.getStateMachine().getName(), machineInstance.getId(), e.getMessage(), e);
                this.clearUp();
                throw e;
            }
        }
    }

    protected void beginTransaction(StateMachineInstance machineInstance, ProcessContext context) {
        if (sagaTransactionalTemplate != null) {
            //获取状态机配置
            StateMachineConfig stateMachineConfig = (StateMachineConfig) context.getVariable(DomainConstants.VAR_NAME_STATEMACHINE_CONFIG);
            //构建事务信息
            TransactionInfo transactionInfo = new TransactionInfo();
            transactionInfo.setTimeOut(stateMachineConfig.getTransOperationTimeout());
            transactionInfo.setName(Constants.SAGA_TRANS_NAME_PREFIX + machineInstance.getStateMachine().getName());
            try {
                //通过Saga事务模版开启全局事务
                GlobalTransaction globalTransaction = sagaTransactionalTemplate.beginTransaction(transactionInfo);
                machineInstance.setId(globalTransaction.getXid());

                context.setVariable(DomainConstants.VAR_NAME_GLOBAL_TX, globalTransaction);
                Map<String, Object> machineContext = machineInstance.getContext();
                if (machineContext != null) {
                    machineContext.put(DomainConstants.VAR_NAME_GLOBAL_TX, globalTransaction);
                }
            } catch (ExecutionException e) {
                String xid = null;
                if (e.getTransaction() != null) {
                    xid = e.getTransaction().getXid();
                }
                throw new EngineExecutionException(e, e.getCode() + ", TransName:" + transactionInfo.getName() + ", XID: " + xid + ", Reason: " + e.getMessage(), FrameworkErrorCode.TransactionManagerError);
            } finally {
                if (Boolean.TRUE.equals(context.getVariable(DomainConstants.VAR_NAME_IS_ASYNC_EXECUTION))) {
                    RootContext.unbind();
                    RootContext.unbindBranchType();
                }
            }
        }
    }
    ...
}

public class StateLogStoreSqls {
    private String recordStateMachineStartedSql;
    private static final String RECORD_STATE_MACHINE_STARTED_SQL = "INSERT INTO ${TABLE_PREFIX}state_machine_inst\n"
        + "(id, machine_id, tenant_id, parent_id, gmt_started, business_key, start_params, is_running, status, "
        + "gmt_updated)\n"
        + "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)";
    ...

    public StateLogStoreSqls(String tablePrefix) {
        this.tablePrefix = tablePrefix;
        init();
    }

    private void init() {
        recordStateMachineStartedSql = RECORD_STATE_MACHINE_STARTED_SQL.replaceAll(TABLE_PREFIX_REGEX, tablePrefix);
        ...
    }

    public String getRecordStateMachineStartedSql(String dbType) {
        return recordStateMachineStartedSql;
    }
    ...
}

public class AbstractStore {
    protected DataSource dataSource;
    ...

    protected <T> int executeUpdate(String sql, ObjectToStatement<T> objectToStatement, T o) {
        Connection connection = null;
        PreparedStatement stmt = null;

        try {
            connection = dataSource.getConnection();
            if (LOGGER.isDebugEnabled()) {
                LOGGER.debug("Preparing SQL: {}", sql);
            }
            stmt = connection.prepareStatement(sql);
            if (LOGGER.isDebugEnabled()) {
                LOGGER.debug("setting params to PreparedStatement: {}", BeanUtils.beanToString(o));
            }

            objectToStatement.toStatement(o, stmt);
            int count = stmt.executeUpdate();
            if (!connection.getAutoCommit()) {
                connection.commit();
            }
            return count;
        } catch (SQLException e) {
            throw new StoreException(e);
        } finally {
            closeSilent(stmt);
            closeSilent(connection);
        }
    }
    ...
}

public class DefaultSagaTransactionalTemplate implements SagaTransactionalTemplate, ApplicationContextAware, DisposableBean, InitializingBean {
    ...
    @Override
    public GlobalTransaction beginTransaction(TransactionInfo txInfo) throws TransactionalExecutor.ExecutionException {
        GlobalTransaction tx = GlobalTransactionContext.getCurrentOrCreate();
        try {
            triggerBeforeBegin();
            //开启一个全局会话
            tx.begin(txInfo.getTimeOut(), txInfo.getName());
            triggerAfterBegin();
        } catch (TransactionException txe) {
            throw new TransactionalExecutor.ExecutionException(tx, txe, TransactionalExecutor.Code.BeginFailure);
        }
        return tx;
    }
    ...
}
```

执行GlobalTransaction的begin()方法开启一个全局会话：

```java
//The type Default global transaction.
//默认的全局事务
public class DefaultGlobalTransaction implements GlobalTransaction {
    private TransactionManager transactionManager;
    private String xid;
    private GlobalStatus status;
    private GlobalTransactionRole role;
    ...

    DefaultGlobalTransaction() {
        //全局事务角色是全局事务发起者
        this(null, GlobalStatus.UnKnown, GlobalTransactionRole.Launcher);
    }

    //Instantiates a new Default global transaction.
    DefaultGlobalTransaction(String xid, GlobalStatus status, GlobalTransactionRole role) {
        this.transactionManager = TransactionManagerHolder.get();//全局事务管理者
        this.xid = xid;
        this.status = status;
        this.role = role;
    }
    ...

    @Override
    public void begin(int timeout, String name) throws TransactionException {
        if (role != GlobalTransactionRole.Launcher) {
            assertXIDNotNull();
            if (LOGGER.isDebugEnabled()) {
                LOGGER.debug("Ignore Begin(): just involved in global transaction [{}]", xid);
            }
            return;
        }

        assertXIDNull();
        String currentXid = RootContext.getXID();
        if (currentXid != null) {
            throw new IllegalStateException("Global transaction already exists," + " can't begin a new global transaction, currentXid = " + currentXid);
        }

        //通过全局事务管理器去真正开启全局事务，一旦开启成功，就可以获取到一个xid
        xid = transactionManager.begin(null, null, name, timeout);
        status = GlobalStatus.Begin;

        //把xid绑定到RootContext的线程本地变量副本里去
        RootContext.bind(xid);
        if (LOGGER.isInfoEnabled()) {
            LOGGER.info("Begin new global transaction [{}]", xid);
        }
    }
    ...
}

public class TransactionManagerHolder {
    private static final Logger LOGGER = LoggerFactory.getLogger(TransactionManagerHolder.class);

    private static class SingletonHolder {
        private static TransactionManager INSTANCE = null;
        static {
            try {
                INSTANCE = EnhancedServiceLoader.load(TransactionManager.class);
                LOGGER.info("TransactionManager Singleton {}", INSTANCE);
            } catch (Throwable anyEx) {
                LOGGER.error("Failed to load TransactionManager Singleton! ", anyEx);
            }
        }
    }

    //Get transaction manager.
    public static TransactionManager get() {
        if (SingletonHolder.INSTANCE == null) {
            throw new ShouldNeverHappenException("TransactionManager is NOT ready!");
        }
        return SingletonHolder.INSTANCE;
    }

    private TransactionManagerHolder() {
    }
}

//The type Default transaction manager.
//默认的全局事务管理器
public class DefaultTransactionManager implements TransactionManager {
    @Override
    public String begin(String applicationId, String transactionServiceGroup, String name, int timeout) throws TransactionException {
        //构建一个全局事务开启请求GlobalBeginRequest
        GlobalBeginRequest request = new GlobalBeginRequest();
        request.setTransactionName(name);
        request.setTimeout(timeout);

        //发起一个同步调用
        GlobalBeginResponse response = (GlobalBeginResponse) syncCall(request);
        if (response.getResultCode() == ResultCode.Failed) {
            throw new TmTransactionException(TransactionExceptionCode.BeginFailed, response.getMsg());
        }
        return response.getXid();
    }
    ...

    private AbstractTransactionResponse syncCall(AbstractTransactionRequest request) throws TransactionException {
        try {
            //TMNettyRemotingClient会和Seata Server基于Netty建立长连接
            return (AbstractTransactionResponse) TmNettyRemotingClient.getInstance().sendSyncRequest(request);
        } catch (TimeoutException toe) {
            throw new TmTransactionException(TransactionExceptionCode.IO, "RPC timeout", toe);
        }
    }
}

public abstract class AbstractNettyRemotingClient extends AbstractNettyRemoting implements RemotingClient {
    ...
    @Override
    public Object sendSyncRequest(Object msg) throws TimeoutException {
        //因为Seata Server是可以多节点部署实现高可用架构的，所以这里调用loadBalance()方法进行负载均衡
        String serverAddress = loadBalance(getTransactionServiceGroup(), msg);
        //获取RPC调用的超时时间
        long timeoutMillis = this.getRpcRequestTimeout();
        //构建一个RPC消息
        RpcMessage rpcMessage = buildRequestMessage(msg, ProtocolConstants.MSGTYPE_RESQUEST_SYNC);

        //send batch message
        //put message into basketMap, @see MergedSendRunnable
        //默认是不开启批量消息发送
        if (this.isEnableClientBatchSendRequest()) {
            ...
        } else {
            //通过网络连接管理器clientChannelManager，获取与指定Seata Server建立的网络连接Channel
            //然后通过网络连接Channel把RpcMessage发送出去
            Channel channel = clientChannelManager.acquireChannel(serverAddress);
            return super.sendSync(channel, rpcMessage, timeoutMillis);
        }
    }
    ...
}

public abstract class AbstractNettyRemoting implements Disposable {
    ...
    protected Object sendSync(Channel channel, RpcMessage rpcMessage, long timeoutMillis) throws TimeoutException {
        if (timeoutMillis <= 0) {
            throw new FrameworkException("timeout should more than 0ms");
        }
        if (channel == null) {
            LOGGER.warn("sendSync nothing, caused by null channel.");
            return null;
        }

        //把发送出去的请求封装到MessageFuture中，然后存放到futures这个Map里
        MessageFuture messageFuture = new MessageFuture();
        messageFuture.setRequestMessage(rpcMessage);
        messageFuture.setTimeout(timeoutMillis);
        futures.put(rpcMessage.getId(), messageFuture);
        channelWritableCheck(channel, rpcMessage.getBody());

        //获取远程地址
        String remoteAddr = ChannelUtil.getAddressFromChannel(channel);
        doBeforeRpcHooks(remoteAddr, rpcMessage);

        //异步化发送数据，同时对发送结果添加监听器
        //如果发送失败，则会对网络连接Channel进行销毁处理
        channel.writeAndFlush(rpcMessage).addListener((ChannelFutureListener) future -> {
            if (!future.isSuccess()) {
                MessageFuture messageFuture1 = futures.remove(rpcMessage.getId());
                if (messageFuture1 != null) {
                    messageFuture1.setResultMessage(future.cause());
                }
                destroyChannel(future.channel());
            }
        });

        try {
            //然后通过请求响应组件MessageFuture同步等待Seata Server返回该请求的响应
            Object result = messageFuture.get(timeoutMillis, TimeUnit.MILLISECONDS);
            doAfterRpcHooks(remoteAddr, rpcMessage, result);
            return result;
        } catch (Exception exx) {
            LOGGER.error("wait response error:{},ip:{},request:{}", exx.getMessage(), channel.remoteAddress(), rpcMessage.getBody());
            if (exx instanceof TimeoutException) {
                throw (TimeoutException) exx;
            } else {
                throw new RuntimeException(exx);
            }
        }
    }
    ...
}
```

## 15.状态操作组件获取状态和State状态类继承体系

### (1)状态操作组件StateInstruction获取状态

### (2)State状态类的继承体系

### (1)状态操作组件StateInstruction获取状态

在状态机引擎ProcessCtrlStateMachineEngine的startInternal()方法中，会通过流程上下文ProcessContext来获取状态操作组件StateInstruction。

根据状态操作组件StateInstruction，可以获取状态机的开始State(状态)、也可以获取指定的某个State(状态)。

```typescript
public class ProcessCtrlStateMachineEngine implements StateMachineEngine {
    ...
    //启动状态机实例StateMachineInstance
    //@param stateMachineName 状态机名称
    //@param tenantId 租户ID
    //@param businessKey 业务key
    //@param startParams 状态机实例的启动参数
    //@param async 是否异步化运行
    //@param callback 异步化运行时的回调接口
    private StateMachineInstance startInternal(String stateMachineName, String tenantId, String businessKey, Map<String, Object> startParams, boolean async, AsyncCallback callback) throws EngineExecutionException {
        try {
            //如果指定需要异步运行，但是状态机配置里是不允许异步运行的，则会抛异常
            if (async && !stateMachineConfig.isEnableAsync()) {
                throw new EngineExecutionException("Asynchronous start is disabled. please set StateMachineConfig.enableAsync=true first.", FrameworkErrorCode.AsynchronousStartDisabled);
            }

            if (StringUtils.isEmpty(tenantId)) {
                tenantId = stateMachineConfig.getDefaultTenantId();
            }

            //创建状态机实例StateMachineInstance
            StateMachineInstance instance = createMachineInstance(stateMachineName, tenantId, businessKey, startParams);

            //创建一个流程上下文构造器ProcessContextBuilder实例，用来构造流程运行时的上下文
            ProcessContextBuilder contextBuilder = ProcessContextBuilder.create()
                .withProcessType(ProcessType.STATE_LANG)//设置流程类型
                .withOperationName(DomainConstants.OPERATION_NAME_START)//设置操作名称
                .withAsyncCallback(callback)//设置异步化时的回调接口
                .withInstruction(new StateInstruction(stateMachineName, tenantId))//设置状态获取组件
                .withStateMachineInstance(instance)//设置状态机实例
                .withStateMachineConfig(getStateMachineConfig())//设置状态机配置
                .withStateMachineEngine(this);//设置状态机引擎

            //上下文变量Map
            Map<String, Object> contextVariables;
            if (startParams != null) {
                contextVariables = new ConcurrentHashMap<>(startParams.size());
                nullSafeCopy(startParams, contextVariables);
            } else {
                contextVariables = new ConcurrentHashMap<>();
            }

            instance.setContext(contextVariables);
            //设置流程上下文构造器ProcessContextBuilder实例
            contextBuilder.withStateMachineContextVariables(contextVariables);
            contextBuilder.withIsAsyncExecution(async);

            //通过流程上下文构造器ProcessContextBuilder构建出一个流程上下文ProcessContext
            ProcessContext processContext = contextBuilder.build();

            //如果状态机定义StateMachine是支持持久化的 且 状态日志的存储组件不为null
            if (instance.getStateMachine().isPersist() && stateMachineConfig.getStateLogStore() != null) {
                //通过状态机实例日志和状态实例日志的存储组件StateLogStore，记录状态机实例StateMachineInstance的启动事件日志 + 开启全局事务
                //比如在DB中更新状态机实例StateMachineInstance的启动状态
                stateMachineConfig.getStateLogStore().recordStateMachineStarted(instance, processContext);
            }

            if (StringUtils.isEmpty(instance.getId())) {
                //生成状态机实例StateMachineInstance的序号
                instance.setId(stateMachineConfig.getSeqGenerator().generate(DomainConstants.SEQ_ENTITY_STATE_MACHINE_INST));
            }

            //从流程上下文中获取状态操作组件StateInstruction
            StateInstruction stateInstruction = processContext.getInstruction(StateInstruction.class);

            //获取循环策略
            Loop loop = LoopTaskUtils.getLoopConfig(processContext, stateInstruction.getState(processContext));
            if (null != loop) {
                stateInstruction.setTemporaryState(new LoopStartStateImpl());
            }

            if (async) {
                stateMachineConfig.getAsyncProcessCtrlEventPublisher().publish(processContext);
            } else {
                stateMachineConfig.getProcessCtrlEventPublisher().publish(processContext);
            }
            return instance;
        } finally {
            if (stateMachineConfig.getStateLogStore() != null) {
                stateMachineConfig.getStateLogStore().clearUp();
            }
        }
    }
    ...
}

//State Instruction，状态操作组件StateInstruction
public class StateInstruction implements Instruction {
    private String stateName;
    private String stateMachineName;
    private String tenantId;
    private boolean end;
    //Temporary state node for running temporary nodes in the state machine
    private State temporaryState;

    public StateInstruction() {
    }

    public StateInstruction(String stateMachineName, String tenantId) {
        this.stateMachineName = stateMachineName;
        this.tenantId = tenantId;
    }

    //根据流程上下文获取状态，可以是状态机的开始State(状态)、也可以是指定的某个State(状态)
    public State getState(ProcessContext context) {
        if (getTemporaryState() != null) {
            return temporaryState;
        }

        String stateName = getStateName();
        String stateMachineName = getStateMachineName();
        String tenantId = getTenantId();
        if (StringUtils.isEmpty(stateMachineName)) {
            throw new EngineExecutionException("StateMachineName is required", FrameworkErrorCode.ParameterRequired);
        }

        StateMachineConfig stateMachineConfig = (StateMachineConfig)context.getVariable(DomainConstants.VAR_NAME_STATEMACHINE_CONFIG);
        StateMachine stateMachine = stateMachineConfig.getStateMachineRepository().getStateMachine(stateMachineName, tenantId);
        if (stateMachine == null) {
            throw new EngineExecutionException("StateMachine[" + stateMachineName + "] is not exist", FrameworkErrorCode.ObjectNotExists);
        }

        //默认就是获取状态机定义StateMachine中的第一个状态State
        if (StringUtils.isEmpty(stateName)) {
            stateName = stateMachine.getStartState();
            setStateName(stateName);
        }

        //根据状态名字stateName，从状态机定义中获取对应的状态State
        State state = stateMachine.getStates().get(stateName);
        if (state == null) {
            throw new EngineExecutionException("State[" + stateName + "] is not exist", FrameworkErrorCode.ObjectNotExists);
        }
        return state;
    }
    ...
}
```

### (2)State状态类的继承体系

![图片](assets/d9ff1e3f9dba.png)

```typescript
//A State in StateMachine
public interface State {
    String getName();
    String getComment();
    String getType();
    String getNext();
    Map<String, Object> getExtensions();
    StateMachine getStateMachine();
}

public abstract class BaseState implements State {
    private transient String name;//状态名称
    private String type;//状态类型
    private String comment;//状态备注
    private String next;//下一个状态名称
    private Map<String, Object> extensions;//状态扩展属性
    private transient StateMachine stateMachine;//状态所属的状态机
    ...
}

//The state of the execution task (abstract class), the specific task to be executed is determined by the subclass
public abstract class AbstractTaskState extends BaseState implements TaskState {
    private String compensateState;//补偿状态
    private boolean isForCompensation;//是否用于补偿
    private boolean isForUpdate;//是否用于更新
    private List<Retry> retry;//重试列表
    private List<ExceptionMatch> catches;//异常匹配列表
    private List<Object> input;//状态输入列表
    private Map<String, Object> output;//状态输出数据
    private Map<String, String> status;//Map<String/* expression */, String /* status */>
    private List<Object> inputExpressions;//输入表达式列表
    private Map<String, Object> outputExpressions;//输出表达式数据
    private boolean isPersist = true;//是否持久化
    private Boolean retryPersistModeUpdate;//是否更新Saga重试持久化的模式
    private Boolean compensatePersistModeUpdate;//是否更新Saga补偿持久化的模式
    private Loop loop;//循环对象
    ...

    public static class RetryImpl implements Retry {
        private List<String> exceptions;//重试的过程中遇到了哪些异常
        private List<Class<? extends Exception>> exceptionClasses;//异常Class
        private double intervalSeconds;//重试间隔，单位是秒
        private int maxAttempts;//最大重试次数
        private double backoffRate;//回退比例
        ...
    }

    public static class ExceptionMatchImpl implements ExceptionMatch {
        List<String> exceptions;
        List<Class<? extends Exception>> exceptionClasses;
        String next;
        ...
    }

    public static class LoopImpl implements Loop {
        private int parallel;//并行度
        private String collection;
        private String elementVariableName;
        private String elementIndexName;
        private String completionCondition;
        ...
    }
    ...
}
```

## 16.启动状态机实例时发布流程上下文到事件总线

### (1)启动状态机实例时的主要工作总结

### (2)发布流程上下文到事件总线的源码

### (1)启动状态机实例时的主要工作总结

调用状态机引擎ProcessCtrlStateMachineEngine的startInternal()方法时：

#### 一.首先创建状态机实例StateMachineInstance

二.然后通过ProcessContextBuilder流程上下文构造器构建出一个流程上下文ProcessContext

#### 三.接着记录状态机实例的启动日志 \+ 开启全局事务

#### 四.然后从流程上下文获取状态操作组件来设置状态

#### 五.最后发布流程上下文ProcessContext到事件总线

![图片](assets/66861acebb4a.png)

```typescript
public class ProcessCtrlStateMachineEngine implements StateMachineEngine {
    ...
    //启动状态机实例StateMachineInstance
    //@param stateMachineName 状态机名称
    //@param tenantId 租户ID
    //@param businessKey 业务key
    //@param startParams 状态机实例的启动参数
    //@param async 是否异步化运行
    //@param callback 异步化运行时的回调接口
    private StateMachineInstance startInternal(String stateMachineName, String tenantId, String businessKey, Map<String, Object> startParams, boolean async, AsyncCallback callback) throws EngineExecutionException {
        try {
            //如果指定需要异步运行，但是状态机配置里是不允许异步运行的，则会抛异常
            if (async && !stateMachineConfig.isEnableAsync()) {
                throw new EngineExecutionException("Asynchronous start is disabled. please set StateMachineConfig.enableAsync=true first.", FrameworkErrorCode.AsynchronousStartDisabled);
            }

            if (StringUtils.isEmpty(tenantId)) {
                tenantId = stateMachineConfig.getDefaultTenantId();
            }

            //1.创建状态机实例StateMachineInstance
            StateMachineInstance instance = createMachineInstance(stateMachineName, tenantId, businessKey, startParams);

            //创建一个流程上下文构造器ProcessContextBuilder实例，用来构造流程运行时的上下文
            ProcessContextBuilder contextBuilder = ProcessContextBuilder.create()
                .withProcessType(ProcessType.STATE_LANG)//设置流程类型
                .withOperationName(DomainConstants.OPERATION_NAME_START)//设置操作名称
                .withAsyncCallback(callback)//设置异步化时的回调接口
                .withInstruction(new StateInstruction(stateMachineName, tenantId))//设置状态获取组件
                .withStateMachineInstance(instance)//设置状态机实例
                .withStateMachineConfig(getStateMachineConfig())//设置状态机配置
                .withStateMachineEngine(this);//设置状态机引擎

            //上下文变量Map
            Map<String, Object> contextVariables;
            if (startParams != null) {
                contextVariables = new ConcurrentHashMap<>(startParams.size());
                nullSafeCopy(startParams, contextVariables);
            } else {
                contextVariables = new ConcurrentHashMap<>();
            }

            instance.setContext(contextVariables);
            //设置流程上下文构造器ProcessContextBuilder实例
            contextBuilder.withStateMachineContextVariables(contextVariables);
            contextBuilder.withIsAsyncExecution(async);

            //2.通过流程上下文构造器ProcessContextBuilder构建出一个流程上下文ProcessContext
            ProcessContext processContext = contextBuilder.build();

            //如果状态机定义StateMachine是支持持久化的 且 状态日志的存储组件不为null
            if (instance.getStateMachine().isPersist() && stateMachineConfig.getStateLogStore() != null) {
                //3.通过状态机实例日志和状态实例日志的存储组件StateLogStore，记录状态机实例StateMachineInstance的启动事件日志 + 开启全局事务
                //比如在DB中更新状态机实例StateMachineInstance的启动状态
                stateMachineConfig.getStateLogStore().recordStateMachineStarted(instance, processContext);
            }

            if (StringUtils.isEmpty(instance.getId())) {
                //生成状态机实例StateMachineInstance的序号
                instance.setId(stateMachineConfig.getSeqGenerator().generate(DomainConstants.SEQ_ENTITY_STATE_MACHINE_INST));
            }

            //从流程上下文中获取状态操作组件StateInstruction
            StateInstruction stateInstruction = processContext.getInstruction(StateInstruction.class);

            //4.先获取State，再根据State获取循环策略Loop，然后判定Loop是否为空来决定是否设置"状态操作组件StateInstruction"
            Loop loop = LoopTaskUtils.getLoopConfig(processContext, stateInstruction.getState(processContext));
            if (null != loop) {
                stateInstruction.setTemporaryState(new LoopStartStateImpl());
            }

            //5.发布流程上下文到事件总线
            if (async) {
                stateMachineConfig.getAsyncProcessCtrlEventPublisher().publish(processContext);
            } else {
                stateMachineConfig.getProcessCtrlEventPublisher().publish(processContext);
            }
            return instance;
        } finally {
            if (stateMachineConfig.getStateLogStore() != null) {
                stateMachineConfig.getStateLogStore().clearUp();
            }
        }
    }
    ...
}
```

### (2)发布流程上下文到事件总线的源码

首先通过状态机配置实例stateMachineConfig的getProcessCtrlEventPublisher()方法获取流程控制事件发布器ProcessCtrlEventPublisher，然后通过流程控制事件发布器的publish()方法，将流程上下文ProcessContext发布到Seata的事件总线EventBus中。

#### 一.同步发送流程上下文到事件总线的分析

此时会将流程上下文放入到发布器内部的栈结构中，然后判断如果是栈结构的第一个元素，则使用一个while循环不断从栈结构中弹出流程上下文，调用流程控制事件消费者进行处理。

#### 二.异步发送流程上下文到事件总线的分析

此时会通过线程池去执行调用流程控制事件消费者来处理流程上下文的逻辑。

```java
public class DefaultStateMachineConfig implements StateMachineConfig, ApplicationContextAware, InitializingBean {
    //流程控制的事件发布器(同步发布)
    private ProcessCtrlEventPublisher syncProcessCtrlEventPublisher;

    //流程控制的事件发布器(异步发布)
    private ProcessCtrlEventPublisher asyncProcessCtrlEventPublisher;
    ...

    //因为DefaultStateMachineConfig实现了InitializingBean接口
    //所以继承DefaultStateMachineConfig的Spring Bean初始化之后，就会回调afterPropertiesSet()方法
    @Override
    public void afterPropertiesSet() throws Exception {
        init();
    }

    //初始化方法
    protected void init() throws Exception {
        ...
        //创建流程控制的事件发布器(同步发布)
        if (syncProcessCtrlEventPublisher == null) {
            //创建流程控制的事件发布器
            ProcessCtrlEventPublisher syncEventPublisher = new ProcessCtrlEventPublisher();

            //创建流程控制器
            ProcessControllerImpl processorController = createProcessorController(syncEventPublisher);

            //创建流程控制事件的消费者
            ProcessCtrlEventConsumer processCtrlEventConsumer = new ProcessCtrlEventConsumer();
            processCtrlEventConsumer.setProcessController(processorController);

            //创建事件总线
            DirectEventBus directEventBus = new DirectEventBus();
            syncEventPublisher.setEventBus(directEventBus);
            directEventBus.registerEventConsumer(processCtrlEventConsumer);
            syncProcessCtrlEventPublisher = syncEventPublisher;
        }

        //如果启用了异步化执行 且 流程控制的事件发布器(异步发布)为null
        if (enableAsync && asyncProcessCtrlEventPublisher == null) {
            ProcessCtrlEventPublisher asyncEventPublisher = new ProcessCtrlEventPublisher();
            ProcessControllerImpl processorController = createProcessorController(asyncEventPublisher);
            ProcessCtrlEventConsumer processCtrlEventConsumer = new ProcessCtrlEventConsumer();
            processCtrlEventConsumer.setProcessController(processorController);

            AsyncEventBus asyncEventBus = new AsyncEventBus();
            asyncEventBus.setThreadPoolExecutor(getThreadPoolExecutor());
            asyncEventPublisher.setEventBus(asyncEventBus);
            asyncEventBus.registerEventConsumer(processCtrlEventConsumer);
            asyncProcessCtrlEventPublisher = asyncEventPublisher;
        }
        ...
    }
    ...

    @Override
    public ProcessCtrlEventPublisher getProcessCtrlEventPublisher() {
        return syncProcessCtrlEventPublisher;
    }

    @Override
    public ProcessCtrlEventPublisher getAsyncProcessCtrlEventPublisher() {
        return asyncProcessCtrlEventPublisher;
    }
    ...
}

//ProcessCtrl Event Pulisher
public class ProcessCtrlEventPublisher implements EventPublisher<ProcessContext> {
    private EventBus<ProcessContext> eventBus;

    @Override
    public boolean publish(ProcessContext event) throws FrameworkException {
        return eventBus.offer(event);
    }

    public void setEventBus(EventBus<ProcessContext> eventBus) {
        this.eventBus = eventBus;
    }
}

//同步发布流程上下文到事件总线
public class DirectEventBus extends AbstractEventBus<ProcessContext> {
    private static final Logger LOGGER = LoggerFactory.getLogger(DirectEventBus.class);
    private static final String VAR_NAME_SYNC_EXE_STACK = "_sync_execution_stack_";

    @Override
    public boolean offer(ProcessContext context) throws FrameworkException {
        List<EventConsumer> eventHandlers = getEventConsumers(context.getClass());
        if (CollectionUtils.isEmpty(eventHandlers)) {
            if (LOGGER.isWarnEnabled()) {
                LOGGER.warn("cannot find event handler by class: " + context.getClass());
            }
            return false;
        }

        //将流程上下文放入到其内部的栈结构中
        boolean isFirstEvent = false;
        Stack<ProcessContext> currentStack = (Stack<ProcessContext>)context.getVariable(VAR_NAME_SYNC_EXE_STACK);
        if (currentStack == null) {
            synchronized (context) {
                currentStack = (Stack<ProcessContext>)context.getVariable(VAR_NAME_SYNC_EXE_STACK);
                if (currentStack == null) {
                    currentStack = new Stack<>();
                    context.setVariable(VAR_NAME_SYNC_EXE_STACK, currentStack);
                    isFirstEvent = true;
                }
            }
        }
        currentStack.push(context);

        //如果是栈结构的第一个元素，则开启一个while循环，不断从栈结构中弹出流程上下文，调用流程控制事件消费者进行处理
        if (isFirstEvent) {
            try {
                while (currentStack.size() > 0) {
                    ProcessContext currentContext = currentStack.pop();
                    for (EventConsumer eventHandler : eventHandlers) {
                        eventHandler.process(currentContext);
                    }
                }
            } finally {
                context.removeVariable(VAR_NAME_SYNC_EXE_STACK);
            }
        }
        return true;
    }
}

public abstract class AbstractEventBus<E> implements EventBus<E> {
    private List<EventConsumer> eventConsumerList = new ArrayList<>();

    @Override
    public List<EventConsumer> getEventConsumers(Class clazz) {
        List<EventConsumer> acceptedConsumers = new ArrayList<>();
        for (EventConsumer eventConsumer : eventConsumerList) {
            if (eventConsumer.accept(clazz)) {
                acceptedConsumers.add(eventConsumer);
            }
        }
        return acceptedConsumers;
    }

    @Override
    public void registerEventConsumer(EventConsumer eventConsumer) {
        eventConsumerList.add(eventConsumer);
    }
}

//异步发布流程上下文到事件总线
public class AsyncEventBus extends AbstractEventBus<ProcessContext> {
    private static final Logger LOGGER = LoggerFactory.getLogger(AsyncEventBus.class);
    private ThreadPoolExecutor threadPoolExecutor;

    @Override
    public boolean offer(ProcessContext context) throws FrameworkException {
        List<EventConsumer> eventConsumers = getEventConsumers(context.getClass());
        if (CollectionUtils.isEmpty(eventConsumers)) {
            if (LOGGER.isWarnEnabled()) {
                LOGGER.warn("cannot find event handler by class: " + context.getClass());
            }
            return false;
        }

        //通过线程池去调用流程控制事件消费者来处理流程上下文
        for (EventConsumer eventConsumer : eventConsumers) {
            threadPoolExecutor.execute(() -> eventConsumer.process(context));
        }
        return true;
    }

    public void setThreadPoolExecutor(ThreadPoolExecutor threadPoolExecutor) {
        this.threadPoolExecutor = threadPoolExecutor;
    }
}
```

## 17.通过业务处理器处理状态机当前需要执行的状态

Seata Saga状态机实例的处理流程，其实就是通过流程控制事件消费者处理流程上下文来触发的，也就是调用ProcessCtrlEventConsumer的process()方法时触发的。

在流程处理控制器ProcessController的process()方法中，首先会调用自定义业务处理器CustomizeBusinessProcessor的process()方法来处理状态机当前需要执行的状态State，然后会继续调用自定义业务处理器的route()方法将自定义业务处理器路由到状态机下一个要执行的状态State。

在业务处理器CustomizeBusinessProcessor的process()方法中，会调用状态机流程处理器StateMachineProcessHandler的process()方法，也就是会调用状态处理器ServiceTaskStateHandler的process()方法处理状态。

在ServiceTaskStateHandler的process()方法中，最终会触发调用服务调用组件SpringBeanServiceInvoker的invoke()方法，通过反射机制执行状态机当前State指定的服务方法，最后将执行结果放入流程上下文里的状态机实例中。

如果执行异常，则触发回滚补偿处理。

![图片](assets/ca0360f908a5.png)

```java
//ProcessCtrl Event Consumer
public class ProcessCtrlEventConsumer implements EventConsumer<ProcessContext> {
    private ProcessController processController;

    @Override
    public void process(ProcessContext event) throws FrameworkException {
        //调用流程处理器的process()方法
        processController.process(event);
    }

    @Override
    public boolean accept(Class<ProcessContext> clazz) {
        return ProcessContext.class.isAssignableFrom(clazz);
    }

    public void setProcessController(ProcessController processController) {
        this.processController = processController;
    }
}

//Default implementation of Process controller
//默认的流程处理器
public class ProcessControllerImpl implements ProcessController {
    private static final Logger LOGGER = LoggerFactory.getLogger(ProcessControllerImpl.class);
    private BusinessProcessor businessProcessor;

    @Override
    public void process(ProcessContext context) throws FrameworkException {
        try {
            //1.BusinessProcessor处理状态机当前需要执行的状态State，调用CustomizeBusinessProcessor.process()方法
            businessProcessor.process(context);

            //2.BusinessProcessor路由到状态机的下一个需要执行的状态State，调用CustomizeBusinessProcessor.route()方法
            businessProcessor.route(context);
        } catch (FrameworkException fex) {
            throw fex;
        } catch (Exception ex) {
            LOGGER.error("Unknown exception occurred, context = {}", context, ex);
            throw new FrameworkException(ex, "Unknown exception occurred", FrameworkErrorCode.UnknownAppError);
        }
    }

    public void setBusinessProcessor(BusinessProcessor businessProcessor) {
        this.businessProcessor = businessProcessor;
    }
}

//Customizable Business Processor
public class CustomizeBusinessProcessor implements BusinessProcessor {
    private Map<String, ProcessHandler> processHandlers;
    ...

    @Override
    public void process(ProcessContext context) throws FrameworkException {
        ProcessType processType = matchProcessType(context);
        if (processType == null) {
            if (LOGGER.isWarnEnabled()) {
                LOGGER.warn("Process type not found, context= {}", context);
            }
            throw new FrameworkException(FrameworkErrorCode.ProcessTypeNotFound);
        }

        ProcessHandler processor = processHandlers.get(processType.getCode());
        if (processor == null) {
            LOGGER.error("Cannot find process handler by type {}, context= {}", processType.getCode(), context);
            throw new FrameworkException(FrameworkErrorCode.ProcessHandlerNotFound);
        }

        //调用StateMachineProcessHandler.process()方法处理
        processor.process(context);
    }

    @Override
    public void route(ProcessContext context) throws FrameworkException {
        ProcessType processType = matchProcessType(context);
        if (processType == null) {
            if (LOGGER.isWarnEnabled()) {
                LOGGER.warn("Process type not found, the process is no longer advanced, context= {}", context);
            }
            return;
        }

        RouterHandler router = routerHandlers.get(processType.getCode());
        if (router == null) {
            LOGGER.error("Cannot find router handler by type {}, context= {}", processType.getCode(), context);
            return;
        }

        //先调用DefaultRouterHandler的route()方法
        //再调用StateMachineProcessRouter.route()方法，将StateInstruction路由到下一个State
        router.route(context);
    }
    ...
}

public class StateMachineProcessHandler implements ProcessHandler {
    private final Map<String, StateHandler> stateHandlers = new ConcurrentHashMap<>();

    @Override
    public void process(ProcessContext context) throws FrameworkException {
        //获取状态处理器StateHandler后，调用stateHandler.process()进行状态的业务逻辑处理
        StateInstruction instruction = context.getInstruction(StateInstruction.class);
        State state = instruction.getState(context);
        String stateType = state.getType();
        StateHandler stateHandler = stateHandlers.get(stateType);
        List<StateHandlerInterceptor> interceptors = null;
        if (stateHandler instanceof InterceptableStateHandler) {
            interceptors = ((InterceptableStateHandler)stateHandler).getInterceptors();
        }

        //获取状态拦截器StateHandlerInterceptor后，
        //调用interceptor.preProcess()进行预处理，调用interceptor.postProcess()进行后置处理
        List<StateHandlerInterceptor> executedInterceptors = null;
        Exception exception = null;
        try {
            if (CollectionUtils.isNotEmpty(interceptors)) {
                executedInterceptors = new ArrayList<>(interceptors.size());
                for (StateHandlerInterceptor interceptor : interceptors) {
                    executedInterceptors.add(interceptor);
                    interceptor.preProcess(context);
                }
            }
            //调用ServiceTaskStateHandler的process()方法
            stateHandler.process(context);
        } catch (Exception e) {
            exception = e;
            throw e;
        } finally {
            if (CollectionUtils.isNotEmpty(executedInterceptors)) {
                for (int i = executedInterceptors.size() - 1; i >= 0; i--) {
                    StateHandlerInterceptor interceptor = executedInterceptors.get(i);
                    interceptor.postProcess(context, exception);
                }
            }
        }
    }
    ...
}

public class ServiceTaskStateHandler implements StateHandler, InterceptableStateHandler {
    private static final Logger LOGGER = LoggerFactory.getLogger(ServiceTaskStateHandler.class);
    private List<StateHandlerInterceptor> interceptors = new ArrayList<>();

    @Override
    public void process(ProcessContext context) throws EngineExecutionException {
        StateInstruction instruction = context.getInstruction(StateInstruction.class);
        ServiceTaskStateImpl state = (ServiceTaskStateImpl) instruction.getState(context);
        String serviceName = state.getServiceName();
        String methodName = state.getServiceMethod();
        StateInstance stateInstance = (StateInstance) context.getVariable(DomainConstants.VAR_NAME_STATE_INST);
        Object result;

        try {
            List<Object> input = (List<Object>) context.getVariable(DomainConstants.VAR_NAME_INPUT_PARAMS);
            //Set the current task execution status to RU (Running)
            stateInstance.setStatus(ExecutionStatus.RU);
            if (LOGGER.isDebugEnabled()) {
                LOGGER.debug(">>>>>>>>>>>>>>>>>>>>>> Start to execute State[{}], ServiceName[{}], Method[{}], Input:{}", state.getName(), serviceName, methodName, input);
            }

            if (state instanceof CompensateSubStateMachineState) {
                //If it is the compensation of the substate machine,
                //directly call the state machine's compensate method
                result = compensateSubStateMachine(context, state, input, stateInstance, (StateMachineEngine) context.getVariable(DomainConstants.VAR_NAME_STATEMACHINE_ENGINE));
            } else {
                StateMachineConfig stateMachineConfig = (StateMachineConfig) context.getVariable(DomainConstants.VAR_NAME_STATEMACHINE_CONFIG);
                //1.获取服务调用组件ServiceInvoker
                ServiceInvoker serviceInvoker = stateMachineConfig.getServiceInvokerManager().getServiceInvoker(state.getServiceType());
                if (serviceInvoker == null) {
                    throw new EngineExecutionException("No such ServiceInvoker[" + state.getServiceType() + "]", FrameworkErrorCode.ObjectNotExists);
                }
                if (serviceInvoker instanceof ApplicationContextAware) {
                    ((ApplicationContextAware) serviceInvoker).setApplicationContext(stateMachineConfig.getApplicationContext());
                }
                //2.调用SpringBeanServiceInvoker的invoke()方法
                result = serviceInvoker.invoke(state, input.toArray());
            }

            if (LOGGER.isDebugEnabled()) {
                LOGGER.debug("<<<<<<<<<<<<<<<<<<<<<< State[{}], ServiceName[{}], Method[{}] Execute finish. result: {}", state.getName(), serviceName, methodName, result);
            }

            if (result != null) {
                //3.将执行结果放入流程上下文里的状态机实例中
                stateInstance.setOutputParams(result);
                ((HierarchicalProcessContext) context).setVariableLocally(DomainConstants.VAR_NAME_OUTPUT_PARAMS, result);
            }
        } catch (Throwable e) {
            LOGGER.error("<<<<<<<<<<<<<<<<<<<<<< State[{}], ServiceName[{}], Method[{}] Execute failed.", state.getName(), serviceName, methodName, e);
            ((HierarchicalProcessContext) context).setVariableLocally(DomainConstants.VAR_NAME_CURRENT_EXCEPTION, e);
            //如果执行异常，下面的调用会获取触发异常的State，然后进行回滚补偿处理
            EngineUtils.handleException(context, state, e);
        }
    }
    ...
}
```

## 18.通过服务调用组件来执行State指定的服务方法

执行服务调用组件SpringBeanServiceInvoker的invoke()方法时，如果State需要异步执行，那么会通过线程池来异步执行doInvoke()方法。其中，doInvoke()方法首先会获取状态State的服务对应的Spring Bean，然后通过反射执行Bean的指定Method。如果出现异常，则会进行重试处理。

```java
public class SpringBeanServiceInvoker implements ServiceInvoker, ApplicationContextAware {
    private ApplicationContext applicationContext;
    private ThreadPoolExecutor threadPoolExecutor;
    ...

    @Override
    public Object invoke(ServiceTaskState serviceTaskState, Object... input) throws Throwable {
        ServiceTaskStateImpl state = (ServiceTaskStateImpl) serviceTaskState;
        //如果State需要异步执行，那么就通过线程池来执行
        if (state.isAsync()) {
            if (threadPoolExecutor == null) {
                if (LOGGER.isWarnEnabled()) {
                    LOGGER.warn("threadPoolExecutor is null, Service[{}.{}] cannot execute asynchronously, executing " + "synchronously now. stateName: {}", state.getServiceName(), state.getServiceMethod(), state.getName());
                }
                return doInvoke(state, input);
            }

            if (LOGGER.isInfoEnabled()) {
                LOGGER.info("Submit Service[{}.{}] to asynchronously executing. stateName: {}", state.getServiceName(), state.getServiceMethod(), state.getName());
            }

            threadPoolExecutor.execute(new Runnable() {
                @Override
                public void run() {
                    try {
                        doInvoke(state, input);
                    } catch (Throwable e) {
                        LOGGER.error("Invoke Service[" + state.getServiceName() + "." + state.getServiceMethod() + "] failed.", e);
                    }
                }
            });
            return null;
        } else {
            return doInvoke(state, input);
        }
    }

    protected Object doInvoke(ServiceTaskStateImpl state, Object[] input) throws Throwable {
        //获取状态State的服务对应的Spring Bean
        Object bean = applicationContext.getBean(state.getServiceName());

        //获取状态State的方法
        Method method = state.getMethod();
        if (method == null) {
            synchronized (state) {
                method = state.getMethod();
                if (method == null) {
                    method = findMethod(bean.getClass(), state.getServiceMethod(), state.getParameterTypes());
                    if (method != null) {
                        state.setMethod(method);
                    }
                }
            }
        }

        if (method == null) {
            throw new EngineExecutionException("No such method[" + state.getServiceMethod() + "] on BeanClass[" + bean.getClass() + "]", FrameworkErrorCode.NoSuchMethod);
        }

        Object[] args = new Object[method.getParameterCount()];
        try {
            Class[] paramTypes = method.getParameterTypes();
            if (input != null && input.length > 0) {
                int len = input.length < paramTypes.length ? input.length : paramTypes.length;
                for (int i = 0; i < len; i++) {
                    args[i] = toJavaObject(input[i], paramTypes[i]);
                }
            }
        } catch (Exception e) {
            throw new EngineExecutionException(e, "Input to java object error, Method[" + state.getServiceMethod() + "] on BeanClass[" + bean.getClass() + "]", FrameworkErrorCode.InvalidParameter);
        }

        if (!Modifier.isPublic(method.getModifiers())) {
            throw new EngineExecutionException("Method[" + method.getName() + "] must be public", FrameworkErrorCode.MethodNotPublic);
        }

        Map<Retry, AtomicInteger> retryCountMap = new HashMap<>();
        while (true) {
            try {
                //通过反射去调用State中配置的服务和方法
                return invokeMethod(bean, method, args);
            } catch (Throwable e) {
                //重试处理
                Retry matchedRetryConfig = matchRetryConfig(state.getRetry(), e);
                if (matchedRetryConfig == null) {
                    throw e;
                }

                AtomicInteger retryCount = CollectionUtils.computeIfAbsent(retryCountMap, matchedRetryConfig, key -> new AtomicInteger(0));
                if (retryCount.intValue() >= matchedRetryConfig.getMaxAttempts()) {
                    throw e;
                }

                double intervalSeconds = matchedRetryConfig.getIntervalSeconds();
                double backoffRate = matchedRetryConfig.getBackoffRate();
                long currentInterval = (long) (retryCount.intValue() > 0 ? (intervalSeconds * backoffRate * retryCount.intValue() * 1000) : (intervalSeconds * 1000));
                if (LOGGER.isWarnEnabled()) {
                    LOGGER.warn("Invoke Service[" + state.getServiceName() + "." + state.getServiceMethod() + "] failed, will retry after " + currentInterval + " millis, current retry count: " + retryCount.intValue(), e);
                }

                try {
                    Thread.sleep(currentInterval);
                } catch (InterruptedException e1) {
                    LOGGER.warn("Retry interval sleep error", e1);
                }
                retryCount.incrementAndGet();
            }
        }
    }

    protected Object invokeMethod(Object serviceBean, Method method, Object... input) throws Throwable {
        try {
            return method.invoke(serviceBean, input);
        } catch (InvocationTargetException e) {
            Throwable targetExp = e.getTargetException();
            if (targetExp == null) {
                throw new EngineExecutionException(e, e.getMessage(), FrameworkErrorCode.MethodInvokeError);
            }
            throw targetExp;
        }
    }
    ...
}
```

## 19.将业务处理器路由到状态机下一个要执行的状态

在流程处理控制器ProcessController的process()方法中，会调用自定义的业务处理器CustomizeBusinessProcessor的route()方法，将自定义业务处理器路由到状态机下一个需要执行的状态State。

CustomizeBusinessProcessor的route()方法，首先会调用DefaultRouterHandler的route()方法，然后再调用StateMachineProcessRouter的route()方法，将状态操作组件StateInstruction的状态名字设置为下一个State。

在DefaultRouterHandler的route()方法中，首先会调用StateMachineProcessRouter的route()方法，也就是调用TaskStateRouter的route()方法，将状态操作组件StateInstruction的状态名字设置为下一个State。然后将状态操作组件StateInstruction设置到流程上下文中，接着再将流程上下文ProcessContext发布到事件总线，继续由流程控制事件消费者进行消费处理。

![图片](assets/dfd6d2a2ff9b.png)

```java
//Default implementation of Process controller
//默认的流程处理器
public class ProcessControllerImpl implements ProcessController {
    private static final Logger LOGGER = LoggerFactory.getLogger(ProcessControllerImpl.class);
    private BusinessProcessor businessProcessor;

    @Override
    public void process(ProcessContext context) throws FrameworkException {
        try {
            //1.BusinessProcessor处理状态机当前需要执行的状态State，调用CustomizeBusinessProcessor.process()方法
            businessProcessor.process(context);

            //2.BusinessProcessor路由到状态机下一个需要执行的状态State，调用CustomizeBusinessProcessor.route()方法
            businessProcessor.route(context);
        } catch (FrameworkException fex) {
            throw fex;
        } catch (Exception ex) {
            LOGGER.error("Unknown exception occurred, context = {}", context, ex);
            throw new FrameworkException(ex, "Unknown exception occurred", FrameworkErrorCode.UnknownAppError);
        }
    }

    public void setBusinessProcessor(BusinessProcessor businessProcessor) {
        this.businessProcessor = businessProcessor;
    }
}

//Customizable Business Processor
public class CustomizeBusinessProcessor implements BusinessProcessor {
    private Map<String, ProcessHandler> processHandlers;
    ...

    @Override
    public void route(ProcessContext context) throws FrameworkException {
        ProcessType processType = matchProcessType(context);
        if (processType == null) {
            if (LOGGER.isWarnEnabled()) {
                LOGGER.warn("Process type not found, the process is no longer advanced, context= {}", context);
            }
            return;
        }

        RouterHandler router = routerHandlers.get(processType.getCode());
        if (router == null) {
            LOGGER.error("Cannot find router handler by type {}, context= {}", processType.getCode(), context);
            return;
        }

        //先调用DefaultRouterHandler的route()方法
        //再调用StateMachineProcessRouter.route()方法，将StateInstruction路由到下一个State
        router.route(context);
    }
    ...
}

public class DefaultRouterHandler implements RouterHandler {
    private EventPublisher<ProcessContext> eventPublisher;
    private Map<String, ProcessRouter> processRouters;

    public static ProcessType matchProcessType(ProcessContext context) {
        ProcessType processType = (ProcessType)context.getVariable(ProcessContext.VAR_NAME_PROCESS_TYPE);
        if (processType == null) {
            processType = ProcessType.STATE_LANG;
        }
        return processType;
    }

    @Override
    public void route(ProcessContext context) throws FrameworkException {
        try {
            ProcessType processType = matchProcessType(context);
            if (processType == null) {
                if (LOGGER.isWarnEnabled()) {
                    LOGGER.warn("Process type not found, context= {}", context);
                }
                throw new FrameworkException(FrameworkErrorCode.ProcessTypeNotFound);
            }

            ProcessRouter processRouter = processRouters.get(processType.getCode());
            if (processRouter == null) {
                LOGGER.error("Cannot find process router by type {}, context = {}", processType.getCode(), context);
                throw new FrameworkException(FrameworkErrorCode.ProcessRouterNotFound);
            }

            //1.调用StateMachineProcessRouter.route()方法，将StateInstruction路由到下一个State
            Instruction instruction = processRouter.route(context);
            if (instruction == null) {
                LOGGER.info("route instruction is null, process end");
            } else {
                //2.将流程上下文ProcessContext发布到事件总线，继续由流程控制事件消费者进行消费处理
                context.setInstruction(instruction);
                eventPublisher.publish(context);
            }
        } catch (FrameworkException e) {
            throw e;
        } catch (Exception ex) {
            throw new FrameworkException(ex, ex.getMessage(), FrameworkErrorCode.UnknownAppError);
        }
    }

    public void setEventPublisher(EventPublisher<ProcessContext> eventPublisher) {
        this.eventPublisher = eventPublisher;
    }

    public void setProcessRouters(Map<String, ProcessRouter> processRouters) {
        this.processRouters = processRouters;
    }
}

public class StateMachineProcessRouter implements ProcessRouter {
    private final Map<String, StateRouter> stateRouters = new ConcurrentHashMap<>();

    @Override
    public Instruction route(ProcessContext context) throws FrameworkException {
        StateInstruction stateInstruction = context.getInstruction(StateInstruction.class);
        State state;
        if (stateInstruction.getTemporaryState() != null) {
            state = stateInstruction.getTemporaryState();
            stateInstruction.setTemporaryState(null);
        } else {
            StateMachineConfig stateMachineConfig = (StateMachineConfig)context.getVariable(DomainConstants.VAR_NAME_STATEMACHINE_CONFIG);
            StateMachine stateMachine = stateMachineConfig.getStateMachineRepository().getStateMachine(stateInstruction.getStateMachineName(), stateInstruction.getTenantId());
            state = stateMachine.getStates().get(stateInstruction.getStateName());
        }

        String stateType = state.getType();
        StateRouter router = stateRouters.get(stateType);
        Instruction instruction = null;
        List<StateRouterInterceptor> interceptors = null;
        if (router instanceof InterceptableStateRouter) {
            interceptors = ((InterceptableStateRouter)router).getInterceptors();
        }
        List<StateRouterInterceptor> executedInterceptors = null;

        Exception exception = null;
        try {
            if (CollectionUtils.isNotEmpty(interceptors)) {
                executedInterceptors = new ArrayList<>(interceptors.size());
                for (StateRouterInterceptor interceptor : interceptors) {
                    executedInterceptors.add(interceptor);
                    interceptor.preRoute(context, state);
                }
            }
            //调用TaskStateRouter的route()方法
            instruction = router.route(context, state);
        } catch (Exception e) {
            exception = e;
            throw e;
        } finally {
            if (CollectionUtils.isNotEmpty(executedInterceptors)) {
                for (int i = executedInterceptors.size() - 1; i >= 0; i--) {
                    StateRouterInterceptor interceptor = executedInterceptors.get(i);
                    interceptor.postRoute(context, state, instruction, exception);
                }
            }
            //if 'Succeed' or 'Fail' State did not configured, we must end the state machine
            if (instruction == null && !stateInstruction.isEnd()) {
                EngineUtils.endStateMachine(context);
            }
        }
        return instruction;
    }
    ...
}

public class TaskStateRouter implements StateRouter {
    @Override
    public Instruction route(ProcessContext context, State state) throws EngineExecutionException {
        StateInstruction stateInstruction = context.getInstruction(StateInstruction.class);
        if (stateInstruction.isEnd()) {
            if (LOGGER.isInfoEnabled()) {
                LOGGER.info("StateInstruction is ended, Stop the StateMachine executing. StateMachine[{}] Current State[{}]", stateInstruction.getStateMachineName(), state.getName());
            }
            return null;
        }

        //check if in loop async condition
        if (Boolean.TRUE.equals(context.getVariable(DomainConstants.VAR_NAME_IS_LOOP_STATE))) {
            return null;
        }

        //The current CompensationTriggerState can mark the compensation process is started and perform compensation route processing.
        State compensationTriggerState = (State)context.getVariable(DomainConstants.VAR_NAME_CURRENT_COMPEN_TRIGGER_STATE);
        if (compensationTriggerState != null) {
            return compensateRoute(context, compensationTriggerState);
        }

        //There is an exception route, indicating that an exception is thrown, and the exception route is prioritized.
        String next = (String)context.getVariable(DomainConstants.VAR_NAME_CURRENT_EXCEPTION_ROUTE);

        if (StringUtils.hasLength(next)) {
            context.removeVariable(DomainConstants.VAR_NAME_CURRENT_EXCEPTION_ROUTE);
        } else {
            //获取状态State的下一个状态名字
            next = state.getNext();
        }

        //If next is empty, the state selected by the Choice state was taken.
        if (!StringUtils.hasLength(next) && context.hasVariable(DomainConstants.VAR_NAME_CURRENT_CHOICE)) {
            next = (String)context.getVariable(DomainConstants.VAR_NAME_CURRENT_CHOICE);
            context.removeVariable(DomainConstants.VAR_NAME_CURRENT_CHOICE);
        }
        if (!StringUtils.hasLength(next)) {
            return null;
        }

        //根据下一个状态名字获取状态State
        StateMachine stateMachine = state.getStateMachine();
        State nextState = stateMachine.getState(next);
        if (nextState == null) {
            throw new EngineExecutionException("Next state[" + next + "] is not exits", FrameworkErrorCode.ObjectNotExists);
        }

        //将下一个状态名字设置到状态操作组件stateInstruction中
        stateInstruction.setStateName(next);
        if (null != LoopTaskUtils.getLoopConfig(context, nextState)) {
            stateInstruction.setTemporaryState(new LoopStartStateImpl());
        }
        return stateInstruction;
    }
    ...
}
```
