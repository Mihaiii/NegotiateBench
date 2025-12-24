import random

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        # 'me' is 0 (Player 1) or 1 (Player 2)
        self.me = me
        self.counts = counts
        self.values = values
        self.rounds = max_rounds
        self.total_turns = max_rounds * 2
        # Track the global turn index: 0, 1, 2, ...
        self.current_turn = me 
        self.total_value = sum(c * v for c, v in zip(counts, values))
        
        # Preferencing Model: Track how many items opponent consistently keeps
        # to infer their valuation and build efficient offers.
        self.opp_kept = [0] * len(counts)

    def offer(self, o: list[int] | None) -> list[int] | None:
        if o is not None:
            # 1. Update Opponent Model
            # If they offered me X, they kept (Total - X).
            for i, offered_qty in enumerate(o):
                kept_qty = self.counts[i] - offered_qty
                self.opp_kept[i] += kept_qty

            # 2. Evaluate Offer
            val_offered = sum(q * v for q, v in zip(o, self.values))
            
            # --- Panic Strategy (Player 2, Final Turn) ---
            # If I am Player 2 and this is the absolute last turn, a rejection/counter
            # means no agreement (score 0). I must accept anything > 0.
            if self.me == 1 and self.current_turn == self.total_turns - 1:
                if val_offered > 0:
                    return None
            
            # --- Standard Acceptance ---
            target = self._get_target_value()
            if val_offered >= target:
                return None

        # --- Generate Counter-Offer ---
        
        # Re-evaluate target as we are now active (making a demand)
        target = self._get_target_value()
        
        # --- Gambit Strategy (Player 1, Penultimate Turn) ---
        # If I am P1 on my last move, P2 will face a "take it or leave it" decision next.
        # I demand maximum value (essentially everything), relying on _build_proposal 
        # to leave a single high-value "crumb" for P2 to incentivize acceptance.
        is_gambit = (self.me == 0 and self.current_turn == self.total_turns - 2)
        if is_gambit:
            target = self.total_value

        proposal = self._build_proposal(target)
        
        # Advance turn counter (my turn + opponent's turn = 2 interactions processed)
        self.current_turn += 2
        
        return proposal

    def _get_target_value(self) -> int:
        if self.total_turns == 0:
            return 0
        
        # Normalized time progress: 0.0 (start) -> 1.0 (end)
        progress = self.current_turn / max(1, self.total_turns - 1)
        
        # Concession Curve:
        # 0.00 - 0.20: Hold firm at 100% (Signal strength)
        # 0.20 - 0.80: Linear concession to 60% (Negotiation zone)
        # 0.80 - 1.00: Drop to 55% (Agreement zone - close to fair split)
        
        if progress < 0.2:
            factor = 1.0
        elif progress < 0.8:
            slope = (0.6 - 1.0) / (0.8 - 0.2)
            factor = 1.0 + slope * (progress - 0.2)
        else:
            slope = (0.55 - 0.6) / (1.0 - 0.8)
            factor = 0.6 + slope * (progress - 0.8)
            
        target = int(self.total_value * factor)
        # Ensure we always ask for at least something if total value is positive
        return max(1, target) if self.total_value > 0 else 0

    def _build_proposal(self, target: int) -> list[int]:
        """
        Builds a proposal trying to meet 'target' value for self, 
        prioritizing items the opponent seemingly values less.
        """
        # Heuristic: Priority = My Value / (1 + Opponent Interest)
        # Low opponent interest implies the item is cheap for them to concede.
        priorities = []
        for i, val in enumerate(self.values):
            if val == 0:
                p = -1.0 # Do not ask for worthless items (give to opponent)
            else:
                # Add small noise to avoid deterministic loops and break ties
                p = val / (1.0 + self.opp_kept[i]) + random.uniform(0, 1e-5)
            priorities.append((p, i))
        
        # Sort desc (Best items for me first)
        priorities.sort(key=lambda x: x[0], reverse=True)
        
        proposal = [0] * len(self.counts)
        current_val = 0
        
        # Greedy Knapsack Fill
        for p, i in priorities:
            if p < 0: continue
            
            needed = target - current_val
            if needed <= 0:
                break
            
            # Calculate quantity needed to close the value gap (ceiling division)
            count_needed = (needed + self.values[i] - 1) // self.values[i]
            to_take = min(count_needed, self.counts[i])
            
            proposal[i] += to_take
            current_val += to_take * self.values[i]
            
        # Validity Check: Ensure opponent isn't left with 0 items.
        # This is critical if we went Full Greedy (Gambit) or if target ~= total.
        opponent_has_items = any(proposal[i] < self.counts[i] for i in range(len(self.counts)))
        
        if not opponent_has_items:
            # We took 100% of physical items.
            # Give back the "least efficient" item we took.
            # (The one with lowest priority score for us, implying high opponent interest).
            # Iterate reversed (lowest priority first).
            for p, i in reversed(priorities):
                if p >= 0 and proposal[i] > 0:
                    proposal[i] -= 1
                    break
                    
        return proposal