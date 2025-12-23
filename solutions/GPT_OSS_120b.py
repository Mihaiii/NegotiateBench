"""
Haggling negotiation agent.

The idea:
* The total value of the whole basket (according to us) is `total`.
* If there are `r` full rounds left (a round = two turns), a safe
  guarantee is to keep at most `total / (r+1)` value – the opponent can
  always enforce at least `total/(r+1)` in the remaining rounds.
* After each opponent turn we decrement the remaining‐round counter,
  recompute the guarantee and either accept the offer (if it meets the
  guarantee) or make a new counter‑offer.
* Counter‑offers are built greedily: we take the most valuable items
  (for us) until we reach the current guarantee.  The opponent receives
  everything else automatically.
* When no rounds are left we accept any offer (otherwise we would walk
  away and earn nothing).
"""

from typing import List, Optional


class Agent:
    def __init__(
        self,
        me: int,
        counts: List[int],
        values: List[int],
        max_rounds: int,
    ) -> None:
        # problem data
        self.counts = counts[:]          # total objects of each type
        self.values = values[:]          # our per‑item values
        self.total = sum(c * v for c, v in zip(self.counts, self.values))

        # negotiation state
        self.rounds_left = max_rounds    # full rounds that are still possible

        # order of item types – most valuable first (ties keep original order)
        self.order = sorted(
            range(len(self.counts)),
            key=lambda i: self.values[i],
            reverse=True,
        )

    # ------------------------------------------------------------------ #
    def _value(self, bundle: List[int]) -> int:
        """Value of a bundle according to us."""
        return sum(b * v for b, v in zip(bundle, self.values))

    # ------------------------------------------------------------------ #
    def _target(self) -> int:
        """
        Minimal value we are willing to accept given the remaining rounds.

        With `r` rounds left we can safely demand at most
        `total * r / (r + 1)`.  The complement (what we keep) is therefore
        `ceil(total / (r + 1))`.  When no rounds are left we set the target
        to 0 so that we accept any final offer.
        """
        r = self.rounds_left
        if r <= 0:
            return 0
        # ceil(total / (r+1)) without floating point
        return (self.total + r) // (r + 1)

    # ------------------------------------------------------------------ #
    def _make_counter(self) -> List[int]:
        """
        Greedy counter‑offer that guarantees us at least the current target.
        We take the most valuable items until the target is satisfied.
        """
        target = self._target()
        remaining = target
        allocation = [0] * len(self.counts)

        for i in self.order:
            if remaining <= 0:
                break
            per_item = self.values[i]
            if per_item == 0:
                continue
            available = self.counts[i]

            # Number of items of this type needed (ceil division)
            need = (remaining + per_item - 1) // per_item
            take = min(available, need)

            allocation[i] = take
            remaining -= take * per_item

        # If we couldn't reach the target (only possible when all remaining
        # items have zero value) we simply take everything – it does not hurt.
        if remaining > 0:
            allocation = self.counts[:]

        return allocation

    # ------------------------------------------------------------------ #
    def offer(self, o: Optional[List[int]]) -> Optional[List[int]]:
        """
        Called on each of our turns.

        Parameters
        ----------
        o : list[int] | None
            The opponent's last offer expressed as the bundle we would receive.
            `None` for the very first turn when we move first.

        Returns
        -------
        list[int] | None
            * ``None`` – we accept the opponent's offer.
            * list[int] – our counter‑offer (the bundle we would receive).
        """
        # If we just received an opponent offer, a full round has elapsed.
        if o is not None:
            self.rounds_left -= 1                     # one round consumed

            # Accept if the offer meets our current guarantee.
            if self._value(o) >= self._target():
                return None

            # Otherwise propose a new split.
            return self._make_counter()

        # First turn (or we are the first mover in a later round):
        return self._make_counter()