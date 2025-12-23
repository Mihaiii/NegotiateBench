class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_turns = max_rounds * 2
        self.current_turn = 0
        self.total_value = sum(c * v for c, v in zip(counts, values))
        
        # Priority for items based on my own valuation
        self.pref_indices = sorted(
            range(len(counts)),
            key=lambda i: self.values[i],
            reverse=True
        )

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.current_turn += 1
        turns_remaining = self.total_turns - self.current_turn
        
        # 1. EVALUATE PARTNER'S OFFER
        if o is not None:
            offer_val = sum(o[i] * self.values[i] for i in range(len(o)))
            
            # Acceptance Thresholds
            # If it's the very last turn of the game, accept anything > 0 (better than nothing)
            if turns_remaining == 0:
                if offer_val > 0 or self.total_value == 0:
                    return None
            
            # Dynamic strategy: Be demanding early, more compromising late.
            # Progress through turns (0.0 to 1.0)
            progress = self.current_turn / self.total_turns
            
            # Minimum value we are willing to accept
            if progress < 0.3:
                threshold = 0.9 * self.total_value
            elif progress < 0.7:
                threshold = 0.7 * self.total_value
            elif progress < 0.9:
                threshold = 0.6 * self.total_value
            else:
                threshold = 0.5 * self.total_value

            if offer_val >= threshold and offer_val > 0:
                return None

        # 2. CONSTRUCT COUNTER-OFFER
        # Start by asking for everything, slowly lowering expectations.
        # target_ratio goes from 1.0 down to ~0.65
        target_ratio = 1.0 - (0.35 * (self.current_turn / self.total_turns))
        target_val = max(target_ratio * self.total_value, self.total_value * 0.5)
        
        my_offer = [0] * len(self.counts)
        current_val = 0
        
        # Fill offer with most valuable items first
        for i in self.pref_indices:
            if self.values[i] > 0:
                for _ in range(self.counts[i]):
                    if current_val < target_val:
                        my_offer[i] += 1
                        current_val += self.values[i]
                    else:
                        break
        
        # 3. STRATEGIC CONCESSION (The "Sweetener")
        # Ensure the partner sees they get something, especially on our final word.
        # If we are asking for every single item, and there's more than one item, 
        # leave them the one that is worth the LEAST to us.
        if sum(my_offer) == sum(self.counts) and sum(self.counts) > 1:
            for i in reversed(self.pref_indices):
                if my_offer[i] > 0:
                    my_offer[i] -= 1
                    current_val -= self.values[i]
                    break

        # Fallback: if we haven't selected anything (e.g., all values are 0), take something.
        if sum(my_offer) == 0:
            my_offer[self.pref_indices[0]] = self.counts[self.pref_indices[0]]
                
        return my_offer