class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts[:]
        self.values = values
        self.n = len(counts)
        self.total = sum(c * v for c, v in zip(counts, values))
        self.max_rounds = max_rounds
        self.turn = 0
        self.opp_self_history = []
        self.my_self_history = []
        self.concede_order_static = sorted(range(self.n), key=lambda i: self.values[i])

    def my_value(self, share: list[int]) -> int:
        return sum(s * self.values[i] for i, s in enumerate(share))

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn += 1
        if o is None:
            prop = self.counts[:]
            self.my_self_history.append(prop)
            return prop
        # o is proposed share for us
        opp_proposed_self = [self.counts[i] - o[i] for i in range(self.n)]
        self.opp_self_history.append(opp_proposed_self)
        myval = self.my_value(o)
        # accept threshold
        progress = min(1.0, (self.turn - 1) / float(self.max_rounds)) if self.max_rounds > 0 else 1.0
        threshold_frac = 0.25 + 0.65 / (1 + 3 * progress)
        if myval >= threshold_frac * self.total or (self.turn >= self.max_rounds and myval > 0):
            return None
        # counteroffer
        # compute concede_score
        if self.opp_self_history:
            num_hist = len(self.opp_self_history)
            avg_self_frac = [sum(h[i] / self.counts[i] for h in self.opp_self_history) / num_hist for i in range(self.n)]
            concede_score = [avg_self_frac[i] / max(self.values[i], 1) for i in range(self.n)]
        else:
            concede_score = [1.0 / max(self.values[i], 1) for i in range(self.n)]
        # base prop on previous or full
        if self.my_self_history:
            prop = self.my_self_history[-1][:]
        else:
            prop = self.counts[:]
        # concede multiple units late
        units = max(1, int(1 + progress * 3))
        for _ in range(units):
            possible = [i for i in range(self.n) if prop[i] > 0]
            if not possible:
                break
            best_i = max(possible, key=lambda i: concede_score[i])
            prop[best_i] -= 1
        self.my_self_history.append(prop)
        return prop