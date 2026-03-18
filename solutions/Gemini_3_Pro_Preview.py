import random

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.n_items = len(counts)
        self.total_val = sum(c * v for c, v in zip(counts, values))
        
        # Negotiation State
        self.round_idx = 0
        
        # Opponent Modeling
        # Cumulative sum of items the opponent decided to KEEP in their offers.
        # High value implies high opponent desire.
        self.opp_kept_sum = [0] * self.n_items
        self.opp_moves_count = 0

    def offer(self, o: list[int] | None) -> list[int] | None:
        # --- 1. State Maintenance ---
        if o is None:
            # Player 1 starts the game (Round 1)
            self.round_idx = 1
        else:
            # Process Opponent's Offer
            # `o` is the list of items offered to ME. 
            # Therefore, opponent kept `self.counts - o`.
            for i in range(self.n_items):
                kept_by_opp = self.counts[i] - o[i]
                if kept_by_opp > 0:
                    self.opp_kept_sum[i] += kept_by_opp
            self.opp_moves_count += 1
            
            # Increment Round Counter
            if self.me == 0:
                # I am P1. Opponent countered. Now it's the start of the next round for me.
                self.round_idx += 1
            else:
                # I am P2. Opponent made an offer.
                # If first move received, it's Round 1. Else increment.
                if self.round_idx == 0:
                    self.round_idx = 1
                else:
                    self.round_idx += 1

        # --- 2. Calculate Value of Current Offer ---
        val_me = 0
        if o is not None:
            val_me = sum(o[i] * self.values[i] for i in range(self.n_items))

        # --- 3. Acceptance Logic ---
        if o is not None:
            # A. Ultimatum Scenario (Player 2, Last Turn)
            # If I (P2) reject in the very last turn of the game, I get 0.
            # Rational move: Accept anything > 0.
            if self.me == 1 and self.round_idx == self.max_rounds:
                if val_me > 0 or self.total_val == 0:
                    return None
            
            # B. Standard Rounds Acceptance
            # Calculate a dynamic acceptance threshold based on time remaining.
            progress = (self.round_idx - 1) / max(1, self.max_rounds - 1)
            
            # Decay curve parameters
            start_frac = 1.0
            # P1 can afford to be stricter (0.7) because they have the last move.
            # P2 should be more flexible (0.6) to settle before the ultimatum.
            end_frac = 0.7 if self.me == 0 else 0.6
            
            # Linear decay
            threshold_frac = start_frac - (start_frac - end_frac) * progress
            threshold_val = int(self.total_val * threshold_frac)
            
            if val_me >= threshold_val:
                return None
            
            # Immediate acceptance if we get everything (or full value)
            if val_me == self.total_val:
                return None

        # --- 4. Counter-Offer Generation ---
        
        # A. Player 1 Ultimatum (Start of Last Round)
        # Use specific logic to squeeze maximum value while securing a deal.
        if self.me == 0 and self.round_idx == self.max_rounds:
            return self._generate_ultimatum()
            
        # B. Standard Greedy Strategy
        # Ask for slightly more than our threshold to leave room for haggling.
        target_frac = 1.0 - 0.3 * (self.round_idx / self.max_rounds)
        target_frac = max(0.7 if self.me == 0 else 0.65, target_frac)
        
        return self._generate_greedy_offer(target_frac)

    def _generate_greedy_offer(self, target_frac: float) -> list[int]:
        target_val = int(self.total_val * target_frac)
        proposal = [0] * self.n_items
        current_val = 0
        
        # Prioritize items based on Benefit/Cost ratio.
        # Benefit: My Utility. Cost: Opponent Utility (inferred from frequency).
        priorities = []
        for i in range(self.n_items):
            if self.counts[i] == 0: continue
            
            # If item is worthless to me, ignore it (effectively giving it to opponent)
            if self.values[i] == 0: continue
            
            opp_interest = self.opp_kept_sum[i] / max(1, self.opp_moves_count)
            # Add small epsilon to avoid division by zero
            score = self.values[i] / (opp_interest + 0.1)
            
            # Add tiny noise to prevent deterministic loops in negotiation
            score *= random.uniform(0.99, 1.01)
            priorities.append((score, i))
            
        priorities.sort(key=lambda x: x[0], reverse=True)
        
        # Fill proposal greedily
        for _, i in priorities:
            if current_val >= target_val:
                break
            
            # Take all available of this type
            take = self.counts[i]
            proposal[i] = take
            current_val += take * self.values[i]
            
        return proposal

    def _generate_ultimatum(self) -> list[int]:
        # Start by taking everything
        proposal = list(self.counts)
        
        # 1. Give up all items that have 0 value to me
        for i in range(self.n_items):
            if self.values[i] == 0:
                proposal[i] = 0
                
        # 2. Check if we have already given something the opponent wants
        # (i.e., a 0-value item for me which they have kept in the past)
        given_opp_val = False
        for i in range(self.n_items):
            opp_gets = self.counts[i] - proposal[i]
            if opp_gets > 0 and self.opp_kept_sum[i] > 0:
                given_opp_val = True
                
        # 3. If we haven't given anything they signaled interest in, give minimal bribe.
        # Find the item with the best (Opponent Interest / My Value) ratio.
        if not given_opp_val:
            candidates = []
            for i in range(self.n_items):
                if proposal[i] > 0:
                    my_cost = self.values[i]
                    opp_gain = self.opp_kept_sum[i]
                    ratio = opp_gain / (my_cost + 0.001)
                    candidates.append((ratio, i))
            
            candidates.sort(key=lambda x: x[0], reverse=True)
            
            if candidates:
                best_idx = candidates[0][1]
                proposal[best_idx] -= 1
                
        return proposal