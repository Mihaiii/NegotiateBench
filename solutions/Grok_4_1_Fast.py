class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts[:]
        self.values = values[:]
        self.n = len(counts)
        self.total = sum(c * v for c, v in zip(counts, values))
        self.max_turns = max_rounds
        self.turn = 0
        self.opp_self_history = []
        self.total_units = sum(counts)

    def my_value(self, share: list[int]) -> int:
        return sum(s * self.values[i] for i, s in enumerate(share))

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn += 1
        progress = 0.0 if self.max_turns <= 1 else max(0.0, min(1.0, (self.turn - 1) / (self.max_turns - 1)))
        if o is not None:
            opp_self = [self.counts[i] - o[i] for i in range(self.n)]
            self.opp_self_history.append(opp_self)
            val = self.my_value(o)
            thresh_frac = 0.90 * (1 - progress) + 0.55 * progress
            is_final = (self.turn == self.max_turns)
            if val >= thresh_frac * self.total:
                return None
            if is_final:
                min_accept = 0.4 * self.total
                if self.me == 1:  # second player: last turn overall
                    if val > 0:
                        return None
                else:  # first player: opponent has one last turn
                    if val >= min_accept:
                        return None

        # Counteroffer
        prop = [self.counts[i] if self.values[i] > 0 else 0 for i in range(self.n)]
        if self.opp_self_history:
            num_hist = len(self.opp_self_history)
            num_use = min(8, max(1, num_hist))
            avg_self = [0.0] * self.n
            for i in range(self.n):
                s = sum(self.opp_self_history[num_hist - 1 - k][i] for k in range(num_use))
                avg_self[i] = s / num_use
            avg_opp_self_units = sum(avg_self) / self.total_units
            opp_concede_unit_frac = 1 - avg_opp_self_units
            concede_unit_frac = opp_concede_unit_frac + 0.4 * progress
            concede_unit_frac = min(0.6, max(0.05, concede_unit_frac))
            concede_num = min(self.total_units, int(self.total_units * concede_unit_frac))

            opp_self_frac = [avg_self[i] / self.counts[i] if self.counts[i] > 0 else 0.0 for i in range(self.n)]
            concede_score = [opp_self_frac[i] / max(self.values[i], 0.01) for i in range(self.n)]
            units = []
            for i in range(self.n):
                score = concede_score[i]
                for _ in range(self.counts[i]):
                    units.append((score, i))
            units.sort(key=lambda x: (-x[0], x[1]))
            prop = self.counts[:]
            for j in range(concede_num):
                if j >= len(units):
                    break
                _, i = units[j]
                if prop[i] > 0:
                    prop[i] -= 1

        if o is not None:
            prop_val = self.my_value(prop)
            o_val = self.my_value(o)
            if prop_val <= o_val:
                return None
        return prop