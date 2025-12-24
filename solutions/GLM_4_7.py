import math

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.counts = counts
        self.values = values
        self.num_types = len(counts)
        self.total_turns = max_rounds * 2
        self.turns_left = self.total_turns
        
        # Calculate total value for me
        self.total_value = sum(c * v for c, v in zip(counts, values))
        
        # Initialize opponent model: uniform distribution normalized to total_value
        # We know the opponent's total value equals ours.
        if sum(counts) > 0:
            self.opp_values = [float(self.total_value) / sum(counts) for _ in range(self.num_types)]
        else:
            self.opp_values = [0.0] * self.num_types

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turns_left -= 1
        
        # Process opponent's offer
        if o is not None:
            my_val = sum(self.values[i] * o[i] for i in range(self.num_types))
            self._update_model(o)
            
            # Last turn: Accept anything positive (0 is better than disagreement)
            if self.turns_left == 0:
                return None if my_val > 0 else None
            
            # Acceptance criterion:
            # Accept if the offer is better than or equal to what we expect to get 
            # if we continue to the next round.
            future_target = self._get_target(self.turns_left - 1)
            
            # Small tolerance (1%) to encourage agreement and reduce friction
            if my_val >= future_target * 0.99:
                return None
        
        # Generate counter-offer
        target_val = self._get_target(self.turns_left)
        return self._generate_offer(target_val)

    def _get_target(self, turns: int) -> float:
        """
        Calculate target value based on remaining turns.
        Strategy: Start high (~95%) and decay to ~20%.
        Uses a square root curve to hold firm longer.
        """
        if turns < 0:
            turns = 0
            
        time_left = turns / self.total_turns
        # Interpolate between 0.20 and 0.95
        target_ratio = 0.20 + 0.75 * (time_left ** 0.5)
        return self.total_value * target_ratio

    def _generate_offer(self, target_val: float) -> list[int]:
        """
        Generates a Pareto-efficient offer.
        We maximize the opponent's value subject to us getting at least target_val.
        This is done by giving away items with the highest (Opponent Value / My Value) ratio.
        """
        offer = self.counts[:]
        current_val = self.total_value
        
        if current_val <= target_val:
            return offer
        
        # Calculate efficiency scores: (Opponent Value) / (My Value)
        # Higher score = Better to give to opponent (low cost to me, high gain to them)
        items = []
        for i in range(self.num_types):
            my_v = self.values[i]
            opp_v = self.opp_values[i]
            
            if my_v == 0:
                eff = float('inf') # Free to give
            else:
                eff = opp_v / my_v if opp_v > 0 else 0
                
            items.append((eff, i))
            
        # Sort by efficiency descending (give away best items first)
        items.sort(key=lambda x: x[0], reverse=True)
        
        # Greedily give items to meet target
        for eff, i in items:
            if current_val <= target_val:
                break
                
            if self.values[i] == 0:
                offer[i] = 0
                continue
            
            to_shed = current_val - target_val
            max_shed = self.counts[i] * self.values[i]
            
            if max_shed <= to_shed:
                offer[i] = 0
                current_val -= max_shed
            else:
                count_needed = math.ceil(to_shed / self.values[i])
                offer[i] -= count_needed
                current_val -= count_needed * self.values[i]
                
        return offer

    def _update_model(self, offer: list[int]):
        """
        Update opponent value estimates.
        If opponent kept an item, increase its estimated value.
        If opponent gave an item, decrease its estimated value.
        """
        learning_rate = 0.5
        
        for i in range(self.num_types):
            kept = self.counts[i] - offer[i]
            given = offer[i]
            
            if kept > given:
                self.opp_values[i] *= (1 + learning_rate * 0.1)
            elif given > kept:
                self.opp_values[i] *= (1 - learning_rate * 0.1)
        
        # Renormalize to maintain total value constraint
        curr_total = sum(self.opp_values[i] * self.counts[i] for i in range(self.num_types))
        if curr_total > 0:
            factor = self.total_value / curr_total
            self.opp_values = [v * factor for v in self.opp_values]