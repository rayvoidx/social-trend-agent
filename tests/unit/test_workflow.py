"""
Unit tests for workflow management.
"""
import pytest
import time
from unittest.mock import patch, MagicMock

from src.core.workflow import (
    WorkflowStatus,
    ReviewAction,
    WorkflowItem,
    ReviewComment,
    WorkflowManager,
    VALID_TRANSITIONS,
    create_insight_workflow,
    create_mission_workflow,
    approve_item,
    reject_item,
    request_revision,
)


class TestWorkflowStatus:
    """Test workflow status enum."""

    def test_status_values(self):
        """Test all status values exist."""
        assert WorkflowStatus.DRAFT.value == "draft"
        assert WorkflowStatus.PENDING_REVIEW.value == "pending_review"
        assert WorkflowStatus.IN_REVIEW.value == "in_review"
        assert WorkflowStatus.APPROVED.value == "approved"
        assert WorkflowStatus.REJECTED.value == "rejected"
        assert WorkflowStatus.REVISION_REQUESTED.value == "revision_requested"
        assert WorkflowStatus.PUBLISHED.value == "published"
        assert WorkflowStatus.ARCHIVED.value == "archived"


class TestReviewAction:
    """Test review action enum."""

    def test_action_values(self):
        """Test all action values exist."""
        assert ReviewAction.APPROVE.value == "approve"
        assert ReviewAction.REJECT.value == "reject"
        assert ReviewAction.REQUEST_REVISION.value == "request_revision"
        assert ReviewAction.ESCALATE.value == "escalate"


class TestValidTransitions:
    """Test valid state transitions."""

    def test_draft_transitions(self):
        """Test valid transitions from draft."""
        valid = VALID_TRANSITIONS[WorkflowStatus.DRAFT]
        assert WorkflowStatus.PENDING_REVIEW in valid
        assert WorkflowStatus.ARCHIVED in valid
        assert WorkflowStatus.PUBLISHED not in valid

    def test_pending_review_transitions(self):
        """Test valid transitions from pending review."""
        valid = VALID_TRANSITIONS[WorkflowStatus.PENDING_REVIEW]
        assert WorkflowStatus.IN_REVIEW in valid
        assert WorkflowStatus.DRAFT in valid
        assert WorkflowStatus.PUBLISHED not in valid

    def test_in_review_transitions(self):
        """Test valid transitions from in review."""
        valid = VALID_TRANSITIONS[WorkflowStatus.IN_REVIEW]
        assert WorkflowStatus.APPROVED in valid
        assert WorkflowStatus.REJECTED in valid
        assert WorkflowStatus.REVISION_REQUESTED in valid

    def test_approved_transitions(self):
        """Test valid transitions from approved."""
        valid = VALID_TRANSITIONS[WorkflowStatus.APPROVED]
        assert WorkflowStatus.PUBLISHED in valid
        assert WorkflowStatus.ARCHIVED in valid

    def test_archived_is_terminal(self):
        """Test archived is a terminal state."""
        valid = VALID_TRANSITIONS[WorkflowStatus.ARCHIVED]
        assert len(valid) == 0


class TestWorkflowItem:
    """Test WorkflowItem dataclass."""

    def test_item_creation(self):
        """Test workflow item creation."""
        item = WorkflowItem(
            id="test-1",
            type="insight",
            data={"title": "Test"}
        )

        assert item.id == "test-1"
        assert item.type == "insight"
        assert item.status == WorkflowStatus.DRAFT
        assert item.created_by == "system"
        assert item.assigned_to is None

    def test_item_to_dict(self):
        """Test workflow item serialization."""
        item = WorkflowItem(
            id="test-1",
            type="insight",
            data={"title": "Test"},
            created_by="user1"
        )

        result = item.to_dict()

        assert result["id"] == "test-1"
        assert result["type"] == "insight"
        assert result["status"] == "draft"
        assert result["data"] == {"title": "Test"}
        assert result["created_by"] == "user1"

    def test_item_with_review_comments(self):
        """Test item with review comments."""
        item = WorkflowItem(
            id="test-1",
            type="insight",
            data={}
        )

        comment = ReviewComment(
            reviewer="reviewer1",
            comment="Looks good",
            action=ReviewAction.APPROVE
        )
        item.review_comments.append(comment)

        result = item.to_dict()
        assert len(result["review_comments"]) == 1
        assert result["review_comments"][0]["reviewer"] == "reviewer1"
        assert result["review_comments"][0]["action"] == "approve"


