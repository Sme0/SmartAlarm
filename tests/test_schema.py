"""Schema tests: a fresh database should contain the columns the current app uses."""

import unittest

from sqlalchemy import inspect

from tests.bootstrap import configure_test_environment, stub_optional_ml_dependencies


configure_test_environment()
stub_optional_ml_dependencies()

from app import app, database as db
from app.models import Alarm, AlarmSession, PuzzleSession


class SchemaTests(unittest.TestCase):
    def setUp(self):
        self.app_context = app.app_context()
        self.app_context.push()
        db.drop_all()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_alarm_and_session_tables_include_current_columns(self):
        """Fresh databases should include the columns current code needs."""
        inspector = inspect(db.engine)

        alarm_columns = {column["name"] for column in inspector.get_columns(Alarm.__tablename__)}
        alarm_session_columns = {column["name"] for column in inspector.get_columns(AlarmSession.__tablename__)}
        puzzle_session_columns = {column["name"] for column in inspector.get_columns(PuzzleSession.__tablename__)}

        self.assertIn("use_dynamic_alarm", alarm_columns)
        self.assertIn("dynamic_start_time", alarm_columns)
        self.assertIn("dynamic_end_time", alarm_columns)
        self.assertIn("waking_difficulty", alarm_session_columns)
        self.assertIn("outcome_action", puzzle_session_columns)

    def test_create_all_is_idempotent_for_current_schema(self):
        """Running create_all twice should keep the same schema."""
        db.create_all()
        inspector = inspect(db.engine)
        alarm_columns = {column["name"] for column in inspector.get_columns(Alarm.__tablename__)}
        alarm_session_columns = {column["name"] for column in inspector.get_columns(AlarmSession.__tablename__)}
        puzzle_session_columns = {column["name"] for column in inspector.get_columns(PuzzleSession.__tablename__)}

        self.assertIn("use_dynamic_alarm", alarm_columns)
        self.assertIn("dynamic_start_time", alarm_columns)
        self.assertIn("dynamic_end_time", alarm_columns)
        self.assertIn("waking_difficulty", alarm_session_columns)
        self.assertIn("outcome_action", puzzle_session_columns)


if __name__ == "__main__":
    unittest.main()
