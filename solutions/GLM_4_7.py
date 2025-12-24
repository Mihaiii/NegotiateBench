import math

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.counts = counts
        self.values = values
        self.num_types = len(counts)
        self.max_rounds = max_rounds
        self.me = me
        self.total_turns = max_rounds  # Number of our turns
        self.turns_left = self.total_turns
        self.turn = 0
        
        # Calculate total value for us
        self.total_value = sum(c * v for c, v in zip(counts, values))
        
        # Initialize opponent model: uniform distribution
        if sum(counts) > 0:
            self.opp_values = [float(self.total_value) / sum(counts) for _ in range(self.num_types)]
        else:
            self.opp_values = [0.0] * self.num_types
            
        # Track opponent's offers for better inference
        self.opp_offers = []

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turns_left -= 1
        self.turn += 1
        
        # Process opponent's offer
        if o is not None:
            my_val = sum(self.values[i] * o[i] for i in range(self.num_types))
            self.opp_offers.append(o[:])
            self._update_model(o)
            
            # Last turn: accept anything positive (better than disagreement)
            if self.turns_left == 0:
                return None if my_val > 0 else self.counts[:]
            
            # Check if we should accept based on value and timing
            if self._should_accept(o, my_val):
                return None
        
        # Generate counter-offer
        return self._generate_offer()

    def _should_accept(self, o: list[int], my_val: float) -> bool:
        """Determine whether to accept the opponent's offer."""
        # Accept if we get at least half (fair split)
        if my_val >= self.total_value / 2:
            return True
        
        # Calculate opponent's estimated value from the offer
        opp_gets = [self.counts[i] - o[i] for i in range(self.num_types)]
        opp_val = sum(self.opp_values[i] * opp_gets[i] for i in range(self.num_types))
        
        # Accept if opponent is getting a very good deal (they might walk away)
        if opp_val >= self.total_value * 0.7:
            return True
        
        # Time pressure: lower standards as deadline approaches
        time_pressure = 1 - (self.turns_left / self.total_turns)
        
        # Minimum acceptable ratio: starts at 45%, goes to 40%
        min_accept = 0.45 - 0.05 * time_pressure
        
        if my_val >= self.total_value * min_accept:
            return True
        
        return False

    def _generate_offer(self) -> list[int]:
        """Generate a Pareto-efficient counter-offer targeting our desired value."""
        time_pressure = 1 - (self.turns_left / self.total_turns)
        
        # Target ratio: starts at 65%, decays to 50%
        target_ratio = 0.65 - 0.15 * time_pressure
        target_val = self.total_value * target_ratio
        
        # Start with all items
        offer = self.counts[:]
        current_val = self.total_value
        
        if current_val <= target_val:
            return offer
        
        # Calculate efficiency scores: (Opponent Value) / (My Value)
        # Higher efficiency = better to give to opponent (low cost to us, high value to them)
        items = []
        for i in range(self.num_types):
            my_v = self.values[i]
            opp_v = self.opp_values[i]
            
            if my_v == 0:
                eff = float('inf')  # Free to give
            else:
                eff = opp_v / my_v if opp_v > 0 else 0
                
            items.append((eff, i))
            
        # Sort by efficiency descending (give away most efficient first)
        items.sort(key=lambda x: x[0], reverse=True)
        
        # Greedily give items to meet target value
        for eff, i in items:
            if current_val <= target_val:
                break
                
            if self.values[i] == 0:
                offer[i] = 0
                continue
            
            to_shed = current_val - target_val
            max_shed = self.counts[i] * self.values[i]
            
            if max_shed <= to_shed:
                # Give all of this item type
                offer[i] = 0
                current_val -= max_shed
            else:
                # Give only what we need to shed
                count_needed = math.ceil(to_shed / self.values[i])
                offer[i] -= count_needed
                current_val -= count_needed * self.values[i]
                
        return offer

    def _update_model(self, offer: list[int]):
        """Update opponent value estimates based on their offer pattern."""
        learning_rate = 0.3
        
        for i in range(self.num_types):
            kept = self.counts[i] - offer[i]
            given = offer[i]
            
            # If opponent kept more of item X, increase its estimated value
            if kept > given:
                self.opp_values[i] *= (1 + learning_rate * 0.15)
            # If opponent gave away more of item X, decrease its estimated value
            elif given > kept:
                self.opp_values[i] *= (1 - learning_rate * 0.15)
        
        # Renormalize to maintain total value constraint
        curr_total = sum(self.opp_values[i] * self.counts[i] for i in range(self.num_types))
        if curr_total > 0:
            factor = self.total_value / curr_total
            self.opp_values = [v * factor for v in self.opp_values]