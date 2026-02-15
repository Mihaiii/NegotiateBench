class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.rounds_remaining = max_rounds
        self.opponent_valuation = None  # Will be inferred over time if possible

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.rounds_remaining -= 1
        
        # Calculate our current offer value
        if o is not None:
            our_value_from_offer = sum(v * x for v, x in zip(self.values, o))
            # If offer gives us at least half our total value and we're not desperate, accept
            if our_value_from_offer >= self.total_value / 2 and self.rounds_remaining > 0:
                # But also consider if we can get more by holding out
                # Simple heuristic: accept if it's reasonable and rounds are running out
                if self.rounds_remaining == 0 or our_value_from_offer >= self.total_value * 0.4:
                    return None
        
        # Generate our offer
        # Start with trying to get most valuable items
        offer = [0] * len(self.counts)
        
        # Sort item types by value (descending) to prioritize getting high-value items
        item_indices = sorted(range(len(self.values)), key=lambda i: self.values[i], reverse=True)
        
        # Calculate how many items we should demand
        if self.rounds_remaining == self.max_rounds - 1 and self.max_rounds > 1:
            # First round: be greedy but reasonable
            for idx in item_indices:
                # Take all of high-value items, skip worthless ones
                if self.values[idx] > 0:
                    offer[idx] = self.counts[idx]
            # But leave some for partner to incentivize agreement
            for idx in item_indices:
                if self.values[idx] > 0 and offer[idx] > 0:
                    offer[idx] = max(0, offer[idx] - 1)
                    break  # Only reduce one type
            
            # Ensure at least some items go to partner if they have any value
            partner_values = [self.counts[i] - offer[i] for i in range(len(self.counts))]
            partner_val_sum = sum(p * v for p, v in zip(partner_values, self.values))
            
            # If partner gets nothing, adjust to make it acceptable
            if partner_val_sum == 0:
                for idx in item_indices:
                    if self.values[idx] == 0:
                        offer[idx] = max(0, offer[idx] - 1)
                        break
                
        elif self.rounds_remaining == 0:
            # Last round - make final reasonable offer
            # Take most items but ensure partner gets something valuable
            for idx in item_indices:
                if self.values[idx] > 0:
                    offer[idx] = self.counts[idx]
            
            # Give partner at least one valuable item if possible
            for idx in item_indices:
                if self.values[idx] > 0 and offer[idx] > 0:
                    offer[idx] -= 1
                    break
        else:
            # Middle rounds - make increasingly generous offers
            base_giveaway = (self.max_rounds - self.rounds_remaining) // 2
            for idx in item_indices:
                if self.values[idx] > 0:
                    offer[idx] = self.counts[idx]
            
            # Give away items strategically
            items_to_give = min(base_giveaway + 1, sum(1 for v in self.values if v > 0))
            for _ in range(items_to_give):
                for idx in item_indices:
                    if self.values[idx] > 0 and offer[idx] > 0:
                        offer[idx] -= 1
                        break
        
        return offer