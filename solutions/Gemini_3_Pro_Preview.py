class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.total_turns = max_rounds * 2
        
        # Track current turn index (0-indexed). 
        # me=0 (First player) plays turns 0, 2, ...
        # me=1 (Second player) plays turns 1, 3, ...
        self.current_turn = me
        
        # Calculate total potential value for myself
        self.val_max = sum(c * v for c, v in zip(counts, values))
        
        # Create a flattened list of items as (value, type_index) tuples
        # and sort them by value descending. This helps in greedy selection.
        self.items = []
        for i, val in enumerate(values):
            if val > 0:
                self.items.extend([(val, i)] * counts[i])
        self.items.sort(key=lambda x: x[0], reverse=True)

    def offer(self, o: list[int] | None) -> list[int] | None:
        if o:
            # Calculate the value of the offer to me
            val_offered = sum(o[i] * self.values[i] for i in range(len(self.counts)))
            
            # Special Endgame Logic for Player 2 (Second Mover)
            # If this is the absolute last turn of the game, rejecting implies 0 payoff.
            # Therefore, rationally accept any offer that gives positive value.
            if self.me == 1 and self.current_turn >= self.total_turns - 1:
                if val_offered > 0:
                    return None
            
            # Standard Acceptance Logic
            # Accept if the offer meets our current target aspirational value
            if val_offered >= self._get_target():
                return None

        # If not accepted, generate a counter-offer
        target = self._get_target()
        my_offer = [0] * len(self.counts)
        current_sum = 0
        
        # Greedy Strategy: Fill my basket with my most valuable items until target is met.
        # This implicitly gives the partner the items I value least (which they might value high).
        for val, idx in self.items:
            if current_sum < target:
                my_offer[idx] += 1
                current_sum += val
            else:
                break
        
        # Increment turn counter for the next time this method is called
        self.current_turn += 2
        return my_offer

    def _get_target(self):
        # Calculate 'progress' of negotiations (0.0 to 1.0)
        # Using max(1, ...) to prevent division by zero in edge cases
        progress = self.current_turn / max(1, self.total_turns - 1)
        
        # Concession Curve
        if progress < 0.5:
            # First half: Hold firm at 100% (High Aspiration)
            factor = 1.0
        elif progress < 0.8:
            # 50% - 80%: Linear concession from 100% to 85%
            # Normalized progress x in [0, 1]
            x = (progress - 0.5) / 0.3
            factor = 1.0 - (0.15 * x)
        else:
            # Last 20%: Rapid concession from 85% to 50% (Fair Split)
            x = (progress - 0.8) / 0.2
            factor = 0.85 - (0.35 * x)
            
        return int(self.val_max * factor)