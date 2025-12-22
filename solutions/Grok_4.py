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
        return sum(off[i] * self.values[i] for i in range(self.n_types))

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
        min_accept = 0 if remaining == 1 else self.V * remaining / (self.max_rounds + 1)
        if o is not None:
            self.history_partner_offers.append(o)
            u = self.utility(o)
            if u >= min_accept:
                return None
        # make offer
        if not self.history_partner_offers:
            estimated_p = [self.default_p] * self.n_types
        else:
            last_o = self.history_partner_offers[-1]
            prop = [0.0] * self.n_types
            denom = 0.0
            for i in range(self.n_types):
                c = self.counts[i]
                if c == 0:
                    prop[i] = 0
                    continue
                f = last_o[i] / c
                prop[i] = 1 - f + 1e-6
                denom += prop[i] * c
            scale = self.V / denom
            estimated_p = [prop[i] * scale for i in range(self.n_types)]
        prop_offer = self.compute_offer(estimated_p)
        return prop_offer