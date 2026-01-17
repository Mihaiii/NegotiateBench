import itertools
import random

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.types = len(counts)
        self.total_val = sum(c * v for c, v in zip(counts, values))
        
        # Opponent modeling: Track items opponent 'kept' (requested items)
        # We assume if they offer O to us, they keep (Counts - O).
        self.opp_req_counts = [0] * self.types
        self.turns_observed = 0
        
        # Complexity check for proposal generation
        # Calculate state space size to decide between Brute Force and Greedy
        self.space_size = 1
        for c in counts:
            self.space_size *= (c + 1)
        self.use_brute_force = self.space_size <= 50000
        
        self.turn_idx = 0 

    def get_opp_est_values(self):
        # Estimate opponent values based on frequency of keeping items
        est = []
        for i in range(self.types):
            # Probability that opponent wants item i approx = (Kept / Opportunities)
            denom = self.turns_observed * self.counts[i]
            if denom == 0:
                prob = 0.5
            else:
                prob = self.opp_req_counts[i] / denom
            # Add small baseline to prevent zero-value assumptions and issues with division
            est.append(prob + 0.1)
        
        # Normalize estimates so their total value matches mine (Symmetry Assumption)
        s = sum(c * v for c, v in zip(self.counts, est))
        if s > 1e-9:
            factor = self.total_val / s
            return [v * factor for v in est]
        return [1.0] * self.types

    def generate_proposals(self, opp_vals):
        # Generate possible splits. 
        # Returns list of dicts: {'get': [counts_for_me], 'vm': my_val, 'vo': est_opp_val}
        proposals = []
        
        if self.use_brute_force:
            # Full enumeration of the state space
            ranges = [range(c + 1) for c in self.counts]
            for p in itertools.product(*ranges):
                o_me = list(p)
                vm = sum(o_me[i] * self.values[i] for i in range(self.types))
                vo = sum((self.counts[i] - o_me[i]) * opp_vals[i] for i in range(self.types))
                proposals.append({'get': o_me, 'vm': vm, 'vo': vo})
        else:
            # Greedy Heuristic for large state spaces
            # Sort object types by efficiency (MyValue / OppValue)
            ratios = []
            for i in range(self.types):
                # Add epsilon to prevent division by zero
                ratios.append({'i': i, 'r': self.values[i] / (opp_vals[i] + 1e-9)})
            ratios.sort(key=lambda x: x['r'], reverse=True)
            
            # Walk the efficient frontier
            cur = [0] * self.types
            vm = 0
            vo = sum(c * v for c, v in zip(self.counts, opp_vals))
            proposals.append({'get': list(cur), 'vm': vm, 'vo': vo})
            
            for r in ratios:
                idx = r['i']
                for _ in range(self.counts[idx]):
                    cur[idx] += 1
                    vm += self.values[idx]
                    vo -= opp_vals[idx] 
                    proposals.append({'get': list(cur), 'vm': vm, 'vo': vo})
                    
        return proposals

    def offer(self, o: list[int] | None) -> list[int] | None:
        total_turns = self.max_rounds * 2
        my_turn_global = self.turn_idx * 2 + self.me
        turns_left = total_turns - my_turn_global

        # 1. Update Opponent Model
        if o:
            self.turns_observed += 1
            for i in range(self.types):
                self.opp_req_counts[i] += (self.counts[i] - o[i])

        val_o = sum(o[i] * self.values[i] for i in range(self.types)) if o else 0

        # --- LAST TURN DECISION (RECEIVER) ---
        # If I am receiving the very last offer of the game, I must accept anything > 0.
        if turns_left == 1:
            return None

        # --- DYNAMIC ASPIRATION LEVEL ---
        # Calculate target value based on remaining time.
        # Curve: Starts at 100%, stays high, drops linearly to 70%, then fast to 50%
        progress = my_turn_global / total_turns
        if progress < 0.2:
            f = 1.0
        elif progress < 0.8:
            # Linear drop from 1.0 to 0.7
            f = 1.0 - 0.5 * (progress - 0.2)
        else:
            # End game drop from 0.7 to 0.5 (Nash/Fair point)
            f = 0.7 - 2.0 * (progress - 0.8)
        
        target = self.total_val * f

        # --- ACCEPTANCE LOGIC ---
        if o:
            # Core condition: Does offer meet target?
            if val_o >= target: return None
            
            # Late game safety: Accept "Fair" offers to avoid total loss
            if turns_left <= 4 and val_o >= self.total_val * 0.65: return None
            if turns_left <= 2 and val_o >= self.total_val * 0.50: return None

        # --- GENERATE COUNTER-OFFER ---
        opp_vals = self.get_opp_est_values()
        cands = self.generate_proposals(opp_vals)
        
        # --- ULTIMATUM PROPOSAL (MY LAST TURN) ---
        # If this is my last chance to make an offer (Opponent has 1 turn to respond),
        # I should offer the bundle that maximizes my value while giving Opponent > 0.
        if turns_left == 2:
            valid = [p for p in cands if p['vo'] > 1e-4]
            # Safety checks
            if not valid: valid = cands
            best = max(valid, key=lambda x: x['vm'])
            self.turn_idx += 1
            return best['get']

        # --- NORMAL PROPOSAL STRATEGY ---
        # 1. Filter proposals that give me at least my target value
        valid = [p for p in cands if p['vm'] >= target]
        
        if not valid:
            # If target is too high, relax constraint to at least 50% or Maximize Me
            valid = [p for p in cands if p['vm'] >= self.total_val * 0.55]
            if not valid:
                valid = [max(cands, key=lambda x: x['vm'])]

        # 2. Selection Strategy: "Sweeten the Deal"
        # Among proposals that satisfy my greed, pick the one that maximizes 
        # the Opponent's estimated utility. This increases probability of acceptance.
        best = max(valid, key=lambda x: x['vo'])
        
        self.turn_idx += 1
        return best['get']