class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_turns = max_rounds * 2
        self.current_turn = 0
        self.total_value = sum(c * v for c, v in zip(counts, values))
        
        # Sort items by efficiency (value per unit, though here units are 1)
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
            
            # Acceptance logic
            # On the last turn, accept anything > 0 (or even 0 if total is 0) 
            # to avoid the zero-payout outcome.
            if turns_remaining <= 0:
                if offer_val > 0 or self.total_value == 0:
                    return None
            
            # Dynamic threshold decreases as time runs out
            progress = self.current_turn / self.total_turns
            if progress < 0.25:
                threshold = 0.9 * self.total_value
            elif progress < 0.5:
                threshold = 0.8 * self.total_value
            elif progress < 0.8:
                threshold = 0.7 * self.total_value
            else:
                # Close to the end: accept lower offers to ensure a deal
                threshold = 0.5 * self.total_value
            
            if offer_val >= max(threshold, 1):
                return None

        # 2. CONSTRUCT COUNTER-OFFER
        # Determine a target value based on progress
        # Start by asking for ~100% and concede down to ~60% naturally
        progress = self.current_turn / self.total_turns
        target_ratio = max(0.6, 1.0 - (0.5 * progress))
        
        # In the final round for us, if we are the second mover, we might need to be extra flexible
        if turns_remaining <= 1:
            target_ratio = 0.5
            
        target_val = target_ratio * self.total_value
        
        my_offer = [0] * len(self.counts)
        accumulated_val = 0
        
        # Greedy selection for our offer
        for i in self.pref_indices:
            for _ in range(self.counts[i]):
                if accumulated_val < target_val:
                    my_offer[i] += 1
                    accumulated_val += self.values[i]
                else:
                    break

        # 3. STRATEGIC CONCESSION ("The Sweetener")
        # Ensure the partner gets at least something if possible, 
        # especially items we value at 0.
        partner_gets_nothing = True
        for i in range(len(self.counts)):
            if self.counts[i] - my_offer[i] > 0:
                partner_gets_nothing = False
                break
        
        if partner_gets_nothing:
            # Give away all items that are worth 0 to us
            for i in range(len(self.counts)):
                if self.values[i] == 0:
                    my_offer[i] = 0
            
            # Check again
            still_nothing = (sum(my_offer) == sum(self.counts))
            if still_nothing and sum(my_offer) > 0:
                # Concede the least valuable item to break the stalemate
                idx = self.pref_indices[-1]
                if my_offer[idx] > 0:
                    my_offer[idx] -= 1

        # Final sanity check: never return an empty list or total zero if we have items
        if sum(my_offer) == 0 and self.total_value > 0:
            my_offer[self.pref_indices[0]] = 1
                
        return my_offer