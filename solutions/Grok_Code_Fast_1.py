class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.counts = counts
        self.values = values
        self.total = sum(c * v for c, v in zip(counts, values))
        self.max_rounds = max_rounds
        self.me = me
        self.current_turn = 0
        self.min_accept_initial = 0.65
        self.min_accept_final = 0.4

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.current_turn += 1
        if o:
            sum_val = sum(o[i] * self.values[i] for i in range(len(o)))
            if sum_val >= self.get_min_accept():
                return None
        return self.generate_offer()

    def get_min_accept(self):
        if self.max_rounds <= 1:
            min_pct = self.min_accept_initial
        else:
            concession = (self.current_turn - 1) / (self.max_rounds - 1)
            min_pct = self.min_accept_final * concession + self.min_accept_initial * (1 - concession)
        return min_pct * self.total

    def generate_offer(self):
        # Gradually reduce the minimum items left for partner as rounds progress
        leave_factor = min(0.05 + (self.current_turn - 1) * 0.02, 0.15)
        leave_num = max(int(len(self.counts) * leave_factor), 1)
        items = sorted([(self.values[i], i) for i in range(len(self.counts))], reverse=True)
        offer = [0] * len(self.counts)
        for _, i in items:
            leave = 1 if self.values[i] == 0 else 0
            max_take = max(0, self.counts[i] - leave)
            offer[i] = max_take
        # Adjust by reducing leave for high-value items
        for _, i in items[:leave_num]:
            if offer[i] >= 1:
                offer[i] -= 1
        return offer