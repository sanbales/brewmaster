from __future__ import division, print_function
from random import expovariate, sample, uniform
from util import Interrupt, SimpyMixin, poisson, csv_to_dict, json_to_dict
from keg import KEGS_PER_PINT


AVG_GROUP_SIZE = 4
AVG_GROUP_STAY = 1.5
AVG_NUM_DRINKS = 1.2
MAX_WAIT = [0.5, 1.5]
TIME_TO_ORDER = [0.05, 0.25]
TIME_TO_BE_SERVED = 0.12
TIME_TO_REORDER = [0.12, 0.65]
TIME_TO_PAY = [0.1, 0.2]
inf = float('inf')


class Patron(SimpyMixin):
    def __init__(self, brewery, max_wait=None, *args, **kwargs):
        super(Patron, self).__init__(*args, **kwargs)
        self.brewery = brewery
        self.departure = self.now + expovariate(AVG_GROUP_STAY)
        self.party_size = poisson(AVG_GROUP_SIZE - 1) + 1
        self.max_wait = uniform(*MAX_WAIT) if max_wait is None else max_wait
        self.max_orders = [poisson(AVG_NUM_DRINKS) for _ in range(self.party_size)]
        self.name = "Party of {} (arrived at {:.1f})".format(self.party_size, self.now)
        self.consuming = self.process(self.consume())

    def consume(self):
        try:
            self.brewery.log(self.name + ' arrived and waiting to be seated')
            tables = self.brewery.tables
            table_size = max(tables, key=lambda x: self.party_size - x if x > self.party_size else -inf)
            with self.brewery.tables[table_size].request() as table:
                request = yield table | self.wait(self.max_wait)
                if table not in request:
                    raise Interrupt("they are tired of waiting")
                    self.brewery.tables[table_size].release(table)

                self.brewery.log(self.name + ' waiting to order')
                yield self.wait(TIME_TO_ORDER)
                beers = True
                while self.now < self.departure and beers:
                    beers = self.select_beers()
                    if beers:
                        yield self.process(self.brewery.take_order(beers, 1))
                        self.brewery.log(self.name + ' waiting to be served')
                        yield self.wait(TIME_TO_BE_SERVED)
                        self.brewery.log(self.name + ' is drinking')
                        yield self.wait(TIME_TO_REORDER)
                self.brewery.log(self.name + ' waiting to pay')
                yield self.wait(TIME_TO_PAY)
                self.brewery.log(self.name + ' leaving')

        except Interrupt as interruption:
            self.brewery.log('Party {} leaving {} hrs early because'.format(self.name, self.departure - self.now, interruption))

    def select_beers(self):
        beers = []
        tapped_kegs = {keg.name: keg for keg in self.brewery.tapped_kegs.items}

        for customer in range(self.party_size):
            if self.max_orders[customer] > 0:
                self.max_orders[customer] -= 1
            else:
                continue
            new_beer = None
            beer = sample(tapped_kegs, 1)[0]
            self.brewery.log('A customer in {} wants to drink a pint of {}'.format(self.name, beer))
            if beer not in tapped_kegs or tapped_kegs[beer].amount < KEGS_PER_PINT:
                candidate_kegs = [key for key, keg in tapped_kegs.items() if keg.amount > KEGS_PER_PINT]
                if candidate_kegs:
                    new_beer = sample(candidate_kegs, 1)[0]
                    self.brewery.log('A customer in {} could not get {} so they ordered {}'.format(self.name, beer, new_beer))
                    beers.append(new_beer)
                else:
                    self.brewery.log('A customer in {} could not get {} nor any other beer'.format(self.name, beer))
            else:
                beers.append(beer)

        return beers
