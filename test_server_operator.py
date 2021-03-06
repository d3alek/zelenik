import unittest
import server_operator

import time

from pathlib import Path
from tempfile import TemporaryDirectory

class TestServerOperator(unittest.TestCase):
    def setUp(self):
        self.tmp_directory = TemporaryDirectory()

        self.source_directory = Path(self.tmp_directory.name) / 'source'
        self.source_directory.mkdir()

        self.destination_directory = Path(self.tmp_directory.name) / 'destination'
        self.destination_directory.mkdir()

        self.server_operator = server_operator.ServerOperator(str(self.source_directory), str(self.destination_directory))


    def tearDown(self):
        self.tmp_directory.cleanup()

    def test_sync_to_copies_to_destination(self):
        a = ('a.txt', 'some-content')
                
        self.given_source_file(a)

        self.when_syncing_to()

        self.then_destination_contains(a)

    def test_sync_to_preserves_new_files_in_destination(self):
        a = ('a.txt', 'new-content')
        b = ('b.txt', 'another-new-content')
                
        self.given_source_file(a)
        self.given_destination_file(b)

        self.when_syncing_to()

        self.then_destination_contains(a)
        self.then_destination_contains(b)

    def test_sync_to_updates_old_files_in_destination(self):
        a = ('a.txt', 'old-content')
        self.given_destination_file(a)
            
        time.sleep(1) # necessary so new file timestamp will be definitely newer

        new_a = ('a.txt', 'new-content')
        self.given_source_file(new_a)

        self.when_syncing_to()

        self.then_destination_contains(new_a)

    def test_sync_from_updates_source(self):
        a = ('a.txt', 'old-content')
        self.given_source_file(a)

        time.sleep(1) # necessary so new file timestamp will be definitely newer

        new_a = ('a.txt', 'new-content')
        self.given_destination_file(new_a)
 
        self.when_syncing_from()

        self.then_source_contains(new_a)

    # Slave does sync_to master, but if aliases have changed in master slave would undo that
    # Same holds for history files that the master archives and removes - slave would restore them. Here we want to prevent these things.
    def test_slave_operate_does_not_add_new_files(self):
        new_a = ('a.txt', 'new-content')
        self.given_source_file(new_a)
 
        self.when_slave_operate()

        self.then_destination_does_not_contain(new_a)

    def test_slave_updates_existing_files(self):
        a = ('a.txt', 'old-content')
        self.given_destination_file(a)

        time.sleep(1)

        new_a = ('a.txt', 'new-content')
        self.given_source_file(new_a)
 
        self.when_slave_operate()

        self.then_source_contains(new_a)
        self.then_destination_contains(new_a)

    def test_slave_operate_fetches_from_destination(self):
        b = ('b.txt', 'another-new-content')
        self.given_destination_file(b)

        self.when_slave_operate()

        self.then_source_contains(b)
        self.then_destination_contains(b)

    def given_source_file(self, file_pair):
        self.given_file(self.source_directory, file_pair)

    def given_destination_file(self, file_pair):
        self.given_file(self.destination_directory, file_pair)

    def given_file(self, directory, file_pair):
        file_name, file_contents = file_pair
        source_file  = directory / file_name
        source_file.parent.mkdir(parents=True, exist_ok=True)
        with source_file.open('w', encoding='utf-8') as f:
            f.write(file_contents) 

    def when_slave_operate(self):
        self.server_operator.slave_operate(destination_host='localhost')

    def when_syncing_to(self):
        self.server_operator.sync_to('localhost', authenticate=False)

    def when_syncing_from(self):
        self.server_operator.sync_from('localhost', authenticate=False)

    def then_source_contains(self, file_pair):
        self.then_contains(self.source_directory, file_pair)

    def then_destination_does_not_contain(self, file_pair):
        self.then_does_not_contain(self.destination_directory, file_pair) 

    def then_destination_contains(self, file_pair):
        self.then_contains(self.destination_directory, file_pair)

    def then_contains(self, directory, file_pair):
        file_name, expected_contents = file_pair
        expected = directory / file_name
        self.assertTrue(expected.exists(), "%s does not exist" % expected)

        with expected.open() as f:
            actual_contents = f.read()

        self.assertEqual(expected_contents, actual_contents)

    def then_does_not_contain(self, directory, file_pair):
        file_name, expected_contents = file_pair
        expected = directory / file_name
        if expected.exists():
            with expected.open() as f:
                actual_contents = f.read()

            self.assertNotEqual(expected_contents, actual_contents)


if __name__ == '__main__':
    unittest.main()
