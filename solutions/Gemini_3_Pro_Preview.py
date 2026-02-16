import random

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me  # 0: First player, 1: Second player
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.n = len(counts)
        self.total_val = sum(c * v for c, v in zip(counts, values))
        
        # Round state tracking
        self.round_idx = 0 
        
        # Opponent modeling: Frequency of items opponent kept for themselves
        # Used to infer their valuation
        self.opp_demands = [0] * self.n

    def offer(self, o: list[int] | None) -> list[int] | None:
        # --- 1. Round & State Update ---
        if o is None:
            # I am P1 starting the game (Round 1, Turn 1)
            self.round_idx = 1
        else:
            # Analyze opponent's offer to infer their preferences
            # 'o' is what they offer ME. Thus they kept `counts - o`.
            for i in range(self.n):
                kept = self.counts[i] - o[i]
                if kept > 0:
                    self.opp_demands[i] += kept
            
            # Increment Round Counter logic
            if self.me == 0:
                # I am P1. I made an offer, Opp countered. Now it's the next round.
                self.round_idx += 1
            else:
                # I am P2. Opp made an offer. 
                # If first time called, it is Round 1. Otherwise increment.
                if self.round_idx == 0:
                    self.round_idx = 1
                else:
                    self.round_idx += 1

        # Calculate the value of the offer to me
        val_me = 0
        if o is not None:
            val_me = sum(o[i] * self.values[i] for i in range(self.n))

        # --- 2. Acceptance Decisions ---
        if o is not None:
            # A. P2 Forced Acceptance in Last Round (Ultimatum Response)
            # If I (P2) reject in the last turn, the game ends and I get 0.
            # Rational move is to accept provided the result isn't worse than 0.
            if self.me == 1 and self.round_idx == self.max_rounds:
                return None 
            
            # B. P1 Pre-Ultimatum Logic (Round N, Turn 1)
            # I have the "Last Mover" advantage in the next turn (Ultimatum).
            # Only accept if the offer is near-perfect/better than what I expect from an ultimatum.
            if self.me == 0 and self.round_idx == self.max_rounds:
                if val_me >= int(self.total_val * 0.98):
                    return None
            
            # C. Standard Rounds Acceptance
            # Check if offer meets the dynamic threshold
            threshold_frac = self._get_threshold(self.round_idx)
            if val_me >= int(self.total_val * threshold_frac):
                return None
            
            # Always accept max possible value
            if val_me == self.total_val:
                return None

        # --- 3. Counter-Offer Generation ---
        
        # A. P1 Ultimatum (Last Round)
        # Offer bare minimum to opponent to secure deal -> maximize own profit.
        if self.me == 0 and self.round_idx == self.max_rounds:
            return self._build_ultimatum()
            
        # B. P2 Penultimate Round Strategy (Pre-empting Ultimatum)
        # I need to offer P1 something good enough (fair-ish) so they don't crush me next turn.
        # Aiming for ~60% ensures decent profit while reducing risk.
        if self.me == 1 and self.round_idx == self.max_rounds - 1:
            return self._build_greedy_offer(target_frac=0.60)
            
        # C. Standard Negotiation
        # Ask for slightly more than threshold to allow haggling room.
        target_frac = self._get_threshold(self.round_idx) * 1.05
        # Clamp between 20% and 100%
        target_frac = min(1.0, max(0.2, target_frac))
        
        return self._build_greedy_offer(target_frac)

    def _get_threshold(self, r: int) -> float:
        # Linear decay pattern of expectations from 1.0 down to ~0.65
        if self.max_rounds <= 1:
            return 0.6
        progress = (r - 1) / (self.max_rounds - 1)
        start, end = 1.0, 0.65
        return start - (start - end) * progress

    def _build_greedy_offer(self, target_frac: float) -> list[int]:
        # Construct an offer that gives me roughly `target_val` 
        # while keeping items I prefer (Ratio: MyValue / OppInterest)
        
        target_val = int(self.total_val * target_frac)
        proposal = [0] * self.n
        current_val = 0
        
        priorities = []
        for i in range(self.n):
            if self.counts[i] == 0: 
                continue
            
            # Opponent interest metric (smoothed)
            opp_interest = 1.0 + self.opp_demands[i]
            
            # If my value is 0, efficient to give it away (priority = 0)
            if self.values[i] == 0:
                prio = 0.0
            else:
                prio = self.values[i] / opp_interest
                
            # Add small noise to prevent deterministic loops
            prio *= random.uniform(0.98, 1.02)
            priorities.append((prio, i))
            
        # Sort descending (We want to KEEP high priority items)
        priorities.sort(key=lambda x: x[0], reverse=True)
        
        # Fill knapsack
        for _, idx in priorities:
            if self.values[idx] == 0: continue # Don't take trash
            
            count = self.counts[idx]
            needed = target_val - current_val
            
            if needed <= 0: break
            
            # Calculate how many to take
            take = (needed + self.values[idx] - 1) // self.values[idx]
            take = min(take, count)
            
            proposal[idx] += take
            current_val += take * self.values[idx]
            
        return proposal

    def _build_ultimatum(self) -> list[int]:
        # Strategy: Keep everything, but give opponent 1 item they seem to value most.
        # This capitalizes on Last Mover Advantage for P1.
        proposal = list(self.counts)
        
        # Evaluate which item is best to give up (Cost-Benefit Analysis)
        # Metric: Maximize (OpponentGain / MyLoss)
        # OpponentGain is estimated via demand history.
        candidates = []
        for i in range(self.n):
            if self.counts[i] > 0:
                opp_gain = self.opp_demands[i] + 0.1
                my_loss = self.values[i] + 0.01
                
                efficiency = opp_gain / my_loss
                efficiency *= random.uniform(0.99, 1.01)
                candidates.append((efficiency, i))
        
        candidates.sort(key=lambda x: x[0], reverse=True)
        
        # Give 1 unit of the best candidate to the opponent
        if candidates:
            best_give_idx = candidates[0][1]
            proposal[best_give_idx] -= 1
            
        return proposal