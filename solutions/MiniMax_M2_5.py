class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total = sum(c * v for c, v in zip(counts, values))
        self.turn = 0
        self.last_offer = None
        self.my_value_sum = sum(c * v for c, v in zip(counts, values))
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn += 1
        current_round = (self.turn + 1) // 2
        
        if o is not None:
            offered_value = sum(ov * self.values[i] for i, ov in enumerate(o))
            min_acceptable = self.total * (0.3 + 0.5 * (current_round / self.max_rounds))
            if offered_value >= min_acceptable:
                return None
        
        if current_round == 1 and o is None:
            best_items = sorted(range(len(self.counts)), key=lambda i: self.values[i], reverse=True)
            offer = [0] * len(self.counts)
            remaining = self.counts.copy()
            for i in best_items[:3]:
                take = min(remaining[i], (self.counts[i] + 1) // 2)
                offer[i] = take
                remaining[i] -= take
            return offer
        
        if self.last_offer is not None:
            last_value = sum(lo * self.values[i] for i, lo in enumerate(self.last_offer))
            if last_value < self.total * 0.35:
                best_items = sorted(range(len(self.counts)), key=lambda i: self.values[i], reverse=True)
                offer = [0] * len(self.counts)
                remaining = self.counts.copy()
                for i in best_items[:4]:
                    take = min(remaining[i], max(1, self.counts[i] // 2))
                    offer[i] = take
                    remaining[i] -= take
                self.last_offer = offer
                return offer
        
        current_min = int(self.total * (0.2 + 0.6 * (current_round / self.max_rounds)))
        best_offer = None
        best_value = 0
        
        from itertools import product
        for take_counts in product(*[range(c + 1) for c in self.counts]):
            give_counts = [self.counts[i] - take_counts[i] for i in range(len(self.counts))]
            my_value = sum(take_counts[i] * self.values[i] for i in range(len(self.counts)))
            if my_value >= current_min and my_value > best_value:
                best_offer = take_counts
                best_value = my_value
        
        if best_offer is None:
            best_offer = [0] * len(self.counts)
            
        self.last_offer = best_offer
        return best_offer