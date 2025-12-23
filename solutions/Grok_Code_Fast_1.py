class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.total = sum(c * v for c, v in zip(counts, values))
        self.threshold = 0.49 * self.total
        self.step = 0
        self.counts = counts
        self.values = values

    def offer(self, o: list[int] | None) -> list[int] | None:
        if o is None:
            return self._get_offer(0)
        offered_v = sum(o[i] * self.values[i] for i in range(len(o)))
        if offered_v >= self.threshold:
            return None
        self.step += 1
        return self._get_offer(self.step)

    def _get_offer(self, step: int) -> list[int]:
        my_offer = self.counts.copy()
        sort_items = sorted(range(len(self.counts)), key=lambda i: self.values[i], reverse=True)
        remain_step = step
        for i in sort_items:
            if remain_step > 0 and my_offer[i] > 0:
                can_reduce = min(remain_step, my_offer[i])
                my_offer[i] -= can_reduce
                remain_step -= can_reduce
        return my_offer