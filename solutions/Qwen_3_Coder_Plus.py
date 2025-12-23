class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_value = sum(counts[i] * values[i] for i in range(len(counts)))
        self.current_round = 0
        
        # Keep track of opponent's offers to infer their preferences
        self.opponent_offers = []
        self.my_offers = []

    def calculate_value(self, allocation):
        """Calculate total value of an allocation according to my values."""
        return sum(allocation[i] * self.values[i] for i in range(len(allocation)))

    def infer_opponent_values(self):
        """Try to infer opponent's values based on their offers."""
        if not self.opponent_offers:
            return None
            
        # Simple heuristic: if opponent keeps requesting same items, they likely value them
        # Count how many times each item type was requested by opponent
        request_counts = [0] * len(self.counts)
        for offer in self.opponent_offers:
            for i in range(len(offer)):
                if offer[i] > 0:
                    request_counts[i] += 1
        
        # Also consider what they left for me in their offers
        remaining_counts = [0] * len(self.counts)
        for offer in self.opponent_offers:
            for i in range(len(offer)):
                remaining_counts[i] += (self.counts[i] - offer[i])
        
        # Calculate potential opponent values based on requests vs. leaving
        estimated_values = []
        for i in range(len(self.counts)):
            if self.counts[i] > 0:
                # Higher requests indicate higher value
                est_val = request_counts[i] - (len(self.opponent_offers) * self.counts[i] - remaining_counts[i])
                estimated_values.append(max(0, est_val))
            else:
                estimated_values.append(0)
        
        return estimated_values

    def make_balanced_offer(self):
        """Create an offer using proportional sharing based on mutual value assessment."""
        # Start with maximum allocation I could want
        best_offer = self.counts[:]
        current_value = self.calculate_value(best_offer)
        
        # If I can get full value, propose that, but let's be strategic
        # Adjust to be competitive but offer some incentives to opponent
        opponent_values = self.infer_opponent_values()
        if opponent_values:
            # Balance between self-interest and offering attractive trade items
            offer = [0] * len(self.counts)
            temp_counts = self.counts[:]
            
            # Prioritize items I value highly first
            indices = sorted(range(len(self.values)), key=lambda i: -self.values[i])
            
            # Try to get most valuable items for myself
            for idx in indices:
                if self.values[idx] > 0:
                    offer[idx] = temp_counts[idx]
                    temp_counts[idx] = 0
                else:
                    # For items I don't value, potentially offer to opponent if they do
                    # But only if it helps my overall strategy
                    if opponent_values[idx] > 0:
                        # Give some to opponent to entice them
                        give_count = max(0, temp_counts[idx] // 2)
                        offer[idx] = temp_counts[idx] - give_count
                        temp_counts[idx] = give_count
            
            # Make sure all items are allocated
            for i in range(len(offer)):
                if offer[i] + temp_counts[i] != self.counts[i]:
                    offer[i] = self.counts[i] - temp_counts[i]
            return offer
        else:
            # Default strategy if no opponent data
            return best_offer[:]

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.current_round += 1
        
        # Process incoming offer if any
        if o is not None:
            # Add opponent's offer to history for learning
            self.opponent_offers.append(o)
            
            # Calculate value of this offer to me
            received_value = self.calculate_value(o)
            
            # Decision logic based on the current round and offer value
            rounds_left = self.max_rounds - self.current_round
            
            # Calculate minimum value needed to accept based on round number
            # Early rounds - accept only very generous offers
            # Later rounds - be more willing to accept
            accept_threshold = self.total_value * (0.6 + 0.2 * (1 - rounds_left/max(1, self.max_rounds - 1)))
            
            if received_value >= accept_threshold:
                # Accept the offer
                return None
                
        # Make a counter-offer if we reject or no offer to accept
        
        # On first turn when there's no opponent offer yet
        if o is None:
            self.my_offers.append(self.counts[:])
            return self.make_balanced_offer()
        
        # If this is a counter-offer (we're rejecting an offer)
        # Try to find a better deal for myself but still acceptable to opponent
        new_offer = [0] * len(self.counts)
        
        # Take a balanced approach: improve on the most valuable items for me
        # but still offer enough to entice opponent
        for i in range(len(self.counts)):
            # If their offer to me is low and I value the item highly, take more
            if self.values[i] > 0:
                # Try to take at least as much as offered to me, perhaps more
                new_offer[i] = max(o[i], self.counts[i] // 2)
            else:
                # For items I don't value, consider letting opponent keep more
                new_offer[i] = min(o[i], self.counts[i] // 2)
        
        # Ensure we're not offering more than available
        for i in range(len(new_offer)):
            new_offer[i] = max(0, min(self.counts[i], new_offer[i]))
        
        # Adjust to ensure all items are distributed properly
        # If allocation is inconsistent (total != counts), fix it
        allocated_to_other = [self.counts[i] - new_offer[i] for i in range(len(self.counts))]
        
        # Add the counter-offer to our history
        self.my_offers.append(new_offer)
        return new_offer