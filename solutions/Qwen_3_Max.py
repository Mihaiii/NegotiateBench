class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.turn_count = 0
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn_count += 1
        
        # If responding to an offer
        if o is not None:
            offer_value = sum(o_i * v_i for o_i, v_i in zip(o, self.values))
            min_acceptable = self._min_acceptable_value()
            if offer_value >= min_acceptable:
                return None
        
        # Generate counter-offer
        return self._generate_offer()
    
    def _min_acceptable_value(self) -> int:
        # Calculate how many full rounds remain after current turn
        turns_remaining = (self.max_rounds * 2) - self.turn_count
        rounds_remaining = (turns_remaining + 1) // 2
        
        # In the final round, accept anything > 0 if we're responding
        if rounds_remaining == 0:
            return 1
        
        # Be more flexible as time runs out
        if rounds_remaining == 1:
            return max(1, self.total_value // 4)
        elif rounds_remaining <= 3:
            return max(1, self.total_value // 3)
        elif rounds_remaining <= 6:
            return max(1, self.total_value // 2)
        else:
            return max(1, (2 * self.total_value) // 3)
    
    def _generate_offer(self) -> list[int]:
        # Calculate our target value for this offer
        min_acceptable = self._min_acceptable_value()
        # Be slightly more aggressive than minimum acceptable
        target_value = min(self.total_value, min_acceptable + max(1, (self.total_value - min_acceptable) // 3))
        
        # Create list of items sorted by our value (descending)
        items = []
        for i in range(len(self.counts)):
            if self.values[i] > 0:
                items.append((self.values[i], i))
        items.sort(reverse=True)
        
        # Start with taking nothing
        offer = [0] * len(self.counts)
        current_value = 0
        
        # Greedily add highest value items first
        for value, idx in items:
            if current_value >= target_value:
                break
            # Calculate how many of this item we need
            remaining_value_needed = target_value - current_value
            max_possible_items = self.counts[idx]
            items_to_take = min(max_possible_items, (remaining_value_needed + value - 1) // value)
            offer[idx] = items_to_take
            current_value += items_to_take * value
        
        # If we're making the first move, be more reasonable
        if self.turn_count == 1 and self.me == 0:
            # Reduce our demand slightly to make it more acceptable
            reduction_needed = max(1, target_value // 10)
            current_value = sum(offer[i] * self.values[i] for i in range(len(offer)))
            if current_value > self.total_value // 2:
                # Remove lowest value items first to reduce demand
                low_value_items = []
                for i in range(len(self.counts)):
                    if offer[i] > 0 and self.values[i] > 0:
                        low_value_items.append((self.values[i], i))
                low_value_items.sort()  # ascending by value
                
                value_to_remove = 0
                for value, idx in low_value_items:
                    while offer[idx] > 0 and value_to_remove < reduction_needed:
                        offer[idx] -= 1
                        value_to_remove += value
                        if value_to_remove >= reduction_needed:
                            break
                    if value_to_remove >= reduction_needed:
                        break
        
        # Ensure we don't exceed available counts
        for i in range(len(offer)):
            offer[i] = min(offer[i], self.counts[i])
            
        return offer