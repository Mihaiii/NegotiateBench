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
        # Categorize items for concession priority
        self.core_threshold = 0.1 * self.total_value if self.total_value > 0 else 0
        self.bargain_threshold = 0.02 * self.total_value if self.total_value > 0 else 0

    def offer(self, o: list[int] | None) -> list[int] | None:
        # Increment turn counter once per call (fixed critical bug from original code)
        self.offers_made += 1
        offers_left = self.total_offers - self.offers_made

        # Edge case: all items worthless to us, accept immediately or take nothing
        if self.total_value == 0:
            return None if o is not None else [0] * len(self.counts)

        # Process incoming opponent offer
        current_offer_val = 0
        if o is not None:
            # Validate offer first
            valid = all(0 <= int(o[i]) <= self.counts[i] for i in range(len(o)))
            if valid:
                current_offer_val = sum(int(o[i]) * self.values[i] for i in range(len(o)))
                self.opponent_offers.append(o)
                # Update best received offer
                if current_offer_val > self.best_offer_val:
                    self.best_offer_val = current_offer_val

                # Rule 1: Accept any offer >= 50% of our total value immediately
                if current_offer_val >= self.total_value * 0.5:
                    return None

                # Rule 2: Near end of negotiation, avoid zero payout
                if offers_left <= 0:
                    return None if current_offer_val > 0 else None
                if offers_left <= 1:
                    return None if current_offer_val >= 0.3 * self.total_value else None
                if offers_left <= 3:
                    if current_offer_val >= 0.4 * self.total_value:
                        return None

                # Calculate dynamic accept threshold
                progress = self.offers_made / max(1, self.total_offers - 1)
                if self.me == self.last_offerer:
                    min_accept = max(0.35 * self.total_value, self.total_value * (0.75 - 0.3 * progress))
                else:
                    min_accept = max(0.3 * self.total_value, self.total_value * (0.7 - 0.35 * progress))
                
                if current_offer_val >= min_accept:
                    return None

        # Calculate opponent concession rate to decide how much we concede
        opponent_concession = 0
        if len(self.opponent_offers) >= 3:
            prev3_val = sum(self.opponent_offers[-3][i] * self.values[i] for i in range(len(self.values)))
            opponent_concession = current_offer_val - prev3_val
        # Only concede if opponent is conceding too, or we are near the end
        concede_multiplier = 1.0 if (opponent_concession >= 0.05 * self.total_value or offers_left < 4) else 0.2

        # Calculate desired value for our counter offer
        progress = self.offers_made / max(1, self.total_offers - 1)
        if self.me == self.last_offerer:
            desired_val = min(self.total_value, max(0.4 * self.total_value, self.total_value * (0.95 - 0.45 * progress * concede_multiplier)))
        else:
            desired_val = min(self.total_value, max(0.35 * self.total_value, self.total_value * (0.9 - 0.5 * progress * concede_multiplier)))
        
        # Final offer adjustment: leave opponent enough value to accept
        if offers_left <= 0:
            desired_val = min(desired_val, 0.85 * self.total_value)

        # Build base offer: take highest value items first
        my_offer = [0] * len(self.counts)
        current_val = 0
        # First take all core high value items
        for idx in self.sorted_items:
            if self.values[idx] >= self.core_threshold:
                take = self.counts[idx]
                my_offer[idx] = take
                current_val += take * self.values[idx]
        # Then add mid value items until we reach desired value
        for idx in self.sorted_items:
            if current_val >= desired_val:
                break
            if self.bargain_threshold < self.values[idx] < self.core_threshold:
                take = min(self.counts[idx], (desired_val - current_val) // self.values[idx]) if self.values[idx] > 0 else 0
                my_offer[idx] += take
                current_val += take * self.values[idx]
        # Add any bargaining chips we don't need to give away yet
        if progress < 0.7:
            for idx in self.sorted_items:
                if self.values[idx] <= self.bargain_threshold:
                    my_offer[idx] = self.counts[idx]

        # Concede items: give away bargaining chips first, then mid value, never core unless forced
        if progress >= 0.3 and len(self.opponent_offers) > 0:
            # Calculate opponent preference (lower offer to us = they want it more)
            opponent_pref = []
            for i in range(len(self.counts)):
                avg_offer = sum(offer[i] for offer in self.opponent_offers) / len(self.opponent_offers)
                opponent_pref.append((avg_offer, i))
            opponent_pref.sort()  # Items they want most first

            concession_rate = min(progress * concede_multiplier + 0.2, 1.0)
            for avg_offer, i in opponent_pref:
                if current_val <= desired_val * 0.9:
                    break
                if self.values[i] <= self.bargain_threshold:
                    # Give away all low/zero value items opponent wants first
                    give = min(my_offer[i], int(self.counts[i] * concession_rate))
                    my_offer[i] -= give
                    current_val -= give * self.values[i]
                elif self.values[i] < self.core_threshold and progress >= 0.7:
                    # Give mid value items only late in negotiation
                    give = min(my_offer[i], int(my_offer[i] * concession_rate * 0.5))
                    my_offer[i] -= give
                    current_val -= give * self.values[i]

        # Ensure all values are valid
        for i in range(len(my_offer)):
            my_offer[i] = max(0, min(int(my_offer[i]), self.counts[i]))

        # If our counter offer is worse than the best offer we received, accept the best one instead
        if o is not None and current_val < self.best_offer_val:
            return None

        return my_offer