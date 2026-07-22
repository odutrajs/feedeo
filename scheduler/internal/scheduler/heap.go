package scheduler

import (
	"container/heap"
	"time"
)

// entry representa um item na priority queue.
type entry struct {
	id          string
	scheduledAt time.Time
	index       int // posição no heap (gerenciado pelo container/heap)
}

// priorityQueue implementa heap.Interface — min-heap por scheduledAt.
type priorityQueue []*entry

func (pq priorityQueue) Len() int { return len(pq) }

func (pq priorityQueue) Less(i, j int) bool {
	return pq[i].scheduledAt.Before(pq[j].scheduledAt)
}

func (pq priorityQueue) Swap(i, j int) {
	pq[i], pq[j] = pq[j], pq[i]
	pq[i].index = i
	pq[j].index = j
}

func (pq *priorityQueue) Push(x any) {
	n := len(*pq)
	item := x.(*entry)
	item.index = n
	*pq = append(*pq, item)
}

func (pq *priorityQueue) Pop() any {
	old := *pq
	n := len(old)
	item := old[n-1]
	old[n-1] = nil
	item.index = -1
	*pq = old[:n-1]
	return item
}

func (pq *priorityQueue) Peek() *entry {
	if len(*pq) == 0 {
		return nil
	}
	return (*pq)[0]
}

func newPQ() *priorityQueue {
	pq := &priorityQueue{}
	heap.Init(pq)
	return pq
}
