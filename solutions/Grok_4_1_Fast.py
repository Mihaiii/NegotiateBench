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

    def offer(self, o: list[int] | list[float] | None) -> list[int] | None:
        self.turn += 1
        progress = 0.0 if self.max_rounds <= 1 else max(0.0, min(1.0, (self.turn - 1) / (self.max_rounds - 1)))

        opp_self = None
        if o is not None:
            opp_self = [self.counts[i] - o[i] for i in range(self.n)]
            self.opp_history.append(opp_self)
            my_val = self.my_value(o)
            accept_thresh = 0.55 + 0.35 * (1 - progress)
            if my_val >= accept_thresh * self.total:
                return None

        # Estimate opp_val
        if self.opp_history:
            num_use = min(5, len(self.opp_history))
            avg_demand = [sum(self.opp_history[-num_use:][k][i] for k in range(num_use)) / num_use for i in range(self.n)]
            avg_frac = [avg_demand[i] / self.counts[i] if self.counts[i] > 0 else 0.0 for i in range(self.n)]
        else:
            avg_frac = [0.5] * self.n
        sum_weight = sum(avg_frac[j] * self.counts[j] for j in range(self.n))
        if sum_weight <= 0:
            avg_frac = [1.0 / self.n] * self.n
            sum_weight = sum(avg_frac[j] * self.counts[j] for j in range(self.n))
        self.opp_val = [avg_frac[i] * self.total / sum_weight for i in range(self.n)]

        # Late game desperate accept
        if o is not None:
            my_val = self.my_value(o)
            if self.turn > self.max_rounds - 2 or self.turn >= self.max_rounds * 0.8:
                if my_val >= 0.25 * self.total:
                    return None
            if self.turn == self.max_rounds and self.me == 1 and my_val > 0:
                return None

        # Target: opp_concede_frac for opponent's share
        opp_concede_frac = 0.1 + 0.5 * progress
        opp_budget = self.total * (1 - opp_concede_frac)

        # Greedy knapsack by density myv / oppv
        keep_score = [self.values[i] / max(self.opp_val[i], 1e-6) for i in range(self.n)]
        type_order = sorted(range(self.n), key=lambda i: -keep_score[i])
        prop = [0.0] * self.n
        remaining_budget = opp_budget
        for i in type_order:
            o_i = self.opp_val[i]
            c_i = self.counts[i]
            if remaining_budget <= 0:
                break
            if o_i < 1e-9:
                prop[i] = c_i
                continue
            max_k = min(c_i, int(remaining_budget / o_i))
            prop[i] = max_k
            remaining_budget -= max_k * o_i

        # Clamp and round
        prop = [min(self.counts[i], max(0, int(round(prop[i])))) for i in range(self.n)]

        # If prop worse than o, accept
        if o is not None:
            prop_val = self.my_value(prop)
            o_val = self.my_value(o)
            if prop_val <= o_val:
                return None

        return prop