class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.turn_count = 0
        self.total_turns = max_rounds * 2
        self.total_value = sum(c * v for c, v in zip(counts, values))
        
        # Sort indices by personal value (high to low)
        self.pref_indices = sorted(
            range(len(counts)), 
            key=lambda i: self.values[i], 
            reverse=True
        )

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn_count += 1
        
        # current_turn is 1-indexed relative to total available turns
        # If me=0, turns are 1, 3, 5... (self.total_turns - 1)
        # If me=1, turns are 2, 4, 6... self.total_turns
        
        # 1. EVALUATE PARTNER'S OFFER
        if o is not None:
            offer_val = sum(o[i] * self.values[i] for i in range(len(o)))
            
            # Acceptance threshold logic based on progress
            progress = self.turn_count / self.total_turns
            
            if progress > 0.95:
                # Absolute last chance - accept if we get at least 60%
                threshold = 0.60 * self.total_value
            elif progress > 0.8:
                threshold = 0.75 * self.total_value
            elif progress > 0.5:
                threshold = 0.85 * self.total_value
            else:
                threshold = 0.95 * self.total_value
                
            if offer_val >= threshold and offer_val > 0:
                return None

        # 2. CONSTRUCT COUNTER-OFFER
        # Calculate a target value we want to keep
        # Starts high (100%) and decays slowly to ~70%
        remaining_ratio = (self.total_turns - self.turn_count) / self.total_turns
        target_percent = 0.7 + (0.3 * (remaining_ratio ** 2))
        target_val = target_percent * self.total_value
        
        my_offer = [0] * len(self.counts)
        accumulated_val = 0
        
        # Greedily take items starting from most valuable
        for i in self.pref_indices:
            if self.values[i] == 0:
                continue
            
            # How many can we take?
            for _ in range(self.counts[i]):
                # Always take if we haven't reached target val
                # Or if it's early in the game, try to hold onto everything valuable
                if accumulated_val < target_val or remaining_ratio > 0.5:
                    my_offer[i] += 1
                    accumulated_val += self.values[i]
                else:
                    break
        
        # Corner case: Ensure we actually ask for something if we have values
        if sum(my_offer) == 0 and self.total_value > 0:
            for i in self.pref_indices:
                if self.values[i] > 0:
                    my_offer[i] = 1
                    break
        
        # Last turn safety: if we are me=0 and it's our last word (turn_count == total-1)
        # or me=1 (turn_count == total), make sure the offer is realistic
        if self.turn_count >= self.total_turns - 1:
            # If our "greedy" offer is still the total value, give one low-value item away
            if accumulated_val >= self.total_value and self.total_value > 0:
                for i in reversed(self.pref_indices):
                    if my_offer[i] > 0:
                        my_offer[i] -= 1
                        break

        return my_offer