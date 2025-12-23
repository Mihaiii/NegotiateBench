class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total = sum(c * v for c, v in zip(counts, values))
        self.me = me  # 0 = first, 1 = second
        self.turn = 0
        self.n_items = len(counts)
        self.best_offer_received = None
        self.best_offer_value = 0
        
    def _my_value(self, offer: list[int]) -> int:
        return sum(o * v for o, v in zip(offer, self.values))
    
    def _generate_offers(self, min_value: int):
        """Generate all valid offers meeting minimum value threshold."""
        offers = []
        def gen(idx, current, cur_val):
            if idx == self.n_items:
                if cur_val >= min_value:
                    offers.append((current.copy(), cur_val))
                return
            max_possible = cur_val + sum(self.counts[j] * self.values[j] for j in range(idx, self.n_items))
            if max_possible < min_value:
                return
            for c in range(self.counts[idx] + 1):
                current.append(c)
                gen(idx + 1, current, cur_val + c * self.values[idx])
                current.pop()
        gen(0, [], 0)
        return offers

    def _best_offer_for_target(self, target_value: int) -> list[int]:
        """Find offer closest to target that gives opponent most items we don't value."""
        offers = self._generate_offers(target_value)
        if not offers:
            return [self.counts[i] if self.values[i] > 0 else 0 for i in range(self.n_items)]
        
        # Score: prefer giving away zero-value items, minimize what we take beyond target
        def score(offer_tuple):
            offer, val = offer_tuple
            items_given = sum(self.counts[i] - offer[i] for i in range(self.n_items))
            zero_val_given = sum(self.counts[i] - offer[i] for i in range(self.n_items) if self.values[i] == 0)
            return (val, zero_val_given, items_given)
        
        offers.sort(key=score, reverse=True)
        return offers[0][0]

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn += 1
        rounds_left = self.max_rounds - (self.turn + 1) // 2
        is_last_turn = rounds_left == 0 and ((self.me == 1 and self.turn % 2 == 0) or (self.me == 0 and self.turn % 2 == 1))
        progress = self.turn / (2 * self.max_rounds)
        
        if o is not None:
            offer_val = self._my_value(o)
            if offer_val > self.best_offer_value:
                self.best_offer_value = offer_val
                self.best_offer_received = o.copy()
            
            # Final turn acceptance logic
            if rounds_left == 0:
                return None if offer_val > 0 else self._best_offer_for_target(1)
            
            # Acceptance threshold: start at 60%, drop to 30% near end
            threshold = self.total * max(0.30, 0.60 - 0.40 * progress)
            if offer_val >= threshold:
                return None
        
        # Demand curve: start at 80%, drop to 35%
        demand = self.total * max(0.35, 0.80 - 0.55 * progress)
        target = max(1, int(demand))
        
        return self._best_offer_for_target(target)