# zk源码—5.请求的处理过程

> **公众号**: 东阳马生架构  
> **发布时间**: 2025-04-11 23:15  

**大纲(26860字)**

- 1.服务器的请求处理链


### (1)Leader服务器的请求处理链

#### 一.PrepRequestProcessor请求预处理器

#### 二.ProposalRequestProcessor事务投票处理器

#### 三.SyncRequestProcessor事务日志处理器

#### 四.AckRequestProcessor投票反馈处理器

#### 五.CommitProcessor事务提交处理器

#### 六.ToBeAppliedRequestProcessor处理器

#### 七.FinalRequestProcessor处理器

### (2)Follower服务器的请求处理链

#### 一.FollowerRequestProcessor请求转发处理器

#### 二.SendAckRequestProcessor投票反馈处理器

2.服务端处理会话创建请求的流程

### (1)请求接收

### (2)会话创建

### (3)请求预处理

### (4)事务处理

### (5)事务应用和响应

## 1.服务器的请求处理链

### (1)Leader服务器的请求处理链

### (2)Follower服务器的请求处理链

### (1)Leader服务器的请求处理链

#### 一.PrepRequestProcessor请求预处理器

#### 二.ProposalRequestProcessor事务投票处理器

#### 三.SyncRequestProcessor事务日志处理器

#### 四.AckRequestProcessor投票反馈处理器

#### 五.CommitProcessor事务提交处理器

#### 六.ToBeAppliedRequestProcessor处理器

#### 七.FinalRequestProcessor处理器

当客户端需要和zk服务端进行相互协调通信时，首先要通过Leader服务器建立该客户端与服务端的连接会话。当会话创建成功后，zk服务端就可以接收来自客户端的请求操作了。

Leader服务器是zk集群的核心，其主要工作是：

工作一：处理事务请求，保证集群事务处理的顺序性

工作二：集群内各服务器的调度者

zk服务端会使用责任链模式来处理每一个客户端的请求。在服务端启动时，会进行请求处理链的初始化。Leader服务器的请求处理链如下图示，主要有7个请求处理器。

![图片](assets/b3b5050b396c.png)

#### 一.PrepRequestProcessor请求预处理器

zk中的事务请求就是会改变服务器状态的请求。事务请求包括创建节点、更新节点、删除节点、创建会话等请求。

PrepRequestProcessor是Leader服务器的请求预处理器(Prepare)，它能够识别出当前客户端请求是否是事务请求，它会对事务请求进行一系列的预处理操作。这些预处理包括：创建请求事务头事务体、会话检查、ACL检查等。

PrepRequestProcessor实现了RequestProcessor接口并继承了zk线程，而且还有一个RequestProcessor类型的nextProcessor属性字段，nextProcessor属性字段的作用是指向下一个请求处理器。

Leader服务器在开始处理请求时，会调用PrepRequestProcessor的processRequest()方法将请求添加到队列。请求预处理器的线程启动后会不断从submittedRequests队列取出请求，然后把请求交给PrepRequestProcessor的pRequest()方法进行预处理。在pRequest()方法中，会根据请求类型来判断请求是否是事务请求。如果是事务请求，就调用pRequest2Txn()方法对事务请求进行预处理。之后再将请求交给nextProcessor属性字段指向的处理器进行下一步处理。

PrepRequestProcessor处理器也是一个线程，它会先把请求添加到队列，然后由线程进行处理。

PrepRequestProcessor的nextProcessor属性指向的是ProposalRequestProcessor处理器。

```java
public class QuorumPeer extends ZooKeeperThread implements QuorumStats.Provider {
    ...
    protected Leader makeLeader(FileTxnSnapLog logFactory) throws IOException, X509Exception {
        return new Leader(this, new LeaderZooKeeperServer(logFactory, this, this.zkDb));
    }
    ...
}

public class LeaderZooKeeperServer extends QuorumZooKeeperServer {
    CommitProcessor commitProcessor;
    PrepRequestProcessor prepRequestProcessor;
    ...
    //初始化请求处理链
    @Override
    protected void setupRequestProcessors() {
        RequestProcessor finalProcessor = new FinalRequestProcessor(this);
        RequestProcessor toBeAppliedProcessor = new Leader.ToBeAppliedRequestProcessor(finalProcessor, getLeader());
        commitProcessor = new CommitProcessor(toBeAppliedProcessor, Long.toString(getServerId()), false, getZooKeeperServerListener());
        commitProcessor.start();
        ProposalRequestProcessor proposalProcessor = new ProposalRequestProcessor(this, commitProcessor);
        proposalProcessor.initialize();
        prepRequestProcessor = new PrepRequestProcessor(this, proposalProcessor);
        prepRequestProcessor.start();//启动请求预处理器线程
        firstProcessor = new LeaderRequestProcessor(this, prepRequestProcessor);
        setupContainerManager();
    }
    ...
}

public class PrepRequestProcessor extends ZooKeeperCriticalThread implements RequestProcessor {
    RequestProcessor nextProcessor;
    LinkedBlockingQueue<Request> submittedRequests = new LinkedBlockingQueue<Request>();

    public void processRequest(Request request) {
        //将请求添加到队列
        submittedRequests.add(request);
    }
    ...
    @Override
    public void run() {
        while (true) {
            Request request = submittedRequests.take();
            ...
            pRequest(request);
        }
    }

    protected void pRequest(Request request) throws RequestProcessorException {
        request.setHdr(null);
        request.setTxn(null);
        switch (request.type) {
            ...
            case OpCode.create:
                CreateRequest createRequest = new CreateRequest();
                pRequest2Txn(request.type, zks.getNextZxid(), request,createRequest, true);
                break;
            case OpCode.delete:
                ...
        }
        ...
        request.zxid = zks.getZxid();
        //将请求交给下一个处理器来处理
        nextProcessor.processRequest(request);
    }

    //下面这个方法专门用来对事务请求进行预处理
    protected void pRequest2Txn(int type, long zxid, Request request, Record record, boolean deserialize) {
        //设置请求的事务头事务体
        request.setHdr(new TxnHeader(request.sessionId, request.cxid, zxid, Time.currentWallTime(), type));
        ...
    }
    ...
}
```

有两个入口会触发调用PrepRequestProcessor的processRequest()方法。

第一是Leader服务器监听到Learner转发给Leader的事务请求。也就是在不断运行的LearnerHandler线程中发现Learner给Leader发送请求时，会调用LeaderZooKeeperServer.submitLearnerRequest方法来触发。

第二是zk服务端监听到的来自客户端的事务请求。此时会先调用ZooKeeperServer的processPacket()方法处理Socket的读请求，然后再调用ZooKeeperServer的submitRequest()方法提交读请求，最后就会调用ZooKeeperServer的firstProcessor的processRequest()方法。firstProcessor的processRequest()方法执行完便进入PrepRequestProcessor。

```java
//第一个入口
public class Leader {
    ...
    void lead() throws IOException, InterruptedException {
        ...
        cnxAcceptor = new LearnerCnxAcceptor();
        cnxAcceptor.start();
        ...
    }

    class LearnerCnxAcceptor extends ZooKeeperCriticalThread {
        ...
        @Override
        public void run() {
            while (!stop) {
                Socket s = ss.accept();
                s.setSoTimeout(self.tickTime * self.initLimit);
                s.setTcpNoDelay(nodelay);
                BufferedInputStream is = new BufferedInputStream(s.getInputStream());
                LearnerHandler fh = new LearnerHandler(s, is, Leader.this);
                fh.start();
                ...
            }
            ...
        }
    }
    ...
}

public class LearnerHandler extends ZooKeeperThread {
    ...
    @Override
    public void run() {
        ...
        while (true) {
            ...
            case Leader.REQUEST:
                ...
                //调用LeaderZooKeeperServer的submitLearnerRequest方法
                leader.zk.submitLearnerRequest(si);
            ...
        }
        ...
    }
    ...
}

public class LeaderZooKeeperServer extends QuorumZooKeeperServer {
    PrepRequestProcessor prepRequestProcessor;
    ...
    @Override
    protected void setupRequestProcessors() {
        ...
        prepRequestProcessor = new PrepRequestProcessor(this, proposalProcessor);
        prepRequestProcessor.start();
        firstProcessor = new LeaderRequestProcessor(this, prepRequestProcessor);
        ...
    }

    public void submitLearnerRequest(Request request) {
        prepRequestProcessor.processRequest(request);
    }
    ...
}

//第二个入口
public class NIOServerCnxnFactory extends ServerCnxnFactory {
    ...
    class SelectorThread extends AbstractSelectThread {
        @Override
        public void run() {
            ...
            while (!stopped) {
                select();
                ...
            }
            ...
        }

        private void select() {
            selector.select();
            Set<SelectionKey> selected = selector.selectedKeys();
            ArrayList<SelectionKey> selectedList = new ArrayList<SelectionKey>(selected);
            Collections.shuffle(selectedList);
            Iterator<SelectionKey> selectedKeys = selectedList.iterator();

            while (!stopped && selectedKeys.hasNext()) {
                SelectionKey key = selectedKeys.next();
                selected.remove(key);
                ...
                if (key.isReadable() || key.isWritable()) {
                    //服务端从客户端读数据(读取请求) + 服务端向客户端写数据(发送响应)
                    handleIO(key);
                }
                ...
            }
        }

        private void handleIO(SelectionKey key) {
            IOWorkRequest workRequest = new IOWorkRequest(this, key);
            NIOServerCnxn cnxn = (NIOServerCnxn) key.attachment();
            cnxn.disableSelectable();
            key.interestOps(0);
            //激活连接：添加连接到连接过期队列
            touchCnxn(cnxn);
            //通过工作线程池来处理请求
            workerPool.schedule(workRequest);
        }
        ...
    }

    private class IOWorkRequest extends WorkerService.WorkRequest {
        private final NIOServerCnxn cnxn;

        public void doWork() throws InterruptedException {
            ...
            if (key.isReadable() || key.isWritable()) {
                cnxn.doIO(key);
                ...
            }
        }
        ...
    }
}

public class WorkerService {
    ...
    public void schedule(WorkRequest workRequest, long id) {
        ScheduledWorkRequest scheduledWorkRequest = new ScheduledWorkRequest(workRequest);
        int size = workers.size();
        if (size > 0) {
            int workerNum = ((int) (id % size) + size) % size;
            ExecutorService worker = workers.get(workerNum);
            worker.execute(scheduledWorkRequest);
        } else {
            scheduledWorkRequest.run();
        }
    }

    private class ScheduledWorkRequest implements Runnable {
        private final WorkRequest workRequest;

        ScheduledWorkRequest(WorkRequest workRequest) {
            this.workRequest = workRequest;
        }

        @Override
        public void run() {
            ...
            workRequest.doWork();
        }
    }
    ...
}

public class NIOServerCnxn extends ServerCnxn {
    private final ZooKeeperServer zkServer;

    void doIO(SelectionKey k) throws InterruptedException {
        ...
        if (k.isReadable()) {
            ...
            readPayload();
        }
    }

    private void readPayload() throws IOException, InterruptedException {
        ...
        readRequest();
    }

    private void readRequest() throws IOException {
        //处理输入流
        zkServer.processPacket(this, incomingBuffer);
    }
    ...
}

public class ZooKeeperServer implements SessionExpirer, ServerStats.Provider {
    ...
    public void processPacket(ServerCnxn cnxn, ByteBuffer incomingBuffer) throws IOException {
        InputStream bais = new ByteBufferInputStream(incomingBuffer);
        BinaryInputArchive bia = BinaryInputArchive.getArchive(bais);
        RequestHeader h = new RequestHeader();
        h.deserialize(bia, "header");
        incomingBuffer = incomingBuffer.slice();
        ...
        Request si = new Request(cnxn, cnxn.getSessionId(), h.getXid(), h.getType(), incomingBuffer, cnxn.getAuthInfo());
        submitRequest(si);
        ...
    }

    public void submitRequest(Request si) {
        ...
        //激活会话
        touch(si.cnxn);
        //firstProcessor.processRequest方法执行完便进入PrepRequestProcessor
        firstProcessor.processRequest(si);
        ...
    }
    ...
}
```

#### 二.ProposalRequestProcessor事务投票处理器

ProposalRequestProcessor处理器是Leader服务器的事务投票处理器。它是PrepRequestProcessor请求预处理器的下一个处理器，它的主要作用是对事务请求进行处理，包括创建提议、发起投票。

对于非事务请求：它会将请求直接交给CommitProcessor处理器处理，不再做其他处理。

对于事务请求：除了将请求交给CommitProcessor处理器外，还会创建请求对应的Proposal提议，并将Proposal提议发送给所有Follower来发起一次集群内的事务投票，同时还会将事务请求交给SyncRequestProcessor处理器来记录事务日志。

提议是指：当处理一个事务请求时，zk会先在服务端发起一次投票流程。该投票的主要作用是通知zk服务端的各机器处理事务请求，从而避免因某个机器出现问题而造成事务不一致的问题。

ProposalRequestProcessor事务投票处理器的三个子流程分别是：Commit流程、Proposal流程、Sync流程。

流程一：Commit流程

完成Proposal流程后，zk服务器上的数据还没有进行任何改变。完成Proposal流程只是说明zk服务端可以执行事务请求操作了，真正执行具体数据的变更需要在Commit流程中实现。Commit流程的主要作用就是完成请求的执行。该流程是由CommitProcessor处理器来实现的。

流程二：Proposal流程

处理事务请求时，zk要取得集群中过半机器的投票才能修改数据。Proposal流程的主要工作就是投票和统计投票结果。

流程三：Sync流程

Sync流程是由SyncRequestProcessor处理器来实现的。

ProposalRequestProcessor处理器不是一个线程，它的nextProcessor就是CommitProcessor处理器，它会调用SyncRequestProcessor处理器的processRequest()方法；

