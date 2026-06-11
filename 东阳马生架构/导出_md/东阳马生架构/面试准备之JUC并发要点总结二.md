# 面试准备之JUC并发要点总结二

> **公众号**: 东阳马生架构  
> **发布时间**: 2025-09-10 09:00  

**大纲(25435字)**

- 1.JUC中的Lock接口
- 2.如何实现具有阻塞或唤醒功能的锁
- 3.ReentractLock如何获取锁
- 4.AQS的acquire()方法和release()方法总结
- 5.ReentractReadWriteLock的基本原理
- 6.ReentractReadWriteLock如何竞争写锁
- 7.ReentractReadWriteLock如何竞争读锁
- 8.ReentractReadWriteLock的公平锁和非公平锁
- 9.Condition的说明和源码
- 10.等待多线程完成的CountDownLatch
- 11.控制并发线程数的Semaphore
- 12.同步屏障CyclicBarrier
- 13.ConcurrentHashMap的原理
- 14.并发安全的数组列表CopyOnWriteArrayList
- 15.并发安全的链表队列ConcurrentLinkedQueue
- 16.JUC的各种阻塞队列介绍
- 17.LinkedBlockingQueue的具体实现原理
- 18.基于两个队列实现的集群同步机制
- 19.锁优化总结
- 20.线程池介绍
- 21.如何设计一个线程池
- 22.ThreadPoolExecutor线程池的执行流程
- 23.如何合理设置线程池参数 + 定制线程池
- 24.ThreadLocal的设计原理
- 25.Disruptor的生产者源码
- 26.Disruptor的消费者源码
- 27.Disruptor的WaitStrategy等待策略
- 28.Disruptor的高性能原因


简历关键词：精通JDK集合和JUC并发包，研究过相关集合源码、锁原理、AQS源码、线程池源码等，深入阅读过Disruptor源码，对高并发的处理有一定的理解。

**
**

## 1.JUC中的Lock接口

### (1)Lock接口的实现类ReentrantLock

ReentractLock是重入锁，属于排他锁，功能和synchronized类似。但是在实际中，其实比较少会使用ReentrantLock。因为ReentrantLock的实现及性能和syncrhonized差不多，所以一般推荐使用synchronized而不是ReentrantLock。

### (2)Lock接口的实现类ReentrantReadWriteLock

ReentrantReadWriteLock是可重入的读写锁，ReentrantReadWriteLock维护了两个锁：一是ReadLock，二是WriteLock。ReadLock和WriteLock都分别实现了Lock接口。

### (3)Lock接口的实现类StampedLock

ReentrantReadWriteLock锁有一个问题，如果当前有线程在调用get()方法，那么所有调用add()方法的线程必须要等调用get()方法的线程释放锁才能写，所以如果调用get()方法的线程非常多，那么就会导致写线程一直被阻塞。

StampedLock优化了ReentrantReadWriteLock的乐观锁，当有线程调用get()方法读取数据时，不会阻塞准备执行写操作的线程。

StampedLock的tryOptimisticRead()方法会返回一个stamp版本号，用来表示当前线程在读操作期间数据是否被修改过。

StampedLock提供了一个validate()方法来验证stamp版本号，如果线程在读取过程中没有其他线程对数据做修改，那么stamp的值不会变。

StampedLock使用了乐观锁的思想，避免了在读多写少场景中，大量线程占用读锁造成的写阻塞，在一定程度上提升了读写锁的并发性能。

ReentrantReadWriteLock采用的是悲观读策略。当第一个读线程获取锁后，第二个、第三个读线程还可以获取锁。这样可能会使得写线程一直拿不到锁，从而导致写线程饿死。所以其公平和非公平实现中，都会尽量避免这种情形。比如非公平锁的实现中，如果读线程在尝试获取锁时发现，AQS的等待队列中的头结点的后继结点是独占锁结点，那么读线程会阻塞。

StampedLock采用的是乐观读策略，类似于MVCC。读的时候不加锁，读出来发现数据被修改了，再升级为悲观锁。

## 2.如何实现具有阻塞或唤醒功能的锁

### (1)需要一个共享变量标记锁的状态

AQS有一个int变量state用来记录锁的状态，通过CAS操作确保对state变量操作的线程安全。

### (2)需要记录当前是哪个线程持有锁

AQS有一个Thread变量exclusiveOwnerThread用来记录持有锁的线程。当state = 0时，没有线程持有锁，此时exclusiveOwnerThread = null。当state = 1时，有一线程持有锁，此时exclusiveOwnerThread = 该线程。当state > 1，说明有一线程重入了锁。

### (3)需要支持对线程进行阻塞和唤醒

AQS使用LockSupport工具类的park()方法和unpark()方法，通过Unsafe类提供的native方法实现阻塞和唤醒线程。

### (4)需要一个无锁队列来维护阻塞线程

AQS通过一个双向链表和CAS实现了一个无锁的阻塞队列来维护阻塞的线程。

AQS中最关键的两部分是：Node等待队列和state变量。其中Node等待队列是一个双向链表，用来存放阻塞等待的线程，而state变量则用来在加锁和释放锁时标记锁的状态。

## 3.ReentractLock如何获取锁

### (1)compareAndSetState()方法尝试加锁

ReentractLock是基于NonfairSync的lock()方法来实现加锁的。AQS里有一个核心的变量state，代表了锁的状态。在NonfairSync.lock()方法中，会通过CAS操作来设置state从0变为1。如果state原来是0，那么就代表此时还没有线程获取锁，当前线程执行AQS的compareAndSetState()方法便能成功将state设置为1。

所以AQS的compareAndSetState()方法相当于在尝试加锁。AQS的compareAndSetState()方法是基于Unsafe类来实现CAS操作的，Atomic原子类也是基于Unsafe来实现CAS操作的。

### (2)setExclusiveOwnerThread()方法设置加锁线程为当前线程

如果执行compareAndSetState(0, 1)返回的是true，那么就说明加锁成功，于是执行AQS的setExclusiveOwnerThread()方法设置加锁线程为当前线程。

### (3)线程重入锁时CAS操作失败

假如线程1加锁后又调用ReentrantLock.lock()方法，应如何实现可重入锁？此时state = 1，故执行AQS的compareAndSetState(0, 1)方法会返回false。所以首先通过CAS操作，尝试获取锁会失败，然后返回false，于是便会执行AQS的acquire(1)方法。

### (4)Sync的nonfairTryAcquire()实现可重入锁

在AQS的acquire()方法中，首先会执行AQS的tryAcquire()方法尝试获取锁。但AQS的tryAcquire()方法是个保护方法，需要由子类重写。所以其实会执行继承自AQS子类Sync的NonfairSync的tryAcquire()方法，而该方法最终又执行回AQS子类Sync的nonfairTryAcquire()方法。

在AQS子类Sync的nonfairTryAcquire()方法中：首先判断state是否为0，如果是则表明此时已释放锁，可通过CAS来获取锁。否则判断持有锁的线程是否为当前线程，如果是则对state进行累加。也就是通过对state进行累加，实现持有锁的线程可以重入锁。

### (5)加锁失败的线程的具体处理流程

首先在ReentrantLock内部类NonfairSync的lock()方法中，执行AQS的compareAndSetState()方法尝试获取锁是失败的。

于是执行AQS的acquire()方法 -> 执行NonfairSync的tryAcquire()方法。也就是执行继承自AQS的Sync的nonfairTryAcquire()方法，进行判断是否是重入锁 + 是否已释放锁。发现也是失败的，所以继承自Sync的NonfairSync的tryAcquire()方法返回false。

然后在AQS的acquire()方法中，if判断的第一个条件tryAcquire()便是false，所以接着会执行acquireQueued(addWaiter(Node.EXCLUSIVE), arg)。也就是先执行AQS的addWaiter()方法将当前线程加入等待队列，然后再去执行AQS的acquireQueued()方法将当前线程挂起阻塞等待。

ReentrantLock内部类NonfairSync的lock()方法总结：如果CAS操作失败，则说明有线程正在持有锁，此时会继续调用acquire(1)。然后通过NonfairSync的tryAcquire()方法尝试获取独占锁，也就是通过Sync的nonfairTryAcquire()方法尝试获取独占锁。如果NonfairSync的tryAcquire()方法返回false，说明锁已被占用。于是执行AQS的addWaiter()方法将当前线程封装成Node并添加到等待队列，接着执行AQS的acquireQueued()方法通过自旋尝试获取锁以及挂起线程。

### (6)执行AQS的addWaiter()方法维护等待队列

在AQS的addWaiter()方法中：首先会将当前获取锁失败的线程封装为一个Node对象，然后判断等待队列(双向链表)的尾结点是否为空。如果尾结点不为空，则使用CAS操作 + 尾插法将Node对象插入等待队列中。如果尾结点为空或者尾结点不为空时CAS操作失败，则调用enq()方法通过自旋 + CAS构建等待队列或把Node对象插入等待队列。注意：等待队列的队头是个空的Node结点，新增一个结点时会从尾部插入。

### (7)执行AQS的acquireQueued()方法挂起线程

执行完AQS的addWaiter()方法后便执行AQS的acquireQueued()方法。

在AQS的acquireQueued()方法中：首先会判断传入结点的上一个结点是否为等待队列的头结点。如果是，则再次调用NonfairSync的tryAcquire()方法尝试获取锁。如果获取锁成功，则将传入的Node结点从等待队列中移除。同时设置传入的Node结点为头结点，然后将该结点设置为空。从而确保等待队列的头结点是一个空的Node结点。注意：NonfairSync的tryAcquire()方法会判断是否重入锁 + 是否已释放锁。

在AQS的acquireQueued()方法中：如果首先进行的尝试获取锁失败了，那么就执行shouldParkAfterFailedAcquire()方法判断是否要将当前线程挂起。如果需要将当前线程挂起，则会调用parkAndCheckInterrupt()方法进行挂起，也就是通过调用LockSupport的park()方法挂起当前线程。注意：如果线程被中断，只会暂时设置interrupted为true。然后还要继续等待被唤醒获取锁，才能调用selfInterrupt()方法对线程中断。

