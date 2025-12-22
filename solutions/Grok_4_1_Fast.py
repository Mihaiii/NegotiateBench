class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts[:]
        self.values = values[:]
        self.total = sum(c * v for c, v in zip(counts, values))
        self.max_rounds = max_rounds
        self.turns_made = 0
        self.opp_offers = []

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turns_made += 1
        n = len(self.counts)
        max_turns = max(1, self.max_rounds)
        progress = min(1.0, (self.turns_made - 1) / (max_turns - 1))

        if o is not None:
            self.opp_offers.append(o[:])
            our_val = sum(self.values[i] * o[i] for i in range(n))
            thresh = self.total * (0.75 - 0.65 * progress)
            if our_val >= thresh or (progress >= 0.8 and our_val > 0):
                return None

        if len(self.opp_offers) == 0:
            return [self.counts[i] if self.values[i] > 0 else 0 for i in range(n)]

        avg_rel_keep = [0.0] * n
        num_off = len(self.opp_offers)
        for oo in self.opp_offers:
            for i in range(n):
                dem = self.counts[i] - oo[i]
                rel = dem / self.counts[i] if self.counts[i] > 0 else 0.0
                avg_rel_keep[i] += rel
        for i in range(n):
            avg_rel_keep[i] /= num_off

        total_avg_demand_obj = sum(avg_rel_keep[j] * self.counts[j] for j in range(n))
        if total_avg_demand_obj < 1e-6:
            return [self.counts[i] if self.values[i] > 0 else 0 for i in range(n)]

        mu = self.total / total_avg_demand_obj
        prop = []
        for i in range(n):
            est_opp_v = mu * avg_rel_keep[i]
            denom = self.values[i] + est_opp_v + 1e-9
            frac = self.values[i] / denom
            s = round(frac * self.counts[i])
            s = max(0, min(self.counts[i], s))
            prop.append(s)
        return prop