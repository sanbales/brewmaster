from __future__ import division, print_function
from .util import SimpyMixin


KEGS_PER_PINT = 1 / 124
GALLONS_PER_KEG = 15.5
ROLES = ('in-house', 'distribution')


class Keg(SimpyMixin):
    def __init__(self, name=None, expiration=0, init=0, role=ROLES[0], *args, **kwargs):
        super(Keg, self).__init__(*args, **kwargs)
        if role not in ROLES:
            raise ValueError("'role' must be one of {}, not {}".format(ROLES, role))
        expiration = 24 * expiration
        self.expiration = self.now + expiration if expiration < self.now else expiration
        self.name = name
        self.contents = self.new_container(capacity=124, init=init)
        self.clean = True
        self.role = role

        get = self.contents.get

    @property
    def amount(self):
        return self.contents.level
    
    @property
    def capacity(self):
        return self.contents.capacity

    def fill(self, beer, amount=None):
        if amount is None:
            amount = self.contents.capacity

        if amount > self.capacity - self.amount:
            raise ValueError("Cannot put {} pints of beer into {}, at most, it can take {} pints!".format(amount,
                                                                                                          self,
                                                                                                          self.capacity - self.amount)
        self.name = beer
        self.clean = False
        self.contents.put(amount)

    def empty(self):
        self.get(self.amount)
