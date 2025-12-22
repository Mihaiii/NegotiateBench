# -*- coding: utf-8 -*-
"""
Simple bargaining agent.

The agent knows:
* its own values for each object type,
* the total number of each object type,
* that the opponent’s total value for the whole set equals our total value.

From this we can compute a *guaranteed* lower bound on the opponent’s value for any
allocation we keep:

    guarantee(our_share) = TOTAL * (1 - max_i (our_share[i] / counts[i]))

because the opponent can always concentrate all of its value on the type we own
the most of.  If we keep a modest proportion of every type, the opponent is forced
to receive a decent amount no matter how it values the items.

The strategy is therefore:
1.   Accept any offer that gives us at least half of the total value.
2.   Otherwise, make an offer that limits the proportion of each type we keep.
     The allowed proportion shrinks linearly as the negotiation proceeds, so we
     become increasingly generous the closer we get to the deadline.
3.   On the very last turn we concede everything (offer only zeros), guaranteeing
     the opponent a value of TOTAL and avoiding a walk‑away.

The allocation itself is easy: for each type we are allowed to keep at most
⌊ratio·counts[i]⌋ items, where *ratio* is the current maximal proportion.
Since every item of a type has the same value for us, taking the maximal
allowed amount for the highest‑valued types first is optimal.
"""

class Agent:
    """
    Negotiation agent.

    Parameters
    ----------
    me : int
        0 if we move first, 1 otherwise (not used directly).
    counts : list[int]
        Number of objects of each type.
    values : list[int]
        Our value for a single object of each type.
    max_rounds : int
        Maximum number of *rounds* (a round = two turns).
    """

    def __init__(self, me: int, counts: list[int],
                 values: list[int], max_rounds: int) -> None:
        self.me = me
        self.counts = counts[:]               # immutable copy
        self.values = values[:]
        self.max_rounds = max_rounds           # total rounds allowed
        self.remaining = max_rounds            # turns we still have to act
        # Our total value for the whole set (equals opponent's total value)
        self.total = sum(c * v for c, v in zip(self.counts, self.values))

    # --------------------------------------------------------------------- #
    # Helper methods
    # --------------------------------------------------------------------- #
    def _value_of(self, share: list[int]) -> int:
        """Return our valuation of the given share."""
        return sum(v * q for v, q in zip(self.values, share))

    # --------------------------------------------------------------------- #
    def offer(self, o: list[int] | None) -> list[int] | None:
        """
        Called each time it is our turn.

        Parameters
        ----------
        o : list[int] | None
            The opponent's last proposal (what we would receive).  ``None`` on the
            very first turn.

        Returns
        -------
        list[int] | None
            * ``None``   – we accept the opponent's proposal.
            * list[int] – our counter‑proposal (how many of each type we want).
        """
        # One of our turns is used now.
        self.remaining -= 1

        # --------------------------------------------------------------
        # 1)  Consider accepting the opponent's offer (if there is one)
        # --------------------------------------------------------------
        if o is not None:
            my_val = self._value_of(o)
            # Simple acceptance rule: keep at least half of the total value.
            if my_val >= self.total / 2:
                return None

        # --------------------------------------------------------------
        # 2)  No acceptable offer – construct a counter‑proposal.
        # --------------------------------------------------------------
        n = len(self.counts)

        # If this was our last possible turn we concede everything.
        if self.remaining == 0:
            return [0] * n

        # Maximal proportion of each type we are allowed to keep.
        # It linearly shrinks from almost 1 down to 0.5 as we approach the end.
        ratio = self.remaining / (self.max_rounds + 1)

        # Build our share: for each type take as many items as the ratio permits,
        # preferring higher‑valued types first (greedy optimal because items are
        # independent and have equal size).
        share = [0] * n
        # indices sorted by our per‑item value, descending
        order = sorted(range(n), key=lambda i: self.values[i], reverse=True)
        for i in order:
            limit = int(ratio * self.counts[i])        # floor(ratio * count)
            share[i] = limit

        return share