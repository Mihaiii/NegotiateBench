class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.n_types = len(counts)
        self.V = sum(counts[i] * values[i] for i in range(self.n_types))
        total_objects = sum(counts)
        self.default_p = self.V / total_objects if total_objects > 0 else 0
        self.history_partner_offers = []
        self.turn = 0

    def utility(self, off):
        return sum((self.counts[i] - off[i]) * self.values[i] for i in range(self.n_types))

    def compute_offer(self, estimated_p):
        offer = []
        for i in range(self.n_types):
            c = self.counts[i]
            if c == 0:
                offer.append(0)
                continue
            v = self.values[i]
            p = estimated_p[i]
            if v + p == 0:
                offer.append(0)
            else:
                frac = v / (v + p)
                num = round(frac * c)
                offer.append(max(0, min(c, num)))
        return offer

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn += 1
        remaining = self.max_rounds - self.turn + 1
        if o is not None:
            self.history_partner_offers.append(o)
            u = self.utility(o)
            if remaining > 1:
                min_accept = self.V * remaining / (self.max_rounds + 1)
                if u >= min_accept:
                    return None
            else:
                if u > 0:
                    return None
                elif self.me == 1:
                    return None  # accept even if 0, same as not

        # compute estimated_p
        if not self.history_partner_offers:
            estimated_p = [self.default_p] * self.n_types
        else:
            prop = [0.0] * self.n_types
            num_hist = len(self.history_partner_offers)
            for past_o in self.history_partner_offers:
                for i in range(self.n_types):
                    c = self.counts[i]
                    if c > 0:
                        f = past_o[i] / c
                        prop[i] += f
            for i in range(self.n_types):
                if self.counts[i] > 0:
                    prop[i] /= num_hist
                prop[i] += 1e-6
            denom = sum(prop[i] * self.counts[i] for i in range(self.n_types))
            if denom == 0:
                estimated_p = [0.0] * self.n_types
            else:
                scale = self.V / denom
                estimated_p = [prop[i] * scale for i in range(self.n_types)]

        # concession
        concession = (self.turn - 1) / (self.max_rounds - 1) if self.max_rounds > 1 else 0.0
        estimated_p = [estimated_p[i] * (1 + concession) for i in range(self.n_types)]

        if remaining == 1 and self.me == 0:
            # greedy offer for last counter
            offer = [self.counts[i] if self.values[i] > 0 else 0 for i in range(self.n_types)]
            opponent_u = sum(estimated_p[i] * (self.counts[i] - offer[i]) for i in range(self.n_types))
            if opponent_u <= 0:
                candidates = []
                for i in range(self.n_types):
                    if estimated_p[i] > 0 and offer[i] > 0:
                        candidates.append((self.values[i], -estimated_p[i], i))
                if candidates:
                    candidates.sort()
                    best_i = candidates[0][2]
                    offer[best_i] -= 1
            return offer
        else:
            # normal offer
            offer = self.compute_offer(estimated_p)
            return offer