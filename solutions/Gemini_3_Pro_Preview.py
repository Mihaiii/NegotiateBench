import random

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.rounds = max_rounds
        self.total_turns = max_rounds * 2
        # current_turn tracks the global turn index (0, 1, 2...)
        # me=0 moves on turns 0, 2, 4...; me=1 moves on turns 1, 3, 5...
        self.current_turn = me
        self.total_value = sum(c * v for c, v in zip(counts, values))
        
        # Track cumulative count of items kept by opponent in their offers to infer their preferences.
        self.opp_kept = [0] * len(counts)

    def offer(self, o: list[int] | None) -> list[int] | None:
        if o is not None:
            # Update opponent model: what they didn't give me, they kept.
            for i, quantity_given in enumerate(o):
                kept_qty = self.counts[i] - quantity_given
                self.opp_kept[i] += kept_qty
            
            # Calculate the value of the offer to me
            val_offered = sum(q * v for q, v in zip(o, self.values))
            
            # --- Panic Strategy (Player 2 only) ---
            # If I am Player 2 and this is the absolute last turn of the game, 
            # I must accept any non-zero value to avoid the "walking away" (0-0) outcome.
            if self.me == 1 and self.current_turn >= self.total_turns - 1:
                if val_offered > 0:
                    return None
            
            # --- Standard Acceptance Logic ---
            target = self._get_target_value()
            if val_offered >= target:
                return None

        # --- Construct Counter-Offer ---
        
        # Determine aspiration level for this turn
        target = self._get_target_value()
        
        # --- Gambit Strategy (Player 1 only) ---
        # If I am Player 1 and this is my last chance to speak (second-to-last turn),
        # I aim high but ensure I leave a "crumb" for Player 2 to panic-accept in the final turn.
        is_gambit = (self.me == 0 and self.current_turn >= self.total_turns - 2)
        if is_gambit:
            target = self.total_value

        proposal = self._build_proposal(target, is_gambit)
        
        # Increment turn counter for next interaction (my turn + opponent's turn = 2 steps)
        self.current_turn += 2
        
        return proposal

    def _get_target_value(self) -> int:
        if self.total_turns == 0:
            return 0
        
        # Normalized progress from 0.0 (start) to 1.0 (end)
        progress = self.current_turn / max(1, self.total_turns - 1)
        
        # Concession Curve Strategy:
        # 0.0 - 0.5: Hold 100% (Signal strength phase)
        # 0.5 - 0.9: Drop linearly to 70% (Negotiation phase)
        # 0.9 - 1.0: Drop steeply to 50% (Agreement phase)
        
        if progress < 0.5:
            factor = 1.0
        elif progress < 0.9:
            # Map range 0.5..0.9 to factor 1.0..0.7
            slope = (0.7 - 1.0) / (0.9 - 0.5) 
            factor = 1.0 + slope * (progress - 0.5)
        else:
            # Map range 0.9..1.0 to factor 0.7..0.5
            slope = (0.5 - 0.7) / (1.0 - 0.9)
            factor = 0.7 + slope * (progress - 0.9)
            
        target = int(self.total_value * factor)
        # Always try to get at least 1, unless total value is really 0.
        return max(1, target) if self.total_value > 0 else 0

    def _build_proposal(self, target: int, is_gambit: bool) -> list[int]:
        # Heuristic: Sort items by "Efficiency" = My Value / (1 + Opponent Interest)
        # Opponent Interest is inferred from how many times they kept the item.
        # This prioritizes asking for items I want but they (seemingly) care less about.
        
        priorities = []
        for i, val in enumerate(self.values):
            if val == 0:
                p = -1.0 # Never request worthless items for ourselves
            else:
                # Add small random noise to break ties and prevent loops
                p = val / (1.0 + self.opp_kept[i]) + random.uniform(0, 1e-5)
            priorities.append((p, i))
        
        # Sort descending by priority
        priorities.sort(key=lambda x: x[0], reverse=True)
        
        proposal = [0] * len(self.counts)
        current_val = 0
        
        # Greedy Knapsack Fill
        for p, i in priorities:
            if p < 0: continue
            
            needed = target - current_val
            if needed <= 0:
                break
            
            # Take as many items of type 'i' as needed/available
            amount_needed = (needed + self.values[i] - 1) // self.values[i] # ceiling division
            amount_to_take = min(amount_needed, self.counts[i])
            
            proposal[i] += amount_to_take
            current_val += amount_to_take * self.values[i]
            
        # Gambit Logic Adjustment
        if is_gambit:
            # If we took EVERYTHING, the opponent gets nothing and might reject (resulting in 0-0).
            # We must verify we left something on the table.
            
            # Check if any items are left for opponent
            # Opponent receives: self.counts[i] - proposal[i]
            anything_left = any(proposal[i] < self.counts[i] for i in range(len(self.counts)))
            
            if not anything_left:
                # We took 100% of items. Give one back.
                # To minimize loss, give back the item with the lowest priority to us 
                # (which implies high opponent interest relative to our value).
                # Iterating 'priorities' in reverse gives us the "worst" items we decided to keep.
                for p, i in reversed(priorities):
                    if p >= 0 and proposal[i] > 0:
                        proposal[i] -= 1
                        break
                        
        return proposal