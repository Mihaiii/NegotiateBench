class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.rounds_left = max_rounds
        
        # Calculate total value
        self.total_value = sum(c * v for c, v in zip(counts, values))
        
        # Sort items by value to us (descending)
        self.item_indices = list(range(len(counts)))
        self.item_indices.sort(key=lambda i: values[i], reverse=True)
        
        # Calculate what we want initially - take everything with positive value
        self.ideal_offer = [0] * len(counts)
        for i in range(len(counts)):
            if values[i] > 0:
                self.ideal_offer[i] = counts[i]
        
        # Track opponent's offers to infer their preferences
        self.opponent_offers = []
        self.my_last_offer = None
    
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.rounds_left -= 0.5  # Each call is half a round
        
        # If we're being offered something
        if o is not None:
            # Track opponent's offer
            self.opponent_offers.append(o)
            
            # Calculate value of opponent's offer to us
            offer_value = sum(v * c for v, c in zip(self.values, o))
            
            # Acceptance threshold decreases over time
            # Start high, end with minimum acceptable value
            time_factor = self.rounds_left / self.max_rounds
            threshold = self.total_value * (0.5 + 0.3 * time_factor)
            
            # If opponent's offer is good enough, accept
            if offer_value >= threshold:
                return None
        
        # If this is our first move or we need to counter
        # Generate a counter-offer based on current round
        
        # Start with ideal offer early
        if len(self.opponent_offers) == 0:
            return self.ideal_offer.copy()
        
        # Analyze opponent's preferences if we have multiple offers
        if len(self.opponent_offers) >= 2:
            # Try to infer what opponent values
            opponent_pref = [0] * len(self.counts)
            for offer in self.opponent_offers[-2:]:
                for i in range(len(self.counts)):
                    if offer[i] < self.counts[i] / 2:  # They're willing to give it up
                        opponent_pref[i] -= 1
                    elif offer[i] > self.counts[i] / 2:  # They want it
                        opponent_pref[i] += 1
        
        # Generate counter-offer based on round
        # Gradually concede less valuable items
        counter = [0] * len(self.counts)
        rounds_passed = self.max_rounds - self.rounds_left
        
        # Determine how many high-value items to keep
        # Keep more early, fewer late
        keep_factor = 1.0 - (rounds_passed / (self.max_rounds * 1.5))
        keep_factor = max(0.3, keep_factor)  # Never drop below 30% of ideal
        
        # Calculate target value
        target_value = self.total_value * keep_factor
        
        # Start with all items we value
        for i in self.item_indices:
            if self.values[i] > 0:
                counter[i] = self.counts[i]
        
        # Calculate current value
        current_value = sum(v * c for v, c in zip(self.values, counter))
        
        # If we're over target, give up less valuable items
        if current_value > target_value:
            excess = current_value - target_value
            
            # Give up items starting with lowest value to us
            for i in reversed(self.item_indices):
                if counter[i] > 0 and self.values[i] > 0:
                    # Give up some or all of this item
                    give_up = min(counter[i], int(excess / self.values[i] + 0.5))
                    if give_up > 0:
                        counter[i] -= give_up
                        excess -= give_up * self.values[i]
                
                if excess <= 0:
                    break
        
        # Ensure we keep at least some of our highest value items
        for i in self.item_indices[:2]:  # Top 2 most valuable items
            if self.values[i] > 0 and counter[i] == 0:
                counter[i] = min(1, self.counts[i])
        
        # If we're the last to speak in the last round, be more aggressive
        if self.rounds_left <= 0.5:
            # Last chance - go for broke
            for i in self.item_indices:
                if self.values[i] > 0:
                    counter[i] = self.counts[i]
        
        self.my_last_offer = counter.copy()
        return counter