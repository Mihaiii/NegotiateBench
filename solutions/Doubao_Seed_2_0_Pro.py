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
        # Sort items by value per unit descending (keep high value first)
        self.sorted_items = sorted(range(len(counts)), key=lambda x: (-values[x], counts[x]))
        # Minimum acceptable value (never go below this)
        self.min_acceptable = max(0.2 * self.total_value, 1 if self.total_value > 0 else 0)

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
                # Update best received offer
                if current_offer_val > self.best_offer_val:
                    self.best_offer_val = current_offer_val

                # Rule 1: Accept any offer >= 50% immediately
                if current_offer_val >= self.total_value * 0.5:
                    return None

                # Rule 2: Last turn, accept any positive offer (0 is same as no deal)
                if offers_left <= 0:
                    return None if current_offer_val > 0 else None

                # Rule 3: Near end, accept lower but reasonable offers
                if offers_left <= 1:
                    if current_offer_val >= max(self.min_acceptable, 0.3 * self.total_value):
                        return None
                if offers_left <= 3:
                    if current_offer_val >= max(self.min_acceptable, 0.35 * self.total_value):
                        return None

                # Dynamic accept threshold based on negotiation progress
                progress = self.offers_made / max(1, self.total_offers - 1)
                min_accept = max(self.min_acceptable, self.total_value * (0.7 - 0.35 * progress))
                if current_offer_val >= min_accept:
                    return None

        # Calculate opponent concession rate
        opponent_conceding = False
        if len(self.opponent_offers) >= 2:
            prev_val = sum(self.opponent_offers[-2][i] * self.values[i] for i in range(len(self.values)))
            if current_offer_val > prev_val + 0.02 * self.total_value:
                opponent_conceding = True
        # If opponent repeats same offer 3x, they are at their limit
        opponent_stubborn = False
        if len(self.opponent_offers) >= 3:
            if self.opponent_offers[-1] == self.opponent_offers[-2] == self.opponent_offers[-3]:
                opponent_stubborn = True

        # Calculate desired value for our counter offer
        progress = self.offers_made / max(1, self.total_offers - 1)
        concede_rate = 0.45 if opponent_conceding else (0.6 if opponent_stubborn else 0.3)
        desired_val = min(self.total_value, max(self.min_acceptable + 0.05 * self.total_value, 
                                                self.total_value * (0.92 - concede_rate * progress)))
        # Final offer adjustment if we are last to offer
        if offers_left <= 0 and self.me == self.last_offerer:
            desired_val = min(desired_val, 0.8 * self.total_value)

        # Build our offer: first give all zero value items to opponent (no cost to us!)
        my_offer = [0] * len(self.counts)
        current_val = 0
        # Take all high value items first
        for idx in self.sorted_items:
            if current_val >= desired_val:
                break
            if self.values[idx] == 0:
                continue  # Give all zero value items to opponent
            take = min(self.counts[idx], (desired_val - current_val) // self.values[idx])
            my_offer[idx] = take
            current_val += take * self.values[idx]

        # If we are below desired value, add any remaining items we value
        if current_val < desired_val:
            for idx in self.sorted_items:
                if self.values[idx] == 0:
                    continue
                remaining = self.counts[idx] - my_offer[idx]
                if remaining <= 0:
                    continue
                add = min(remaining, (desired_val - current_val) // self.values[idx])
                my_offer[idx] += add
                current_val += add * self.values[idx]

        # If opponent is stubborn, concede extra low-value items to get deal done
        if opponent_stubborn and progress > 0.6:
            for idx in self.sorted_items:
                if current_val <= max(self.min_acceptable, desired_val * 0.9):
                    break
                if self.values[idx] <= 0.05 * self.total_value and my_offer[idx] > 0:
                    give = min(my_offer[idx], 1)
                    my_offer[idx] -= give
                    current_val -= give * self.values[idx]

        # Ensure all values are valid
        for i in range(len(my_offer)):
            my_offer[i] = max(0, min(int(my_offer[i]), self.counts[i]))

        # If our counter offer is worse than the best offer we received, accept the best one
        if o is not None and current_val < self.best_offer_val and self.best_offer_val >= self.min_acceptable:
            return None

        return my_offer