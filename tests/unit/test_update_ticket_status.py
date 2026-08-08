from unittest import TestCase
from unittest.mock import Mock, patch

from fastapi import HTTPException
from peewee import DoesNotExist

from app.api import TicketStatus, update_ticket_status


class TestUpdateTicketStatus(TestCase):
    @patch("app.api.ModeratorActionModel.create")
    @patch("app.api.TicketModel.get_by_id")
    def test_update_ticket_status_records_custom_moderator_action(
        self, mock_get_by_id, mock_create
    ):
        ticket = Mock()
        mock_get_by_id.return_value = ticket
        db_mock = Mock()
        db_mock.__enter__ = Mock(return_value=db_mock)
        db_mock.__exit__ = Mock(return_value=False)

        with patch("app.api.db", db_mock):
            result = update_ticket_status(
                ticket_id=42,
                status=TicketStatus.closed,
                action="fix",
                moderator_data={"user_id": "moderator-123"},
            )

        self.assertIs(result, ticket)
        self.assertEqual(ticket.status, TicketStatus.closed)
        ticket.save.assert_called_once()
        mock_create.assert_called_once()
        create_kwargs = mock_create.call_args.kwargs
        self.assertEqual(create_kwargs["action_type"], "fix")
        self.assertEqual(create_kwargs["user_id"], "moderator-123")
        self.assertIs(create_kwargs["ticket"], ticket)
        self.assertIsNotNone(create_kwargs["created_at"])

    @patch("app.api.ModeratorActionModel.create")
    @patch("app.api.TicketModel.get_by_id")
    def test_update_ticket_status_uses_default_action_when_missing(
        self, mock_get_by_id, mock_create
    ):
        ticket = Mock()
        mock_get_by_id.return_value = ticket
        db_mock = Mock()
        db_mock.__enter__ = Mock(return_value=db_mock)
        db_mock.__exit__ = Mock(return_value=False)

        with patch("app.api.db", db_mock):
            update_ticket_status(
                ticket_id=42,
                status=TicketStatus.closed,
                action=None,
                moderator_data={"user_id": "moderator-123"},
            )

        self.assertEqual(
            mock_create.call_args.kwargs["action_type"], "set_status_closed"
        )

    @patch("app.api.ModeratorActionModel.create")
    @patch("app.api.TicketModel.get_by_id")
    def test_update_ticket_status_uses_default_action_when_action_is_whitespace(
        self, mock_get_by_id, mock_create
    ):
        ticket = Mock()
        mock_get_by_id.return_value = ticket
        db_mock = Mock()
        db_mock.__enter__ = Mock(return_value=db_mock)
        db_mock.__exit__ = Mock(return_value=False)

        with patch("app.api.db", db_mock):
            update_ticket_status(
                ticket_id=42,
                status=TicketStatus.closed,
                action="   ",
                moderator_data={"user_id": "moderator-123"},
            )

        self.assertEqual(
            mock_create.call_args.kwargs["action_type"], "set_status_closed"
        )

    @patch("app.api.ModeratorActionModel.create")
    @patch("app.api.TicketModel.get_by_id")
    def test_update_ticket_status_uses_unknown_user_when_missing_data(
        self, mock_get_by_id, mock_create
    ):
        ticket = Mock()
        mock_get_by_id.return_value = ticket
        db_mock = Mock()
        db_mock.__enter__ = Mock(return_value=db_mock)
        db_mock.__exit__ = Mock(return_value=False)

        with patch("app.api.db", db_mock):
            update_ticket_status(
                ticket_id=42,
                status=TicketStatus.closed,
                action=None,
                moderator_data=None,
            )

        self.assertEqual(mock_create.call_args.kwargs["user_id"], "unknown")

    @patch("app.api.ModeratorActionModel.create")
    @patch("app.api.TicketModel.get_by_id", side_effect=DoesNotExist())
    def test_update_ticket_status_returns_404_when_ticket_not_found(
        self, _mock_get_by_id, mock_create
    ):
        db_mock = Mock()
        db_mock.__enter__ = Mock(return_value=db_mock)
        db_mock.__exit__ = Mock(return_value=False)

        with patch("app.api.db", db_mock), self.assertRaises(HTTPException) as error:
            update_ticket_status(
                ticket_id=404,
                status=TicketStatus.closed,
                action=None,
                moderator_data={"user_id": "moderator-123"},
            )

        self.assertEqual(error.exception.status_code, 404)
        mock_create.assert_not_called()
