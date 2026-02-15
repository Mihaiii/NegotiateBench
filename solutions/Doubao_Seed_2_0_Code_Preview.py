class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts.copy()
        self.values = values.copy()
        self.max_rounds = max_rounds
        self.total_turns = 2 * max_rounds
        self.my_total = sum(c * v for c, v in zip(counts, values))
        # Precompute items with positive value sorted by ascending value (give up least valuable first)
        self.sorted_items = sorted(
            [(v, i) for i, v in enumerate(values) if v > 0],
            key=lambda x: x[0]
        )
        self.turn_count = 0
        self.last_offer = None

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn_count += 1
        
        # Handle acceptance if we received an offer
        if o is not None:
            offer_value = sum(oi * vi for oi, vi in zip(o, self.values))
            
            # Accept immediately if we value nothing
            if self.my_total == 0:
                return None
            
            # Calculate acceptance threshold: linear decrease from 80% to 0%
            if self.total_turns == 1:
                fraction = 1.0
            else:
                fraction = (self.turn_count - 1) / (self.total_turns - 1)
            threshold = self.my_total * (0.8 - 0.8 * fraction)
            
            # Accept any offer on the last turn (since rejection gives 0)
            if self.turn_count == self.total_turns:
                threshold = -1
            
            if offer_value >= threshold:
                return None
        
        # Generate our counter-offer
        # Calculate target value for our offer: linear decrease from 90% to 50%
        if self.total_turns == 1:
            offer_fraction = 0.5
        else:
            offer_fraction = 0.9 - 0.4 * (self.turn_count - 1) / (self.total_turns - 1)
        offer_target = max(0, min(offer_fraction * self.my_total, self.my_total))
        
        # Start with maximum value split (take all valuable items)
        my_split = [self.counts[i] if self.values[i] > 0 else 0 for i in range(len(self.counts))]
        current_value = self.my_total
        
        # Adjust split to meet target by giving up least valuable items first
        if current_value > offer_target and self.sorted_items:
            need_to_give = current_value - offer_target
            for val, idx in self.sorted_items:
                if need_to_give <= 0:
                    break
                available = my_split[idx]
                if available == 0:
                    continue
                
                # Give as many as possible without exceeding need_to_give
                max_possible = min(available, int(need_to_give // val))
                if max_possible > 0:
                    my_split[idx] -= max_possible
                    current_value -= max_possible * val
                    need_to_give -= max_possible * val
                
                # Give one more if still needed (even if it goes slightly under target)
                if need_to_give > 0 and my_split[idx] > 0:
                    my_split[idx] -= 1
                    current_value -= val
                    need_to_give -= val
        
        # Avoid repeating the same offer as last time
        if self.last_offer is not None and my_split == self.last_offer and self.sorted_items:
            for val, idx in self.sorted_items:
                if my_split[idx] > 0:
                    my_split[idx] -= 1
                    current_value -= val
                    break
        
        # Update last offer and return
        self.last_offer = my_split.copy()
        return my_split