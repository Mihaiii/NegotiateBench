class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts[:]
        self.values = values[:]
        self.n = len(counts)
        self.total = sum(c * v for c, v in zip(counts, values))
        self.max_rounds = max_rounds
        self.turn_num = 0
        self.turns_possible = max_rounds * 2
        self.avg_prop = [0.5] * self.n  # init neutral
        self.opp_val = [self.total / sum(counts)] * self.n  # init uniform per item

    def value(self, share: list[int], vals: list[int]) -> float:
        return sum(v * s for v, s in zip(vals, share))

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn_num += 1
        urgency = min(1.0, self.turn_num / self.turns_possible)

        # Adaptive EMA alpha, slow learning early
        ema_alpha = 0.1 + 0.4 * urgency

        # Update opp estimate
        if o is not None:
            for i in range(self.n):
                opp_take = self.counts[i] - o[i]
                frac = opp_take / max(1, self.counts[i])
                self.avg_prop[i] = ema_alpha * frac + (1 - ema_alpha) * self.avg_prop[i]
            denom = sum(self.avg_prop[j] * self.counts[j] for j in range(self.n))
            if denom > 1e-6:
                self.opp_val = [self.avg_prop[i] * self.total / denom for i in range(self.n)]
            else:
                self.opp_val = [0.0] * self.n

        # Greedy offer: all positive value items
        greedy = [0] * self.n
        for i in range(self.n):
            if self.values[i] > 0:
                greedy[i] = self.counts[i]

        # First offer special if first player
        if o is None:
            return greedy

        # Fair compromise offer
        gamma = 0.3 + 1.2 * urgency
        fair = [0] * self.n
        for i in range(self.n):
            myv = float(self.values[i])
            oppv = self.opp_val[i]
            coeff = myv - gamma * oppv
            scale = (myv + oppv + 1e-6) / 2
            frac_take = 0.5 + 0.5 * (coeff / scale)
            frac_take = max(0.0, min(1.0, frac_take))
            k = max(0, min(self.counts[i], round(frac_take * self.counts[i])))
            fair[i] = k

        # Mix: early greedy, late fair
        mix_alpha = urgency ** 2  # quadratic, slow at first
        best_offer = [max(0, min(self.counts[i], round((1 - mix_alpha) * greedy[i] + mix_alpha * fair[i])))
                      for i in range(self.n)]

        my_best_val = self.value(best_offer, self.values)

        # Accept?
        if o is not None:
            my_o_val = self.value(o, self.values)
            thresh = self.total * max(0.15, 0.75 - 0.65 * urgency)
            is_late = urgency > 0.85
            accept = (my_o_val >= thresh or
                      (is_late and my_o_val > 0.01 * self.total) or
                      my_o_val >= 0.98 * my_best_val)
            if accept:
                return None

        return best_offer