class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.turn_count = 0
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn_count += 1
        total_turns = self.max_rounds * 2
        turns_remaining = total_turns - self.turn_count
        
        # Handle incoming offer
        if o is not None:
            offer_value = sum(o_i * v_i for o_i, v_i in zip(o, self.values))
            
            # Accept if it meets our minimum threshold for this stage
            if turns_remaining == 0:
                # Last chance - accept anything > 0
                if offer_value > 0:
                    return None
            elif turns_remaining <= 2:
                # Very late game - accept 40% or more
                if offer_value >= self.total_value * 0.4:
                    return None
            elif turns_remaining <= 4:
                # Late game - accept 50% or more  
                if offer_value >= self.total_value * 0.5:
                    return None
            else:
                # Early/mid game - accept 60% or more
                if offer_value >= self.total_value * 0.6:
                    return None
        
        # Determine our target share based on how many turns remain
        if turns_remaining == 0:
            target_share = 0.5  # Be fair on final offer
        elif turns_remaining <= 2:
            target_share = 0.55
        elif turns_remaining <= 4:
            target_share = 0.6
        elif turns_remaining <= 8:
            target_share = 0.65
        else:
            target_share = 0.7  # Start ambitious
        
        target_value = self.total_value * target_share
        
        # Build our offer by taking items in order of our value (highest first)
        offer = [0] * len(self.counts)
        current_value = 0
        
        # Create list of item indices sorted by our value (descending)
        item_indices = sorted(range(len(self.values)), key=lambda i: self.values[i], reverse=True)
        
        for i in item_indices:
            if current_value >= target_value:
                break
                
            # How much more value do we need?
            needed_value = target_value - current_value
            
            # If this item has no value to us, only take it if we absolutely need to
            # fill the allocation (but we shouldn't need to since we're targeting a share)
            if self.values[i] == 0:
                # Only take zero-value items if we're forced to by previous offers
                # But generally, leave them for opponent
                continue
            
            # Calculate how many of this item we can take
            max_possible = self.counts[i]
            if needed_value > 0:
                # Take enough to get close to our target
                items_needed = min(max_possible, int((needed_value + self.values[i] - 1) // self.values[i]))
                offer[i] = items_needed
                current_value += items_needed * self.values[i]
        
        # Ensure we don't exceed available counts (shouldn't happen but safety check)
        for i in range(len(offer)):
            offer[i] = min(offer[i], self.counts[i])
        
        # Handle the case where we might be asking for too little (shouldn't happen with our logic)
        # But ensure we're making a valid offer
        offer_value = sum(offer[i] * self.values[i] for i in range(len(offer)))
        
        # If we're in the final rounds and our offer is way below target, 
        # we might want to be slightly more aggressive, but our target_share logic should handle this
        
        return offer