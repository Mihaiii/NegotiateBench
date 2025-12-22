class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_turns = max_rounds * 2
        self.current_turn = 0
        self.total_value = sum(c * v for c, v in zip(counts, values))
        
        # Sort indices by personal value density
        self.pref_indices = sorted(
            range(len(counts)),
            key=lambda i: self.values[i],
            reverse=True
        )

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.current_turn += 1
        
        # 1. Evaluate incoming offer
        if o is not None:
            offer_val = sum(o[i] * self.values[i] for i in range(len(o)))
            
            # Progress represents normalized time remaining
            # In very last turn (current_turn == total_turns), we must be pragmatic.
            progress = self.current_turn / self.total_turns
            
            # Dynamic thresholding: Start demanding 95%, drop to 65% at the absolute end.
            if progress > 0.98:
                threshold = 0.65 * self.total_value
            elif progress > 0.9:
                threshold = 0.75 * self.total_value
            elif progress > 0.7:
                threshold = 0.85 * self.total_value
            else:
                threshold = 0.95 * self.total_value
            
            # Accept if it meets threshold and has at least some value
            if offer_val >= threshold and (offer_val > 0 or self.total_value == 0):
                return None

        # 2. Construct Counter-Offer
        # Calculate how much we want to demand
        # Slowly decrease from 100% to ~75% based on time
        demand_ratio = 1.0 - (0.25 * (self.current_turn / self.total_turns))
        target_val = demand_ratio * self.total_value
        
        my_offer = [0] * len(self.counts)
        current_val = 0
        
        # Take everything that has value until target is reached
        for i in self.pref_indices:
            if self.values[i] > 0:
                for _ in range(self.counts[i]):
                    if current_val < target_val:
                        my_offer[i] += 1
                        current_val += self.values[i]
                    else:
                        break
        
        # Strategic concession: if it's the very last turn and we are greedy,
        # drop one item of the lowest nonzero value to entice the partner.
        if self.current_turn >= self.total_turns - 1:
            # If we still have a "perfect" offer, give away the least valuable item we hold
            if current_val >= self.total_value and self.total_value > 0:
                for i in reversed(self.pref_indices):
                    if my_offer[i] > 0:
                        my_offer[i] -= 1
                        current_val -= self.values[i]
                        break

        # Safety check: ensure the offer is at least 1 item if possible
        if sum(my_offer) == 0 and self.total_value > 0:
            for i in self.pref_indices:
                if self.values[i] > 0:
                    my_offer[i] = 1
                    break
                    
        return my_offer