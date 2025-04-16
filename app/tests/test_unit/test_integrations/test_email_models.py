"""Module providing Test Email Models functionality for the tests test unit test integrations."""

from datetime import datetime

from app.integrations.email.models import (
    EmailAttachment,
    InboundEmailData,
    MailchimpWebhook,
)


class TestEmailAttachment:
    """Tests for the EmailAttachment model."""

    def test_email_attachment_to_dict(self) -> None:
        """Test the to_dict method of EmailAttachment."""
        # Arrange
        attachment = EmailAttachment(
            name="test.pdf", type="application/pdf", content="content1", url=None
        )

        # Act
        result = attachment.to_dict()

        # Assert
        assert isinstance(result, dict)
        assert result["name"] == "test.pdf"
        assert result["type"] == "application/pdf"
        assert result["content"] == "content1"
        assert result["url"] is None

    def test_email_attachment_with_partial_data(self) -> None:
        """Test EmailAttachment with only required fields."""
        # Arrange
        attachment = EmailAttachment(
            name="test.pdf", type="application/pdf", content=None, url=None
        )

        # Act
        result = attachment.to_dict()

        # Assert
        assert isinstance(result, dict)
        assert result["name"] == "test.pdf"
        assert result["type"] == "application/pdf"
        assert result["content"] is None
        assert result["url"] is None


class TestInboundEmailData:
    """Tests for the InboundEmailData model."""

    def test_inbound_email_data_to_dict_no_attachments(self) -> None:
        """Test the to_dict method without attachments."""
        # Arrange
        now = datetime.now()
        email_data = InboundEmailData(
            message_id="test123",
            from_email="sender@example.com",
            from_name="Sender Name",
            subject="Test Subject",
            text="Plain text content",
            html="<p>HTML content</p>",
            to=["recipient@example.com"],
            cc=["cc@example.com"],
            bcc=["bcc@example.com"],
            date=now,
            reply_to="reply@example.com",
        )

        # Act
        result = email_data.to_dict()

        # Assert
        assert isinstance(result, dict)
        assert result["message_id"] == "test123"
        assert result["from_email"] == "sender@example.com"
        assert result["from_name"] == "Sender Name"
        assert result["subject"] == "Test Subject"
        assert result["text"] == "Plain text content"
        assert result["html"] == "<p>HTML content</p>"
        assert result["to"] == ["recipient@example.com"]
        assert result["cc"] == ["cc@example.com"]
        assert result["bcc"] == ["bcc@example.com"]
        assert result["date"] == now
        assert result["reply_to"] == "reply@example.com"
        assert result["attachments"] == []

    def test_inbound_email_data_to_dict_with_attachments(self) -> None:
        """Test the to_dict method with attachments."""
        # Arrange
        attachment1 = EmailAttachment(
            name="test1.pdf", type="application/pdf", content="content1", url=None
        )
        attachment2 = EmailAttachment(
            name="test2.jpg",
            type="image/jpeg",
            url="https://example.com/test2.jpg",
            content=None,
        )
        email_data = InboundEmailData(
            message_id="test123",
            from_email="sender@example.com",
            from_name="Sender Name",
            text="Test text",
            html="<p>HTML content</p>",
            date=datetime.now(),
            reply_to="reply@example.com",
            subject="Test Subject",
            attachments=[attachment1, attachment2],
        )

        # Act
        result = email_data.to_dict()

        # Assert
        assert isinstance(result, dict)
        assert result["message_id"] == "test123"
        assert len(result["attachments"]) == 2
        assert result["attachments"][0]["name"] == "test1.pdf"
        assert result["attachments"][0]["type"] == "application/pdf"
        assert result["attachments"][0]["content"] == "content1"
        assert result["attachments"][1]["name"] == "test2.jpg"
        assert result["attachments"][1]["type"] == "image/jpeg"
        assert result["attachments"][1]["url"] == "https://example.com/test2.jpg"


class TestMailchimpWebhook:
    """Tests for the MailchimpWebhook model."""

    def test_mailchimp_webhook_to_dict_with_dict_data(self) -> None:
        """Test the to_dict method with dictionary data."""
        # Arrange
        now = datetime.now()
        webhook = MailchimpWebhook(
            type="inbound",
            fired_at=now,
            data={"key": "value"},
            event="inbound",
            webhook_id="webhook123",
            test_mode=True,
        )

        # Act
        result = webhook.to_dict()

        # Assert
        assert isinstance(result, dict)
        assert result["type"] == "inbound"
        assert result["fired_at"] == now
        assert result["data"] == {"key": "value"}
        assert result["event"] == "inbound"
        assert result["webhook_id"] == "webhook123"
        assert result["test_mode"] is True

    def test_mailchimp_webhook_to_dict_with_inbound_email_data(self) -> None:
        """Test the to_dict method with InboundEmailData object."""
        # Arrange
        now = datetime.now()
        email_data = InboundEmailData(
            message_id="test123",
            from_email="sender@example.com",
            subject="Test Subject",
            from_name="Test Name",
            text="Test Text",
            html="<p>Test HTML</p>",
            date=now,
            reply_to="reply@example.com",
        )
        webhook = MailchimpWebhook(
            type="inbound",
            fired_at=now,
            data=email_data,
            event="inbound",
            webhook_id="webhook123",
            test_mode=False,
        )

        # Act
        result = webhook.to_dict()

        # Assert
        assert isinstance(result, dict)
        assert result["type"] == "inbound"
        assert result["fired_at"] == now
        assert isinstance(result["data"], dict)  # Should be converted to dict
        assert result["data"]["message_id"] == "test123"
        assert result["data"]["from_email"] == "sender@example.com"
        assert result["event"] == "inbound"
        assert result["webhook_id"] == "webhook123"
        assert result["test_mode"] is False

    def test_mailchimp_webhook_with_minimal_data(self) -> None:
        """Test MailchimpWebhook with minimal data."""
        # Arrange
        webhook = MailchimpWebhook(
            type=None,
            fired_at=None,
            event=None,
            webhook_id=None,
            test_mode=None,
            data={},
        )

        # Act
        result = webhook.to_dict()

        # Assert
        assert isinstance(result, dict)
        assert result["type"] is None
        assert result["fired_at"] is None
        assert result["data"] == {}
        assert result["event"] is None
        assert result["webhook_id"] is None
        assert result["test_mode"] is None

    def test_mailchimp_webhook_to_dict(self) -> None:
        """Test the to_dict method of MailchimpWebhook."""
        # Arrange
        now = datetime.now()
        webhook = MailchimpWebhook(
            type="inbound",
            fired_at=now,
            event="inbound",
            webhook_id="webhook123",
            test_mode=False,
            data={
                "message_id": "msg123",
                "subject": "Test Subject",
                "from_email": "sender@example.com",
            },
        )

        # Act
        result = webhook.to_dict()

        # Assert
        assert isinstance(result, dict)
        assert result["type"] == "inbound"
        assert result["fired_at"] == now
        assert result["event"] == "inbound"
        assert result["webhook_id"] == "webhook123"
        assert result["test_mode"] is False
        assert result["data"] == {
            "message_id": "msg123",
            "subject": "Test Subject",
            "from_email": "sender@example.com",
        }