**AQS的acquireQueued()方法总结：** 如果当前结点的前驱结点不是队头结点或者当前线程尝试抢占锁失败，那么都会调用shouldParkAfterFailedAcquire()方法，修改当前线程结点的前驱结点的状态为SIGNAL \+ 决定是否应挂起当前线程。shouldParkAfterFailedAcquire()方法作用是检查当前结点的前驱结点状态。如果状态是SIGNAL，则可以挂起线程。如果状态是CANCELED，则要移除该前驱结点。如果状态是其他，则通过CAS操作修改该前驱结点的状态为SIGNAL。

### (5)如何处理正常唤醒和中断唤醒

LockSupport的park操作，会挂起一个线程。LockSupport的unpark操作，会唤醒被挂起的线程。

被LockSupport.park()方法阻塞的线程被其他线程唤醒有两种情况。情况一：其他线程调用了LockSupport.unpark()方法，正常唤醒。情况二：其他线程调用了阻塞线程Thread的interrupt()方法，中断唤醒。

正是因为被LockSupport.park()方法阻塞的线程可能会被中断唤醒，所以AQS的acquireQueued()方法才写了一个for自旋。当阻塞的线程被唤醒后，如果发现自己的前驱结点是头结点，那么就去获取锁。如果获取不到锁，那么就再次阻塞自己，不断重复直到获取到锁为止。

被LockSupport.park()方法阻塞的线程不管是正常唤醒还是被中断唤醒，唤醒后都会通过Thread.interruptrd()方法来判断是否是中断唤醒。如果是中断唤醒，唤醒后不会立刻响应中断，而是再次获取锁，获取到锁后才能响应中断。

## 4.AQS的acquire()方法和release()方法总结

### (1)acquire()方法获取锁的流程总结

首先调用AQS子类的tryAcquire()方法尝试获取锁(是否重入 + 是否释放锁)。如果获取成功，则说明是重入锁或CAS抢占释放的锁成功，于是退出返回。如果获取失败，则调用AQS的addWaiter()方法将当前线程封装成Node结点，并通过AQS的compareAndSetTail()方法将该Node结点添加到等待队列尾部。

然后将该Node结点传入AQS的acquireQueued()方法，通过自旋尝试获取锁。在AQS的acquireQueued()方法中，会判断该Node结点的前驱是否为头结点。如果不是，则挂起当前线程进行阻塞。如果是，则尝试获取锁。如果获取成功，则设置当前结点为头结点，然后退出返回。如果获取失败，则继续挂起当前线程进行阻塞。

当被阻塞线程，被其他线程中断唤醒或其对应结点的前驱结点释放了锁，那么就继续判断该线程对应结点的前驱结点是否成为头结点。

### (2)release()方法释放锁的总结

AQS的release()方法主要做了两件事情：一是通过tryRelease()方法释放锁(递减state变量)，二是通过unparkSuccessor()方法唤醒等待队列中的下一个线程。

由于是独占锁，只有持有锁的线程才有资格释放锁，所以tryRelease()方法修改state变量值时不需要使用CAS操作。

## 5.ReentractReadWriteLock的基本原理

### (1)读锁和写锁关系

表面上读锁和写锁是两把锁，但实际上只是同一把锁的两个视图。读锁和写锁在初始化的时候会共用一个Sync，也就是同一把锁、两类线程。其中读线程和读线程不互斥，读线程和写线程互斥，写线程和写线程互斥。

### (2)锁状态设计

和独占锁一样，读写锁也是使用state变量来表示锁的状态。只是将state变量拆成两半：高16位表示读锁状态，低16位表示写锁状态。

读写锁是通过位运算来快速确定读和写的状态的。假设当前state = s，则写状态等于s & ((1 << 16) - 1)，读状态等于s >>> 16。当写状态增加1时，state = s + 1。当读状态加1时，state = s + (1 << 16)。

将一个int型的state变量拆成两半，而不是用两个int型变量分别表示读锁和写锁的状态，是因为无法用一次CAS同时操作两个int型变量。

```bash
1 << 0 等于 1，(1 << 0) - 1 = 0
1 << 1 等于 10，(1 << 1) - 1 = 01
1 << 2 等于 100，(1 << 2) - 1 = 011
1 << 4 等于 1000，(1 << 4) - 1 = 0111
1 << 8 等于 100000000，(1 << 8) - 1 = 011111111
1 << 16 等于 10000000000000000，(1 << 16) - 1 = 01111111111111111
//所以s & ((1 << 16) - 1)相当于将s的高16位全部抹去，只剩下低16位

//若s = 11111，则s >>> 2 = 00111
//所以s >>> 16，就是无符号补0右移16位
```

### (3)写锁的获取与释放

写锁是一个可重入的排他锁，它只能被一个线程同时获取。如果当前线程已获取写锁，则增加写状态：s + 1。如果当前线程在获取写锁时，读锁已被获取或者自己不是已获写锁的线程，则进入等待状态。

### (4)读锁的获取与释放

读锁是一个可重入的共享锁，它能被多个线程同时获取。在写状态为0时，读锁总会被成功获取，而所做的也只是增加读状态。如果当前线程已获取读锁，则增加读状态：state = s + (1 << 16)。如果当前线程在获取读锁时，写锁已被其他其他线程获取，则该线程进入等待状态。

## 6.ReentractReadWriteLock如何竞争写锁

### (1)WriteLock的获取

WriteLock的lock()方法会调用AQS的acquire()模版方法来获取锁，而AQS的acquire()方法又会调用继承自AQS的Sync类的tryAcquire()方法。

在Sync类的tryAcquire()方法中，getState()方法会返回当前state变量的值。exclusiveCount()方法会从state变量中查找当前获得写锁的线程数量，writerShouldBlock()方法会判断当前写线程在抢占锁时是否应该阻塞。

**情况一：c != 0 && w == 0**

说明此时有线程持有读锁，所以当前线程获取不到写锁，返回false。由此可见，一个线程获取读锁后不能再继续重入获取写锁(不能锁升级)。但从后续可知，一个线程获取写锁后可以再继续重入获取读锁(能锁降级)。

**情况二：c != 0 && w != 0**

说明此时有线程持有写锁且不可能有线程持有读锁，所以需要判断持有写锁的线程是否是当前线程自己，如果不是则返回false。

**情况三：c != 0 && w != 0 && current持有锁**

说明此时当前线程正在持有写锁，属于重入写锁的情况，需要判断重入次数，锁重入的次数不能大于65535。

**情况四：c == 0**

说明此时没有线程持有锁，所以当前线程可以通过CAS操作抢占锁。

### (2)WriteLock的释放

WriteLock的unlock()方法会调用AQS的release()模版方法来释放锁，而AQS的release()方法又会调用继承自AQS的Sync类的tryRelease()方法。

在Sync类的tryRelease()方法中，首先通过getState() - releases来递减写锁的次数。由于写锁的重入次数保存在低位，所以直接十进制相减即可。然后通过exclusiveCount()获取写锁的重入次数，如果为0说明锁释放成功。最后通过setState()方法修改state变量的值。由于写锁是独占锁，所以设置state变量的值不需要CAS操作。

## 7.ReentractReadWriteLock如何竞争读锁

### (1)ReadLock的获取

ReadLock的lock()方法会调用AQS的acquireShared()模版方法来获取读锁，而AQS的acquireShared()方法又会调用Sync类的tryAcquireShared()方法。

在继承自AQS的Sync类的tryAcquireShared()方法中：首先会判断是否有线程持有写锁 \+ 持有写锁的线程是否是当前线程。如果有线程持有写锁，但不是当前线程持有写锁，那么会阻塞当前线程。然后判断当前线程获取读锁是否应该阻塞，读锁重入次数是否小于65535，以及通过CAS修改state值来抢占读锁是否成功。

如果当前线程获取读锁不应该被阻塞，读锁重入次数也小于65535，且CAS抢占读锁也成功，那么就使用ThreadLocal记录线程重入读锁的次数。否则，就继续调用fullTryAcquireShared()方法通过自旋尝试获取锁。

如果调用Sync的tryAcquireShared()方法返回-1，则调用AQS的doAcquireShared()方法入队等待队列和阻塞当前线程。

在等待队列中，如果等待获取读锁的线程被唤醒，那么会继续循环把其后连续的所有等待获取读锁的线程都唤醒，直到遇到一个等待获取写锁的线程为止。

### (2)ReadLock的释放

ReadLock的unlock()方法会调用AQS的releaseShared()模版方法来释放锁，而AQS的releaseShared()方法又会调用Sync类的tryReleaseShared()方法。

在Sync类的tryReleaseShared()方法中：首先会结合ThreadLocal处理当前线程重入读锁的次数，然后再通过自旋 + CAS设置state值来实现释放读锁，最后执行AQS的doReleaseShared()方法唤醒阻塞的线程。

tryRelease()和tryReleaseShared()的区别：读锁是共享锁，由多个线程持有，所以释放读锁需要通过自旋 + CAS完成。写锁是独占锁，由单个线程持有，所以释放写锁时不需要CAS操作。

## 8.ReentractReadWriteLock的公平锁和非公平锁

### (1)公平锁的实现代码

对公平锁来说，用于判断读线程在抢占锁时是否应该阻塞的readerShouldBlock()方法，以及用于判断写线程在抢占锁时是否应该阻塞的writerShouldBlock()方法，都会通过hasQueuedPredecessors()方法判断当前队列中是否有线程排队。只要队列中有其他线程在排队，写线程和读线程都要排队尾，不能抢占锁。

### (2)非公平锁的实现代码

对非公平锁来说，writerShouldBlock()方法会直接返回false，因为写线程可以去抢非公平锁的情况一定是：没有其他线程持有锁或者是线程自己重入写锁，所以不需要阻塞。而readerShouldBlock()方法会调用一个方法来决定是否阻塞读线程，在一定程度上避免发生写锁无限等待的问题(死锁饥饿问题)。

