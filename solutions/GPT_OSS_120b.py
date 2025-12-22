# -*- coding: utf-8 -*-
"""
A fast, deterministic bargaining agent.

The idea
--------
*  total = Σ count_i * value_i  (the same for both players)
*  In turn t we know how many turns are left:   R = remaining_turns
*  To keep the opponent from being forced below a
   reasonable payoff we never keep more than

          max_frac = R / (2 * max_rounds + 1)

   of any item type.  (When R = 2·max_rounds this is ≈ 1,
   when R = 0 it becomes 0 – we give everything away.)

*  The best value we could still reach given this bound is
   obtained by taking, for each type, up to
   floor(max_frac * count_i) items, preferring the types
   with the highest personal value.

*  If the opponent’s offer gives us at least this value we accept;
   otherwise we propose the greedy allocation described above.

The agent never walks away, never returns an illegal list and
conforms to the required `Agent` interface.
"""

from typing import List, Optional


class Agent:
    def __init__(self, me: int, counts: List[int],
                 values: List[int], max_rounds: int) -> None:
        """
        Parameters
        ----------
        me : int
            0 if we move first, 1 otherwise (unused – the strategy is symmetric).
        counts : list[int]
            Number of objects of each type.
        values : list[int]
            Our value for a single object of each type.
        max_rounds : int
            Maximum number of *rounds* (a round = two turns, one per player).
        """
        self.me = me                         # kept only for compatibility
        self.counts = counts[:]              # immutable copy
        self.values = values[:]
        self.max_rounds = max_rounds

        # total value of the whole set (identical for the opponent)
        self.total = sum(c * v for c, v in zip(self.counts, self.values))

        # number of *turns* we will ever be asked to act
        self.remaining_turns = max_rounds * 2

    # -----------------------------------------------------------------
    # Helper functions
    # -----------------------------------------------------------------
    def _value_of(self, share: List[int]) -> int:
        """Value of a share for us."""
        return sum(v * q for v, q in zip(self.values, share))

    def _max_fraction_allowed(self) -> float:
        """
        Maximum fraction of any item type we are allowed to keep in the
        current turn.  The bound shrinks linearly to 0 when the deadline
        is reached.
        """
        # denominator is (2*max_rounds + 1) – a tiny slack prevents
        # division by zero when we are on the last turn.
        return self.remaining_turns / (self.max_rounds * 2 + 1)

    def _best_future_value(self, max_frac: float) -> int:
        """
        Greedy upper‑bound on the value we could still achieve if we keep
        at most `max_frac` of each type.
        """
        # how many of each type we *could* keep
        limits = [int(max_frac * c) for c in self.counts]

        # take the most valuable items first
        order = sorted(range(len(self.values)),
                       key=lambda i: self.values[i],
                       reverse=True)

        value = 0
        for i in order:
            value += self.values[i] * limits[i]
        return value

    # -----------------------------------------------------------------
    def offer(self, o: Optional[List[int]]) -> Optional[List[int]]:
        """
        Called on each of our turns.

        Parameters
        ----------
        o : list[int] | None
            The opponent's last proposal (what we would receive).  ``None``
            on the very first turn.

        Returns
        -------
        list[int] | None
            * ``None`` – we accept the opponent's proposal.
            * list[int] – our counter‑proposal (how many of each type we want).
        """
        # One turn is consumed.
        self.remaining_turns -= 1

        # -----------------------------------------------------------------
        # 1)  Decide whether to accept the opponent's offer.
        # -----------------------------------------------------------------
        if o is not None:
            my_val = self._value_of(o)

            # Upper bound on the value we could still reach later.
            max_frac = self._max_fraction_allowed()
            future_best = self._best_future_value(max_frac)

            # Accept if the offer is at least as good as what we could still
            # hope to obtain.
            if my_val >= future_best:
                return None

            # As a safety net we also accept any offer that gives us
            # at least half of the total value (the classic “fair
            # split” benchmark).  This helps against opponents that
            # quickly drop their demands.
            if my_val >= self.total * 0.5:
                return None

        # -----------------------------------------------------------------
        # 2)  Build a counter‑proposal.
        # -----------------------------------------------------------------
        n = len(self.counts)

        # If this is our very last turn we concede everything.
        if self.remaining_turns == 0:
            return [0] * n

        # Maximum fraction we may keep for each type in this turn.
        max_frac = self._max_fraction_allowed()
        limits = [int(max_frac * c) for c in self.counts]

        # Greedy allocation: take as many high‑valued items as the limits allow.
        order = sorted(range(n), key=lambda i: self.values[i], reverse=True)
        share = [0] * n
        for i in order:
            share[i] = limits[i]

        # The constructed share is always feasible (share_i ≤ count_i) and
        # respects the fairness bound, so the opponent always has a
        # non‑negative guarantee.
        return share