import math

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.n_types = len(counts)
        self.total = sum(counts[i] * values[i] for i in range(self.n_types))
        self.max_turns = 2 * max_rounds
        self.my_turn_number = 0
        self.partner_offers = []

    def value(self, o: list[int]) -> float:
        return sum(o[i] * self.values[i] for i in range(self.n_types))

    def estimate_v_partner(self) -> list[float]:
        if not self.partner_offers:
            total_items = sum(self.counts)
            if total_items == 0:
                return [0.0] * self.n_types
            unit = self.total / total_items
            return [unit] * self.n_types
        num_off = len(self.partner_offers)
        avg_taken = [0.0] * self.n_types
        sum_weights = 0.0
        alpha = 0.9
        for k in range(num_off):
            weight = alpha ** (num_off - 1 - k)
            o = self.partner_offers[k]
            for i in range(self.n_types):
                avg_taken[i] += weight * (self.counts[i] - o[i])
            sum_weights += weight
        for i in range(self.n_types):
            avg_taken[i] /= sum_weights
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
        is_last_turn = remaining == 0
        if self.me == 0:
            is_penultimate = remaining == 1
        else:
            is_penultimate = remaining == 2
        progress = current_turn / self.max_turns if self.max_turns > 0 else 1.0
        v_partner = self.estimate_v_partner()
        if is_last_turn:
            min_accept = 0
            partner_threshold = self.total / 2
        elif is_penultimate:
            min_accept = self.total / 2
            max_unit = max((v_partner[i] for i in range(self.n_types) if self.counts[i] > 0), default=0)
            partner_threshold = max_unit * 0.1 if max_unit > 0 else 0
        else:
            power = 10
            f = 1 - progress ** power
            my_share_frac = 0.5 + 0.5 * f
            min_accept = self.total * my_share_frac
            partner_threshold = self.total * (1 - my_share_frac)
        if o is not None:
            my_val = self.value(o)
            if my_val >= min_accept:
                return None
        if is_last_turn and o is not None:
            if my_val > 0:
                return None
            else:
                return [self.counts[i] if self.values[i] > 0 else 0 for i in range(self.n_types)]
        m = [0] * self.n_types
        current_util = 0.0
        for i in range(self.n_types):
            if self.values[i] == 0:
                m[i] = self.counts[i]
                current_util += m[i] * v_partner[i]
        remaining_needed = partner_threshold - current_util
        if remaining_needed > 0:
            candidates = [i for i in range(self.n_types) if self.values[i] > 0 and v_partner[i] > 0 and m[i] < self.counts[i]]
            if candidates:
                candidates.sort(key=lambda i: (-v_partner[i] / self.values[i], self.values[i]))
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
        if is_penultimate and current_util == 0 and candidates:
            i = candidates[0]
            m[i] += 1
        my_offer = [self.counts[i] - m[i] for i in range(self.n_types)]
        return my_offer