readerShouldBlock()方法调用的这个方法就是AQS的apparentlyFirstQueuedIsExclusive()方法。如果当前等待队列头结点的后继结点是写锁结点，那么该方法就返回true，表示当前来获取读锁的读线程需要排队。如果当前等待队列头结点的后继结点是读锁结点，那么该方法就返回false，表示当前来获取读锁的读线程可以抢占锁。

由于读线程和读线程是不互斥的，如果当前正在有线程持有读锁，而新来的读线程还非公平地抢读锁，可能导致写线程永远拿不到写锁。

## 9.Condition的说明和源码

### (1)Condition说明

**说明一：Condition与wait/notify的对比**

Condition的功能和wait/notify类似，可以实现等待/通知模式。wait/notify必须要和synchronized一起使用，Condition也必须要和Lock一起使用。Condition避免了wait/notify的生产者通知生产者，消费者通知消费者的问题。

**说明二：Condition的使用**

一般都会将Condition对象作为成员变量。当调用Condition的await()方法后，当前线程会释放锁并挂起等待。当其他线程线程调用Condition的signal()方法通知当前线程(释放锁)后，当前线程才会从Condition的await()方法处返回，并且返回的时候已经获得了锁。

**说明三：两个线程在使用Condition的交互流程**

线程1 -> 获取锁 -> 释放锁 + await()阻塞等待 ->

线程2 -> 获取锁 -> signal()唤醒线程1 + 释放锁 ->

线程1 -> 被唤醒 + 尝试获取锁 -> 释放锁

**说明四：读写锁和独占锁是否支持Condition**

独占锁和读写锁的写锁都支持Condition，但是读写锁的读锁是不支持Condition的。

ReentrantLock支持Condition。

ReentrantReadWriteLock的WriteLock支持Condition。

**说明五：由AQS的内部类ConditionObject实现**

每个Condition对象都有一个Condition队列，这个队列是Condition对象实现等待/通知功能的关键。

**说明六：Condition的应用场景**

LinkedBlockingQueue、ArrayBlockQueue、CyclicBarrier都用到了Condition来实现线程等待。

### (2)创建ConditionObject对象

调用ReentrantLock的newCondition()方法可以创建一个Condition对象，ReentrantLock的newCondition()方法会调用Sync的newCondition()方法，而Sync的newCondition()方法会创建ConditionObject对象。

### (3)ConditionObject的Condition队列

在ConditionObject对象中，会有一个Condition队列，ConditionObject对象维护的Condition队列是一个单向链表。

ConditionObject对象的属性firstWaiter和lastWaiter代表队列的头尾结点。当线程调用await()方法时，该线程就会被封装成Node结点。然后该Node结点就会被作为新增结点加入到Condition队列的尾部。

由于Condition对象拥有Condition队列的头尾结点的引用，所以只需将原来尾结点的nextWaiter指向新增结点，并更新尾结点即可。这个更新过程无须使用CAS保证，因为调用await()方法的线程已经获取锁了。

### (4)ConditionObject的等待方法await()

ConditionObject的await()方法的主要逻辑：通过addConditionWaiter()方法将当前线程添加到Condition队列、通过fullyRelease()方法释放锁、通过LockSupport.park()方法挂起当前线程、被signal()方法唤醒后，通过acquireQueued()方法尝试获取锁。

其实相当于将等待队列的头结点(获取了锁的结点)移动到Condition队列中。但等待队列的头结点不会直接加入Condition队列，而是会把当前线程封装成一个新的Node结点加入到Condition队列尾部。

**注意：** 调用await()方法的线程其实已成功获取锁，该线程对应等待队列的头结点。await()方法会将当前线程封装成结点并加入到Condition队列，然后释放锁，并唤醒等待队列头结点的后继结点对应线程，再挂起当前线程进入等待状态。当该线程被signal()方法唤醒后，便会通过acquireQueued()方法尝试获取锁。所以调用await()方法的线程在阻塞后被唤醒，也有可能获取锁失败继续阻塞。

**Condition.await()原理总结：** 将自己加入Condition队列、释放锁、挂起自己。

### (5)ConditionObject的通知方法signal()

ConditionObject的signal()方法的主要逻辑：首先从Condition队列中取出等待时间最长的结点，也就是first结点、然后将等待时间最长的结点(first结点)转移到AQS的等待队列(CLH队列)中、最后唤醒该first结点对应的线程。

由于该first结点对应的线程在await()方法中加入Condition队列后被阻塞，所以该first结点对应的线程在被唤醒后，会回到await()方法中继续执行，也就是会执行AQS的acquireQueued()方法去尝试获取锁。

调用signal()方法的前提条件是当前线程必须获得了锁，所以signal()方法首先会检查当前线程是否获取了锁，接着才去获取Condition队列的first结点，然后才将first结点移动到等待队列，并唤醒该first结点对应的线程。通过调用AQS的enq()方法，Condition队列的first结点会添加到等待队列。当first结点被移动到等待队列后，再唤醒first结点对应的线程尝试获取锁。

被唤醒的first结点对应的线程，将从await()方法中的while循环退出。因为已经在等待队列中，所以isOnSyncQueue()方法会返回true，从而会调用AQS的acquireQueued()方法来竞争获取锁。

**Condition.signal()原理总结：** 把Condition队列中的头结点，转化为等待队列中的尾结点。

## 10.等待多线程完成的CountDownLatch

### (1)CountDownLatch的简介

CountDownLatch允许一个或多个线程等待其他线程完成操作。CountDownLatch提供了两个核心方法，分别是await()方法和countDown()方法。CountDownLatch.await()方法让调用线程进行阻塞进入等待状态，CountDownLatch.countDown()方法用于对计数器进行递减。

CountDownLatch在构造时需要传入一个正整数作为计数器初始值。线程每调用一次countDown()方法，都会对该计数器减一。当计数器为0时，会唤醒所有执行await()方法时被阻塞的线程。

### (2)CountDownLatch.await()方法的阻塞流程

CountDownLatch是基于AQS中的共享锁来实现的。从CountDownLatch的构造方法可知，CountDownLatch的count就是AQS的state。

调用CountDownLatch的await()方法时，会先调用AQS的acquireSharedInterruptibly()模版方法，然后会调用CountDownLatch的内部类Sync实现的tryAcquireShared()方法。tryAcquireShared()方法会判断state的值是否为0，如果为0，才返回1，否则返回-1。

当调用CountDownLatch内部类Sync的tryAcquireShared()方法获得的返回值是-1时，才会调用AQS的doAcquireSharedInterruptibly()方法，将当前线程封装成Node结点加入等待队列，然后挂起当前线程进行阻塞。

### (3)CountDownLatch.await()方法的阻塞总结

只要state != 0，就会进行如下处理：将当前线程封装成一个Node结点，然后添加到AQS的等待队列中。调用LockSupport.park()方法，挂起当前线程。

### (4)CountDownLatch.coutDown()的唤醒流程

调用CountDownLatch的countDown()方法时，会先调用AQS的releaseShared()模版方法，然后会执行CountDownLatch的内部类Sync实现的tryReleaseShared()方法。

如果tryReleaseShared()方法返回true，则执行AQS的doReleaseShared()方法，通过AQS的doReleaseShared()方法唤醒共享锁模式下的等待队列中的线程。

### (5)CountDownLatch总结

假设有两个线程A和B，分别调用了CountDownLatch的await()方法，此时state所表示的计数器不为0。所以线程A和B会被封装成SHARED类型的结点，并添加到AQS的等待队列中。

当线程C调用CountDownLatch的coutDown()方法后，如果state被递减到0，那么就会调用doReleaseShared()方法唤醒等待队列中的线程。然后被唤醒的线程会继续调用setHeadAndPropagate()方法实现唤醒传递，从而继续在doReleaseShared()方法中唤醒所有在等待队列中的被阻塞的线程。

## 11.控制并发线程数的Semaphore

### (1)Semaphore的作用

Semaphore信号量用来控制同时访问特定资源的线程数量，有两核心方法。

方法一：acquire()方法，获取一个令牌

方法二：release()方法，释放一个令牌

多个线程访问某限制访问流量的资源时，可先调用acquire()获取访问令牌。如果能够正常获得，则表示允许访问。如果令牌不够，则会阻塞当前线程。当某个获得令牌的线程通过release()方法释放一个令牌后，被阻塞在acquire()方法的线程就有机会获得这个释放的令牌。

### (2)Semaphore的原理

Semaphore也是基于AQS中的共享锁来实现的。在创建Semaphore实例时传递的参数permits，其实就是AQS中的state属性。每次调用Semaphore的acquire()方法，都会对state值进行递减。

## 12.同步屏障CyclicBarrier

CyclicBarrier的字面意思就是可循环使用的屏障。CyclicBarrier的主要作用就是让一组线程到达一个屏障时被阻塞，直到最后一个线程到达屏障时屏障才会打开，接着才让所有被屏障拦截的线程一起继续往下执行。线程进入屏障是通过CyclicBarrier的await()方法来实现的。

CyclicBarrier是基于ReentrantLock + Condition来实现的。

## 13.ConcurrentHashMap的原理

### (1)JDK1.8相比于JDK1.7的改进

**改进一：** 取消了segment分段设计，直接使用Node数组来保存数据。采用Node数组元素作为锁的粒度，进一步减少并发冲突的范围和概率。

**改进二：** 引入红黑树设计，红黑树降低了极端情况下查询某个结点数据的时间复杂度，从O(n)降低到了O(logn)，提升了查找性能。

### (2)ConcurrentHashMap的设计思想

设计一：通过对数组元素加锁来降低锁的粒度

设计二：多线程进行并发扩容

设计三：高低位迁移方法

设计四：链表转红黑树及红黑树转链表

设计五：分段锁来实现数据统计

### (3)ConcurrentHashMap的数据结构定义

ConcurrentHashMap采用Node数组来存储数据，数组长度默认为16。Node表示数组中的一个具体的数据结点，并且实现了Map.Entry接口。Node的key和val属性，表示实际存储的key和value。Node的hash属性，表示当前key对应的hash值。Node的next属性，表示如果是链表结构，则指向下一个Node结点。当链表长度大于等于8 \+ Node数组长度大于64时，链表会转为红黑树，红黑树的存储使用TreeNode来实现。

