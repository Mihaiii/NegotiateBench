class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.turn_count = 0
        self.initial_offer = None
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn_count += 1
        total_turns = self.max_rounds * 2
        turns_remaining = total_turns - self.turn_count + 1
        
        # Handle opponent's offer
        if o is not None:
            # Validate offer
            offer_value = 0
            valid = True
            for i in range(len(o)):
                if o[i] < 0 or o[i] > self.counts[i]:
                    valid = False
                    break
                offer_value += o[i] * self.values[i]
            
            if not valid:
                return None
                
            # Calculate minimum acceptable value based on remaining turns
            if turns_remaining == 1:
                # Last turn - accept any non-zero offer
                if offer_value > 0:
                    return None
            else:
                # Time-based acceptance threshold
                if turns_remaining <= 2:
                    min_acceptable = max(1, self.total_value * 0.25)
                elif turns_remaining <= 4:
                    min_acceptable = self.total_value * 0.35
                elif turns_remaining <= 8:
                    min_acceptable = self.total_value * 0.45
                else:
                    min_acceptable = self.total_value * 0.55
                
                if offer_value >= min_acceptable:
                    return None
        
        # Generate counter-offer
        return self._generate_counter_offer(turns_remaining)
    
    def _generate_counter_offer(self, turns_remaining: int) -> list[int]:
        # Sort items by our value (descending)
        item_indices = sorted(range(len(self.values)), key=lambda i: self.values[i], reverse=True)
        
        # Start with taking all items we value
        proposal = [0] * len(self.counts)
        for i in range(len(self.counts)):
            if self.values[i] > 0:
                proposal[i] = self.counts[i]
        
        # Make concessions based on time pressure and turn number
        concessions_needed = 0
        if turns_remaining <= 2:
            # Last few turns - be very reasonable
            concessions_needed = 2
        elif turns_remaining <= 4:
            # Moderate concessions
            concessions_needed = 1
        elif self.turn_count == 1:
            # First move - be slightly less greedy to appear reasonable
            concessions_needed = 1
        # Otherwise, stick to aggressive position
        
        # Make concessions on lowest-value items we're taking
        for _ in range(concessions_needed):
            # Find the lowest-value item we're currently taking (that has count > 0)
            concession_item = -1
            min_value_per_item = float('inf')
            
            for i in item_indices:
                if proposal[i] > 0 and self.values[i] < min_value_per_item:
                    min_value_per_item = self.values[i]
                    concession_item = i
            
            if concession_item != -1 and proposal[concession_item] > 0:
                proposal[concession_item] -= 1
        
        # Ensure we don't exceed counts (shouldn't happen but just in case)
        for i in range(len(proposal)):
            proposal[i] = max(0, min(proposal[i], self.counts[i]))
        
        return proposal