class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_turns = max_rounds * 2
        self.current_turn = 0
        self.total_value = sum(c * v for c, v in zip(counts, values))
        
        # Priority: Items with most value to me
        self.pref_indices = sorted(
            range(len(counts)),
            key=lambda i: self.values[i],
            reverse=True
        )

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.current_turn += 1
        
        # Remaining turns for me (including this one)
        turns_left = self.total_turns - self.current_turn
        
        # 1. Evaluate incoming offer
        if o is not None:
            offer_val = sum(o[i] * self.values[i] for i in range(len(o)))
            
            # Acceptance Logic:
            # If it's the very last turn of the game, accept anything > 0 (or any if total is 0)
            if turns_left == 0:
                if offer_val > 0 or self.total_value == 0:
                    return None
            
            # Dynamic Threshold: 
            # Early: Demand 90%+ 
            # Middle: Demand 75-80%
            # Late: Demand 60-70%
            progress = self.current_turn / self.total_turns
            if progress < 0.3:
                threshold = 0.9 * self.total_value
            elif progress < 0.7:
                threshold = 0.8 * self.total_value
            else:
                threshold = 0.6 * self.total_value

            if offer_val >= threshold and offer_val > 0:
                return None

        # 2. Construct Counter-Offer
        # We start by demanding high and slowly concede items the partner might want.
        # Target value decreases as time runs out.
        target_ratio = max(0.6, 1.0 - (0.4 * (self.current_turn / self.total_turns)))
        target_val = target_ratio * self.total_value
        
        my_offer = [0] * len(self.counts)
        acc_val = 0
        
        # Fill offer with most valuable items first
        for i in self.pref_indices:
            num_to_take = self.counts[i]
            # If item is worthless to us, don't take it unless we need it to reach a value
            # Actually, better to leave worthless items for the partner as "concessions"
            if self.values[i] == 0:
                continue
                
            for _ in range(num_to_take):
                if acc_val < target_val:
                    my_offer[i] += 1
                    acc_val += self.values[i]
                else:
                    break
        
        # If it's our last turn to propose (turn 2*max_rounds - 1) and we are the first player,
        # or if it's the second-to-last turn overall, ensure we don't ask for everything 
        # to maximize the chance of a last-second "Accept".
        if turns_left <= 1:
            # Ensure we leave at least one item (preferably one we value at 0)
            # if we are currently asking for everything.
            if acc_val == self.total_value and self.total_value > 0:
                # Remove the least valuable item we currently hold
                for i in reversed(self.pref_indices):
                    if my_offer[i] > 0:
                        my_offer[i] -= 1
                        acc_val -= self.values[i]
                        break

        # Final safety: If offer is effectively empty but there is value, take one item.
        if sum(my_offer) == 0 and self.total_value > 0:
            my_offer[self.pref_indices[0]] = 1
                    
        return my_offer