### (4)ConcurrentHashMap的put操作流程

首先通过key的hashCode的高低16位的位与操作来计算key的hash值，让32位的hashCode都参与运算以降低数组大小小于32时哈希冲突的概率。

然后判断Node数组是否为空或者Node数组的长度是否为0。如果为空或者为0，则调用initTable()方法进行初始化。如果不为空，则通过hash & (n - 1)计算当前key在Node数组中的下标位置。并通过tabAt()方法获取该位置的值f，然后判断该位置的值f是否为空。

如果该位置的值f为空，则把当前的key和value封装成Node对象。然后尝试通过casTabAt()方法使用CAS设置该位置的值f为封装好的Node对象。如果CAS设置成功，则退出for循环，否则继续进行下一次for循环。

如果该位置的值f不为空，则判断Node数组是否正处于扩容中。如果是，那么当前线程就调用helpTransfer()方法进行并发扩容。如果不是，那么说明当前的key在Node数组中出现了Hash冲突。于是通过synchronized关键字，对该位置的值f进行Hash冲突处理。其实JUC还可以继续优化，比如先用CAS尝试修改哈希冲突下的链表或红黑树。如果CAS修改失败，那么再通过使用synchronized对该数组元素加锁来进行处理。

最后，会调用addCount()方法统计Node数组中的元素个数。

### (5)ConcurrentHashMap和HashMap的put操作

都是通过key的hashCode的高低16位的异或运算，来降低Hash冲突概率。都是通过Hash值与数组大小-1的位与运算(取模)，来定位key在数组的位置。但ConcurrentHashMap使用了自旋 + CAS + synchronized来处理put操作，从而保证了多个线程对数组里某个key进行赋值时的效率 + 并发安全性。

**为什么ConcurrentHashMap是并发安全的：** 首先在初始化Node数组时，会通过自旋 + CAS去设置sizeCtl的值来获得锁。然后在put()操作时，也会通过自旋 + CAS去设置数组某个位置的值。当出现Hash冲突时，则使用synchronized关键字来修改数组某个位置的值。

### (6)ConcurrentHashMap对Hash冲突的处理

首先使用synchronized对当前位置的Node对象f进行加锁。由于这种锁控制在数组的单个数据元素上，所以长度为16的数组理论上就可以支持16个线程并发写入数据。

然后判断当前位置的Node对象f是链表还是红黑树。如果是链表，那么就把当前的key/value封装成Node对象插入到链表的尾部。如果是红黑树，那么就调用TreeBin的putTreeVal()方法往红黑树插入结点。

最后判断链表的长度是否大于等于8，如果链表的长度大于等于8，再调用treeifyBin()方法决定是扩容数组还是将链表转化为红黑树。

### (7)ConcurrentHashMap中的扩容设计

扩容就是创建一个2倍原大小的数组，然后把原数组的数据迁移到新数组中。但多线程环境下的扩容，需要考虑其他线程会同时往数组添加元素的情况。如果简单地对扩容过程增加一把同步锁，保证扩容过程不存在其他线程操作，那么就会对性能的损耗特别大，特别是数据量比较大时，阻塞的线程会很多。

首先使用CAS来实现计算每个线程的迁移区间。然后使用synchronized把锁粒度控制到每个数组元素上。如果数组有16个元素就有16把锁，如果数组有32个元素就有32把锁。接着如果线程A在进行数组扩容时，线程B要修改数组的某个元素f。那么就让修改元素的线程加入迁移，从而实现多线程并发扩容来提高效率。等数组扩容完成后，线程B才继续去修改元素f。最后通过高低位迁移逻辑计算出高位链和低位链，大大减少了数据迁移次数。

### (8)多线程并发扩容的原理

当存在多个线程并发扩容及数据迁移时，默认会给每个线程分配一个区间。这个区间的默认长度是16，每个线程会负责自己区间内的数据迁移工作。如果只有两个线程对长度为64的数组迁移数据，则每个线程要做2次迁移，迁移过程会依赖transferIndex来更新每个线程的迁移区间。

ConcurrentHashMap的transfer()方法用于处理数组扩容时的流程细节，该方法主要分为五部分：

第一部分：创建扩容后的数组

第二部分：计算当前线程的数据迁移区间

第三部分：更新扩容标记advance

第四部分：开始数据迁移和扩容

第五部分：完成迁移后的判断

### (9)ConcurrentHashMap的分段锁统计元素数据

**ConcurrentHashMap维护数组元素个数思路：** 当调用完put()方法后，ConcurrentHashMap必须增加当前元素的个数，以方便在size()方法中获得存储的元素个数。在常规的集合中，只需要一个全局int类型的字段保存元素个数即可。每次添加一个元素，就对这个size变量 + 1。在ConcurrentHashMap中，需要保证对该变量修改的并发安全。如果使用同步锁synchronized，那么性能开销比较大，不合适。所以ConcurrentHashMap使用了自旋 + 分段锁来维护元素个数。

**ConcurrentHashMap维护数组元素个数流程：** ConcurrentHashMap采用了两种方式来保存元素的个数。当线程竞争不激烈时，直接使用baseCount + 1来增加元素个数。当线程竞争比较激烈时，构建一个CounterCell数组，默认长度为2。然后随机选择一个CounterCell，针对该CounterCell中的value进行保存。

### (10)ConcurrentHashMap的查询操作是否涉及锁

**put操作会加锁：** 首先尝试通过CAS设置Node数组对应位置的Node元素。如果该位置的Node元素非空，或者CAS设置失败，则说明发生了哈希冲突。此时就会使用synchronized关键字对该数组元素加锁来处理链表或者红黑树。其实JUC还可以继续优化，先用CAS尝试修改哈希冲突下的链表或红黑树。如果CAS修改失败，再通过使用synchronized对该数组元素加锁来处理。

**size操作不会加锁：** size()方法在计算总的元素个数时并没有加锁，所以size()方法返回的元素个数不一定代表此时此刻数组元素的总数量。

**get操作也不会加锁：** get()方法也使用了CAS操作，通过Unsafe类让数组中的元素具有可见性。保证线程根据tabAt()方法获取数组的某个位置的元素时，能获取最新的值。所以get不加锁，但通过volatile读数组，可以保证读到数组元素的最新值。虽然table变量使用了volatile，但这只保证了table引用对所有线程的可见性，还不能保证table数组中的元素的修改对于所有线程是可见的。因此才通过Unsafe类的getObjectVolatile()来保证table数组中元素的可见性。

## 14.并发安全的数组列表CopyOnWriteArrayList

### (1)CopyOnWriteArrayList的初始化

并发安全的HashMap是ConcurrentHashMap

并发安全的ArrayList是CopyOnWriteArrayList

并发安全的LinkedList是ConcurrentLinkedQueue

从CopyOnWriteArrayList的构造方法可知，CopyOnWriteArrayList基于Object对象数组实现。这个Object对象数组array会使用volatile修饰，保证了多线程下的可见性。只要有一个线程修改了数组array，其他线程可以马上读取到最新值。

### (2)基于锁 + 写时复制机制实现的增删改操作

**使用独占锁解决对数组的写写并发问题：** 每个CopyOnWriteArrayList都有一个Object数组 \+ 一个ReentrantLock锁。在对Object数组进行增删改时，都要先获取锁，保证只有一个线程增删改。从而确保多线程增删改CopyOnWriteArrayList的Object数组是并发安全的。注意：获取锁的动作需要在执行getArray()方法前执行。但因为获取独占锁，所以导致CopyOnWriteArrayList的写并发并性能不太好。而ConcurrentHashMap由于通过CAS设置 \+ 分段加锁，所以写并发性能很高。

**使用写时复制机制解决对数组的读写并发问题：** CopyOnWrite就是写时复制。写数据时不直接在当前数组里写，而是先把当前数组的数据复制到新数组里。然后再在新数组里写数据，写完数据后再将新数组赋值给array变量。这样原数组由于没有了array变量的引用，很快就会被JVM回收掉。其中会使用System.arraycopy()方法和Arrays.copyOf()方法来复制数据到新数组，从Arrays.copyOf(elements, len + 1)可知，新数组的大小比原数组大小多1。所以CopyOnWriteArrayList不需要进行数组扩容，这与ArrayList不一样。ArrayList会先初始化一个固定大小的数组，然后数组大小达到阈值时会扩容。

**总结：** 为了解决CopyOnWriteArrayList的数组写写并发问题，使用了锁。为了解决CopyOnWriteArrayList的数组读写并发问题，使用了写时复制。所以CopyOnWriteArrayList可以保证多线程对数组写写 + 读写的并发安全。

### (3)使用写时复制的原因是读操作不加锁 + 不使用Unsafe读取数组元素

CopyOnWriteArrayList的增删改采用写时复制的原因在于get操作不需加锁。get操作就是先获取array数组，然后再通过index定位返回对应位置的元素。

由于在写数据的时候，首先更新的是复制了原数组数据的新数组。所以同一时间大量的线程读取数组数据时，都会读到原数组的数据，因此读写之间不会出现并发冲突的问题。而且在写数据的时候，在更新完新数组之后，才会更新volatile修饰的数组变量。所以读操作只需要直接对volatile修饰的数组变量进行读取，就能获取最新的数组值。

如果不使用写时复制机制，那么即便有写线程先更新了array引用的数组中的元素，后续的读线程也只是具有对使用volatile修饰的array引用的可见性，而不会具有对array引用的数组中的元素的可见性。所以此时只要array引用没有发生改变，读线程还是会读到旧的元素，除非使用Unsafe.getObjectVolatile()方法来获取array引用的数组的元素。

### (4)对数组进行迭代时采用了副本快照机制

CopyOnWriteArrayList的Iterator迭代器里有一个快照数组snapshot，该数组指向的就是创建迭代器时CopyOnWriteArrayList的当前数组array。所以使用CopyOnWriteArrayList的迭代器进行迭代时，会遍历快照数组。此时如果有其他线程更新了数组array，也不会影响迭代的过程。

### (5)核心思想是通过最终一致性提升读并发

