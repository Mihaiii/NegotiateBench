class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.counts = counts
        self.values = values
        self.total = sum(c * v for c, v in zip(counts, values))
        self.max_rounds = max_rounds
        self.max_offers = self.max_rounds * 2
        self.me = me
        self.current_turn = 0
        self.min_accept_initial = 0.95
        self.min_accept_final = 0.4

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.current_turn += 1
        if o:
            sum_val = sum(o[i] * self.values[i] for i in range(len(o)))
            if sum_val >= self.get_min_accept():
                return None
        return self.generate_offer()

    def get_min_accept(self):
        if self.max_offers <= 1:
            min_pct = self.min_accept_initial
        else:
            concession = (self.current_turn - 1) / (self.max_offers - 1)
            min_pct = self.min_accept_final * concession + self.min_accept_initial * (1 - concession)
        return min_pct * self.total

    def generate_offer(self):
        if self.max_offers <= 1:
            leave_factor = 0.5
        else:
            concession = (self.current_turn - 1) / (self.max_offers - 1)
            leave_factor = 0.1 + 0.7 * concession
        leave_num = int(len(self.counts) * leave_factor + 0.5)
        items = sorted([(self.values[i], i) for i in range(len(self.counts))], reverse=True)
        offer = [0] * len(self.counts)
        for _, i in items:
            leave_base = 0  # For non-zero, take all initially; adjust later
            if self.values[i] == 0:
                leave_base = max(1, self.counts[i] // 2)  # Leave at least half if worthless to us, to encourage partner
            offer[i] = max(0, self.counts[i] - leave_base)
        for _, i in items[:leave_num]:
            if offer[i] >= 1:
                offer[i] -= 1
        return offer