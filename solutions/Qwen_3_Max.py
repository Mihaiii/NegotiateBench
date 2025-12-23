class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.round_num = 0
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.round_num += 1
        
        # If this is a counter-offer (not the first move), evaluate the offer
        if o is not None:
            # Calculate value of the offer to us
            offer_value = sum(o_i * v_i for o_i, v_i in zip(o, self.values))
            
            # If the offer gives us at least our minimum acceptable value, accept it
            min_acceptable = self._min_acceptable_value()
            if offer_value >= min_acceptable:
                return None
        
        # Generate our counter-offer
        return self._generate_offer()
    
    def _min_acceptable_value(self) -> int:
        # Calculate how many rounds remain (including current)
        rounds_remaining = self.max_rounds - (self.round_num - 1) // 2
        
        # If we're in the last possible round and it's our turn to respond,
        # we should accept anything better than 0
        if rounds_remaining <= 1 and self.round_num % 2 == (1 if self.me == 0 else 0):
            return 1
        
        # Be more flexible as rounds run out
        if rounds_remaining <= 2:
            return max(1, self.total_value // 3)
        elif rounds_remaining <= 4:
            return max(1, self.total_value // 2)
        else:
            return max(1, (2 * self.total_value) // 3)
    
    def _generate_offer(self) -> list[int]:
        # Create a list of (value_per_item, item_index) for items we value
        item_values = []
        for i, (count, value) in enumerate(zip(self.counts, self.values)):
            if value > 0 and count > 0:
                item_values.append((value, i))
        
        # Sort by value descending (we want high-value items first)
        item_values.sort(reverse=True)
        
        # Start with taking nothing
        offer = [0] * len(self.counts)
        
        # Calculate target value based on remaining rounds
        min_acceptable = self._min_acceptable_value()
        target_value = min(self.total_value, min_acceptable + (self.total_value - min_acceptable) // 2)
        
        current_value = 0
        
        # Greedily take items starting with highest value
        for value, idx in item_values:
            if current_value >= target_value:
                break
            # Take as many as needed of this item to reach target
            needed_value = target_value - current_value
            max_items = min(self.counts[idx], (needed_value + value - 1) // value)
            offer[idx] = max_items
            current_value += max_items * value
        
        # Ensure we don't exceed counts
        for i in range(len(offer)):
            offer[i] = min(offer[i], self.counts[i])
            
        return offer