class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.n = len(counts)
        self.total = sum(c * v for c, v in zip(counts, values))
        self.turn = 0
        self.opp_history = []

    def my_value(self, share: list[int] | list[float]) -> float:
        return sum(self.values[i] * share[i] for i in range(self.n))

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn += 1
        progress = min(1.0, self.turn / (self.max_rounds + 1.0))

        my_val = 0.0
        if o is not None:
            my_val = self.my_value(o)
            accept_thresh = 0.65 + 0.25 * (1 - progress)
            if my_val >= accept_thresh * self.total:
                return None

        if o is not None:
            opp_self = [self.counts[i] - o[i] for i in range(self.n)]
            self.opp_history.append(opp_self)

        # Estimate opp_val
        if self.opp_history:
            num_use = min(5, len(self.opp_history))
            avg_demand = [sum(self.opp_history[-num_use:][k][i] for k in range(num_use)) / num_use for i in range(self.n)]
            avg_frac = [avg_demand[i] / self.counts[i] if self.counts[i] > 0 else 0.0 for i in range(self.n)]
        else:
            avg_frac = [0.5] * self.n
        sum_weight = sum(avg_frac[j] * self.counts[j] for j in range(self.n))
        if sum_weight <= 0:
            avg_frac = [0.5] * self.n
            sum_weight = sum(avg_frac[j] * self.counts[j] for j in range(self.n))
        self.opp_val = [avg_frac[i] * self.total / sum_weight for i in range(self.n)]

        # Late game desperate accept
        if o is not None:
            if progress > 0.6 and my_val >= 0.45 * self.total:
                return None
            if progress > 0.85 and my_val >= 0.25 * self.total:
                return None
            if self.turn > self.max_rounds * 1.2 and my_val > 0.01 * self.total:
                return None

        # Compute proposal: greedy give opp cheap items first
        opp_frac = 0.25 + 0.55 * progress
        opp_budget = opp_frac * self.total
        density = [self.values[i] / max(self.opp_val[i], 1e-10) if self.opp_val[i] > 1e-10 else (float('inf') if self.values[i] > 0 else 0.0) for i in range(self.n)]
        type_order = sorted(range(self.n), key=lambda k: density[k])
        opp_share = [0] * self.n
        remaining = opp_budget
        for i in type_order:
            if remaining < 1e-6:
                break
            ov = self.opp_val[i]
            if ov < 1e-9:
                continue
            ci = self.counts[i]
            k_frac = remaining / ov
            k = min(ci, k_frac)
            opp_share[i] = max(0, min(ci, int(round(k))))
            remaining -= opp_share[i] * ov

        prop = [self.counts[i] - opp_share[i] for i in range(self.n)]

        if o is not None:
            prop_val = self.my_value(prop)
            if prop_val + 1e-6 < my_val:
                return None

        return prop