class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts[:]
        self.values = values[:]
        self.n = len(counts)
        self.total = sum(c * v for c, v in zip(counts, values))
        self.total_items = sum(counts)
        self.max_rounds = max_rounds
        self.history = []
        self.opp_val = [self.total / self.total_items] * self.n
        self.turn_num = 0

    def value(self, share: list[int], vals: list[float | int]) -> float:
        return sum(v * s for v, s in zip(vals, share))

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn_num += 1
        if o is not None:
            self.history.append(o[:])
        # Update opp_val
        if self.history:
            num_h = len(self.history)
            avg_prop = [0.0] * self.n
            for i in range(self.n):
                s = sum((self.counts[i] - h[i]) / self.counts[i] for h in self.history)
                avg_prop[i] = s / num_h
            self.opp_val = [avg_prop[i] * (self.total / self.total_items) for i in range(self.n)]
        # Urgency
        remaining_rounds = max(1, self.max_rounds - self.turn_num + 1)
        urgency = 1.0 - remaining_rounds / self.max_rounds
        # Check accept
        if o is not None:
            my_val_o = self.value(o, self.values)
            thresh = self.total * max(0.05, 0.8 - 0.7 * urgency)
            if my_val_o >= thresh or (urgency >= 0.9 and my_val_o > 0):
                return None
        # First offer
        if self.turn_num == 1 and o is None:
            return [self.counts[i] if self.values[i] > 0 else 0 for i in range(self.n)]
        # Enumerate best offer
        opp_min = self.total * max(0.05, 0.6 - 0.5 * urgency)
        best_offer = None
        best_my_val = -1.0
        def gen(pos: int, current: list[int]):
            nonlocal best_offer, best_my_val
            if pos == self.n:
                my_v = self.value(current, self.values)
                opp_share = [self.counts[i] - current[i] for i in range(self.n)]
                opp_v = self.value(opp_share, self.opp_val)
                if opp_v >= opp_min and my_v > best_my_val:
                    best_my_val = my_v
                    best_offer = current[:]
                return
            for k in range(self.counts[pos] + 1):
                current[pos] = k
                gen(pos + 1, current)
            current[pos] = 0
        current = [0] * self.n
        gen(0, current)
        if best_offer is not None:
            return best_offer
        # Fallback to greedy
        return [self.counts[i] if self.values[i] > 0 else 0 for i in range(self.n)]