CopyOnWriteArrayList的核心思想是通过弱一致性来提升读写并发的能力。CopyOnWriteArrayList基于写时复制机制存在的最大问题是最终一致性。

多个线程并发读写数组，写线程已将新数组修改好，但还没设置给array。此时其他读线程读到的(get或者迭代)都是数组array的数据，于是在同一时刻，读线程和写线程看到的数据是不一致的。这就是写时复制机制存在的问题：最终一致性或弱一致性。

### (6)写时复制的总结

**优点：** 读读不互斥，读写不互斥，写写互斥。同一时间只有一个线程可以写，写的同时允许其他线程来读。

**缺点：** 空间换时间，写的时候内存里会出现一模一样的副本，对内存消耗大。通过数组副本可以保证大量的读不需要和写互斥。如果数组很大，可能要考虑内存占用会是数组大小的几倍。此外使用数组副本来统计数据，会存在统计数据不一致的问题。

**使用场景：** 适用于读多写少的场景，这样大量的读操作不会被写操作影响，而且不要求统计数据具有实时性。

## 15.并发安全的链表队列ConcurrentLinkedQueue

### (1)ConcurrentLinkedQueue的介绍

ConcurrentLinkedQueue是一种并发安全且非阻塞的链表队列(无界队列)。ConcurrentLinkedQueue采用CAS机制来保证多线程操作队列时的并发安全。

链表队列会采用先进先出的规则来对结点进行排序。每次往链表队列添加元素时，都会添加到队列的尾部。每次需要获取元素时，都会直接返回队列头部的元素。

### (2)ConcurrentLinkedQueue的构造方法

ConcurrentLinkedQueue是基于链表实现的，链表结点为其内部类Node。ConcurrentLinkedQueue的构造方法会初始化链表的头结点和尾结点为同一个值为null的Node对象。

Node结点通过next指针指向下一个Node结点，从而组成一个单向链表。而ConcurrentLinkedQueue的head和tail两个指针指向了链表的头和尾结点。

### (3)ConcurrentLinkedQueue的offer()方法

其中关键的代码就是"p.casNext(null, newNode))"，就是把p的next指针由原来的指向空设置为指向新的结点，并且通过CAS确保同一时间只有一个线程可以成功执行这个操作。注意：更新tail指针并不是实时更新的，而是隔一个结点再更新。这样可以减少CAS指令的执行次数，从而降低CAS操作带来的性能影响。

### (4)ConcurrentLinkedQueue的poll()方法

poll()方法会将链表队列的头结点出队。注意：更新head指针时也不是实时更新的，而是隔一个结点再更新。这样可以减少CAS指令的执行次数，从而降低CAS操作带来的性能影响。

### (5)ConcurrentLinkedQueue的size()方法

size()方法主要用来返回链表队列的大小，查看链表队列有多少个元素。size()方法不会加锁，会直接从头节点开始遍历链表队列中的每个结点。

这些并发安全的集合：ConcurrentHashMap、CopyOnWriteArrayList和ConcurrentLinkedQueue，为了优化多线程下的并发性能，会牺牲掉统计数据的一致性。为了保证多线程写的高并发性能，会大量采用CAS进行无锁化操作。同时会让很多读操作比如常见的size()操作，不使用锁。因此使用这些并发安全的集合时，要考虑并发下的统计数据的不一致问题。

## 16.JUC的各种阻塞队列介绍

### (1)基于数组的阻塞队列ArrayBlockingQueue

ArrayBlockingQueue是一个基于数组实现的阻塞队列。其构造方法可以指定：数组的长度、公平还是非公平、数组的初始集合。ArrayBlockingQueue会通过ReentrantLock来解决线程竞争的问题，以及采用Condition来解决线程的唤醒与阻塞的问题。

### (2)基于链表的阻塞队列LinkedBlockingQueue

LinkedBlockingQueue是一个基于链表实现的阻塞队列，它可以不指定阻塞队列的长度，它的默认长度是Integer.MAX_VALUE。由于这个默认长度非常大，一般也称LinkedBlockingQueue为无界队列。

### (3)优先级阻塞队列PriorityBlockingQueue

PriorityBlockingQueue是一个支持自定义元素优先级的无界阻塞队列。默认情况下添加的元素采用自然顺序升序排列，当然可以通过实现元素的compareTo()方法自定义优先级规则。

PriorityBlockingQueue是基于数组实现的，这个数组会自动进行动态扩容。在应用方面，消息中间件可以基于优先级阻塞队列来实现。

### (4)延迟阻塞队列DelayQueue

DelayQueue是一个支持延迟获取元素的无界阻塞队列，它是基于优先级队列PriorityQueue实现的。

往DelayQueue队列插入元素时，可以按照自定义的delay时间进行排序。也就是队列中的元素顺序是按照到期时间排序的，只有delay时间小于或等于0的元素才能够被取出。

### (5)无存储结构的阻塞队列SynchronousQueue

SynchronousQueue的内部没有容器来存储数据，因此当生产者往其添加一个元素而没有消费者去获取元素时，生产者会阻塞。当消费者往其获取一个元素而没有生产者去添加元素时，消费者也会阻塞。

SynchronousQueue的本质是借助了无容量存储的特点，来实现生产者线程和消费者线程的即时通信，所以它特别适合在两个线程之间及时传递数据。

线程池是基于阻塞队列来实现生产者/消费者模型的。当向线程池提交任务时，首先会把任务放入阻塞队列中，然后线程池中会有对应的工作线程专门处理阻塞队列中的任务。

Executors.newCachedThreadPool()就是基于SynchronousQueue来实现的，它会返回一个可以缓存的线程池。如果这个线程池大小超过处理当前任务所需的数量，会灵活回收空闲线程。当任务数量增加时，这个线程池会不断创建新的工作线程来处理这些任务。

## 17.LinkedBlockingQueue的具体实现原理

### (1)阻塞队列的设计分析

阻塞队列的特性为：如果队列为空，消费者线程会被阻塞。如果队列满了，生产者线程会被阻塞。为了实现这个特性：如何让线程在满足某个特定条件的情况下实现阻塞和唤醒？阻塞队列中的数据应该用什么样的容器来存储？线程的阻塞和唤醒，可以使用wait/notify或者Condition。阻塞队列中数据的存储，可以使用数组或者链表。

### (2)有界队列LinkedBlockingQueue

**并发安全的无界****队列：** 比如ConcurrentLinkedQueue，是没有边界没有大小限制的。它就是一个单向链表，可以无限制的往里面去存放数据。如果不停地往无界队列里添加数据，那么可能会导致内存溢出。

**并发安全的有界队列：** 比如LinkedBlockingQueue，是有边界的有大小限制的。它也是一个单向链表，如果超过了限制，往队列里添加数据就会被阻塞。因此可以限制内存队列的大小，避免内存队列无限增长，最后撑爆内存。

### (3)LinkedBlockingQueue的put()方法

put()方法是阻塞添加元素的方法，当队列满时，阻塞添加元素的线程。

首先把添加的元素封装成一个Node对象，该对象表示链表中的一个结点。然后使用ReentrantLock.lockInterruptibly()方法来获取一个可被中断的锁，加锁的目的是保证数据添加到队列过程中的安全性 \+ 避免队列长度超阈值。接着调用enqueue()方法把封装的Node对象存储到链表尾部，然后通过AtomicInteger来递增当前阻塞队列中的元素个数。最后根据AtomicInteger类型的变量判断队列元素是否已超阈值。

注意：这里用到了一个很重要的属性notFull。notFull是一个Condition对象，用来阻塞和唤醒生产者线程。如果队列元素个数等于最大容量，就调用notFull.await()阻塞生产者线程。如果队列元素个数小于最大容量，则调用notFull.signal()唤醒生产者线程。

### (4)LinkedBlockingQueue的take()方法

take()方法是阻塞获取元素的方法，当队列为空时，阻塞获取元素的线程。

首先使用ReentrantLock.lockInterruptibly()方法来获取一个可被中断的锁。然后判断元素个数是否为0，若是则通过notEmpty.await()阻塞消费者线程。否则接着调用dequeue()方法从链表头部获取一个元素，并通过AtomicInteger来递减当前阻塞队列中的元素个数。最后判断阻塞队列中的元素个数是否大于1，如果是，则调用notEmpty.signal()唤醒被阻塞的消费者线程。

### (5)LinkedBlockingQueue使用两把锁拆分锁功能

两把独占锁可以提升并发性能，因为出队和入队用的是不同的锁。这样在并发出队和入队的时候，出队和入队就可以同时执行，不会锁冲突。

这也是锁优化的一种思想，通过将一把锁按不同的功能进行拆分，使用不同的锁控制不同功能下的并发冲突，从而提升性能。

**(6)对比LinkedBlockingQueue链表队列和ArrayBlockingQueue数组队列**

ArrayBlockingQueue的整体实现原理与LinkedBlockingQueue的整体实现原理是一样的。但LinkedBlockingQueue是基于链表实现的有界阻塞队列，ArrayBlockingQueue是基于数组实现的有界阻塞队列。

LinkedBlockingQueue需要使用两把独占锁，分别锁出队和入队的场景。ArrayBlockingQueue只使用一把锁，锁整个数组，所以其入队和出队不能同时进行。

ArrayBlockingQueue执行size()方法获取元素个数时会直接加独占锁，ArrayBlockingQueue和LinkedBlockingQueue执行迭代方法时都会锁数据。

## 18.基于两个队列实现的集群同步机制

### (1)服务注册中心集群需要实现的功能

服务实例向任何一个服务注册中心实例发送注册、下线、心跳的请求，该服务注册中心实例都需要将这些信息同步到其他的服务注册中心实例上，从而确保所有服务注册中心实例的内存注册表的数据是一致的。

### (2)基于两个队列实现的集群同步机制

某服务注册中心实例接收到服务实例A的请求时，首先会把服务实例A的服务请求信息存储到本地的内存注册表里，也就是把服务实例A的服务请求信息写到第一个内存队列中，之后该服务注册中心实例对服务实例A的请求处理就可以结束并返回。

接着该服务注册中心实例会有一个后台线程消费第一个内存队列里的数据，把消费到的第一个内存队列的数据batch打包然后写到第二个内存队列里。