```java
public class LeaderZooKeeperServer extends QuorumZooKeeperServer {
    ...
    @Override
    protected void setupRequestProcessors() {
        RequestProcessor finalProcessor = new FinalRequestProcessor(this);
        RequestProcessor toBeAppliedProcessor = new Leader.ToBeAppliedRequestProcessor(finalProcessor, getLeader());
        commitProcessor = new CommitProcessor(toBeAppliedProcessor, Long.toString(getServerId()), false, getZooKeeperServerListener());
        commitProcessor.start();
        //构建ProposalRequestProcessor处理器，下一个处理器为CommitProcessor处理器
        ProposalRequestProcessor proposalProcessor = new ProposalRequestProcessor(this, commitProcessor);
        proposalProcessor.initialize();//初始化ProposalRequestProcessor处理器
        prepRequestProcessor = new PrepRequestProcessor(this, proposalProcessor);
        prepRequestProcessor.start();
        firstProcessor = new LeaderRequestProcessor(this, prepRequestProcessor);
        setupContainerManager();
    }
    ...
}

//ProposalRequestProcessor的nextProcessor就是CommitProcessor
public class ProposalRequestProcessor implements RequestProcessor {
    LeaderZooKeeperServer zks;
    RequestProcessor nextProcessor;//nextProcessor其实就是CommitProcessor处理器
    SyncRequestProcessor syncProcessor;//事务日志处理器，它的下一个处理器是AckRequestProcessor

    public ProposalRequestProcessor(LeaderZooKeeperServer zks, RequestProcessor nextProcessor) {
        this.zks = zks;
        this.nextProcessor = nextProcessor;
        AckRequestProcessor ackProcessor = new AckRequestProcessor(zks.getLeader());
        //创建事务日志处理器，它的下一个处理器是AckRequestProcessor
        syncProcessor = new SyncRequestProcessor(zks, ackProcessor);
    }

    //初始化ProposalRequestProcessor处理器
    public void initialize() {
        syncProcessor.start();//启动事务日志处理器的线程
    }

    public void processRequest(Request request) throws RequestProcessorException {
        if (request instanceof LearnerSyncRequest) {
            //处理Learner的数据同步请求
            zks.getLeader().processSync((LearnerSyncRequest)request);
        } else {
            //Commit流程，nextProcessor其实就是CommitProcessor处理器
            nextProcessor.processRequest(request);
            if (request.getHdr() != null) {
                //Proposal流程
                zks.getLeader().propose(request);
                //Sync流程，将请求添加到队列，然后由事务日志处理器线程去处理
                syncProcessor.processRequest(request);
            }
        }
    }
    ...
}

public class Leader {
    final ConcurrentMap<Long, Proposal> outstandingProposals = new ConcurrentHashMap<Long, Proposal>();
    ...
    public Proposal propose(Request request) throws XidRolloverException {
        ...
        byte[] data = SerializeUtils.serializeRequest(request);
        proposalStats.setLastBufferSize(data.length);
        QuorumPacket pp = new QuorumPacket(Leader.PROPOSAL, request.zxid, data, null);
        //生成Proposal提议
        Proposal p = new Proposal();
        p.packet = pp;
        p.request = request;

        synchronized(this) {
            p.addQuorumVerifier(self.getQuorumVerifier());
            if (request.getHdr().getType() == OpCode.reconfig) {
                self.setLastSeenQuorumVerifier(request.qv, true);
            }
            if (self.getQuorumVerifier().getVersion()<self.getLastSeenQuorumVerifier().getVersion()) {
                p.addQuorumVerifier(self.getLastSeenQuorumVerifier());
            }
            lastProposed = p.packet.getZxid();
            //将发送的Proposal提议放入outstandingProposals队列中
            outstandingProposals.put(lastProposed, p);
            //发送Proposal提议，其实就是把Proposal提议交给LearnerHandler处理
            sendPacket(pp);
        }
        return p;
    }

    void sendPacket(QuorumPacket qp) {
        synchronized (forwardingFollowers) {
            for (LearnerHandler f : forwardingFollowers) {
                //LearnerHandler会将提议放入其发送队列里
                f.queuePacket(qp);
            }
        }
    }
    ...
}

public class LearnerHandler extends ZooKeeperThread {
    final LinkedBlockingQueue<QuorumPacket> queuedPackets = new LinkedBlockingQueue<QuorumPacket>();
    ...
    void queuePacket(QuorumPacket p) {
        queuedPackets.add(p);
    }

    @Override
    public void run() {
        ...
        //启动一个线程去发送Packet，比如Proposal提议
        startSendingPackets();
        ...
    }

    protected void startSendingPackets() {
        if (!sendingThreadStarted) {
            // Start sending packets
            new Thread() {
                public void run() {
                    Thread.currentThread().setName("Sender-" + sock.getRemoteSocketAddress());
                    sendPackets();
                }
            }.start();
            sendingThreadStarted = true;
        } else {
            LOG.error("Attempting to start sending thread after it already started");
        }
    }

    private void sendPackets() throws InterruptedException {
        long traceMask = ZooTrace.SERVER_PACKET_TRACE_MASK;
        while (true) {
            QuorumPacket p;
            p = queuedPackets.poll();
            if (p == null) {
                bufferedOutput.flush();
                p = queuedPackets.take();
            }
            if (p == proposalOfDeath) {
                break;
            }
            if (p.getType() == Leader.PING) {
                traceMask = ZooTrace.SERVER_PING_TRACE_MASK;
            }
            if (p.getType() == Leader.PROPOSAL) {
                syncLimitCheck.updateProposal(p.getZxid(), System.nanoTime());
            }
            if (LOG.isTraceEnabled()) {
                ZooTrace.logQuorumPacket(LOG, traceMask, 'o', p);
            }
            oa.writeRecord(p, "packet");
        }
    }
    ...
}
```

#### 三.SyncRequestProcessor事务日志处理器

SyncRequestProcessor处理器是事务日志处理器。它的作用是将事务请求记录到事务日志文件中，同时触发zk进行数据快照。

SyncRequestProcessor处理器也是一个线程，它会先把请求添加到队列，然后由线程处理，它的nextProcessor是AckRequestProcessor处理器。

```java
//SyncRequestProcessor事务日志处理器，它的下一个处理器是AckRequestProcessor
public class SyncRequestProcessor extends ZooKeeperCriticalThread implements RequestProcessor {
    private final ZooKeeperServer zks;
    private final LinkedBlockingQueue<Request> queuedRequests = new LinkedBlockingQueue<Request>();
    private final RequestProcessor nextProcessor;//AckRequestProcessor处理器
    private Thread snapInProcess = null;
    volatile private boolean running;
    private final LinkedList<Request> toFlush = new LinkedList<Request>();
    private final Random r = new Random();
    private static int snapCount = ZooKeeperServer.getSnapCount();
    private final Request requestOfDeath = Request.requestOfDeath;

    public SyncRequestProcessor(ZooKeeperServer zks, RequestProcessor nextProcessor) {
        super("SyncThread:" + zks.getServerId(), zks.getZooKeeperServerListener());
        this.zks = zks;
        this.nextProcessor = nextProcessor;
        running = true;
    }

    public void processRequest(Request request) {
        //将请求添加到队列
        queuedRequests.add(request);
    }

    @Override
    public void run() {
        try {
            int logCount = 0;
            int randRoll = r.nextInt(snapCount/2);
            while (true) {
                Request si = null;
                if (toFlush.isEmpty()) {
                    si = queuedRequests.take();
                } else {
                    si = queuedRequests.poll();
                    if (si == null) {
                        flush(toFlush);
                        continue;
                    }
                }
                if (si == requestOfDeath) {
                    break;
                }
                if (si != null) {
                    if (zks.getZKDatabase().append(si)) {
                        logCount++;
                        if (logCount > (snapCount / 2 + randRoll)) {
                            randRoll = r.nextInt(snapCount/2);
                            // roll the log
                            zks.getZKDatabase().rollLog();
                            // take a snapshot
                            if (snapInProcess != null && snapInProcess.isAlive()) {
                                LOG.warn("Too busy to snap, skipping");
                            } else {
                                snapInProcess = new ZooKeeperThread("Snapshot Thread") {
                                    public void run() {
                                        try {
                                            zks.takeSnapshot();
                                        } catch(Exception e) {
                                            LOG.warn("Unexpected exception", e);
                                        }
                                    }
                                };
                                snapInProcess.start();
                            }
                            logCount = 0;
                        }
                    } else if (toFlush.isEmpty()) {
                        if (nextProcessor != null) {
                            nextProcessor.processRequest(si);
                            if (nextProcessor instanceof Flushable) {
                                ((Flushable)nextProcessor).flush();
                            }
                        }
                        continue;
                    }
                    toFlush.add(si);
                    if (toFlush.size() > 1000) {
                        flush(toFlush);
                    }
                }
            }
        } catch (Throwable t) {
            handleException(this.getName(), t);
        } finally{
            running = false;
        }
    }

    private void flush(LinkedList<Request> toFlush) throws IOException, RequestProcessorException {
        if (toFlush.isEmpty()) {
            return;
        }
        zks.getZKDatabase().commit();
        while (!toFlush.isEmpty()) {
            Request i = toFlush.remove();
            if (nextProcessor != null) {
                nextProcessor.processRequest(i);
            }
        }
        if (nextProcessor != null && nextProcessor instanceof Flushable) {
            ((Flushable)nextProcessor).flush();
        }
    }

    public void shutdown() {
        queuedRequests.add(requestOfDeath);
        if (running) {
            this.join();
        }
        if (!toFlush.isEmpty()) {
            flush(toFlush);
        }
        if (nextProcessor != null) {
            nextProcessor.shutdown();
        }
    }
}
```

#### 四.AckRequestProcessor投票反馈处理器

SyncRequestProcessor的nextProcessor就是AckRequestProcessor，AckRequestProcessor是Leader特有的处理器。

它负责在SyncRequestProcessor处理器完成事务日志记录后，通过Leader的processAck()方法向Proposal提议添加来自Leader的ACK响应。也就是将Leader的SID添加到Proposal提议的投票收集器里，然后调用Leader的tryToCommit()方法检查提议是否已有过半ACK并尝试提交。

同理，如果Leader收到Follower对该Proposal提议请求返回的ACK响应，也会通过Leader的processAck()方法向提议添加来自Follower的ACK响应，也就是将Follower的SID添加到Proposal提议的投票收集器里，然后调用Leader的tryToCommit()方法检查提议是否已有过半ACK来尝试提交。

AckRequestProcessor处理器不是一个线程，它没有nextProcessor属性字段。

```java
//SyncRequestProcessor的nextProcessor就是AckRequestProcessor
class AckRequestProcessor implements RequestProcessor {
    Leader leader;

    AckRequestProcessor(Leader leader) {
        this.leader = leader;
    }

    //Forward the request as an ACK to the leader
    public void processRequest(Request request) {
        QuorumPeer self = leader.self;
        if (self != null) {
            //Leader也作为参与Proposal投票的一份子进行ACK响应
            //将Leader的SID添加到Proposal提议的投票收集器里 + 检查Proposal提议的投票收集器是否有过半ACK才提交
            leader.processAck(self.getId(), request.zxid, null);
        } else {
            LOG.error("Null QuorumPeer");
        }
    }
}

public class LearnerHandler extends ZooKeeperThread {
    ...
    @Override
    public void run() {
        ...
        while (true) {
            ...
            switch (qp.getType()) {
                case Leader.ACK:
                    ...
                    //如果Leader收到Follower对某Proposal提议请求返回的ACK响应
                    //那么就将Follower的SID添加到该Proposal提议的投票收集器里
                    leader.processAck(this.sid, qp.getZxid(), sock.getLocalSocketAddress());
                    break;
                ...
            }
        ...
    }
    ...
}

public class Leader {
    final ConcurrentMap<Long, Proposal> outstandingProposals = new ConcurrentHashMap<Long, Proposal>();
    ...
    public Proposal propose(Request request) throws XidRolloverException {
        ...
        byte[] data = SerializeUtils.serializeRequest(request);
        proposalStats.setLastBufferSize(data.length);
        QuorumPacket pp = new QuorumPacket(Leader.PROPOSAL, request.zxid, data, null);
        //生成Proposal提议
        Proposal p = new Proposal();
        p.packet = pp;
        p.request = request;

        synchronized(this) {
            p.addQuorumVerifier(self.getQuorumVerifier());
            if (request.getHdr().getType() == OpCode.reconfig) {
                self.setLastSeenQuorumVerifier(request.qv, true);
            }
            if (self.getQuorumVerifier().getVersion()<self.getLastSeenQuorumVerifier().getVersion()) {
                p.addQuorumVerifier(self.getLastSeenQuorumVerifier());
            }
            lastProposed = p.packet.getZxid();
            //将发送的Proposal提议放入outstandingProposals队列中
            outstandingProposals.put(lastProposed, p);
            //发送Proposal提议，其实就是把Proposal提议交给LearnerHandler处理
            sendPacket(pp);
        }
        return p;
    }

    void sendPacket(QuorumPacket qp) {
        synchronized (forwardingFollowers) {
            for (LearnerHandler f : forwardingFollowers) {
                //LearnerHandler会将提议放入其发送队列里
                f.queuePacket(qp);
            }
        }
    }

    synchronized public void processAck(long sid, long zxid, SocketAddress followerAddr) {
        ...
        //检查请求的ZXID，需要比上次已提交的请求的ZXID也就是lastCommitted要大
        if (lastCommitted >= zxid) {
            if (LOG.isDebugEnabled()) {
                LOG.debug("proposal has already been committed, pzxid: 0x{} zxid: 0x{}", Long.toHexString(lastCommitted), Long.toHexString(zxid));
            }
            // The proposal has already been committed
            return;
        }
        Proposal p = outstandingProposals.get(zxid);
        //将Leader的SID添加到Proposal提议的投票收集器里
        p.addAck(sid);
        //尝试提交，即检查Proposal提议的投票收集器中是否有过半ACK响应
        boolean hasCommitted = tryToCommit(p, zxid, followerAddr);
        ...
    }

    synchronized public boolean tryToCommit(Proposal p, long zxid, SocketAddress followerAddr) {
        //如果提议队列中存在该提议的前一个提议，说明该提议的前一个提议还没提交，那么就返回false
        //zxid - 1是因为，只有事务请求才会生成zxid，那么前一个事务肯定就是zxid = 1
        if (outstandingProposals.containsKey(zxid - 1)) return false;

        //getting a quorum from all necessary configurations.
        //Proposal提议的投票收集器是否已过半
        if (!p.hasAllQuorums()) {
            return false;
        }
        ...
        outstandingProposals.remove(zxid);
        if (p.request != null) {
            toBeApplied.add(p);
        }
        ...
        //一旦提议通过，马上就要在Leader中标记lastCommitted为最新的提交ZXID
        commit(zxid);//给Follower广播commit消息
        inform(p);//给Observer发送commit消息
        ...
        //调用CommitProcessor处理器的commit方法提交请求
        zk.commitProcessor.commit(p.request);//让Leader执行commit消息
        //下面处理的是Learner发起的同步请求
        if (pendingSyncs.containsKey(zxid)) {
            for (LearnerSyncRequest r: pendingSyncs.remove(zxid)) {
                sendSync(r);
            }
        }
        return true;
    }

    //广播commit消息
    public void commit(long zxid) {
        synchronized(this) {
            //标记lastCommitted为最新的提交ZXID
            lastCommitted = zxid;
        }
        QuorumPacket qp = new QuorumPacket(Leader.COMMIT, zxid, null, null);
        sendPacket(qp);
    }

    void sendPacket(QuorumPacket qp) {
        synchronized (forwardingFollowers) {
            for (LearnerHandler f : forwardingFollowers) {
                //调用LearnerHandler的queuePacket方法添加Packet到发送队列
                f.queuePacket(qp);
            }
        }
    }

    public void inform(Proposal proposal) {
        QuorumPacket qp = new QuorumPacket(Leader.INFORM, proposal.request.zxid, proposal.packet.getData(), null);
        sendObserverPacket(qp);
    }

    ...
    static public class Proposal extends SyncedLearnerTracker {
        public QuorumPacket packet;
        public Request request;
        ...
    }
}

public class SyncedLearnerTracker {
    protected ArrayList<QuorumVerifierAcksetPair> qvAcksetPairs = new ArrayList<QuorumVerifierAcksetPair>();
    ...
    //添加到投票收集器
    public boolean addAck(Long sid) {
        boolean change = false;
        for (QuorumVerifierAcksetPair qvAckset : qvAcksetPairs) {
            if (qvAckset.getQuorumVerifier().getVotingMembers().containsKey(sid)) {
                qvAckset.getAckset().add(sid);
                change = true;
            }
        }
        return change;
    }

    //判断投票收集器是否过半
    public boolean hasAllQuorums() {
        for (QuorumVerifierAcksetPair qvAckset : qvAcksetPairs) {
            if (!qvAckset.getQuorumVerifier().containsQuorum(qvAckset.getAckset()))
                return false;
        }
        return true;
    }
    ...
}
```

