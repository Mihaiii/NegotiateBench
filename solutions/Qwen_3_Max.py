class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.turn_count = 0
        self.last_offer = None
        self.opponent_offers = []
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn_count += 1
        total_turns = self.max_rounds * 2
        turns_remaining = total_turns - self.turn_count
        
        # Handle incoming offer
        if o is not None:
            self.opponent_offers.append(o)
            offer_value = sum(o_i * v_i for o_i, v_i in zip(o, self.values))
            
            # Accept if it meets our minimum threshold
            if turns_remaining == 0:
                # Last chance - accept anything > 0
                if offer_value > 0:
                    return None
            elif turns_remaining <= 2:
                # Very late game - accept 35% or more
                if offer_value >= self.total_value * 0.35:
                    return None
            elif turns_remaining <= 4:
                # Late game - accept 45% or more  
                if offer_value >= self.total_value * 0.45:
                    return None
            else:
                # Early/mid game - accept 55% or more
                if offer_value >= self.total_value * 0.55:
                    return None
        
        # Determine target share based on negotiation stage
        if turns_remaining == 0:
            target_share = 0.5
        elif turns_remaining <= 2:
            target_share = 0.5
        elif turns_remaining <= 4:
            target_share = 0.55
        elif turns_remaining <= 8:
            target_share = 0.6
        else:
            target_share = 0.65
        
        target_value = self.total_value * target_share
        
        # Create initial offer by taking highest value items first
        offer = [0] * len(self.counts)
        current_value = 0
        
        # Sort items by our value (descending)
        item_indices = sorted(range(len(self.values)), key=lambda i: self.values[i], reverse=True)
        
        for i in item_indices:
            if self.values[i] == 0:
                continue
            if current_value >= target_value:
                break
            needed_value = target_value - current_value
            items_needed = min(self.counts[i], (needed_value + self.values[i] - 1) // self.values[i])
            offer[i] = int(items_needed)
            current_value += offer[i] * self.values[i]
        
        # Apply concessions based on negotiation history
        if self.opponent_offers:
            # Look at the most recent opponent offer to understand what they want
            last_opponent_offer = self.opponent_offers[-1]
            # Calculate what opponent is keeping for themselves (from their perspective)
            # But we don't know their values, so we infer from what they're demanding
            
            # If we've been making the same offer repeatedly and it's being rejected,
            # we need to make a meaningful change
            if self.last_offer is not None and self.last_offer == offer:
                # Make a small concession on the lowest-value item we're claiming
                concession_made = False
                # Sort by our value (ascending) to find items to concede
                low_value_items = sorted(range(len(self.values)), key=lambda i: self.values[i])
                for i in low_value_items:
                    if offer[i] > 0 and self.values[i] > 0:
                        offer[i] = max(0, offer[i] - 1)
                        concession_made = True
                        break
                
                # If no concession was possible on valuable items, try on zero-value items
                if not concession_made:
                    for i in low_value_items:
                        if offer[i] > 0 and self.values[i] == 0:
                            offer[i] = max(0, offer[i] - 1)
                            break
        
        # Ensure offer is valid
        for i in range(len(offer)):
            offer[i] = min(offer[i], self.counts[i])
            offer[i] = max(0, offer[i])
        
        # Safety check: if we're asking for nothing and it's not the first turn, ask for something minimal
        if sum(offer) == 0 and self.turn_count > 1:
            # Take at least one item we value most
            best_item = max(range(len(self.values)), key=lambda i: self.values[i])
            offer[best_item] = min(1, self.counts[best_item])
        
        self.last_offer = offer.copy()
        return offer