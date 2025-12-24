import math

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.counts = counts
        self.values = values
        self.num_types = len(counts)
        
        # Game state tracking
        self.turn = 0
        self.total_turns = max_rounds * 2
        self.total_value = sum(c * v for c, v in zip(counts, values))
        
        # Opponent model: Initialize with my values as a prior
        self.opp_values = [float(v) for v in values]

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn += 1
        turns_left = self.total_turns - self.turn
        
        # 1. Process incoming offer
        if o is not None:
            self._update_model(o)
            
            offer_value_to_me = sum(self.values[i] * o[i] for i in range(self.num_types))
            
            # Acceptance Strategy
            # If it's the last turn, accept any positive offer to avoid getting 0
            if turns_left == 0:
                if offer_value_to_me > 0:
                    return None
            else:
                # Dynamic threshold: Starts at ~50%, drops as turns decrease
                # This allows us to accept "fair" deals early and avoid breakdown
                progress = 1.0 - (turns_left / self.total_turns)
                threshold = self.total_value * (0.5 - 0.4 * progress)
                
                if offer_value_to_me >= threshold:
                    return None

        # 2. Generate Counter-Offer
        return self._generate_offer(turns_left)

    def _update_model(self, offer: list[int]):
        """Updates estimated opponent values based on their offer."""
        for i in range(self.num_types):
            kept = self.counts[i] - offer[i]
            given = offer[i]
            
            # Heuristic: They likely value items they keep, and value less items they give
            self.opp_values[i] += kept
            self.opp_values[i] -= given * 0.5
            
            # Prevent values from dropping to zero to avoid division errors
            if self.opp_values[i] < 0.1:
                self.opp_values[i] = 0.1
        
        # Normalize so total estimated value matches the known total value
        current_sum = sum(self.opp_values[i] * self.counts[i] for i in range(self.num_types))
        if current_sum > 0:
            factor = self.total_value / current_sum
            for i in range(self.num_types):
                self.opp_values[i] *= factor

    def _generate_offer(self, turns_left: int) -> list[int]:
        """Generates a demand maximizing value for self based on efficiency."""
        # Determine target value. Start greedy (70%), concede to 10% by the end.
        fraction_remaining = turns_left / self.total_turns
        target_fraction = 0.1 + 0.6 * fraction_remaining
        target_val = self.total_value * target_fraction
        
        # Prioritize items with high MyValue / OpponentValue ratio
        # This helps maximize my gain while conceding items valuable to the opponent
        efficiencies = []
        for i in range(self.num_types):
            if self.opp_values[i] < 1e-9:
                eff = float('inf')
            else:
                eff = self.values[i] / self.opp_values[i]
            efficiencies.append((eff, i))
            
        efficiencies.sort(key=lambda x: x[0], reverse=True)
        
        my_demand = [0] * self.num_types
        current_val = 0.0
        
        for eff, idx in efficiencies:
            if current_val >= target_val:
                break
                
            count_avail = self.counts[idx]
            val_per_unit = self.values[idx]
            
            if val_per_unit == 0:
                continue
            
            needed_units = (target_val - current_val) / val_per_unit
            
            if needed_units >= count_avail:
                take = count_avail
            else:
                take = math.ceil(needed_units)
                if take > count_avail:
                    take = count_avail
            
            my_demand[idx] = take
            current_val += take * val_per_unit
            
        return my_demand