#### 五.CommitProcessor事务提交处理器

ProposalRequestProcessor的nextProcessor就是CommitProcessor处理器，CommitProcessor就是事务提交处理器。

对于非事务请求，CommitProcessor会将其转交给nextProcessor处理。对于事务请求，CommitProcessor会阻塞等待Proposal提议可以被提交。

CommitProcessor有个LinkedBlockingQueue队列queuedRequests。当调用CommitProcessor的processRequest()方法时，请求会被添加到该队列。CommitProcessor线程会从queuedRequests队列中取出请求进行处理。此外还通过nextPending和committedRequests队列保证请求的顺序处理。

CommitProcessor处理器也是一个线程，它会先把请求添加到队列，然后由线程处理，它的nextProcessor是ToBeAppliedRequestProcessor.

```cs
public class CommitProcessor extends ZooKeeperCriticalThread implements RequestProcessor {
    //请求队列
    protected final LinkedBlockingQueue<Request> queuedRequests = new LinkedBlockingQueue<Request>();
    protected final LinkedBlockingQueue<Request> committedRequests = new LinkedBlockingQueue<Request>();
    //下一个要提交的请求
    protected final AtomicReference<Request> nextPending = new AtomicReference<Request>();
    //当前正在处理的请求数
    protected AtomicInteger numRequestsProcessing = new AtomicInteger(0);
    ...

    @Override
    public void processRequest(Request request) {
        if (stopped) {
            return;
        }
        queuedRequests.add(request);
        if (!isWaitingForCommit()) {
            wakeup();//唤醒
        }
    }

    private boolean isProcessingRequest() {
        return numRequestsProcessing.get() != 0;
    }

    private boolean isWaitingForCommit() {
        return nextPending.get() != null;
    }

    private boolean isProcessingCommit() {
        return currentlyCommitting.get() != null;
    }

    synchronized private void wakeup() {
        notifyAll();//唤醒阻塞的线程
    }

    @Override
    public void run() {
        Request request;
        while (!stopped) {
            synchronized(this) {
                while (!stopped && ((queuedRequests.isEmpty() || isWaitingForCommit() || isProcessingCommit()) && (committedRequests.isEmpty() || isProcessingRequest()))) {
                    wait();//阻塞等待
                }
            }
            while (!stopped && !isWaitingForCommit() && !isProcessingCommit() && (request = queuedRequests.poll()) != null) {
                if (needCommit(request)) {//需要进行提交的事务请求
                    nextPending.set(request);//设置下一个要提交的请求
                } else {//非事务请求转交给下一个处理器
                    sendToNextProcessor(request);
                }
            }
            processCommitted();//处理提交
        }
    }

    protected void processCommitted() {
        Request request;
        if (!stopped && !isProcessingRequest() && (committedRequests.peek() != null)) {
            if ( !isWaitingForCommit() && !queuedRequests.isEmpty()) {
                return;
            }
            request = committedRequests.poll();
            Request pending = nextPending.get();
            if (pending != null && pending.sessionId == request.sessionId && pending.cxid == request.cxid) {
                pending.setHdr(request.getHdr());
                pending.setTxn(request.getTxn());
                pending.zxid = request.zxid;
                currentlyCommitting.set(pending);
                nextPending.set(null);
                sendToNextProcessor(pending);
            } else {
                currentlyCommitting.set(request);
                sendToNextProcessor(request);
            }
        }
    }

    public void commit(Request request) {
        committedRequests.add(request);
        if (!isProcessingCommit()) {//CommitProcessor处理器当前没有提交请求
            wakeup();//CommitProcessor唤醒线程
        }
    }

    private void sendToNextProcessor(Request request) {
        numRequestsProcessing.incrementAndGet();
        workerPool.schedule(new CommitWorkRequest(request), request.sessionId);
    }

    private class CommitWorkRequest extends WorkerService.WorkRequest {
        private final Request request;
        CommitWorkRequest(Request request) {
            this.request = request;
        }
        ...
        public void doWork() throws RequestProcessorException {
            try {
                nextProcessor.processRequest(request);
            } finally {
                currentlyCommitting.compareAndSet(request, null);
                if (numRequestsProcessing.decrementAndGet() == 0) {
                    if (!queuedRequests.isEmpty() || !committedRequests.isEmpty()) {
                        wakeup();
                    }
                }
            }
        }
    }
    ...
}
```

如何理解保证事务请求的顺序处理：

顺序排队的事务请求在被ProposalRequestProcessor处理的过程中，首先会执行CommitProcessor的processRequest()方法将请求加入请求队列，所以请求队列queuedRequests里面的请求是按顺序排好的。然后会生成Proposal提议发送给Follower并收集ACK响应，最后当ACK响应过半时才调用CommitProcessor的commit()方法，此时可以进行提交的请求就会被添加到CommitProcessor的committedRequests队列中。

是否会因网络原因，导致CommitProcessor的committedRequests队列里的请求并不一定按顺序排好呢？

事务请求能保证顺序处理的根本原因是：

整个Proposal消息广播过程是基于FIFO特性的TCP协议来进行网络通信的，所以能够很容易保证消息广播过程中消息接收和发送的顺序性。也就是广播时是由一个主进程Leader去通过FIFO的TCP协议进行发送的，所以每个Follower接收到的Proposal和Commit请求都会按顺序进入队列。

客户端并发执行的事务请求到达Leader时一定会按顺序入队。然后Leader对事务请求进行广播时，也会按顺序进行广播。被单一Leader进行顺序广播的多个事务请求也会顺序到达某Follower。所以某Follower收到的多个Proposal提议也会按广播时的顺序进入队列，之后某Follower都会按广播时的顺序发送ACK响应给Leader。

所以Leader收到某Follower的ACK响应都是按广播时的顺序收到的。即使Leader先收到Follower2响应的事务2，后收到Follower1的响应事务1，但最终统计过半选票时，Leader会发现事务1首先过半从而优先保证事务1的顺序。

![图片](assets/b7b66ce9f551.png)

当然，Leader的processAck()方法会先确保要被提交的请求ZXID比上次大。此外，Leader的tryToCommit()方法也会首先确保前一个事务提交了才能处理。以及Follower在接收到Proposal和Commit请求就是按顺序响应，即若Follower要提交的事务ID不是pendingTxns的头部元素，那么就退出程序。最后结合CommitProcessor里的queuedRequests \+ committedRequests \+ nextPending，于是便能保证事务请求的顺序处理。

```java
public class Leader {
    ...
    synchronized public void processAck(long sid, long zxid, SocketAddress followerAddr) {
        ...
        //检查请求的ZXID，需要比上次已提交的请求的ZXID也就是lastCommitted要大
        if (lastCommitted >= zxid) {
            if (LOG.isDebugEnabled()) {
                LOG.debug("proposal has already been committed, pzxid: 0x{} zxid: 0x{}", Long.toHexString(lastCommitted), Long.toHexString(zxid));
            }
            // The proposal has already been committed
            return;
        }
        Proposal p = outstandingProposals.get(zxid);
        //将Leader的SID添加到Proposal提议的投票收集器里
        p.addAck(sid);
        //尝试提交，即检查Proposal提议的投票收集器中是否有过半ACK响应
        boolean hasCommitted = tryToCommit(p, zxid, followerAddr);
        ...
    }

    synchronized public boolean tryToCommit(Proposal p, long zxid, SocketAddress followerAddr) {
        //如果提议队列中存在该提议的前一个提议，说明该提议的前一个提议还没提交，那么就返回false
        //zxid - 1是因为，只有事务请求才会生成zxid，那么前一个事务肯定就是zxid = 1
        if (outstandingProposals.containsKey(zxid - 1)) return false;
        //getting a quorum from all necessary configurations.
        //Proposal提议的投票收集器是否已过半
        if (!p.hasAllQuorums()) {
            return false;
        }
        ...
        zk.commitProcessor.commit(p.request);
        ...
    }
    ...
}

public class Follower extends Learner{
    ...
    void followLeader() throws InterruptedException {
        ...
        while (this.isRunning()) {
            readPacket(qp);
            processPacket(qp);
        }
        ...
    }

    protected void processPacket(QuorumPacket qp) throws Exception {
        switch (qp.getType()) {
            case Leader.PING:
                ping(qp);
                break;
            case Leader.PROPOSAL:
                //处理Leader发起的Proposal提议投票请求
                TxnHeader hdr = new TxnHeader();
                Record txn = SerializeUtils.deserializeTxn(qp.getData(), hdr);
                lastQueued = hdr.getZxid();
                ...
                fzk.logRequest(hdr, txn);
                break;
            case Leader.COMMIT:
                //处理Leader发送过来的对Proposal提议进行提交的请求
                fzk.commit(qp.getZxid());
                break;
            ...
        }
    }
}

public class FollowerZooKeeperServer extends LearnerZooKeeperServer {
    LinkedBlockingQueue<Request> pendingTxns = new LinkedBlockingQueue<Request>();
    ...

    //将收到的投票请求放入队列pendingTxns
    public void logRequest(TxnHeader hdr, Record txn) {
        Request request = new Request(hdr.getClientId(), hdr.getCxid(), hdr.getType(), hdr, txn, hdr.getZxid());
        if ((request.zxid & 0xffffffffL) != 0) {
            pendingTxns.add(request);
        }
        syncProcessor.processRequest(request);
    }

    //When a COMMIT message is received, eventually this method is called,
    //which matches up the zxid from the COMMIT with (hopefully) the head of
    //the pendingTxns queue and hands it to the commitProcessor to commit.
    //@param zxid - must correspond to the head of pendingTxns if it exists
    public void commit(long zxid) {
        if (pendingTxns.size() == 0) {
            LOG.warn("Committing " + Long.toHexString(zxid) + " without seeing txn");
            return;
        }
        long firstElementZxid = pendingTxns.element().zxid;
        if (firstElementZxid != zxid) {
            //如果Follower需要提交的事务ID不是pendingTxns的头部元素，就退出程序
            LOG.error("Committing zxid 0x" + Long.toHexString(zxid) + " but next pending txn 0x" + Long.toHexString(firstElementZxid));
            System.exit(12);
        }
        Request request = pendingTxns.remove();
        commitProcessor.commit(request);
    }
    ...
}
```

#### 六.ToBeAppliedRequestProcessor处理器

Leader中有一个toBeApplied队列，专门存储那些可以被提交的Proposal提议。ToBeAppliedRequestProcessor会把已被CommitProcessor处理过的请求，转交给下一个处理器处理，并把请求从Leader的toBeApplied队列中移除。

ToBeAppliedRequestProcessor处理器不是一个线程，它的next是FinalRequestProcessor处理器。

```java
public class Leader {
    private final ConcurrentLinkedQueue<Proposal> toBeApplied = new ConcurrentLinkedQueue<Proposal>();
    ...
    static class ToBeAppliedRequestProcessor implements RequestProcessor {
        private final RequestProcessor next;
        private final Leader leader;

        ToBeAppliedRequestProcessor(RequestProcessor next, Leader leader) {
            this.leader = leader;
            this.next = next;
        }
        ...
        public void processRequest(Request request) throws RequestProcessorException {
            next.processRequest(request);
            if (request.getHdr() != null) {
                long zxid = request.getHdr().getZxid();
                Iterator<Proposal> iter = leader.toBeApplied.iterator();
                if (iter.hasNext()) {
                    Proposal p = iter.next();
                    if (p.request != null && p.request.zxid == zxid) {
                        iter.remove();
                        return;
                    }
                }
            }
        }
        ...
    }
    ...
}
```

#### 七.FinalRequestProcessor处理器

FinalRequestProcessor处理器用来处理返回客户端响应前的收尾工作，包括创建客户端的响应、将事务请求应用到内存数据库中。

FinalRequestProcessor处理器不是一个线程，它也没有nextProcessor属性字段。

```java
public class FinalRequestProcessor implements RequestProcessor {
    ...
    public void processRequest(Request request) {
        ...
        ProcessTxnResult rc = null;
        synchronized (zks.outstandingChanges) {
            // Need to process local session requests
            rc = zks.processTxn(request);
            if (request.getHdr() != null) {
                TxnHeader hdr = request.getHdr();
                Record txn = request.getTxn();
                long zxid = hdr.getZxid();

                while (!zks.outstandingChanges.isEmpty() && zks.outstandingChanges.peek().zxid <= zxid) {
                    ChangeRecord cr = zks.outstandingChanges.remove();
                    if (zks.outstandingChangesForPath.get(cr.path) == cr) {
                        zks.outstandingChangesForPath.remove(cr.path);
                    }
                }
            }
            // do not add non quorum packets to the queue.
            if (request.isQuorum()) {
                zks.getZKDatabase().addCommittedProposal(request);
            }
        }
        ...
        //创建响应并发送响应给客户端
        long lastZxid = zks.getZKDatabase().getDataTreeLastProcessedZxid();
        ReplyHeader hdr = new ReplyHeader(request.cxid, lastZxid, err.intValue());
        zks.serverStats().updateLatency(request.createTime);
        cnxn.updateStatsForResponse(request.cxid, lastZxid, lastOp, request.createTime, Time.currentElapsedTime());
        cnxn.sendResponse(hdr, rsp, "response");
        if (request.type == OpCode.closeSession) {
            cnxn.sendCloseSession();
        }
    }
    ...
}
```

总结：

```perl
PrepRequestProcessor的nextProcessor就是ProposalRequestProcessor；
ProposalRequestProcessor的nextProcessor就是CommitProcessor；
CommitProcessor的nextProcessor就是ToBeAppliedRequestProcessor；
ToBeAppliedRequestProcessor的next是FinalRequestProcessor；
FinalRequestProcessor没有nextProcessor属性字段；

ProposalRequestProcessor会调用SyncRequestProcessor处理器的方法；
SyncRequestProcessor的nextProcessor就是AckRequestProcessor；
AckRequestProcessor没有nextProcessor属性字段；

PrepRequestProcessor处理器是一个线程；
ProposalRequestProcessor处理器不是一个线程；
CommitProcessor处理器是一个线程；
ToBeAppliedRequestProcessor处理器不是一个线程；
FinalRequestProcessor处理器不是一个线程；

SyncRequestProcessor处理器是一个线程；
AckRequestProcessor处理器不是一个线程；
```

### (2)Follower服务器的请求处理链

#### 一.FollowerRequestProcessor请求转发处理器

#### 二.SendAckRequestProcessor投票反馈处理器

Follower服务器的主要工作是：

#### 一.处理非事务请求 \+ 转发事务请求给Leader服务器

#### 二.参与事务请求的Proposal提议的投票

#### 三.参与Leader选举投票

