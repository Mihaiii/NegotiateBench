class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.counts = counts[:]
        self.values = values[:]
        self.n = len(counts)
        self.total = sum(c * v for c, v in zip(counts, values))
        self.max_our_turns = max_rounds
        self.turn = 0
        self.opp_self_history = []

    def my_value(self, share: list[int]) -> int:
        return sum(s * self.values[i] for i, s in enumerate(share))

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn += 1
        if o is None:
            return [self.counts[i] if self.values[i] > 0 else 0 for i in range(self.n)]
        opp_self = [self.counts[i] - o[i] for i in range(self.n)]
        self.opp_self_history.append(opp_self)
        val = self.my_value(o)
        progress = 0.0 if self.max_our_turns <= 1 else max(0.0, min(1.0, (self.turn - 1) / (self.max_our_turns - 1)))
        thresh_frac = 0.85 * (1 - progress) + 0.5 * progress
        is_last = (self.turn == self.max_our_turns)
        if val >= thresh_frac * self.total or (is_last and val > 0):
            return None
        # counteroffer
        num_hist = len(self.opp_self_history)
        num_use = min(4, num_hist)
        avg_self = [0.0] * self.n
        for i in range(self.n):
            s = sum(self.opp_self_history[num_hist - 1 - k][i] for k in range(num_use))
            avg_self[i] = s / num_use
        opp_frac = [avg_self[i] / self.counts[i] if self.counts[i] > 0 else 0.0 for i in range(self.n)]
        concede_score = [opp_frac[i] / max(self.values[i], 0.01) for i in range(self.n)]
        units = []
        for i in range(self.n):
            score = concede_score[i]
            for _ in range(self.counts[i]):
                units.append((score, i))
        units.sort(key=lambda x: (-x[0], x[1]))
        total_units = len(units)
        concede_frac = 0.1 + 0.25 * progress
        concede_num = min(total_units, int(total_units * concede_frac))
        prop = self.counts[:]
        for j in range(concede_num):
            _, i = units[j]
            prop[i] -= 1
        if self.my_value(prop) <= val:
            return None
        return prop