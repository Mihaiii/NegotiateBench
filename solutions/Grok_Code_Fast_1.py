class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.counts = counts
        self.values = values
        self.total = sum(c * v for c, v in zip(counts, values))
        self.max_rounds = max_rounds
        self.me = me
        self.current_turn = 0
        self.min_accept_initial = 0.8
        self.min_accept_final = 0.5

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.current_turn += 1
        if o is not None:
            my_value = sum(o[i] * self.values[i] for i in range(len(o)))
            if my_value >= self.get_min_accept():
                return None
        return self.generate_offer()

    def get_min_accept(self):
        if self.max_rounds <= 1:
            return (self.min_accept_initial + self.min_accept_final) / 2 * self.total
        concession = (self.current_turn - 1) / (self.max_rounds - 1)
        return (self.min_accept_final * concession + self.min_accept_initial * (1 - concession)) * self.total

    def generate_offer(self):
        offer = [0] * len(self.counts)
        items = sorted([(self.values[i], i) for i in range(len(self.counts))], reverse=True)
        for _, i in items:
            leave = 1 if self.counts[i] > 0 else 0
            offer[i] = self.counts[i] - leave
        return offer