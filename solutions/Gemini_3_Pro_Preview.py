import random

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_turns = max_rounds * 2
        
        # Turn tracking: 
        # If me=0: 0, 2, 4... | If me=1: 1, 3, 5...
        self.turn = me
        
        self.total_value = sum(c * v for c, v in zip(counts, values))
        
        # Opponent modeling: Track how many items opponent consistently KEEPS
        # to infer their high-value items.
        self.opp_kept_sum = [0] * len(counts)

    def offer(self, o: list[int] | None) -> list[int] | None:
        if o is not None:
            # 1. Update Opponent Model
            val_offered = 0
            for i, qty in enumerate(o):
                kept = self.counts[i] - qty
                self.opp_kept_sum[i] += kept
                val_offered += qty * self.values[i]

            # 2. Endgame Acceptance Logic
            
            # --- Panic Strategy (Player 2, Final Turn T-1) ---
            # If I reject here, the game ends with 0 for both. Accept anything > 0.
            if self.turn == self.total_turns - 1:
                if val_offered > 0:
                    return None
            
            # --- Gambit Defense (Player 1, Turn T-2) ---
            # I am about to make my final offer (Ultimatum). P2 will respond.
            # If P2 rejects, I get 0. To de-risk, accept if offer is strong (>= 75%).
            if self.turn == self.total_turns - 2:
                if val_offered >= self.total_value * 0.75:
                    return None
            
            # --- Standard Acceptance ---
            target = self._get_target()
            if val_offered >= target:
                return None

        # --- Generate Counter-Offer ---
        
        demand_target = self._get_target()
        
        # --- Gambit Offense (Player 1, Turn T-2) ---
        # It's the last offer I can make. Ask for nearly everything.
        if self.turn == self.total_turns - 2:
            demand_target = self.total_value

        proposal = self._build_proposal(demand_target)
        
        # Prepare turn counter for next interaction
        self.turn += 2
        return proposal

    def _get_target(self) -> int:
        if self.total_turns == 0:
            return 0
        
        # Normalized time progress: 0.0 (start) -> 1.0 (end)
        progress = self.turn / max(1, self.total_turns - 1)
        
        # Concession Curve strategy:
        # 0.0 - 0.5: Hold firm at 100% (Signal strength)
        # 0.5 - 0.9: Linear concession to 65% (Negotiation zone)
        # 0.9 - 1.0: Drop to 55% (Endgame safety buffer)
        
        if progress < 0.5:
            factor = 1.0
        elif progress < 0.9:
            slope = (0.65 - 1.0) / (0.9 - 0.5)
            factor = 1.0 + slope * (progress - 0.5)
        else:
            slope = (0.55 - 0.65) / (1.0 - 0.9)
            factor = 0.65 + slope * (progress - 0.9)
            
        target = int(self.total_value * factor)
        # Always allow accepting/asking for something > 0
        return max(1, target) if self.total_value > 0 else 0

    def _build_proposal(self, target: int) -> list[int]:
        """
        Constructs a bundle of items worth >= target.
        Prioritizes items with high (My Value / Opponent Interest).
        """
        priorities = []
        for i, val in enumerate(self.values):
            if val == 0:
                # Worthless to me: give to opponent to increase acceptance chance
                p = -1.0 
            else:
                # Priority: My Value vs. How much they fight for it
                # Add noise to prevent deterministic loops
                p = (val / (1.0 + self.opp_kept_sum[i])) + random.uniform(0, 1e-5)
            priorities.append((p, i))
        
        # Best items first
        priorities.sort(key=lambda x: x[0], reverse=True)
        
        proposal = [0] * len(self.counts)
        current_val = 0
        
        # 1. Greedy Fill
        for p, i in priorities:
            if p < 0: continue
            
            if current_val >= target:
                break
                
            # Take all available of this type
            proposal[i] = self.counts[i]
            current_val += self.counts[i] * self.values[i]
            
        # 2. Refinement: If we overshot target, give back items to aid opponent.
        # We start giving back from the lowest priority items we actually took.
        if current_val > target:
            # Filter for items we took, reversed to start with lowest priority
            taken_indices = []
            for p, i in reversed(priorities):
                if p >= 0 and proposal[i] > 0:
                    taken_indices.append(i)
            
            for i in taken_indices:
                if current_val <= target:
                    break
                val_i = self.values[i]
                
                # Calculate how many we can drop while staying >= target
                diff = current_val - target
                can_drop = diff // val_i
                
                drop_amt = min(proposal[i], can_drop)
                proposal[i] -= drop_amt
                current_val -= drop_amt * val_i

        # 3. Gambit Safety: If this is the Ultimatum (P1, T-2), 
        # ensure we don't take 100% of physical items, leaving at least 1 crumb.
        if self.turn == self.total_turns - 2:
            total_items = sum(self.counts)
            my_items = sum(proposal)
            if my_items == total_items:
                # Give back 1 unit of the item I value least (among taken)
                # which is likely the one the opponent values most.
                for p, i in reversed(priorities):
                    if proposal[i] > 0:
                        proposal[i] -= 1
                        break
                        
        return proposal