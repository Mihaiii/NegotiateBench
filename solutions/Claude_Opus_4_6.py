class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.round = 0
        self.n = len(counts)
        self.total = sum(c * v for c, v in zip(counts, values))
        self.opponent_offers = []
        
    def _my_value(self, offer):
        return sum(self.values[i] * offer[i] for i in range(self.n))
    
    def _opponent_gets(self, my_offer):
        return [self.counts[i] - my_offer[i] for i in range(self.n)]
    
    def _enumerate_splits(self):
        """Generate all possible splits (what I get)."""
        def generate(idx):
            if idx == self.n:
                yield []
                return
            for k in range(self.counts[idx] + 1):
                for rest in generate(idx + 1):
                    yield [k] + rest
        return list(generate(0))
    
    def _estimate_opponent_values(self):
        """Estimate opponent values from their offers (what they offered me = what they don't want)."""
        if not self.opponent_offers:
            return None
        # Opponent offers me little of what they value highly
        # So items they give me few of, they value more
        weights = [0.0] * self.n
        for offer in self.opponent_offers:
            for i in range(self.n):
                if self.counts[i] > 0:
                    # fraction they keep
                    kept_frac = 1.0 - offer[i] / self.counts[i]
                    weights[i] += kept_frac
        
        # Normalize to sum to self.total
        total_w = sum(weights)
        if total_w == 0:
            return [self.total / sum(self.counts)] * self.n if sum(self.counts) > 0 else None
        est = [weights[i] / total_w * self.total / max(self.counts[i], 1) for i in range(self.n)]
        return est

    def offer(self, o: list[int] | None) -> list[int] | None:
        if o is not None:
            self.opponent_offers.append(o[:])
        
        self.round += 1
        total_turns = self.max_rounds * 2
        turn = len(self.opponent_offers) + (len(self.opponent_offers) if self.me == 0 else len(self.opponent_offers))
        progress = self.round / self.max_rounds  # 0 to 1
        
        # Acceptance threshold decreases over time
        min_accept = self.total * max(0.35, 0.7 - 0.35 * progress)
        
        # On last round as second player, accept anything positive
        if self.round >= self.max_rounds and self.me == 1 and o is not None:
            min_accept = max(1, self.total * 0.15)
        elif self.round >= self.max_rounds:
            min_accept = max(1, self.total * 0.2)
        
        if o is not None:
            my_val = self._my_value(o)
            if my_val >= min_accept:
                return None
        
        # Generate all splits, score them
        all_splits = self._enumerate_splits()
        opp_values = self._estimate_opponent_values()
        
        scored = []
        target = self.total * max(0.45, 0.75 - 0.30 * progress)
        
        for split in all_splits:
            mv = self._my_value(split)
            if mv < target * 0.85:
                continue
            # Estimate opponent value of their share
            if opp_values:
                opp_val = sum(opp_values[i] * (self.counts[i] - split[i]) for i in range(self.n))
            else:
                opp_val = 0
            # Score: prioritize my value but also opponent satisfaction
            score = mv + 0.5 * opp_val
            scored.append((score, mv, split))
        
        scored.sort(key=lambda x: (-x[1], -x[0]))
        
        if not scored:
            # Fallback: demand everything valuable
            return [self.counts[i] if self.values[i] > 0 else 0 for i in range(self.n)]
        
        # Pick best offer that gives opponent something reasonable
        for score, mv, split in scored[:20]:
            if mv >= target * 0.85:
                return split
        
        return scored[0][2]