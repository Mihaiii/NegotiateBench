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
        # Lower minimum acceptable to avoid no-deal scenarios
        self.abs_min_acceptable = max(0.1 * self.total_value, 1 if self.total_value > 0 else 0)

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.offers_made += 1
        offers_left = self.total_offers - self.offers_made

        # Edge case: nothing has value to us, accept immediately
        if self.total_value == 0:
            return None if o is not None else [0] * len(self.counts)

        current_offer_val = 0
        if o is not None:
            # Validate incoming offer
            valid = all(0 <= o[i] <= self.counts[i] for i in range(len(o)))
            if valid:
                current_offer_val = sum(o[i] * self.values[i] for i in range(len(o)))
                self.opponent_offers.append(o.copy())
                self.opponent_offer_values.append(current_offer_val)
                # Track what opponent keeps to learn their preferences
                for i in range(len(o)):
                    self.opponent_kept[i] += (self.counts[i] - o[i])
                if current_offer_val > self.best_offer_val:
                    self.best_offer_val = current_offer_val

                # Accept immediately if we get half or more
                if current_offer_val >= self.total_value * 0.5:
                    return None

                # Critical late game rules to avoid no-deal
                if offers_left <= 0:
                    return None  # Any offer is better than zero
                if offers_left <= 2:
                    if current_offer_val >= max(1, 0.05 * self.total_value):
                        return None

                # Analyze opponent behavior
                offers_decreasing = False
                opponent_conceding = False
                opponent_stubborn = False
                if len(self.opponent_offer_values) >= 3:
                    if self.opponent_offer_values[-1] < self.opponent_offer_values[-2] < self.opponent_offer_values[-3]:
                        offers_decreasing = True
                    if all(x == self.opponent_offers[-1] for x in self.opponent_offers[-3:]):
                        opponent_stubborn = True
                if len(self.opponent_offer_values) >= 2:
                    if self.opponent_offer_values[-1] > self.opponent_offer_values[-2] + 0.02 * self.total_value:
                        opponent_conceding = True

                # Calculate dynamic acceptance threshold that drops faster over time
                progress = self.offers_made / self.total_offers
                min_accept_base = 0.8 - 0.7 * progress  # Starts at 80%, drops to 10% at end
                if offers_decreasing:
                    min_accept_base -= 0.15  # Accept lower if offers are getting worse
                if opponent_stubborn:
                    min_accept_base -= 0.1  # Accept lower if opponent won't move
                if opponent_conceding:
                    min_accept_base += 0.05  # Hold out for more if they are improving offers
                
                # Accept if current offer meets threshold, or is close to best we've had late game
                min_accept = max(self.abs_min_acceptable, self.total_value * min_accept_base)
                if current_offer_val >= min_accept:
                    return None
                if progress >= 0.7 and current_offer_val >= self.best_offer_val * 0.95:
                    return None

        # Analyze opponent behavior for counter offer strategy
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

        # Calculate desired value for our counter offer
        progress = self.offers_made / self.total_offers
        # Concede faster if opponent is stubborn or offers are decreasing
        concede_speed = 0.8 if opponent_stubborn else 0.7 if offers_decreasing else 0.3 if opponent_conceding else 0.5
        desired_val = min(self.total_value, max(self.abs_min_acceptable,
                                                self.total_value * (0.95 - concede_speed * progress)))
        # Reduce desired value significantly if this is our final offer (opponent can't counter)
        if offers_left <= 1 and self.me == self.last_offerer:
            desired_val = max(self.abs_min_acceptable, desired_val * 0.7)

        # Accept current offer if our counter would be worse for us
        if o is not None and desired_val < current_offer_val and current_offer_val >= self.abs_min_acceptable:
            return None
        # Accept if best offer we ever got is better than our desired counter
        if self.best_offer_val > desired_val and progress >= 0.6:
            return None if (o is not None and current_offer_val >= self.best_offer_val * 0.9) else ...

        # Sort opponent preferences: items they keep most are highest value to them
        sorted_opponent_value = sorted(range(len(self.counts)), key=lambda x: (-self.opponent_kept[x], -self.counts[x]))

        # Build our offer: take highest value items for us first
        my_offer = [0] * len(self.counts)
        current_val = 0
        for idx in self.sorted_my_value:
            if current_val >= desired_val or self.values[idx] == 0:
                break
            take = min(self.counts[idx], (desired_val - current_val) // self.values[idx])
            my_offer[idx] = take
            current_val += take * self.values[idx]

        # Top up if we are below desired value
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

        # Give opponent items they value that are low cost to us to improve acceptance chance
        for idx in sorted_opponent_value:
            if self.values[idx] == 0 or my_offer[idx] == 0:
                continue
            if current_val > desired_val * 0.95 and self.values[idx] <= 0.1 * self.total_value:
                give = min(my_offer[idx], 2)
                my_offer[idx] -= give
                current_val -= give * self.values[idx]
                if current_val <= desired_val * 0.9:
                    break

        # Explicitly give all zero-value items to opponent (no cost to us)
        for i in range(len(my_offer)):
            if self.values[i] == 0:
                my_offer[i] = 0

        # Avoid repeating same offer more than twice, concede more if stuck
        repeat_count = sum(1 for x in self.my_previous_offers if x == my_offer)
        if repeat_count >= 2:
            for idx in reversed(self.sorted_my_value):
                if my_offer[idx] > 0 and self.values[idx] <= 0.12 * self.total_value:
                    give = min(my_offer[idx], 3 if repeat_count >= 3 else 1)
                    my_offer[idx] -= give
                    current_val -= give * self.values[idx]
                    break

        # Validate offer is within bounds
        for i in range(len(my_offer)):
            my_offer[i] = max(0, min(my_offer[i], self.counts[i]))
        self.my_previous_offers.append(my_offer.copy())

        return my_offer