Follower服务器的请求处理链如下图示：

![图片](assets/9d685a182f84.png)

Leader服务器的第一个处理器是LeaderRequestProcessor，Follower服务器的第一个处理器是FollowerRequestProcessor。由于不需要处理事务请求的投票，所以Follower服务器没有ProposalRequestProcessor处理器。

#### 一.FollowerRequestProcessor请求转发处理器

FollowerRequestProcessor主要工作是识别当前请求是否是事务请求。如果是事务请求，那么Follower就会将该事务请求转发给Leader服务器。FollowerRequestProcessor处理器会通过调用Learner的request()方法实现请求转发。Learner的request方法会往输出流leaderOs中写入请求数据来发给Leader。输出流leaderOs在Follower和Leader建立好连接时就已经初始化好了的。

```java
public class QuorumPeer extends ZooKeeperThread implements QuorumStats.Provider {
    ...
    protected Follower makeFollower(FileTxnSnapLog logFactory) throws IOException {
        return new Follower(this, new FollowerZooKeeperServer(logFactory, this, this.zkDb));
    }
    ...
}

public class FollowerZooKeeperServer extends LearnerZooKeeperServer {
    ...
    @Override
    protected void setupRequestProcessors() {
        RequestProcessor finalProcessor = new FinalRequestProcessor(this);
        commitProcessor = new CommitProcessor(finalProcessor, Long.toString(getServerId()), true, getZooKeeperServerListener());
        commitProcessor.start();
        firstProcessor = new FollowerRequestProcessor(this, commitProcessor);
        ((FollowerRequestProcessor) firstProcessor).start();
        syncProcessor = new SyncRequestProcessor(this, new SendAckRequestProcessor((Learner)getFollower()));
        syncProcessor.start();
    }

    public Follower getFollower(){
        return self.follower;
    }
    ...
}

public class FollowerRequestProcessor extends ZooKeeperCriticalThread implements RequestProcessor {
    FollowerZooKeeperServer zks;
    RequestProcessor nextProcessor;
    LinkedBlockingQueue<Request> queuedRequests = new LinkedBlockingQueue<Request>();
    boolean finished = false;

    public FollowerRequestProcessor(FollowerZooKeeperServer zks, RequestProcessor nextProcessor) {
        super("FollowerRequestProcessor:" + zks.getServerId(), zks.getZooKeeperServerListener());
        this.zks = zks;
        this.nextProcessor = nextProcessor;
    }

    @Override
    public void run() {
        while (!finished) {
            Request request = queuedRequests.take();
            if (request == Request.requestOfDeath) {
                break;
            }
            nextProcessor.processRequest(request);
            //如果是事务请求，则调用zks.getFollower().request(request)转发事务请求给Leader
            switch (request.type) {
                case OpCode.sync:
                    zks.pendingSyncs.add(request);
                    zks.getFollower().request(request);
                    break;
                case OpCode.create:
                case OpCode.create2:
                case OpCode.createTTL:
                case OpCode.createContainer:
                case OpCode.delete:
                case OpCode.deleteContainer:
                case OpCode.setData:
                case OpCode.reconfig:
                case OpCode.setACL:
                case OpCode.multi:
                case OpCode.check:
                    zks.getFollower().request(request);
                    break;
                case OpCode.createSession:
                case OpCode.closeSession:
                    // Don't forward local sessions to the leader.
                    if (!request.isLocalSession()) {
                        zks.getFollower().request(request);
                    }
                    break;
            }
        }
    }

    public void processRequest(Request request) {
        if (!finished) {
            Request upgradeRequest = null;
            upgradeRequest = zks.checkUpgradeSession(request);
            if (upgradeRequest != null) {
                queuedRequests.add(upgradeRequest);
            }
            queuedRequests.add(request);
        }
    }
    ...
}

public class Learner {
    protected BufferedOutputStream bufferedOutput;
    protected Socket sock;
    protected InputArchive leaderIs;
    protected OutputArchive leaderOs;
    ...
    //send a request packet to the leader
    //发送一个请求给Leader
    void request(Request request) throws IOException {
        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        DataOutputStream oa = new DataOutputStream(baos);
        oa.writeLong(request.sessionId);
        oa.writeInt(request.cxid);
        oa.writeInt(request.type);
        if (request.request != null) {
            request.request.rewind();
            int len = request.request.remaining();
            byte b[] = new byte[len];
            request.request.get(b);
            request.request.rewind();
            oa.write(b);
        }
        oa.close();
        QuorumPacket qp = new QuorumPacket(Leader.REQUEST, -1, baos.toByteArray(), request.authInfo);
        //发送请求，往输出流leaderOs写数据
        writePacket(qp, true);
    }

    void writePacket(QuorumPacket pp, boolean flush) throws IOException {
        synchronized (leaderOs) {
            if (pp != null) {
                leaderOs.writeRecord(pp, "packet");
            }
            if (flush) {
                bufferedOutput.flush();
            }
        }
    }

    //和Leader建立连接时就已经初始化好输出流leaderOs了
    protected void connectToLeader(InetSocketAddress addr, String hostname) throws IOException, InterruptedException, X509Exception {
        this.sock = createSocket();
        int initLimitTime = self.tickTime * self.initLimit;
        int remainingInitLimitTime = initLimitTime;
        long startNanoTime = nanoTime();

        for (int tries = 0; tries < 5; tries++) {
            remainingInitLimitTime = initLimitTime - (int)((nanoTime() - startNanoTime) / 1000000);
            sockConnect(sock, addr, Math.min(self.tickTime * self.syncLimit, remainingInitLimitTime));
            if (self.isSslQuorum())  {
                ((SSLSocket) sock).startHandshake();
            }
            sock.setTcpNoDelay(nodelay);
            break;
        }
        Thread.sleep(1000);
        self.authLearner.authenticate(sock, hostname);
        //初始化好输入流leaderIs
        leaderIs = BinaryInputArchive.getArchive(new BufferedInputStream(sock.getInputStream()));
        bufferedOutput = new BufferedOutputStream(sock.getOutputStream());
        //初始化好输出流leaderOs
        leaderOs = BinaryOutputArchive.getArchive(bufferedOutput);
    }

    //创建BIO的scoekt
    private Socket createSocket() throws X509Exception, IOException {
        Socket sock;
        if (self.isSslQuorum()) {
            sock = self.getX509Util().createSSLSocket();
        } else {
            sock = new Socket();
        }
        sock.setSoTimeout(self.tickTime * self.initLimit);
        return sock;
    }
    ...
}
```

#### 二.SendAckRequestProcessor投票反馈处理器

Leader的请求处理链有个叫AckRequestProcessor的投票反馈处理器，主要负责在执行完SyncRequestProcessor处理器记录好事务日志后，向Proposal提议反馈来自Leader的ACK响应。

Follower的请求处理链也有个叫SendAckRequestProcessor的投票反馈处理器，主要负责在执行完SyncRequestProcessor处理器记录好事务日志后，通过发送消息给Leader来向Proposal提议反馈来自Follower的ACK响应。

Follower请求处理链的SyncRequestProcessor处理器会启动一个线程。SyncRequestProcessor处理器会先把请求添加到队列，然后由线程处理。SyncRequestProcessor的nextProcessor就是SendAckRequestProcessor请求处理器。SendAckRequestProcessor不是一个线程。

```java
public class SendAckRequestProcessor implements RequestProcessor, Flushable {
    Learner learner;

    SendAckRequestProcessor(Learner peer) {
        this.learner = peer;
    }

    public void processRequest(Request si) {
        if (si.type != OpCode.sync) {
            QuorumPacket qp = new QuorumPacket(Leader.ACK, si.getHdr().getZxid(), null, null);
            learner.writePacket(qp, false);//向Leader发送ACK响应
            ...
        }
    }
    ...
}

public class Follower extends Learner {
    ...
    void followLeader() throws InterruptedException {
        ...
        QuorumServer leaderServer = findLeader();
        connectToLeader(leaderServer.addr, leaderServer.hostname);

        long newEpochZxid = registerWithLeader(Leader.FOLLOWERINFO);
        syncWithLeader(newEpochZxid);

        QuorumPacket qp = new QuorumPacket();
        while (this.isRunning()) {
            readPacket(qp);//读取Leader发过来的请求的输入流leaderIs
            processPacket(qp);//处理Leader发过来的请求，其中就包括Proposal提议的投票请求
        }
        ...
    }

    protected void processPacket(QuorumPacket qp) throws Exception{
        switch (qp.getType()) {
            case Leader.PING:
                ping(qp);
                break;
            //对Leader发起的Proposal提议投票进行响应
            case Leader.PROPOSAL:
                TxnHeader hdr = new TxnHeader();
                Record txn = SerializeUtils.deserializeTxn(qp.getData(), hdr);
                ...
                //对Leader发起的Proposal提议投票进行响应
                //此时请求便能进入SyncRequestProcessor处理器的队列里了
                //SyncRequestProcessor线程处理完该请求，就会由SendAckRequestProcessor来发送ACK响应
                fzk.logRequest(hdr, txn);
                break;
            ...
        }
    }
    ...
}

public class FollowerZooKeeperServer extends LearnerZooKeeperServer {
    ...
    @Override
    protected void setupRequestProcessors() {
        RequestProcessor finalProcessor = new FinalRequestProcessor(this);
        commitProcessor = new CommitProcessor(finalProcessor, Long.toString(getServerId()), true, getZooKeeperServerListener());
        commitProcessor.start();
        firstProcessor = new FollowerRequestProcessor(this, commitProcessor);
        ((FollowerRequestProcessor) firstProcessor).start();
        syncProcessor = new SyncRequestProcessor(this, new SendAckRequestProcessor((Learner)getFollower()));
        syncProcessor.start();
    }

    public void logRequest(TxnHeader hdr, Record txn) {
        Request request = new Request(hdr.getClientId(), hdr.getCxid(), hdr.getType(), hdr, txn, hdr.getZxid());
        if ((request.zxid & 0xffffffffL) != 0) {
            pendingTxns.add(request);
        }
        //调用SyncRequestProcessor的processRequest方法处理Proposal提议的投票响应
        syncProcessor.processRequest(request);
    }
    ...
}

public class Learner {
    protected BufferedOutputStream bufferedOutput;
    protected Socket sock;
    protected InputArchive leaderIs;
    protected OutputArchive leaderOs;
    ...
    void readPacket(QuorumPacket pp) throws IOException {
        synchronized (leaderIs) {
            //读取Leader发送过来的请求的输入流
            leaderIs.readRecord(pp, "packet");
        }
    }

    void writePacket(QuorumPacket pp, boolean flush) throws IOException {
        synchronized (leaderOs) {
            if (pp != null) {
                //将响应写入输出流，发送给Leader
                leaderOs.writeRecord(pp, "packet");
            }
            if (flush) {
                bufferedOutput.flush();
            }
        }
    }

    //和Leader建立连接时就已经初始化好输出流leaderOs了
    protected void connectToLeader(InetSocketAddress addr, String hostname) throws IOException, InterruptedException, X509Exception {
        this.sock = createSocket();
        int initLimitTime = self.tickTime * self.initLimit;
        int remainingInitLimitTime = initLimitTime;
        long startNanoTime = nanoTime();

        for (int tries = 0; tries < 5; tries++) {
            remainingInitLimitTime = initLimitTime - (int)((nanoTime() - startNanoTime) / 1000000);
            sockConnect(sock, addr, Math.min(self.tickTime * self.syncLimit, remainingInitLimitTime));
            if (self.isSslQuorum())  {
                ((SSLSocket) sock).startHandshake();
            }
            sock.setTcpNoDelay(nodelay);
            break;
        }
        Thread.sleep(1000);
        self.authLearner.authenticate(sock, hostname);
        //初始化好输入流leaderIs
        leaderIs = BinaryInputArchive.getArchive(new BufferedInputStream(sock.getInputStream()));
        bufferedOutput = new BufferedOutputStream(sock.getOutputStream());
        //初始化好输出流leaderOs
        leaderOs = BinaryOutputArchive.getArchive(bufferedOutput);
    }
    ...
}
```

2.服务端处理会话创建请求的流程

### (1)请求接收

### (2)会话创建

### (3)请求预处理

### (4)事务处理

### (5)事务应用和响应

zk服务端(即Leader服务器)对会话创建请求的处理，可以分为六大环节：

```sql
(1)请求接收
一.首先读取客户端的会话创建请求
二.然后判断是否是会话创建请求
三.接着反序列化输入流成一个ConnectRequest请求
四.然后判断客户端是否readOnly客户端
五.接着检查客户端的ZXID
六.然后协商会话超时时间
七.最后判断是否需要重新创建会话

(2)会话创建
一.为客户端生成sessionID
二.注册会话
三.激活会话
四.生成会话密码

(3)请求预处理
一.将请求交给PrepRequestProcessor请求预处理器
二.创建和设置请求的事务头TxnHeader
三.创建和设置请求的事务体CreateSessionTxn
四.注册与激活会话

(4)事务处理
Sync流程
一.将请求交给ProposalRequestProcessor请求处理器处理
二.将请求交给SyncRequestProcessor请求处理器处理

Proposal流程
一.调用Leader的propose()方法发起投票
二.在Leader的propose()方法中生成Proposal提议
三.调用Leader的sendPacket()方法广播提议
四.调用Leader的processAck()方法收集投票
五.在Leader的tryToCommit()方法中将请求放入toBeApplied队列中
六.在Leader的tryToCommit()方法中广播Commit消息

Commit流程
一.将请求交给CommitProcessor请求处理器处理
二.处理queuedRequests请求队列
三.等待Proposal提议的投票
四.投票通过
五.标记nextPending
六.提交请求

(5)事务应用和响应
一.将请求交给FinalRequestProcessor请求处理器处理
二.首先进行事务应用
三.然后创建响应
四.最后序列化响应并发送给客户端
```

整体流程图如下：

![图片](assets/693ba117f4c8.png)

### (1)请求接收环节

#### 一.首先读取客户端的会话创建请求

#### 二.然后判断是否是会话创建请求

#### 三.接着反序列化输入流成ConnectRequest请求

#### 四.然后判断客户端是否readOnly客户端

#### 五.接着检查客户端的ZXID

#### 六.然后协商会话超时时间

#### 七.最后判断是否需要重新创建会话

入口一：ServerCnxnFactory的SelectorThread线程收到来自客户端的会话创建请求。

