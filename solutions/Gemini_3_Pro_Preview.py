import random

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_turns = max_rounds * 2
        
        # Current turn index: Starts at 0 (if me=0) or 1 (if me=1), increments by 2
        self.current_turn = me
        
        self.max_val = sum(c * v for c, v in zip(counts, values))
        
        # Opponent modeling: Store lists of what opponent wanted (Total - Offered to me)
        self.opp_history_demands = []
        self.best_offer_val = 0
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        # 1. Update Opponent Model & Parse Offer
        if o is not None:
            # o is what partner offers ME.
            # Determine what partner WANTS for themselves: Total - Offered
            opp_wants = [self.counts[i] - o[i] for i in range(len(self.counts))]
            self.opp_history_demands.append(opp_wants)
            
            val_offered = sum(q * v for q, v in zip(o, self.values))
            self.best_offer_val = max(self.best_offer_val, val_offered)
        else:
            val_offered = 0
            
        # 2. Check Acceptance Conditions
        turns_left = self.total_turns - 1 - self.current_turn
        
        if o is not None:
            # A. Last Turn Absolute Safety
            # If I allow the negotiation to fail on the last turn, we both get 0.
            # I must accept anything positive.
            if turns_left == 0:
                if val_offered > 0 or self.max_val == 0:
                    return None
            
            # B. Target-based Acceptance
            target = self._get_target_value(turns_left)
            if val_offered >= target:
                return None
                
            # C. Panic Mode / Near Deadline
            # If 2 turns or fewer left, accept any reasonably good deal (>65% max)
            # to avoid accidental collisions or stubbornness failures.
            if turns_left <= 2 and val_offered >= self.max_val * 0.65:
                return None
                
        # 3. Formulate Counter-Offer
        target = self._get_target_value(turns_left)
        my_proposal = self._build_knapsack_proposal(target)
        
        # D. Rationality Check
        # If the proposal I generated is worth LESS to me than what they just offered,
        # I should just accept their offer.
        my_proposal_val = sum(q * v for q, v in zip(my_proposal, self.values))
        if o is not None and val_offered >= my_proposal_val:
            return None
            
        # Update state for next turn
        self.current_turn += 2
        return my_proposal

    def _get_target_value(self, turns_left: int) -> int:
        # Calculate negotiation progress (0.0 start -> 1.0 deadline)
        turns_passed = self.current_turn
        progress = turns_passed / max(1, self.total_turns - 1)
        
        # Concession Curve Strategy
        if progress < 0.2:
            f = 1.0 # Phase 1: Hold firm
        elif progress < 0.8:
            # Phase 2: Linear descent from 1.0 down to 0.75
            p = (progress - 0.2) / 0.6
            f = 1.0 - (0.25 * p)
        else:
            # Phase 3: End game descent 0.75 -> 0.50
            p = (progress - 0.8) / 0.2
            f = 0.75 - (0.25 * p)
            
        target = int(self.max_val * f)
        # Always try to get at least 1 unit of value if possible
        return max(1, target)

    def _build_knapsack_proposal(self, target: int) -> list[int]:
        # Estimate opponent interest using weighted recency
        opp_interest = [0.0] * len(self.counts)
        weight_sum = 0.0
        
        if self.opp_history_demands:
            for i, demands in enumerate(reversed(self.opp_history_demands)):
                # Decay factor: recent rounds count more
                w = 0.85 ** i
                weight_sum += w
                for k in range(len(demands)):
                    opp_interest[k] += demands[k] * w
            for k in range(len(opp_interest)):
                opp_interest[k] /= weight_sum
                
        # Create list of individual item units with their efficiency scores
        candidates = []
        for i in range(len(self.counts)):
            my_v = self.values[i]
            
            # Efficiency = My Value / Opponent Cost
            # Add small epsilon to cost to avoid division by zero
            # Note: opp_interest[i] is roughly the count they demand on average.
            cost = opp_interest[i] + 0.05
            
            # If I value it 0, efficiency is 0. 
            # I shouldn't take it unless needed, but generally good to give to opponent.
            efficiency = my_v / cost
            
            # Add tiny noise for predictable tie-breaking prevention
            efficiency += random.uniform(0, 1e-6)
            
            for _ in range(self.counts[i]):
                candidates.append((efficiency, i, my_v))
        
        # Sort by efficiency descending (Best items for ME to keep)
        candidates.sort(key=lambda x: x[0], reverse=True)
        
        proposal = [0] * len(self.counts)
        current_val = 0
        
        # Greedy selection until target is met
        for eff, idx, val in candidates:
            if current_val < target:
                proposal[idx] += 1
                current_val += val
            else:
                # Target met. Stop taking items.
                # Leaving the rest improves chances opponent accepts.
                break
                
        return proposal