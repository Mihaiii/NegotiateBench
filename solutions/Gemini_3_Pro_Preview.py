class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.n = len(counts)
        self.total_val = sum(c * v for c, v in zip(counts, values))
        
        # Opponent modeling: Frequency of kept items
        self.opp_kept_sum = [0] * self.n
        self.turns_seen = 0
        
        self.my_turn_idx = 0

    def get_opp_vals(self):
        # Estimate opponent values proportional to keep frequency
        raw = []
        for i in range(self.n):
            # Bayesian smoothing: (kept + 1) / (observed_total + 2)
            # observed_total is turns_seen * count[i]
            denom = self.turns_seen * self.counts[i] + 2 if self.counts[i] > 0 else 1
            prob = (self.opp_kept_sum[i] + 1) / denom
            raw.append(prob)
            
        # Normalize estimates so their total value matches mine (Symmetry Assumption)
        s = sum(c * v for c, v in zip(self.counts, raw))
        if s > 1e-9:
            factor = self.total_val / s
            return [r * factor for r in raw]
        else:
            return [1.0] * self.n

    def get_pareto(self, opp_vals):
        # Generate Pareto frontier using greedy efficiency metric (MyVal / OppVal)
        items = []
        for i in range(self.n):
            vm, vo = self.values[i], opp_vals[i]
            # Avoid division by zero
            ratio = vm / (vo + 1e-9)
            items.append({'i': i, 'eff': ratio, 'vm': vm, 'vo': vo, 'c': self.counts[i]})
        
        # Sort items by efficiency descending (best for Me)
        items.sort(key=lambda x: x['eff'], reverse=True)
        
        frontier = []
        cur_counts = [0] * self.n
        cur_m = 0
        cur_o = self.total_val # Opponent starts with assumed theoretical max (everything)
        
        # Point 0: I take nothing
        frontier.append({'c': list(cur_counts), 'm': cur_m, 'o': cur_o})
        
        # Greedily add items to my bundle
        for item in items:
            idx = item['i']
            for _ in range(item['c']):
                cur_counts[idx] += 1
                cur_m += item['vm']
                cur_o -= item['vo']
                frontier.append({'c': list(cur_counts), 'm': cur_m, 'o': cur_o})
        return frontier

    def offer(self, o: list[int] | None) -> list[int] | None:
        if o:
            self.turns_seen += 1
            # o is what "I" receive. Opponent kept (counts - o).
            for i in range(self.n):
                self.opp_kept_sum[i] += (self.counts[i] - o[i])

        # Calculate current global turn index (0 to 2*max_rounds - 1)
        curr_global_turn = self.my_turn_idx * 2 + self.me
        turns_left = (self.max_rounds * 2) - curr_global_turn
        
        opp_vals = self.get_opp_vals()
        val_o = sum(x * v for x, v in zip(o, self.values)) if o else 0
        frontier = self.get_pareto(opp_vals)

        # --- Acceptance Logic ---
        if o:
            # Player 1 Last Turn: Ultimatum received.
            # Rejecting means 0 for both. Accepting > 0 is rational.
            if turns_left == 1:
                return None 

            # Calculate Dynamic Target
            progress = curr_global_turn / (self.max_rounds * 2)
            # Aspiration curve: 100% -> 75% -> 55%
            # Gently concede from "I want all" to "Fair split"
            if progress < 0.8:
                f = 1.0 - (progress * 0.3) # 1.0 to 0.76
            else:
                # 0.76 to 0.55 fast concession in end game
                f = 0.76 - ((progress - 0.8) / 0.2) * 0.21
            
            # Floor target at 55% of total value to ensure decent deal, 
            # but allow dropping near 50% implicitly via Nash checks.
            target = max(self.total_val * 0.55, self.total_val * f)
            
            # Find approximate Nash point (max product of utilities)
            nash = max(frontier, key=lambda x: x['m'] * max(0, x['o']))
            
            # Acceptance conditions
            if val_o >= target: return None
            # If offer is very close to Fair (Nash), accept
            if val_o >= nash['m'] * 0.95: return None
            # Safety valve: if very late and offer is reasonable (>60%), take it
            if turns_left <= 4 and val_o >= self.total_val * 0.6: return None

        # --- Counter-Offer Logic ---
        self.my_turn_idx += 1
        
        # Player 0 Last Turn: Send Ultimatum
        # Maximize my gain such that Opponent > 0 (Rational)
        if turns_left == 2:
            cands = [p for p in frontier if p['o'] > 0]
            if not cands: cands = frontier
            return max(cands, key=lambda x: x['m'])['c']

        # Normal Turn: Proposal Logic
        # Update target for proposal (similar to acceptance)
        progress = (curr_global_turn + 1) / (self.max_rounds * 2)
        if progress < 0.8:
            f = 1.0 - (progress * 0.3)
        else:
            f = 0.76 - ((progress - 0.8) / 0.2) * 0.21
        target = max(self.total_val * 0.55, self.total_val * f)

        # Select candidates satisfying target
        cands = [p for p in frontier if p['m'] >= target]
        if not cands:
            # If target too high, fall back to maximizing my value
            cands = [max(frontier, key=lambda x: x['m'])]
        
        # Strategy: Pick the candidate that maximizes Opponent's utility
        # This increases the probability of them accepting.
        best_offer = max(cands, key=lambda x: x['o'])
        
        return best_offer['c']