```java
//入口一：ServerCnxnFactory的SelectorThread线程收到来自客户端的会话创建请求；
public class QuorumPeerMain {
    ...
    public static void main(String[] args) {
        QuorumPeerMain main = new QuorumPeerMain();
        main.initializeAndRun(args);
    }

    protected void initializeAndRun(String[] args) {
        //解析配置
        QuorumPeerConfig config = new QuorumPeerConfig();
        if (args.length == 1) {
            config.parse(args[0]);
        }
        //创建并启动历史文件清理器
        DatadirCleanupManager purgeMgr = new DatadirCleanupManager(config.getDataDir(), config.getDataLogDir(), config.getSnapRetainCount(), config.getPurgeInterval());
        purgeMgr.start();
        //判断是单机模式还是集群模式
        if (args.length == 1 && config.isDistributed()) {
            runFromConfig(config);//集群模式
        } else {
            ZooKeeperServerMain.main(args);//单机模式
        }
    }

    public void runFromConfig(QuorumPeerConfig config) {
        ...
        quorumPeer = getQuorumPeer();
        ...
        //启动QuorumPeer实例
        quorumPeer.start();
        quorumPeer.join();
    }
    ...
}

public class QuorumPeer extends ZooKeeperThread implements QuorumStats.Provider {
    ServerCnxnFactory cnxnFactory;
    ...
    public synchronized void start() {
        //恢复集群版服务器实例QuorumPeer本地数据
        loadDataBase();
        //启动网络连接工厂ServerCnxnFactory主线程
        startServerCnxnFactory();
        adminServer.start();
        //初始化Leader选举(初始化当前投票+监听选举端口+启动选举守护线程)
        startLeaderElection();
        //开启监控JVM停顿的线程
        startJvmPauseMonitor();
        //执行集群版服务器实例QuorumPeer.run()方法
        super.start();
    }

    private void startServerCnxnFactory() {
        if (cnxnFactory != null) {
            //例如启动NIOServerCnxnFactory
            cnxnFactory.start();
        }
        if (secureCnxnFactory != null) {
            secureCnxnFactory.start();
        }
    }
    ...
}

public class NIOServerCnxnFactory extends ServerCnxnFactory {
    private volatile boolean stopped = true;
    private ConnectionExpirerThread expirerThread;
    private AcceptThread acceptThread;
    private final Set<SelectorThread> selectorThreads = new HashSet<SelectorThread>();
    ...
    public void start() {
        stopped = false;
        if (workerPool == null) {
            workerPool = new WorkerService("NIOWorker", numWorkerThreads, false);
        }
        for (SelectorThread thread : selectorThreads) {
            if (thread.getState() == Thread.State.NEW) {
                thread.start();//处理客户端发起请求
            }
        }
        if (acceptThread.getState() == Thread.State.NEW) {
            acceptThread.start();//处理客户端发起连接
        }
        if (expirerThread.getState() == Thread.State.NEW) {
            expirerThread.start();//处理客户端连接过期
        }
    }
    ...
    private class AcceptThread extends AbstractSelectThread {
        private final ServerSocketChannel acceptSocket;
        private final Collection<SelectorThread> selectorThreads;
        private Iterator<SelectorThread> selectorIterator;
        ...
        public void run() {
            while (!stopped && !acceptSocket.socket().isClosed()) {
                select();
            }
        }

        private void select() {
            selector.select();
            Iterator<SelectionKey> selectedKeys = selector.selectedKeys().iterator();
            while (!stopped && selectedKeys.hasNext()) {
                SelectionKey key = selectedKeys.next();
                selectedKeys.remove();
                if (!key.isValid()) {
                    continue;
                }
                if (key.isAcceptable()) {
                    if (!doAccept()) {
                        pauseAccept(10);
                    }
                } else {
                    LOG.warn("Unexpected ops in accept select " + key.readyOps());
                }
            }
        }

        private boolean doAccept() {
            SocketChannel sc = acceptSocket.accept();
            ...
            if (!selectorIterator.hasNext()) {
                selectorIterator = selectorThreads.iterator();
            }
            SelectorThread selectorThread = selectorIterator.next();
            if (!selectorThread.addAcceptedConnection(sc)) {
                throw new IOException("Unable to add connection to selector queue" + (stopped ? " (shutdown in progress)" : ""));
            }
            ...
        }
        ...
    }

    private abstract class AbstractSelectThread extends ZooKeeperThread {
        protected final Selector selector;

        public AbstractSelectThread(String name) throws IOException {
            super(name);
            // Allows the JVM to shutdown even if this thread is still running.
            setDaemon(true);
            this.selector = Selector.open();
        }

        public void wakeupSelector() {
            selector.wakeup();
        }
        ...
    }

    class SelectorThread extends AbstractSelectThread {
        private final Queue<SocketChannel> acceptedQueue;
        ...
        public boolean addAcceptedConnection(SocketChannel accepted) {
            if (stopped || !acceptedQueue.offer(accepted)) {
                return false;
            }
            wakeupSelector();
            return true;
        }

        public void run() {
            while (!stopped) {
                select();
                processAcceptedConnections();
                processInterestOpsUpdateRequests();
            }
            ...
        }

        private void select() {
            selector.select();
            Set<SelectionKey> selected = selector.selectedKeys();
            ArrayList<SelectionKey> selectedList = new ArrayList<SelectionKey>(selected);
            Collections.shuffle(selectedList);
            Iterator<SelectionKey> selectedKeys = selectedList.iterator();

            while (!stopped && selectedKeys.hasNext()) {
                SelectionKey key = selectedKeys.next();
                selected.remove(key);
                if (!key.isValid()) {
                    cleanupSelectionKey(key);
                    continue;
                }
                //处理客户端发过来的读请求 + 处理服务端发出去的写响应
                if (key.isReadable() || key.isWritable()) {
                    handleIO(key);
                } else {
                    LOG.warn("Unexpected ops in select " + key.readyOps());
                }
            }
        }

        private void handleIO(SelectionKey key) {
            IOWorkRequest workRequest = new IOWorkRequest(this, key);
            NIOServerCnxn cnxn = (NIOServerCnxn) key.attachment();
            cnxn.disableSelectable();
            key.interestOps(0);
            touchCnxn(cnxn);//激活连接
            //交给工作线程池去处理请求
            workerPool.schedule(workRequest);
        }

        private class IOWorkRequest extends WorkerService.WorkRequest {
            private final SelectorThread selectorThread;
            private final SelectionKey key;
            private final NIOServerCnxn cnxn;
            ...
            public void doWork() throws InterruptedException {
                ...
                if (key.isReadable() || key.isWritable()) {
                    //调用NIOServerCnxn.doIO方法来处理客户端发过来的请求+服务端返回的响应
                    cnxn.doIO(key);
                }
                ...
            }
        }
        ...
    }
}
```

接下来的NIOServerCnxn的doIO()方法会处理客户端发来的会话创建请求，具体步骤如下：

#### 一.首先读取客户端的会话创建请求

NIOServerCnxn的doIO()方法会从Socket读取客户端的会话创建请求。一个NIOServerCnxn实例维护一个客户端连接，一个LearnerHandler实例维护一个Learner连接。客户端与服务端的所有通信都会经过NIOServerCnxn的doIO()方法进行处理。NIOServerCnxn的doIO()方法会将收到的客户端的会话创建请求读取出来。

#### 二.然后判断是否是会话创建请求

NIOServerCnxn的readPayload()方法会判断是否是会话创建请求。通过NIOServerCnxn实例是否已被初始化，来判断是否为会话创建请求。如果NIOServerCnxn实例没有被初始化，那么该请求一定是会话创建请求。

#### 三.接着反序列化输入流成ConnectRequest请求

在ZooKeeperServer的processConnectRequest()方法中对输入流进行反序列化。

#### 四.然后判断客户端是否readOnly客户端

如果当前zk服务端是以readOnly模式启动的，那么所有来自非readOnly客户端的请求都无法被处理。

#### 五.接着检查客户端的ZXID

服务端的ZXID必须大于客户端的ZXID。如果客户端发送过来的会话创建请求的ZXID大于服务端的ZXID，则抛异常。

#### 六.然后协商会话超时时间

客户端在构造ZooKeeper实例时，会有一个会话超时时间sessionTimeout。服务端接收到客户端的会话创建请求后，会结合自己的超时时间来决定。

#### 七.最后判断是否需要重新创建会话

服务端会根据会话创建请求中是否包含sessionID来判断是否需要创建会话。如果会话创建请求已包含了sessionID，则认为客户端正在进行会话重连。此时就需要执行ZooKeeperServer的reopenSession()方法重新打开会话，否则就执行ZooKeeperServer的createSession()方法创建会话。重新打开会话可能发生在两次请求前后，由不同的Follower接收到进行处理。

```java
public class NIOServerCnxn extends ServerCnxn {
    private final ZooKeeperServer zkServer;//此时应为LeaderZooKeeperServer
    private final SocketChannel sock;
    private boolean initialized;
    ...
    void doIO(SelectionKey k) throws InterruptedException {
        ...
        if (k.isReadable()) {
            //1.从底层网络IO中读取出客户端的会话创建请求
            int rc = sock.read(incomingBuffer);
            if (incomingBuffer.remaining() == 0) {
                boolean isPayload;
                if (incomingBuffer == lenBuffer) { // start of next request
                    incomingBuffer.flip();
                    isPayload = readLength(k);
                    incomingBuffer.clear();
                } else {
                    isPayload = true;
                }
                if (isPayload) {
                    readPayload();
                } else {
                    return;
                }
            }
        }
        if (k.isWritable()) {
            handleWrite(k);
        }
    }

    private void readPayload() throws IOException, InterruptedException {
        ...
        //2.判断是否是客户端会话创建请求
        if (!initialized) {//如果NIOServerCnxn还没有被初始化
            readConnectRequest();//是客户端的会话创建请求
        } else {
            readRequest();//不是客户端的会话创建请求
        }
        ...
    }

    private void readConnectRequest() throws IOException, InterruptedException {
        zkServer.processConnectRequest(this, incomingBuffer);//处理连接请求
        initialized = true;
    }

    private void readRequest() throws IOException {
        zkServer.processPacket(this, incomingBuffer);//处理非连接请求
    }
    ...
}

public class ZooKeeperServer implements SessionExpirer, ServerStats.Provider {
    ...
    public void processConnectRequest(ServerCnxn cnxn, ByteBuffer incomingBuffer) throws IOException {
        //3.反序列化输入流为ConnectRequest请求
        BinaryInputArchive bia = BinaryInputArchive.getArchive(new ByteBufferInputStream(incomingBuffer));
        ConnectRequest connReq = new ConnectRequest();
        connReq.deserialize(bia, "connect");

        //4.判断客户端是否readOnly客户端
        boolean readOnly = false;
        readOnly = bia.readBool("readOnly");
        cnxn.isOldClient = false;
        if (!readOnly && this instanceof ReadOnlyZooKeeperServer) {
            String msg = "Refusing session request for not-read-only client " + cnxn.getRemoteSocketAddress();
            LOG.info(msg);
            throw new CloseRequestException(msg);
        }

        //5.检查客户端的ZXID
        if (connReq.getLastZxidSeen() > zkDb.dataTree.lastProcessedZxid) {
            String msg = "Refusing session request for client " + cnxn.getRemoteSocketAddress()
                + " as it has seen zxid 0x" + Long.toHexString(connReq.getLastZxidSeen()) + " our last zxid is 0x"
                + Long.toHexString(getZKDatabase().getDataTreeLastProcessedZxid()) + " client must try another server";
            LOG.info(msg);
            throw new CloseRequestException(msg);
        }

        //6.协商会话超时时间
        int sessionTimeout = connReq.getTimeOut();
        int minSessionTimeout = getMinSessionTimeout();
        if (sessionTimeout < minSessionTimeout) {
            sessionTimeout = minSessionTimeout;
        }
        int maxSessionTimeout = getMaxSessionTimeout();
        if (sessionTimeout > maxSessionTimeout) {
            sessionTimeout = maxSessionTimeout;
        }
        cnxn.setSessionTimeout(sessionTimeout);
        // We don't want to receive any packets until we are sure that the session is setup
        cnxn.disableRecv();

        byte passwd[] = connReq.getPasswd();
        long sessionId = connReq.getSessionId();
        //7.判断是否需要创建会话
        if (sessionId == 0) {
            //创建新会话
            long id = createSession(cnxn, passwd, sessionTimeout);
            LOG.debug("Client attempting to establish new session:" + " session = 0x{}, zxid = 0x{}, timeout = {}, address = {}",
            Long.toHexString(id),
            Long.toHexString(connReq.getLastZxidSeen()),
            connReq.getTimeOut(),
            cnxn.getRemoteSocketAddress());
        } else {
            long clientSessionId = connReq.getSessionId();
            LOG.debug("Client attempting to renew session:" + " session = 0x{}, zxid = 0x{}, timeout = {}, address = {}",
            Long.toHexString(clientSessionId),
            Long.toHexString(connReq.getLastZxidSeen()),
            connReq.getTimeOut(),
            cnxn.getRemoteSocketAddress());
            if (serverCnxnFactory != null) {
                serverCnxnFactory.closeSession(sessionId);
            }
            if (secureServerCnxnFactory != null) {
                secureServerCnxnFactory.closeSession(sessionId);
            }
            cnxn.setSessionId(sessionId);
            //重新打开会话
            reopenSession(cnxn, sessionId, passwd, sessionTimeout);
        }
    }

    long createSession(ServerCnxn cnxn, byte passwd[], int timeout) {
        if (passwd == null) {
            passwd = new byte[0];
        }
        //创建会话环节
        long sessionId = sessionTracker.createSession(timeout);
        Random r = new Random(sessionId ^ superSecret);
        r.nextBytes(passwd);
        ByteBuffer to = ByteBuffer.allocate(4);
        to.putInt(timeout);
        cnxn.setSessionId(sessionId);
        Request si = new Request(cnxn, sessionId, 0, OpCode.createSession, to, null);
        setLocalSessionFlag(si);
        //提交请求给服务器的请求处理链处理
        submitRequest(si);
        return sessionId;
    }
    ...
    public void processPacket(ServerCnxn cnxn, ByteBuffer incomingBuffer) throws IOException {
        InputStream bais = new ByteBufferInputStream(incomingBuffer);
        BinaryInputArchive bia = BinaryInputArchive.getArchive(bais);
        RequestHeader h = new RequestHeader();
        h.deserialize(bia, "header");
        incomingBuffer = incomingBuffer.slice();
        if (h.getType() == OpCode.auth) {
            ...
        } else if (h.getType() == OpCode.sasl) {
            ...
        } else {
            ...
            Request si = new Request(cnxn, cnxn.getSessionId(), h.getXid(), h.getType(), incomingBuffer, cnxn.getAuthInfo());
            si.setOwner(ServerCnxn.me);
            setLocalSessionFlag(si);
            //提交请求给服务器的请求处理链处理
            submitRequest(si);
        }
        cnxn.incrOutstandingRequests(h);
        ...
    }

    public void submitRequest(Request si) {
        if (firstProcessor == null) {
            synchronized (this) {
                while (state == State.INITIAL) {
                    wait(1000);
                }
            }
        }
        //激活会话
        touch(si.cnxn);
        boolean validpacket = Request.isValid(si.type);
        if (validpacket) {
            //将请求交给服务器的请求处理链处理
            //如果是FollowerZooKeeperServer，那么firstProcessor就是FollowerRequestProcessor
            //FollowerRequestProcessor.processRequest会将请求转发给LeaderZooKeeperServer
            firstProcessor.processRequest(si);
            if (si.cnxn != null) {
                incInProcess();
            }
        } else {
            LOG.warn("Received packet at server of unknown type " + si.type);
            new UnimplementedRequestProcessor().processRequest(si);
        }
    }
    ...
}
```

