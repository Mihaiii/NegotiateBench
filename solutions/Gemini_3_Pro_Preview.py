import random

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.num_items = len(counts)
        self.round_cnt = 0
        
        # Opponent modeling: Track accumulated kept amount by opponent to infer preference
        self.opp_kept_sum = [0] * self.num_items
        self.opp_offers_count = 0

    def offer(self, o: list[int] | None) -> list[int] | None:
        # --- 1. Round Tracking ---
        if o is None:
            # P1 starts the game (Round 1)
            self.round_cnt = 1
        else:
            if self.me == 0:
                # P1 receives counter from P2 -> New Round
                self.round_cnt += 1
            else:
                # P2 receives offer from P1 -> Update Round
                if self.round_cnt == 0:
                    self.round_cnt = 1
                else:
                    self.round_cnt += 1

        # --- 2. Update Opponent Model ---
        offer_val_me = 0
        if o is not None:
            offer_val_me = sum(o[i] * self.values[i] for i in range(self.num_items))
            # Opponent offered 'o' to me, meaning they kept 'counts - o'
            self.opp_offers_count += 1
            for i in range(self.num_items):
                kept = self.counts[i] - o[i]
                if kept > 0:
                    self.opp_kept_sum[i] += kept

        # --- 3. Acceptance Logic ---
        if o is not None:
            # A. Optimal or near-optimal deal
            if offer_val_me >= self.total_value:
                return None
            
            # B. P2 Last Turn Check (Rationality)
            # If I (P2) reject in the very last round, the game ends with 0 for both.
            # Accept anything > 0.
            if self.me == 1 and self.round_cnt == self.max_rounds:
                if offer_val_me > 0:
                    return None
            
            # C. P1 Pre-Ultimatum Check
            # If I (P1) reject in the final round, I make an Ultimatum.
            # I should only accept the current offer if it matches or beats my expected Ultimatum return.
            if self.me == 0 and self.round_cnt == self.max_rounds:
                my_ultimatum = self._make_ultimatum()
                my_ultimatum_val = sum(my_ultimatum[i] * self.values[i] for i in range(self.num_items))
                if offer_val_me >= my_ultimatum_val:
                    return None
                
            # D. Dynamic Concession Curve
            # Normalized progress 0.0 -> 1.0 throughout the rounds
            progress = (self.round_cnt - 1) / max(1, self.max_rounds - 1)
            
            thresh_start = 1.0
            thresh_end = 0.65 
            
            # If P2 is approaching the Ultimatum round, lower threshold to secure a deal
            if self.me == 1 and self.round_cnt >= self.max_rounds - 1:
                thresh_end = 0.55
                
            threshold = thresh_start - (thresh_start - thresh_end) * (progress ** 2)
            
            if offer_val_me >= int(threshold * self.total_value):
                return None

        # --- 4. Counter-Offer Generation ---
        
        # A. P1 Ultimatum (Last Move)
        if self.me == 0 and self.round_cnt == self.max_rounds:
            return self._make_ultimatum()

        # B. Standard Offer Generation
        progress = (self.round_cnt - 1) / max(1, self.max_rounds - 1)
        target_start = 1.0
        target_end = 0.70
        
        # P2 Penultimate Round: Offer a tempting 50/50 split to avoid P1's Ultimatum
        if self.me == 1 and self.round_cnt == self.max_rounds - 1:
            target_frac = 0.50
        else:
            target_frac = target_start - (target_start - target_end) * (progress ** 1.5)
            
        target_val = int(target_frac * self.total_value)
        return self._build_greedy_offer(target_val)

    def _make_ultimatum(self) -> list[int]:
        # Strategy: Keep everything, but give opponent 1 item they seem to value most.
        # This entices a rational opponent to accept (>0) while maximizing my profit.
        best_item = -1
        max_score = -float('inf')
        
        indices = list(range(self.num_items))
        random.shuffle(indices) # Break ties randomly
        
        for i in indices:
            if self.counts[i] > 0:
                # Heuristic: maximize Opponent Interest (history) - MyCost (value)
                score = self.opp_kept_sum[i] * 1000 - self.values[i]
                if score > max_score:
                    max_score = score
                    best_item = i
        
        proposal = list(self.counts)
        if best_item != -1:
            proposal[best_item] -= 1
            
        return proposal

    def _build_greedy_offer(self, target_val: int) -> list[int]:
        # Sort items by Efficiency: MyValue / OpponentInterest
        candidates = []
        for i in range(self.num_items):
            if self.counts[i] == 0: continue
            
            opp_interest = self.opp_kept_sum[i] + 0.1
            ratio = self.values[i] / opp_interest
            # Add small noise to avoid deterministic loops
            ratio *= random.uniform(0.98, 1.02)
            candidates.append((ratio, i))
            
        # Highest efficiency first
        candidates.sort(key=lambda x: x[0], reverse=True)
        
        proposal = [0] * self.num_items
        current_val = 0
        
        for _, idx in candidates:
            if current_val >= target_val:
                break
                
            total_available = self.counts[idx]
            
            # If I value the item, take as many as needed to reach target
            if self.values[idx] > 0:
                needed = target_val - current_val
                # Ceiling division for integer count
                count_needed = (needed + self.values[idx] - 1) // self.values[idx]
                take = min(total_available, count_needed)
            else:
                # If I don't value it, don't take it (effectively giving it to opponent)
                take = 0
            
            proposal[idx] += take
            current_val += take * self.values[idx]
            
        return proposal