最后该服务注册中心实例还有一个后台线程消费第二个内存队列里的数据，把消费到的第二个内存队列的数据同步到其他服务注册中心实例中。

### (3)使用ConcurrentLinkedQueue实现第一个队列

首先有两种队列：一是无界队列ConcurrentLinkedQueue，基于CAS实现，并发性能很高。二是有界队列LinkedBlockingQueue，基于两把锁实现，并发性能一般。

LinkedBlockingQueue默认的队列长度是MAX_VALUE，所以可以看成是无界队列。但是也可以指定正常大小的队列长度，从而实现入队的阻塞，避免耗尽内存。

当服务注册中心实例接收到各种请求时，会先将请求信息放入第一个队列。所以第一个队列会存在高并发写的情况，因此LinkedBlockingQueue不合适。因为LinkedBlockingQueue属于阻塞队列，如果LinkedBlockingQueue满了，那么服务注册中心实例中的，处理服务请求的线程，就会被阻塞住。而且LinkedBlockingQueue的并发性能也不是太高，要获取独占锁才能写，所以最好还是使用无界队列ConcurrentLinkedQueue来实现第一个队列。

### (4)使用LinkedBlockingQueue实现第二个队列

消费第一个内存队列的数据时，可以按时间来进行batch打包，比如每隔500ms才将消费到的所有数据打包成一个batch消息。接着再将这个batch信息放入到第二个内存队列中，这样消费第二个队列的数据时，只需同步batch信息到集群其他实例即可。可见对第二个队列进行的入队和出队操作是由少数的后台线程来执行的，因此可以使用有界队列LinkedBlockingQueue来实现第二个内存队列。

## 19.锁优化总结

### (1)标志位修改等可见性场景优先使用volatile

分布式系统、中间件系统都需要开启大量的线程进行处理。多线程访问共享变量时，首先需要明确是并发写还是并发读。如果仅仅只有一个线程会来写一个共享变量，比如标志位。另外多个线程会来读取这个标志位的值，那么此时优先使用volatile。

所以锁优化的原则是：能不用锁就尽量不用锁。因为可能会导致锁争用和锁冲突，从而导致系统吞吐量、性能大幅度降低。比如可以通过volatile标志位实现服务优雅停机。

### (2)数值递增场景优先使用Atomic原子类

多线程并发访问共享变量时，首先判断变量是否只需保证可见性即可，如果是则使用volatile优化。然后判断是否要保证原子性，如果是则判断是简单数值累加还是变更操作。如果只需要简单进行数值累加，那么则建议使用Atomic原子类，否则才使用synchronized或者ReentrantLock这种重量级锁。Atomic原子类基于CAS机制实现了无锁化编程，并发性比synchronized好。

### (3)共享变量仅对当前线程可见的场景优先使用ThreadLocal

在多线程环境中，当多个线程同时访问某个共享变量时，如果希望对共享变量的操作仅对当前线程可见，那么可以使用ThreadLocal。ThreadLocal会为每个线程提供独立的存储空间来存储共享变量的副本，每个线程只会对共享变量的副本进行操作，且该操作对其他线程不可见。volatile、Atomic、ThreadLocal是锁优化的三大利器，应当优先考虑。如果不能使用它们，再考虑synchronized和ReentrantLock等这些重量级锁。

### (4)读多写少需要加锁的场景优先使用读写锁

如果volatile、Atomic、ThreadLocal都不适用，这时多线程并发访问一块共享数据就需要加锁了。但是此时会优先考虑使用读写锁，而不是使用synchronized重量级锁。比如在读多写少的场景下，可以进行读写锁分离。读锁 -> 大量的线程可以并发的读，写锁 -> 有线程写数据时其他线程不能同时来写也不能同时来读。

### (5)尽可能减少线程对锁占用的时间

无论是synchronized锁还是读写锁，都要尽量保证加锁的时间比较短，不能在加锁后执行耗时的磁盘文件读写、网络IO读写等操作长时间占有锁。一般会在操作内存中的数据时加锁，而不会在操作数据库中的数据时加锁。否则可能会导致长时间占用锁，导致线程并发的性能和吞吐量大幅度下降。比如，可以考虑通过分段锁来减少锁占用时间。

### (6)尽可能减少线程对数据加锁的粒度

如果有一份共享数据，里面包含了多个子数据。可以对完整的这份数据加锁，线程只要访问这份数据，就会竞争锁。也可以只对数据里的部分子数据进行加锁，从而降低加锁的粒度，减少竞争。比如库存扣减时可以仅仅对部分库存数据加锁，而不是对完整的库存数据加锁。

### (7)尽可能按不同功能对锁进行分离

如果可以按照使用功能的不同，将一把锁拆分为多把锁。那么在使用不同的功能时，就可以使用不同的锁了，从而减少线程竞争同一把锁时的冲突。

比如LinkedBlockingQueue有界阻塞队列，就使用了两把锁。队列头部使用一把take锁，队列尾部使用一把put锁。执行put()方法时先获取put锁，然后再从队列尾部入队元素。执行take()方法时先获取take锁，然后再从队列头部出队元素。这样同一时刻对阻塞队列的入队和出队操作，就不会产生锁冲突。

### (8)尽量减少高并发下线程对锁的竞争(多级缓存)

**使用读写锁：** 读写锁主要用来解决读请求和读请求不会冲突可以并行执行，但写请求和读请求还是会冲突，写请求和写请求也是会冲突的。

**按不同功能进行锁分离：** 比如按使用功能不同，将一把锁拆分为多把锁。

**减少锁占用的时间：** 比如分布式存储系统中的edits log分段锁。

**数据分段加锁：** 比如分布式锁的分段库存扣减。

**减少线程对锁的竞争频率：** 比如通过多级缓存来降低锁竞争的频率。

### (9)服务注册表通过多级缓存来降低锁竞争频率

**读写锁依然存在并发读写冲突：** 虽然服务注册中心已经使用了读写锁来处理读写服务注册表，但是当需要对服务注册表进行写操作时，可能会出现大量的读操作被阻塞。现在假设每分钟会出现并发读写冲突的次数是10次。

**多级缓存的运行逻辑：** 因此可以使用多级缓存机制来优化服务注册表的读写并发冲突问题。服务注册表的多级缓存是：一级缓存(只读缓存)，二级缓存(读写缓存)。所有的读请求都先从一级缓存(只读缓存)里读取数据。如果一级缓存(只读缓存)里没找到，则从二级缓存(读写缓存)里查找。如果二级缓存(读写缓存)也没有找到，则再从服务注册表中进行加载。

**多级缓存的过期策略：** 一级缓存(读写缓存)中的数据的过期策略是：通过一个定时任务，每隔30s和二级缓存的数据保持同步(一致)。二级缓存(读写缓存)中的数据的过期策略是：当有服务实例发生注册、下线时，就会主动过期(更新)其对应的二级缓存。此外构建二级缓存时会指定默认的过期时间为180秒，180秒后自动过期。

**多级缓存如何降低并发读写频率：** 一级缓存使用ConcurrentHashMap实现，二级缓存使用Guava Cache实现。一级缓存主要用于降低每分钟的写频率，二级缓存主要用于冷热数据分离。当服务注册表的某个key对应的数据更新时，二级缓存的数据会立即更新，30秒后一级缓存的数据也一定会更新。当服务注册表的某个key数据没有更新时，二级缓存的数据180秒后就会过期，过期的30秒后一级缓存的数据变为null。后续访问一级缓存时，再从服务注册表中获取对应的数据，写入二级缓存。通过这两级缓存，就可以大大降低每分钟并发读写缓存注册表的冲突次数，比如一级缓存就可以将每分钟并发读写冲突的次数从10次降为2次，因为一级缓存的数据最多每30秒更新一次。而二级缓存则实现冷数据180秒没访问则不缓存，减少需要缓存的热数据数量。

**多级缓存的本质：** 一级缓存是只读缓存，二级缓存是读写缓存。在一级缓存(只读缓存)中存在很少的并发读写情况，每分钟两次。在二级缓存(读写缓存)中会进行冷热数据分离，冷数据不缓存。服务注册表的数据更新之后，最多30秒就会更新到一级缓存，多级缓存就是牺牲读数据和写数据的实时一致性来降低读写竞争的频率。

### (10)避免死锁的常见方式

避免一个线程同时获得多个锁、避免一个线程在锁内同时占用多个资源，尽量保证每个锁只占用一个资源、尝试使用定时锁，使用Lock.tryLock(timeout)来替代使用内部锁、对于数据库锁，加锁和解锁必须要在同一个数据库连接里。

## 20.线程池介绍

### (1)线程池的优势

合理使用线程池，可以带来很多好处：减少频繁创建和销毁线程的性能开销、重复利用线程，避免对每个任务都创建线程，可以提高响应速度、合理设置线程池的大小，可以避免因为线程池过大影响性能。

### (2)JUC提供的线程池

可以通过如下两种方式来创建线程池：ThreadPoolExecutor线程池的具体实现类、Executors的工厂方法。

Executors中常用的线程池分4种：Fixed线程池里有固定数量的线程、Single线程池里只有一个线程、Cached线程池里的线程数量不固定，但线程空闲的时候会被释放、Scheduled线程池里有固定数量的线程，可以延期执行和周期执行。

### (3)ThreadPoolExecutor构造方法的参数

参数一：核心线程数corePoolSize

参数二：最大线程数maximumPoolSize

参数三：线程存活时间keepAliveTime

参数四：线程存活时间的单位TimeUnit unit

参数五：存放待处理任务的阻塞队列workQueue

参数六：线程工厂threadFactory

参数七：拒绝策略handler

## 21.如何设计一个线程池

### (1)如何让线程可以重复使用

对于线程来说，本身的调度和执行并不由开发者控制，而且线程是当Thread中的run()方法结束后自动销毁完成回收的，所以应该如何让线程可重复使用？

可以在run()方法中增加一个while(true)循环，只要run()方法一直运行，那么线程就不会被回收。虽然while(true)可以让线程不被销毁，但是线程一直运行会占用CPU资源。

