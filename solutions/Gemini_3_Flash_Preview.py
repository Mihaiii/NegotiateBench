class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_turns = max_rounds * 2
        self.current_turn = 0
        self.total_value = sum(c * v for c, v in zip(counts, values))
        
        # Priority for items based on my own valuation (highest value first)
        self.pref_indices = sorted(
            range(len(counts)),
            key=lambda i: self.values[i],
            reverse=True
        )

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.current_turn += 1
        # Calculate how many turns are strictly remaining AFTER this one
        turns_remaining = self.total_turns - self.current_turn
        
        # 1. EVALUATE PARTNER'S OFFER
        if o is not None:
            offer_val = sum(o[i] * self.values[i] for i in range(len(o)))
            
            # Acceptance Logic
            # On the very last turn, accept anything > 0. 0 is better than a walk-away if total is 0.
            if turns_remaining == 0:
                if offer_val > 0 or self.total_value == 0:
                    return None
            
            # Dynamic threshold that lowers as the deadline approaches
            progress = self.current_turn / self.total_turns
            if progress < 0.2:
                threshold = 0.95 * self.total_value
            elif progress < 0.5:
                threshold = 0.8 * self.total_value
            elif progress < 0.8:
                threshold = 0.7 * self.total_value
            else:
                # Be willing to take slightly more than half toward the end
                threshold = 0.55 * self.total_value

            if offer_val >= threshold and offer_val > 0:
                return None

        # 2. CONSTRUCT COUNTER-OFFER
        # We start by demanding high and slowly concede.
        # target_ratio slides from 1.0 to 0.6
        progress = self.current_turn / self.total_turns
        target_ratio = 1.0 - (0.4 * progress)
        # Never aim below 50% voluntarily unless it's the absolute last chance
        min_voluntary_ratio = 0.5 if turns_remaining > 1 else 0.1
        target_val = max(target_ratio * self.total_value, self.total_value * min_voluntary_ratio)
        
        my_offer = [0] * len(self.counts)
        current_val = 0
        
        # Greedily take items according to preference until target reached
        for i in self.pref_indices:
            for _ in range(self.counts[i]):
                if current_val < target_val:
                    my_offer[i] += 1
                    current_val += self.values[i]
                else:
                    break
        
        # 3. STRATEGIC CONCESSION (The "Sweetener")
        # Top-performing partners often won't accept if they get literally nothing.
        # If we currently have everything, and there are items we don't value (0 pts),
        # or items worth very little, give them away to entice the partner.
        if sum(my_offer) == sum(self.counts):
            # Try to give away objects with 0 value first
            given_away = False
            for i in reversed(self.pref_indices):
                if my_offer[i] > 0 and self.values[i] == 0:
                    my_offer[i] -= 1
                    given_away = True
                    break
            
            # If we value everything, give away one of the least valuable items if we still have a lot
            if not given_away and sum(my_offer) > 1:
                # Concede one least-valuable item if it's past the halfway point in rounds
                if progress > 0.5:
                    idx = self.pref_indices[-1]
                    if my_offer[idx] > 0:
                        my_offer[idx] -= 1

        # Final check: Don't return an empty offer if we can avoid it
        if sum(my_offer) == 0:
            my_offer[self.pref_indices[0]] = self.counts[self.pref_indices[0]]
                
        return my_offer