注意：如果客户端的会话创建请求发到了Leader服务器，则直接走入口一的流程。如果客户端的会话创建请求发到了Follower服务器，除了走入口一的流程，还要通过ZooKeeperServer的submitRequest()方法，进入FollowerRequestProcessor处理器的processRequest()方法，最后将会话创建请求转发给Leader，走入口二的流程。

入口二：Leader创建的LearnerHandler收到来自Learner转发的会话创建请求。

```java
//入口二：Leader创建的LearnerHandler收到来自Learner转发的会话创建请求
public class QuorumPeerMain {
    ...
    public void runFromConfig(QuorumPeerConfig config) {
        ...
        quorumPeer = getQuorumPeer();
        ...
        quorumPeer.start();
        quorumPeer.join();
    }
}

public class QuorumPeer extends ZooKeeperThread implements QuorumStats.Provider {
    ...
    public synchronized void start() {
        //恢复集群版服务器实例QuorumPeer本地数据
        loadDataBase();
        //启动网络连接工厂ServerCnxnFactory主线程
        startServerCnxnFactory();
        adminServer.start();
        //初始化Leader选举(初始化当前投票+监听选举端口+启动选举守护线程)
        startLeaderElection();
        //开启监控JVM停顿的线程
        startJvmPauseMonitor();
        //执行集群版服务器实例QuorumPeer.run()方法
        super.start();
    }

    @Override
    public void run() {
        ...
        while (running) {
            switch (getPeerState()) {
                case LOOKING:
                    ...
                case FOLLOWING:
                    setFollower(makeFollower(logFactory));
                    follower.followLeader();
                    ...
                    break;
                case LEADING:
                    setLeader(makeLeader(logFactory));
                    leader.lead();
                    setLeader(null);
                    ...
                    break;
            }
            ...
        }
    }
    ...
}

public class Leader {
    final LeaderZooKeeperServer zk;
    ...
    void lead() throws IOException, InterruptedException {
        ...
        //创建Learner接收器LearnerCnxAcceptor监听Learner发起的连接请求
        cnxAcceptor = new LearnerCnxAcceptor();
        cnxAcceptor.start();
        //阻塞等待过半Learner完成向Leader的注册
        long epoch = getEpochToPropose(self.getId(), self.getAcceptedEpoch());
        ...
        //阻塞等待过半Learner返回ackNewEpoch响应
        waitForEpochAck(self.getId(), leaderStateSummary);
        ...
        //阻塞等待过半Learner完成数据同步
        waitForNewLeaderAck(self.getId(), zk.getZxid());
        ...
        //开始启动Leader绑定的LeaderZooKeeperServer服务器实例
        startZkServer();
        ...
    }

    //Start up Leader ZooKeeper server and initialize zxid to the new epoch
    private synchronized void startZkServer() {
        ...
        //初始化LeaderZooKeeperServer：创建并启动会话管理器 + 初始化请求处理链
        zk.startup();
        self.updateElectionVote(getEpoch());
        zk.getZKDatabase().setlastProcessedZxid(zk.getZxid());
    }
    ...
    private final ServerSocket ss;

    class LearnerCnxAcceptor extends ZooKeeperCriticalThread {
        ...
        @Override
        public void run() {
            while (!stop) {
                //获取ACCEPT请求
                Socket s = ss.accept();
                s.setSoTimeout(self.tickTime * self.initLimit);
                s.setTcpNoDelay(nodelay);
                BufferedInputStream is = new BufferedInputStream(s.getInputStream());
                //Leader会和每个Learner建立连接，并创建对应的LearnerHandler实例
                LearnerHandler fh = new LearnerHandler(s, is, Leader.this);
                fh.start();
                ...
            }
        }
        ...
    }
}

public class LearnerHandler extends ZooKeeperThread {
    final Leader leader;
    protected long sid = 0;//ZooKeeper server identifier of this learner
    protected final Socket sock;
    private BinaryInputArchive ia;
    private BinaryOutputArchive oa;
    ...
    @Override
    public void run() {
        leader.addLearnerHandler(this);
        tickOfNextAckDeadline = leader.self.tick.get() + leader.self.initLimit + leader.self.syncLimit;
        //将ia和oa与Socket进行绑定
        //以便当Leader通过oa发送LeaderInfo消息给Learner时，可以通过ia读取到Learner的ackNewEpoch响应
        ia = BinaryInputArchive.getArchive(bufferedInput);
        bufferedOutput = new BufferedOutputStream(sock.getOutputStream());
        oa = BinaryOutputArchive.getArchive(bufferedOutput);

        QuorumPacket qp = new QuorumPacket();
        ia.readRecord(qp, "packet");
        byte learnerInfoData[] = qp.getData();
        ...
        //根据LearnerInfo信息解析出Learner的SID
        ByteBuffer bbsid = ByteBuffer.wrap(learnerInfoData);
        if (learnerInfoData.length >= 8) {
            this.sid = bbsid.getLong();
        }
        ...
        //根据Learner的ZXID解析出对应Learner的epoch
        long lastAcceptedEpoch = ZxidUtils.getEpochFromZxid(qp.getZxid());
        long zxid = qp.getZxid();
        //将Learner的epoch和Leader的epoch进行比较
        //如果Learner的epoch更大，则更新Leader的epoch为Learner的epoch + 1
        long newEpoch = leader.getEpochToPropose(this.getSid(), lastAcceptedEpoch);
        long newLeaderZxid = ZxidUtils.makeZxid(newEpoch, 0);
        ...
        //发送一个包含该epoch的LeaderInfo消息给该LearnerHandler对应的Learner
        QuorumPacket newEpochPacket = new QuorumPacket(Leader.LEADERINFO, newLeaderZxid, ver, null);
        oa.writeRecord(newEpochPacket, "packet");
        bufferedOutput.flush();
        QuorumPacket ackEpochPacket = new QuorumPacket();
        //发送包含该epoch的LeaderInfo消息后等待Learner响应
        //读取Learner返回的ackNewEpoch响应
        ia.readRecord(ackEpochPacket, "packet");
        ...
        //等待过半Learner响应
        leader.waitForEpochAck(this.getSid(), ss);
        ...
        //下面执行与Learner的数据同步
        peerLastZxid = ss.getLastZxid();
        boolean needSnap = syncFollower(peerLastZxid, leader.zk.getZKDatabase(), leader);
        if (needSnap) {
            long zxidToSend = leader.zk.getZKDatabase().getDataTreeLastProcessedZxid();
            oa.writeRecord(new QuorumPacket(Leader.SNAP, zxidToSend, null, null), "packet");
            bufferedOutput.flush();
            // Dump data to peer
            leader.zk.getZKDatabase().serializeSnapshot(oa);
            oa.writeString("BenWasHere", "signature");
            bufferedOutput.flush();
        }
        LOG.debug("Sending NEWLEADER message to " + sid);
        if (getVersion() < 0x10000) {
            QuorumPacket newLeaderQP = new QuorumPacket(Leader.NEWLEADER, newLeaderZxid, null, null);
            oa.writeRecord(newLeaderQP, "packet");
        } else {
            QuorumPacket newLeaderQP = new QuorumPacket(Leader.NEWLEADER, newLeaderZxid, leader.self.getLastSeenQuorumVerifier().toString().getBytes(), null);
            queuedPackets.add(newLeaderQP);
        }
        bufferedOutput.flush();
        //Start thread that blast packets in the queue to learner
        startSendingPackets();

        //Have to wait for the first ACK, wait until the leader is ready, and only then we can start processing messages.
        qp = new QuorumPacket();
        ia.readRecord(qp, "packet");

        //阻塞等待过半Learner完成数据同步，接下来就可以启动QuorumPeer服务器实例了
        leader.waitForNewLeaderAck(getSid(), qp.getZxid());
        ...
        //接下来处理Learner发送给Leader的请求，包括PING心跳、事务请求转发等
        while (true) {
            qp = new QuorumPacket();
            ia.readRecord(qp, "packet");
            ...
            switch (qp.getType()) {
                ...
                case Leader.REQUEST:
                    bb = ByteBuffer.wrap(qp.getData());
                    sessionId = bb.getLong();
                    cxid = bb.getInt();
                    type = bb.getInt();
                    bb = bb.slice();
                    Request si;
                    if (type == OpCode.sync) {
                        si = new LearnerSyncRequest(this, sessionId, cxid, type, bb, qp.getAuthinfo());
                    } else {
                        si = new Request(null, sessionId, cxid, type, bb, qp.getAuthinfo());
                    }
                    si.setOwner(this);
                    //让Leader执行Learner转发过来的请求，比如会话创建请求
                    leader.zk.submitLearnerRequest(si);
                    break;
                ...
            }
        }
    }
    ...
}

public class LeaderZooKeeperServer extends QuorumZooKeeperServer {
    ...
    public void submitLearnerRequest(Request request) {
        //交给LeaderZooKeeperServer的PrepRequestProcessor处理器进行处理
        prepRequestProcessor.processRequest(request);
    }
    ...
}
```

### (2)会话创建环节

接下来分析执行ZooKeeperServer的createSession()方法创建会话的环节。步骤如下：

#### 一.为客户端生成sessionID

根据原子类的nextSessionId来为客户端生成sessionID。

#### 二.注册会话

也就是注册会话到sessionsById和sessionsWithTimeout中。

#### 三.激活会话

也就是更新会话管理器的过期队列sessionExpiryQueue。

#### 四.生成会话密码

服务端在为客户端创建一个会话时，会同时为客户端生成一个会话密码。这个会话密码会连同会话ID一起发给客户端，作为会话在集群中通行证。

```java
public class ZooKeeperServer implements SessionExpirer, ServerStats.Provider {
    protected SessionTracker sessionTracker;
    ...
    long createSession(ServerCnxn cnxn, byte passwd[], int timeout) {
        if (passwd == null) {
            passwd = new byte[0];
        }
        //创建会话环节
        long sessionId = sessionTracker.createSession(timeout);
        //4.生成会话密码
        Random r = new Random(sessionId ^ superSecret);
        r.nextBytes(passwd);
        ByteBuffer to = ByteBuffer.allocate(4);
        to.putInt(timeout);
        cnxn.setSessionId(sessionId);
        Request si = new Request(cnxn, sessionId, 0, OpCode.createSession, to, null);
        setLocalSessionFlag(si);
        //提交请求给服务器的请求处理链处理
        submitRequest(si);
        return sessionId;
    }
    ...
}

public class SessionTrackerImpl extends ZooKeeperCriticalThread implements SessionTracker {
    private final ExpiryQueue<SessionImpl> sessionExpiryQueue;//会话管理器的过期队列
    private final AtomicLong nextSessionId = new AtomicLong();//当前生成的会话ID
    ConcurrentHashMap<Long, SessionImpl> sessionsById;//根据会话ID来管理具体的会话实体
    ConcurrentMap<Long, Integer> sessionsWithTimeout;//根据不同的会话ID管理每个会话的超时时间
    ...
    public long createSession(int sessionTimeout) {
        //1.生成sessionID
        long sessionId = nextSessionId.getAndIncrement();
        addSession(sessionId, sessionTimeout);
        return sessionId;
    }

    public synchronized boolean addSession(long id, int sessionTimeout) {
        //2.注册会话
        sessionsWithTimeout.put(id, sessionTimeout);
        boolean added = false;
        SessionImpl session = sessionsById.get(id);
        if (session == null) {
            session = new SessionImpl(id, sessionTimeout);
        }
        //2.注册会话
        SessionImpl existedSession = sessionsById.putIfAbsent(id, session);
        if (existedSession != null) {
            session = existedSession;
        } else {
            added = true;
            LOG.debug("Adding session 0x" + Long.toHexString(id));
        }
        //3.更新会话管理器的过期队列
        updateSessionExpiry(session, sessionTimeout);
        return added;
    }

    private void updateSessionExpiry(SessionImpl s, int timeout) {
        logTraceTouchSession(s.sessionId, timeout, "");
        sessionExpiryQueue.update(s, timeout);
    }
    ...
}
```

### (3)请求预处理环节

在ZooKeeperServer的createSession()方法中完成创建会话后，便会执行ZooKeeperServer的submitRequest()方法把请求提交给请求处理链。

#### 一.将请求交给PrepRequestProcessor处理器

收到的会话创建请求会交给Leader的PrepRequestProcessor请求预处理器处理。在ZooKeeperServer的submitRequest()方法把请求提交给第一个请求处理器前，会执行ZooKeeperServer的touch()方法进行一次会话的激活。之后，请求就会被PrepRequestProcessor预处理器进行处理。

#### 二.创建和设置请求的事务头TxnHeader

通过request.setHdr(new TxnHeader())创建事务头。之后就可通过request.getHdr()方法判断请求是否有事务头来识别请求是否为事务请求。

#### 三.创建和设置请求的事务体CreateSessionTxn

通过request.setTxn(new CreateSessionTxn())创建事务体。

#### 四.注册与激活会话

也就是注册会话和更新会话管理器的过期队列。由于在会话创建环节已经注册过会话和已经更新过会话管理器的过期队列了，所以这里进行会话注册和过期队列更新是为了处理Learner转发的会话创建请求。对于Learner转发的会话请求，虽然在Learner的会话管理器注册了会话，但还没在Leader的会话管理器中进行注册，因此需要在预处理器进行注册。

