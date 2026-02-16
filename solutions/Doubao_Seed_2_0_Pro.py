class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts.copy()
        self.values = values.copy()
        self.max_rounds = max_rounds
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.total_offers = 2 * max_rounds
        self.last_offerer = 0 if (2 * max_rounds) % 2 == 1 else 1
        self.offers_made = 0
        self.opponent_offers = []
        # Sort items by our value per unit descending
        self.sorted_items = sorted(range(len(counts)), key=lambda x: (-values[x], counts[x]))

    def offer(self, o: list[int] | None) -> list[int] | None:
        # Accept immediately if all items are worthless to us
        if self.total_value == 0:
            return None if o is not None else [0]*len(self.counts)

        # Process incoming opponent offer
        if o is not None:
            self.offers_made += 1
            self.opponent_offers.append(o)
            
            # Validate offer
            valid = all(0 <= int(o[i]) <= self.counts[i] for i in range(len(o)))
            if not valid:
                pass  # Ignore invalid offers
            else:
                offer_val = sum(int(o[i]) * self.values[i] for i in range(len(o)))
                offers_left = self.total_offers - self.offers_made
                
                # Rule 1: Accept any offer >= half our total value immediately
                if offer_val >= self.total_value * 0.5:
                    return None
                
                # Rule 2: If almost no offers left, accept any positive value to avoid 0
                if offers_left <= 1:
                    return None if offer_val > 0 else []
                
                # Rule 3: Calculate dynamic minimum accept threshold
                progress = self.offers_made / max(1, self.total_offers - 1)
                if self.me == self.last_offerer:
                    min_accept = max(0.3 * self.total_value, self.total_value * (0.7 - 0.3 * progress))
                else:
                    min_accept = max(0.25 * self.total_value, self.total_value * (0.65 - 0.35 * progress))
                
                # Lower threshold when few offers left
                if offers_left <= 3:
                    min_accept = max(1, min_accept * 0.7)
                
                if offer_val >= min_accept:
                    return None

        offers_left_after = self.total_offers - (self.offers_made + 1)
        progress = self.offers_made / max(1, self.total_offers - 1)

        # Calculate desired value for our counter offer
        if self.me == self.last_offerer:
            desired_val = min(self.total_value, max(0.45 * self.total_value, self.total_value * (0.9 - 0.4 * progress)))
        else:
            desired_val = min(self.total_value, max(0.4 * self.total_value, self.total_value * (0.85 - 0.45 * progress)))
        
        # If final offer, leave something opponent will accept to avoid no-deal
        if offers_left_after <= 0:
            desired_val = min(desired_val, 0.8 * self.total_value)

        # Build base offer: take highest value items first
        my_offer = [0]*len(self.counts)
        current_val = 0
        for idx in self.sorted_items:
            if current_val >= desired_val or self.values[idx] == 0:
                continue
            take = min(self.counts[idx], (desired_val - current_val) // self.values[idx])
            my_offer[idx] = take
            current_val += take * self.values[idx]
        
        # Top up to reach desired value if needed
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

        # Concede items opponent wants most first (bargaining chips)
        if self.opponent_offers:
            # Calculate opponent preference: lower offer to us = they want the item more
            opponent_pref = []
            for i in range(len(self.counts)):
                avg_offer = sum(offer[i] for offer in self.opponent_offers) / len(self.opponent_offers)
                opponent_pref.append((avg_offer, i))  # Lower avg = they want more
            opponent_pref.sort()  # Sort ascending: items they want most first
            
            # Give away items we value least first that opponent wants
            concession_rate = min(progress + 0.3, 1.0)
            for avg_offer, i in opponent_pref:
                if self.values[i] == 0:
                    # Give all zero value items opponent wants
                    my_offer[i] = max(0, self.counts[i] - int(self.counts[i] * concession_rate))
                elif self.values[i] <= 0.1 * self.total_value / sum(self.counts):
                    # Give away low value items first
                    give = min(my_offer[i], int(my_offer[i] * concession_rate * 0.5))
                    my_offer[i] -= give
        else:
            # First offer: keep all zero value items to use as concessions later
            for i in range(len(self.counts)):
                if self.values[i] == 0:
                    my_offer[i] = self.counts[i]

        # Ensure all values are valid
        for i in range(len(my_offer)):
            my_offer[i] = max(0, min(int(my_offer[i]), self.counts[i]))

        self.offers_made += 1
        return my_offer