class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts[:]
        self.values = values[:]
        self.total = sum(c * v for c, v in zip(counts, values))
        self.max_rounds = max_rounds
        self.our_turns = 0
        self.opp_offers = []

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.our_turns += 1
        n = len(self.counts)
        progress = min(1.0, self.our_turns / (self.max_rounds + 1.0))

        # Accept immediately on last turn if positive value
        if o is not None and self.our_turns >= self.max_rounds:
            our_val = sum(self.values[i] * o[i] for i in range(n))
            if our_val > 0:
                return None

        if o is not None:
            self.opp_offers.append(o[:])
            our_val = sum(self.values[i] * o[i] for i in range(n))
            thresh = self.total * (0.75 - 0.65 * progress)
            if our_val >= thresh or (progress >= 0.8 and our_val > 0):
                return None

        # Initial greedy offer
        if len(self.opp_offers) == 0:
            return [self.counts[i] if self.values[i] > 0 else 0 for i in range(n)]

        # Estimate opponent's relative keeps
        avg_rel_keep = [0.0] * n
        num_off = len(self.opp_offers)
        for oo in self.opp_offers:
            for i in range(n):
                keep = self.counts[i] - oo[i]
                rel = keep / self.counts[i] if self.counts[i] > 0 else 0.0
                avg_rel_keep[i] += rel
        for i in range(n):
            avg_rel_keep[i] /= num_off

        total_avg_keep_items = sum(avg_rel_keep[j] * self.counts[j] for j in range(n))
        if total_avg_keep_items < 1e-6:
            return [self.counts[i] if self.values[i] > 0 else 0 for i in range(n)]

        mu = self.total / total_avg_keep_items

        # Fair split biased by progress
        prop = [0] * n
        for i in range(n):
            est_opp_vi = mu * avg_rel_keep[i]
            k = 0.3 + 0.7 * progress  # bias from aggressive to fair
            denom = self.values[i] + k * est_opp_vi + 1e-9
            frac = self.values[i] / denom
            s = round(frac * self.counts[i])
            prop[i] = max(0, min(self.counts[i], s))

        # Mix with greedy, conceding over time
        greedy = [self.counts[i] if self.values[i] > 0 else 0 for i in range(n)]
        alpha = 1.0 - progress
        proposal = [0] * n
        for i in range(n):
            mixed = greedy[i] * alpha + prop[i] * (1 - alpha)
            s = round(mixed)
            proposal[i] = max(0, min(self.counts[i], s))

        # Extra concession near end
        if progress > 0.9 and self.opp_offers:
            prop_val = sum(self.values[i] * proposal[i] for i in range(n))
            if prop_val < self.total * 0.6:
                last_o = self.opp_offers[-1]
                for i in range(n):
                    mixed = (proposal[i] * 0.7 + last_o[i] * 0.3)
                    proposal[i] = max(0, min(self.counts[i], round(mixed)))

        return proposal