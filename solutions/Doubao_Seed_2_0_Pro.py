class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts.copy()
        self.values = values.copy()
        self.max_rounds = max_rounds
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.total_offers = 2 * max_rounds
        self.last_offerer = 1  # Total offers always even, so agent 1 makes last offer
        self.offers_made = 0
        self.opponent_offers = []
        # Sort items by our value descending to prioritize highest value items
        self.sorted_items = sorted(range(len(counts)), key=lambda x: (-values[x], counts[x]))

    def offer(self, o: list[int] | None) -> list[int] | None:
        # Edge case: all items are worthless to us
        if self.total_value == 0:
            return None if o is not None else [0] * len(self.counts)

        # Process incoming offer if present
        if o is not None:
            self.offers_made += 1
            self.opponent_offers.append(o)
            
            # Validate offer
            valid = True
            offer_val = 0
            for i in range(len(o)):
                count = int(o[i])
                if count < 0 or count > self.counts[i]:
                    valid = False
                    break
                offer_val += count * self.values[i]
            
            if valid:
                offers_left = self.total_offers - self.offers_made
                # No more offers left if we reject, accept anything >= 0
                if offers_left <= 0:
                    return None
                
                # Calculate minimum acceptable value
                progress = self.offers_made / max(1, self.total_offers - 1)
                if self.me == self.last_offerer:
                    # We have final say, hold out for higher value longer
                    min_accept = int(max(0.2 * self.total_value, self.total_value * (0.85 - 0.6 * progress)))
                else:
                    # Opponent has final say, be more flexible
                    min_accept = int(max(0.1 * self.total_value, self.total_value * (0.75 - 0.65 * progress)))
                
                if offer_val >= min_accept:
                    return None

        offers_left_after = self.total_offers - (self.offers_made + 1)
        # Final offer if we are last offerer, take all valuable items (opponent will accept)
        if offers_left_after <= 0 and self.me == self.last_offerer:
            my_offer = [0] * len(self.counts)
            for i in range(len(self.counts)):
                if self.values[i] > 0:
                    my_offer[i] = self.counts[i]
            return my_offer

        # Calculate desired value for our counter offer
        progress = self.offers_made / max(1, self.total_offers - 1)
        if self.me == self.last_offerer:
            desired_val = int(min(self.total_value, max(0.3 * self.total_value, self.total_value * (0.95 - 0.6 * progress))))
        else:
            desired_val = int(min(self.total_value, max(0.15 * self.total_value, self.total_value * (0.9 - 0.7 * progress))))

        # Build offer by taking highest value items first
        my_offer = [0] * len(self.counts)
        current_val = 0
        for idx in self.sorted_items:
            if current_val >= desired_val or self.values[idx] == 0:
                continue
            max_possible = self.counts[idx]
            # Don't ask for way more than opponent has offered before
            if self.opponent_offers:
                max_opponent = max(int(offer[idx]) for offer in self.opponent_offers)
                max_possible = min(max_possible, max_opponent + 1)
            take = min(max_possible, (desired_val - current_val) // self.values[idx])
            my_offer[idx] = take
            current_val += take * self.values[idx]

        # Top up if we haven't reached desired value yet
        if current_val < desired_val:
            for idx in self.sorted_items:
                if self.values[idx] == 0:
                    continue
                remaining = self.counts[idx] - my_offer[idx]
                if self.opponent_offers:
                    max_opponent = max(int(offer[idx]) for offer in self.opponent_offers)
                    remaining = min(remaining, max_opponent + 1 - my_offer[idx])
                if remaining > 0:
                    take = min(remaining, 1)
                    my_offer[idx] += take
                    current_val += take * self.values[idx]
                    if current_val >= desired_val:
                        break

        # Handle zero value items: keep initially, gradually give away as negotiations progress
        give_ratio = progress
        for i in range(len(self.counts)):
            if self.values[i] == 0:
                give = int(self.counts[i] * give_ratio)
                my_offer[i] = self.counts[i] - give

        # Ensure all values are valid integers within bounds
        for i in range(len(my_offer)):
            my_offer[i] = max(0, min(int(my_offer[i]), self.counts[i]))

        self.offers_made += 1
        return my_offer