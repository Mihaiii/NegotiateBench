class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.turn_count = 0
        self.opponent_offers = []
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn_count += 1
        total_turns = self.max_rounds * 2
        turns_remaining = total_turns - self.turn_count + 1
        
        # Handle opponent's offer
        if o is not None:
            # Validate offer
            valid = True
            offer_value = 0
            for i in range(len(o)):
                if o[i] < 0 or o[i] > self.counts[i]:
                    valid = False
                    break
                offer_value += o[i] * self.values[i]
            
            if not valid:
                return None
                
            self.opponent_offers.append(o)
            
            # Calculate minimum acceptable value
            if turns_remaining == 1:
                # Last turn - accept any positive offer
                if offer_value > 0:
                    return None
            else:
                # Calculate target based on time pressure
                if turns_remaining <= 2:
                    min_acceptable = max(1, self.total_value * 0.3)
                elif turns_remaining <= 5:
                    min_acceptable = self.total_value * 0.4
                elif turns_remaining <= 10:
                    min_acceptable = self.total_value * 0.5
                else:
                    min_acceptable = self.total_value * 0.6
                
                # If opponent is making concessions, be more flexible
                if len(self.opponent_offers) >= 2:
                    prev_value = sum(self.opponent_offers[-2][i] * self.values[i] for i in range(len(self.values)))
                    if offer_value > prev_value:
                        min_acceptable *= 0.9
                
                if offer_value >= min_acceptable:
                    return None
        
        # Generate counter-offer
        return self._generate_counter_offer(turns_remaining)
    
    def _generate_counter_offer(self, turns_remaining: int) -> list[int]:
        # Sort items by our value (descending)
        item_indices = list(range(len(self.values)))
        item_indices.sort(key=lambda i: self.values[i], reverse=True)
        
        # Calculate target value based on time pressure
        if turns_remaining == 1:
            target_ratio = 0.3
        elif turns_remaining <= 3:
            target_ratio = 0.4
        elif turns_remaining <= 7:
            target_ratio = 0.5
        else:
            target_ratio = 0.7
            
        target_value = self.total_value * target_ratio
        
        # Start with taking nothing
        proposal = [0] * len(self.counts)
        current_value = 0
        
        # First, take all items we value that opponent seems to value less
        if self.opponent_offers:
            # Calculate what opponent typically offers us (what they're willing to give up)
            avg_offers = [0] * len(self.counts)
            for offer in self.opponent_offers:
                for i in range(len(self.counts)):
                    avg_offers[i] += offer[i]
            for i in range(len(self.counts)):
                avg_offers[i] /= len(self.opponent_offers)
            
            # Take items where opponent offers us a lot (they don't value them much)
            for i in item_indices:
                if self.values[i] == 0:
                    continue
                    
                # If opponent typically offers us most of this item, take it
                if avg_offers[i] >= self.counts[i] * 0.7:
                    items_to_take = self.counts[i]
                    if current_value + items_to_take * self.values[i] <= target_value * 2:
                        proposal[i] = items_to_take
                        current_value += items_to_take * self.values[i]
        
        # Then fill remaining target with our most valuable items
        for i in item_indices:
            if current_value >= target_value:
                break
            if self.values[i] == 0:
                continue
            if proposal[i] == self.counts[i]:
                continue
                
            # Take as much as needed to reach target
            remaining_needed = target_value - current_value
            items_needed = min(self.counts[i] - proposal[i], (remaining_needed + self.values[i] - 1) // self.values[i])
            proposal[i] += items_needed
            current_value += items_needed * self.values[i]
        
        # Don't be greedy on first move - leave something for opponent
        if len(self.opponent_offers) == 0:
            for i in reversed(item_indices):  # Start with least valuable items we took
                if self.values[i] > 0 and proposal[i] > 0:
                    # Reduce by 1 if we have more than 1, or if it's a high-value item
                    if proposal[i] > 1 or self.values[i] > self.total_value * 0.1:
                        proposal[i] = max(0, proposal[i] - 1)
                        break
        
        # Ensure we don't exceed counts
        for i in range(len(proposal)):
            proposal[i] = max(0, min(proposal[i], self.counts[i]))
        
        return proposal