class TestWorkflowManager:
    """Test WorkflowManager class."""

    @pytest.fixture
    def manager(self):
        """Create fresh workflow manager."""
        return WorkflowManager()

    def test_create_item(self, manager):
        """Test creating a workflow item."""
        item = manager.create_item(
            id="test-1",
            type="insight",
            data={"title": "Test"}
        )

        assert item is not None
        assert item.id == "test-1"
        assert item.status == WorkflowStatus.DRAFT

    def test_create_item_with_auto_submit(self, manager):
        """Test creating item with auto submit."""
        item = manager.create_item(
            id="test-1",
            type="insight",
            data={},
            auto_submit=True
        )

        assert item.status == WorkflowStatus.PENDING_REVIEW

    def test_get_item(self, manager):
        """Test getting an item."""
        manager.create_item(id="test-1", type="insight", data={})

        item = manager.get_item("test-1")
        assert item is not None
        assert item.id == "test-1"

        # Non-existent
        item = manager.get_item("non-existent")
        assert item is None

    def test_update_item_data(self, manager):
        """Test updating item data."""
        manager.create_item(id="test-1", type="insight", data={"a": 1})

        updated = manager.update_item_data("test-1", {"b": 2})

        assert updated is not None
        assert updated.data == {"a": 1, "b": 2}

    def test_transition_status_valid(self, manager):
        """Test valid status transition."""
        manager.create_item(id="test-1", type="insight", data={})

        success = manager.transition_status(
            "test-1",
            WorkflowStatus.PENDING_REVIEW
        )

        assert success
        item = manager.get_item("test-1")
        assert item.status == WorkflowStatus.PENDING_REVIEW

    def test_transition_status_invalid(self, manager):
        """Test invalid status transition."""
        manager.create_item(id="test-1", type="insight", data={})

        # Draft -> Published is invalid
        success = manager.transition_status(
            "test-1",
            WorkflowStatus.PUBLISHED
        )

        assert not success
        item = manager.get_item("test-1")
        assert item.status == WorkflowStatus.DRAFT

    def test_transition_status_with_comment(self, manager):
        """Test transition with comment."""
        manager.create_item(id="test-1", type="insight", data={})

        manager.transition_status(
            "test-1",
            WorkflowStatus.PENDING_REVIEW,
            comment="Submitting for review",
            actor="user1"
        )

        item = manager.get_item("test-1")
        assert len(item.review_comments) == 1
        assert item.review_comments[0].comment == "Submitting for review"
        assert item.review_comments[0].reviewer == "user1"

    def test_submit_for_review(self, manager):
        """Test submitting item for review."""
        manager.create_item(id="test-1", type="insight", data={})

        success = manager.submit_for_review("test-1", assignee="reviewer1")

        assert success
        item = manager.get_item("test-1")
        assert item.status == WorkflowStatus.PENDING_REVIEW
        assert item.assigned_to == "reviewer1"

    def test_submit_for_review_non_draft(self, manager):
        """Test cannot submit non-draft for review."""
        manager.create_item(id="test-1", type="insight", data={}, auto_submit=True)

        # Already in pending review
        success = manager.submit_for_review("test-1")
        assert not success

    def test_start_review(self, manager):
        """Test starting a review."""
        manager.create_item(id="test-1", type="insight", data={}, auto_submit=True)

        success = manager.start_review("test-1", "reviewer1")

        assert success
        item = manager.get_item("test-1")
        assert item.status == WorkflowStatus.IN_REVIEW
        assert item.assigned_to == "reviewer1"

    def test_submit_review_approve(self, manager):
        """Test approving a review."""
        manager.create_item(id="test-1", type="insight", data={}, auto_submit=True)
        manager.start_review("test-1", "reviewer1")

        success = manager.submit_review(
            "test-1",
            ReviewAction.APPROVE,
            "Approved",
            "reviewer1"
        )

        assert success
        item = manager.get_item("test-1")
        assert item.status == WorkflowStatus.APPROVED

    def test_submit_review_reject(self, manager):
        """Test rejecting a review."""
        manager.create_item(id="test-1", type="insight", data={}, auto_submit=True)
        manager.start_review("test-1", "reviewer1")

        success = manager.submit_review(
            "test-1",
            ReviewAction.REJECT,
            "Rejected",
            "reviewer1"
        )

        assert success
        item = manager.get_item("test-1")
        assert item.status == WorkflowStatus.REJECTED

    def test_submit_review_request_revision(self, manager):
        """Test requesting revision."""
        manager.create_item(id="test-1", type="insight", data={}, auto_submit=True)
        manager.start_review("test-1", "reviewer1")

        success = manager.submit_review(
            "test-1",
            ReviewAction.REQUEST_REVISION,
            "Needs work",
            "reviewer1"
        )

        assert success
        item = manager.get_item("test-1")
        assert item.status == WorkflowStatus.REVISION_REQUESTED

    def test_publish(self, manager):
        """Test publishing an item."""
        manager.create_item(id="test-1", type="insight", data={}, auto_submit=True)
        manager.start_review("test-1", "reviewer1")
        manager.submit_review("test-1", ReviewAction.APPROVE, "OK", "reviewer1")

        success = manager.publish("test-1", "publisher1")

        assert success
        item = manager.get_item("test-1")
        assert item.status == WorkflowStatus.PUBLISHED

    def test_archive(self, manager):
        """Test archiving an item."""
        manager.create_item(id="test-1", type="insight", data={})

        success = manager.archive("test-1", "No longer needed")

        assert success
        item = manager.get_item("test-1")
        assert item.status == WorkflowStatus.ARCHIVED

    def test_list_items(self, manager):
        """Test listing items."""
        manager.create_item(id="test-1", type="insight", data={})
        manager.create_item(id="test-2", type="mission", data={})
        manager.create_item(id="test-3", type="insight", data={}, auto_submit=True)

        # All items
        items = manager.list_items()
        assert len(items) == 3

        # By status
        items = manager.list_items(status=WorkflowStatus.DRAFT)
        assert len(items) == 2

        # By type
        items = manager.list_items(type="insight")
        assert len(items) == 2

    def test_get_pending_reviews(self, manager):
        """Test getting pending reviews."""
        manager.create_item(id="test-1", type="insight", data={}, auto_submit=True)
        manager.create_item(id="test-2", type="insight", data={})
        manager.create_item(id="test-3", type="mission", data={}, auto_submit=True)

        # All pending
        pending = manager.get_pending_reviews()
        assert len(pending) == 2

    def test_get_review_history(self, manager):
        """Test getting review history."""
        manager.create_item(id="test-1", type="insight", data={}, auto_submit=True)
        manager.start_review("test-1", "reviewer1")
        manager.submit_review(
            "test-1",
            ReviewAction.APPROVE,
            "Looks good",
            "reviewer1"
        )

        history = manager.get_review_history("test-1")

        assert len(history) >= 2  # Submit comment + approve comment
        assert any(h["action"] == "approve" for h in history)

    def test_register_hook(self, manager):
        """Test registering hooks."""
        callback = MagicMock()
        manager.register_hook("on_status_change", callback)

        manager.create_item(id="test-1", type="insight", data={})
        manager.transition_status("test-1", WorkflowStatus.PENDING_REVIEW)

        assert callback.called


