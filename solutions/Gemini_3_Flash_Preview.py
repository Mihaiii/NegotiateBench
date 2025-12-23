class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_turns = max_rounds * 2
        self.current_turn = 0
        self.total_value = sum(c * v for c, v in zip(counts, values))
        
        # Sort indices by value density (highest value first)
        self.pref_indices = sorted(
            range(len(counts)),
            key=lambda i: self.values[i],
            reverse=True
        )

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.current_turn += 1
        
        # How many turns are left after THIS turn
        turns_remaining = self.total_turns - self.current_turn
        
        # 1. EVALUATE PARTNER'S OFFER
        if o is not None:
            offer_val = sum(o[i] * self.values[i] for i in range(len(o)))
            
            # Acceptance Logic:
            # If it's the absolute last turn, accept any value > 0
            if turns_remaining == 0:
                if offer_val > 0 or self.total_value == 0:
                    return None
            
            # Dynamic Threshold: Be stubborn early, flexible late
            # progress is 0.0 at start, 1.0 at end
            progress = self.current_turn / self.total_turns
            
            if progress < 0.2:
                threshold = 0.95 * self.total_value
            elif progress < 0.5:
                threshold = 0.85 * self.total_value
            elif progress < 0.8:
                threshold = 0.70 * self.total_value
            else:
                # In the final stretch, aim for a bit more than half
                threshold = 0.55 * self.total_value

            if offer_val >= threshold and offer_val > 0:
                return None

        # 2. CONSTRUCT COUNTER-OFFER
        # Start high, lower target value as the clock ticks
        # We start at 100% and drop towards 60%
        target_ratio = 1.0 - (0.4 * (self.current_turn / self.total_turns))
        target_val = max(target_ratio * self.total_value, 1)
        
        my_offer = [0] * len(self.counts)
        current_offer_val = 0
        
        # Strategy: Take items valuable to me first.
        # Leave items worth 0 to me for the partner (they might value them).
        for i in self.pref_indices:
            if self.values[i] == 0:
                continue
            
            for _ in range(self.counts[i]):
                if current_offer_val < target_val:
                    my_offer[i] += 1
                    current_offer_val += self.values[i]
                else:
                    break

        # 3. STRATEGIC CONCESSION
        # If we are in the last moments of negotiation, 
        # make sure the partner feels they are getting something.
        # This increases the chance they click "Accept" on our last offer.
        if turns_remaining <= 1:
            # Ensure we aren't asking for everything unless we have to
            # If our offer still captures all the value, drop one small item
            total_items_in_offer = sum(my_offer)
            total_items_available = sum(self.counts)
            
            if total_items_in_offer == total_items_available and total_items_available > 1:
                # Give away the item in our offer that is worth the LEAST to us
                for i in reversed(self.pref_indices):
                    if my_offer[i] > 0:
                        my_offer[i] -= 1
                        current_offer_val -= self.values[i]
                        break

        # Safety: If current_offer_val is 0 due to values being 0, take at least one thing
        if current_offer_val == 0 and sum(self.counts) > 0:
             my_offer[self.pref_indices[0]] = self.counts[self.pref_indices[0]]
                    
        return my_offer