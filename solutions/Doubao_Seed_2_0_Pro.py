class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts.copy()
        self.values = values.copy()
        self.max_rounds = max_rounds
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.total_offers = 2 * max_rounds
        self.last_offerer = 1  # Even total offers means agent 1 makes last offer
        self.offers_made = 0
        self.opponent_offers = []
        # Sort items by our value descending to prioritize highest value items first
        self.sorted_items = sorted(range(len(counts)), key=lambda x: (-values[x], -counts[x]))

    def offer(self, o: list[int] | None) -> list[int] | None:
        # Edge case: all items are worthless to us, accept immediately
        if self.total_value == 0:
            return None if o is not None else [0] * len(self.counts)

        # Process incoming opponent offer
        if o is not None:
            self.offers_made += 1
            self.opponent_offers.append(o)
            
            # Calculate offer value to us
            offer_val = sum(int(o[i]) * self.values[i] for i in range(len(o)))
            # Validate offer
            valid = all(0 <= int(o[i]) <= self.counts[i] for i in range(len(o)))
            
            if valid:
                offers_left = self.total_offers - self.offers_made
                # If no offers left after rejecting, accept any positive value
                if offers_left <= 0:
                    return None if offer_val >= 0 else []
                
                # Calculate minimum acceptable value (never below 40% unless last turn)
                progress = self.offers_made / max(1, self.total_offers - 1)
                if self.me == self.last_offerer:
                    # We have final say, hold out for higher value
                    min_accept = max(0.4 * self.total_value, self.total_value * (0.7 - 0.2 * progress))
                else:
                    # Opponent has final say, slightly more flexible
                    min_accept = max(0.35 * self.total_value, self.total_value * (0.65 - 0.25 * progress))
                
                # Accept if offer is good enough
                if offer_val >= min_accept or offer_val >= 0.5 * self.total_value:
                    return None

        offers_left_after = self.total_offers - (self.offers_made + 1)
        # Final offer: take all valuable items, opponent will accept rather than get 0
        if offers_left_after <= 0 and self.me == self.last_offerer:
            my_offer = [0] * len(self.counts)
            for i in range(len(self.counts)):
                if self.values[i] > 0:
                    my_offer[i] = self.counts[i]
            return my_offer

        # Calculate desired value for our counter offer
        progress = self.offers_made / max(1, self.total_offers - 1)
        if self.me == self.last_offerer:
            desired_val = min(self.total_value, max(0.5 * self.total_value, self.total_value * (0.95 - 0.4 * progress)))
        else:
            desired_val = min(self.total_value, max(0.45 * self.total_value, self.total_value * (0.9 - 0.45 * progress)))

        # Build offer by taking highest value items first
        my_offer = [0] * len(self.counts)
        current_val = 0
        for idx in self.sorted_items:
            if current_val >= desired_val or self.values[idx] == 0:
                continue
            max_possible = self.counts[idx]
            take = min(max_possible, (desired_val - current_val) // self.values[idx])
            my_offer[idx] = take
            current_val += take * self.values[idx]

        # Top up if we haven't reached desired value yet
        if current_val < desired_val:
            for idx in self.sorted_items:
                if self.values[idx] == 0:
                    continue
                remaining = self.counts[idx] - my_offer[idx]
                if remaining > 0:
                    take = min(remaining, 1)
                    my_offer[idx] += take
                    current_val += take * self.values[idx]
                    if current_val >= desired_val:
                        break

        # Concede low/zero value items first (bargaining chips)
        # Prioritize giving away items opponent seems to value (from their offers)
        if self.opponent_offers:
            # Calculate opponent preference: lower average offer = they value item more
            opponent_pref = []
            for i in range(len(self.counts)):
                avg_offer = sum(offer[i] for offer in self.opponent_offers) / len(self.opponent_offers)
                opponent_pref.append((-avg_offer, i))  # Negative for ascending sort
            opponent_pref.sort()
            # Give away items we don't value first, that opponent wants most
            for _, i in opponent_pref:
                if self.values[i] == 0:
                    give = int(self.counts[i] * min(progress + 0.2, 1.0))
                    my_offer[i] = self.counts[i] - give
        else:
            # First offer: keep all zero value items as bargaining chips
            for i in range(len(self.counts)):
                if self.values[i] == 0:
                    my_offer[i] = self.counts[i]

        # Ensure all values are valid integers within bounds
        for i in range(len(my_offer)):
            my_offer[i] = max(0, min(int(my_offer[i]), self.counts[i]))

        self.offers_made += 1
        return my_offer