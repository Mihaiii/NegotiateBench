import random

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_turns = max_rounds * 2
        self.turn_index = me 
        
        self.max_val = sum(c * v for c, v in zip(counts, values))
        
        # Opponent modeling:
        # Track effective 'cost' of items based on how often opponent keeps them.
        self.opp_kept_sum = [0] * len(counts)
        self.opp_moves = 0
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        # 1. Update Inferred Opponent Utility if an offer is received
        val_offered = 0
        if o is not None:
            self.opp_moves += 1
            for i, qty in enumerate(o):
                # Calculate what opponent kept for themselves: Total - Offered to Me
                kept = self.counts[i] - qty
                self.opp_kept_sum[i] += kept
                val_offered += qty * self.values[i]
        
        # 2. Determine Strategy (Aspiration Level)
        # Calculate progress from 0.0 (start) to 1.0 (deadline)
        progress = self.turn_index / max(1, self.total_turns - 1)
        
        # Target Curve: 
        # Phase 1 (0-20%): Hardball (100%). Establish dominance.
        # Phase 2 (20%-80%): Negotiation (Linear drop to 75%). Trade efficiency.
        # Phase 3 (80%-100%): Closing (Drop to 50%). Secure the deal.
        if progress < 0.2:
            factor = 1.0
        elif progress < 0.8:
            # Linear descent from 1.0 to 0.75 over 0.6 progress
            factor = 1.0 - 0.25 * ((progress - 0.2) / 0.6)
        else:
            # Steep descent from 0.75 to 0.50 over 0.2 progress
            factor = 0.75 - 0.25 * ((progress - 0.8) / 0.2)
            
        target = int(self.max_val * factor)
        # Always try to get at least 1 unit of value if possible
        if self.max_val > 0:
            target = max(1, target)

        # 3. Generate Proposal Plan
        # We utilize a heuristic Knapsack approach based on efficiency (MyVal / OppCost)
        proposal_bundle, proposal_val = self._build_proposal(target)

        # 4. Acceptance Logic
        if o is not None:
            turns_left = self.total_turns - 1 - self.turn_index
            
            # A. Ultimatum (Last turn for Me to act)
            # If I (P2) reject now at the very last turn, the outcome is 0 for both.
            # Rationally, accept anything > 0.
            if turns_left == 0:
                if val_offered > 0 or self.max_val == 0:
                    return None
            
            # B. Standard Acceptance
            # If the offer meets my current strategic target, accept.
            if val_offered >= target:
                return None
            
            # C. Strategic Dominance Check
            # If their offer gives me more value than what I am planning to propose back,
            # accept it immediately. Counter-offering less value is irrational.
            if val_offered >= proposal_val:
                return None
                
            # D. Late Game Compromise
            # Near the deadline (last 1-2 rounds), accept any 'good' deal (>65%)
            # to avoid the risk of the opponent walking away or random failures.
            if turns_left <= 2 and val_offered >= self.max_val * 0.65:
                return None

        # 5. Return Proposal
        self.turn_index += 2
        return proposal_bundle

    def _build_proposal(self, target: int) -> tuple[list[int], int]:
        """
        Constructs a bundle summing to >= target using greedy efficiency.
        Prioritizes items with high (My Value / Opponent Interest).
        Returns (proposal_list, actual_value_of_proposal)
        """
        proposal = [0] * len(self.counts)
        current_val = 0
        
        # 1. Expand items into individual units for granular selection
        candidates = []
        for i, count in enumerate(self.counts):
            my_v = self.values[i]
            
            # Opponent Interest: Normalized frequency of them keeping this item.
            # If they keep it often, it's "expensive" to ask for it.
            if self.opp_moves > 0:
                opp_freq = self.opp_kept_sum[i] / self.opp_moves
            else:
                opp_freq = 0.0
            
            # Efficiency Score: Value gained per unit of Opponent Resistance.
            # If I value it 0, score is negative (I want to NOT keep it, i.e. give to opponent).
            if my_v > 0:
                # Add small epsilon to denominator to handle implicit 0 freq
                score = my_v / (opp_freq + 0.05)
            else:
                score = -1.0
            
            # Add tiny noise to prevent deterministic loops in negotiation cycles
            score += random.uniform(0, 1e-5)
            
            for _ in range(count):
                candidates.append((score, i, my_v))
        
        # 2. Sort candidates by Efficiency (Highest Score = Best for Me to Keep)
        candidates.sort(key=lambda x: x[0], reverse=True)
        
        # 3. Fill Bundle Greedily
        for score, idx, v in candidates:
            if current_val < target:
                proposal[idx] += 1
                current_val += v
            else:
                # Target met. 
                # Stop taking items. Leaving the rest for the opponent increases 
                # likelihood they accept, as we are giving them "High Frequency" items.
                break
                
        return proposal, current_val