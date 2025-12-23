class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_turns = max_rounds * 2
        self.current_turn = 0
        self.total_value = sum(c * v for c, v in zip(counts, values))
        # Sort items by value density (though density is just value here as counts are discrete)
        self.pref_indices = sorted(range(len(counts)), key=lambda i: values[i], reverse=True)

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.current_turn += 1 if o is None and self.me == 0 else 2 if o is not None else 1
        
        # Calculate how deep we are into the negotiation (0.0 to 1.0)
        progress = self.current_turn / self.total_turns
        
        if o is not None:
            offer_val = sum(o[i] * self.values[i] for i in range(len(o)))
            
            # Acceptance logic: Be stubborn early, flexible late.
            if progress < 0.2:
                threshold = 0.95 * self.total_value
            elif progress < 0.5:
                threshold = 0.85 * self.total_value
            elif progress < 0.8:
                threshold = 0.7 * self.total_value
            elif progress < 0.95:
                threshold = 0.6 * self.total_value
            else:
                # In the absolute last moments, accept any reasonable offer above 40%.
                # If it's the very last turn, accept anything > 0 to avoid total loss.
                threshold = 0.4 * self.total_value if self.current_turn < self.total_turns else 1
            
            if offer_val >= max(threshold, 1):
                return None

        # Counter-offer logic:
        # We start by demanding everything and slowly concede.
        if progress < 0.3:
            target_ratio = 1.0
        elif progress < 0.6:
            target_ratio = 0.9
        elif progress < 0.8:
            target_ratio = 0.8
        elif progress < 0.9:
            target_ratio = 0.7
        else:
            target_ratio = 0.6

        return self._create_offer(target_ratio)

    def _create_offer(self, ratio: float) -> list[int]:
        target_val = ratio * self.total_value
        my_offer = [0] * len(self.counts)
        current_val = 0
        
        # Fill offer based on our preferences
        for i in self.pref_indices:
            for _ in range(self.counts[i]):
                if current_val < target_val:
                    my_offer[i] += 1
                    current_val += self.values[i]
                else:
                    break
        
        # Ensure the partner is offered at least one item to keep them at the table
        # prioritize giving them items that are worth 0 to us.
        if sum(my_offer) == sum(self.counts):
            for i in reversed(self.pref_indices):
                if my_offer[i] > 0:
                    my_offer[i] -= 1
                    break
        
        # Final safety check: if we somehow have 0 value but the total exists, take the best item.
        if sum(m * v for m, v in zip(my_offer, self.values)) == 0 and self.total_value > 0:
            my_offer[self.pref_indices[0]] = 1
            
        return my_offer