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
        # Higher weight for recent opponent preferences
        self.opponent_kept_ema = [0.0] * len(counts)
        self.my_previous_offers = []
        # Sort our items by value per unit descending
        self.sorted_my_value = sorted(range(len(counts)), key=lambda x: (-values[x], -counts[x]))
        # Absolute minimum we accept (better than 0)
        self.abs_min_acceptable = max(0.35 * self.total_value, 1 if self.total_value > 0 else 0)
        # Initial desired value: 80% of total, not 90% to avoid being too aggressive
        self.min_desired = self.total_value * 0.8

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.offers_made += 1
        offers_left = self.total_offers - self.offers_made
        num_obj = len(self.counts)

        # Edge case: no value to us, accept immediately
        if self.total_value == 0:
            return None if o is not None else [0] * num_obj

        current_offer_val = 0
        if o is not None:
            # Validate offer
            valid = all(0 <= o[i] <= self.counts[i] for i in range(num_obj))
            if valid:
                current_offer_val = sum(o[i] * self.values[i] for i in range(num_obj))
                self.opponent_offers.append(o.copy())
                self.opponent_offer_values.append(current_offer_val)
                # Update EMA of opponent kept items (higher weight for new data)
                for i in range(num_obj):
                    kept = self.counts[i] - o[i]
                    self.opponent_kept_ema[i] = 0.5 * self.opponent_kept_ema[i] + 0.5 * kept
                # Update best offer received
                if current_offer_val > self.best_offer_val:
                    self.best_offer_val = current_offer_val

            # Final turn: accept anything > 0, no exceptions
            if offers_left <= 0:
                return None if current_offer_val > 0 else [0]*num_obj

            # Accept immediately if we get 48%+ (near fair split)
            if current_offer_val >= self.total_value * 0.48:
                return None

            # Accept if offers are decreasing, take best we can get before it gets worse
            if len(self.opponent_offer_values) >= 3 and \
               self.opponent_offer_values[-1] < self.opponent_offer_values[-2] < self.opponent_offer_values[-3]:
                if current_offer_val >= self.best_offer_val * 0.95:
                    return None

            # Accept if current offer is above our absolute minimum with <3 offers left
            if offers_left <= 2 and current_offer_val >= self.abs_min_acceptable:
                return None

            # Accept if offer is >= 95% of best received after half negotiation
            progress = self.offers_made / self.total_offers
            if progress >= 0.5 and current_offer_val >= self.best_offer_val * 0.95:
                return None

        # Calculate adjusted desired value for counteroffer
        progress = self.offers_made / self.total_offers
        opponent_conceding = len(self.opponent_offer_values) >= 2 and \
                             self.opponent_offer_values[-1] > self.opponent_offer_values[-2] + 0.02 * self.total_value
        offers_decreasing = len(self.opponent_offer_values) >=3 and \
                            self.opponent_offer_values[-1] < self.opponent_offer_values[-2] < self.opponent_offer_values[-3]
        opponent_stubborn = len(self.opponent_offers) >=3 and \
                            all(x == self.opponent_offers[-1] for x in self.opponent_offers[-3:])

        # Always concede slowly, even if opponent is stubborn (avoid deadlock)
        if opponent_stubborn:
            concede_speed = 0.1
        elif offers_decreasing:
            concede_speed = 0.15
        elif opponent_conceding:
            concede_speed = 0.3
        else:
            concede_speed = 0.25

        desired_val = self.total_value * (0.8 - concede_speed * progress)
        # Never go below absolute minimum, or 95% of best offer received
        desired_val = max(desired_val, self.abs_min_acceptable, self.best_offer_val * 0.95)
        # Never increase demands over time
        desired_val = min(desired_val, self.min_desired)
        self.min_desired = desired_val

        # Accept current offer if it's better than our desired counter value
        if o is not None and current_offer_val >= desired_val:
            return None

        # If we are last offerer, lower desired slightly to increase acceptance chance
        if offers_left <= 1 and self.me == self.last_offerer:
            desired_val = max(self.abs_min_acceptable, desired_val * 0.9)

        # Build our offer: take highest value items first to reach desired value
        my_offer = [0] * num_obj
        current_val = 0
        for idx in self.sorted_my_value:
            if current_val >= desired_val or self.values[idx] == 0:
                break
            take = min(self.counts[idx], (desired_val - current_val + self.values[idx] -1) // self.values[idx])
            my_offer[idx] = int(take)
            current_val += take * self.values[idx]

        # Top up if we are below desired value
        if current_val < desired_val:
            for idx in self.sorted_my_value:
                if self.values[idx] == 0: continue
                remaining = self.counts[idx] - my_offer[idx]
                if remaining <=0: continue
                add = min(remaining, (desired_val - current_val + self.values[idx] -1) // self.values[idx])
                my_offer[idx] += add
                current_val += add * self.values[idx]
                if current_val >= desired_val: break

        # Give opponent items they want most that cost us <5% of total value, to improve acceptance
        sorted_opponent_pref = sorted(range(num_obj), key=lambda x: (-self.opponent_kept_ema[x], -self.counts[x]))
        for idx in sorted_opponent_pref:
            if my_offer[idx] == 0: continue
            if current_val > desired_val * 0.98 and self.values[idx] <= 0.05 * self.total_value:
                give = 1
                my_offer[idx] -= give
                current_val -= give * self.values[idx]
                if current_val <= desired_val * 0.98:
                    break

        # Give all zero-value items to opponent (no cost to us)
        for i in range(num_obj):
            if self.values[i] == 0:
                my_offer[i] = 0

        # If we repeated same offer twice, make meaningful concession
        repeat_count = sum(1 for x in self.my_previous_offers if x == my_offer)
        if repeat_count >= 2:
            for idx in reversed(self.sorted_my_value):
                if my_offer[idx] > 0 and self.values[idx] <= 0.07 * self.total_value:
                    give = min(my_offer[idx], 2)
                    my_offer[idx] -= give
                    current_val -= give * self.values[idx]
                    self.min_desired = max(self.abs_min_acceptable, self.min_desired * 0.95)
                    break

        # Final validation of offer
        for i in range(num_obj):
            my_offer[i] = max(0, min(int(my_offer[i]), self.counts[i]))
        self.my_previous_offers.append(my_offer.copy())

        return my_offer