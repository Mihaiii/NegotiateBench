class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.turn_count = 0
        self.total_turns = max_rounds * 2
        
        # Calculate total possible value
        self.total_value = sum(c * v for c, v in zip(counts, values))
        
        # Pre-sort items by value density (though quantity is 1 unit here)
        # to decide which items to "give away" first.
        self.items_by_value = sorted(
            range(len(counts)), 
            key=lambda i: self.values[i], 
            reverse=True
        )

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn_count += 1
        
        # 1. Evaluate the incoming offer (if it's not the first turn)
        if o is not None:
            offer_value = sum(o[i] * self.values[i] for i in range(len(o)))
            
            # Acceptance Logic: 
            # Be stubborn early, but become more flexible as the deadline approaches.
            # turn_ratio goes from ~0 to 1
            turn_ratio = self.turn_count / self.total_turns
            
            # Acceptance threshold starts at 90% and drops to 70%, 
            # then drops sharply to 50% on the very last turn.
            if turn_ratio < 0.5:
                threshold = 0.9 * self.total_value
            elif turn_ratio < 0.8:
                threshold = 0.8 * self.total_value
            elif self.turn_count == self.total_turns:
                # Last turn: take anything better than nothing (or at least half)
                threshold = 0.5 * self.total_value
            else:
                threshold = 0.7 * self.total_value

            if offer_value >= threshold:
                return None

        # 2. Formulate a counter-offer
        # Logic: We want to keep items that are valuable to us.
        # As rounds progress, we are willing to concede item types that are less valuable.
        
        remaining_turns_ratio = 1 - (self.turn_count / self.total_turns)
        # Target value to keep: starts at 100%, drops towards 60%
        target_value = (0.6 + 0.4 * remaining_turns_ratio) * self.total_value
        
        my_offer = [0] * len(self.counts)
        current_val = 0
        
        # Fill offer with most valuable items first until we hit target_value
        for i in self.items_by_value:
            for _ in range(self.counts[i]):
                if current_val < target_value or self.values[i] > 0:
                    # On the first half of turns, try to keep everything valuable
                    if self.turn_count < self.max_rounds and self.values[i] > 0:
                        my_offer[i] += 1
                        current_val += self.values[i]
                    # Later, only keep if we haven't hit the target
                    elif current_val < target_value:
                        my_offer[i] += 1
                        current_val += self.values[i]
        
        # Safety check: if the offer is empty and we have items, give a minimal demand
        if sum(my_offer) == 0:
            my_offer[self.items_by_value[0]] = 1
            
        return my_offer