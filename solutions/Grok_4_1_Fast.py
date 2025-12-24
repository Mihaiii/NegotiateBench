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

    def my_value(self, share: list[int]) -> int:
        return sum(s * self.values[i] for i, s in enumerate(share))

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn += 1
        progress = 0.0 if self.max_rounds <= 1 else max(0.0, min(1.0, (self.turn - 1) / (self.max_rounds - 1)))
        if o is not None:
            opp_self = [self.counts[i] - o[i] for i in range(self.n)]
            self.opp_history.append(opp_self)
            val = self.my_value(o)
            thresh = 0.6 + 0.3 * (1 - progress)
            if val >= thresh * self.total:
                return None
            if self.turn >= self.max_rounds - 1:
                if val >= 0.45 * self.total or val > 0:
                    return None
        # Estimate opp_val
        opp_val = [0.1] * self.n
        if self.opp_history:
            num_use = min(5, len(self.opp_history))
            avg_self_frac = [0.0] * self.n
            for i in range(self.n):
                s = sum(self.opp_history[len(self.opp_history) - 1 - k][i] for k in range(num_use))
                avg_self_frac[i] = (s / num_use) / self.counts[i] if self.counts[i] > 0 else 0.0
            sum_weight = sum(avg_self_frac[j] * self.counts[j] for j in range(self.n))
            if sum_weight > 0:
                for i in range(self.n):
                    opp_val[i] = avg_self_frac[i] * self.total / sum_weight
        # Target value
        target_frac = 0.75 * (1 - progress) + 0.50 * progress
        target_val = target_frac * self.total
        # Keep scores: high my/opp good to keep
        keep_score = [self.values[i] / max(opp_val[i], 0.1) for i in range(self.n)]
        # Order types by keep_score desc
        type_order = sorted(range(self.n), key=lambda i: -keep_score[i])
        prop = [0] * self.n
        remaining_val = target_val
        for i in type_order:
            if remaining_val <= 0:
                break
            v_i = max(self.values[i], 1)
            can_take = min(self.counts[i], remaining_val // v_i)
            prop[i] = can_take
            remaining_val -= can_take * self.values[i]
        # Fill remaining from any
        if remaining_val > 0:
            for i in type_order:
                if remaining_val <= 0:
                    break
                if prop[i] < self.counts[i]:
                    v_i = max(self.values[i], 1)
                    add = min(self.counts[i] - prop[i], remaining_val // v_i)
                    prop[i] += add
                    remaining_val -= add * self.values[i]
        # Clamp
        for i in range(self.n):
            prop[i] = max(0, min(self.counts[i], prop[i]))
        # If worse than o, accept
        if o is not None:
            prop_val = self.my_value(prop)
            o_val = self.my_value(o)
            if prop_val < o_val:
                return None
        return prop