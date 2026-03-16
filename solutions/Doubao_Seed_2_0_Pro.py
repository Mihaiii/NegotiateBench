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
        # EMA of items opponent keeps, higher weight for recent offers
        self.opponent_kept_ema = [0.0] * len(counts)
        self.my_previous_offers = []
        # Sort our items by value descending, then count descending
        self.sorted_my_value = sorted(range(len(counts)), key=lambda x: (-values[x], -counts[x]))
        # Hard minimum we accept except final turn: 40% of total value
        self.abs_min_acceptable = max(0.4 * self.total_value, 1 if self.total_value > 0 else 0)
        # Track minimum desired value to avoid increasing demands
        self.min_desired = self.total_value * 0.9

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.offers_made += 1
        offers_left = self.total_offers - self.offers_made
        num_obj = len(self.counts)

        # Edge case: nothing has value to us, accept immediately
        if self.total_value == 0:
            return None if o is not None else [0] * num_obj

        current_offer_val = 0
        if o is not None:
            # Validate incoming offer first
            valid = all(0 <= o[i] <= self.counts[i] for i in range(num_obj))
            if valid:
                current_offer_val = sum(o[i] * self.values[i] for i in range(num_obj))
                self.opponent_offers.append(o.copy())
                self.opponent_offer_values.append(current_offer_val)
                # Update EMA of opponent kept items
                for i in range(num_obj):
                    kept = self.counts[i] - o[i]
                    self.opponent_kept_ema[i] = 0.6 * self.opponent_kept_ema[i] + 0.4 * kept
                # Update best offer we've ever received
                if current_offer_val > self.best_offer_val:
                    self.best_offer_val = current_offer_val

                # Immediate accept if we get near fair split (48%+)
                if current_offer_val >= self.total_value * 0.48:
                    return None

                # Final turn: accept any offer better than zero
                if offers_left <= 0:
                    return None if current_offer_val > 0 else [0]*num_obj

                # Final 2 turns: accept anything above our hard minimum
                if offers_left <= 2:
                    if current_offer_val >= self.abs_min_acceptable:
                        return None

                # Analyze opponent behavior
                offers_decreasing = False
                opponent_conceding = False
                opponent_stubborn = False
                opponent_not_conceding = False
                if len(self.opponent_offer_values) >= 3:
                    if self.opponent_offer_values[-1] < self.opponent_offer_values[-2] < self.opponent_offer_values[-3]:
                        offers_decreasing = True
                    if all(x == self.opponent_offers[-1] for x in self.opponent_offers[-3:]):
                        opponent_stubborn = True
                    if self.opponent_offer_values[-1] <= self.opponent_offer_values[-3]:
                        opponent_not_conceding = True
                if len(self.opponent_offer_values) >= 2:
                    if self.opponent_offer_values[-1] > self.opponent_offer_values[-2] + 0.02 * self.total_value:
                        opponent_conceding = True

                # Accept if offer is near best we've ever got, past halfway point
                progress = self.offers_made / self.total_offers
                if progress >= 0.5 and current_offer_val >= self.best_offer_val * 0.95:
                    return None

                # Dynamic acceptance threshold, starts at 90% ends at 45%
                min_accept_base = 0.9 - 0.45 * progress
                if offers_decreasing:
                    min_accept_base += 0.1  # Hold firm if offers are getting worse
                if opponent_stubborn:
                    min_accept_base += 0.05  # Don't reward stubbornness
                if opponent_conceding:
                    min_accept_base += 0.1  # Hold out for more if they're improving
                
                min_accept = max(self.abs_min_acceptable, self.total_value * min_accept_base)
                if current_offer_val >= min_accept:
                    return None

        # Re-analyze opponent behavior for counter offer strategy
        opponent_conceding = False
        offers_decreasing = False
        opponent_stubborn = False
        opponent_not_conceding = False
        if len(self.opponent_offer_values) >= 2:
            if self.opponent_offer_values[-1] > self.opponent_offer_values[-2] + 0.02 * self.total_value:
                opponent_conceding = True
        if len(self.opponent_offer_values) >= 3:
            if self.opponent_offer_values[-1] < self.opponent_offer_values[-2] < self.opponent_offer_values[-3]:
                offers_decreasing = True
            if all(x == self.opponent_offers[-1] for x in self.opponent_offers[-3:]):
                opponent_stubborn = True
            if self.opponent_offer_values[-1] <= self.opponent_offer_values[-3]:
                opponent_not_conceding = True

        # Calculate desired value for our counter, never increase demands
        progress = self.offers_made / self.total_offers
        # Concede speed: zero if opponent is stubborn/not conceding, slower if offers are decreasing
        if opponent_stubborn or opponent_not_conceding:
            concede_speed = 0.0
        elif offers_decreasing:
            concede_speed = 0.2
        elif opponent_conceding:
            concede_speed = 0.3
        else:
            concede_speed = 0.4

        desired_val = self.total_value * (0.9 - concede_speed * progress)
        # Never go below hard minimum, or below 95% of best offer received
        desired_val = max(desired_val, self.abs_min_acceptable, self.best_offer_val * 0.95)
        # Ensure desired value never increases over time
        desired_val = min(desired_val, self.min_desired)
        self.min_desired = desired_val

        # If this is our final offer, no need to concede more than necessary
        if offers_left <= 1 and self.me == self.last_offerer:
            desired_val = max(self.abs_min_acceptable, desired_val * 0.95)

        # Accept if current offer is better than our desired counter value
        if o is not None and current_offer_val >= desired_val:
            return None

        # Sort opponent preferences by EMA of kept items (highest first)
        sorted_opponent_value = sorted(range(num_obj), key=lambda x: (-self.opponent_kept_ema[x], -self.counts[x]))

        # Build our offer: take highest value items for us first to reach desired value
        my_offer = [0] * num_obj
        current_val = 0
        for idx in self.sorted_my_value:
            if current_val >= desired_val or self.values[idx] == 0:
                break
            take = min(self.counts[idx], (desired_val - current_val + self.values[idx] - 1) // self.values[idx])
            my_offer[idx] = int(take)
            current_val += take * self.values[idx]

        # Top up if we are still below desired value
        if current_val < desired_val:
            for idx in self.sorted_my_value:
                if self.values[idx] == 0:
                    continue
                remaining = self.counts[idx] - my_offer[idx]
                if remaining <= 0:
                    continue
                add = min(remaining, (desired_val - current_val + self.values[idx] - 1) // self.values[idx])
                my_offer[idx] += int(add)
                current_val += add * self.values[idx]
                if current_val >= desired_val:
                    break

        # Give opponent items they value most that cost us almost nothing to improve acceptance chance
        for idx in sorted_opponent_value:
            if self.values[idx] == 0 or my_offer[idx] == 0:
                continue
            if current_val > desired_val * 1.02 and self.values[idx] <= 0.03 * self.total_value:
                give = 1
                my_offer[idx] -= give
                current_val -= give * self.values[idx]
                if current_val <= desired_val:
                    break

        # Give all zero-value items to opponent (no cost to us)
        for i in range(num_obj):
            if self.values[i] == 0:
                my_offer[i] = 0

        # Avoid repeating same offer more than twice, concede minimal amount if stuck
        repeat_count = sum(1 for x in self.my_previous_offers if x == my_offer)
        if repeat_count >= 2:
            for idx in reversed(self.sorted_my_value):
                if my_offer[idx] > 0 and self.values[idx] <= 0.05 * self.total_value:
                    give = 1
                    my_offer[idx] -= give
                    current_val -= give * self.values[idx]
                    break

        # Final validation: ensure all counts are integers within bounds
        for i in range(num_obj):
            my_offer[i] = max(0, min(int(my_offer[i]), self.counts[i]))
        self.my_previous_offers.append(my_offer.copy())

        return my_offer