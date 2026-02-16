class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts.copy()
        self.values = values.copy()
        self.max_rounds = max_rounds
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.total_offers = 2 * max_rounds
        self.last_offerer = 1 if (self.total_offers % 2 == 0) else 0
        self.offers_made = 0
        self.opponent_offers = []
        self.opponent_offer_values = []
        self.best_offer_val = 0
        self.opponent_kept = [0] * len(counts)
        self.my_previous_offers = []
        self.sorted_my_value = sorted(range(len(counts)), key=lambda x: (-values[x], counts[x]))
        self.abs_min_acceptable = max(0.2 * self.total_value, 1 if self.total_value > 0 else 0)

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.offers_made += 1
        offers_left = self.total_offers - self.offers_made

        if self.total_value == 0:
            return None if o is not None else [0] * len(self.counts)

        current_offer_val = 0
        if o is not None:
            valid = all(0 <= int(o[i]) <= self.counts[i] for i in range(len(o)))
            if valid:
                current_offer_val = sum(int(o[i]) * self.values[i] for i in range(len(o)))
                self.opponent_offers.append(o)
                self.opponent_offer_values.append(current_offer_val)
                for i in range(len(o)):
                    self.opponent_kept[i] += (self.counts[i] - o[i])
                if current_offer_val > self.best_offer_val:
                    self.best_offer_val = current_offer_val

                # Accept immediately if >= 50%
                if current_offer_val >= self.total_value * 0.5:
                    return None

                # Late game acceptance rules
                if offers_left <= 0:
                    return None if current_offer_val > 0 else [0]*len(self.counts)
                if offers_left <= 2:
                    if current_offer_val >= self.abs_min_acceptable:
                        return None
                if offers_left <= 4:
                    if current_offer_val >= max(self.abs_min_acceptable, 0.3 * self.total_value):
                        return None

                # Check opponent trend
                offers_decreasing = False
                if len(self.opponent_offer_values) >= 3:
                    if self.opponent_offer_values[-1] < self.opponent_offer_values[-2] < self.opponent_offer_values[-3]:
                        offers_decreasing = True
                opponent_stubborn = len(self.opponent_offers) >= 3 and all(x == self.opponent_offers[-1] for x in self.opponent_offers[-3:])

                # Adjust accept threshold based on opponent behavior
                progress = self.offers_made / max(1, self.total_offers - 1)
                min_accept_base = 0.75 - 0.4 * progress
                if offers_decreasing:
                    min_accept_base -= 0.1
                if opponent_stubborn:
                    min_accept_base -= 0.08
                min_accept = max(self.abs_min_acceptable, self.total_value * min_accept_base)
                if current_offer_val >= min_accept:
                    return None

        # Opponent behavior analysis for counter offer
        opponent_conceding = False
        offers_decreasing = False
        opponent_stubborn = False
        if len(self.opponent_offer_values) >= 2:
            if self.opponent_offer_values[-1] > self.opponent_offer_values[-2] + 0.02 * self.total_value:
                opponent_conceding = True
        if len(self.opponent_offer_values) >= 3:
            if self.opponent_offer_values[-1] < self.opponent_offer_values[-2] < self.opponent_offer_values[-3]:
                offers_decreasing = True
            if all(x == self.opponent_offers[-1] for x in self.opponent_offers[-3:]):
                opponent_stubborn = True

        # Calculate desired value for counter
        progress = self.offers_made / max(1, self.total_offers - 1)
        concede_speed = 0.3 if opponent_conceding else 0.6 if opponent_stubborn else 0.5 if offers_decreasing else 0.4
        desired_val = min(self.total_value, max(self.abs_min_acceptable + 0.05 * self.total_value,
                                                self.total_value * (0.95 - concede_speed * progress)))
        # Adjust if we are making final offer
        if offers_left <= 0 and self.me == self.last_offerer:
            desired_val = max(self.abs_min_acceptable, desired_val * 0.85)

        # Sort opponent preferences: items they keep most first (they value these)
        sorted_opponent_value = sorted(range(len(self.counts)), key=lambda x: (-self.opponent_kept[x], self.values[x]))

        # Build our offer: prioritize high value items for us first
        my_offer = [0] * len(self.counts)
        current_val = 0
        for idx in self.sorted_my_value:
            if current_val >= desired_val or self.values[idx] == 0:
                break
            take = min(self.counts[idx], (desired_val - current_val) // self.values[idx])
            my_offer[idx] = take
            current_val += take * self.values[idx]

        # Top up if below desired value
        if current_val < desired_val:
            for idx in self.sorted_my_value:
                if self.values[idx] == 0:
                    continue
                remaining = self.counts[idx] - my_offer[idx]
                if remaining <= 0:
                    continue
                add = min(remaining, (desired_val - current_val) // self.values[idx])
                my_offer[idx] += add
                current_val += add * self.values[idx]

        # Give opponent items they want that are low value to us to improve acceptance chance
        for idx in sorted_opponent_value:
            if self.values[idx] == 0 or my_offer[idx] == 0:
                continue
            if current_val > desired_val * 1.05 and self.values[idx] <= 0.08 * self.total_value:
                give = min(my_offer[idx], 2)
                my_offer[idx] -= give
                current_val -= give * self.values[idx]
                if current_val <= desired_val:
                    break

        # Avoid repeating offers more than twice, concede more if stuck
        repeat_count = sum(1 for x in self.my_previous_offers if x == my_offer)
        if repeat_count >= 2:
            for idx in reversed(self.sorted_my_value):
                if my_offer[idx] > 0 and self.values[idx] <= 0.12 * self.total_value:
                    give = min(my_offer[idx], 2 if repeat_count >=3 else 1)
                    my_offer[idx] -= give
                    current_val -= give * self.values[idx]
                    break

        # Validate offer
        for i in range(len(my_offer)):
            my_offer[i] = max(0, min(int(my_offer[i]), self.counts[i]))
        self.my_previous_offers.append(my_offer.copy())

        # If our counter is worse than current offer, accept current offer
        if o is not None and current_val < current_offer_val and current_offer_val >= self.abs_min_acceptable:
            return None

        return my_offer