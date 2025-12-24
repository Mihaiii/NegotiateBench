class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts[:]
        self.values = values[:]
        self.n = len(counts)
        self.total = sum(c * v for c, v in zip(counts, values))
        self.max_rounds = max_rounds
        self.avg_prop = [0.0] * self.n
        self.opp_val = [float(v) for v in self.values]
        self.turn_num = 0

    def value(self, share: list[int], vals: list[float | int]) -> float:
        return sum(float(v) * s for v, s in zip(vals, share))

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn_num += 1
        urgency = (self.turn_num - 1) / self.max_rounds

        # Update opp_val estimate using EMA if o provided
        if o is not None:
            for i in range(self.n):
                c = self.counts[i]
                frac = (c - o[i]) / max(c, 1)
                self.avg_prop[i] = 0.3 * frac + 0.7 * self.avg_prop[i]
            denom = sum(self.avg_prop[j] * self.counts[j] for j in range(self.n))
            if denom > 0:
                self.opp_val = [self.avg_prop[i] * float(self.total) / denom for i in range(self.n)]
            else:
                self.opp_val = [0.0] * self.n

        # Compute parameters
        gamma = 0.2 + 1.8 * urgency

        # Compute best offer greedily per type with smooth splitting
        best_offer = [0] * self.n
        my_best = 0.0
        for i in range(self.n):
            coeff = float(self.values[i]) - gamma * self.opp_val[i]
            scale = (float(self.values[i]) + self.opp_val[i] + 1e-6) / 2.0
            frac_take = 0.5 + 0.5 * (coeff / scale)
            frac_take = max(0.0, min(1.0, frac_take))
            k = round(frac_take * self.counts[i])
            k = max(0, min(self.counts[i], k))
            best_offer[i] = k
            my_best += float(self.values[i]) * k

        # Check if should accept
        if o is not None:
            my_o = self.value(o, self.values)
            thresh = self.total * max(0.05, 0.8 - 0.7 * urgency)
            if (my_o >= thresh or
                (urgency >= 0.9 and my_o > 0) or
                (urgency >= 0.5 and my_o > my_best)):
                return None

        return best_offer