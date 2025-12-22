class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.counts = counts
        self.values = values
        self.rounds = max_rounds
        self.total = 0
        for i in range(len(counts)):
            self.total += counts[i] * values[i]

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.rounds -= 1
        if o:
            sum_val = 0
            for i in range(len(o)):
                sum_val += self.values[i] * o[i]
            if sum_val >= self.total / 2:
                return None
        o = self.counts.copy()
        for i in range(len(o)):
            if self.values[i] == 0:
                o[i] = 0
        return o
