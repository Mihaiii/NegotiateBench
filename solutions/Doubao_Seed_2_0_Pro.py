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
        self.best_offer_val = 0
        # Track opponent preferences based on items they keep
        self.opponent_kept = [0] * len(counts)
        self.my_previous_offers = []
        # Sort items by our value descending (priority to keep high value items)
        self.sorted_my_value = sorted(range(len(counts)), key=lambda x: (-values[x], counts[x]))
        # Minimum acceptable value (never go below this except last turn)
        self.min_acceptable = max(0.3 * self.total_value, 1 if self.total_value > 0 else 0)

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.offers_made += 1
        offers_left = self.total_offers - self.offers_made

        # Edge case: all items worthless to us, accept immediately
        if self.total_value == 0:
            return None if o is not None else [0] * len(self.counts)

        # Process incoming opponent offer
        current_offer_val = 0
        if o is not None:
            # Validate offer
            valid = all(0 <= int(o[i]) <= self.counts[i] for i in range(len(o)))
            if valid:
                current_offer_val = sum(int(o[i]) * self.values[i] for i in range(len(o)))
                self.opponent_offers.append(o)
                # Update opponent kept items for preference inference
                for i in range(len(o)):
                    self.opponent_kept[i] += (self.counts[i] - o[i])
                # Update best received offer
                if current_offer_val > self.best_offer_val:
                    self.best_offer_val = current_offer_val

                # Rule 1: Accept any offer >= 50% immediately
                if current_offer_val >= self.total_value * 0.5:
                    return None

                # Rule 2: Last turn: accept if offer > 0, else reject
                if offers_left <= 0:
                    return None if current_offer_val > 0 else [0]*len(self.counts)

                # Rule 3: Near end accept thresholds
                if offers_left <= 1:
                    if current_offer_val >= max(self.min_acceptable, 0.35 * self.total_value):
                        return None
                if offers_left <= 3:
                    if current_offer_val >= max(self.min_acceptable, 0.4 * self.total_value):
                        return None

                # Dynamic accept threshold based on progress
                progress = self.offers_made / max(1, self.total_offers - 1)
                min_accept = max(self.min_acceptable, self.total_value * (0.75 - 0.3 * progress))
                if current_offer_val >= min_accept:
                    return None

        # Calculate opponent behavior
        opponent_conceding = False
        if len(self.opponent_offers) >= 2:
            prev_val = sum(self.opponent_offers[-2][i] * self.values[i] for i in range(len(self.values)))
            if current_offer_val > prev_val + 0.02 * self.total_value:
                opponent_conceding = True
        opponent_stubborn = len(self.opponent_offers) >= 3 and self.opponent_offers[-1] == self.opponent_offers[-2] == self.opponent_offers[-3]

        # Calculate desired value for our counter offer
        progress = self.offers_made / max(1, self.total_offers - 1)
        concede_speed = 0.3 if opponent_conceding else (0.45 if opponent_stubborn else 0.35)
        desired_val = min(self.total_value, max(self.min_acceptable + 0.05 * self.total_value,
                                                self.total_value * (0.95 - concede_speed * progress)))
        # If we are last offerer, adjust to make offer more acceptable
        if offers_left <= 0 and self.me == self.last_offerer:
            desired_val = max(self.min_acceptable, desired_val * 0.9)

        # Get sorted opponent preferences (items they want most first, so we give those first)
        sorted_opponent_value = sorted(range(len(self.counts)), key=lambda x: (-self.opponent_kept[x], -self.counts[x]))

        # Build our offer: keep high value items first, give opponent desired items we don't care about
        my_offer = [0] * len(self.counts)
        current_val = 0
        # Take maximum of high value items first
        for idx in self.sorted_my_value:
            if current_val >= desired_val or self.values[idx] == 0:
                break
            take = min(self.counts[idx], (desired_val - current_val) // self.values[idx])
            my_offer[idx] = take
            current_val += take * self.values[idx]

        # If below desired value, take more of our valued items
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

        # Give opponent items they value (that we don't need) to make offer more attractive
        for idx in sorted_opponent_value:
            if self.values[idx] == 0 or my_offer[idx] == 0:
                continue
            # If item is low value to us and opponent wants it, give 1 to improve offer attractiveness
            if current_val > desired_val * 1.05 and self.values[idx] <= 0.05 * self.total_value:
                give = min(my_offer[idx], 1)
                my_offer[idx] -= give
                current_val -= give * self.values[idx]

        # Ensure we don't repeat same offer more than twice
        if my_offer in self.my_previous_offers and len(self.my_previous_offers)>=2:
            # Concede small amount by giving 1 low value item to opponent
            for idx in reversed(self.sorted_my_value):
                if my_offer[idx] > 0 and self.values[idx] <= 0.1 * self.total_value:
                    my_offer[idx] -= 1
                    current_val -= self.values[idx]
                    break

        # Validate offer
        for i in range(len(my_offer)):
            my_offer[i] = max(0, min(int(my_offer[i]), self.counts[i]))
        self.my_previous_offers.append(my_offer.copy())

        # If our counter is worse than best received offer, accept the best offer
        if o is not None and current_val < self.best_offer_val and self.best_offer_val >= self.min_acceptable:
            return None

        return my_offer