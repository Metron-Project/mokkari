# Testing

These tests use the mokkari requests caching for mocking tests, so tests will
run quickly and not require credentials.

If your code adds a new URL to the cache, set the `METRON_USERNAME` and
`METRON_PASSWD` environment variables before running the test and it will be
populated in the `testing_mock.sqlite` database.

At any point you should be able to delete the database, set any creditials, and
run the full test suite to repopulate it (though some of the results might be
diffent if any of the data has change at metron.cloud).
