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
        
        # If responding to an offer
        if o is not None:
            self.opponent_offers.append(o)
            offer_value = sum(o_i * v_i for o_i, v_i in zip(o, self.values))
            
            # Calculate minimum acceptable based on time pressure
            total_turns = self.max_rounds * 2
            turns_elapsed = self.turn_count
            time_pressure = turns_elapsed / total_turns
            
            # Be more willing to accept as time runs out
            if time_pressure >= 0.9:  # Last 10% of turns
                min_acceptable = self.total_value * 0.4
            elif time_pressure >= 0.7:  # Last 30% of turns
                min_acceptable = self.total_value * 0.5
            elif time_pressure >= 0.5:  # Middle phase
                min_acceptable = self.total_value * 0.6
            else:  # Early phase
                min_acceptable = self.total_value * 0.7
            
            if offer_value >= min_acceptable:
                return None
        
        # Generate counter-offer
        return self._generate_offer()
    
    def _generate_offer(self) -> list[int]:
        total_turns = self.max_rounds * 2
        turns_elapsed = self.turn_count
        time_pressure = turns_elapsed / total_turns
        
        # Base target value decreases with time pressure
        if time_pressure >= 0.9:
            target_ratio = 0.6
        elif time_pressure >= 0.7:
            target_ratio = 0.7
        elif time_pressure >= 0.5:
            target_ratio = 0.8
        elif time_pressure >= 0.3:
            target_ratio = 0.85
        else:
            target_ratio = 0.9
        
        target_value = self.total_value * target_ratio
        
        # Create offer prioritizing high-value items
        offer = [0] * len(self.counts)
        current_value = 0
        
        # Create list of (value_per_item, index) for valuable items
        valuable_items = []
        for i in range(len(self.counts)):
            if self.values[i] > 0:
                valuable_items.append((self.values[i], i))
        
        # Sort by value descending
        valuable_items.sort(reverse=True)
        
        # Greedily take highest value items first
        for value, idx in valuable_items:
            if current_value >= target_value:
                break
            remaining_needed = target_value - current_value
            max_items = self.counts[idx]
            items_to_take = min(max_items, int((remaining_needed + value - 1) // value))
            offer[idx] = items_to_take
            current_value += items_to_take * value
        
        # If we have opponent offer history, identify items they seem to value
        if self.opponent_offers:
            # Calculate what opponent keeps: counts[i] - opponent_offer[i]
            opponent_keeps_total = [0] * len(self.counts)
            for opp_offer in self.opponent_offers:
                for i in range(len(self.counts)):
                    opponent_keeps_total[i] += self.counts[i] - opp_offer[i]
            
            avg_opponent_keeps = [keeps / len(self.opponent_offers) for keeps in opponent_keeps_total]
            
            # Concede items that opponent values highly but we value lowly
            # Only do this if we're not in very early rounds
            if turns_elapsed > 2:
                for i in range(len(self.counts)):
                    # If opponent keeps most of this item and we don't value it much
                    if (avg_opponent_keeps[i] >= self.counts[i] * 0.6 and 
                        self.values[i] <= max(self.values) * 0.3 and
                        offer[i] > 0):
                        # Reduce our demand on this item
                        reduction = min(offer[i], 1)
                        offer[i] -= reduction
        
        # Ensure we don't exceed available counts
        for i in range(len(offer)):
            offer[i] = min(offer[i], self.counts[i])
            
        # Safety: if this is our last possible turn, make a reasonable offer
        if self.turn_count >= self.max_rounds * 2 - 1:
            # Be very reasonable - aim for 50% of our value
            target_value = self.total_value * 0.5
            offer = [0] * len(self.counts)
            current_value = 0
            
            valuable_items = [(self.values[i], i) for i in range(len(self.counts)) if self.values[i] > 0]
            valuable_items.sort(reverse=True)
            
            for value, idx in valuable_items:
                if current_value >= target_value:
                    break
                remaining_needed = target_value - current_value
                items_to_take = min(self.counts[idx], int((remaining_needed + value - 1) // value))
                offer[idx] = items_to_take
                current_value += items_to_take * value
        
        return offer