我们希望线程池中线程的运行机制是：有任务的时候执行任务，没有任务的时候不需要做无效的运转。所以可以让线程在没有任务的时候阻塞，这样就不会占用CPU资源了。

因此我们对于线程池中的线程复用的要求是：如果有任务时，线程池中的线程会处理这个任务。如果没有任务，就让线程池中的线程进行阻塞。

### (2)需要构建生产者消费者模型

为了构建生产者消费者模型，可以使用阻塞队列。通过线程池的execute(task)方法提交任务时，任务会被放入阻塞队列。线程池的线程在循环执行时，会不断从阻塞队列中获取任务来执行。所以当阻塞队列中没有任务时，线程池的线程就会被阻塞住。

注意：ConcurrentLinkedQueue是无界队列，LinkedBlockingQueue / ArrayBlockingQueue是有界队列，LinkedBlockingQueue的阻塞效果是队列满放数据和队列空取数据都会阻塞。

### (3)需要考虑拒绝策略

如果生产者的请求非常多，阻塞队列可能满了。此时要么提高消费者的消费能力，要么限流生产者降低生产者的生产频率。对应于线程池就是，要么增加线程数量，要么拒绝处理满了之后的任务。

所以当阻塞队列满了之后，一般会先考虑扩容，也就是增加线程数量。如果扩容之后，生产者的请求量依然很大，那只能再采取拒绝策略来处理。

### (4)需要回收非核心线程

当引入线程扩容机制解决请求任务过多的问题后，生产者的请求量开始减少。此时线程池中就不需要那么多线程来处理任务了，新增的线程最好进行回收。

线程的回收就是让线程跳出while循环，当run()方法执行完毕后会自动销毁。所以可以让线程池的线程从阻塞队列中获取任务时，如果等待一段时间后还没获取到任务，说明当前线程池处于空闲状态。这也就意味着这个线程也没有必要继续等待了，于是直接退出即可。

## 22.ThreadPoolExecutor线程池的执行流程

### (1)执行流程总结

当调用execute(Runnable command)方法往线程池提交一个任务后，线程池首先会判断的核心线程是否已经初始化。

如果核心线程还没有初始化，则创建核心线程并启动该线程，该线程会从阻塞队列workQueue中获取任务并执行。然后再将command任务添加到阻塞队列workQueue中。

如果阻塞队列workQueue满了，则尝试创建非核心线程并启动。这些非核心线程也会从阻塞队列workQueue中获取任务并执行。

如果线程池中总的线程数达到阈值且阻塞队列已经满了，则执行拒绝策略。

### (2)线程池的execute()方法

向线程池提交一个任务是通过execute()方法的三个步骤来完成的。

**步骤一：** 首先根据ctl当前的值来判断当前线程数量是否小于核心线程数量，主要用来解决线程池中核心线程未初始化的问题。如果是，则调用addWorker()方法创建一个核心线程并启动，同时把当前任务command传递进新创建的核心线程直接执行。如果否，则说明核心线程已经初始化了。

**步骤二：** 当前线程数量大于等于核心线程数量，核心线程已初始化，那么就把任务command添加到阻塞队列workQueue中。

**步骤三：** 如果向阻塞队列添加任务失败，说明阻塞队列workQueue已满，那么就调用addWorker()方法来创建一个非核心线程。如果通过addWorker()方法创建一个非核心线程也失败了，则说明当前线程池中的线程总数已达到最大线程数量，此时需要调用reject()方法执行拒绝策略。

**第一种情况：** 如果线程池的线程数量 < corePoolSize，就创建一个新的线程并执行任务。刚开始时线程池里的线程数量一定是小于corePoolSize指定的数量，此时每提交一个任务就会创建一个新的线程放到线程池里去。

**第二种情况：** 如果线程池的线程数量 >= corePoolSize，就不会创建新的线程和执行任务，此时唯一做的事情就是通过offer()方法把任务提交到阻塞队列里进行排队。LinkedBlockingQueue的offer()是非阻塞的，而put()和take()则是阻塞的。队列满了offer()不会阻塞等待其他线程take()一个元素，而是直接返回false。但LinkedBlockingQueue默认下是近乎无界的，此时offer()只会返回true。

**第三种情况：** 如果线程池的线程数量 >= corePoolSize \+ 阻塞队列已满即尝试入队失败了，此时就会再次尝试根据最大线程数来创建新的非核心线程。如果创建非核心线程失败最大线程数也满了，就会执行拒绝策略降级处理。超过corePoolSize数量的线程，在keepAliveTime时间范围内空闲会被回收。

### (3)线程池的拒绝策略

在执行线程池的execute()方法向线程池提交一个任务时，如果阻塞队列和工作线程都满了，那么该任务只能通过拒绝策略来降级处理。ThreadPoolExecutor提供了4种拒绝策略：

AbortPolicy策略：这是ThreadPoolExecutor默认使用的拒绝策略，这种策略就是简单抛出一个RejectedExecutionHandler异常。这种策略适合用在一些关键业务上，如果这些业务不能承载更大的并发量，那么可以通过抛出的异常及时发现问题并做出相关处理。

CallerRunsPolicy策略：只要线程池没有被关闭，就由提交任务的线程执行任务的run()方法来执行，这种策略相当于保证了所有的任务都必须执行完成。

DiscardPolicy策略：直接把任务丢弃，不做任何处理，这种策略使得系统无法发现具体的问题，建议用在不重要的业务上。

DiscardOldestPolicy策略：如果线程池没有调用shutdown()方法，则通过workQueue.poll()把阻塞队列头部也就是等待最久的任务丢弃，然后把当前任务通过execute()方法提交到阻塞队列中。

## 23.如何合理设置线程池参数 + 定制线程池

### (1)线程池的核心参数

构建线程池时的核心参数其实就是线程数量和队列类型及长度：corePoolSize、MaximumPoolSize、workQueue类型、workQueue长度。

如果最大线程数设置过大，可能会创建大量线程导致不必要的上下文切换。如果最大线程数设置过小，可能会频繁触发线程池的拒绝策略影响运行。

如果阻塞队列为无界队列，会导致线程池的非核心线程无法被创建，从而导致最大线程数量的设置是失效的，造成大量任务堆积在阻塞队列中。如果这些任务涉及上下游请求，那么就会造成大量请求超时失败。

### (2)如何设置线程池的大小

要看当前线程池中执行的任务是属于IO密集型还是CPU密集型。

**IO密集型：** 就是线程需要频繁和磁盘或者远程网络通信的场景，这种场景中磁盘的耗时和网络通信的耗时较大。这意味着线程处于阻塞期间，不会占用CPU资源，所以线程数量超过CPU核心数并不会造成问题。

**CPU密集型：** 就是对CPU的利用率较高的场景，比如循环、递归、逻辑运算等。这种场景下线程数量设置越少，就越能减少CPU的上下文频繁切换。

如果N表示CPU的核心数量，那么：对于CPU密集型，线程池大小可以设置为N + 1。对于IO密集型，线程池大小可以设置为2N + 1。

### (3)如何动态设置线程池参数

线程池的setMaximumPoolSize()方法可以动态设置最大线程数量、线程池的setCorePoolSize()方法可以动态设置核心线程数量。线程池没有动态设置队列大小的方法，但可以继承LinkedBlockingQueue实现一个队列，提供方法修改其大小。然后根据该队列去创建线程池，这样就能实现动态修改阻塞队列大小了。

### (4)定制线程池的注意事项

当线程池的线程数少于corePoolSize，会自动创建核心线程。这是在执行execute()方法提交任务时，由addWorker()方法创建的。线程创建后，会通过阻塞队列的take()方法阻塞式地获取任务，所以这些线程(也就是核心线程)是不会自动退出的。

当线程池的线程数达到corePoolSize后，execute()提交的任务会直接入队。如果阻塞队列是有界队列且队列满了，入队失败，就尝试创建非核心线程。但是要注意此时线程池里的线程数量最多不能超过maximumPoolSize，而且非核心线程在一定时间内获取不到任务，就会自动退出释放线程。

当阻塞队列满了+线程数达到maximumPoolSize，就执行拒绝策略来降级。拒绝策略有4种：抛出异常、提交线程自己执行、丢弃任务、丢弃头部任务。

## 24.ThreadLocal的设计原理

### (1)早期的设计

首先每个ThreadLocal都创建一个Map，然后用线程作为Map的key，线程的变量副本作为Map的value，这样就能让各个线程的变量副本实现数据隔离的效果。这是最简单的设计方法，JDK最早期的ThreadLocal确实是这样设计的。

### (2)现在的设计

首先让每个Thread创建一个ThreadLocalMap，这个Map的key是ThreadLocal实例本身，value才是真正要存储的局部变量。

具体设计如下：每个Thread线程内部都有一个Map(ThreadLocalMap)、Map里面存储ThreadLocal对象(key)和线程的变量副本(value)、Thread内部的Map由ThreadLocal维护，ThreadLocal会向Map获取和设置线程的变量副本、其他线程不能获取当前线程的变量副本，从而实现数据隔离。

### (3)现在的设计的优势

**优势一：** 每个Map存储的Entry数量变少，可以降低Hash冲突发生的概率。因为之前的存储数量由Thread的数量决定，现在由ThreadLocal的数量决定。在实际中，ThreadLocal的数量往往要少于Thread的数量。

**优势二：** 当Thread销毁后，对应的ThreadLocalMap也随之销毁。让线程变量副本的生命周期跟随着线程的生命周期，可以减少内存的占用。

### (4)ThreadLocal的整体设计原理

ThreadLocal为实现多个线程对同一个共享变量进行set操作时线程隔离，每个线程都有一个与ThreadLocal关联的容器来存储共享变量的初始化副本。当线程对变量副本更新时，只更新存储在当前线程关联容器中的数据副本。

如下图示，在每个线程中都会维护一个成员变量ThreadLocalMap。其中key是一个指向ThreadLocal实例的弱引用，而value表示ThreadLocal的初始化值或者当前线程执行set()方法设置的值。

