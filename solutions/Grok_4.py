import math

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.n_types = len(counts)
        self.total = sum(counts[i] * values[i] for i in range(self.n_types))
        self.max_turns = 2 * max_rounds
        self.my_turn_number = 0
        self.partner_offers = []

    def value(self, o: list[int]) -> float:
        return sum(o[i] * self.values[i] for i in range(self.n_types))

    def estimate_v_partner(self) -> list[float]:
        if not self.partner_offers:
            return self.values.copy()
        num_off = len(self.partner_offers)
        avg_taken = [0.0] * self.n_types
        for o in self.partner_offers:
            for i in range(self.n_types):
                taken = self.counts[i] - o[i]
                avg_taken[i] += taken
        for i in range(self.n_types):
            avg_taken[i] /= num_off
        sum_avg = sum(avg_taken)
        if sum_avg == 0:
            return [0.0] * self.n_types
        c = self.total / sum_avg
        v = [0.0] * self.n_types
        for i in range(self.n_types):
            v[i] = c * (avg_taken[i] / self.counts[i]) if self.counts[i] > 0 else 0.0
        return v

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.my_turn_number += 1
        if self.me == 0:
            current_turn = 2 * (self.my_turn_number - 1) + 1
        else:
            current_turn = 2 * self.my_turn_number
        remaining = self.max_turns - current_turn
        if o is not None:
            self.partner_offers.append(o)

        # Special handling for last turn
        if remaining == 0:
            if o is None:
                # Must make an offer
                pass
            else:
                my_val = self.value(o)
                if my_val > 0:
                    return None
                else:
                    # Counter to force no deal
                    return [self.counts[i] if self.values[i] > 0 else 0 for i in range(self.n_types)]

        # Compute min_accept
        min_accept = self.total * remaining / self.max_turns if self.max_turns > 0 else 0

        # Decide to accept
        if o is not None and self.value(o) >= min_accept:
            return None

        # Make counter-offer
        v_partner = self.estimate_v_partner()
        partner_threshold = self.total * max(0, remaining - 1) / self.max_turns if self.max_turns > 0 else 0
        m = [0] * self.n_types
        current_util = 0.0
        # Give free items (valueless to me but valuable to partner)
        for i in range(self.n_types):
            if self.values[i] == 0 and v_partner[i] > 0:
                m[i] = self.counts[i]
                current_util += self.counts[i] * v_partner[i]
        remaining_needed = partner_threshold - current_util
        if remaining_needed > 0:
            candidates = [i for i in range(self.n_types) if self.values[i] > 0 and v_partner[i] > 0 and m[i] < self.counts[i]]
            candidates.sort(key=lambda i: v_partner[i] / self.values[i], reverse=True)
            for i in candidates:
                util_per = v_partner[i]
                max_give = self.counts[i] - m[i]
                if remaining_needed <= 0:
                    break
                num_needed = math.ceil(remaining_needed / util_per)
                num = min(num_needed, max_give)
                m[i] += num
                added = num * util_per
                current_util += added
                remaining_needed -= added
        # Compute my offer (what I get)
        my_offer = [self.counts[i] - m[i] for i in range(self.n_types)]
        return my_offer