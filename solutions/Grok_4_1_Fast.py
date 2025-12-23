class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts[:]
        self.values = values[:]
        self.n = len(counts)
        self.total = sum(c * v for c, v in zip(self.counts, self.values))
        self.max_rounds = max_rounds
        self.max_our_turns = max_rounds + (1 if me == 0 else 0)
        self.turn = 0
        self.opp_self_history = []

    def my_value(self, share: list[int]) -> int:
        return sum(s * self.values[i] for i, s in enumerate(share))

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn += 1
        if o is None:
            prop = [self.counts[i] if self.values[i] > 0 else 0 for i in range(self.n)]
            return prop
        opp_self = [self.counts[i] - o[i] for i in range(self.n)]
        self.opp_self_history.append(opp_self)
        myval = self.my_value(o)
        progress = min(1.0, (self.turn - 1) / max(self.max_our_turns - 1, 1)) if self.max_our_turns > 0 else 1.0
        thresh_frac = 0.7 * (1.0 - progress) + 0.25 * progress
        if myval >= thresh_frac * self.total or (self.turn >= self.max_rounds and myval > 0):
            return None
        # compute counteroffer
        num_hist = len(self.opp_self_history)
        avg_self = [sum(self.opp_self_history[j][i] for j in range(num_hist)) / num_hist for i in range(self.n)]
        opp_frac = [avg_self[i] / self.counts[i] if self.counts[i] > 0 else 0.0 for i in range(self.n)]
        concede_score = [opp_frac[i] / max(self.values[i], 0.01) for i in range(self.n)]
        units = []
        for i in range(self.n):
            score = concede_score[i]
            for _ in range(self.counts[i]):
                units.append((score, i))
        units.sort(key=lambda x: x[0], reverse=True)
        total_units = len(units)
        concede_frac = 0.2 + 0.45 * progress
        concede_num = min(total_units, int(total_units * concede_frac))
        prop = self.counts[:]
        for _, i in units[:concede_num]:
            prop[i] -= 1
        if self.my_value(prop) < myval:
            return None
        return prop