class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts[:]
        self.values = values[:]
        self.n = len(counts)
        self.total_v = sum(c * v for c, v in zip(counts, values))
        self.max_turns = max_rounds
        self.turn_count = 0
        # Build units only for positive value types
        units = []
        for i in range(self.n):
            if values[i] > 0:
                units.extend([(values[i], i)] * counts[i])
        self.sorted_units = sorted(units)
        self.total_units = len(units)
        # Precompute claims for each k (concede k lowest value units)
        self.claims_for_k = {}
        for k in range(self.total_units + 1):
            claim = [0] * self.n
            for j in range(k, self.total_units):
                claim[self.sorted_units[j][1]] += 1
            self.claims_for_k[k] = claim

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn_count += 1
        turns_left = self.max_turns - self.turn_count + 1
        if o is not None:
            accept_val = sum(v * oo for v, oo in zip(self.values, o))
            # Early accept fair or generous offers
            if accept_val >= self.total_v / 2:
                return None
            # Desperate near end
            if turns_left <= 3 and accept_val > 0:
                return None
        # Compute proposed k
        if self.max_turns == 0:
            return [0] * self.n
        progress = (self.turn_count - 1) / max(self.max_turns - 1, 1)
        hold_progress = 0.6
        if progress < hold_progress:
            prop_k = 0
        else:
            frac = (progress - hold_progress) / (1 - hold_progress)
            prop_k = int(self.total_units * frac)
        prop_k = min(prop_k, self.total_units)
        prop_claim = self.claims_for_k[prop_k]
        prop_val = sum(v * c for v, c in zip(self.values, prop_claim))
        if o is not None:
            accept_val = sum(v * oo for v, oo in zip(self.values, o))
            # Accept if at least as good as my proposal (with tolerance)
            if accept_val + 1 >= prop_val:
                return None
            # Also accept decent late offers
            if turns_left <= 6 and accept_val >= self.total_v * 0.3:
                return None
        # Counter or first offer
        return prop_claim[:]