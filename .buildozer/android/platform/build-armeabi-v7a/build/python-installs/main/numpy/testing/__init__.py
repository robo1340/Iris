"""Common test support for all numpy test scripts.

This single module should provide all the common functionality for numpy tests
in a single location, so that test scripts can just import it and work right
away.

"""

# fake tester, android don't have unittest
class Tester(object):
    def test(self, *args, **kwargs):
        pass
    def bench(self, *args, **kwargs):
        pass
test = Tester().test
