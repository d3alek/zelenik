import unittest
import datetime

from graph import subsample_history 


def today():
    return datetime.datetime.today()

def today_midnight():
    return datetime.datetime.combine(datetime.datetime.today(), datetime.time(0, 0))

def yesterday_midnight():
    return today_midnight() - datetime.timedelta(days=1)

def yesterday():
    return today() - datetime.timedelta(days=1)

def two_days_ago():
    return today() - datetime.timedelta(days=2)

def state(timestamp, senses={}):
    return {'timestamp_utc': timestamp.isoformat(sep=' '), 'senses': senses}

def t(hour, date=today()):
    time = datetime.time(hour, 0)
    return datetime.datetime.combine(date, time)

class TestGraph(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        pass
    def tearDown(self):
        pass
    
    def test_subsample_history_preserves_all(self):
        full_history = [state(t(10)), state(t(11)), state(t(12))]
        self.given_history(full_history)

        self.when_subsampling([(today_midnight(), 3)])

        self.then_sparse_history(full_history)

    def test_subsample_history_simple(self):
        today_history = [state(t(10)), state(t(11)), state(t(12))]

        full_history = [state(t(10, yesterday())), state(t(11, yesterday())), state(t(12, yesterday()))]
        full_history.extend(today_history)
        self.given_history(full_history)

        self.when_subsampling([(today_midnight(), 3)])

        expected = [full_history[0]]
        expected.extend(today_history)
        self.then_sparse_history(expected)

    def test_subsample_history_multiple_conditions(self):
        today_history = [state(t(10)), state(t(11)), state(t(12))]

        yesterday_history = [state(t(10, yesterday())), state(t(11, yesterday())), state(t(12, yesterday())), state(t(13, yesterday()))]

        full_history = [state(t(10, two_days_ago())), state(t(11, two_days_ago())), state(t(12, two_days_ago()))]

        full_history.extend(yesterday_history)
        full_history.extend(today_history)

        self.given_history(full_history)

        self.when_subsampling([(today_midnight(), 2), (yesterday_midnight(), 3)])

        expected = [full_history[0]]
        expected.extend(yesterday_history[::2])
        expected.extend(today_history)
        self.then_sparse_history(expected)

    def given_history(self, history):
        self.history = history

    def when_subsampling(self, conditions):
        self.sparse_history = subsample_history(self.history, conditions)

    def then_sparse_history(self, expected):
        self.assertEqual(expected, self.sparse_history)

if __name__ == '__main__':
    unittest.main()
