import random

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_turns = max_rounds * 2
        
        # Track turn state: 
        # If me=0 (P1), turns are 0, 2, 4... | If me=1 (P2), turns are 1, 3, 5...
        self.turn_index = me 
        
        self.total_value = sum(c * v for c, v in zip(counts, values))
        
        # Opponent modeling: 
        # Track the cumulative count of each item type the opponent has KEPT.
        # This helps estimate what they value most.
        self.opp_kept_sum = [0] * len(counts)

    def offer(self, o: list[int] | None) -> list[int] | None:
        if o is not None:
            # 1. Update Opponent Model
            # 'o' is what they offer ME. Therefore, they keep (counts - o).
            val_offered_to_me = 0
            for i, qty_offered in enumerate(o):
                kept = self.counts[i] - qty_offered
                self.opp_kept_sum[i] += kept
                val_offered_to_me += qty_offered * self.values[i]
            
            # 2. Acceptance Logic
            
            # Endgame Safety (Player 2, Final Turn T-1)
            # If I reject here, the negotiation fails (Outcome: 0, 0). 
            # Rationally, I must accept any offer that gives me > 0 value.
            if self.turn_index == self.total_turns - 1:
                # Accept if I get anything positive, or if the total pot is 0.
                if val_offered_to_me > 0 or self.total_value == 0:
                    return None
            
            # Standard Acceptance
            # Accept if the offer meets my current strategic target value.
            current_target = self._get_target()
            if val_offered_to_me >= current_target:
                return None

        # 3. Generate Counter-Offer Proposal
        
        proposal_target = self._get_target()
        
        # Build proposal using a granular Knapsack-like heuristic
        proposal = self._build_proposal(proposal_target)
        
        # Advance internal turn counter for the next invocation
        self.turn_index += 2
        
        return proposal

    def _get_target(self) -> int:
        """
        Determines the minimum value I want to achieve at the current stage.
        Uses a time-based function to remain firm initially and concede later.
        """
        # Calculate negotiation progress (0.0 to 1.0)
        # Use (total_turns - 1) so the final turn aligns with 1.0
        if self.total_turns <= 1: 
            return 0
        progress = self.turn_index / (self.total_turns - 1)
        
        # Strategy Curve:
        # Phase 1 (0.00 - 0.40): Hardball (100%). Establish position/Signal strength.
        # Phase 2 (0.40 - 0.80): Negotiation (Linear drop to 75%).
        # Phase 3 (0.80 - 0.95): Closing (Steep drop to 60%).
        # Phase 4 (0.95 - 1.00): Deal (Floor at 51%).
        
        if progress < 0.4:
            factor = 1.0
        elif progress < 0.8:
            # Linear 1.0 -> 0.75
            slope = (0.75 - 1.0) / (0.8 - 0.4)
            factor = 1.0 + slope * (progress - 0.4)
        elif progress < 0.95:
             # Linear 0.75 -> 0.60
            slope = (0.60 - 0.75) / (0.95 - 0.8)
            factor = 0.75 + slope * (progress - 0.8)
        else:
            # Absolute floor for the final desperation move
            factor = 0.51
            
        target = int(self.total_value * factor)
        
        # Always desire at least 1 if the pot is not empty
        if self.total_value > 0:
            return max(1, target)
        return 0

    def _build_proposal(self, target: int) -> list[int]:
        """
        Constructs a bundle of items for myself that sums to >= target.
        Prioritizes items with high (My Value / Opponent Interest).
        """
        # Decompose counts into individual item units for granular selection.
        # Each unit candidate tuple: (Priority Score, Item Index, My Value)
        candidates = []
        for i, count in enumerate(self.counts):
            my_val = self.values[i]
            # Opponent Cost heuristic: Cumulative count of this item kept by opponent.
            # Higher 'opp_cost' means they fight harder for it.
            opp_cost = self.opp_kept_sum[i]
            
            # Efficiency Score: Value I gain per unit of opponent "pain".
            # Add 1.0 to denominator for stabilization.
            if my_val > 0:
                score = my_val / (opp_cost + 1.0)
            else:
                score = -1.0 # Worthless to me -> Lowest priority (give to opponent)
            
            # Add small noise to prevent deterministic loops in stalemates
            score += random.uniform(0, 1e-5)
            
            for _ in range(count):
                candidates.append((score, i, my_val))
                
        # Sort candidates: Best efficiency (High MyVal / Low OppCost) first.
        candidates.sort(key=lambda x: x[0], reverse=True)
        
        proposal = [0] * len(self.counts)
        current_val = 0
        
        # Greedy Fill
        for score, idx, val in candidates:
            # Stop if we hit the target
            if current_val >= target:
                break
                
            proposal[idx] += 1
            current_val += val
            
        return proposal