class TestHelperFunctions:
    """Test helper functions."""

    @patch("src.core.workflow.get_workflow_manager")
    def test_create_insight_workflow(self, mock_get_manager):
        """Test create_insight_workflow helper."""
        mock_manager = MagicMock()
        mock_get_manager.return_value = mock_manager

        create_insight_workflow(
            "insight-1",
            {"title": "Test"},
            auto_submit=True
        )

        mock_manager.create_item.assert_called_once_with(
            id="insight-1",
            type="insight",
            data={"title": "Test"},
            auto_submit=True
        )

    @patch("src.core.workflow.get_workflow_manager")
    def test_create_mission_workflow(self, mock_get_manager):
        """Test create_mission_workflow helper."""
        mock_manager = MagicMock()
        mock_get_manager.return_value = mock_manager

        create_mission_workflow(
            "mission-1",
            {"title": "Test"},
            auto_submit=False
        )

        mock_manager.create_item.assert_called_once_with(
            id="mission-1",
            type="mission",
            data={"title": "Test"},
            auto_submit=False
        )

    @patch("src.core.workflow.get_workflow_manager")
    def test_approve_item_helper(self, mock_get_manager):
        """Test approve_item helper."""
        mock_manager = MagicMock()
        mock_item = MagicMock()
        mock_item.status = WorkflowStatus.PENDING_REVIEW
        mock_manager.get_item.return_value = mock_item
        mock_get_manager.return_value = mock_manager

        approve_item("test-1", "reviewer1", "Approved")

        mock_manager.start_review.assert_called_once()
        mock_manager.submit_review.assert_called_once_with(
            "test-1",
            ReviewAction.APPROVE,
            "Approved",
            "reviewer1"
        )

    @patch("src.core.workflow.get_workflow_manager")
    def test_reject_item_helper(self, mock_get_manager):
        """Test reject_item helper."""
        mock_manager = MagicMock()
        mock_item = MagicMock()
        mock_item.status = WorkflowStatus.PENDING_REVIEW
        mock_manager.get_item.return_value = mock_item
        mock_get_manager.return_value = mock_manager

        reject_item("test-1", "reviewer1", "Rejected")

        mock_manager.start_review.assert_called_once()
        mock_manager.submit_review.assert_called_once_with(
            "test-1",
            ReviewAction.REJECT,
            "Rejected",
            "reviewer1"
        )

    @patch("src.core.workflow.get_workflow_manager")
    def test_request_revision_helper(self, mock_get_manager):
        """Test request_revision helper."""
        mock_manager = MagicMock()
        mock_item = MagicMock()
        mock_item.status = WorkflowStatus.PENDING_REVIEW
        mock_manager.get_item.return_value = mock_item
        mock_get_manager.return_value = mock_manager

        request_revision("test-1", "reviewer1", "Needs more details")

        mock_manager.start_review.assert_called_once()
        mock_manager.submit_review.assert_called_once_with(
            "test-1",
            ReviewAction.REQUEST_REVISION,
            "Needs more details",
            "reviewer1"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