假设定义了3个不同功能的ThreadLocal共享变量，而在Thread1中分别用到了这3个ThreadLocal进行操作，那么这3个ThreadLocal都会存储到Thread1的ThreadLocalMap中。如果Thread2也想用这3个ThreadLocal共享变量，那么在Thread2中也会维护一个ThreadLocalMap，把这3个ThreadLocal共享变量保存到该ThreadLocalMap中。如果Thread1想要对local1进行运算，则将local1实例作为key，从Thread1的ThreadLocalMap中获取对应的value值，进行运算即可。

![图片](assets/aeb275917263.png)

### (5)ThreadLocalMap的弱引用

ThreadLocalMap的数组table中的Entry元素的key什么时候会为空？当线程已经退出 \+ ThreadLocal已失去了线程的引用 \+ 垃圾回收时，key便会为空。也就是如果ThreadLocal对象被回收了，那么ThreadLocalMap中的key就会为空。因为Entry继承自WeakReference，也就是key(ThreadLocal对象)是弱引用，使用弱引用的目的是将ThreadLocal对象的生命周期和线程的生命周期进行解绑。

ThreadLocalMap的数组中的Entry元素的key，无论使用强引用还是弱引用，都无法完全避免内存泄漏，出现内存泄露与使用弱引用是没有关系的。

要完全避免内存泄漏只有两种方式：一.使用完ThreadLocal后，调用其remove()方法删除对应的Entry元素。二.使用完ThreadLocal后，当前线程也结束运行。相对第一种方式，第二种方式显然更不好控制。特别是在使用线程池的时候，核心线程一般不会随便结束的。也就是说，只要记得在使用完ThreadLocal后及时调用remove()方法删除Entry，那么无论Entry元素的key是强引用还是弱引用都不会出现内存泄露的问题。

那么为什么Entry元素的key要用弱引用呢？因为在调用ThreadLocal的set()、get()、remove()方法中，会触发调用ThreadLocalMap的set()、getEntry()、remove()方法。这些方法会判断key是否为null，如果为null就设置对应的value也为null。这就意味着使用完ThreadLocal，CurrentThread依然运行的前提下，就算忘记调用remove()方法删除Entry元素，弱引用也比强引用多一层保障。弱引用的ThreadLocal对象会被回收，那么对应的value在下一次调用set()、getEntry()、remove()方法时就会被清除，从而避免内存泄漏。但如果没有下一次调用set()、getEntry()、remove()中的任一方法，那么还是会存在内存泄露的问题。

### (6)使用线性探测法解决Hash冲突

ThreadLocalMap是使用线性探测法(开放寻址法)来解决Hash冲突的，该方法一次探测下一个位置，直到有空的位置后插入。若整个空间都找不到有空的位置，则产生溢出。

假设当前table长度为16，如果根据当前key计算出来的Hash值为14。此时table[14]上已经有值，且其key与当前key不一致，则发生了Hash冲突。这时就会将14加1得到15，取table[15]进行判断。如果判断table[15]时还是Hash冲突，那么就会回到0，取table[0]继续判断，直到可以插入为止。

## 25.Disruptor的生产者源码

### (1)通过Sequence序号发布消息

生产者可以先从RingBuffer中获取一个可用的Sequence序号，然后再根据该Sequence序号从RingBuffer的环形数组中获取对应的元素，接着对该元素进行赋值替换，最后调用RingBuffer的publish()方法设置当前生产者的Sequence序号来完成事件消息的发布。其中，RingBuffer的publish(sequence)方法会调用Sequencer接口的publish()方法来设置当前生产者的Sequence序号。RingBuffer的sequencer属性会在创建RingBuffer对象时传入，而创建RingBuffer对象的时机则是在初始化Disruptor的时候。

在Disruptor的构造方法中，会调用RingBuffer的create()方法，RingBuffer的create()方法会根据不同的生产者类型来初始化sequencer属性。由生产者线程通过new创建的Sequencer接口实现类的实例就是一个生产者。单生产者的线程执行上面的main()方法时，会创建一个单生产者Sequencer实例来代表生产者。多生产者的线程执行如下的main()方法时，会创建一个多生产者Sequencer实例来代表生产者。

SingleProducerSequencer的publish()方法在发布事件消息时，首先会设置当前生产者的Sequence，然后会通过等待策略通知阻塞的消费者。

MultiProducerSequencer的publish()方法在发布事件消息时，则会通过UnSafe设置sequence在int数组中对应元素的值。

### (2)通过Translator事件转换器发布消息

生产者还可以直接调用RingBuffer的tryPublishEvent()方法来完成发布事件消息到RingBuffer。该方法首先会调用Sequencer接口的tryNext()方法获取sequence序号，然后根据该sequence序号从RingBuffer的环形数组中获取对应的元素，接着再调用RingBuffer的translateAndPublish()方法将事件消息赋值替换到该元素中，最后调用Sequencer接口的publish()方法设置当前生产者的sequence序号来完成事件消息的发布。

## 26.Disruptor的消费者源码

Disruptor的消费者主要由BatchEventProcessor类和WorkProcessor类来实现，并通过Disruptor的handleEventsWith()方法或者handleEventsWithWorkerPool()方法和start()方法来启动。

执行Disruptor的handleEventsWith()方法绑定消费者时，会创建BatchEventProcessor对象，并将其添加到Disruptor的consumerRepository属性。

执行Disruptor的handleEventsWithWorkerPool()方法绑定消费者时，则会创建WorkProcessor对象，并将该对象添加到Disruptor的consumerRepository属性。

执行Disruptor的start()方法启动Disruptor实例时，便会通过线程池执行BatchEventProcessor里的run()方法，或者通过线程池执行WorkProcessor里的run()方法。

执行BatchEventProcessor的run()方法时，会通过修改BatchEventProcessor的sequence来实现消费RingBuffer的数据。

执行WorkProcessor的run()方法时，会通过修改WorkProcessor的sequence来实现消费RingBuffer的数据。

## 27.Disruptor的WaitStrategy等待策略

在生产者发布消息时，会调用WaitStrategy的signalAllWhenBlocking()方法唤醒阻塞的消费者。在消费者消费消息时，会调用WaitStrategy的waitFor()方法阻塞消费过快的消费者。

当然，不同的策略不一定就是阻塞消费者，比如BlockingWaitStrategy会通过ReentrantLock来阻塞消费者，而YieldingWaitStrategy则通过yield切换线程来实现让消费者无锁等待，即通过Thread的yield()方法切换线程让另一个线程继续执行自旋判断操作。

所以YieldingWaitStrategy等待策略的效率是最高的 \+ 最耗费CPU资源，当然效率次高、比较耗费CPU资源的是BusySpinWaitStrategy等待策略。

为了达到最高效率，有大量CPU资源，可切换线程让多个线程各自自旋100次进行判断 为了保证高效的同时兼顾CPU资源，可以让单个线程一直自旋不限次数进行判断 为了保证比较高效更加兼顾CPU资源，可以切换线程自旋 + 最少睡眠 为了完全兼顾CPU资源不考虑效率问题，可以采用重入锁实现阻塞唤醒 为了完全兼顾CPU资源但考虑一点效率，可以采用重入锁 + GAS唤醒。

## 28.Disruptor的高性能原因

### (1)使用了环形结构 + 数组 + 内存预加载

环形数组可以避免数组扩容和缩容带来的性能损耗。

初始化RingBuffer时，会将entries数组里的每一个元素都先new出来。比如RingBuffer的大小设置为8，那么初始化RingBuffer时，就会先将entries数组的8个元素分别指向新new出来的空的Event对象。往RingBuffer填充元素时，只是将对应的Event对象进行赋值。所以RingBuffer中的Event对象是一直存活着的，也就是说它能最小程度减少系统GC频率，从而提升性能。

### (2)使用了单线程写的方式并配合内存屏障

Disruptor的RingBuffer之所以可以做到完全无锁是因为单线程写。离开单线程写，没有任何技术可以做到完全无锁。Redis和Netty等高性能技术框架也是利用单线程写来实现的。

具体就是：单生产者时，固然只有一个生产者线程在写。多生产者时，每个生产者线程都只会写各自获取到的Sequence序号对应的环形数组的元素，从而使得多个生产者线程相互之间不会产生写冲突。

### (3)消除伪共享(填充缓存行)

CPU缓存是以缓存行(Cache Line)为单位进行存储的。缓存行是2的整数幂个连续字节，一般为32-256个字节，最常见的缓存行大小是64个字节。当多线程修改互相独立的变量时，如果这些变量共享同一个缓存行，就会对这个缓存行形成竞争，从而无意中影响彼此性能，这就是伪共享。

消除伪共享：利用了空间换时间的思想。由于代表着一个序号的Sequence其核心字段value是一个long型变量(占8个字节)，所以有可能会出现多个Sequence对象的value变量共享同一个缓存行。因此，需要对Sequence对象的value变量消除伪共享。具体做法就是：对Sequence对象的value变量前后增加7个long型变量。

注意：伪共享与Sequence的静态变量无关，因为静态变量本身就是多个线程共享的，而不是多个线程隔离独立的。

### (4)序号栅栏和序号配合使用来消除锁

**高性能的序号获取优化：** 为避免生产者每次执行next()获取序号时，都要查询消费者的最小序号，Disruptor采取了自旋 + LockSupport挂起线程 + 缓存最小序号 + CAS来优化。既避免了锁，也尽量在不耗费CPU的情况下提升了性能。

单生产者的情况下，只有一个线程添加元素，此时没必要使用锁。多生产者的情况下，会有多个线程并发获取Sequence序号添加元素，此时会通过自旋 + CAS避免锁。

### (5)提供了多种不同性能的等待策略

```
为了达到最高效率，有大量CPU资源，可切换线程让多个线程各自自旋100次进行判断
为了保证高效的同时兼顾CPU资源，可以让单个线程一直自旋不限次数进行判断
为了保证比较高效更加兼顾CPU资源，可以切换线程自旋 + 最少睡眠
为了完全兼顾CPU资源不考虑效率问题，可以采用重入锁实现阻塞唤醒
为了完全兼顾CPU资源但考虑一点效率，可以采用重入锁 + GAS唤醒。
```
