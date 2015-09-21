from __future__ import division, print_function
from warnings import warn
from traceback import print_exc
from StringIO import StringIO
from json import load
from csv import DictReader
from random import uniform, expovariate
from simpy import Environment, Interrupt, Store, FilterStore, Container, Resource, PreemptiveResource, PriorityResource, Event


inf = float('inf')
TIMESTAMP = '[{:10.1f}]'
MAX_POISSON = 1000


def check_inputs(beers, prices):
    for beer, data in beers.items():
        if beer not in prices:
            raise KeyError('Beer {} is not listed in prices'.format(beer))
        for ingredient in data['ingredients']:
            if ingredient not in prices:
                raise KeyError('Ingredient {} for beer {} is not listed in prices'.format(ingredient, beer))


def poisson(alpha):
    count = 0
    total = 0
    while True and count < MAX_POISSON:
        count += 1
        total += expovariate(alpha)
        if total > 1:
            return int(count - 1)


def json_to_dict(filename):
    with open(filename) as jsonfile:
        return load(jsonfile)


def csv_to_dict(filename, dialect='excel'):
    """
    Reads a CSV file and returns a dictionary of the rows in it.

    """

    output = []
    with open(filename) as csvfile:
        reader = DictReader(csvfile, dialect=dialect)
        for row in reader:
            for key, value in row.items():
                row[key] = to_number(value)
            output.append(row)
    return output


def to_number(string):
    try:
        return int(string)
    except ValueError:
        try:
            return float(string)
        except ValueError:
            return string


class NotifyingStore(Store):
    """
    A store that calls an optional callback whenever there is a put/get request.

    TODO: make the callback happen when the request is fullfilled.

    """
    def __init__(self, *args, **kwargs):
        self.callback = kwargs.pop('callback', None)
        super(NotifyingStore, self).__init__(*args, **kwargs)

    def _trigger_put(self, put_event, *args, **kwargs):
        super(NotifyingStore, self)._trigger_put(put_event)
        if self.callback is not None and put_event is not None:
            self.callback('put', self, put_event, *args, **kwargs)

    def _trigger_get(self, get_event, *args, **kwargs):
        super(NotifyingStore, self)._trigger_get(get_event)
        if self.callback is not None and get_event is not None:
            self.callback('get', self, get_event, *args, **kwargs)


class SelfMonitoringStore(Store):
    """
    A store that calls an optional callback whenever there is a put/get request.

    TODO: make the callback happen when the request is fullfilled.

    """
    def __init__(self, item_func=None, *args, **kwargs):
        super(SelfMonitoringStore, self).__init__(*args, **kwargs)
        if item_func is None:
            item_func = len
        self.item_func = item_func
        self._quantities = [(0, self.item_func(self.items))]

    def _trigger_put(self, event):
        super(SelfMonitoringStore, self)._trigger_put(event)
        self._record('put')

    def _trigger_get(self, event):
        super(SelfMonitoringStore, self)._trigger_get(event)
        self._record('get')

    def _do_put(self, event):
        super(SelfMonitoringStore, self)._do_put(event)
        if event.triggered:
            self._record('put')

    def _do_get(self, event):
        super(SelfMonitoringStore, self)._do_get(event)
        if event.triggered:
            self._record('get')

    def _record(self, call):
        self._quantities.append((self._env.now, self.item_func(self.items)))

    @property
    def records(self):
        result = [self._quantities[0]]
        for idx, record in enumerate(self._quantities[1:]):
            result.append((record[0], self._quantities[idx][1]))
            result.append(record)
        return result


class SelfMonitoringFilterStore(FilterStore, SelfMonitoringStore):
    pass


class SimpyMixin(object):
    """
    A mixin for objects that function inside a simpy environment.

    :param env: the simulation environment

    :type env: :class:`simpy.Environment`

    """

    def __init__(self, env=None, strict=False, **kwargs):
        self.env = env
        if self.env is None and not strict:
            self.env = Environment()
            self._log = []
            warn("Creating new environment")
        super(SimpyMixin, self).__init__()

    def run(self, until=365*24):
        try:
            self.env.run(until)
            self.errors = None
        except Exception as e:
            tb_string = StringIO()
            print_exc(file=tb_string)
            self.errors = tb_string.getvalue()
            tb_string.close()
            print(self.errors)
            raise e


    @property
    def now(self):
        """
        Return the current time in the simulation.

        """
        return self.env.now

    def wait(self, time):
        """
        Return a timeout. If time is a list of length 2, choose a random time between the interval given.

        :param time: amount of time to wait
        :type time: float or list
        """
        if isinstance(time, list) and len(time) == 2:
            time = uniform(*time)
        return self.env.timeout(time)

    def process(self, generator):
        """
        Return a Simpy process from the generator passed.

        :param generator: the generator that will be used by :class:`simpy.Process`
        :type generator:

        :rtype: :class:`simpy.Process`

        """
        return self.env.process(generator)

    def new_container(self, capacity=inf, init=0):
        """
        Return a new container.

        :param capacity: the maximum amount the container can store
        :param init: the initial quantity in the container

        :type capacity: float
        :type init: float

        :rtype: :class:`simpy.Container`

        """
        return Container(self.env, capacity=capacity, init=init)

    def new_resource(self, capacity=1, kind=None):
        """
        Return a new resource.

        :param capacity: the maximum amount of requests the resource can handle at one time
        :param kind: the type of resource (options: 'preemptive', 'priority')

        :type capacity: int
        :type kind: str

        :rtype: :class:`simpy.Resource`

        """
        if kind is None:
            return Resource(env=self.env, capacity=capacity)
        elif kind == 'preemptive':
            return PreemptiveResource(env=self.env, capacity=capacity)
        elif kind == 'priority':
            return PriorityResource(env=self.env, capacity=capacity)
        else:
            raise ValueError(
                'A specialized resource can either be `priority` or `preemptive`.')

    def new_store(self, capacity=inf, kind=None, monitoring=False):
        """
        Return a new store.

        :param capacity: the maximum number of items the store can hold
        :param kind: the type of store (options: 'priority', 'filter')

        :type capacity: int
        :type kind: str

        :rtype: :class:`Store`

        """
        if monitoring:
            if kind is None:
                return SelfMonitoringStore(env=self.env, capacity=capacity)
            elif kind== 'priority':
                return SelfMonitoringPriorityFilterStore(env=self.env, capacity=capacity)
            elif kind == 'filter':
                return SelfMonitoringFilterStore(env=self.env, capacity=capacity)
        else:
            if kind is None:
                return Store(env=self.env, capacity=capacity)
            elif kind == 'priority':
                return PriorityFilterStore(env=self.env, capacity=capacity)
            elif kind == 'filter':
                return FilterStore(env=self.env, capacity=capacity)
            else:
                raise ValueError('A specialized store can either be `priority` or `filter`.')

    def new_event(self):
        """
        Return a new event.

        :rtype: :class:`simpy.Event`

        """
        return Event(self.env)

    def log(self, msg):
        text = getattr(self, 'timestamp', TIMESTAMP) + " - {}"
        self._log.append(text.format(self.now, msg))