```java
public class ZooKeeperServer implements SessionExpirer, ServerStats.Provider {
    protected SessionTracker sessionTracker;
    ...
    long createSession(ServerCnxn cnxn, byte passwd[], int timeout) {
        if (passwd == null) {
            passwd = new byte[0];
        }
        //创建会话环节
        long sessionId = sessionTracker.createSession(timeout);
        //4.生成会话密码
        Random r = new Random(sessionId ^ superSecret);
        r.nextBytes(passwd);
        ByteBuffer to = ByteBuffer.allocate(4);
        to.putInt(timeout);
        cnxn.setSessionId(sessionId);
        Request si = new Request(cnxn, sessionId, 0, OpCode.createSession, to, null);
        setLocalSessionFlag(si);
        //提交请求给服务器的请求处理链处理
        submitRequest(si);
        return sessionId;
    }

    public void submitRequest(Request si) {
        if (firstProcessor == null) {
            synchronized (this) {
                while (state == State.INITIAL) {
                    wait(1000);
                }
            }
        }
        //激活会话
        touch(si.cnxn);
        boolean validpacket = Request.isValid(si.type);
        if (validpacket) {
            //1.将请求交给服务器的请求处理链处理
            //如果是FollowerZooKeeperServer，那么firstProcessor就是FollowerRequestProcessor
            //FollowerRequestProcessor.processRequest会将请求转发给LeaderZooKeeperServer
            //如果是LeaderZooKeeperServer，那么firstProcessor就是LeaderRequestProcessor
            //LeaderRequestProcessor的nextProcessor就是PrepRequestProcessor请求预处理器
            firstProcessor.processRequest(si);
            if (si.cnxn != null) {
                incInProcess();
            }
        } else {
            LOG.warn("Received packet at server of unknown type " + si.type);
            new UnimplementedRequestProcessor().processRequest(si);
        }
    }

    void touch(ServerCnxn cnxn) throws MissingSessionException {
        if (cnxn == null) {
            return;
        }
        long id = cnxn.getSessionId();
        int to = cnxn.getSessionTimeout();
        if (!sessionTracker.touchSession(id, to)) {
            throw new MissingSessionException("No session with sessionid 0x" + Long.toHexString(id) + " exists, probably expired and removed");
        }
    }
    ...
}

public class PrepRequestProcessor extends ZooKeeperCriticalThread implements RequestProcessor {
    RequestProcessor nextProcessor;
    LinkedBlockingQueue<Request> submittedRequests = new LinkedBlockingQueue<Request>();

    public void processRequest(Request request) {
        //将请求添加到请求队列
        submittedRequests.add(request);
    }
    ...
    @Override
    public void run() {
        while (true) {
            Request request = submittedRequests.take();
            ...
            pRequest(request);
        }
    }

    protected void pRequest(Request request) throws RequestProcessorException {
        request.setHdr(null);
        request.setTxn(null);
        switch (request.type) {
            ...
            case OpCode.createSession:
            case OpCode.closeSession:
                if (!request.isLocalSession()) {
                    pRequest2Txn(request.type, zks.getNextZxid(), request, null, true);
                }
                break;
            ...
        }
        ...
        request.zxid = zks.getZxid();
        //将请求交给下一个处理器来处理
        nextProcessor.processRequest(request);
    }

    //下面这个方法专门用来对事务请求进行预处理
    protected void pRequest2Txn(int type, long zxid, Request request, Record record, boolean deserialize) {
        //2.创建和设置请求的事务头
        request.setHdr(new TxnHeader(request.sessionId, request.cxid, zxid, Time.currentWallTime(), type));
        switch (type) {
            ...
            case OpCode.createSession:
                request.request.rewind();
                int to = request.request.getInt();
                //3.创建和设置请求的事务体
                request.setTxn(new CreateSessionTxn(to));
                request.request.rewind();
                //4.注册会话和更新会话管理器的过期队列
                if (request.isLocalSession()) {
                    // This will add to local session tracker if it is enabled
                    zks.sessionTracker.addSession(request.sessionId, to);
                } else {
                    // Explicitly add to global session if the flag is not set
                    zks.sessionTracker.addGlobalSession(request.sessionId, to);
                }
                zks.setOwner(request.sessionId, request.getOwner());
                break;
            ...
        }
    }
    ...
}
```

### (4)事务处理环节

收到的会话创建请求经过Leader的PrepRequestProcessor请求预处理器处理后，便会被下一个处理器ProposalRequestProcessor事务投票处理器处理。

ProposalRequestProcessor处理器是与Proposal提议相关的处理器，Proposal提议是zk中针对事务请求发起一个投票流程时对事务请求的包装。

从ProposalRequestProcessor事务投票处理器将请求处理分成三个流程：Commit流程、Proposal流程、Sync流程。

```java
public class LeaderZooKeeperServer extends QuorumZooKeeperServer {
    ...
    @Override
    protected void setupRequestProcessors() {
        RequestProcessor finalProcessor = new FinalRequestProcessor(this);
        RequestProcessor toBeAppliedProcessor = new Leader.ToBeAppliedRequestProcessor(finalProcessor, getLeader());
        commitProcessor = new CommitProcessor(toBeAppliedProcessor, Long.toString(getServerId()), false, getZooKeeperServerListener());
        commitProcessor.start();
        //构建ProposalRequestProcessor处理器，下一个处理器为CommitProcessor处理器
        ProposalRequestProcessor proposalProcessor = new ProposalRequestProcessor(this, commitProcessor);
        proposalProcessor.initialize();//初始化ProposalRequestProcessor处理器
        prepRequestProcessor = new PrepRequestProcessor(this, proposalProcessor);
        prepRequestProcessor.start();
        firstProcessor = new LeaderRequestProcessor(this, prepRequestProcessor);
        setupContainerManager();
    }
    ...
}

//ProposalRequestProcessor的nextProcessor就是CommitProcessor
public class ProposalRequestProcessor implements RequestProcessor {
    LeaderZooKeeperServer zks;
    RequestProcessor nextProcessor;//nextProcessor其实就是CommitProcessor处理器
    SyncRequestProcessor syncProcessor;//事务日志处理器，它的下一个处理器是AckRequestProcessor

    public ProposalRequestProcessor(LeaderZooKeeperServer zks, RequestProcessor nextProcessor) {
        this.zks = zks;
        this.nextProcessor = nextProcessor;
        AckRequestProcessor ackProcessor = new AckRequestProcessor(zks.getLeader());
        //创建事务日志处理器，它的下一个处理器是AckRequestProcessor
        syncProcessor = new SyncRequestProcessor(zks, ackProcessor);
    }

    //初始化ProposalRequestProcessor处理器
    public void initialize() {
        syncProcessor.start();//启动事务日志处理器的线程
    }

    public void processRequest(Request request) throws RequestProcessorException {
        if (request instanceof LearnerSyncRequest) {
            //处理Learner的数据同步请求
            zks.getLeader().processSync((LearnerSyncRequest)request);
        } else {
            //Commit流程，nextProcessor其实就是CommitProcessor处理器
            nextProcessor.processRequest(request);
            if (request.getHdr() != null) {//判断是不是事务请求
                //Proposal流程，发起投票
                zks.getLeader().propose(request);
                //Sync流程，将请求添加到队列，然后由事务日志处理器线程去处理
                syncProcessor.processRequest(request);
            }
        }
    }
    ...
}
```

Sync流程：

Sync流程就是使用SyncRequestProcessor事务日志处理器记录事务日志。

ProposalRequestProcessor的processRequest()方法处理请求时，首先会判断该请求是否是事务请求，如果是则通过事务日志将其记录下来。Leader和Follower的请求处理链中都有这个事务日志处理器SyncRequestProcessor。

通过SyncRequestProcessor处理器完成事务日志记录后，Leader会由AckRequestProcessor向Leader自己发送ACK消息，每个Follower也都会由SendAckRequestProcessor向Leader发送ACK消息。从而表明每个服务器自身已完成事务日志的记录，以便Leader的Proposal提议的投票收集器可以统计投票情况。

Leader中的AckRequestProcessor处理器和Follower中的SendAckRequestProcessor处理器，最终都会触发调用Leader的processAck()方法和tryToCommit()方法，而Leader的tryToCommit()方法又会调用CommitProcessor的commit()方法进行事务提交。

```java
//SyncRequestProcessor事务日志处理器，它的下一个处理器是AckRequestProcessor
public class SyncRequestProcessor extends ZooKeeperCriticalThread implements RequestProcessor {
    ...
    private final LinkedBlockingQueue<Request> queuedRequests = new LinkedBlockingQueue<Request>();
    private final RequestProcessor nextProcessor;//AckRequestProcessor处理器

    public void processRequest(Request request) {
        //将请求添加到队列
        queuedRequests.add(request);
    }

    @Override
    public void run() {
        ...
        nextProcessor.processRequest(si);
        ...
    }
}

//SyncRequestProcessor的nextProcessor就是AckRequestProcessor
class AckRequestProcessor implements RequestProcessor {
    Leader leader;

    AckRequestProcessor(Leader leader) {
        this.leader = leader;
    }

    //Forward the request as an ACK to the leader
    public void processRequest(Request request) {
        QuorumPeer self = leader.self;
        if (self != null) {
            //Leader也作为参与Proposal投票的一份子进行ACK响应
            //将Leader的SID添加到Proposal提议的投票收集器里 + 检查Proposal提议的投票收集器是否有过半ACK才提交
            leader.processAck(self.getId(), request.zxid, null);
        } else {
            LOG.error("Null QuorumPeer");
        }
    }
}

public class LearnerHandler extends ZooKeeperThread {
    ...
    @Override
    public void run() {
        ...
        while (true) {
            ...
            switch (qp.getType()) {
                case Leader.ACK:
                    ...
                    //如果Leader收到Follower的SendAckRequestProcessor处理器对某Proposal提议请求返回的ACK响应
                    //那么就将Follower的SID添加到该Proposal提议的投票收集器里
                    leader.processAck(this.sid, qp.getZxid(), sock.getLocalSocketAddress());
                    break;
                ...
            }
        }
        ...
    }
    ...
}

public class Leader {
    final ConcurrentMap<Long, Proposal> outstandingProposals = new ConcurrentHashMap<Long, Proposal>();
    ...
    //收集投票
    synchronized public void processAck(long sid, long zxid, SocketAddress followerAddr) {
        ...
        //检查请求的ZXID，需要比上次已提交的请求的ZXID也就是lastCommitted要大
        if (lastCommitted >= zxid) {
            if (LOG.isDebugEnabled()) {
                LOG.debug("proposal has already been committed, pzxid: 0x{} zxid: 0x{}", Long.toHexString(lastCommitted), Long.toHexString(zxid));
            }
            // The proposal has already been committed
            return;
        }
        Proposal p = outstandingProposals.get(zxid);
        //将Leader的SID添加到Proposal提议的投票收集器里
        p.addAck(sid);
        //尝试提交，即检查Proposal提议的投票收集器中是否有过半ACK响应
        boolean hasCommitted = tryToCommit(p, zxid, followerAddr);
        ...
    }

    synchronized public boolean tryToCommit(Proposal p, long zxid, SocketAddress followerAddr) {
        //如果提议队列中存在该提议的前一个提议，说明该提议的前一个提议还没提交，那么就返回false
        if (outstandingProposals.containsKey(zxid - 1)) return false;
        //getting a quorum from all necessary configurations.
        //Proposal提议的投票收集器是否已过半
        if (!p.hasAllQuorums()) {
            return false;
        }
        ...
        outstandingProposals.remove(zxid);
        if (p.request != null) {
            //将请求放入toBeApplied队列
            toBeApplied.add(p);
        }
        ...
        //一旦提议通过，马上就要在Leader中标记lastCommitted即最新的提交ZXID
        commit(zxid);//给Follower广播commit消息
        inform(p);//给Observer发送commit消息
        ...
        //调用CommitProcessor处理器的commit方法提交请求
        zk.commitProcessor.commit(p.request);//让Leader执行commit消息
        //下面处理的是Learner发起的同步请求
        if (pendingSyncs.containsKey(zxid)) {
            for (LearnerSyncRequest r: pendingSyncs.remove(zxid)) {
                sendSync(r);
            }
        }
        return  true;
    }
    ...
    static public class Proposal extends SyncedLearnerTracker {
        public QuorumPacket packet;
        public Request request;
        ...
    }
}

public class SyncedLearnerTracker {
    protected ArrayList<QuorumVerifierAcksetPair> qvAcksetPairs = new ArrayList<QuorumVerifierAcksetPair>();
    ...
    //添加到投票收集器
    public boolean addAck(Long sid) {
        boolean change = false;
        for (QuorumVerifierAcksetPair qvAckset : qvAcksetPairs) {
            if (qvAckset.getQuorumVerifier().getVotingMembers().containsKey(sid)) {
                qvAckset.getAckset().add(sid);
                change = true;
            }
        }
        return change;
    }

    //判断投票收集器是否过半
    public boolean hasAllQuorums() {
        for (QuorumVerifierAcksetPair qvAckset : qvAcksetPairs) {
            if (!qvAckset.getQuorumVerifier().containsQuorum(qvAckset.getAckset()))
                return false;
        }
        return true;
    }
    ...
}
```

Proposal流程：

zk客户端的每个事务请求都需要zk集群中过半机器投票认可才能提交到内存数据库，所以ProposalRequestProcessor处理器会执行如下Proposal流程：

#### 一.调用Leader的propose()方法发起投票

如果ProposalRequestProcessor处理器发现当前请求是事务请求，那么接下来就会调用Leader的propose()方法发起一轮事务投票。在发起事务投票前，Leader的propose()方法会先检查服务端ZXID是否可用。如果当前服务端的ZXID可用，就可以开始事务投票。

#### 二.在Leader的propose()方法中生成Proposal

根据请求创建Proposal提议对象，作为zk服务器状态的一次变更申请。

#### 三.调用Leader的sendPacket()方法广播提议

生成提议后，先将提议放入投票箱outstandingProposals队列中，然后再将该提议广播给所有的Follower服务器。

#### 四.调用Leader的processAck()方法收集投票

Follower服务器接收到Leader发过来的这个提议后，会先经过SyncRequestProcessor处理器进行事务日志记录。完成事务日志的记录后，Proposal提议请求会交给SendAckRequestProcessor处理，SendAckRequestProcessor就会发送ACK消息给Leader服务器。Leader服务器会通过LearnerHandler收到Follower发送的ACK消息，然后调用Leader的processAck()方法来统计提议的投票情况。

#### 五.在Leader的tryToCommit()方法中将请求放入toBeApplied队列中

Leader的tryToCommit()方法首先会判断提议是否获得集群过半机器的投票。如果获得则表明提议通过，接下来就会将请求放入toBeApplied队列。

#### 六.在Leader的tryToCommit()方法中广播Commit消息

当Leader的tryToCommit()方法确认提议已经可以被提交后，就会向Leader和Follower服务器发送Commit消息，让所有服务器提交事务。

注意：由于Observer服务器并未参与提议投票，因此没保存关于提议的任何消息。所以在广播Commit消息时，需要区别对待。Leader会广播一种叫INFORM的消息给Observer，该消息包含提议的内容。由于Follower服务器参与提议投票，已保存所有关于提议的消息，因此Leader只需向Follower服务器广播提议的ZXID即可。

