class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.rounds_elapsed = 0
        self.total_value = sum(c * v for c, v in zip(counts, values))
        
        # Track opponent patterns and history
        self.opponent_history = []
        self.my_history = []
        self.acceptance_threshold = 0.4

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.rounds_elapsed += 1
        
        # If opponent offered something (not first turn)
        if o is not None:
            # Record the offer
            self.opponent_history.append(o[:])
            
            # Calculate value of opponent's offer to me
            offer_value = sum(o[i] * self.values[i] for i in range(len(o)))
            offer_ratio = offer_value / self.total_value if self.total_value > 0 else 0
            
            # Determine acceptance threshold based on time remaining
            progress = self.rounds_elapsed / self.max_rounds
            min_acceptance = max(0.3, self.acceptance_threshold * (1 - progress))
            ideal_acceptance = max(0.5, 0.7 * (1 - progress))
            
            # Accept if a good offer or if running out of time
            time_pressure = progress > 0.7
            very_good_offer = offer_ratio > 0.8
            
            if very_good_offer or (time_pressure and offer_ratio >= 0.3) or offer_ratio >= ideal_acceptance:
                return None  # Accept the offer
        
        # Make a counter-offer if we're not accepting
        my_offer = self.create_counteroffer(o)
        
        # Track our counter-offer
        self.my_history.append(my_offer[:])
        
        return my_offer

    def create_counteroffer(self, opponent_offer):
        """Create a strategic counter-offer using a more balanced approach"""
        # Start with a reasonable allocation for ourselves
        desired = [0] * len(self.counts)
        
        # Calculate relative importance of each item type to us
        importance = [v for v in self.values]
        
        # Create an offer based on our valuation and try to give opponent something too
        remaining = self.counts[:]
        
        # First, try to allocate high-value items to ourselves
        for i in sorted(range(len(importance)), key=lambda x: importance[x], reverse=True):
            desired[i] = min(remaining[i], self.counts[i])
            remaining[i] = 0  # We take all of this item
        
        # Check if we're asking for everything (greedy), which might be bad for negotiations
        items_i_get = sum(desired[i] for i in range(len(desired)))
        total_items = sum(self.counts)
        
        if items_i_get == total_items:
            # If we're asking for all items, give some back, especially of low value to us
            low_value_indices = [i for i in range(len(self.values)) if self.values[i] == 0]
            
            # Give back items with value 0 to us
            for i in low_value_indices:
                if desired[i] > 0:
                    desired[i] = 0
            
            # If still demanding all high-value items, reconsider
            remaining_low_val = [i for i in range(len(self.values)) if 
                                self.values[i] > 0 and desired[i] > 0]
            
            # If we have multiple high-value items, consider giving back the least valuable ones
            # based on opponent's pattern of accepting items they value more
            if len(remaining_low_val) > 1 and len(self.opponent_history) > 0:
                # If not the first offer, consider opponent's previous values
                # and maybe give back something they might value
                min_value_idx = min(remaining_low_val, key=lambda x: self.values[x])
                if desired[min_value_idx] > 0:
                    desired[min_value_idx] = max(0, desired[min_value_idx] - 1)
                    
        else:
            # If the opponent made a previous offer, consider incorporating some of their preferences
            # assuming they might value certain items more than we do
            if opponent_offer and len(self.opponent_history) == 1:
                # This is our first counteroffer - be strategic about what to counter
                # Keep valuable items but be willing to give something back
                for i in range(len(desired)):
                    if self.values[i] == 0 and desired[i] > 0:
                        desired[i] = 0  # No point keeping stuff worth nothing to us
        
        # Ensure we don't exceed available counts
        for i in range(len(desired)):
            desired[i] = min(desired[i], self.counts[i])
            
        return desired