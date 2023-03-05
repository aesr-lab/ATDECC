#pragma once

#include <queue>
#include <mutex>
#include <condition_variable>
#include <chrono>

// A threadsafe-queue.
template <class T>
class SafeQueue
{
public:
  SafeQueue(void)
    : q()
    , m()
    , c()
  {}

  ~SafeQueue(void)
  {}

  void push(T t)
  {
    {
      std::lock_guard<std::mutex> lock(qMutex);
      q.push(std::move(t));
    }
    c.notify_one();
  }

  bool try_pop(T &t, std::chrono::milliseconds timeout)
  {
    std::unique_lock<std::mutex> lock(qMutex);

    if(!c.wait_for(lock, timeout, [this] { return !q.empty(); }))
      return false;

    t = std::move(q.front());
    q.pop();

    return true;
  }

private:
  std::queue<T> q;
  mutable std::mutex m;
  std::condition_variable c;
};