```java
public class Leader {
    final ConcurrentMap<Long, Proposal> outstandingProposals = new ConcurrentHashMap<Long, Proposal>();
    ...
    //1.发起投票
    public Proposal propose(Request request) throws XidRolloverException {
        if ((request.zxid & 0xffffffffL) == 0xffffffffL) {
            String msg = "zxid lower 32 bits have rolled over, forcing re-election, and therefore new epoch start";
            shutdown(msg);
            throw new XidRolloverException(msg);
        }
        byte[] data = SerializeUtils.serializeRequest(request);
        proposalStats.setLastBufferSize(data.length);
        QuorumPacket pp = new QuorumPacket(Leader.PROPOSAL, request.zxid, data, null);
        //2.生成Proposal提议
        Proposal p = new Proposal();
        p.packet = pp;
        p.request = request;

        synchronized(this) {
            p.addQuorumVerifier(self.getQuorumVerifier());
            if (request.getHdr().getType() == OpCode.reconfig) {
                self.setLastSeenQuorumVerifier(request.qv, true);
            }
            if (self.getQuorumVerifier().getVersion()<self.getLastSeenQuorumVerifier().getVersion()) {
                p.addQuorumVerifier(self.getLastSeenQuorumVerifier());
            }
            lastProposed = p.packet.getZxid();
            //将发送的Proposal提议放入outstandingProposals队列中
            outstandingProposals.put(lastProposed, p);
            //广播Proposal提议，其实就是把Proposal提议交给LearnerHandler处理
            sendPacket(pp);
        }
        return p;
    }

    //3.广播提议
    void sendPacket(QuorumPacket qp) {
        synchronized (forwardingFollowers) {
            //广播提议
            for (LearnerHandler f : forwardingFollowers) {
                //LearnerHandler.queuePacket方法会将提议放入其发送队列里
                f.queuePacket(qp);
            }
        }
    }

    //4.收集投票
    synchronized public void processAck(long sid, long zxid, SocketAddress followerAddr) {
        ...
        //检查请求的ZXID，需要比上次已提交的请求的ZXID也就是lastCommitted要大
        if (lastCommitted >= zxid) {
            if (LOG.isDebugEnabled()) {
                LOG.debug("proposal has already been committed, pzxid: 0x{} zxid: 0x{}", Long.toHexString(lastCommitted), Long.toHexString(zxid));
            }
            // The proposal has already been committed
            return;
        }
        Proposal p = outstandingProposals.get(zxid);
        //将Leader的SID添加到Proposal提议的投票收集器里
        p.addAck(sid);
        //尝试提交，即检查Proposal提议的投票收集器中是否有过半ACK响应
        boolean hasCommitted = tryToCommit(p, zxid, followerAddr);
        ...
    }

    synchronized public boolean tryToCommit(Proposal p, long zxid, SocketAddress followerAddr) {
        //如果提议队列中存在该提议的前一个提议，说明该提议的前一个提议还没提交，那么就返回false
        if (outstandingProposals.containsKey(zxid - 1)) return false;
        //getting a quorum from all necessary configurations.
        //Proposal提议的投票收集器是否已过半
        if (!p.hasAllQuorums()) {
            return false;
        }
        ...
        outstandingProposals.remove(zxid);
        if (p.request != null) {
            //5.将请求放入toBeApplied队列
            toBeApplied.add(p);
        }
        ...
        //一旦提议通过，马上就在Leader中标记lastCommitted即最新的提交ZXID
        commit(zxid);//给Follower广播commit消息
        inform(p);//给Observer发送commit消息
        ...
        //调用CommitProcessor处理器的commit方法提交请求
        zk.commitProcessor.commit(p.request);//让Leader执行commit消息
        //下面处理的是Learner发起的同步请求
        if (pendingSyncs.containsKey(zxid)) {
            for (LearnerSyncRequest r: pendingSyncs.remove(zxid)) {
                sendSync(r);
            }
        }
        return  true;
    }

    //6.广播commit消息
    public void commit(long zxid) {
        synchronized(this) {
            lastCommitted = zxid;
        }
        QuorumPacket qp = new QuorumPacket(Leader.COMMIT, zxid, null, null);
        sendPacket(qp);
    }

    void sendPacket(QuorumPacket qp) {
        synchronized (forwardingFollowers) {
            for (LearnerHandler f : forwardingFollowers) {
                //调用LearnerHandler的queuePacket方法添加Packet到发送队列
                f.queuePacket(qp);
            }
        }
    }

    public void inform(Proposal proposal) {
        QuorumPacket qp = new QuorumPacket(Leader.INFORM, proposal.request.zxid, proposal.packet.getData(), null);
        sendObserverPacket(qp);
    }
    ...
}

public class LearnerHandler extends ZooKeeperThread {
    protected final Socket sock;
    private BinaryInputArchive ia;
    private BinaryOutputArchive oa;
    private final BufferedInputStream bufferedInput;
    private BufferedOutputStream bufferedOutput;
    //要被发送给Learner的Packets
    final LinkedBlockingQueue<QuorumPacket> queuedPackets = new LinkedBlockingQueue<QuorumPacket>();
    ...
    void queuePacket(QuorumPacket p) {
        queuedPackets.add(p);
    }

    @Override
    public void run() {
        ...
        ia = BinaryInputArchive.getArchive(bufferedInput);
        bufferedOutput = new BufferedOutputStream(sock.getOutputStream());
        oa = BinaryOutputArchive.getArchive(bufferedOutput);
        ...
        //启动线程从发送队列中提取Packet发送给Learner
        startSendingPackets();
        ...
    }

    protected void startSendingPackets() {
        //启动线程从发送队列中提取Packet发送给Learner
        new Thread() {
            public void run() {
                Thread.currentThread().setName("Sender-" + sock.getRemoteSocketAddress());
                //发送queuedPackets中的packet
                sendPackets();
            }
        }.start();
        sendingThreadStarted = true;
    }

    private void sendPackets() throws InterruptedException {
        while (true) {
            QuorumPacket p = queuedPackets.poll();
            ...
            oa.writeRecord(p, "packet");
        }
    }
    ...
}
```

Commit流程：

ProposalRequestProcessor请求处理器的nextProcessor就是CommitProcessor。注意：Commit流程会处理事务请求和非事务请求。

#### 一.将请求交给CommitProcessor请求处理器处理

ProposalRequestProcessor的processRequest()方法在处理请求时，首先就会将请求交给CommitProcessor请求处理器处理。CommitProcessor请求处理器收到请求后，不会立即处理，会先将请求放入queuedRequests队列中。

#### 二.处理queuedRequests请求队列

CommitProcessor会启动一个线程来处理queuedRequests请求队列，CommitProcessor会有个单独的线程处理从上一个处理器流转来的请求。

#### 三.等待Proposal提议的投票

在ProposalRequestProcessor的Commit流程处理的同时，ProposalRequestProcessor的Proposal流程会生成一个提议Proposal，然后将该Proposal提议广播给所有的Follower服务器。所以此时会阻塞Commit流程，等待Proposal提议的投票结束。

#### 四.投票通过

当Leader的tryToCommit()方法发现Proposal提议的投票通过时，会调用CommitProcessor的commit()方法。此时该方法会将请求放入到committedRequests队列中，同时唤醒被阻塞的Commit流程。

#### 五.标记nextPending

如果从queuedRequests队列中取出的请求是一个事务请求，那么就需要进行集群中各服务器之间的投票处理，同时需要将nextPending标记为当前请求。

标记nextPending的作用：一是为了确保事务请求的顺序性，二是便于CommitProcessor检测当前集群中是否正在进行事务请求的投票。

#### 六.提交请求

一旦发现committedRequests队列中已经有可以提交的请求，那么Commit流程就会开始提交请求。

在提交请求前，为了保证事务请求的顺序执行，Commit流程还会对比：标记的nextPending和committedRequests队列的第一个请求是否一致。

```cs
//ProposalRequestProcessor处理器的nextProcessor就是CommitProcessor
public class CommitProcessor extends ZooKeeperCriticalThread implements RequestProcessor {
    //请求队列
    protected final LinkedBlockingQueue<Request> queuedRequests = new LinkedBlockingQueue<Request>();
    protected final LinkedBlockingQueue<Request> committedRequests = new LinkedBlockingQueue<Request>();
    //下一个要提交的请求
    protected final AtomicReference<Request> nextPending = new AtomicReference<Request>();
    //当前正在处理的请求数
    protected AtomicInteger numRequestsProcessing = new AtomicInteger(0);
    ...
    @Override
    public void processRequest(Request request) {
        if (stopped) {
            return;
        }
        //1.将请求添加到queuedRequests请求队列中
        queuedRequests.add(request);
        if (!isWaitingForCommit()) {
            wakeup();//唤醒
        }
    }

    private boolean isProcessingRequest() {
        return numRequestsProcessing.get() != 0;
    }

    private boolean isWaitingForCommit() {
        return nextPending.get() != null;
    }

    private boolean isProcessingCommit() {
        return currentlyCommitting.get() != null;
    }

    synchronized private void wakeup() {
        notifyAll();//唤醒阻塞的线程
    }

    //2.开启单独的线程处理queuedRequests请求队列
    @Override
    public void run() {
        Request request;
        while (!stopped) {
            synchronized(this) {
                while (!stopped && ((queuedRequests.isEmpty() || isWaitingForCommit() || isProcessingCommit()) && (committedRequests.isEmpty() || isProcessingRequest()))) {
                    //3.等待Proposal投票
                    wait();//阻塞等待
                }
            }
            while (!stopped && !isWaitingForCommit() && !isProcessingCommit() && (request = queuedRequests.poll()) != null) {
                if (needCommit(request)) {//需要进行提交的事务请求
                    //5.标记nextPending
                    nextPending.set(request);//设置下一个要提交的请求
                } else {//非事务请求转交给下一个处理器
                    sendToNextProcessor(request);
                }
            }
            processCommitted();//处理提交
        }
    }

    //6.提交请求
    protected void processCommitted() {
        Request request;
        if (!stopped && !isProcessingRequest() && (committedRequests.peek() != null)) {
            if ( !isWaitingForCommit() && !queuedRequests.isEmpty()) {
                return;
            }
            request = committedRequests.poll();
            Request pending = nextPending.get();
            if (pending != null && pending.sessionId == request.sessionId && pending.cxid == request.cxid) {
                pending.setHdr(request.getHdr());
                pending.setTxn(request.getTxn());
                pending.zxid = request.zxid;
                currentlyCommitting.set(pending);
                nextPending.set(null);
                sendToNextProcessor(pending);
            } else {
                currentlyCommitting.set(request);
                sendToNextProcessor(request);
            }
        }
    }

    //4.投票通过
    public void commit(Request request) {
        committedRequests.add(request);
        if (!isProcessingCommit()) {//CommitProcessor处理器当前没有提交请求
            wakeup();//CommitProcessor唤醒线程
        }
    }

    private void sendToNextProcessor(Request request) {
        numRequestsProcessing.incrementAndGet();
        workerPool.schedule(new CommitWorkRequest(request), request.sessionId);
    }

    private class CommitWorkRequest extends WorkerService.WorkRequest {
        private final Request request;

        CommitWorkRequest(Request request) {
            this.request = request;
        }
        ...
        public void doWork() throws RequestProcessorException {
            try {
                nextProcessor.processRequest(request);
            } finally {
                currentlyCommitting.compareAndSet(request, null);
                if (numRequestsProcessing.decrementAndGet() == 0) {
                    if (!queuedRequests.isEmpty() || !committedRequests.isEmpty()) {
                        wakeup();
                    }
                }
            }
        }
    }
    ...
}
```

### (5)事务应用和响应环节

#### 一.将请求交给FinalRequestProcessor请求处理器处理

事务应用和响应环节发生在FinalRequestProcessor请求处理器中。

#### 二.首先进行事务应用

如果是会话创建请求，则进行会话创建的事务应用。如果是setData请求，则进行setData的事务应用。由于在前面只是将事务请求记录到事务日志，而内存数据库状态还未变更，因此在该环节需要将事务变更应用到内存数据库中去。

对于会话创建请求，由于会话的管理是由SessionTracker负责的。而在会话创建的环节，zk已经已经将会话信息注册到了SessionTracker中。因此此时无须对内存数据库做处理，只需再次向SessionTracker注册即可。

#### 三.然后创建响应

例如对于setData请求来说，会创建SetDataResponse响应。

#### 四.最后序列化响应并发送给客户端

调用ServerCnxn的sendResponse()方法序列化响应并发送响应给客户端。

```java
public class FinalRequestProcessor implements RequestProcessor {
    ...
    public void processRequest(Request request) {
        ...
        ProcessTxnResult rc = null;
        synchronized (zks.outstandingChanges) {
            // Need to process local session requests
            rc = zks.processTxn(request);
            if (request.getHdr() != null) {
                TxnHeader hdr = request.getHdr();
                Record txn = request.getTxn();
                long zxid = hdr.getZxid();

                while (!zks.outstandingChanges.isEmpty() && zks.outstandingChanges.peek().zxid <= zxid) {
                    ChangeRecord cr = zks.outstandingChanges.remove();
                    if (zks.outstandingChangesForPath.get(cr.path) == cr) {
                        zks.outstandingChangesForPath.remove(cr.path);
                    }
                }
            }
            // do not add non quorum packets to the queue.
            if (request.isQuorum()) {
                zks.getZKDatabase().addCommittedProposal(request);
            }
        }

        //进行事务应用
        ServerCnxn cnxn = request.cnxn;
        Record rsp = null;
        switch (request.type) {
            case OpCode.ping: {
                zks.serverStats().updateLatency(request.createTime);
                lastOp = "PING";
                cnxn.updateStatsForResponse(request.cxid, request.zxid, lastOp, request.createTime, Time.currentElapsedTime());
                cnxn.sendResponse(new ReplyHeader(-2, zks.getZKDatabase().getDataTreeLastProcessedZxid(), 0), null, "response");
                return;
            }
            case OpCode.createSession: {
                zks.serverStats().updateLatency(request.createTime);
                lastOp = "SESS";
                cnxn.updateStatsForResponse(request.cxid, request.zxid, lastOp, request.createTime, Time.currentElapsedTime());
                zks.finishSessionInit(request.cnxn, true);
                return;
            }
            case OpCode.create: {
                lastOp = "CREA";
                //创建响应
                rsp = new CreateResponse(rc.path);
                err = Code.get(rc.err);
                break;
            }
            case OpCode.setData: {
                lastOp = "SETD";
                //创建响应
                rsp = new SetDataResponse(rc.stat);
                err = Code.get(rc.err);
                break;
            }
            case OpCode.getData: {
                lastOp = "GETD";
                GetDataRequest getDataRequest = new GetDataRequest();
                ByteBufferInputStream.byteBuffer2Record(request.request, getDataRequest);
                DataNode n = zks.getZKDatabase().getNode(getDataRequest.getPath());
                if (n == null) {
                    throw new KeeperException.NoNodeException();
                }
                PrepRequestProcessor.checkACL(zks, zks.getZKDatabase().aclForNode(n), ZooDefs.Perms.READ, request.authInfo);
                Stat stat = new Stat();
                byte b[] = zks.getZKDatabase().getData(getDataRequest.getPath(), stat, getDataRequest.getWatch() ? cnxn : null);
                //创建响应
                rsp = new GetDataResponse(b, stat);
                break;
            }
            ...
        }
        ...
        long lastZxid = zks.getZKDatabase().getDataTreeLastProcessedZxid();
        ReplyHeader hdr = new ReplyHeader(request.cxid, lastZxid, err.intValue());
        zks.serverStats().updateLatency(request.createTime);
        cnxn.updateStatsForResponse(request.cxid, lastZxid, lastOp, request.createTime, Time.currentElapsedTime());
        //序列化响应并发送给客户端
        cnxn.sendResponse(hdr, rsp, "response");
        if (request.type == OpCode.closeSession) {
            cnxn.sendCloseSession();
        }
    }
    ...
}

public abstract class ServerCnxn implements Stats, Watcher {
    ...
    //序列化响应并发送给客户端
    public void sendResponse(ReplyHeader h, Record r, String tag) throws IOException {
        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        // Make space for length
        BinaryOutputArchive bos = BinaryOutputArchive.getArchive(baos);
        try {
            baos.write(fourBytes);
            bos.writeRecord(h, "header");
            if (r != null) {
                bos.writeRecord(r, tag);
            }
            baos.close();
        } catch (IOException e) {
            LOG.error("Error serializing response");
        }
        byte b[] = baos.toByteArray();
        serverStats().updateClientResponseSize(b.length - 4);
        ByteBuffer bb = ByteBuffer.wrap(b);
        bb.putInt(b.length - 4).rewind();
        sendBuffer(bb);
    }
    ...
}
public class NIOServerCnxn extends ServerCnxn {
    ...
    public void sendBuffer(ByteBuffer bb) {
        outgoingBuffers.add(bb);
        requestInterestOpsUpdate();
    }
    ...
}
```
